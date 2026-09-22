import os
import re

CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb"}
IGNORE_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv", "env"}


def _tokenize(text):
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text.lower()))


def find_relevant_files(issue_title, issue_body, repo_path=".", max_files=5):
    """Keyword-overlap search over repo source files. Not RAG/embeddings —
    deliberately simple, good enough at small-repo scale."""
    keywords = _tokenize(issue_title) | _tokenize(issue_body)
    scored = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for name in files:
            if os.path.splitext(name)[1] not in CODE_EXTENSIONS:
                continue
            path = os.path.join(root, name)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except OSError:
                continue

            file_tokens = _tokenize(content) | _tokenize(name)
            score = len(keywords & file_tokens)
            if score > 0:
                scored.append((score, path, content))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [(path, content) for _, path, content in scored[:max_files]]


def format_context_block(relevant_files):
    """Turn [(path, content)] into a single string block for the LLM prompt."""
    blocks = []
    for path, content in relevant_files:
        blocks.append(f"### File: {path}\n```\n{content}\n```")
    return "\n\n".join(blocks)
