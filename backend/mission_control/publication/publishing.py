"""Publishing workbench summary (MC-PUBLISH-01).

Read-only aggregation of publication-readiness evidence. Mission Control owns
the workflow (aggregate, blockers, next actions); Writer, proof tooling and
Bookbuilder own their evidence. Nothing here validates, builds, publishes,
approves or mutates manuscripts.
"""

from __future__ import annotations

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
    manuscript_dir = Path(chapter_dir) if chapter_dir else None

    # 3b. Stored Writer finalization events (read-only, digest-compared).
    evidence.append(_writer_finalization_evidence(book_id, repo_roots, manuscript_dir))

    # 3c. Writer readthrough acceptances (read-only database observation).
    evidence.append(_writer_readthrough_evidence(book_id, project_id, manuscript_dir))

    # 4. Proof evidence (math only has an integration).
    evidence.append(
        _proof_evidence(
            book_id, project_id, Path(definition.repo_path) if definition else None
        )
    )

    # 5. Builder artifacts (existence + config + freshness vs manuscript).
    evidence.append(_bookbuilder_evidence(
        book_id, project_id, settings,
        manuscript_root=manuscript_dir,
        book_title=(book.title if book else None) or (definition.title if definition else None)))

    # 6. Website/publication copies (observed only).
    evidence.append(_hugo_evidence(book_id, project_id, chapter_dir, settings))

    # 6b. ALIVE connection state (read-only observation).
    evidence.append(_alive_evidence(
        session, settings, project_id,
        manuscript_root=str(manuscript_dir) if manuscript_dir else None))

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
    # Gate join: policy gates annotated with observed evidence (display-only;
    # readiness derivation stays in the assessment flow, never invented here).
    from mission_control.publication import policy as _policy

    gates = gate_evidence_join(list(_policy.GATES), items)
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
        "gates": gates,
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


GATE_EVIDENCE_MAP: dict[str, list[str]] = {
    "manuscript_identity": ["manuscript_discovery"],
    "chapter_structure": ["manuscript_discovery", "writer_validation_run"],
    "publication_build": ["builder_config", "builder_artifacts"],
    "assets_references": ["builder_artifacts"],
    "prose_review": ["writer_validation_run", "writer_finalization"],
    "technical_verification": ["proof_claims"],
    "evidence_completeness": ["mission_assessment"],
    "author_approval": ["human_approval", "writer_finalization"],
}


