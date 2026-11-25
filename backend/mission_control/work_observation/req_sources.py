"""WORK-OUTCOME-01 W6A: deterministic requirement-source resolution.

Read-only. Maps a Work Episode to candidate authorizing artifacts in the
target repository (programme docs, specs, reviews, commissions) plus the
git history that touched them. Never assigns authority by itself: a repo
document is not an authorized requirement merely because it exists.
Authority upgrades require either a linked independent review (accepted
proposal) or a human attestation call (explicit user commissioning).

No model calls. Bounded filesystem + git plumbing reads only.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

DOC_DIRS = ("docs/design", "docs/reports", "docs/reviews", "docs/architecture",
            "docs/guides", "docs/evaluation", "docs/qualification",
            "docs/programmes", "docs/plans")

REVIEW_MARKERS = ("-REVIEW", "-R1-REVIEW", "REVIEW-", "review")


@dataclass
class SourceCandidate:
    episode_key: str
    path: str  # repo-relative posix path
    revision: str  # git HEAD sha of the repo at scan time ("" if unknown)
    digest: str  # sha256 of file bytes (bounded read)
    has_review_sibling: bool = False
    review_path: str = ""
    suggested_authority: str = "inferred"  # inferred|accepted_proposal-candidate|unknown
    basis: str = ""
    extra: dict = field(default_factory=dict)


def _episode_key(episode_id: str, title: str) -> str:
    """Episode key is the task identifier (e.g. AI-CORE-08C), not the row id."""
    for token in (title or "").split():
        token = token.strip().strip(":,")
        if "-" in token and any(c.isdigit() for c in token):
            return token.upper()
    tail = (episode_id or "").split(":")[-1]
    return tail.upper()


def _bounded_digest(path: Path, limit: int = 200_000) -> str:
    try:
        data = path.read_bytes()[:limit]
    except OSError:
        return ""
    return hashlib.sha256(data).hexdigest()[:32]


def _repo_head(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root),
            capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.decode().strip()[:40]


def resolve_candidates(repo_root: str | Path, episode_id: str,
                       title: str, limit: int = 25) -> list[SourceCandidate]:
    """Deterministic candidate scan. Pure read; safe to run on page load
    (though normal use is via explicit recovery runs, never auto-eval)."""
    root = Path(repo_root)
    key = _episode_key(episode_id, title)
    if not key or len(key) < 3:
        return []
    head = _repo_head(root)
    found: list[SourceCandidate] = []
    for d in DOC_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        try:
            names = sorted(p.name for p in base.iterdir() if p.is_file())
        except OSError:
            continue
        for name in names:
            if key not in name.upper():
                continue
            rel = f"{d}/{name}"
            if len(found) >= limit:
                break
            found.append(SourceCandidate(
                episode_key=key, path=rel, revision=head,
                digest=_bounded_digest(base / name)))
        if len(found) >= limit:
            break
    # Sibling-review check: a *-REVIEW* file sharing the key prefix.
    by_prefix: dict[str, list[SourceCandidate]] = {}
    for c in found:
        stem = c.path.rsplit("/", 1)[-1].split("-REVIEW")[0].split("-R1")[0]
        by_prefix.setdefault(stem[:24], []).append(c)
    for c in found:
        upper = c.path.upper()
        if any(m in upper for m in REVIEW_MARKERS):
            continue
        stem = c.path.rsplit("/", 1)[-1].split("-R1")[0]
        for other in found:
            if other is c:
                continue
            oupper = other.path.upper()
            if any(m in oupper for m in REVIEW_MARKERS) and \
                    stem.split("-R")[0] in other.path:
                c.has_review_sibling = True
                c.review_path = other.path
                c.suggested_authority = "accepted_proposal-candidate"
                c.basis = (f"independent review sibling {other.path} exists; "
                           f"human confirmation required before accepted_proposal")
                break
        if not c.has_review_sibling:
            c.suggested_authority = "inferred"
            c.basis = ("filename match only; a repo document is not an "
                       "authorized requirement merely because it exists")
    return found


def commit_history(repo_root: str | Path, episode_key: str,
                   limit: int = 15) -> list[dict[str, str]]:
    """Bounded read-only git log grep for the episode key. Provenance only;
    a commit message is an implementation summary, never a requirement."""
    try:
        proc = subprocess.run(
            ["git", "log", f"--grep={episode_key}", f"-n{max(1, min(limit, 30))}",
             "--format=%H%x1f%s"],
            cwd=str(repo_root), capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    out = []
    for line in proc.stdout.decode(errors="replace").splitlines():
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        out.append({"sha": sha, "subject": subject[:160]})
    return out
