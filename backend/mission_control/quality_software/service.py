"""Software quality evaluation engine (MC-PROJECTS-QUALITY-02).

Reuses the approved AI execution layer (resolve_model/complete_chat) and the
established async review pattern (queued/running/completed/failed + active
guards). Never invents scores: missing evidence stays explicitly missing and
overall scores publish only under the rubric aggregation policy.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.core.errors import NotFound, ValidationProblem
from mission_control.models import (
    Project,
    ProjectRepository,
    Repository,
    SoftwareCharter,
    SoftwareEvaluation,
    SoftwareEvalReview,
    SoftwareFinding,
    SoftwareFindingReview,
    SoftwarePrompt,
)
from mission_control.persistence.db import Database, now_iso
from mission_control.quality_software import rubric as _rubric

logger = logging.getLogger(__name__)

EVAL_ID_PREFIX = "sqeval"
REVIEW_ID_PREFIX = "sqrev"
FINDING_ID_PREFIX = "sqfind"
PROMPT_ID_PREFIX = "sqprompt"

EVAL_SYSTEM = (
    "You are a rigorous software quality evaluator. Fitness for purpose outranks "
    "code appearance: a beautifully structured application that does not solve "
    "its intended problem must not score highly. Never invoke tools, list files, "
    "or inspect any workspace: the evidence provided inline is complete. Output "
    "ONLY one JSON object matching the contract. No thinking trace, no markdown "
    "fences, no tool calls, no commentary before or after. Score only cited "
    "evidence from the manifest (evidence_refs must be manifest evidence ids). "
    "Abstain on any dimension the evidence cannot support; use state \"na\" only "
    "when the dimension genuinely does not apply, with a reason. Never claim "
    "tests were executed unless the manifest carries execution evidence. Identify "
    "both strengths and weaknesses."
)

CLOSER = (
    "END OF EVIDENCE. Do not use tools. Do not list files or inspect any "
    "workspace; the evidence above is complete. Output ONLY the single JSON "
    "object described in the contract, with no other text before or after it."
)

REVIEW_SYSTEM = (
    "You are an independent second reviewer of a software quality evaluation. "
    "Judge the ORIGINAL EVIDENCE, not the first evaluator's conclusions. Never "
    "invoke tools, list files, or inspect any workspace. Output ONLY one JSON "
    "object matching the contract. No thinking trace, no markdown fences, no "
    "tool calls, no commentary. Agree only where the evidence supports the claim; "
    "disagree where evidence is thin."
)


def _new_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:12]}"


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8", errors="replace")).hexdigest()[:16]


def _prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:24]


def _extract_json(content: str) -> Any:
    text = (content or "").strip()
    if not text:
        raise _rubric.RubricProblem("empty model output")
    try:
        return json.loads(text)
    except ValueError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except ValueError:
            pass
    raise _rubric.RubricProblem("model output is not valid JSON")


# ------------------------------------------------------------------ charters


def current_charter(session: Session, project_id: str) -> dict[str, Any] | None:
    row = session.scalar(
        select(SoftwareCharter)
        .where(SoftwareCharter.project_id == project_id)
        .order_by(desc(SoftwareCharter.revision))
    )
    return _charter_read(row) if row else None


def list_charters(session: Session, project_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(SoftwareCharter)
        .where(SoftwareCharter.project_id == project_id)
        .order_by(desc(SoftwareCharter.revision))
    ).all()
    return [_charter_read(row) for row in rows]


def _charter_read(row: SoftwareCharter) -> dict[str, Any]:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "revision": row.revision,
        "status": row.status,
        "purpose": row.purpose,
        "users": row.users,
        "capabilities": list(row.capabilities or []),
        "interfaces": list(row.interfaces or []),
        "acceptance": list(row.acceptance or []),
        "non_goals": list(row.non_goals or []),
        "constraints": list(row.constraints or []),
        "lifecycle": row.lifecycle,
        "dependencies": list(row.dependencies or []),
        "verification_expectations": row.verification_expectations,
        "evidence_refs": list(row.evidence_refs or []),
        "provenance": dict(row.provenance or {}),
        "supersedes": row.supersedes,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def create_charter(session: Session, project_id: str, payload: dict[str, Any], *, created_by: str = "owner") -> SoftwareCharter:
    if session.get(Project, project_id) is None:
        raise NotFound("Project not found")
    revision = int(session.scalar(select(func.max(SoftwareCharter.revision)).where(SoftwareCharter.project_id == project_id)) or 0) + 1
    latest = session.scalar(
        select(SoftwareCharter)
        .where(SoftwareCharter.project_id == project_id)
        .order_by(desc(SoftwareCharter.revision))
    )
    row = SoftwareCharter(
        id=_new_id("sqcharter"),
        project_id=project_id,
        revision=revision,
        status="draft",
        purpose=str(payload.get("purpose") or ""),
        users=str(payload.get("users") or ""),
        capabilities=list(payload.get("capabilities") or [])[:50],
        interfaces=list(payload.get("interfaces") or [])[:50],
        acceptance=list(payload.get("acceptance") or [])[:50],
        non_goals=list(payload.get("non_goals") or [])[:50],
        constraints=list(payload.get("constraints") or [])[:50],
        lifecycle=str(payload.get("lifecycle") or ""),
        dependencies=list(payload.get("dependencies") or [])[:50],
        verification_expectations=str(payload.get("verification_expectations") or ""),
        evidence_refs=list(payload.get("evidence_refs") or [])[:50],
        provenance=dict(payload.get("provenance") or {}),
        supersedes=latest.id if latest else None,
        created_by=created_by,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    session.add(row)
    session.flush()
    return row


def confirm_charter(session: Session, charter_id: str) -> SoftwareCharter:
    row = session.get(SoftwareCharter, charter_id)
    if row is None:
        raise NotFound("Charter not found")
    if row.status == "confirmed":
        return row
    for other in session.scalars(
        select(SoftwareCharter).where(
            SoftwareCharter.project_id == row.project_id,
            SoftwareCharter.status == "confirmed",
        )
    ).all():
        other.status = "archived"
        other.updated_at = now_iso()
    row.status = "confirmed"
    row.updated_at = now_iso()
    record_activity(
        session, event_type="system", title="Project charter confirmed",
        detail=f"{row.project_id} revision {row.revision}",
        project_id=row.project_id, source="mission-control", provenance="user",
    )
    session.flush()
    return row


def propose_charter(session: Session, project_id: str) -> dict[str, Any]:
    """Deterministic draft from observed evidence. Everything is unconfirmed."""
    from mission_control.quality_software.evidence import collect_evidence

    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found")
    try:
        manifest = collect_evidence(session, project_id, inspect_dir=None)
    except ValueError:
        manifest = {}
    readme = str((manifest.get("docs", {}) or {}).get("readme", "") or "")
    entrypoints = manifest.get("entrypoints", []) or []
    manifests = manifest.get("manifests", {}) or {}
    dependencies: list[str] = []
    package = manifests.get("package.json", "")
    if package:
        try:
            data = json.loads(package)
            dependencies.extend(sorted((data.get("dependencies", {}) or {}).keys())[:20])
        except ValueError:
            pass
    inspect_caps = [c.get("name", "") for c in (manifest.get("inspect", {}) or {}).get("capabilities", [])[:10]]
    apps = [a.get("name", "") for a in manifest.get("applications", [])]
    git = manifest.get("git", {}) or {}
    branch = git.get("branch") or "unknown"

    def inferred(value: str, source: str) -> dict[str, str]:
        return {"value": value, "source": source}

    return {
        "project_id": project_id,
        "status": "draft",
        "purpose": inferred(
            readme[:600].split("\n\n")[0][:600] if readme else (project.description or ""),
            "README.md head" if readme else "project record (unconfirmed)",
        ),
        "users": inferred(
            ("; ".join(apps) if apps else "Undeclared — owner must name the users or consuming systems."),
            "application registry" if apps else "inferred: missing",
        ),
        "capabilities": [
            inferred(cmd, "declared entry point") for cmd in entrypoints[:8]
        ] + [inferred(name, "Inspect observation (unverified)") for name in inspect_caps[:5] if name],
        "interfaces": [inferred(cmd, "declared entry point") for cmd in entrypoints[:8]],
        "acceptance": [inferred("Undeclared — owner must state acceptance tests.", "inferred: missing")],
        "non_goals": [],
        "constraints": [inferred("Do not rewrite history or modify remotes.", "policy default")],
        "lifecycle": inferred(f"Active development on branch {branch}.", "git index"),
        "dependencies": [inferred(dep, "dependency manifest") for dep in dependencies[:15]],
        "verification_expectations": inferred(
            "Undeclared — owner must state what evidence counts as done.", "inferred: missing"
        ),
        "note": "Every field above is UNCONFIRMED. Review, correct and confirm before evaluations treat purpose as approved.",
    }


# ---------------------------------------------------------------- evaluations


def _software_only(session: Session, project_id: str) -> Project:
    from mission_control.projects.registration import _book_project_ids  # noqa: SLF001

    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found")
    if project.kind == "book" or project.id in _book_project_ids(session):
        raise ValidationProblem("Book-legacy projects use the manuscript evaluation system")
    return project


def request_evaluation(
    session: Session,
    project_id: str,
    *,
    model: str = "",
    charter_id: str | None = None,
    force: bool = False,
    inspect_dir: Path | str | None = None,
) -> SoftwareEvaluation:
    from mission_control.quality_software.evidence import collect_evidence

    project = _software_only(session, project_id)
    manifest = collect_evidence(session, project_id, inspect_dir=inspect_dir)
    charter = _resolve_charter(session, project_id, charter_id)
    previous = session.scalar(
        select(SoftwareEvaluation)
        .where(SoftwareEvaluation.project_id == project_id)
        .order_by(desc(SoftwareEvaluation.created_at))
    )
    if not force:
        duplicate = session.scalar(
            select(SoftwareEvaluation)
            .where(
                SoftwareEvaluation.project_id == project_id,
                SoftwareEvaluation.evidence_fingerprint == manifest["fingerprint"],
                SoftwareEvaluation.requested_model == (model or "").strip(),
                SoftwareEvaluation.status.in_(["queued", "running"]),
            )
            .order_by(desc(SoftwareEvaluation.created_at))
        )
        if duplicate is not None:
            return duplicate
    row = SoftwareEvaluation(
        id=_new_id(EVAL_ID_PREFIX),
        project_id=project.id,
        charter_id=charter.id if charter else None,
        charter_revision=charter.revision if charter else None,
        repo_uid=str((manifest.get("git", {}) or {}).get("repo_uid") or ""),
        repo_path=str((manifest.get("repositories", [{}])[0] or {}).get("path", "")),
        head_sha=(manifest.get("git", {}) or {}).get("head_sha"),
        evidence_fingerprint=manifest["fingerprint"],
        evidence_manifest=manifest,
        rubric_id=_rubric.RUBRIC_ID,
        rubric_version=_rubric.RUBRIC_VERSION,
        prompt_version=_rubric.PROMPT_VERSION,
        requested_model=(model or "").strip() or None,
        status="queued",
        previous_evaluation_id=previous.id if previous else None,
        created_at=now_iso(),
    )
    session.add(row)
    session.flush()
    return row


def build_preview(
    session: Session,
    project_id: str,
    *,
    model: str = "",
    charter_id: str | None = None,
    inspect_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Build the exact execution prompt without creating a row or executing."""
    from mission_control.research.inference import resolve_model
    from mission_control.quality_software.evidence import collect_evidence

    _software_only(session, project_id)
    manifest = collect_evidence(session, project_id, inspect_dir=inspect_dir)
    charter = _resolve_charter(session, project_id, charter_id)
    calls = _build_dimension_prompts(dict(manifest), charter)
    resolved_model, route = resolve_model(session, (model or "").strip())
    all_ids: set[str] = set()
    for call in calls:
        all_ids.update(call["evidence_ids"])
    first = calls[0]
    return {
        "prompt": EVAL_SYSTEM + "\n\n" + first["prompt"],
        "prompt_hash": first["prompt_hash"],
        "prompt_chars": sum(len(call["prompt"]) for call in calls),
        "model": resolved_model,
        "route": route,
        "evidence_id_count": len(all_ids),
        "evidence_fingerprint": manifest.get("fingerprint", ""),
        "charter": {"id": charter.id, "revision": charter.revision, "status": charter.status} if charter else None,
        "rubric": {"id": _rubric.RUBRIC_ID, "version": _rubric.RUBRIC_VERSION},
        "calls_planned": len(calls),
        "calls": [
            {"dimension": call["dimension"], "prompt_chars": len(call["prompt"]), "prompt_hash": call["prompt_hash"]}
            for call in calls
        ],
    }


