"""GitHub repository inventory adapter (MC-CULTIVATION-APPS-01).

Read-only by design. Mission Control never mutates GitHub repositories,
never commits files, never clones hundreds of repositories and never
executes application launch commands during discovery.

Two fetch paths, both read-only:
- ``gh`` CLI (``gh repo list``), reusing the operator's existing
  authenticated session. No token handling required.
- REST API (``GET /user/repos`` with pagination) using a deliberately
  configured read-only token named by the source config (``token_env``).

Sync merges remote facts into ``cultivation_github_repos`` (keyed by the
stable GitHub node id, never the name) and reconciles owner judgement rows
in ``cultivation_repo_states`` (``repo_id = 'gh-' + node_id``). Owner
decisions (qualification, lifecycle, classification, rationale) are never
overwritten: only rows with ``decided_by == 'undecided'`` receive inferred
updates, and inferred updates never qualify anything for counting.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import Any, Callable


class GitHubError(Exception):
    """Base class carrying a machine-readable status for the source row."""

    status = "unavailable"


class GitHubAuthError(GitHubError):
    status = "auth_error"


class GitHubRateLimitError(GitHubError):
    status = "rate_limited"


class GitHubUnavailable(GitHubError):
    status = "unavailable"


GH_LIST_FIELDS = (
    "id,nameWithOwner,name,owner,url,description,visibility,"
    "isPrivate,isArchived,isFork,primaryLanguage,languages,"
    "repositoryTopics,pushedAt,createdAt,updatedAt,defaultBranchRef"
)

GH_REPO_PREFIX = "gh-"
GH_UID_PREFIX = "github:"


def gh_repo_id(node_id: str) -> str:
    return GH_REPO_PREFIX + str(node_id)


def gh_repo_uid(node_id: str) -> str:
    return GH_UID_PREFIX + str(node_id)


def _language_name(value: Any) -> str | None:
    if isinstance(value, dict):
        name = value.get("name")
        return str(name) if name else None
    return None


def _topic_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        nodes = value.get("nodes")
        if isinstance(nodes, list):
            names = []
            for node in nodes:
                if isinstance(node, dict) and node.get("name"):
                    names.append(str(node["name"]))
                elif isinstance(node, dict) and isinstance(node.get("topic"), dict):
                    topic = node["topic"].get("name")
                    if topic:
                        names.append(str(topic))
            return names
        return []
    if isinstance(value, list):
        names = []
        for entry in value:
            if isinstance(entry, dict) and entry.get("name"):
                names.append(str(entry["name"]))
            elif isinstance(entry, str):
                names.append(entry)
        return names
    return []


def normalize_repo(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one ``gh``/REST repository object into the snapshot shape."""
    node_id = str(raw.get("node_id") or raw.get("id") or "").strip()
    full_name = str(raw.get("full_name") or raw.get("nameWithOwner") or "").strip()
    owner = ""
    owner_raw = raw.get("owner")
    if isinstance(owner_raw, dict):
        owner = str(owner_raw.get("login") or "")
    elif isinstance(owner_raw, str):
        owner = owner_raw
    if not owner and "/" in full_name:
        owner = full_name.split("/", 1)[0]
    name = str(raw.get("name") or (full_name.split("/", 1)[-1] if full_name else "")).strip()
    visibility = str(raw.get("visibility") or ("PRIVATE" if raw.get("isPrivate") or raw.get("private") else "PUBLIC")).upper()
    languages_raw = raw.get("languages") or []
    languages: list[str] = []
    if isinstance(languages_raw, dict) and isinstance(languages_raw.get("nodes"), list):
        for node in languages_raw["nodes"]:
            if isinstance(node, dict) and node.get("name"):
                languages.append(str(node["name"]))
    elif isinstance(languages_raw, list):
        for entry in languages_raw:
            if isinstance(entry, dict):
                node = entry.get("node") if isinstance(entry.get("node"), dict) else entry
                if isinstance(node, dict) and node.get("name"):
                    languages.append(str(node["name"]))
            elif isinstance(entry, str):
                languages.append(entry)
    branch_raw = raw.get("default_branch") or raw.get("defaultBranchRef")
    if isinstance(branch_raw, dict):
        branch = branch_raw.get("name")
    else:
        branch = branch_raw
    numeric_id = raw.get("databaseId")
    if numeric_id is None and isinstance(raw.get("id"), int):
        numeric_id = raw.get("id")
    try:
        numeric = int(numeric_id) if numeric_id is not None else None
    except (TypeError, ValueError):
        numeric = None
    return {
        "node_id": node_id,
        "numeric_id": numeric,
        "owner": owner,
        "name": name,
        "full_name": full_name,
        "url": str(raw.get("html_url") or raw.get("url") or ""),
        "description": str(raw.get("description") or ""),
        "visibility": visibility,
        "is_private": bool(raw.get("isPrivate", raw.get("private", visibility == "PRIVATE"))),
        "is_fork": bool(raw.get("isFork", raw.get("fork", False))),
        "is_archived": bool(raw.get("isArchived", raw.get("archived", False))),
        "language": _language_name(raw.get("primaryLanguage") or raw.get("language")),
        "languages": languages,
        "topics": _topic_names(raw.get("repositoryTopics") or raw.get("topics")),
        "default_branch": str(branch) if branch else None,
        "pushed_at": raw.get("pushedAt") or raw.get("pushed_at"),
        "created_at": raw.get("createdAt") or raw.get("created_at"),
        "updated_at": raw.get("updatedAt") or raw.get("updated_at"),
    }


