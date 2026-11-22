"""Publishing workbench summary (MC-PUBLISH-01).

Read-only aggregation of publication-readiness evidence. Mission Control owns
the workflow (aggregate, blockers, next actions); Writer, proof tooling and
Bookbuilder own their evidence. Nothing here validates, builds, publishes,
approves or mutates manuscripts.
"""

from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.publication.evidence import EvidenceItem, unknown_evidence
from mission_control.publication.fingerprint import (
    fingerprint_manuscript,
    git_revision,
    writer_source_digest,
)

_BOOKBUILDER_DEFAULT = Path(r"C:\Projects\bookbuilder")


def _bookbuilder_root(settings: Any | None) -> Path:
    raw = os.environ.get("MISSION_CONTROL_BOOKBUILDER_ROOT")
    if raw and str(raw).strip():
        return Path(raw)
    candidate = getattr(settings, "bookbuilder_root", None) if settings else None
    if candidate is not None:
        return Path(candidate)
    return _BOOKBUILDER_DEFAULT


def _file_meta(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"path": str(path)}
    return {
        "path": str(path),
        "bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _writer_run_evidence(
    book_id: str, repo_roots: list[Path]
) -> tuple[EvidenceItem, dict[str, Any]]:
    """Inspect Writer validation outputs without running anything.

    Freshness is established only by exact digest comparison: a stored
    ``source_digest`` is recomputed with Writer's own algorithm against the
    current file. Anything else leaves freshness ``unknown``.
    """
    checked: list[str] = []
    for repo in repo_roots:
        output = repo / ".writer" / "validation"
        checked.append(str(output))
        chapters_dir = output / "chapters"
        try:
            is_dir = output.is_dir()
        except OSError:
            continue
        if not is_dir:
            continue
        states: dict[str, int] = {}
        current = 0
        stale = 0
        compared = 0
        files: list[Path] = []
        try:
            files = sorted(
                p
                for p in chapters_dir.iterdir()
                if p.is_file() and p.suffix == ".json"
            )
        except OSError:
            files = []
        for path in files[:200]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                states["unreadable"] = states.get("unreadable", 0) + 1
                continue
            status = str(data.get("machine_status") or "UNKNOWN").upper()
            states[status] = states.get(status, 0) + 1
            stored_digest = data.get("source_digest")
            chapter_ref = str(data.get("chapter_path") or "")
            if stored_digest and chapter_ref:
                candidate = Path(chapter_ref)
                if not candidate.is_absolute():
                    candidate = repo / Path(chapter_ref.replace("/", os.sep))
                if not candidate.is_file():
                    candidate = chapters_dir.parent / Path(Path(chapter_ref).name)
                try:
                    on_disk = candidate.is_file()
                except OSError:
                    on_disk = False
                if on_disk:
                    try:
                        if writer_source_digest(candidate.read_text(encoding="utf-8")) == stored_digest:
                            current += 1
                        else:
                            stale += 1
                        compared += 1
                    except (OSError, ValueError):
                        pass
        finalizations = 0
        try:
            final_dir = output / "finalization"
            if final_dir.is_dir():
                finalizations = sum(
                    1 for p in final_dir.iterdir() if p.is_file() and p.suffix == ".json"
                )
        except OSError:
            finalizations = 0
        freshness: str = "unknown"
        freshness_note = "Freshness not compared against current source digests."
        if compared:
            if stale:
                freshness = "stale"
                freshness_note = (
                    f"{stale} stored report(s) no longer match current chapter sources."
                )
            else:
                freshness = "current"
                freshness_note = (
                    f"{compared} stored report(s) match current chapter sources exactly."
                )
        if not files and finalizations == 0:
            return (
                unknown_evidence(
                    book_id,
                    "writer_validation_run",
                    "writer",
                    diagnostics=f"Validation output directory exists but holds no chapter reports: {output}.",
                    available_actions=["Run `writer validate --project <key>` in Writer."],
                ),
                {"checked": checked, "states": states, "finalizations": finalizations},
            )
        failed = sum(states.get(k, 0) for k in ("FAIL", "ERROR", "BLOCKED"))
        pending = sum(
            states.get(k, 0) for k in ("NOT_RUN", "STALE", "PENDING", "UNKNOWN")
        )
        if failed:
            result = "failed"
        elif states.get("PASS", 0) and not pending:
            result = "passed"
        else:
            result = "pending"
        return (
            EvidenceItem(
                book_id=book_id,
                evidence_type="writer_validation_run",
                source_system="writer",
                source_reference=str(output),
                result=result,  # type: ignore[arg-type]
                freshness=freshness,  # type: ignore[arg-type]
                diagnostics=(
                    f"Stored Writer validation states: {states}. "
                    f"Finalization events: {finalizations}. "
                    + freshness_note
                ),
                available_actions=["Run `writer validate --project <key>` to refresh."],
                detail={"checked": checked, "states": states, "finalizations": finalizations},
            ),
            {"checked": checked, "states": states, "finalizations": finalizations},
        )
    return (
        unknown_evidence(
            book_id,
            "writer_validation_run",
            "writer",
            diagnostics=(
                "No stored Writer validation output observed at "
                + ("; ".join(checked) if checked else "(no repository roots resolved)")
                + ". Obtain the latest Writer validation results."
            ),
            available_actions=["Run `writer validate --project <key>` in Writer."],
        ),
        {"checked": checked},
    )


