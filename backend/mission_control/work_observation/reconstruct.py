"""WORK-OUTCOME-01 W2: deterministic episode reconstruction engine.

Pure functions over plain records (no DB, no git, no models calls). The
service layer assembles inputs from W1 signals + the git index; tests drive
the engine directly with synthetic fixtures.

Confidence labels are heuristic (explicit > strong > moderate > weak) and
must never be read as probabilities. Temporal proximity alone never creates
an association. Objectives are never invented: titles are mechanical
(task id, chain root, or unresolved bucket).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

EPISODE_VERSION = 1

# File names so generic that overlap alone proves nothing.
COMMON_FILES = {
    "readme.md", "package.json", "package-lock.json", "requirements.txt",
    ".gitignore", "license", "license.md", ".env.example", "changelog.md",
}

# Signal values that look like task ids but are test/probe artefacts, or common
# non-task patterns (HTTP/CVE/ERROR codes discussed as CVE-2024-1234 etc.).
# A lone passing mention of these must never seed a work episode.
TASK_ID_DENY = ("SES_", "MSG_", "TEST-", "FIXTURE-", "EXAMPLE-")
TASK_ID_DENY_RES = [
    __import__("re").compile(r"^(HTTP|CVE|ERROR|CODE|BUG|ISSUE|TICKET)-[\d-]+$"),
]


def _denied_task(value: str) -> bool:
    if value.startswith(TASK_ID_DENY):
        return True
    return any(rx.match(value) for rx in TASK_ID_DENY_RES)

TEMPORAL_WINDOW_MS = 14 * 24 * 3600 * 1000


@dataclass
class SessionRec:
    id: str
    parent_id: str | None
    directory: str
    worktree: str
    repo_uid: str | None
    title: str
    first_ms: int
    last_ms: int


@dataclass
class CommitRec:
    repo_uid: str | None
    sha: str
    message: str
    time_ms: int
    files: list[str] = field(default_factory=list)


@dataclass
class EpisodeRec:
    id: str
    kind: str  # programme | stage | task | chain | cluster | unresolved
    title: str
    project_key: str
    session_ids: list[str] = field(default_factory=list)
    parent_id: str | None = None
    first_ms: int = 0
    last_ms: int = 0
    status: str = "candidate"
    source_digest: str = ""


@dataclass
class AssociationRec:
    episode_id: str
    assoc_type: str  # session | commit | repository | review_of | signal
    target_ref: str
    method: str  # explicit | derived | candidate | rejected
    confidence: str  # explicit | strong | moderate | weak
    reason: str
    signals: list[str] = field(default_factory=list)


@dataclass
class ReconResult:
    episodes: list[EpisodeRec] = field(default_factory=list)
    associations: list[AssociationRec] = field(default_factory=list)
    unresolved_session_ids: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def _slug(value: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in value)


def episode_id_for_task(task_id: str) -> str:
    return f"ep:task:{_slug(task_id)}"[:120]


def episode_id_for_chain(root_session_id: str) -> str:
    return f"ep:chain:{_slug(root_session_id)}"[:120]


def episode_id_for_cluster(session_ids: list[str]) -> str:
    digest = hashlib.sha1("|".join(sorted(session_ids)).encode()).hexdigest()[:16]
    return f"ep:cluster:{digest}"


def unresolved_bucket_id(project_key: str) -> str:
    return f"ep:unresolved:{_slug(project_key or 'default')}"[:120]


def classify_task_id(value: str) -> str:
    """programme | stage | task | artefact. Artefacts never seed episodes."""
    if _denied_task(value):
        return "artefact"
    core = value.split(":")[-1]
    if not core or len(core) > 60:
        return "artefact"
    if core.startswith("W") and core[1:].split("-")[0].isdigit():
        return "stage"  # W1, W2-ENTRY…
    if "-" in core and core.rsplit("-", 1)[-1][:2].isdigit():
        return "task"  # WORK-OUTCOME-01, AI-CORE-08C
    if "-" in core:
        return "programme"  # WORK-OUTCOME, MC-COST
    return "artefact"


def _norm_file(path: str) -> str:
    return path.replace("\\", "/").lstrip("/").lower()


def _distinctive(files: list[str]) -> list[str]:
    out = []
    for f in files:
        base = _norm_file(f).rsplit("/", 1)[-1]
        if base not in COMMON_FILES:
            out.append(_norm_file(f))
    return out


def reconstruct(sessions: list[SessionRec],
                signals_by_session: dict[str, dict[str, list[str]]],
                commits: list[CommitRec],
                project_key: str = "") -> ReconResult:
    """Deterministic reconstruction. See W2-CORRELATION-RULES for the rules."""
    episodes: dict[str, EpisodeRec] = {}
    associations: list[AssociationRec] = []
    stats: dict[str, int] = {"rules_fired": 0, "rejected": 0, "abstained": 0}

    def _ep(eid: str, kind: str, title: str) -> EpisodeRec:
        ep = episodes.get(eid)
        if ep is None:
            ep = EpisodeRec(id=eid, kind=kind, title=title, project_key=project_key)
            episodes[eid] = ep
        return ep

    def _link(episode_id: str, assoc_type: str, target_ref: str, method: str,
              confidence: str, reason: str, signals: list[str]) -> None:
        associations.append(AssociationRec(episode_id, assoc_type, target_ref,
                                           method, confidence, reason, signals))
        stats["rules_fired"] += 1

    by_id = {s.id: s for s in sessions}

    # R2: session-hierarchy chains (explicit, strongest structural signal).
    roots: dict[str, list[str]] = {}
    for s in sessions:
        root = s.id
        seen = {s.id}
        cur = s
        while cur.parent_id and cur.parent_id in by_id and cur.parent_id not in seen:
            seen.add(cur.parent_id)
            cur = by_id[cur.parent_id]
            root = cur.id
        roots.setdefault(root, []).append(s.id)
    chain_of: dict[str, str] = {}
    for root, members in roots.items():
        if len(members) > 1:
            eid = episode_id_for_chain(root)
            ep = _ep(eid, "chain", f"Session chain {root[:12]} ({len(members)} sessions)")
            ep.session_ids.extend(sorted(members))
            for m in members:
                chain_of[m] = eid
                _link(eid, "session", f"opencode:{m}", "explicit", "explicit",
                      "session-chain-parent-link", [f"chain-root:{root}"])

    # R1: explicit task/programme/stage identifiers seed episodes.
    # Corroboration rule (review M1): a lone generic mention seeds a
    # candidate/weak episode; explicit/explicit requires corroboration —
    # same id in >=2 sessions, or a co-occurring sha/file/chain/co-mention.
    task_sessions: dict[str, set[str]] = {}
    for s in sessions:
        for task_id in signals_by_session.get(s.id, {}).get("task_id_candidate", []):
            if classify_task_id(task_id) != "artefact":
                task_sessions.setdefault(task_id, set()).add(s.id)
    task_episodes: dict[str, str] = {}  # task id -> episode id
    for s in sessions:
        bucket = signals_by_session.get(s.id, {})
        corroborating = bool(bucket.get("commit_sha_candidate")
                             or bucket.get("file_path")
                             or s.parent_id in by_id
                             or len(bucket.get("task_id_candidate", [])) > 1)
        for task_id in bucket.get("task_id_candidate", []):
            cls = classify_task_id(task_id)
            if cls == "artefact":
                stats["rejected"] += 1
                associations.append(AssociationRec(
                    "", "signal", f"opencode:{s.id}", "rejected", "weak",
                    "task-id-artefact-or-fixture", [f"task:{task_id}"]))
                continue
            eid = episode_id_for_task(task_id)
            ep = _ep(eid, cls, task_id)
            if s.id not in ep.session_ids:
                ep.session_ids.append(s.id)
            task_episodes[task_id] = eid
            if corroborating or len(task_sessions.get(task_id, ())) > 1:
                _link(eid, "session", f"opencode:{s.id}", "explicit", "explicit",
                      "explicit-task-identifier", [f"task:{task_id}"])
            else:
                _link(eid, "session", f"opencode:{s.id}", "candidate", "weak",
                      "lone-task-mention", [f"task:{task_id}"])

    # R6: hierarchy — stage/task co-mentioned with a programme links under it.
    mentioned: dict[str, set[str]] = {}
    for s in sessions:
        kinds: dict[str, str] = {}
        for t in signals_by_session.get(s.id, {}).get("task_id_candidate", []):
            c = classify_task_id(t)
            if c != "artefact":
                kinds[t] = c
        mentioned[s.id] = set(kinds)
        progs = [t for t, c in kinds.items() if c == "programme"]
        subs = [t for t, c in kinds.items() if c in ("stage", "task")]
        for sub in subs:
            for prog in progs:
                child = task_episodes.get(sub)
                parent = task_episodes.get(prog)
                if child and parent and child != parent:
                    ep = episodes[child]
                    if ep.parent_id is None:
                        ep.parent_id = parent
                    _link(child, "signal", f"programme:{prog}", "candidate",
                          "weak", "programme-co-mention", [f"task:{sub}", f"task:{prog}"])

    # R3: commit resolution (repo-scoped existence checks). Abbreviated SHAs
    # (<40 hex) resolve only with session corroboration (review M2): a bare
    # 7-char token such as a version number must never become an explicit
    # same-repo link on a coincidental unique-prefix match.
    index: dict[str, dict[str, CommitRec]] = {}
    for c in commits:
        index.setdefault(c.repo_uid or "", {})[c.sha.lower()] = c
    for s in sessions:
        bucket = signals_by_session.get(s.id, {})
        # Artefact task ids (HTTP-500 etc.) never corroborate (re-review).
        sha_corroborated = bool(
            [t for t in bucket.get("task_id_candidate", [])
             if classify_task_id(t) != "artefact"]
            or bucket.get("file_path") or s.parent_id in by_id)
        for sha in bucket.get("commit_sha_candidate", []):
            low = sha.lower()
            home = (s.repo_uid or "")
            if len(sha) < 40 and not sha_corroborated:
                stats["abstained"] += 1
                associations.append(AssociationRec(
                    "", "signal", f"opencode:{s.id}", "rejected", "weak",
                    "short-sha-uncorroborated", [f"sha:{sha}"]))
                continue
            found: CommitRec | None = index.get(home, {}).get(low)
            if found is None and len(sha) < 40:
                # Abbreviated: unique-prefix match within home repo only.
                cands = [c for h, c in index.get(home, {}).items()
                         if h.startswith(low)]
                if len(cands) == 1:
                    found = cands[0]
                elif len(cands) > 1:
                    stats["abstained"] += 1
                    associations.append(AssociationRec(
                        "", "signal", f"opencode:{s.id}", "rejected", "weak",
                        "ambiguous-abbreviated-sha", [f"sha:{sha}"]))
                    continue
            host_ep = _host_episode(s.id, task_episodes, signals_by_session, chain_of)
            if found is not None:
                if host_ep is None:
                    eid = episode_id_for_cluster([s.id])
                    host_ep = _ep(eid, "cluster", f"Commit-linked work {s.id[:12]}").id
                    _ep(host_ep, "cluster", "").session_ids.append(s.id)
                    _link(host_ep, "session", f"opencode:{s.id}", "derived",
                          "moderate", "sha-mention-seeds-episode", [f"sha:{sha}"])
                _link(host_ep, "commit", f"{found.repo_uid}:{found.sha}",
                      "explicit", "explicit", "sha-resolved-same-repo" if
                      (found.repo_uid or "") == home else "sha-resolved-cross-repo",
                      [f"sha:{sha}"])
                continue
            # Not in home repo: check other repos (cross-repo reference case).
            other = [(r, c) for r, m in index.items()
                     for h, c in m.items() if h == low or (len(sha) < 40 and h.startswith(low))]
            if other:
                if host_ep is None:
                    eid = episode_id_for_cluster([s.id])
                    host_ep = _ep(eid, "cluster", f"Commit-linked work {s.id[:12]}").id
                    _ep(host_ep, "cluster", "").session_ids.append(s.id)
                _link(host_ep, "commit", f"{other[0][1].repo_uid}:{other[0][1].sha}",
                      "candidate", "weak", "sha-resolved-other-repo", [f"sha:{sha}"])
            else:
                stats["abstained"] += 1
                associations.append(AssociationRec(
                    host_ep or "", "signal", f"opencode:{s.id}", "rejected",
                    "weak", "sha-unresolved-no-object", [f"sha:{sha}"]))

    # R4: file overlap (+ temporal support) for sessions without episode homes.
    commit_files = {c.sha: set(_norm_file(f) for f in c.files) for c in commits}
    for s in sessions:
        if _host_episode(s.id, task_episodes, signals_by_session, chain_of):
            continue
        sess_files = [_norm_file(f) for files in
                      [signals_by_session.get(s.id, {}).get("file_path", [])]
                      for f in files]
        distinctive = _distinctive(sess_files)
        if not distinctive:
            continue
        best: CommitRec | None = None
        for c in commits:
            if (c.repo_uid or "") != (s.repo_uid or ""):
                continue
            overlap = set(distinctive) & commit_files.get(c.sha, set())
            if not overlap:
                continue
            if best is None or len(overlap) > len(
                    set(distinctive) & commit_files.get(best.sha, set())):
                best = c
        if best is None:
            continue
        overlap = set(distinctive) & commit_files.get(best.sha, set())
        near = abs(best.time_ms - s.last_ms) <= TEMPORAL_WINDOW_MS or \
            abs(best.time_ms - s.first_ms) <= TEMPORAL_WINDOW_MS
        if len(overlap) >= 2 or (len(overlap) == 1 and near):
            eid = episode_id_for_cluster([s.id])
            ep = _ep(eid, "cluster", f"File-linked work {s.id[:12]}")
            ep.session_ids.append(s.id)
            _link(eid, "session", f"opencode:{s.id}", "derived", "moderate",
                  "file-overlap-session-seed", sorted(overlap)[:5])
            # Review M3: a single generic file + automatic 14-day proximity
            # must never yield moderate — weak at most.
            _link(eid, "commit", f"{best.repo_uid}:{best.sha}", "candidate",
                  "moderate" if (len(overlap) >= 2 and near) else "weak",
                  "file-overlap-temporal" if near else "file-overlap-only",
                  sorted(overlap)[:5])
        else:
            stats["abstained"] += 1

    # R5: temporal proximity alone never links — enforced by construction
    # (no rule consumes timestamps without another signal).

    # R7: review/correction — sessions invoking review tooling attach as
    # review_of to task episodes they reference. A member session may also be
    # a reviewer (separate assoc_type); correction resolution is NOT inferred
    # here (later stages own that).
    for s in sessions:
        tools = [t.lower() for t in
                 signals_by_session.get(s.id, {}).get("tool_invocation", [])]
        if not any("review" in t or "cocoder" in t for t in tools):
            continue
        for task_id in signals_by_session.get(s.id, {}).get("task_id_candidate", []):
            if classify_task_id(task_id) in ("artefact", "programme"):
                continue
            eid = task_episodes.get(task_id)
            if eid and not any(a.target_ref == f"opencode:{s.id}"
                               and a.assoc_type == "review_of"
                               for a in associations if a.episode_id == eid):
                _link(eid, "review_of", f"opencode:{s.id}", "candidate",
                      "weak", "review-session-shares-task", [f"task:{task_id}"])

    # Unresolved bucket: sessions with no episode home and no commit-only home.
    # Rejected markers without a home (artefacts, ambiguous SHAs) are attached
    # here as well (review M5) so refusals are auditable from PG, not just
    # envelope stats.
    homed = {a.target_ref for a in associations
             if a.assoc_type == "session" and a.episode_id}
    unlinked = [s.id for s in sessions if f"opencode:{s.id}" not in homed]
    homeless = [a for a in associations if not a.episode_id]
    bucket = ""
    if unlinked or homeless:
        bucket = unresolved_bucket_id(project_key or "default")
        ep = _ep(bucket, "unresolved",
                 f"Unidentified development activity ({len(unlinked)} sessions)")
        ep.session_ids.extend(sorted(unlinked))
        for sid in sorted(unlinked):
            _link(bucket, "session", f"opencode:{sid}", "candidate", "weak",
                  "no-corroborating-signal", [])
        for a in homeless:
            a.episode_id = bucket

    # Time bounds + digests.
    for ep in episodes.values():
        ms = [(by_id[i].first_ms, by_id[i].last_ms) for i in ep.session_ids if i in by_id]
        if ms:
            ep.first_ms = min(a for a, _ in ms)
            ep.last_ms = max(b for _, b in ms)
        ep.source_digest = hashlib.sha1(
            f"{ep.id}|{','.join(sorted(ep.session_ids))}".encode()).hexdigest()[:16]
        if ep.kind != "unresolved" and ep.session_ids:
            ep.status = "established"

    stats.update({"episodes": len(episodes), "associations": len(associations),
                  "unresolved_sessions": len(unlinked)})
    return ReconResult(list(episodes.values()), associations, sorted(unlinked), stats)


def _host_episode(session_id: str, task_episodes: dict[str, str],
                  signals_by_session: dict[str, dict[str, list[str]]],
                  chain_of: dict[str, str]) -> str | None:
    for t in signals_by_session.get(session_id, {}).get("task_id_candidate", []):
        if classify_task_id(t) != "artefact" and t in task_episodes:
            return task_episodes[t]
    return chain_of.get(session_id)


def check_cycle(episodes: dict[str, EpisodeRec], child: str, parent: str) -> bool:
    """True if linking child→parent would create a cycle."""
    seen = {child}
    cur = parent
    while cur:
        if cur in seen:
            return True
        seen.add(cur)
        nxt = episodes.get(cur)
        cur = nxt.parent_id if nxt else None
    return False