# ----------------------------------------------------------------------
# Inference (advisory only — never qualifies, never counts)


_BOOK_NAMES = {
    "language", "inference", "math", "project-language", "applied-language",
    "next-books",
}

_BOOK_HINTS = ("book", "manuscript", "novel", "memoir", "textbook", "workbook")

_APPLICATION_HINTS = (
    "builder", "writer", "workbench", "-app", "app-", "translator",
    "assistant", "engine", "cocoder", "bookbuilder",
)

_WEBSITE_HINTS = ("programmer.ie", "-site", "website", "-web", ".github.io")

_TUTORIAL_HINTS = (
    "example", "tutorial", "course", "cookbook", "demo", "sample",
    "playground", "kata", "exercise", "starter", "-101", "101-",
)

_DATASET_HINTS = (
    "dataset", "data-", "-data", "arxiv", "zotero", "corpus", "benchmark",
)

_RESEARCH_HINTS = (
    "research", "experiment", "thesis", "paper", "study", "zeromodel",
    "distillation",
)

_LIBRARY_HINTS = ("-lib", "lib-", "sdk", "-kit", "kit-", "bookkit", "framework")

_INFRA_HINTS = (
    "runtime", "runtimes", "server", "worker", "sidecar", "infra",
    "deploy", "pipeline", "runner",
)

_CODE_LANGUAGES = {
    "Python", "TypeScript", "JavaScript", "Java", "Go", "Rust", "C", "C++",
    "C#", "Kotlin", "Swift", "Ruby", "PHP", "Shell", "PowerShell", "Svelte",
    "HTML", "CSS",
}


def _matches(haystack: str, hints: tuple[str, ...]) -> bool:
    return any(hint in haystack for hint in hints)


def infer_classification(repo: dict[str, Any]) -> tuple[str, str]:
    """Advisory classification; uncertain results stay ``unclassified``.

    Returns (classification, rationale). Never raises for missing fields.
    """
    name = str(repo.get("name") or "")
    lowered = name.lower()
    description = str(repo.get("description") or "").lower()
    topics = [str(topic).lower() for topic in (repo.get("topics") or [])]
    language = repo.get("language")
    haystack = f"{lowered} {description} {' '.join(topics)}"

    if lowered in _BOOK_NAMES or lowered.endswith(".notebooks"):
        return "book", f"Inferred book: repository name '{name}' matches a known book-associated project."
    if _matches(haystack, _WEBSITE_HINTS):
        return "website", f"Inferred website: name '{name}' suggests a site or web presence."
    if _matches(haystack, _TUTORIAL_HINTS):
        return "tutorial", f"Inferred tutorial: name '{name}' suggests examples or teaching material."
    if _matches(haystack, _DATASET_HINTS):
        return "dataset", f"Inferred dataset: name '{name}' suggests data rather than an application."
    if _matches(haystack, _RESEARCH_HINTS):
        return "research", f"Inferred research: name '{name}' suggests research or experimentation."
    if _matches(haystack, _LIBRARY_HINTS) or "library" in topics or "framework" in topics:
        return "library", f"Inferred library: name/topics of '{name}' suggest a reusable library or framework."
    if _matches(haystack, _INFRA_HINTS):
        return "infrastructure", f"Inferred infrastructure: name '{name}' suggests runtime or platform plumbing."
    if _matches(haystack, _APPLICATION_HINTS):
        return "application", (
            f"Inferred application: name '{name}' suggests a working tool or product; "
            "pending owner review.")
    if _matches(haystack, _BOOK_HINTS) or "book" in topics:
        return "book", f"Inferred book: name/description/topics of '{name}' suggest a book or publication project."
    if language == "Jupyter Notebook":
        return "experiment", (
            f"Inferred experiment: '{name}' is notebook-based; notebooks here are usually "
            "experiments or analysis, but review is required (it may back a book)."
        )
    if language in _CODE_LANGUAGES:
        return "application", (
            f"Inferred application: '{name}' is primarily {language}; treated as a candidate "
            "software application pending owner review."
        )
    if "jupyter-notebook" in topics:
        return "experiment", (
            f"Inferred experiment: '{name}' is tagged jupyter-notebook; review whether it backs a book."
        )
    return "unclassified", (
        f"No confident signal for '{name}': left unclassified for owner review. "
        f"Observed language={language or 'unknown'}, topics={', '.join(topics) or 'none'}."
    )


def infer_lifecycle(repo: dict[str, Any]) -> tuple[str, str]:
    if repo.get("is_archived"):
        return "archived", "GitHub marks this repository archived; lifecycle follows the observed fact."
    return "unreviewed", "New GitHub observation; lifecycle not yet reviewed by the owner."