def _proof_evidence(
    book_id: str, project_id: str, repo_path: Path | None
) -> EvidenceItem:
    if project_id != "math" or repo_path is None:
        return unknown_evidence(
            book_id,
            "proof_claims",
            "proof_tooling",
            diagnostics="No proof integration reports for this book (unavailable).",
        )
    report = repo_path / "artifacts" / "math01" / "report.json"
    try:
        if not report.is_file():
            return EvidenceItem(
                book_id=book_id,
                evidence_type="proof_claims",
                source_system="proof_tooling",
                source_reference=str(report),
                result="unavailable",
                freshness="unknown",
                diagnostics=f"Expected proof report is absent: {report}.",
                available_actions=["Run the MATH01 investigation in the math repository."],
            )
    except OSError:
        return EvidenceItem(
            book_id=book_id,
            evidence_type="proof_claims",
            source_system="proof_tooling",
            source_reference=str(report),
            result="unknown",
            freshness="unknown",
            diagnostics=f"Proof report could not be read: {report}.",
        )
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return EvidenceItem(
            book_id=book_id,
            evidence_type="proof_claims",
            source_system="proof_tooling",
            source_reference=str(report),
            result="unknown",
            freshness="unknown",
            diagnostics=f"Proof report is not valid JSON: {exc}.",
        )
    assessments = data.get("assessments") or []
    statuses: dict[str, int] = {}
    open_obligations = 0
    claim_ids: list[str] = []
    for item in assessments if isinstance(assessments, list) else []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("overall_status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        obligations = item.get("unresolved_obligations") or []
        open_obligations += len(obligations) if isinstance(obligations, list) else 0
        if item.get("claim_id"):
            claim_ids.append(str(item["claim_id"]))
    capabilities = data.get("capabilities") or []
    tools_available = sorted(
        str(c.get("system"))
        for c in capabilities
        if isinstance(c, dict) and c.get("available")
    )
    tools_missing = sorted(
        str(c.get("system"))
        for c in capabilities
        if isinstance(c, dict) and not c.get("available")
    )
    return EvidenceItem(
        book_id=book_id,
        evidence_type="proof_claims",
        source_system="proof_tooling",
        source_reference=str(report),
        executed_at=str(data.get("generated_at") or ""),
        result="unknown",
        freshness="unknown",
        diagnostics=(
            f"{len(assessments)} claim assessments: {statuses}. "
            f"Open obligations: {open_obligations}. "
            "No merged adjudication verdict exists; statuses are source-native, not a readiness score."
        ),
        available_actions=[
            "Inspect artifacts/math01/report.json and open obligations.",
            "Adjudicate claims in the math repository.",
        ],
        detail={
            "claim_ids": claim_ids,
            "statuses": statuses,
            "provenance": {
                "known": [
                    "claim identifiers and versions",
                    "per-result tool, version, timestamps and input hashes",
                    f"available tools: {', '.join(tools_available) or 'none recorded'}",
                ],
                "verifiable": [
                    "rerun recorded commands against recorded inputs",
                    "input source hashes in results[].inputs",
                ],
                "unknown": [
                    "manuscript passage binding (which chapter text each claim covers)",
                    "merged cross-claim adjudication",
                    "cross-kernel semantic equivalence (explicitly not established)",
                    f"unavailable tools: {', '.join(tools_missing) or 'none'}",
                ],
            },
        },
    )


def _bookbuilder_evidence(
    book_id: str, project_id: str, settings: Any | None
) -> EvidenceItem:
    dist = _bookbuilder_root(settings) / "dist"
    found: list[dict[str, Any]] = []
    for suffix in (".epub", ".pdf", ".md"):
        candidate = dist / f"{project_id}{suffix}"
        try:
            if candidate.is_file():
                found.append(_file_meta(candidate))
        except OSError:
            continue
    if not found:
        return EvidenceItem(
            book_id=book_id,
            evidence_type="builder_artifacts",
            source_system="bookbuilder",
            source_reference=str(dist / f"{project_id}.epub"),
            result="unavailable",
            freshness="unknown",
            diagnostics=f"No Bookbuilder outputs observed in {dist} for {project_id!r}.",
            available_actions=["Build with Bookbuilder (`bookbuilder build --config <book>.toml`)."],
        )
    return EvidenceItem(
        book_id=book_id,
        evidence_type="builder_artifacts",
        source_system="bookbuilder",
        source_reference=str(dist),
        result="unknown",
        freshness="unknown",
        diagnostics=(
            f"{len(found)} artifact(s) observed; a file's existence proves neither "
            "validity nor freshness against the current manuscript."
        ),
        available_actions=["Rebuild with Bookbuilder to refresh artifacts."],
        detail={"artifacts": found},
    )


def _hugo_evidence(
    book_id: str,
    project_id: str,
    chapter_dir: Path | None,
    settings: Any | None,
) -> EvidenceItem:
    found: list[str] = []
    site_config: str | None = None
    if chapter_dir is not None:
        current = chapter_dir
        for _ in range(5):
            for name in ("hugo.toml", "hugo.yaml", "hugo.yml", "hugo.json"):
                candidate = current / name
                try:
                    if candidate.is_file():
                        site_config = str(candidate)
                        break
                except OSError:
                    continue
            if site_config:
                break
            parent = current.parent
            if parent == current:
                break
            current = parent
    websites_root = None
    try:
        if settings is not None and getattr(settings, "websites_root", None) is not None:
            websites_root = Path(settings.websites_root)
    except (OSError, TypeError):
        websites_root = None
    deployed_copies: list[str] = []
    if websites_root is not None:
        for site in ("programmer.ie",):
            for candidate in (
                websites_root / site / "content" / "books" / project_id,
                websites_root / site / "public" / "books" / project_id,
            ):
                try:
                    if candidate.is_dir():
                        deployed_copies.append(str(candidate))
                except OSError:
                    continue
    detail = {"site_config": site_config, "deployed_copies": deployed_copies}
    if site_config:
        found.append(f"site config: {site_config}")
    found.extend(f"deployed copy: {path}" for path in deployed_copies)
    if not found:
        return EvidenceItem(
            book_id=book_id,
            evidence_type="website_publication",
            source_system="hugo",
            result="unavailable",
            freshness="unknown",
            diagnostics="No Hugo site config or deployed book copies observed.",
            available_actions=["Find the actual Hugo/deployment state."],
            detail=detail,
        )
    # When both the manuscript source and a deployed copy are available,
    # compare content fingerprints. A local public/ folder alone never
    # establishes deployment.
    copy_state = "not compared"
    if chapter_dir is not None and deployed_copies:
        source_fp = fingerprint_manuscript(chapter_dir, "*.md")
        for copy in deployed_copies:
            if "public" in Path(copy).parts:
                continue
            copy_fp = fingerprint_manuscript(copy, "*.md")
            if source_fp.get("ok") and copy_fp.get("ok"):
                copy_state = (
                    "identical"
                    if source_fp["fingerprint"] == copy_fp["fingerprint"]
                    else "differs"
                )
                break
    freshness = "unknown"
    if copy_state == "identical":
        freshness = "current"
    elif copy_state == "differs":
        freshness = "stale"
    return EvidenceItem(
        book_id=book_id,
        evidence_type="website_publication",
        source_system="hugo",
        source_reference=site_config or (deployed_copies[0] if deployed_copies else ""),
        result="unknown",
        freshness=freshness,  # type: ignore[arg-type]
        diagnostics=(
            "Observed copies are listed; deployment state is not established. "
            + "; ".join(found)
            + f". Deployed copy comparison: {copy_state}."
        ),
        available_actions=["Verify deployment state in the owning site repository."],
        detail={**detail, "copy_state": copy_state},
    )


def get_publishing_summary(
    session: Session, settings: Any | None, project_id: str
) -> dict[str, Any]:
    """Read-only publishing evidence summary for one book workspace."""
    from sqlalchemy import select as _select

    from mission_control.models import Book as _Book
    from mission_control.models import Project as _Project
    from mission_control.writer_registry import (
        book_source_diagnostic,
        load_writer_registry,
        resolve_registry_path,
    )

    project = session.get(_Project, project_id)
    book = session.scalar(_select(_Book).where(_Book.project_id == project_id))
    try:
        snapshot = load_writer_registry(
            resolve_registry_path(settings) if settings is not None else None
        )
    except Exception:
        snapshot = None
    definition = snapshot.books.get(project_id) if snapshot else None
    diagnostic = book_source_diagnostic(session, project_id, snapshot) if snapshot else None

    book_id = book.id if book else f"book-{project_id}"
    chapter_dir = None
    if definition is not None:
        try:
            chapter_dir = Path(definition.chapter_dir)
        except (OSError, TypeError):
            chapter_dir = None

    evidence: list[EvidenceItem] = []

    # 1. Manuscript discovery (Writer registry).
    if definition is not None and definition.available:
        evidence.append(
            EvidenceItem(
                book_id=book_id,
                evidence_type="manuscript_discovery",
                source_system="writer",
                source_reference=str(definition.chapter_dir),
                result="passed",
                freshness="current",
                diagnostics=(
                    f"Writer registry locates {definition.chapter_count} chapter files "
                    f"matching {definition.chapter_pattern!r}."
                ),
                available_actions=["Refresh book"],
                detail={"chapter_count": definition.chapter_count},
            )
        )
    elif definition is not None:
        configured = list(book.manuscript_paths or []) if book else []
        working = (
            configured[0]
            if configured
            and Path(configured[0]).is_dir()
            else None
        )
        diagnostics = definition.error or "Registered chapter directory unavailable."
        if working and _norm(configured[0]) != _norm(str(definition.chapter_dir)):
            diagnostics += f" Kept working source {working}; Writer drift unresolved."
        evidence.append(
            EvidenceItem(
                book_id=book_id,
                evidence_type="manuscript_discovery",
                source_system="writer",
                source_reference=str(definition.chapter_dir),
                result="unavailable",
                freshness="unknown",
                diagnostics=diagnostics,
                available_actions=[
                    "Update the Writer registry entry or confirm the working source.",
                    "Refresh book",
                ],
            )
        )
    else:
        evidence.append(
            unknown_evidence(
                book_id,
                "manuscript_discovery",
                "writer",
                diagnostics="Book is not registered in the Writer registry.",
                available_actions=["Register the book in Writer or confirm identity."],
            )
        )

    # 2. Configured validation requirements (no execution).
    if definition is not None and definition.validation_checks:
        required = [c["id"] for c in definition.validation_checks if c.get("required")]
        evidence.append(
            EvidenceItem(
                book_id=book_id,
                evidence_type="writer_validation_requirements",
                source_system="writer",
                source_reference=(
                    str(snapshot.source_path) if snapshot and snapshot.source_path else ""
                ),
                result="unknown",
                freshness="current" if snapshot else "unknown",
                diagnostics=(
                    f"Writer requires {len(required)} check(s): {', '.join(required) or 'none'}. "
                    "Human approval required."
                    if definition.human_approval_required
                    else f"Writer requires {len(required)} check(s): {', '.join(required) or 'none'}."
                ),
                available_actions=["Run `writer validate --project <key>` in Writer."],
                detail={"checks": definition.validation_checks},
            )
        )

    # 3. Stored Writer validation runs (read-only).
    repo_roots: list[Path] = []
    if definition is not None:
        for candidate in (definition.repo_path, definition.project_root):
            try:
                path = Path(candidate)
            except (OSError, TypeError):
                continue
            if path not in repo_roots:
                repo_roots.append(path)
    run_item, _ = _writer_run_evidence(book_id, repo_roots)
    evidence.append(run_item)

    # 4. Proof evidence (math only has an integration).
    evidence.append(
        _proof_evidence(
            book_id, project_id, Path(definition.repo_path) if definition else None
        )
    )

    # 5. Builder artifacts (existence only).
    evidence.append(_bookbuilder_evidence(book_id, project_id, settings))

    # 6. Website/publication copies (observed only).
    evidence.append(_hugo_evidence(book_id, project_id, chapter_dir, settings))

    # 7. Mission assessment + approval (stored only, never created here).
    assessment_read: dict[str, Any] | None = None
    try:
        from mission_control.models import PublicationAssessment as _Assessment
        from mission_control.publication import service as _pub

        record = session.scalars(
            _select(_Assessment)
            .where(_Assessment.project_id == project_id)
            .order_by(desc(_Assessment.created_at))
            .limit(1)
        ).first()
        if record is not None:
            assessment_read = _pub.to_read(session, record)
    except Exception:
        assessment_read = None
    if assessment_read is not None:
        readiness = str(assessment_read.get("readiness_detail") or "")
        if "BLOCKED" in readiness or any(
            g.get("result") == "FAIL" and not g.get("waivable")
            for g in assessment_read.get("gates", [])
        ):
            assessment_result = "failed"
        elif any(
            g.get("result") in ("NOT_RUN", "UNKNOWN", "STALE", "ERROR")
            for g in assessment_read.get("gates", [])
        ):
            assessment_result = "pending"
        else:
            assessment_result = "passed"
        freshness = (
            "stale" if assessment_read.get("freshness") == "STALE" else "current"
        )
        evidence.append(
            EvidenceItem(
                book_id=book_id,
                evidence_type="mission_assessment",
                source_system="mission_control",
                source_reference=str(assessment_read.get("id")),
                executed_at=str(assessment_read.get("created_at") or ""),
                observed_at=str(assessment_read.get("created_at") or ""),
                result=assessment_result,  # type: ignore[arg-type]
                freshness=freshness,  # type: ignore[arg-type]
                diagnostics=readiness or "Stored Mission assessment.",
                available_actions=["Open the assessment dossier.", "Refresh evidence."],
                detail={
                    "gates": [
                        {"gate_id": g.get("gate_id"), "result": g.get("result")}
                        for g in assessment_read.get("gates", [])
                    ]
                },
            )
        )
        approvals = assessment_read.get("approvals", [])
        fresh_approvals = [
            a for a in approvals if a.get("freshness") != "STALE" and a.get("decision") == "APPROVE_RELEASE_CANDIDATE"
        ]
        if fresh_approvals:
            evidence.append(
                EvidenceItem(
                    book_id=book_id,
                    evidence_type="human_approval",
                    source_system="mission_control",
                    source_reference=str(fresh_approvals[-1].get("id")),
                    result="passed",
                    freshness="current",
                    diagnostics=f"Recorded by {fresh_approvals[-1].get('reviewer') or 'author'}.",
                    available_actions=[],
                )
            )
        elif definition is not None and definition.human_approval_required:
            evidence.append(
                EvidenceItem(
                    book_id=book_id,
                    evidence_type="human_approval",
                    source_system="mission_control",
                    result="pending",
                    freshness="unknown",
                    diagnostics="Human approval is required by Writer policy and not recorded for this snapshot.",
                    available_actions=["Record author approval for this exact snapshot."],
                )
            )
    else:
        if definition is not None and definition.human_approval_required:
            evidence.append(
                EvidenceItem(
                    book_id=book_id,
                    evidence_type="human_approval",
                    source_system="mission_control",
                    result="pending",
                    freshness="unknown",
                    diagnostics="Human approval is required by Writer policy and not recorded.",
                    available_actions=["Record author approval for the exact release snapshot."],
                )
            )

    items = [item.to_dict() for item in evidence]
    failed = [i["evidence_type"] for i in items if i["result"] == "failed"]
    stale = [i["evidence_type"] for i in items if i["freshness"] == "stale"]
    missing = [
        i["evidence_type"]
        for i in items
        if i["result"] in ("unknown", "unavailable", "pending")
    ]
    lifecycle = definition.publication_status if definition else None

    # Manuscript provenance: reproducible fingerprint + git revision (kept separate).
    # Fingerprint the active source: the resolved Writer directory when it
    # exists, else the working Mission source (drift case), else the resolved
    # path for an honest unavailable diagnostic.
    manuscript_source = diagnostic.get("resolved_chapter_dir") if diagnostic else None
    try:
        if manuscript_source is None or not Path(manuscript_source).is_dir():
            for candidate in (diagnostic.get("manuscript_paths") or []) if diagnostic else []:
                try:
                    if candidate and Path(candidate).is_dir():
                        manuscript_source = candidate
                        break
                except OSError:
                    continue
    except OSError:
        pass
    source_fingerprint: dict[str, Any] = {"ok": False, "diagnostics": "No manuscript source resolved."}
    if manuscript_source:
        pattern = definition.chapter_pattern if definition else "*.md"
        source_fingerprint = fingerprint_manuscript(manuscript_source, pattern)
    git_info: dict[str, Any] = {"ok": False, "diagnostics": "No repository path resolved."}
    if definition is not None:
        git_info = git_revision(definition.repo_path)

    # Independent fingerprint cross-check against the stored assessment.
    fingerprint_match: bool | None = None
    if assessment_read is not None and manuscript_source:
        check = fingerprint_manuscript(manuscript_source, "*-chapter.md")
        if check.get("ok"):
            fingerprint_match = check["fingerprint"] == assessment_read.get("manuscript_fingerprint")
    if fingerprint_match is False and "mission_assessment" not in stale:
        stale.append("mission_assessment")

    # Canonical identity for this book.
    identity_block: dict[str, Any] = {"identity_state": "unregistered"}
    try:
        from mission_control.publication.identity import get_aliases, identity_status

        writer_ids = set(snapshot.books) if snapshot else set()
        writer_available = (
            {pid: bool(defn.available) for pid, defn in snapshot.books.items()}
            if snapshot
            else {}
        )
        status = identity_status(session, project_id, writer_ids, writer_available)
        identity_block = {
            "canonical_id": project_id,
            "identity_state": status.get("state"),
            "identity_reason": status.get("reason"),
            "writer_project_id": status.get("writer_id"),
            "candidates": status.get("candidates", []),
            "aliases": [
                entry for entry in get_aliases(session)
                if entry.get("canonical_project_id") == project_id
            ],
        }
    except Exception as exc:
        identity_block = {"identity_state": "unknown", "identity_reason": f"Identity check failed: {exc}."}

    from mission_control.persistence.db import now_iso as _now_iso

    return {
        "project_id": project_id,
        "project_name": project.name if project else None,
        "book_id": book.id if book else None,
        "book_title": book.title if book else (definition.title if definition else None),
        "manuscript_root": diagnostic.get("resolved_chapter_dir") if diagnostic else None,
        "chapter_count": diagnostic.get("chapter_count") if diagnostic else None,
        "lifecycle": lifecycle,
        "lifecycle_note": "Writer lifecycle is knowledge state, not publication approval.",
        "publication_gate": (
            assessment_read.get("readiness_detail") if assessment_read else "Unknown"
        ),
        "policy_version": assessment_read.get("policy_version") if assessment_read else None,
        "identity": identity_block,
        "source_fingerprint": source_fingerprint,
        "git_revision": git_info,
        "fingerprint_match": fingerprint_match,
        "observed_at": _now_iso(),
        "evidence": items,
        "blockers": {
            "failed": failed,
            "stale": stale,
            "missing": missing,
            "identity_conflicts": (
                identity_block.get("candidates", [])
                if identity_block.get("identity_state") in ("candidate", "conflict")
                else []
            ),
        },
        "refresh_note": "Refresh rereads stored evidence only; it never validates, builds or publishes.",
    }


def _norm(value: str | None) -> str:
    import os as _os

    if not value:
        return ""
    try:
        return _os.path.normcase(_os.path.normpath(value))
    except OSError:
        return _os.path.normcase(str(value))
