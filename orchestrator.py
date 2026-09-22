import json
import os
import re
import subprocess
import time

import claude_agent
import code_context
import config
import github_client
import test_runner

_PATCH_TARGET_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def _target_file_from_patch(patch_diff):
    match = _PATCH_TARGET_RE.search(patch_diff)
    return match.group(1) if match else None


def _target_dir_from_patch(patch_diff):
    """Generated tests import the patched module by name, so they need to
    live next to it (e.g. sample_app/) rather than at the repo root."""
    target_file = _target_file_from_patch(patch_diff)
    return os.path.dirname(target_file) if target_file else "."


def _run_git(args):
    result = subprocess.run(["git"] + args, capture_output=True, text=True)
    return result.returncode == 0, (result.stdout + result.stderr)


def _naive_line_replace(patch_diff, target_file):
    """Last-resort fallback: extract the removed/added line blocks from the
    diff, ignoring line numbers and context entirely, and do an exact text
    substitution in the target file. Handles the common case this free
    model keeps producing — a correct single-hunk change wrapped in a diff
    whose context lines don't quite match (e.g. a dropped blank line) —
    without needing the surrounding context to line up at all. Only applies
    when the removed block appears exactly once, so it can't silently patch
    the wrong spot."""
    removed, added = [], []
    for line in patch_diff.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    if not removed:
        return False, "no removed lines found in patch"

    removed_block = "\n".join(removed)
    added_block = "\n".join(added)

    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    count = content.count(removed_block)
    if count != 1:
        return False, (
            f"removed block found {count} time(s) in {target_file}, "
            f"need exactly 1 to apply safely"
        )

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content.replace(removed_block, added_block, 1))
    return True, "applied via naive line-replace fallback"


