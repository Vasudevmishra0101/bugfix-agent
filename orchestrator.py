import time

import claude_agent
import code_context
import config
import github_client
import test_runner


def process_issue(issue):
    """Runs analyze -> patch -> tests -> local test run for one GitHub issue.
    Committing the patch, pushing, and opening the PR are still manual steps
    for now (see CLAUDE agent.md next steps) — this prints the generated
    output so it can be reviewed before anything touches the repo."""
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

    test_file_path = f"test_generated_issue_{issue.number}.py"
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write(tests)

    print(f"\n--- Running generated tests ({test_file_path}) ---")
    passed, output = test_runner.run_tests(test_file_path)
    print(output)
    print("PASSED" if passed else "FAILED")

    return {
        "issue": issue,
        "analysis": analysis,
        "patch": patch,
        "tests": tests,
        "tests_passed": passed,
    }


def poll_pr_for_comments(pr_number, context_block, poll_interval_seconds=60):
    """After a PR is open, watch for reviewer comments and decide whether to
    revise the patch. Stops on approval or after MAX_ITERATIONS."""
    seen_comment_ids = set()

    for iteration in range(config.MAX_ITERATIONS):
        if github_client.is_pr_approved(pr_number):
            print(f"PR #{pr_number} approved. Done.")
            return

        comments = github_client.get_pr_comments(pr_number)
        new_comments = [c for c in comments if c.id not in seen_comment_ids]
        seen_comment_ids.update(c.id for c in comments)

        for comment in new_comments:
            print(f"\n--- New review comment on PR #{pr_number} ---\n{comment.body}")
            # Requires the current patch text to be tracked by the caller;
            # left as a manual wiring point until auto-revision is enabled.

        print(f"[iteration {iteration + 1}/{config.MAX_ITERATIONS}] "
              f"waiting {poll_interval_seconds}s for reviewer activity...")
        time.sleep(poll_interval_seconds)

    print(f"Hit MAX_ITERATIONS ({config.MAX_ITERATIONS}) without approval. "
          f"Leaving PR #{pr_number} for human follow-up.")


def main():
    issues = github_client.get_open_issues(label="bug")
    print(f"Found {len(issues)} open bug issue(s).")

    for issue in issues:
        process_issue(issue)


if __name__ == "__main__":
    main()
