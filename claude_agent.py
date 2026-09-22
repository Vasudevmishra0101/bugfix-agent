import re

from openai import OpenAI

import config

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=config.OPENROUTER_API_KEY,
)

_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_+-]*\n(.*)\n```$", re.DOTALL)


def _strip_code_fences(text):
    """Free-tier models routinely wrap output in ```lang ... ``` fences
    despite being told not to; strip them so callers get raw code/diff."""
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    return match.group(1) if match else stripped


def _chat(system_prompt, user_prompt, strip_fences=False):
    response = client.chat.completions.create(
        model=config.MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content
    return _strip_code_fences(content) if strip_fences else content


def analyze_bug(issue_title, issue_body, context_block):
    system_prompt = (
        "You are a senior software engineer diagnosing a bug. "
        "Given the issue report and relevant source files, identify the root "
        "cause. Be specific: name the file, function, and the exact reason "
        "it's wrong. Do not propose a fix yet."
    )
    user_prompt = (
        f"Issue title: {issue_title}\n\n"
        f"Issue body:\n{issue_body}\n\n"
        f"Relevant code:\n{context_block}"
    )
    return _chat(system_prompt, user_prompt)


def generate_patch(issue_title, issue_body, context_block, root_cause_analysis):
    system_prompt = (
        "You are a senior software engineer fixing a bug. Given the root "
        "cause analysis and the relevant source files, write a minimal fix "
        "as a unified diff (git diff format, with proper --- / +++ / @@ "
        "headers) so it can be applied with `git apply`. Output only the "
        "diff, no explanation, no markdown fences."
    )
    user_prompt = (
        f"Issue title: {issue_title}\n\n"
        f"Issue body:\n{issue_body}\n\n"
        f"Root cause analysis:\n{root_cause_analysis}\n\n"
        f"Relevant code:\n{context_block}"
    )
    return _chat(system_prompt, user_prompt, strip_fences=True)


def generate_tests(issue_title, issue_body, patch_diff, context_block):
    system_prompt = (
        "You are a senior software engineer writing regression tests. Given "
        "the bug report and the patch that fixes it, write pytest tests "
        "that fail without the patch and pass with it. Output only valid "
        "Python code for a single test file, no explanation, no markdown "
        "fences."
    )
    user_prompt = (
        f"Issue title: {issue_title}\n\n"
        f"Issue body:\n{issue_body}\n\n"
        f"Patch:\n{patch_diff}\n\n"
        f"Relevant code:\n{context_block}"
    )
    return _chat(system_prompt, user_prompt, strip_fences=True)


def explain_simply(issue_title, analysis, patch_diff):
    """Plain-language bug + fix summary for a non-technical audience (the
    live dashboard shows this instead of the raw diff/analysis)."""
    system_prompt = (
        "You explain software bugs to a non-technical audience (e.g. a "
        "product manager or a recruiter watching a demo). Given a bug "
        "title, a technical root-cause analysis, and the code patch that "
        "fixed it, write two short plain-language explanations. No jargon, "
        "no code, no file names, no function names — describe the "
        "user-visible behavior only. 1-3 short sentences each. "
        "Respond with only a JSON object: "
        '{"plain_bug": "<what was wrong, in plain language>", '
        '"plain_fix": "<how it was fixed, in plain language>"}.'
    )
    user_prompt = (
        f"Bug title: {issue_title}\n\n"
        f"Technical root cause:\n{analysis}\n\n"
        f"Patch:\n{patch_diff}"
    )
    return _chat(system_prompt, user_prompt, strip_fences=True)


def revise_patch_from_comment(issue_title, patch_diff, review_comment, context_block):
    system_prompt = (
        "You are a senior software engineer responding to code review "
        "feedback on your own patch. First decide whether the comment "
        "requests a real, actionable change (vs. a question, nit, or "
        "approval). "
        "Respond with a JSON object: "
        '{"actionable": true|false, "revised_patch": "<diff or null>", '
        '"reasoning": "<one sentence>"}. '
        "If actionable is true, revised_patch must be a full unified diff "
        "incorporating the requested change. If false, set revised_patch to "
        "null."
    )
    user_prompt = (
        f"Issue title: {issue_title}\n\n"
        f"Current patch:\n{patch_diff}\n\n"
        f"Reviewer comment:\n{review_comment}\n\n"
        f"Relevant code:\n{context_block}"
    )
    return _chat(system_prompt, user_prompt, strip_fences=True)
