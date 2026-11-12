"""Publication-readiness service (MC-QUALITY-03D).

Deterministic release assurance over existing evidence. No model calls, no
manuscript writes, no deployment. Every gate result is auditable to stored
evidence and a versioned policy.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.models import (
    Project,
    PublicationApproval,
    PublicationAssessment,
    PublicationCalibrationReview,
    PublicationGateResult,
    PublicationIssue,
    PublicationPreflight,
    QualityReview,
)
from mission_control.publication import policy
from mission_control.schemas import (
    PublicationApprovalCreate,
    PublicationCalibrationCreate,
)

PREFLIGHT_SCHEMA = "workbench-publication-preflight-v1"
PREFLIGHT_OUTPUT_BOUND = 262144
CALIBRATION_SAMPLE_VERSION = 1

ISSUE_DECISIONS = (
    "ACCEPT FINDING",
    "REJECT FINDING",
    "DEFER",
    "ACCEPT LIMITATION",
    "REQUEST RECHECK",
)
APPROVAL_DECISIONS = ("APPROVE_RELEASE_CANDIDATE", "REVOKE_APPROVAL")


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dossier_dir(data_dir: Path, assessment_id: str) -> Path:
    # IDs carry a "kind:hex" shape; colons are not valid in Windows paths.
    return Path(data_dir) / "publication_dossiers" / assessment_id.replace(":", "-")


def build_snapshot(book_root: str) -> dict:
    """Read-only chapter manifest with workbench-identical text hashing."""
    root = Path(book_root)
    if not root.is_dir():
        raise ValidationProblem(f"book root is not available: {book_root}")
    chapters = []
    for path in sorted(root.iterdir()):
        if not (path.is_file() and path.name.endswith("-chapter.md")):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValidationProblem(f"chapter unreadable: {path.name}: {exc}") from exc
        chapters.append({"file": path.name, "sha256": _sha_text(text),
                         "bytes": len(text.encode("utf-8"))})
    if not chapters:
        raise ValidationProblem("no numbered chapters found under the book root")
    fingerprint = hashlib.sha256(
        "\n".join(f"{c['file']}:{c['sha256']}" for c in chapters).encode("utf-8")
    ).hexdigest()
    return {"book_root": str(root), "chapters": chapters,
            "manuscript_fingerprint": fingerprint, "chapter_count": len(chapters)}


def _ensure_workbench():
    """Make the Workbench checkout importable for the read-only preflight.

    Smallest reliable interface: in-process call of ``build_preflight``
    (no model, no writes). Prefers WORKBENCH_SRC, then the conventional
    sibling checkout. Raises ImportError when unavailable — callers record
    NOT_RUN instead of inventing results.
    """
    import os
    import sys

    try:
        import workbench.publication  # noqa: F401
        return
    except ImportError:
        pass
    candidates = []
    env_src = os.environ.get("WORKBENCH_SRC", "").strip()
    if env_src:
        candidates.append(env_src)
    candidates.append(r"C:\Projects\workbench\src")
    for candidate in candidates:
        try:
            if candidate and Path(candidate).is_dir():
                if candidate not in sys.path:
                    sys.path.insert(0, candidate)
                import workbench.publication  # noqa: F401
                return
        except ImportError:
            continue
    raise ImportError("workbench publication module unavailable")


def run_preflight(book_root: str, project_id: str, out_dir: Path) -> dict:
    """Consume the Workbench publication preflight via its actual contract.

    In-process call of ``build_preflight`` (read-only, no model). The full
    report is stored as a dossier file — never truncated. Oversized reports
    (beyond the capability's declared output bound) are recorded explicitly.
    """
    try:
        _ensure_workbench()
        from workbench.publication import SCHEMA, build_preflight
    except ImportError as exc:
        return {"status": "NOT_RUN", "error": f"workbench publication module unavailable: {exc}"}
    from workbench.publication import PreflightError

    try:
        report = build_preflight(book_root, project_id=project_id, scope="book")
    except PreflightError as exc:
        return {"status": "ERROR", "error": f"preflight refused the source: {exc}"}
    except Exception as exc:  # noqa: BLE001 - transport/dependency failure is data
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        return {"status": "ERROR",
                "error": f"preflight response violates its contract (schema={report.get('schema')!r})"}
    for key in ("manuscript_fingerprint", "input_manifest_fingerprint",
                "project_id", "publication_readiness", "findings"):
        if key not in report:
            return {"status": "ERROR",
                    "error": f"preflight response missing required key {key!r}"}
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    report_bytes = len(payload.encode("utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "preflight-report.json"
    report_path.write_text(payload, encoding="utf-8")
    status = "CURRENT"
    error = ""
    if report_bytes > PREFLIGHT_OUTPUT_BOUND:
        # No silent truncation: the full report is stored; gates treat the
        # bound breach as an explicit limitation, not a silent pass.
        status = "OVERSIZED"
        error = (f"report is {report_bytes} bytes, beyond the capability bound "
                 f"{PREFLIGHT_OUTPUT_BOUND}; full report stored, findings paged by file")
    if not report.get("snapshot_consistent", False):
        status = "ERROR"
        error = (error + " | " if error else "") + "book changed mid-scan; report is not current"
    return {
        "status": status,
        "error": error,
        "schema_id": report["schema"],
        "schema_version": "",
        "manuscript_fingerprint": report["manuscript_fingerprint"],
        "input_manifest_fingerprint": report["input_manifest_fingerprint"],
        "chapters_found": int(report.get("inventory", {}).get("chapters_found", 0)),
        "findings_count": len(report.get("findings", [])),
        "report_bytes": report_bytes,
        "report_path": str(report_path),
        "snapshot_consistent": bool(report.get("snapshot_consistent", False)),
        "report": report,
    }


def run_hugo_build(site_root: str | None, out_dir: Path, *, timeout: int = 600) -> dict:
    """Allowlisted production-build verification. Output goes to a temp dir
    outside the book — the canonical source is never modified.

    A missing Hugo site configuration is NOT_RUN (no build harness), not a
    failed build. Only an attempted build that exits nonzero FAILs."""
    if not site_root:
        return {"status": "NOT_RUN",
                "error": "no Hugo site configuration found above the book root; build not verifiable"}
    hugo = shutil.which("hugo")
    if hugo is None:
        return {"status": "NOT_RUN", "error": "hugo executable not found on PATH"}
    dest = out_dir / "hugo-public"
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    cmd = [hugo, "--source", site_root, "--destination", str(dest), "--gc", "--minify"]
    try:
        version = subprocess.run([hugo, "version"], capture_output=True, text=True,
                                 timeout=60)
        version_text = (version.stdout or version.stderr or "").strip().splitlines()
        version_text = version_text[0] if version_text else "unknown"
    except Exception:  # noqa: BLE001
        version_text = "unknown"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "ERROR", "hugo_version": version_text,
                "error": f"production build exceeded {timeout}s; nothing was concluded"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "ERROR", "hugo_version": version_text,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()[-15:]
    if proc.returncode == 0:
        return {"status": "CURRENT", "hugo_version": version_text,
                "error": "", "output": "\n".join(tail),
                "exit_code": 0, "destination": str(dest)}
    return {"status": "FAILED", "hugo_version": version_text,
            "error": f"hugo exited {proc.returncode}", "output": "\n".join(tail),
            "exit_code": proc.returncode, "destination": str(dest)}


def _evidence_inputs(session: Session, project_id: str, technical_scope: str) -> dict:
    from mission_control.quality import service as qs
    from mission_control.technical import service as tech

    try:
        ws = qs.workspace(session, project_id)
        prose = {"chapters_total": ws.chapters_total, "chapters_current": ws.chapters_current,
                 "limitations": list(ws.limitations or [])}
    except Exception as exc:  # noqa: BLE001 - missing evidence is a gate input
        prose = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    try:
        discovered = [d.chapter_id for d in qs.eligibility(session, project_id, model=None)]
    except Exception:  # noqa: BLE001
        discovered = []
    try:
        overview = tech.book_overview(session, project_id)
    except Exception as exc:  # noqa: BLE001
        overview = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    chapters: dict[str, dict] = {}
    assessed = sorted({r.chapter_id for r in tech.list_claims(
        session, project_id=project_id, limit=100000)})
    for chapter_id in assessed:
        try:
            a = tech.chapter_assessment(session, project_id, chapter_id)
            chapters[chapter_id] = {"claims_total": a.claims_total,
                                    "claims_unresolved": a.claims_unresolved,
                                    "by_status": dict(a.by_status)}
        except Exception as exc:  # noqa: BLE001
            chapters[chapter_id] = {"error": f"{type(exc).__name__}"}
    completeness: dict[str, dict] = {}
    for chapter_id in assessed:
        try:
            completeness[chapter_id] = tech.chapter_completeness(session, project_id, chapter_id)
        except Exception as exc:  # noqa: BLE001
            completeness[chapter_id] = {"error": f"{type(exc).__name__}"}
    reviews = [{"finding_id": r.finding_id, "decision": r.decision,
                "source_digest": r.source_digest or ""}
               for r in session.query(QualityReview).all()]
    from mission_control.models import TechnicalEvidenceRequirement as _R
    req_by_id = {r.id: r for r in session.query(_R).all()}
    calibration = [{"requirement_id": r.requirement_id,
                    "requirement_applicable": r.requirement_applicable,
                    "would_block": bool(r.would_block), "verdict": r.verdict or "",
                    "correction": r.correction or "",
                    "satisfaction": (req_by_id.get(r.requirement_id).satisfaction
                                     if req_by_id.get(r.requirement_id) else "UNKNOWN")}
                   for r in session.query(PublicationCalibrationReview).all()]
    from mission_control.models import TechnicalVerification as _V
    latest: dict[str, dict] = {}
    for v in session.query(_V).order_by(_V.created_at).all():
        latest[v.claim_id] = {"status": v.status, "method": v.method}
    from mission_control.models import TechnicalClaim as _C
    claim_chapters = {c.id: c.chapter_id
                      for c in session.query(_C).filter_by(project_id=project_id).all()}
    contradictions = [
        {"claim_id": cid, "chapter_id": claim_chapters.get(cid, ""),
         "reviewed": _reviewed(cid, reviews)}
        for cid, v in latest.items() if v["status"] == "CONTRADICTED_BY_EVIDENCE"]
    return {"prose": prose, "discovered": discovered, "overview": overview,
            "chapters": chapters, "completeness": completeness,
            "reviews": reviews, "calibration": calibration,
            "contradictions": contradictions}


def _reviewed(claim_id: str, reviews: list[dict]) -> bool:
    return any(r["finding_id"] == claim_id and r["decision"] in ("ACCEPT", "DEFER")
               for r in reviews)


def evaluate_gates(snapshot: dict, preflight: dict, build: dict,
                   evidence: dict, approvals: list[dict]) -> list[dict]:
    """Deterministic gate evaluation. Returns gate result dicts (no persistence)."""
    results: list[dict] = []

    def add(gate_id: str, result: str, detail: str, evidence_refs: list,
            limitations: str = "") -> None:
        gate = policy.get_gate(gate_id)
        results.append({
            "gate_id": gate_id, "gate_version": gate["gate_version"],
            "gate_group": gate["gate_group"], "result": result,
            "blocking": gate["failure_severity"] == "blocker",
            "waivable": gate["waiver_policy"] == "waivable",
            "detail": detail, "evidence_refs": evidence_refs,
            "limitations": limitations,
        })

    # G1 identity
    if snapshot.get("chapter_count", 0) > 0 and len(snapshot.get("manuscript_fingerprint", "")) == 64:
        add("manuscript_identity", policy.PASS,
            f"{snapshot['chapter_count']} chapters hashed; snapshot {snapshot['manuscript_fingerprint'][:12]}",
            ["snapshot:chapter_manifest"])
    else:
        add("manuscript_identity", policy.ERROR, "chapter manifest is empty or unfingerprinted",
            ["snapshot:chapter_manifest"])

    # G2/G4 from preflight findings
    findings = (preflight.get("report") or {}).get("findings", []) if preflight.get("report") else []
    if preflight.get("status") in ("NOT_RUN", "ERROR") or not preflight.get("report"):
        add("chapter_structure", policy.NOT_RUN if preflight.get("status") == "NOT_RUN" else policy.ERROR,
            f"preflight {preflight.get('status')}: {preflight.get('error', '')[:200]}",
            ["preflight:report"])
        add("assets_references", policy.NOT_RUN if preflight.get("status") == "NOT_RUN" else policy.ERROR,
            f"preflight {preflight.get('status')}: {preflight.get('error', '')[:200]}",
            ["preflight:report"])
    else:
        by_code: dict[str, list] = {}
        for found in findings:
            by_code.setdefault(found.get("code", ""), []).append(found)
        dup = by_code.get("chapter_number_duplicate", [])
        mismatch = by_code.get("index_chapter_count_mismatch", [])
        if dup or mismatch:
            add("chapter_structure", policy.FAIL,
                f"{len(dup)} duplicate-number and {len(mismatch)} index-count findings",
                [f"preflight:finding:{f.get('code')}" for f in (dup + mismatch)[:10]])
        else:
            warns = [c for c in ("chapter_number_gap", "part_range_incomplete",
                                 "parts_not_declared", "index_status_stale") if by_code.get(c)]
            add("chapter_structure", policy.WARNING if warns else policy.PASS,
                "numbering consistent" + (f"; advisory: {', '.join(warns)}" if warns else ""),
                [f"preflight:stage:metadata"])
        highs = [f for f in findings
                 if f.get("code") in ("asset_missing", "link_target_missing",
                                      "svg_not_well_formed", "svg_contains_script",
                                      "svg_event_handler", "svg_javascript_uri")
                 and f.get("severity") == "high"]
        mediums = [f for f in findings if f.get("severity") in ("medium", "low")]
        if highs:
            add("assets_references", policy.FAIL,
                f"{len(highs)} high-severity asset/reference findings",
                [f"preflight:finding:{f.get('code')}:{f.get('chapter', '')}" for f in highs[:10]],
                "waivable only via explicit ACCEPT LIMITATION; never auto-passed")
        elif mediums:
            add("assets_references", policy.WARNING,
                f"{len(mediums)} medium/low illustration findings; no high-severity findings",
                ["preflight:stage:illustrations"])
        else:
            add("assets_references", policy.PASS, "all referenced assets resolve; no high findings",
                ["preflight:stage:illustrations"])

    # G3 build
    if build.get("status") == "CURRENT":
        add("publication_build", policy.PASS,
            f"production build exit 0 ({build.get('hugo_version', 'unknown')}); output outside the book root",
            ["build:record"])
    elif build.get("status") == "FAILED":
        add("publication_build", policy.FAIL,
            f"{build.get('error', 'build failed')}; {build.get('output', '')[:200]}",
            ["build:record"],
            "a failed build says nothing about prose or technical correctness")
    elif build.get("status") == "NOT_RUN":
        add("publication_build", policy.NOT_RUN, build.get("error", "build not run"),
            ["build:record"])
    else:
        add("publication_build", policy.ERROR, build.get("error", "build error")[:300],
            ["build:record"])

    # G5 prose
    prose = evidence.get("prose", {})
    discovered = evidence.get("discovered", [])
    if "error" in prose:
        add("prose_review", policy.ERROR, prose["error"], ["prose:workspace"])
    elif prose.get("chapters_total", 0) == 0:
        add("prose_review", policy.NOT_RUN, "no prose evaluations recorded", ["prose:workspace"])
    elif discovered and prose.get("chapters_current", 0) < len(discovered):
        add("prose_review", policy.NOT_RUN,
            f"{prose.get('chapters_current', 0)} of {len(discovered)} discovered chapters current",
            ["prose:workspace", "quality:discovery"])
    elif prose.get("chapters_current", 0) < prose.get("chapters_total", 0):
        add("prose_review", policy.WARNING, "some evaluations stale; review completion required, not scores",
            ["prose:workspace"])
    else:
        add("prose_review", policy.PASS,
            f"{prose.get('chapters_current', 0)} of {prose.get('chapters_total', 0)} chapters current; no score threshold imposed",
            ["prose:workspace"])

    # G6 technical
    overview = evidence.get("overview", {})
    chapters = evidence.get("chapters", {})
    reviews = evidence.get("reviews", [])
    if "error" in overview or not chapters:
        add("technical_verification", policy.NOT_RUN,
            overview.get("error", "no technical claims inventoried"),
            ["technical:overview"])
    else:
        assessed_chapters = sorted(chapters)
        unreviewed = [c["claim_id"] for c in evidence.get("contradictions", [])
                      if not c.get("reviewed")]
        known = [f"{c}: {chapters[c].get('claims_total', 0)} claims, "
                 f"{chapters[c].get('claims_unresolved', 0)} unresolved"
                 for c in assessed_chapters]
        refs = ["technical:overview"] + [f"technical:chapter:{c}" for c in assessed_chapters]
        if unreviewed:
            add("technical_verification", policy.FAIL,
                f"unreviewed contradictions: {', '.join(unreviewed)} | " + "; ".join(known),
                refs)
        elif not discovered:
            add("technical_verification", policy.UNKNOWN,
                "chapter discovery unavailable; coverage unverifiable against "
                f"{overview.get('chapters_with_claims', 0)} chapters with claims | " + "; ".join(known),
                refs + ["quality:discovery"],
                "a missing denominator is never treated as full coverage")
        elif len(assessed_chapters) < len(discovered):
            # Pilot-scope findings are still evaluated and reported; the gate
            # itself stays unknown at book level per policy v1.
            add("technical_verification", policy.NOT_RUN,
                f"pilot covers {len(assessed_chapters)} of {len(discovered)} chapters "
                f"({', '.join(assessed_chapters)}); full-book coverage not established; "
                "no unreviewed contradictions in pilot scope | " + "; ".join(known),
                refs,
                "pilot scope only; a full-book rollout is separately authorized")
        elif overview.get("claims_unresolved", 0):
            add("technical_verification", policy.WARNING,
                f"full chapter coverage; {overview.get('claims_unresolved', 0)} claims unresolved | "
                + "; ".join(known),
                refs)
        else:
            add("technical_verification", policy.PASS,
                "full chapter coverage with no unresolved or contradicted claims",
                refs)

    # G7 completeness (calibration-gated)
    calibration = evidence.get("calibration", [])
    completeness = evidence.get("completeness", {})
    if not completeness:
        add("evidence_completeness", policy.NOT_RUN, "no completeness assessments recorded",
            ["completeness:reports"])
    else:
        # A human-reviewed blocker is verified evidence regardless of
        # calibration coverage; unreviewed priorities stay advisory.
        blockers = [c["requirement_id"] for c in calibration
                    if c.get("would_block")
                    and c.get("satisfaction") in ("UNRESOLVED", "NOT_ASSESSED", "UNKNOWN")]
        if blockers:
            add("evidence_completeness", policy.FAIL,
                f"human-reviewed release blockers unresolved: {', '.join(blockers[:10])}",
                ["completeness:reports", "calibration:reviews"] + [
                    f"requirement:{b}" for b in blockers[:10]],
                "only human-reviewed requirements can block; see calibration verdicts")
        elif not any("P0" in (c.get("verdict", "") + c.get("correction", ""))
                     for c in calibration) or len(calibration) < 30:
            open_gaps = sum(r.get("open_gaps", 0) for r in completeness.values()
                            if isinstance(r, dict))
            add("evidence_completeness", policy.UNKNOWN,
                f"requirement calibration pending ({len(calibration)} reviewed); "
                f"unconfirmed priorities are advisory only and cannot block; "
                f"{open_gaps} open gaps recorded, none promoted to blockers",
                ["completeness:reports", "calibration:reviews"],
                "calibration must precede release use of P0 labels")
        else:
            add("evidence_completeness", policy.NOT_YET_ASSESSED,
                "calibrated; full assessment coverage still required for READY",
                ["completeness:reports", "calibration:reviews"])

    # G8 approval
    fresh = [a for a in approvals if a.get("freshness") == "CURRENT"
             and a.get("decision") == "APPROVE_RELEASE_CANDIDATE"]
    if fresh:
        add("author_approval", policy.PASS,
            f"approved by {fresh[-1].get('reviewer', 'author')} at {fresh[-1].get('created_at', '')}",
            [f"approval:{fresh[-1].get('id', '')}"])
    elif approvals:
        add("author_approval", policy.WARNING,
            f"{len(approvals)} approval record(s) but none fresh for this snapshot",
            [f"approval:{a.get('id', '')}" for a in approvals])
    else:
        add("author_approval", policy.NOT_YET_ASSESSED, "no author approval recorded",
            ["approval:records"])
    return results


def derive_issues(assessment_id: str, gate_results: list[dict]) -> list[dict]:
    """Normalized release issues from gate outcomes. Blocking comes from
    policy and verified facts only."""
    issues = []
    for gate in gate_results:
        gid = gate["gate_id"]
        if gate["result"] == policy.FAIL:
            issues.append({
                "gate_id": gid,
                "issue_type": "confirmed_build_blocker" if gid == "publication_build"
                else "required_publication_asset_missing" if gid == "assets_references"
                else "invalid_mandatory_metadata" if gid == "chapter_structure"
                else "verified_technical_blocker",
                "severity": "blocker",
                "verification_method": "deterministic",
                "status": "OPEN",
                "waiver_eligibility": "waivable" if gate["waivable"] else "nonwaivable",
                "author_review_status": "pending",
                "source_refs": [],
                "evidence_refs": gate["evidence_refs"],
                "rationale": gate["detail"],
            })
        elif gate["result"] == policy.WARNING:
            issues.append({
                "gate_id": gid,
                "issue_type": "evidence_gap_requiring_attention"
                if gid in ("evidence_completeness", "technical_verification")
                else "nonblocking_editorial_warning",
                "severity": "advisory",
                "verification_method": "deterministic",
                "status": "OPEN",
                "waiver_eligibility": "waivable",
                "author_review_status": "pending",
                "source_refs": [],
                "evidence_refs": gate["evidence_refs"],
                "rationale": gate["detail"],
            })
        elif gate["result"] in (policy.NOT_RUN, policy.UNKNOWN, policy.STALE, policy.ERROR,
                                 policy.NOT_YET_ASSESSED):
            if gate["result"] == policy.NOT_YET_ASSESSED and not gate["blocking"]:
                issues.append({
                    "gate_id": gid,
                    "issue_type": "unresolved_required_review",
                    "severity": "advisory",
                    "verification_method": "deterministic",
                    "status": "OPEN",
                    "waiver_eligibility": "waivable",
                    "author_review_status": "pending",
                    "source_refs": [],
                    "evidence_refs": gate["evidence_refs"],
                    "rationale": gate["detail"],
                })
            else:
                issues.append({
                    "gate_id": gid,
                    "issue_type": "incomplete_mandatory_assessment",
                    "severity": "unknown",
                    "verification_method": "deterministic",
                    "status": "OPEN",
                    "waiver_eligibility": "nonwaivable",
                    "author_review_status": "pending",
                    "source_refs": [],
                    "evidence_refs": gate["evidence_refs"],
                    "rationale": gate["detail"],
                })
    return issues


def get_assessment(session: Session, assessment_id: str) -> PublicationAssessment:
    record = session.get(PublicationAssessment, assessment_id)
    if record is None:
        raise NotFound("Publication assessment does not exist")
    return record


def to_read(session: Session, record: PublicationAssessment) -> dict:
    gates = session.scalars(
        select(PublicationGateResult)
        .where(PublicationGateResult.assessment_id == record.id)
        .order_by(PublicationGateResult.gate_id)
    ).all()
    issues = session.scalars(
        select(PublicationIssue)
        .where(PublicationIssue.assessment_id == record.id)
        .order_by(desc(PublicationIssue.created_at))
    ).all()
    approvals = session.scalars(
        select(PublicationApproval)
        .where(PublicationApproval.assessment_id == record.id)
        .order_by(PublicationApproval.created_at)
    ).all()
    return {
        "id": record.id,
        "project_id": record.project_id,
        "book_id": record.book_id or "",
        "book_root": record.book_root or "",
        "policy_version": record.policy_version,
        "technical_scope": record.technical_scope,
        "manuscript_fingerprint": record.manuscript_fingerprint,
        "input_manifest_fingerprint": record.input_manifest_fingerprint,
        "chapter_count": record.chapter_count,
        "assessment_status": record.assessment_status,
        "freshness": record.freshness,
        "readiness_detail": record.readiness_detail or "",
        "preflight_id": record.preflight_id,
        "gates": [{
            "id": g.id, "gate_id": g.gate_id, "gate_version": g.gate_version,
            "gate_group": g.gate_group, "result": g.result, "blocking": bool(g.blocking),
            "waivable": bool(g.waivable), "detail": g.detail or "",
            "evidence_refs": list(g.evidence_refs or []),
            "limitations": g.limitations or "", "created_at": g.created_at} for g in gates],
        "issues": [{
            "id": i.id, "gate_id": i.gate_id, "issue_type": i.issue_type,
            "severity": i.severity, "verification_method": i.verification_method,
            "status": i.status, "waiver_eligibility": i.waiver_eligibility,
            "author_review_status": i.author_review_status,
            "source_refs": list(i.source_refs or []),
            "evidence_refs": list(i.evidence_refs or []),
            "rationale": i.rationale or "", "created_at": i.created_at} for i in issues],
        "approvals": [{
            "id": a.id, "assessment_id": a.assessment_id, "decision": a.decision,
            "rationale": a.rationale or "",
            "manuscript_fingerprint": a.manuscript_fingerprint,
            "input_manifest_fingerprint": a.input_manifest_fingerprint,
            "policy_version": a.policy_version,
            "accepted_limitation_ids": list(a.accepted_limitation_ids or []),
            "freshness": a.freshness, "reviewer": a.reviewer or "",
            "created_at": a.created_at} for a in approvals],
        "created_at": record.created_at,
    }


def _persist_gates_issues(session: Session, assessment_id: str,
                          gate_results: list[dict]) -> None:
    for gate in gate_results:
        session.add(PublicationGateResult(
            id=f"pubgate:{uuid.uuid4().hex[:12]}", assessment_id=assessment_id,
            gate_id=gate["gate_id"], gate_version=gate["gate_version"],
            gate_group=gate["gate_group"], result=gate["result"],
            blocking=bool(gate["blocking"]), waivable=bool(gate["waivable"]),
            detail=gate["detail"], evidence_refs=list(gate["evidence_refs"]),
            limitations=gate.get("limitations", "")))
    for issue in derive_issues(assessment_id, gate_results):
        session.add(PublicationIssue(
            id=f"pubissue:{uuid.uuid4().hex[:12]}", assessment_id=assessment_id,
            gate_id=issue["gate_id"], issue_type=issue["issue_type"],
            severity=issue["severity"], verification_method=issue["verification_method"],
            status=issue["status"], waiver_eligibility=issue["waiver_eligibility"],
            author_review_status=issue["author_review_status"],
            source_refs=list(issue["source_refs"]),
            evidence_refs=list(issue["evidence_refs"]), rationale=issue["rationale"]))
    session.flush()


def create_assessment(session: Session, settings, *, project_id: str,
                      book_id: str = "", policy_version: str = policy.POLICY_VERSION,
                      technical_scope: str = "pilot",
                      force: bool = False) -> PublicationAssessment:
    """Build a release-candidate assessment. Read-only against manuscripts.

    Idempotent: the same project + snapshot + policy reuses the latest
    assessment unless force=True.
    """
    if policy_version != policy.POLICY_VERSION:
        raise ValidationProblem(f"unknown policy version {policy_version!r}")
    if technical_scope not in ("pilot", "full"):
        raise ValidationProblem("technical_scope must be pilot or full")
    if project_id and session.get(Project, project_id) is None:
        raise ValidationProblem("Project does not exist")
    from mission_control.quality.service import resolve_book_root
    book_root = resolve_book_root(session, project_id)
    snapshot = build_snapshot(book_root)

    if not force:
        existing = session.scalars(
            select(PublicationAssessment)
            .where(PublicationAssessment.project_id == project_id,
                   PublicationAssessment.policy_version == policy_version,
                   PublicationAssessment.manuscript_fingerprint == snapshot["manuscript_fingerprint"])
            .order_by(desc(PublicationAssessment.created_at))
            .limit(1)
        ).first()
        if existing is not None:
            return existing

    assessment_id = f"pubass:{uuid.uuid4().hex[:12]}"
    out_dir = dossier_dir(settings.data_dir, assessment_id)

    preflight = run_preflight(book_root, project_id, out_dir)

    site_root: str | None = None
    # The Hugo site root is the directory holding hugo.toml above the book.
    candidate = Path(book_root)
    while candidate != candidate.parent and not (candidate / "hugo.toml").exists():
        candidate = candidate.parent
    if (candidate / "hugo.toml").exists():
        site_root = str(candidate)
    build = run_hugo_build(site_root, out_dir)

    evidence = _evidence_inputs(session, project_id, technical_scope)
    gate_results = evaluate_gates(snapshot, preflight, build, evidence, approvals=[])
    results = {g["gate_id"]: g["result"] for g in gate_results}
    status, detail = policy.derive_readiness(results, approval_present=False)

    record = PublicationAssessment(
        id=assessment_id, project_id=project_id, book_id=book_id or f"book-{project_id}",
        book_root=book_root, policy_version=policy_version,
        technical_scope=technical_scope,
        manuscript_fingerprint=snapshot["manuscript_fingerprint"],
        input_manifest_fingerprint=preflight.get("input_manifest_fingerprint", ""),
        chapter_count=snapshot["chapter_count"],
        assessment_status=status, freshness="CURRENT",
        readiness_detail=detail, preflight_id=None)
    session.add(record)
    session.flush()
    preflight_row = PublicationPreflight(
        id=f"pubpre:{uuid.uuid4().hex[:12]}", assessment_id=assessment_id,
        project_id=project_id, schema_id=PREFLIGHT_SCHEMA,
        schema_version=preflight.get("schema_version", ""),
        book_root=book_root, scope="book",
        manuscript_fingerprint=preflight.get("manuscript_fingerprint", ""),
        input_manifest_fingerprint=preflight.get("input_manifest_fingerprint", ""),
        chapters_found=preflight.get("chapters_found", 0),
        findings_count=preflight.get("findings_count", 0),
        report_bytes=preflight.get("report_bytes", 0),
        report_path=preflight.get("report_path", ""),
        snapshot_consistent=bool(preflight.get("snapshot_consistent", False)),
        status=preflight.get("status", "NOT_RUN"),
        error=preflight.get("error", ""))
    session.add(preflight_row)
    session.flush()
    record.preflight_id = preflight_row.id
    session.flush()
    _persist_gates_issues(session, assessment_id, gate_results)
    write_dossier(settings, session, record, snapshot, preflight, build, evidence)
    session.flush()
    return record


def refresh_freshness(session: Session, settings, assessment_id: str) -> PublicationAssessment:
    """Recompute the snapshot; mark the assessment (and approvals) STALE on change."""
    record = get_assessment(session, assessment_id)
    try:
        snapshot = build_snapshot(record.book_root)
    except ValidationProblem as exc:
        record.freshness = "STALE"
        record.readiness_detail = f"source unavailable: {exc}"
        session.flush()
        return record
    preflight = session.get(PublicationPreflight, record.preflight_id) if record.preflight_id else None
    current_input = preflight.input_manifest_fingerprint if preflight else ""
    if (snapshot["manuscript_fingerprint"] != record.manuscript_fingerprint
            or (current_input and current_input != record.input_manifest_fingerprint)):
        record.freshness = "STALE"
        record.readiness_detail = ("source or evidence changed since assessment; "
                                   "gate results no longer current")
        for approval in session.scalars(
                select(PublicationApproval)
                .where(PublicationApproval.assessment_id == record.id)):
            approval.freshness = "STALE"
    else:
        record.freshness = "CURRENT"
    session.flush()
    return record


def approve(session: Session, payload: PublicationApprovalCreate) -> PublicationApproval:
    if payload.decision not in APPROVAL_DECISIONS:
        raise ValidationProblem(
            f"decision must be one of {', '.join(APPROVAL_DECISIONS)}; got {payload.decision!r}")
    record = get_assessment(session, payload.assessment_id)
    if record.freshness == "STALE":
        raise ValidationProblem("assessment is stale; refresh against the current source first")
    if payload.decision == "APPROVE_RELEASE_CANDIDATE" and record.assessment_status == "BLOCKED":
        raise ValidationProblem("a blocked release candidate cannot be approved; resolve blockers first")
    accepted = list(payload.accepted_limitation_ids or [])
    if accepted:
        known = {i.id for i in session.scalars(
            select(PublicationIssue).where(PublicationIssue.assessment_id == record.id))}
        unknown = [i for i in accepted if i not in known]
        if unknown:
            raise ValidationProblem(f"unknown issue ids: {', '.join(unknown)}")
    approval = PublicationApproval(
        id=f"pubappr:{uuid.uuid4().hex[:12]}", assessment_id=record.id,
        project_id=record.project_id, decision=payload.decision,
        rationale=payload.rationale,
        manuscript_fingerprint=record.manuscript_fingerprint,
        input_manifest_fingerprint=record.input_manifest_fingerprint,
        policy_version=record.policy_version,
        accepted_limitation_ids=accepted,
        freshness="CURRENT", reviewer=payload.reviewer)
    session.add(approval)
    session.flush()
    if payload.decision == "APPROVE_RELEASE_CANDIDATE":
        for issue_id in accepted:
            issue = session.get(PublicationIssue, issue_id)
            if issue is not None and issue.waiver_eligibility == "waivable":
                issue.author_review_status = "accepted_limitation"
                issue.status = "WAIVED"
        session.flush()
    # Re-derive readiness: approval is a separate recorded action that can
    # move NOT_YET_ASSESSED to READY / READY_WITH_ACCEPTED_LIMITATIONS.
    # Waivable FAILs covered by accepted limitations count as WARNING.
    gates = session.scalars(
        select(PublicationGateResult)
        .where(PublicationGateResult.assessment_id == record.id)).all()
    waived_gates = {i.gate_id for i in session.scalars(
        select(PublicationIssue).where(
            PublicationIssue.assessment_id == record.id,
            PublicationIssue.author_review_status == "accepted_limitation"))}
    results = {g.gate_id: (policy.WARNING if g.result == policy.FAIL and g.gate_id in waived_gates
                           else g.result) for g in gates}
    approvals = session.scalars(
        select(PublicationApproval)
        .where(PublicationApproval.assessment_id == record.id)).all()
    fresh_approval = any(a.decision == "APPROVE_RELEASE_CANDIDATE" and a.freshness == "CURRENT"
                         for a in approvals)
    status, detail = policy.derive_readiness(results, approval_present=fresh_approval)
    record.assessment_status = status
    record.readiness_detail = detail
    session.flush()
    return approval


def review_issue(session: Session, issue_id: str, *, decision: str,
                 rationale: str = "", reviewer: str = "") -> PublicationIssue:
    if decision not in ISSUE_DECISIONS:
        raise ValidationProblem(
            f"decision must be one of {', '.join(ISSUE_DECISIONS)}; got {decision!r}")
    issue = session.get(PublicationIssue, issue_id)
    if issue is None:
        raise NotFound("Release issue does not exist")
    if decision == "ACCEPT LIMITATION":
        if issue.waiver_eligibility != "waivable":
            raise ValidationProblem("this issue is nonwaivable and cannot be accepted as a limitation")
        issue.author_review_status = "accepted_limitation"
        issue.status = "WAIVED"
    elif decision == "ACCEPT FINDING":
        issue.author_review_status = "accepted"
    elif decision == "REJECT FINDING":
        issue.author_review_status = "rejected"
        issue.status = "DISMISSED"
    elif decision == "DEFER":
        issue.author_review_status = "deferred"
    elif decision == "REQUEST RECHECK":
        issue.author_review_status = "recheck_requested"
        issue.status = "OPEN"
    if rationale:
        issue.rationale = (issue.rationale + f" | author({reviewer or 'author'}): {rationale}").strip(" |")
    session.flush()
    return issue


def record_calibration(session: Session, payload: PublicationCalibrationCreate) -> PublicationCalibrationReview:
    from mission_control.models import TechnicalEvidenceRequirement
    if session.get(TechnicalEvidenceRequirement, payload.requirement_id) is None:
        raise NotFound("Requirement does not exist")
    if payload.requirement_applicable not in ("APPLICABLE", "NOT_APPLICABLE", "UNDETERMINED"):
        raise ValidationProblem("requirement_applicable must be APPLICABLE, NOT_APPLICABLE or UNDETERMINED")
    record = PublicationCalibrationReview(
        id=f"pubcal:{uuid.uuid4().hex[:12]}",
        requirement_id=payload.requirement_id,
        sample_version=payload.sample_version,
        sample_reason=payload.sample_reason,
        claim_accurate=bool(payload.claim_accurate),
        requirement_applicable=payload.requirement_applicable,
        necessary=bool(payload.necessary),
        strictness_ok=bool(payload.strictness_ok),
        satisfied_by_evidence=payload.satisfied_by_evidence,
        gap_justified=bool(payload.gap_justified),
        priority_proportionate=bool(payload.priority_proportionate),
        would_block=bool(payload.would_block),
        qualification_sufficient=bool(payload.qualification_sufficient),
        duplicate_of=payload.duplicate_of,
        verdict=payload.verdict,
        correction=payload.correction,
        reviewer=payload.reviewer)
    session.add(record)
    session.flush()
    return record


def calibration_summary(session: Session) -> dict:
    rows = session.scalars(select(PublicationCalibrationReview)).all()
    total = len(rows)
    applicable = sum(1 for r in rows if r.requirement_applicable == "APPLICABLE")
    false_positive = sum(1 for r in rows if r.requirement_applicable == "NOT_APPLICABLE")
    gap_ok = sum(1 for r in rows if r.gap_justified)
    priority_ok = sum(1 for r in rows if r.priority_proportionate)
    would_block = sum(1 for r in rows if r.would_block)
    corrections = [r.correction for r in rows if r.correction]
    return {
        "sample_version": CALIBRATION_SAMPLE_VERSION,
        "reviewed": total,
        "applicable": applicable,
        "false_positive_obligations": false_positive,
        "gap_justified": gap_ok,
        "priority_proportionate": priority_ok,
        "would_block": would_block,
        "corrections": corrections,
        "advisory_only": True,
        "note": ("Unconfirmed requirement priorities are advisory only and can never "
                 "block publication until calibration certifies them."),
    }


def write_dossier(settings, session: Session, record: PublicationAssessment,
                  snapshot: dict, preflight: dict, build: dict, evidence: dict) -> Path:
    """Durable release dossier: manifest, policy, gates, preflight reference,
    quality evidence, issues, author decisions and a readable report."""
    out_dir = dossier_dir(settings.data_dir, record.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    read = to_read(session, record)
    (out_dir / "publication-manifest.json").write_text(json.dumps({
        "assessment_id": record.id, "book_id": record.book_id,
        "book_root": record.book_root, "chapter_count": record.chapter_count,
        "manuscript_fingerprint": record.manuscript_fingerprint,
        "input_manifest_fingerprint": record.input_manifest_fingerprint,
        "policy_version": record.policy_version,
        "technical_scope": record.technical_scope,
        "assessment_status": record.assessment_status,
        "freshness": record.freshness,
        "created_at": record.created_at,
        "chapters": snapshot.get("chapters", []),
    }, indent=2), encoding="utf-8")
    (out_dir / "release-policy.json").write_text(json.dumps({
        "policy_version": policy.POLICY_VERSION, "policy_kind": policy.POLICY_KIND,
        "gates": policy.GATES}, indent=2), encoding="utf-8")
    (out_dir / "gate-results.json").write_text(json.dumps(read["gates"], indent=2), encoding="utf-8")
    (out_dir / "preflight-reference.json").write_text(json.dumps({
        "preflight_id": record.preflight_id,
        "schema": preflight.get("schema_id", PREFLIGHT_SCHEMA),
        "manuscript_fingerprint": preflight.get("manuscript_fingerprint", ""),
        "input_manifest_fingerprint": preflight.get("input_manifest_fingerprint", ""),
        "chapters_found": preflight.get("chapters_found", 0),
        "findings_count": preflight.get("findings_count", 0),
        "report_bytes": preflight.get("report_bytes", 0),
        "report_path": preflight.get("report_path", ""),
        "snapshot_consistent": preflight.get("snapshot_consistent", False),
        "status": preflight.get("status", "NOT_RUN"),
        "error": preflight.get("error", ""),
        "output_bound_bytes": PREFLIGHT_OUTPUT_BOUND,
    }, indent=2), encoding="utf-8")
    (out_dir / "build-record.json").write_text(json.dumps({
        "status": build.get("status", "NOT_RUN"),
        "hugo_version": build.get("hugo_version", "unknown"),
        "exit_code": build.get("exit_code"),
        "destination": build.get("destination", ""),
        "output_tail": build.get("output", ""),
        "error": build.get("error", ""),
    }, indent=2), encoding="utf-8")
    (out_dir / "quality-evidence.json").write_text(json.dumps({
        "prose": evidence.get("prose", {}),
        "discovered_chapters": evidence.get("discovered", []),
        "technical_overview": evidence.get("overview", {}),
        "technical_chapters": evidence.get("chapters", {}),
        "completeness": evidence.get("completeness", {}),
        "calibration": evidence.get("calibration", []),
    }, indent=2), encoding="utf-8")
    (out_dir / "release-issues.json").write_text(json.dumps(read["issues"], indent=2), encoding="utf-8")
    (out_dir / "author-decisions.json").write_text(json.dumps({
        "approvals": read["approvals"],
        "note": "Approval is not deployment. Approvals bind to one exact snapshot and policy version.",
    }, indent=2), encoding="utf-8")
    lines = [f"# Publication readiness — {record.book_id or record.project_id}", "",
             f"Assessment: `{record.id}`  ", f"Policy: `{record.policy_version}`  ",
             f"Snapshot: `{record.manuscript_fingerprint[:16]}...`  ",
             f"Status: **{record.assessment_status}** ({record.freshness})  ",
             f"Detail: {record.readiness_detail}", "", "## Gates", ""]
    for gate in read["gates"]:
        lines.append(f"- **{gate['gate_id']}** `{gate['result']}`"
                     f"{' (blocking)' if gate['blocking'] else ''}"
                     f"{' (waivable)' if gate['waivable'] else ''}: {gate['detail']}")
    lines += ["", "## Issues", ""]
    for issue in read["issues"]:
        lines.append(f"- **{issue['issue_type']}** `{issue['severity']}/{issue['status']}` "
                     f"[{issue['gate_id']}] waiver={issue['waiver_eligibility']} "
                     f"review={issue['author_review_status']}: {issue['rationale'][:200]}")
    lines += ["", "## Approval", ""]
    if read["approvals"]:
        for approval in read["approvals"]:
            lines.append(f"- {approval['decision']} by {approval['reviewer'] or 'author'} "
                         f"({approval['freshness']}): {approval['rationale'][:200]}")
    else:
        lines.append("- No author approval recorded. A verified but unapproved candidate is not authorized.")
    lines += ["", "## Reproduction", "",
              f"- Snapshot manifest: `publication-manifest.json`",
              f"- Policy: `release-policy.json` ({policy.POLICY_VERSION})",
              f"- Preflight report: `preflight-report.json` (identity-bound, never truncated)",
              "- Rerun: same source snapshot + same evidence snapshots reproduce these gates; "
              "a changed chapter, asset or evidence record invalidates dependents."]
    (out_dir / "publication-readiness.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_dir


def dossier_zip(settings, assessment_id: str) -> tuple[str, bytes]:
    out_dir = dossier_dir(settings.data_dir, assessment_id)
    if not out_dir.is_dir():
        raise NotFound("Dossier does not exist for this assessment")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(out_dir.iterdir()):
            if path.is_file():
                handle.write(path, arcname=path.name)
    return f"{assessment_id}-dossier.zip", buffer.getvalue()