# ----------------------------------------------------------------------
# Fetchers (read-only)


def fetch_via_gh_cli(*, limit: int = 1000, owner: str | None = None,
                      timeout: int = 120) -> list[dict[str, Any]]:
    """List repositories via the ``gh`` CLI (reuses the operator's login)."""
    command = ["gh", "repo", "list", "--limit", str(max(1, int(limit or 1000))),
               "--json", GH_LIST_FIELDS]
    if owner:
        command.append(owner)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout,
            shell=False, check=False)
    except FileNotFoundError as exc:
        raise GitHubUnavailable("GitHub CLI (gh) is not installed or not on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitHubUnavailable(f"GitHub CLI timed out after {timeout}s.") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        lowered = detail.lower()
        if "auth" in lowered or "login" in lowered or "token" in lowered:
            raise GitHubAuthError(
                "GitHub CLI is not authenticated. Run 'gh auth login'; "
                f"kept the last inventory. Detail: {detail[:300]}")
        raise GitHubUnavailable(
            f"GitHub CLI failed (exit {completed.returncode}); kept the last "
            f"inventory. Detail: {detail[:300]}")
    try:
        raw = json.loads(completed.stdout or "[]")
    except ValueError as exc:
        raise GitHubUnavailable("GitHub CLI returned unreadable JSON; kept the last inventory.") from exc
    if not isinstance(raw, list):
        raise GitHubUnavailable("GitHub CLI returned an unexpected shape; kept the last inventory.")
    return [normalize_repo(item) for item in raw if isinstance(item, dict)]


def fetch_via_rest(*, token: str, account: str | None = None,
                   per_page: int = 100, max_pages: int = 20,
                   timeout: int = 30) -> list[dict[str, Any]]:
    """List ``/user/repos`` with pagination (read-only token, never stored)."""
    import httpx

    headers = {"Accept": "application/vnd.github+json",
               "Authorization": f"Bearer {token}",
               "X-GitHub-Api-Version": "2022-11-28"}
    params_base = {"per_page": str(max(1, min(int(per_page or 100), 100))),
                   "affiliation": "owner", "sort": "full_name"}
    repos: list[dict[str, Any]] = []
    with httpx.Client(timeout=timeout) as client:
        for page in range(1, int(max_pages or 20) + 1):
            params = dict(params_base)
            params["page"] = str(page)
            try:
                response = client.get("https://api.github.com/user/repos",
                                      headers=headers, params=params)
            except Exception as exc:
                raise GitHubUnavailable(
                    f"GitHub API unreachable ({type(exc).__name__}); kept the last inventory.") from exc
            if response.status_code == 401:
                raise GitHubAuthError(
                    "GitHub token rejected (401). Check the configured token; kept the last inventory.")
            if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
                reset = response.headers.get("X-RateLimit-Reset", "")
                raise GitHubRateLimitError(
                    f"GitHub rate limit exhausted (resets at {reset or 'unknown'}); "
                    "kept the last inventory.")
            if response.status_code >= 400:
                raise GitHubUnavailable(
                    f"GitHub API returned {response.status_code}; kept the last inventory.")
            try:
                batch = response.json()
            except ValueError as exc:
                raise GitHubUnavailable("GitHub API returned unreadable JSON; kept the last inventory.") from exc
            if not batch:
                break
            repos.extend(normalize_repo(item) for item in batch if isinstance(item, dict))
            if len(batch) < int(params_base["per_page"]):
                break
            if account:
                repos = [repo for repo in repos
                         if not repo.get("owner") or repo.get("owner") == account]
    return repos


Fetcher = Callable[[], list[dict[str, Any]]]


def resolve_fetcher(config: dict[str, Any]) -> Fetcher:
    """Choose the read-only fetch path from the source config.

    ``config`` supports ``account``, ``auth`` (``"gh_cli"`` default or
    ``"token"``), ``token_env`` (default ``GITHUB_TOKEN``) and ``limit``.
    """
    if not isinstance(config, dict):
        config = {}
    auth = str(config.get("auth") or "gh_cli").strip().lower()
    account = str(config.get("account") or "").strip() or None
    limit = int(config.get("limit") or 1000)
    if auth == "token":
        token_env = str(config.get("token_env") or "GITHUB_TOKEN").strip()
        token = os.environ.get(token_env, "")
        if not token:
            def _missing() -> list[dict[str, Any]]:
                raise GitHubAuthError(
                    f"GitHub token env '{token_env}' is not set; kept the last inventory.")
            return _missing

        def _rest() -> list[dict[str, Any]]:
            return fetch_via_rest(token=token, account=account)

        return _rest

    def _cli() -> list[dict[str, Any]]:
        return fetch_via_gh_cli(limit=limit, owner=account)

    return _cli


def fingerprint(repos: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for repo in sorted(repos, key=lambda item: item.get("node_id") or ""):
        digest.update(str(repo.get("node_id") or "").encode("utf-8"))
        digest.update(str(repo.get("pushed_at") or "").encode("utf-8"))
        digest.update(str(repo.get("full_name") or "").encode("utf-8"))
    return digest.hexdigest()[:24]