def _resolve_charter(
    session: Session, project_id: str, charter_id: str | None
) -> SoftwareCharter | None:
    if charter_id:
        charter = session.get(SoftwareCharter, charter_id)
        if charter is None or charter.project_id != project_id:
            raise ValidationProblem("Charter does not belong to this project")
        return charter
    latest = current_charter(session, project_id)
    if latest:
        return session.get(SoftwareCharter, latest["id"])
    return None


def _single_dimension_contract(dim_id: str, weight: int, label: str) -> str:
    return (
        "Respond with EXACTLY ONE JSON object: {\"state\": \"assessed|abstained|na\", "
        f"\"score\": number|null (0..{weight}), \"confidence\": 0..1, "
        "\"rationale\": string (concise, <= 60 words), \"positives\": [], "
        "\"findings\": [{\"severity\": \"critical|high|medium|low\", \"component\": string, "
        "\"title\": string, \"expected\": string, \"observed\": string, \"impact\": string, "
        "\"proposal\": string, \"verification\": string, \"evidence_refs\": [manifest ids]}], "
        "\"assumptions\": [], \"unknowns\": [], \"na_reason\": string, "
        "\"evidence_refs\": [manifest ids from the evidence index only]}. "
        f"You are scoring ONLY the \"{dim_id}\" dimension ({label}, max {weight}). "
        "Every assessed dimension needs evidence_refs from the evidence index. "
        "Abstain rather than guess. Never claim tests were executed without execution evidence."
    )


