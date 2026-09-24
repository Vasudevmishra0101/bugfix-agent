from github import Github

import config

_gh = Github(config.GITHUB_TOKEN)
_repo = _gh.get_repo(config.REPO_NAME)


def get_open_issues(label="bug"):
    return list(_repo.get_issues(state="open", labels=[label]))


def find_issue_by_title(title, state="all"):
    """Guards the autonomous scanner against re-filing the same bug on
    every run — checks open AND closed issues, since a closed-but-unmerged
    or already-fixed bug shouldn't be re-reported either."""
    for issue in _repo.get_issues(state=state):
        if issue.title.strip().lower() == title.strip().lower():
            return issue
    return None


def create_bug_issue(title, body, label="bug"):
    labels = [l.name for l in _repo.get_labels()]
    if label not in labels:
        _repo.create_label(name=label, color="d73a4a")
    return _repo.create_issue(title=title, body=body, labels=[label])


def create_branch(branch_name, base_branch="main"):
    base_ref = _repo.get_git_ref(f"heads/{base_branch}")
    _repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_ref.object.sha)
    return branch_name


def commit_file_change(branch_name, file_path, new_content, commit_message):
    contents = _repo.get_contents(file_path, ref=branch_name)
    _repo.update_file(
        path=file_path,
        message=commit_message,
        content=new_content,
        sha=contents.sha,
        branch=branch_name,
    )


def open_pull_request(branch_name, title, body, base_branch="main"):
    return _repo.create_pull(
        title=title, body=body, head=branch_name, base=base_branch
    )


def get_pr_comments(pr_number):
    pr = _repo.get_pull(pr_number)
    return list(pr.get_issue_comments())


def is_pr_approved(pr_number):
    pr = _repo.get_pull(pr_number)
    reviews = pr.get_reviews()
    return any(review.state == "APPROVED" for review in reviews)