def gate_evidence_join(policy_gates: list[dict[str, Any]],
                       items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join policy gates to observed evidence without inventing verdicts.

    Status roll-up: any failed evidence fails the gate; otherwise any pending
    evidence pends it; all-passed passes; unavailable evidence on its own
    reports unavailable; anything else stays unknown. Staleness is reported
    alongside, never merged into the result.
    """
    joined = []
    for gate in policy_gates:
        gate_id = str(gate.get("gate_id", ""))
        matched = [item for item in items
                   if item.get("evidence_type") in GATE_EVIDENCE_MAP.get(gate_id, [])]
        stale = any(item.get("freshness") == "stale" for item in matched)
        if any(item.get("result") == "failed" for item in matched):
            status = "failed"
        elif any(item.get("result") == "pending" for item in matched):
            status = "pending"
        elif matched and all(item.get("result") == "passed" for item in matched):
            status = "passed"
        elif any(item.get("result") == "unavailable" for item in matched):
            status = "unavailable"
        else:
            status = "unknown"
        joined.append({
            "gate_id": gate_id,
            "label": str(gate.get("description", gate_id))[:200],
            "gate_group": str(gate.get("gate_group", "")),
            "status": status,
            "stale": stale,
            "evidence": [
                {"evidence_type": item.get("evidence_type"),
                 "result": item.get("result"),
                 "freshness": item.get("freshness"),
                 "source_system": item.get("source_system"),
                 "source_reference": item.get("source_reference")}
                for item in matched
            ],
        })
    return joined


def _sha256_file(path: Path) -> str | None:
    try:
        digest = __import__("hashlib").sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _manuscript_chapter_files(manuscript_root: Path | None) -> list[Path]:
    if manuscript_root is None:
        return []
    try:
        if not manuscript_root.is_dir():
            return []
        return sorted(path for path in manuscript_root.iterdir()
                      if path.is_file() and path.suffix.lower() == ".md")
    except OSError:
        return []


def _writer_finalization_evidence(
    book_id: str, repo_roots: list[Path], manuscript_root: Path | None
) -> EvidenceItem:
    """Read stored Writer finalization events; compare digests to live files."""
    checked: list[str] = []
    events: list[dict[str, Any]] = []
    for repo in repo_roots:
        final_dir = repo / ".writer" / "validation" / "finalization"
        checked.append(str(final_dir))
        try:
            if not final_dir.is_dir():
                continue
            files = sorted(p for p in final_dir.iterdir()
                           if p.is_file() and p.suffix == ".json")
        except OSError:
            continue
        for path in files[:200]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if isinstance(entry, dict):
                    events.append({"file": str(path), **entry})
    if not events:
        return unknown_evidence(
            book_id, "writer_finalization", "writer",
            diagnostics=("No stored Writer finalization events observed at "
                         + ("; ".join(checked) if checked else "(no repository roots resolved)")
                         + ". Only an explicit, digest-bound author approval counts."),
            available_actions=["Finalize chapters in Writer (`writer finalize ... --approved-by ...`)."],
        )
    live_by_stem = {path.stem: path for path in _manuscript_chapter_files(manuscript_root)}
    current = stale = unknown = 0
    approvers: set[str] = set()
    for event in events:
        digest = str(event.get("source_digest") or event.get("content_sha256") or "")
        chapter = str(event.get("chapter_path") or event.get("chapter") or "")
        stem = Path(chapter).stem if chapter else Path(str(event.get("file", ""))).stem
        live = live_by_stem.get(stem)
        live_digest = _sha256_file(live) if live is not None else None
        if event.get("approved_by"):
            approvers.add(str(event["approved_by"]))
        if not digest or live_digest is None:
            unknown += 1
        elif digest == live_digest:
            current += 1
        else:
            stale += 1
    if stale:
        result, freshness = "pending", "stale"
    elif unknown and not current:
        result, freshness = "pending", "unknown"
    elif current:
        result, freshness = "passed", "current"
    else:
        result, freshness = "pending", "unknown"
    return EvidenceItem(
        book_id=book_id,
        evidence_type="writer_finalization",
        source_system="writer",
        source_reference="; ".join(sorted({str(event.get("file", "")) for event in events})[:5]),
        result=result,  # type: ignore[arg-type]
        freshness=freshness,  # type: ignore[arg-type]
        diagnostics=(
            f"{len(events)} finalization event(s): {current} current, {stale} stale, "
            f"{unknown} unverifiable against live chapters. "
            f"Approved by: {', '.join(sorted(approvers)) or 'none recorded'}. "
            "Only digest-bound approvals for the current revision count."
        ),
        available_actions=["Finalize chapters in Writer (`writer finalize ... --approved-by ...`)."],
        detail={"current": current, "stale": stale, "unknown": unknown},
    )


def _writer_readthrough_evidence(
    book_id: str, project_id: str, manuscript_root: Path | None
) -> EvidenceItem:
    """Read chapter acceptances from Writer's Postgres (read-only).

    Never invents acceptances: no DSN, unreachable DB, or any error reports
    unknown. An empty acceptance set for a required gate reports pending,
    never passed.
    """
    import os as _os

    dsn = (_os.environ.get("MISSION_CONTROL_WRITER_DSN") or "").strip()
    if not dsn:
        return unknown_evidence(
            book_id, "writer_readthrough", "writer",
            diagnostics=("Readthrough acceptances are not observable: set "
                         "MISSION_CONTROL_WRITER_DSN to a read-only Writer database URL. "
                         "Human chapter acceptance remains required where configured."),
            available_actions=["Accept chapters in Writer readthrough, or configure read access."],
        )
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        return unknown_evidence(
            book_id, "writer_readthrough", "writer",
            diagnostics="psycopg is unavailable, so readthrough acceptances cannot be observed.",
            available_actions=["Accept chapters in Writer readthrough."],
        )
    live_by_name = {path.name: path for path in _manuscript_chapter_files(manuscript_root)}
    if manuscript_root is not None and not live_by_name:
        return unknown_evidence(
            book_id, "writer_readthrough", "writer",
            diagnostics="No live manuscript chapters resolved; acceptance cannot be compared.",
            available_actions=["Confirm the manuscript location."],
        )
    try:
        with psycopg.connect(
            dsn, options="-c default_transaction_read_only=on -c statement_timeout=5000",
            connect_timeout=5,
        ) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT chapter_path, accepted_source_digest, accepted_by, created_at "
                    "FROM readthrough_chapter_acceptances WHERE project_id = %s "
                    "ORDER BY chapter_path ASC, created_at DESC",
                    (project_id,),
                )
                rows = list(cursor.fetchall())
    except Exception as exc:
        return unknown_evidence(
            book_id, "writer_readthrough", "writer",
            diagnostics=f"Readthrough store unreachable ({type(exc).__name__}); nothing invented.",
            available_actions=["Accept chapters in Writer readthrough."],
        )
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("chapter_path") or "")
        if key and key not in latest:
            latest[key] = row
    current = stale = missing = 0
    approvers: set[str] = set()
    for name, live in live_by_name.items():
        digest = _sha256_file(live)
        match = latest.get(name) or latest.get(str(live)) or latest.get(live.stem)
        if match is None:
            missing += 1
            continue
        if match.get("accepted_by"):
            approvers.add(str(match["accepted_by"]))
        if digest is not None and match.get("accepted_source_digest") == digest:
            current += 1
        else:
            stale += 1
    total = len(live_by_name)
    if total and missing == 0 and stale == 0:
        result, freshness = "passed", "current"
    elif stale:
        result, freshness = "pending", "stale"
    elif missing == total:
        result, freshness = "pending", "unknown"
    else:
        result, freshness = "pending", "unknown"
    return EvidenceItem(
        book_id=book_id,
        evidence_type="writer_readthrough",
        source_system="writer",
        source_reference="readthrough_chapter_acceptances",
        result=result,  # type: ignore[arg-type]
        freshness=freshness,  # type: ignore[arg-type]
        diagnostics=(
            f"{current}/{total} chapters accepted on the current digest; "
            f"{stale} stale, {missing} never accepted. "
            f"Accepted by: {', '.join(sorted(approvers)) or 'nobody recorded'}. "
            "Acceptance is digest-bound; edited chapters need re-acceptance."
        ),
        available_actions=["Accept chapters in Writer readthrough."],
        detail={"current": current, "stale": stale, "missing": missing, "total": total},
    )


def _bookbuilder_config_for(
    project_id: str, book_title: str | None, settings: Any | None
) -> tuple[Path | None, dict[str, Any]]:
    """Locate the Bookbuilder config that builds this book, if any."""
    root = _bookbuilder_root(settings)
    try:
        candidates = sorted(root.glob("*.toml"))
    except OSError:
        return None, {"root": str(root), "error": "Bookbuilder root unreadable."}
    slug = project_id.strip().lower()
    wanted = {slug, (book_title or "").strip().lower()}
    for path in candidates:
        try:
            import tomllib as _tomllib

            data = _tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        book = data.get("book") if isinstance(data, dict) else None
        if not isinstance(book, dict):
            continue
        identifier = str(book.get("identifier", "")).strip().lower()
        title = str(book.get("title", "")).strip().lower()
        if identifier in wanted or (title and title in wanted) or path.stem.lower() in wanted:
            return path, {"root": str(root), "identifier": identifier or path.stem}
    return None, {"root": str(root), "checked": len(candidates),
                  "detail": "No bookbuilder config names this book."}


def _bookbuilder_evidence(
    book_id: str, project_id: str, settings: Any | None,
    manuscript_root: Path | None = None, book_title: str | None = None,
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
    config_path, config_detail = _bookbuilder_config_for(project_id, book_title, settings)
    config_note = (f"Config: {config_path}." if config_path
                   else f"No bookbuilder config found ({config_detail.get('checked', 0)} checked).")
    if not found:
        return EvidenceItem(
            book_id=book_id,
            evidence_type="builder_artifacts",
            source_system="bookbuilder",
            source_reference=str(dist / f"{project_id}.epub"),
            result="unavailable",
            freshness="unknown",
            diagnostics=(f"No Bookbuilder outputs observed in {dist} for {project_id!r}. {config_note}"),
            available_actions=["Build with Bookbuilder (`bookbuilder build --config <book>.toml`)."],
            detail={"artifacts": found, "config": str(config_path) if config_path else None},
        )
    newest_artifact = max(int(item.get("mtime_ns", 0)) for item in found)
    chapters = _manuscript_chapter_files(manuscript_root)
    newest_chapter = 0
    for path in chapters:
        try:
            newest_chapter = max(newest_chapter, int(path.stat().st_mtime_ns))
        except OSError:
            continue
    if chapters and newest_artifact and newest_chapter and newest_artifact < newest_chapter:
        freshness: str = "stale"
        freshness_note = "An artifact predates the newest chapter edit; rebuild to refresh."
    elif chapters:
        freshness = "current"
        freshness_note = "Artifacts are newer than every observed chapter file."
    else:
        freshness = "unknown"
        freshness_note = "No live chapters resolved for comparison."
    return EvidenceItem(
        book_id=book_id,
        evidence_type="builder_artifacts",
        source_system="bookbuilder",
        source_reference=str(dist),
        result="unknown",
        freshness=freshness,  # type: ignore[arg-type]
        diagnostics=(
            f"{len(found)} artifact(s) observed; a file's existence proves neither "
            f"validity nor freshness against the current manuscript. {freshness_note} {config_note}"
        ),
        available_actions=["Rebuild with Bookbuilder to refresh artifacts."],
        detail={"artifacts": found, "config": str(config_path) if config_path else None},
    )


def _math_proof_evidence(repo_path: Path, report: Path, data: dict[str, Any]) -> EvidenceItem:
    detail: dict[str, Any] = {
        "claim_ids": [str(item.get("claim_id")) for item in data.get("assessments", [])
                      if isinstance(item, dict) and item.get("claim_id")],
        "statuses": {},
    }
    statuses = detail["statuses"]
    open_obligations = 0
    for item in data.get("assessments", []):
        if not isinstance(item, dict):
            continue
        status = str(item.get("overall_status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        obligations = item.get("unresolved_obligations") or []
        open_obligations += len(obligations) if isinstance(obligations, list) else 0
    artifacts = repo_path / "artifacts" / "math01"
    capabilities: dict[str, Any] = {}
    try:
        capabilities_path = artifacts / "capabilities.json"
        if capabilities_path.is_file():
            capabilities_data = json.loads(capabilities_path.read_text(encoding="utf-8"))
            if isinstance(capabilities_data, list):
                capabilities = {str(entry.get("system")): bool(entry.get("available"))
                                for entry in capabilities_data if isinstance(entry, dict)}
    except (OSError, ValueError):
        capabilities = {}
    formal_path = artifacts / "formal-dependencies.json"
    formal_status: str | None = None
    try:
        if formal_path.is_file():
            formal_data = json.loads(formal_path.read_text(encoding="utf-8"))
            if isinstance(formal_data, dict):
                formal_status = str(formal_data.get("status") or "unknown")
    except (OSError, ValueError):
        formal_status = None
    r3 = (repo_path / "artifacts" / "math01-r3" / "interface-baseline.json").is_file()
    r4 = (repo_path / "artifacts" / "math01-r4" / "statement-alignment.json").is_file()
    inv02e = (repo_path / "docs" / "research" / "math-inv-02" / "02e" / "MATH-INV-02E-ADJUDICATION.md").is_file()
    approvals_path = repo_path / "experiments" / "investigations" / "n1-fermat" / "approvals.json"
    approvals_note = ("N1-Fermat correspondence approval recorded (not a MATH01 approval)."
                      if approvals_path.is_file() else "No human approval record observed.")
    detail.update({
        "systems": capabilities,
        "formal_dependencies": formal_status,
        "r3_interface_baseline": r3,
        "r4_statement_alignment": r4,
        "inv02e_adjudication": ("present; agent-authored, not independent human review."
                                if inv02e else "absent"),
        "human_approval": approvals_note,
    })
    return EvidenceItem(
        book_id="",  # filled by the caller
        evidence_type="proof_claims",
        source_system="proof_tooling",
        source_reference=str(report),
        executed_at=str(data.get("generated_at") or ""),
        result="unknown",
        freshness="unknown",
        diagnostics=(
            f"{len(detail['claim_ids'])} claim assessments: {statuses}. "
            f"Open obligations: {open_obligations}. Systems: "
            + (", ".join(f"{name}={'ok' if ok else 'missing'}" for name, ok in capabilities.items()) or "unknown")
            + f". Formal dependencies: {formal_status or 'unknown'}. "
            "No merged adjudication verdict exists; statuses are source-native, not a readiness score. "
            + approvals_note
        ),
        available_actions=[
            "Inspect artifacts/math01/report.json and open obligations.",
            "Adjudicate claims in the math repository (independent human review still pending).",
        ],
        detail=detail,
    )


PROOF_ADAPTERS = {"math"}


def _proof_evidence(
    book_id: str, project_id: str, repo_path: Path | None
) -> EvidenceItem:
    if project_id not in PROOF_ADAPTERS or repo_path is None:
        return unknown_evidence(
            book_id,
            "proof_claims",
            "proof_tooling",
            diagnostics=("No proof integration registered for this book; "
                         "only 'math' has a proof tooling adapter."),
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
    if not isinstance(data, dict):
        return EvidenceItem(
            book_id=book_id,
            evidence_type="proof_claims",
            source_system="proof_tooling",
            source_reference=str(report),
            result="unknown",
            freshness="unknown",
            diagnostics="Proof report is not a JSON object.",
        )
    item = _math_proof_evidence(repo_path, report, data)
    item.book_id = book_id
    return item


def _alive_evidence(session: Session, settings: Any | None, project_id: str,
                    manuscript_root: str | None = None) -> EvidenceItem:
    """ALIVE connection state as first-class evidence (read-only).

    Synchronous read-only HTTP against the loopback ALIVE API (the living-book
    service is async; publishing stays synchronous). Never breaks the summary:
    any failure to observe reports unknown.
    """
    from mission_control.living_book.client import validate_base_url

    base_url = ""
    try:
        candidate = getattr(settings, "alive_url", "") if settings else ""
        base_url = validate_base_url(str(candidate or "http://127.0.0.1:8000"))
    except Exception as exc:
        return unknown_evidence(
            book_id="",
            evidence_type="alive_connection",
            source_system="alive",
            diagnostics=f"ALIVE endpoint is not configured ({type(exc).__name__}).",
        )
    try:
        import httpx as _httpx
        from urllib.parse import quote as _quote

        with _httpx.Client(timeout=5.0, trust_env=False) as http:
            listing = http.get(
                f"{base_url}/api/v1/living-books"
                f"?manuscript_root={_quote(manuscript_root or '', safe='')}")
            if listing.status_code != 200:
                return unknown_evidence(
                    book_id="",
                    evidence_type="alive_connection",
                    source_system="alive",
                    diagnostics=f"ALIVE returned HTTP {listing.status_code}; not interpreted.",
                )
            books = (listing.json().get("books") or []) if isinstance(listing.json(), dict) else []
            match = next(
                (book for book in books
                 if isinstance(book, dict)
                 and str(book.get("manuscript_root") or "") == (manuscript_root or "")),
                None,
            ) if manuscript_root else (books[0] if books else None)
            if match is None:
                return EvidenceItem(
                    book_id="",
                    evidence_type="alive_connection",
                    source_system="alive",
                    result="pending",
                    freshness="unknown",
                    diagnostics="Book is not connected to ALIVE; no reading session exists.",
                    available_actions=["Connect the manuscript in the Living Book workspace."],
                )
            detail = http.get(
                f"{base_url}/api/v1/living-books/{_quote(str(match.get('id')), safe='')}",
                timeout=10.0).json()
    except Exception as exc:
        return unknown_evidence(
            book_id="",
            evidence_type="alive_connection",
            source_system="alive",
            diagnostics=f"ALIVE state could not be observed ({type(exc).__name__}).",
        )
    if not isinstance(detail, dict):
        return unknown_evidence(
            book_id="",
            evidence_type="alive_connection",
            source_system="alive",
            diagnostics="ALIVE returned an unreadable response.",
        )
    if detail.get("ready") is True:
        chapters = detail.get("chapters") or []
        return EvidenceItem(
            book_id="",
            evidence_type="alive_connection",
            source_system="alive",
            source_reference=str(detail.get("id", "")),
            result="passed",
            freshness="current",
            diagnostics=(f"Reading room ready ({len(chapters)} chapters); "
                         f"model: {(detail.get('model') or {}).get('name', 'unknown')}."),
            available_actions=["Open the Reading Room.", "Ask or improve from the living book."],
            detail={"book_id": detail.get("id")},
        )
    return unknown_evidence(
        book_id="",
        evidence_type="alive_connection",
        source_system="alive",
        diagnostics=f"ALIVE book state is '{detail.get('ready')}'; not interpreted as readiness.",
    )


def get_publishing_overview(session: Session, settings: Any | None) -> dict[str, Any]:
    """All books, one compact row each. Read-only; never validates or builds.

    Each row reuses the per-book summary, so the workbench shows the same
    evidence the book page shows — no second computation path.
    """
    from mission_control.persistence.db import now_iso as _now_iso2

    from mission_control.models import Book as _Book
    from mission_control.models import Project as _Project

    rows = session.execute(
        select(_Book, _Project).join(_Project, _Project.id == _Book.project_id).order_by(
            _Book.title
        )
    ).all()
    books = []
    for book, project in rows:
        try:
            summary = get_publishing_summary(session, settings, project.id)
        except Exception as exc:
            summary = {"project_id": project.id, "error": f"{type(exc).__name__}: {exc}",
                       "evidence": [], "blockers": {"failed": [], "stale": [], "missing": []}}
        blockers = summary.get("blockers", {}) if isinstance(summary, dict) else {}
        identity = summary.get("identity", {}) if isinstance(summary, dict) else {}
        books.append({
            "project_id": project.id,
            "project_name": project.name,
            "book_id": book.id,
            "book_title": book.title,
            "lifecycle": summary.get("lifecycle") if isinstance(summary, dict) else None,
            "publication_gate": summary.get("publication_gate") if isinstance(summary, dict) else "Unknown",
            "chapter_count": summary.get("chapter_count") if isinstance(summary, dict) else None,
            "fingerprint_match": summary.get("fingerprint_match") if isinstance(summary, dict) else None,
            "identity_state": identity.get("identity_state"),
            "failed": list(blockers.get("failed", [])),
            "stale": list(blockers.get("stale", [])),
            "missing": list(blockers.get("missing", [])),
            "identity_conflicts": list(blockers.get("identity_conflicts", [])),
            "error": summary.get("error") if isinstance(summary, dict) else None,
        })
    attention = [row for row in books
                 if row["failed"] or row["stale"] or row["missing"] or row["identity_conflicts"] or row["error"]]
    return {"books": books, "count": len(books), "needs_attention": len(attention),
            "observed_at": _now_iso2(),
            "refresh_note": "Refresh rereads stored evidence only; it never validates, builds or publishes."}


def _norm(value: str | None) -> str:
    import os as _os

    if not value:
        return ""
    try:
        return _os.path.normcase(_os.path.normpath(value))
    except OSError:
        return _os.path.normcase(str(value))


def _chapter_key(filename: str) -> str:
    """Canonical chapter key from a manuscript filename (``01-chapter.md`` → ``01-chapter``)."""
    stem = filename.rsplit(".", 1)[0]
    return stem.strip().lower()


def _chapter_title(path: Path, fallback: str) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:8192]
    except OSError:
        return fallback
    # Hugo-style TOML frontmatter (+++ delimited): title = "...".
    if text.startswith("+++"):
        end = text.find("\n+++", 3)
        head = text[3:end if end != -1 else min(len(text), 2000)]
        for line in head.splitlines():
            stripped = line.strip()
            if stripped.startswith("title"):
                _, _, value = stripped.partition("=")
                title = value.strip().strip("\"'")[:200]
                if title:
                    return title
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()[:200] or fallback
    return fallback


def _mentions_chapter(blob: str, key: str) -> bool:
    return key in blob.lower()


class UnknownProjectError(Exception):
    def __init__(self, project_id: str):
        super().__init__(project_id)
        self.project_id = project_id


# Retained experimental candidates (PUB-06/07/08 historical records).
# Fixed allow-list of repo-relative paths: the backend reads these
# read-only and reports digests + recorded verification summaries. These
# are historical experimental records, not production candidates — the UI
# must label them as such and never present them as current.
RETAINED_CANDIDATES: tuple[dict[str, str], ...] = (
    {"id": "pub6-ch1", "chapter": "01-chapter", "label": "PUB-06 Ch1 surgical candidate (retained record)",
     "candidate": "pub06/ch01/01-chapter-candidate.md",
     "verification": "pub06/ch01/verification-report.json"},
    {"id": "pub7-ch2-run1", "chapter": "02-chapter", "label": "PUB-07 Ch2 run-1 candidate (superseded, preserved verbatim)",
     "candidate": "pub07/ch02-superseded-run1/candidate.md",
     "verification": "pub07/ch02-superseded-run1/verification.json"},
    {"id": "pub7-ch2-rerun", "chapter": "02-chapter", "label": "PUB-07 Ch2 rerun candidate (demonstration candidate)",
     "candidate": "pub07/ch02-rerun/candidate.md",
     "verification": "pub07/ch02-rerun/verification.json"},
    {"id": "pub8-a1", "chapter": "01-chapter", "label": "PUB-08 arm A1 direct-editing candidate (experimental sample)",
     "candidate": "pub08/experiment/arm_a_r1/candidate.md",
     "verification": "pub08/experiment/arm_a_r1/dispatch-record.json"},
    {"id": "pub8-b1", "chapter": "01-chapter", "label": "PUB-08 arm B1 engineered candidate (experimental sample)",
     "candidate": "pub08/experiment/arm_b1/candidate.md",
     "verification": "pub08/experiment/arm_b1/merge-record.json"},
)

_CANDIDATE_BODY_LIMIT = 1_000_000


def _read_text_bounded(path: Path, limit: int = _CANDIDATE_BODY_LIMIT) -> str | None:
    try:
        if not path.is_file() or path.stat().st_size > limit:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _summarize_verification(text: str | None) -> dict[str, Any]:
    """Best-effort extraction of headline verdicts from a retained record.

    Only keys the record itself asserts (status/verdict/pass/fail counts);
    anything absent stays absent — never inferred.
    """
    summary: dict[str, Any] = {"present": text is not None}
    if not text:
        return summary
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        summary["format"] = "non-json"
        summary["excerpt"] = text[:500]
        return summary
    if isinstance(data, dict):
        for key in ("status", "verdict", "outcome", "decision", "assessment",
                    "verify", "verification", "result", "pass", "passed",
                    "fail", "failed"):
            if key in data and not isinstance(data[key], (dict, list)):
                summary[key] = data[key]
    summary["truncatedKeys"] = len(data) if isinstance(data, dict) else 0
    return summary


def get_publishing_candidates(project_id: str) -> dict[str, Any]:
    """Retained experimental candidates by reference. Read-only.

    Only meaningful for the Jev book (the records are Jev-scoped); other
    projects get an empty collection, not an error. Bodies are served
    separately via ``get_publishing_candidate_body``.
    """
    import hashlib as _hashlib

    from mission_control.persistence.db import now_iso as _now_iso_candidates

    repo_root = Path(__file__).resolve().parents[3]
    records = []
    for entry in RETAINED_CANDIDATES:
        cand_path = repo_root / entry["candidate"]
        ver_text = _read_text_bounded(repo_root / entry["verification"], 200_000)
        digest = ""
        size = 0
        if cand_path.is_file():
            try:
                raw = cand_path.read_bytes()[:_CANDIDATE_BODY_LIMIT]
                size = len(raw)
                digest = _hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
            except OSError:
                pass
        records.append({
            "id": entry["id"], "chapter": entry["chapter"], "label": entry["label"],
            "kind": "historical-experimental",
            "candidate_path": entry["candidate"],
            "available": cand_path.is_file(),
            "bytes": size, "fingerprint": digest,
            "verification": _summarize_verification(ver_text),
            "note": "Historical experimental record with recorded verification only; "
                    "not a production candidate and not evidence of publication readiness.",
        })
    return {"project_id": project_id, "candidates": records, "count": len(records),
            "observed_at": _now_iso_candidates()}


def get_publishing_candidate_body(record_id: str) -> dict[str, Any]:
    """Full markdown body of one retained candidate. Read-only, bounded."""
    repo_root = Path(__file__).resolve().parents[3]
    entry = next((e for e in RETAINED_CANDIDATES if e["id"] == record_id), None)
    if entry is None:
        raise KeyError(record_id)
    text = _read_text_bounded(repo_root / entry["candidate"])
    if text is None:
        return {"id": record_id, "available": False,
                "reason": "Candidate file is missing or exceeds the bounded read size."}
    import hashlib as _hashlib
    return {"id": record_id, "available": True, "markdown": text,
            "bytes": len(text.encode("utf-8")),
            "fingerprint": _hashlib.sha256(
                text.replace("\r\n", "\n").encode("utf-8")).hexdigest()}


def get_publishing_chapters(
    session: Session, settings: Any | None, project_id: str
) -> dict[str, Any]:
    """Per-chapter publication state. Read-only aggregation, no new tables.

    Chapters come from the Writer registry manuscript directory. State per
    chapter: ``unknown`` (no assessment ever recorded), ``stale`` (latest
    assessment fingerprint differs from current sources), ``assessed``
    (named in the latest assessment's gates/issues or a project follow-up),
    else ``unassessed``. Zero findings are never reported as success: an
    unassessed chapter carries no verdict at all.
    """
    import hashlib as _hashlib
    import json as _json

    from mission_control.models import Project as _Project
    from mission_control.models import PublicationApproval as _Approval
    from mission_control.models import PublicationAssessment as _Assessment
    from mission_control.models import PublicationFollowup as _Followup
    from mission_control.models import PublicationGateResult as _Gate
    from mission_control.models import PublicationIssue as _Issue
    from mission_control.persistence.db import now_iso as _now_iso
    from mission_control.publication.fingerprint import _sha_text
    from mission_control.writer_registry import (
        load_writer_registry,
        resolve_registry_path,
    )

    project = session.get(_Project, project_id)
    if project is None:
        raise UnknownProjectError(project_id)
    try:
        snapshot = load_writer_registry(
            resolve_registry_path(settings) if settings is not None else None
        )
    except Exception:
        snapshot = None
    definition = snapshot.books.get(project_id) if snapshot else None
    if definition is None or not getattr(definition, "available", False):
        return {"project_id": project_id, "chapters": [], "count": 0,
                "assessment": None, "approvals": [],
                "error": "Manuscript directory is not available from the Writer registry."}
    try:
        chapter_dir = Path(definition.chapter_dir)
    except (OSError, TypeError):
        return {"project_id": project_id, "chapters": [], "count": 0,
                "assessment": None, "approvals": [],
                "error": "Configured chapter directory is not a usable path."}
    try:
        files = sorted(
            (p for p in chapter_dir.iterdir()
             if p.is_file() and len(p.name) >= 12 and p.name[0:2].isdigit()
             and p.name.lower().endswith("-chapter.md")),
            key=lambda p: p.name,
        )[:500]
    except OSError as exc:
        return {"project_id": project_id, "chapters": [], "count": 0,
                "assessment": None, "approvals": [],
                "error": f"Cannot list chapter directory: {exc}."}

    current_fp = fingerprint_manuscript(chapter_dir, "*.md")
    current_fp_value = current_fp.get("fingerprint") if current_fp.get("ok") else None
    # Assessment-scope fingerprint: assessments bind ONLY numbered-chapter
    # files (service.build_snapshot: "file:sha" per *-chapter.md). Comparing
    # against the book-scope (*.md, incl. _index.md) fingerprint would mark
    # everything stale on scope difference alone — a false positive. So
    # staleness is decided on the assessment's own scope; the book-scope
    # fingerprint is still reported for transparency.
    assessment_scope_rows = []
    for path in files:
        try:
            assessment_scope_rows.append(
                f"{path.name}:{_sha_text(path.read_text(encoding='utf-8', errors='replace'))}")
        except OSError:
            pass
    import hashlib as _hashlib_scope
    assessment_scope_fp = _hashlib_scope.sha256(
        "\n".join(assessment_scope_rows).encode("utf-8")).hexdigest() if assessment_scope_rows else None
    latest = session.scalars(
        select(_Assessment).where(_Assessment.project_id == project_id)
        .order_by(desc(_Assessment.created_at)).limit(1)
    ).first()
    assessment = None
    fingerprint_match: bool | None = None
    if latest is not None:
        fingerprint_match = bool(
            assessment_scope_fp and latest.manuscript_fingerprint
            and latest.manuscript_fingerprint == assessment_scope_fp)
        assessment = {
            "id": latest.id,
            "status": latest.assessment_status,
            "freshness": latest.freshness,
            "fingerprint_match": fingerprint_match,
            "created_at": latest.created_at,
        }
    gate_rows = session.scalars(
        select(_Gate).where(_Gate.assessment_id == latest.id)
    ).all() if latest is not None else []
    issue_rows = session.scalars(
        select(_Issue).where(_Issue.assessment_id == latest.id)
    ).all() if latest is not None else []
    followup_rows = session.scalars(
        select(_Followup).where(_Followup.project_id == project_id)
    ).all()
    approvals = [
        {"id": r.id, "decision": r.decision, "rationale": r.rationale,
         "manuscript_fingerprint": r.manuscript_fingerprint,
         "freshness": r.freshness, "created_at": r.created_at}
        for r in session.scalars(
            select(_Approval).where(_Approval.project_id == project_id)
            .order_by(desc(_Approval.created_at)).limit(10)
        ).all()
    ]

    def _blob(*parts: Any) -> str:
        try:
            return _json.dumps(parts, default=str)[:4096]
        except (TypeError, ValueError):
            return ""

    gate_blob = _blob([(g.gate_id, g.evidence_refs, g.detail) for g in gate_rows])
    named_in_assessment: set[str] = set()
    chapters = []
    for path in files:
        key = _chapter_key(path.name)
        try:
            raw = path.read_bytes()[:2_000_000]
        except OSError:
            raw = b""
        digest = _hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() if raw else ""
        title = _chapter_title(path, key)
        issue_refs = [
            {"id": r.id, "gate_id": r.gate_id, "issue_type": r.issue_type,
             "severity": r.severity, "status": r.status,
             "author_review_status": r.author_review_status}
            for r in issue_rows
            if _mentions_chapter(_blob(r.source_refs, r.evidence_refs, r.rationale), key)
        ]
        followup_refs = [
            {"id": r.id, "title": r.title, "status": r.status,
             "evidence_type": r.evidence_type}
            for r in followup_rows
            if _mentions_chapter(_blob(r.source_reference, r.title, r.rationale), key)
        ]
        named = bool(issue_refs or followup_refs or _mentions_chapter(gate_blob, key))
        if named:
            named_in_assessment.add(key)
        if latest is None:
            state = "unknown"
        elif fingerprint_match is False:
            state = "stale"
        elif named:
            state = "assessed"
        else:
            state = "unassessed"
        chapters.append({
            "chapter_id": key,
            "title": title,
            "filename": path.name,
            "bytes": len(raw),
            "fingerprint": digest,
            "state": state,
            "issues": issue_refs,
            "followups": followup_refs,
        })
    return {"project_id": project_id, "chapters": chapters, "count": len(chapters),
            "chapter_named_in_assessment": sorted(named_in_assessment),
            "assessment": assessment, "approvals": approvals,
            "manuscript_fingerprint": current_fp_value,
            "assessment_scope_fingerprint": assessment_scope_fp,
            "assessment_scope_note": "Staleness compares the assessment fingerprint against numbered-chapter files only (the assessment's own scope); the book fingerprint covers all *.md files.",
            "observed_at": _now_iso()}