def apply_patch(patch_diff, target_file=None):
    """Free-tier models frequently produce diffs with slightly-off context
    (e.g. a dropped blank line) that are still unambiguous fixes. Try
    strict `git apply` first, then classic GNU `patch` with fuzz (tolerates
    that drift via approximate context matching), then a naive exact-text
    line-replace as a last resort."""
    patch_file = ".patchpilot_tmp.patch"
    with open(patch_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(patch_diff if patch_diff.endswith("\n") else patch_diff + "\n")

    ok, output = _run_git(["apply", "--whitespace=fix", patch_file])
    if ok:
        os.remove(patch_file)
        return True, output
    combined_output = output

    patch_exe = os.path.join(
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        "Git", "usr", "bin", "patch.exe",
    )
    if os.path.exists(patch_exe):
        result = subprocess.run(
            [patch_exe, "-p1", "--fuzz=3", "--no-backup-if-mismatch",
             "-i", patch_file],
            capture_output=True, text=True,
        )
        reject_file = f"{target_file}.rej" if target_file else None
        if result.returncode == 0:
            os.remove(patch_file)
            return True, f"(git apply failed, patch --fuzz succeeded)\n{result.stdout}"
        if reject_file and os.path.exists(reject_file):
            os.remove(reject_file)
        combined_output += f"\n--- patch --fuzz also failed ---\n{result.stdout}{result.stderr}"

    os.remove(patch_file)

    if target_file:
        ok, naive_output = _naive_line_replace(patch_diff, target_file)
        if ok:
            return True, f"(git apply and patch --fuzz failed) {naive_output}"
        combined_output += f"\n--- naive line-replace also failed ---\n{naive_output}"

    return False, combined_output


def open_pr_for_fix(issue, analysis, target_file, test_file_path):
    """Commit the verified patch + tests to a fresh branch, push it, and open
    a PR. Only called after the patch has been applied locally and the
    generated tests pass against the patched code — this is the automated
    part; a human is still the merge gate (see CLAUDE agent.md)."""
    branch_name = f"patchpilot/issue-{issue.number}"

    ok, output = _run_git(["checkout", "-b", branch_name])
    if not ok:
        print(f"Could not create branch {branch_name}:\n{output}")
        return None

    ok, output = _run_git(["add", target_file, test_file_path])
    if ok:
        ok, output = _run_git([
            "commit", "-m", f"Fix #{issue.number}: {issue.title}",
        ])
    if not ok:
        print(f"Commit failed:\n{output}")
        _run_git(["checkout", "main"])
        _run_git(["branch", "-D", branch_name])
        return None

    ok, output = _run_git(["push", "-u", "origin", branch_name])
    if not ok:
        print(f"Push failed:\n{output}")
        _run_git(["checkout", "main"])
        return None

    pr_body = (
        f"Closes #{issue.number}\n\n"
        f"## Root cause\n{analysis}\n\n"
        f"---\n_Patch, tests, and this PR were generated by PatchPilot. "
        f"Generated tests were verified to fail before this patch and pass "
        f"after it. Human review required before merge._"
    )
    pr = github_client.open_pull_request(
        branch_name, f"Fix #{issue.number}: {issue.title}", pr_body
    )
    print(f"Opened PR #{pr.number}: {pr.html_url}")

    _run_git(["checkout", "main"])
    return pr


def process_issue(issue, auto_push=True):
    """Runs analyze -> patch -> tests -> verify-before -> apply -> verify-after
    -> (commit, push, open PR). The PR only gets opened if the generated
    tests fail on the unpatched code and pass on the patched code — that's
    the pipeline's proof the fix is real before a human ever looks at it.
    A human is still the merge gate; nothing here auto-merges."""
    print(f"\n=== Issue #{issue.number}: {issue.title} ===")

    relevant_files = code_context.find_relevant_files(issue.title, issue.body or "")
    context_block = code_context.format_context_block(relevant_files)
    print(f"Found {len(relevant_files)} relevant file(s): "
          f"{[path for path, _ in relevant_files]}")

    print("\n--- Root cause analysis ---")
    analysis = claude_agent.analyze_bug(issue.title, issue.body or "", context_block)
    print(analysis)

    print("\n--- Generated patch (unified diff) ---")
    patch = claude_agent.generate_patch(
        issue.title, issue.body or "", context_block, analysis
    )
    print(patch)

    print("\n--- Generated tests ---")
    tests = claude_agent.generate_tests(issue.title, issue.body or "", patch, context_block)
    print(tests)

    target_file = _target_file_from_patch(patch)
    target_dir = _target_dir_from_patch(patch)
    test_file_path = os.path.join(target_dir, f"test_generated_issue_{issue.number}.py")
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write(tests)

    result = {
        "issue": issue, "analysis": analysis, "patch": patch, "tests": tests,
        "tests_passed_before": None, "tests_passed_after": None,
        "patch_applied": False, "pr": None,
    }

    print(f"\n--- Running generated tests against unpatched code ({test_file_path}) ---")
    passed_before, output_before = test_runner.run_tests(test_file_path)
    print(output_before)
    result["tests_passed_before"] = passed_before
    if passed_before:
        print("WARNING: tests already pass without the patch — they may not "
              "actually cover the bug. Skipping auto-push for human review.")
        return result
    print("Tests fail on unpatched code, as expected.")

    if not target_file:
        print("Could not determine target file from patch header; "
              "skipping apply/push.")
        return result

    print("\n--- Applying patch ---")
    applied, apply_output = apply_patch(patch, target_file)
    print(apply_output or "(applied cleanly)")
    result["patch_applied"] = applied
    if not applied:
        print("Patch failed to apply. Leaving working tree untouched for "
              "human review.")
        os.remove(test_file_path)
        return result

    print("\n--- Running generated tests against patched code ---")
    passed_after, output_after = test_runner.run_tests(test_file_path)
    print(output_after)
    result["tests_passed_after"] = passed_after

    if not passed_after:
        print("Tests still fail after applying the patch — the fix is not "
              "verified. Reverting and skipping PR.")
        _run_git(["checkout", "--", target_file])
        os.remove(test_file_path)
        return result

    print("Tests pass after the patch. Fix verified.")

    if auto_push:
        result["pr"] = open_pr_for_fix(issue, analysis, target_file, test_file_path)
    else:
        print("auto_push=False: leaving verified changes uncommitted locally.")

    result["context_block"] = context_block
    result["target_file"] = target_file
    result["test_file_path"] = test_file_path
    return result


def _apply_revision(branch_name, target_file, revised_patch):
    """Reset target_file to main's original (pre-fix) version, apply the
    revised patch fresh, and verify. Returns True and updates the working
    tree/commit only if the revision actually fixes things."""
    ok, output = _run_git(["checkout", branch_name])
    if not ok:
        print(f"Could not check out {branch_name}:\n{output}")
        return False

    _run_git(["checkout", "main", "--", target_file])
    applied, apply_output = apply_patch(revised_patch, target_file)
    if not applied:
        print(f"Revised patch failed to apply:\n{apply_output}")
        _run_git(["checkout", "HEAD", "--", target_file])
        return False
    return True


def poll_pr_for_comments(pr, issue, context_block, target_file, test_file_path,
                          poll_interval_seconds=60):
    """After a PR is open, watch for reviewer comments and decide whether to
    revise the patch. On an actionable comment, regenerates the patch,
    re-verifies it against the generated tests, and pushes the revision to
    the same branch (which updates the PR in place). Stops on approval or
    after MAX_ITERATIONS — a hard cap so a stubborn disagreement can't burn
    API credits forever. Either way, a human makes the final merge call."""
    seen_comment_ids = set()
    branch_name = pr.head.ref

    for iteration in range(config.MAX_ITERATIONS):
        if github_client.is_pr_approved(pr.number):
            print(f"PR #{pr.number} approved. Done.")
            return

        comments = github_client.get_pr_comments(pr.number)
        new_comments = [c for c in comments if c.id not in seen_comment_ids]
        seen_comment_ids.update(c.id for c in comments)

        for comment in new_comments:
            print(f"\n--- New review comment on PR #{pr.number} ---\n{comment.body}")

            with open(os.path.join(target_file), "r", encoding="utf-8") as f:
                current_patched_content = f.read()

            raw = claude_agent.revise_patch_from_comment(
                issue.title, current_patched_content, comment.body, context_block
            )
            try:
                decision = json.loads(raw)
            except json.JSONDecodeError:
                print(f"Could not parse revision decision as JSON, skipping:\n{raw}")
                continue

            if not decision.get("actionable"):
                print(f"Not actionable: {decision.get('reasoning', '(no reasoning given)')}")
                continue

            revised_patch = decision.get("revised_patch")
            if not revised_patch:
                print("Marked actionable but no revised_patch provided, skipping.")
                continue

            print(f"Actionable: {decision.get('reasoning', '')}")
            if not _apply_revision(branch_name, target_file, revised_patch):
                continue

            passed, output = test_runner.run_tests(test_file_path)
            print(output)
            if not passed:
                print("Revised patch fails generated tests — reverting, "
                      "not pushing.")
                _run_git(["checkout", "HEAD", "--", target_file])
                continue

            _run_git(["add", target_file])
            _run_git(["commit", "-m", f"Address review feedback on #{issue.number}"])
            ok, output = _run_git(["push", "origin", branch_name])
            if ok:
                print(f"Pushed revision to {branch_name} (PR #{pr.number} updated).")
            else:
                print(f"Push failed:\n{output}")

        print(f"[iteration {iteration + 1}/{config.MAX_ITERATIONS}] "
              f"waiting {poll_interval_seconds}s for reviewer activity...")
        time.sleep(poll_interval_seconds)

    print(f"Hit MAX_ITERATIONS ({config.MAX_ITERATIONS}) without approval. "
          f"Leaving PR #{pr.number} for human follow-up.")
    _run_git(["checkout", "main"])


def main():
    issues = github_client.get_open_issues(label="bug")
    print(f"Found {len(issues)} open bug issue(s).")

    for issue in issues:
        result = process_issue(issue)
        if result.get("pr"):
            poll_pr_for_comments(
                result["pr"], issue, result["context_block"],
                result["target_file"], result["test_file_path"],
            )


if __name__ == "__main__":
    main()