def _build_dimension_prompts(
    manifest_full: dict[str, Any], charter: SoftwareCharter | None
) -> list[dict[str, Any]]:
    """One bounded prompt per rubric dimension (Windows argv-safe).

    The full manifest stays persisted for audit and freshness. Validation
    enforces references against exactly the ids each call received.
    """
    from mission_control.quality_software.evidence import (
        build_compact_evidence,
        fit_package,
        slice_for_dimension,
    )

    compact = build_compact_evidence(manifest_full or {})
    charter_text = ""
    if charter is not None:
        charter_text = json.dumps(_charter_read(charter), indent=1)[:1500]
    calls: list[dict[str, Any]] = []
    for dim in _rubric.DIMENSIONS:
        sliced = slice_for_dimension(compact, dim["id"])
        package = {
            "contract": "software-eval-v1",
            "dimension": {"id": dim["id"], "label": dim["label"], "weight": dim["weight"]},
            "required": _single_dimension_contract(dim["id"], dim["weight"], dim["label"]),
            "charter": charter_text or "(no charter recorded: treat purpose alignment as provisional)",
            "charter_status": charter.status if charter else "missing",
            "evidence": sliced,
        }
        fitted = fit_package(package, limit=6000)
        ids = {item.get("id", "") for item in (fitted["evidence"].get("evidence", []) or [])} - {""}
        calls.append({
            "dimension": dim["id"],
            "prompt": json.dumps(fitted),
            "prompt_hash": _prompt_hash(json.dumps(fitted, sort_keys=True)),
            "evidence_ids": sorted(ids),
        })
    return calls


def get_evaluation(session: Session, evaluation_id: str) -> SoftwareEvaluation:
    row = session.get(SoftwareEvaluation, evaluation_id)
    if row is None:
        raise NotFound("Evaluation not found")
    return row


def list_evaluations(session: Session, project_id: str, limit: int = 50) -> list[SoftwareEvaluation]:
    return list(
        session.scalars(
            select(SoftwareEvaluation)
            .where(SoftwareEvaluation.project_id == project_id)
            .order_by(desc(SoftwareEvaluation.created_at))
            .limit(min(max(limit, 1), 200))
        ).all()
    )


def evaluation_freshness(
    session: Session, row: SoftwareEvaluation, inspect_dir: Path | str | None = None
) -> dict[str, Any]:
    """Derived staleness: head drift, charter drift, rubric drift. Read-only."""
    reasons: list[str] = []
    try:
        from mission_control.quality_software.evidence import collect_evidence

        live = collect_evidence(session, row.project_id, inspect_dir=inspect_dir)
        if live.get("fingerprint") != row.evidence_fingerprint:
            reasons.append("project evidence changed since this assessment")
        live_head = ((live.get("git", {}) or {}).get("head_sha") or "")
        if row.head_sha and live_head and live_head != row.head_sha:
            reasons.append("new commits landed since this assessment")
    except Exception:
        reasons.append("live evidence unavailable; freshness unknown")
    charter = current_charter(session, row.project_id)
    if charter and row.charter_revision is not None and charter["revision"] != row.charter_revision:
        reasons.append(f"charter moved to revision {charter['revision']}")
    if row.rubric_id != _rubric.RUBRIC_ID or row.rubric_version != _rubric.RUBRIC_VERSION:
        reasons.append("rubric version changed; scores are not directly comparable")
    return {"fresh": not reasons, "state": "current" if not reasons else "stale", "reasons": reasons}


def compare_evaluations(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Score comparability rules: same rubric version required; NA/head/charter drift flagged."""
    warnings: list[str] = []
    if first["rubric_id"] != second["rubric_id"] or first["rubric_version"] != second["rubric_version"]:
        return {
            "compatible": False,
            "reason": "different rubric versions; scores are not comparable without a normalization policy",
            "warnings": warnings,
            "delta": None,
        }
    na_first = {d for d, e in first["dimensions"].items() if e.get("state") == "na"}
    na_second = {d for d, e in second["dimensions"].items() if e.get("state") == "na"}
    if na_first != na_second:
        warnings.append(f"NA sets differ ({sorted(na_first)} vs {sorted(na_second)}): denominators differ")
    if first.get("head_sha") != second.get("head_sha"):
        warnings.append("different HEAD revisions: delta mixes code change with judgement change")
    if first.get("charter_revision") != second.get("charter_revision"):
        warnings.append("different charter revisions: goal alignment is judged against different goals")
    delta = None
    if first.get("overall") is not None and second.get("overall") is not None and not warnings:
        delta = round(second["overall"] - first["overall"], 1)
    return {"compatible": not warnings, "reason": "" if not warnings else "; ".join(warnings), "warnings": warnings, "delta": delta}


class SoftwareQualityService:
    """Background execution for evaluations and independent reviews."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self._active_evals: set[str] = set()
        self._active_reviews: set[str] = set()

    async def execute_evaluation(self, evaluation_id: str) -> None:
        if evaluation_id in self._active_evals:
            return
        self._active_evals.add(evaluation_id)
        try:
            with self.database.session() as session:
                row = session.get(SoftwareEvaluation, evaluation_id)
                if row is None or row.status != "queued":
                    return
                row.status = "running"
            with self.database.session() as session:
                row = session.get(SoftwareEvaluation, evaluation_id)
                charter = session.get(SoftwareCharter, row.charter_id) if row and row.charter_id else None
                if row is None:
                    return
                charter_obj = charter
                calls = _build_dimension_prompts(dict(row.evidence_manifest or {}), charter_obj)
            from mission_control.research.inference import complete_chat, resolve_model

            dimensions: dict[str, Any] = {}
            call_records: list[dict[str, Any]] = []
            total_chars = sum(len(call["prompt"]) for call in calls)
            with self.database.session() as chat_session:
                requested = (chat_session.get(SoftwareEvaluation, evaluation_id).requested_model or "").strip()
                model, route = resolve_model(chat_session, requested)
                try:
                    for call in calls:
                        result = await complete_chat(
                            chat_session,
                            model=model,
                            messages=[
                                {"role": "system", "content": EVAL_SYSTEM},
                                {"role": "user", "content": call["prompt"]},
                            ],
                            route=route,
                        )
                        content = str(result.get("content", ""))
                        call_records.append({
                            "dimension": call["dimension"],
                            "model": str(result.get("model") or model)[:200],
                            "route": str(result.get("route") or route)[:120],
                            "latency_ms": result.get("latency_ms"),
                            "prompt_chars": len(call["prompt"]),
                            "prompt_hash": call["prompt_hash"],
                        })
                        try:
                            document = _extract_json(content)
                            dimensions[call["dimension"]] = _rubric.validate_dimension(
                                call["dimension"], document, set(call["evidence_ids"])
                            )
                        except _rubric.RubricProblem as exc:
                            raise _rubric.RubricProblem(
                                f"dimension {call['dimension']}: {exc}"
                            ) from exc
                except _rubric.RubricProblem as exc:
                    self._finish_failed(evaluation_id, f"contract violation: {exc}")
                    return
                except Exception as exc:
                    if "CapabilityUnavailable" in type(exc).__name__ or "disabled" in str(exc).lower():
                        self._finish_blocked(evaluation_id, f"{type(exc).__name__}: {exc}")
                    else:
                        self._finish_failed(evaluation_id, f"{type(exc).__name__}: {exc}")
                    return
            try:
                stats = _rubric.aggregate(dimensions)
            except _rubric.RubricProblem as exc:  # pragma: no cover - aggregate is total
                self._finish_failed(evaluation_id, f"contract violation: {exc}")
                return
            positives: list[str] = []
            for entry in dimensions.values():
                positives.extend(entry.get("positives", [])[:2])
            with self.database.session() as session:
                row = session.get(SoftwareEvaluation, evaluation_id)
                if row is None:
                    return
                row.status = "completed" if stats["valid"] else "partial"
                row.observed_model = str(result.get("model") or model)[:200]
                row.model_route = str(result.get("route") or route)[:120]
                row.overall = stats["overall"]
                row.max_attainable = stats["max_attainable"]
                row.coverage_percent = stats["coverage_percent"]
                row.dimensions = dimensions
                row.uncertainty = ""
                row.limitations = []
                row.execution = {
                    "transport": "model",
                    "calls": call_records,
                    "prompt_chars": total_chars,
                    "prompt_hash": _prompt_hash("".join(c["prompt"] for c in calls)),
                    "strengths": positives[:10],
                }
                row.prompt_hash = _prompt_hash("".join(c["prompt"] for c in calls))
                row.completed_at = now_iso()
            with self.database.session() as session:
                self._extract_findings(session, evaluation_id)
        except Exception as exc:  # defensive: failures are recorded, never silent
            logger.exception("Software evaluation %s failed", evaluation_id)
            self._finish_failed(evaluation_id, f"{type(exc).__name__}: {exc}")
        finally:
            self._active_evals.discard(evaluation_id)

    def _finish_failed(self, evaluation_id: str, error: str) -> None:
        with self.database.session() as session:
            row = session.get(SoftwareEvaluation, evaluation_id)
            if row is not None and row.status in {"queued", "running"}:
                row.status = "failed"
                row.error = error[:2000]
                row.completed_at = now_iso()

    def _finish_blocked(self, evaluation_id: str, error: str) -> None:
        with self.database.session() as session:
            row = session.get(SoftwareEvaluation, evaluation_id)
            if row is not None and row.status in {"queued", "running"}:
                row.status = "blocked"
                row.error = error[:2000]
                row.completed_at = now_iso()

    def _extract_findings(self, session: Session, evaluation_id: str) -> list[SoftwareFinding]:
        row = session.get(SoftwareEvaluation, evaluation_id)
        if row is None:
            return []
        created: list[SoftwareFinding] = []
        for dim_id, entry in (row.dimensions or {}).items():
            for finding in entry.get("findings", []) or []:
                fingerprint = _fingerprint(
                    row.project_id,
                    str(finding.get("component", "")).strip().casefold(),
                    str(finding.get("title", "")).strip().casefold(),
                )
                existing = session.scalar(
                    select(SoftwareFinding).where(
                        SoftwareFinding.project_id == row.project_id,
                        SoftwareFinding.fingerprint == fingerprint,
                    )
                )
                if existing is None:
                    existing = SoftwareFinding(
                        id=_new_id(FINDING_ID_PREFIX),
                        project_id=row.project_id,
                        fingerprint=fingerprint,
                        severity=finding.get("severity", "medium"),
                        component=finding.get("component", ""),
                        title=finding.get("title", ""),
                        expected=finding.get("expected", ""),
                        observed=finding.get("observed", ""),
                        impact=finding.get("impact", ""),
                        proposal=finding.get("proposal", ""),
                        verification_required=finding.get("verification", ""),
                        evidence_refs=list(finding.get("evidence_refs", [])),
                        source_evaluations=[evaluation_id],
                        status="proposed",
                        history=[{"at": now_iso(), "event": "extracted", "evaluation_id": evaluation_id, "dimension": dim_id}],
                        created_at=now_iso(),
                        updated_at=now_iso(),
                    )
                    session.add(existing)
                    created.append(existing)
                else:
                    sources = list(existing.source_evaluations or [])
                    if evaluation_id not in sources:
                        sources.append(evaluation_id)
                        existing.source_evaluations = sources
                    history = list(existing.history or [])
                    history.append({"at": now_iso(), "event": "re-observed", "evaluation_id": evaluation_id, "dimension": dim_id})
                    existing.history = history
                    existing.updated_at = now_iso()
        session.flush()
        return created

    # ------------------------------------------------ independent reviews

    def request_eval_review(self, session: Session, evaluation_id: str, model: str = "") -> SoftwareEvalReview:
        row = get_evaluation(session, evaluation_id)
        if row.status not in {"completed", "partial"}:
            raise ValidationProblem("Independent review requires a finished evaluation")
        duplicate = session.scalar(
            select(SoftwareEvalReview)
            .where(
                SoftwareEvalReview.evaluation_id == evaluation_id,
                SoftwareEvalReview.reviewer_model == (model or "").strip(),
                SoftwareEvalReview.status.in_(["queued", "running"]),
            )
            .order_by(desc(SoftwareEvalReview.created_at))
        )
        if duplicate is not None:
            return duplicate
        review = SoftwareEvalReview(
            id=_new_id(REVIEW_ID_PREFIX),
            evaluation_id=evaluation_id,
            reviewer_model=(model or "").strip(),
            status="queued",
            created_at=now_iso(),
        )
        session.add(review)
        session.flush()
        return review

    async def execute_eval_review(self, review_id: str) -> None:
        if review_id in self._active_reviews:
            return
        self._active_reviews.add(review_id)
        try:
            with self.database.session() as session:
                review = session.get(SoftwareEvalReview, review_id)
                if review is None or review.status != "queued":
                    return
                review.status = "running"
                evaluation_id = review.evaluation_id
            with self.database.session() as session:
                row = session.get(SoftwareEvaluation, evaluation_id)
                finding_ids = {f.id for f in self._linked_findings(evaluation_id)}
                review_calls = self._build_review_calls(session, row) if row else []
            from mission_control.research.inference import complete_chat, resolve_model

            with self.database.session() as chat_session:
                requested = (chat_session.get(SoftwareEvalReview, review_id).reviewer_model or "").strip()
                if requested and row is not None and requested == (row.observed_model or row.requested_model or ""):
                    raise ValidationProblem("Independent review requires a different model from the evaluation")
                model, route = resolve_model(chat_session, requested)
                merged_verdicts: list[str] = []
                merged_findings: list[dict[str, Any]] = []
                rationales: list[str] = []
                try:
                    for call in review_calls:
                        result = await complete_chat(
                            chat_session,
                            model=model,
                            messages=[
                                {"role": "system", "content": REVIEW_SYSTEM},
                                {"role": "user", "content": call["prompt"]},
                            ],
                            route=route,
                        )
                        content = str(result.get("content", ""))
                        document = _extract_json(content)
                        verdict = str(document.get("verdict", "")).strip().lower()
                        if verdict not in _rubric.REVIEW_VERDICTS:
                            raise _rubric.RubricProblem(f"unknown review verdict {verdict!r}")
                        merged_verdicts.append(verdict)
                        rationales.append(str(document.get("rationale", ""))[:1000])
                        for item in document.get("finding_verdicts", []) or []:
                            ref = str((item or {}).get("finding_id", ""))
                            vote = str((item or {}).get("verdict", "")).strip().lower()
                            if ref not in finding_ids:
                                raise _rubric.RubricProblem(f"review references unknown finding {ref!r}")
                            if vote not in _rubric.REVIEW_VERDICTS:
                                raise _rubric.RubricProblem(f"unknown finding verdict {vote!r}")
                            merged_findings.append({
                                "finding_id": ref,
                                "verdict": vote,
                                "rationale": str((item or {}).get("rationale", ""))[:500],
                            })
                except _rubric.RubricProblem as exc:
                    self._finish_review(review_id, "failed", {}, f"contract violation: {exc}")
                    return
                except Exception as exc:
                    self._finish_review(review_id, "failed" if "Capability" not in type(exc).__name__ else "blocked", {}, str(exc))
                    return
            if not merged_verdicts:
                self._finish_review(review_id, "failed", {}, "model returned no review verdicts")
                return
            if all(vote == "agree" for vote in merged_verdicts):
                overall = "agree"
            elif all(vote == "disagree" for vote in merged_verdicts):
                overall = "disagree"
            else:
                overall = "partial"
            self._finish_review(
                review_id, "completed",
                {
                    "verdict": overall,
                    "rationale": " | ".join(r for r in rationales if r)[:4000],
                    "finding_verdicts": merged_findings,
                    "model": model,
                    "route": route,
                    "usage": {},
                },
                "",
            )
        except ValidationProblem as exc:
            self._finish_review(review_id, "failed", {}, str(exc))
        except Exception as exc:  # defensive
            logger.exception("Software eval review %s failed", review_id)
            self._finish_review(review_id, "failed", {}, f"{type(exc).__name__}: {exc}")
        finally:
            self._active_reviews.discard(review_id)

    def _build_review_calls(
        self, session: Session, row: SoftwareEvaluation
    ) -> list[dict[str, Any]]:
        """One bounded prompt per finding chunk (Windows argv-safe)."""
        from mission_control.quality_software.evidence import build_compact_evidence, fit_package

        findings = session.scalars(
            select(SoftwareFinding).where(SoftwareFinding.project_id == row.project_id)
            .order_by(SoftwareFinding.severity, SoftwareFinding.title)
        ).all()
        linked = [f for f in findings if row.id in (f.source_evaluations or [])]
        compact = build_compact_evidence(
            dict(row.evidence_manifest or {}), max_files=0, readme_chars=1500,
            max_caps=15, max_opps=10,
        )
        dims = row.dimensions or {}
        dim_summary = {
            dim_id: {
                "state": (entry or {}).get("state"),
                "score": (entry or {}).get("score"),
                "rationale": str((entry or {}).get("rationale", ""))[:200],
            }
            for dim_id, entry in dims.items()
        }
        calls: list[dict[str, Any]] = []
        for index in range(0, max(len(linked), 1), 6):
            chunk = linked[index : index + 6]
            package = {
                "contract": "software-review-v1",
                "instruction": (
                    "Return EXACTLY ONE JSON object: {\"verdict\": \"agree|disagree|partial\", "
                    "\"rationale\": string (concise), \"finding_verdicts\": [{\"finding_id\": id-from-findings, "
                    "\"verdict\": \"agree|disagree|partial\", \"rationale\": string}]}. "
                    "Judge the evidence, not the first evaluator. Disagree where evidence is thin."
                ),
                "evidence": compact,
                "evaluation": {
                    "overall": row.overall,
                    "dimensions": dim_summary,
                    "uncertainty": str(row.uncertainty or "")[:500],
                },
                "findings": [
                    {
                        "finding_id": f.id,
                        "severity": f.severity,
                        "component": (f.component or "")[:150],
                        "title": f.title,
                        "expected": (f.expected or "")[:300],
                        "observed": (f.observed or "")[:300],
                        "evidence_refs": list(f.evidence_refs or [])[:8],
                    }
                    for f in chunk
                ],
            }
            fitted = fit_package(package, limit=6000)
            calls.append({
                "prompt": json.dumps(fitted),
                "finding_ids": [f.id for f in chunk],
            })
        return calls

    def _linked_findings(self, evaluation_id: str) -> list[SoftwareFinding]:
        with self.database.session() as session:
            row = session.get(SoftwareEvaluation, evaluation_id)
            if row is None:
                return []
            return list(
                session.scalars(
                    select(SoftwareFinding).where(SoftwareFinding.project_id == row.project_id)
                ).all()
            )

    def _finish_review(self, review_id: str, status: str, result: dict[str, Any], error: str) -> None:
        with self.database.session() as session:
            review = session.get(SoftwareEvalReview, review_id)
            if review is None or review.status not in {"queued", "running"}:
                return
            review.status = status
            review.error = (error[:2000] if error else None)
            if result:
                review.verdict = result.get("verdict", "")
                review.rationale = result.get("rationale", "")
                review.finding_verdicts = result.get("finding_verdicts", [])
                review.reviewer_model = result.get("model", review.reviewer_model)
                review.model_route = result.get("route", "")
                review.usage_info = result.get("usage", {})
            review.completed_at = now_iso()


def _strings(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _rubric.RubricProblem(f"{field} must be a string list")
    return [item[:1000] for item in value][:20]


# ------------------------------------------------------------------ findings


def list_findings(
    session: Session, project_id: str, *, status: str | None = None, severity: str | None = None
) -> list[dict[str, Any]]:
    query = select(SoftwareFinding).where(SoftwareFinding.project_id == project_id)
    if status:
        query = query.where(SoftwareFinding.status == status)
    if severity:
        query = query.where(SoftwareFinding.severity == severity)
    rows = session.scalars(query.order_by(SoftwareFinding.severity, SoftwareFinding.updated_at)).all()
    return [_finding_read(session, row) for row in rows]


def _finding_read(session: Session, row: SoftwareFinding) -> dict[str, Any]:
    reviews = session.scalars(
        select(SoftwareFindingReview)
        .where(SoftwareFindingReview.finding_id == row.id)
        .order_by(desc(SoftwareFindingReview.created_at))
        .limit(10)
    ).all()
    return {
        "id": row.id,
        "project_id": row.project_id,
        "fingerprint": row.fingerprint,
        "severity": row.severity,
        "component": row.component,
        "title": row.title,
        "expected": row.expected,
        "observed": row.observed,
        "impact": row.impact,
        "proposal": row.proposal,
        "verification_required": row.verification_required,
        "evidence_refs": list(row.evidence_refs or []),
        "source_evaluations": list(row.source_evaluations or []),
        "status": row.status,
        "verified": finding_verified(session, row),
        "resolution_evidence": list(row.resolution_evidence or []),
        "history": list(row.history or []),
        "reviews": [
            {
                "id": r.id, "decision": r.decision, "reason": r.reason,
                "reviewer": r.reviewer, "source_digest": r.source_digest,
                "created_at": r.created_at,
            }
            for r in reviews
        ],
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def finding_verified(session: Session, row: SoftwareFinding) -> bool:
    """Derived verification: owner acceptance plus independent corroboration
    for high/critical findings. Never a status set by the evaluator."""
    if row.status not in {"accepted", "in_progress", "needs_verification", "resolved"}:
        return False
    accepted = any(r.decision == "ACCEPT" for r in session.scalars(
        select(SoftwareFindingReview).where(SoftwareFindingReview.finding_id == row.id)
    ).all())
    if not accepted:
        return False
    if row.severity in {"high", "critical"}:
        for review in session.scalars(select(SoftwareEvalReview)).all():
            for vote in review.finding_verdicts or []:
                if vote.get("finding_id") == row.id and vote.get("verdict") == "agree":
                    return True
        return False
    return True


def review_finding(
    session: Session, finding_id: str, *, decision: str, reason: str = "", reviewer: str = "owner"
) -> SoftwareFindingReview:
    if decision not in _rubric.FINDING_DECISIONS:
        raise ValidationProblem(f"Unknown decision {decision!r}")
    row = session.get(SoftwareFinding, finding_id)
    if row is None:
        raise NotFound("Finding not found")
    if row.status not in {"proposed", "reopened", "deferred", "investigate", "accepted", "in_progress"}:
        raise ValidationProblem(f"Finding is {row.status}; reopen it before reviewing")
    review = SoftwareFindingReview(
        id=_new_id("sqfrev"),
        finding_id=finding_id,
        decision=decision,
        reason=reason[:2000],
        reviewer=reviewer[:120],
        source_digest=row.source_evaluations[-1] if row.source_evaluations else "",
        created_at=now_iso(),
    )
    session.add(review)
    mapping = {"ACCEPT": "accepted", "REJECT": "rejected", "DEFER": "deferred", "INVESTIGATE": "investigate"}
    row.status = mapping[decision]
    history = list(row.history or [])
    history.append({"at": now_iso(), "event": f"owner_{decision.lower()}", "reason": reason[:500]})
    row.history = history
    row.updated_at = now_iso()
    record_activity(
        session, event_type="system", title=f"Finding {decision.lower()}: {row.title[:120]}",
        detail=reason[:500], project_id=row.project_id, source="mission-control", provenance="user",
    )
    session.flush()
    return review


def start_finding_work(session: Session, finding_id: str) -> SoftwareFinding:
    row = session.get(SoftwareFinding, finding_id)
    if row is None:
        raise NotFound("Finding not found")
    if row.status != "accepted":
        raise ValidationProblem("Only accepted findings can move to in-progress")
    row.status = "in_progress"
    row.updated_at = now_iso()
    session.flush()
    return row


def resolve_finding(session: Session, finding_id: str, resolution_evidence: list[str]) -> SoftwareFinding:
    row = session.get(SoftwareFinding, finding_id)
    if row is None:
        raise NotFound("Finding not found")
    if row.status not in {"accepted", "in_progress", "needs_verification"}:
        raise ValidationProblem("Only active findings can record resolution evidence")
    if not resolution_evidence:
        raise ValidationProblem("Resolution requires evidence references")
    row.resolution_evidence = list(resolution_evidence)[:20]
    row.status = "needs_verification"
    history = list(row.history or [])
    history.append({"at": now_iso(), "event": "resolution_claimed", "evidence": list(resolution_evidence)[:20]})
    row.history = history
    row.updated_at = now_iso()
    session.flush()
    return row


def confirm_resolution(session: Session, finding_id: str, note: str = "") -> SoftwareFinding:
    row = session.get(SoftwareFinding, finding_id)
    if row is None:
        raise NotFound("Finding not found")
    if row.status != "needs_verification" or not row.resolution_evidence:
        raise ValidationProblem("Resolution must be evidenced before it can be confirmed")
    row.status = "resolved"
    history = list(row.history or [])
    history.append({"at": now_iso(), "event": "resolution_confirmed", "note": note[:500]})
    row.history = history
    row.updated_at = now_iso()
    record_activity(
        session, event_type="system", title=f"Finding resolved: {row.title[:120]}",
        detail="; ".join(row.resolution_evidence[:5]), project_id=row.project_id,
        source="mission-control", provenance="user",
    )
    session.flush()
    return row


def reopen_finding(session: Session, finding_id: str, reason: str = "") -> SoftwareFinding:
    row = session.get(SoftwareFinding, finding_id)
    if row is None:
        raise NotFound("Finding not found")
    if row.status not in {"resolved", "rejected", "deferred", "investigate"}:
        raise ValidationProblem("Only closed findings can be reopened")
    row.status = "reopened"
    history = list(row.history or [])
    history.append({"at": now_iso(), "event": "reopened", "reason": reason[:500]})
    row.history = history
    row.updated_at = now_iso()
    session.flush()
    return row


# ------------------------------------------------------------------- prompts


def build_improvement_prompt(
    session: Session, project_id: str, finding_ids: list[str], scope: str = ""
) -> str:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found")
    findings = []
    for finding_id in finding_ids[:15]:
        row = session.get(SoftwareFinding, finding_id)
        if row is None or row.project_id != project_id:
            raise ValidationProblem(f"Finding not in this project: {finding_id}")
        if row.status not in {"accepted", "in_progress", "needs_verification", "reopened"}:
            raise ValidationProblem(f"Finding {finding_id} is {row.status}; accept it before generating a prompt")
        findings.append(row)
    if not findings:
        raise ValidationProblem("Select at least one accepted finding")
    repos = [
        session.get(Repository, link.repository_id)
        for link in session.scalars(
            select(ProjectRepository).where(ProjectRepository.project_id == project_id)
        ).all()
    ]
    repo_lines = [r.path for r in repos if r is not None]
    lines = [
        f"# Implementation request — {project.name} (scope: {scope or 'bounded fix batch'})",
        "",
        "## Project purpose and current state",
        project.description or "Purpose recorded in the project charter.",
        f"Repositories: {', '.join(repo_lines) or 'none linked'}",
        "",
        "## Findings to address (do not fix anything outside this list)",
    ]
    for index, row in enumerate(findings, 1):
        lines.extend([
            f"{index}. [{row.severity}] {row.title} ({row.component or 'unspecified component'})",
            f"   Expected: {row.expected[:400]}",
            f"   Observed: {row.observed[:400]}",
            f"   Impact: {row.impact[:400]}" if row.impact else "",
            f"   Suggested fix: {row.proposal[:400]}" if row.proposal else "",
            f"   Evidence: {', '.join(row.evidence_refs[:8])}",
            f"   Must verify by: {row.verification_required[:400]}" if row.verification_required else "",
        ])
    lines.extend([
        "",
        "## Architectural constraints",
        "- Preserve existing behaviour unless the task requires a change.",
        "- Keep diffs scoped; explain scope changes.",
        "- Never rewrite Git history or modify remotes.",
        "",
        "## Tests and validation required",
        "- Run the repository test command before finishing; report results.",
        "- Re-run applicable checks and cite evidence for each closed finding.",
        "",
        "## Explicit non-goals",
        "- No unrelated refactors, no new features, no dependency upgrades without need.",
        "",
        "## Expected completion report",
        "- Per-finding outcome with file/commit evidence; unresolved items stay open.",
        "- A finding is not resolved because implementation claims success — verification decides.",
    ])
    return "\n".join(line for line in lines if line != "" or True).rstrip() + "\n"


def save_prompt(session: Session, project_id: str, finding_ids: list[str], scope: str, prompt: str, provenance: dict[str, Any]) -> SoftwarePrompt:
    row = SoftwarePrompt(
        id=_new_id(PROMPT_ID_PREFIX),
        project_id=project_id,
        finding_ids=list(finding_ids)[:15],
        scope=(scope or "")[:500],
        prompt=prompt,
        provenance=dict(provenance or {}),
        created_at=now_iso(),
    )
    session.add(row)
    session.flush()
    return row


def list_prompts(session: Session, project_id: str, limit: int = 20) -> list[SoftwarePrompt]:
    return list(
        session.scalars(
            select(SoftwarePrompt)
            .where(SoftwarePrompt.project_id == project_id)
            .order_by(desc(SoftwarePrompt.created_at))
            .limit(min(max(limit, 1), 100))
        ).all()
    )


# ------------------------------------------------------------ cultivation


def report_progress(
    session: Session,
    *,
    project_id: str,
    goal_id: str,
    item_id: str | None = None,
    note: str = "",
    finding_id: str | None = None,
    evaluation_id: str | None = None,
) -> dict[str, Any]:
    """Record verified quality progress as cultivation evidence.

    Appending evidence only. Never sets stages, qualification, releases or
    measurements: those stay owner decisions in the Cultivation system.
    A bare evaluation score is recorded as an unverified observation, never
    as verified progress.
    """
    from mission_control.cultivation.service import add_evidence
    from mission_control.models import CultivationGoal

    if session.get(CultivationGoal, goal_id) is None:
        raise NotFound("Cultivation goal not found")
    verified = False
    reference = ""
    if finding_id:
        row = session.get(SoftwareFinding, finding_id)
        if row is None or row.project_id != project_id:
            raise ValidationProblem("Finding not in this project")
        if row.status != "resolved" or not row.resolution_evidence:
            raise ValidationProblem("Only resolved findings with evidence count as verified progress")
        if row.severity in {"high", "critical"} and not finding_verified(session, row):
            raise ValidationProblem("High/critical findings need independent corroboration first")
        verified = True
        reference = f"software-finding:{finding_id}"
        note = note or f"Resolved: {row.title}"
    elif evaluation_id:
        row = session.get(SoftwareEvaluation, evaluation_id)
        if row is None or row.project_id != project_id:
            raise ValidationProblem("Evaluation not in this project")
        reference = f"software-evaluation:{evaluation_id}"
        note = note or f"Evaluation {evaluation_id} recorded (overall={row.overall}); score alone is not qualification"
    else:
        raise ValidationProblem("Provide finding_id or evaluation_id")
    evidence = add_evidence(
        session, goal_id, item_id=item_id, kind="verification" if verified else "reference",
        reference=reference, note=note[:2000], verified=verified,
    )
    session.flush()
    return {"evidence_id": evidence.id, "verified": verified, "reference": reference}
