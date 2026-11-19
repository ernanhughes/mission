"""Mission-side one-chapter improvement journey.

Mission owns the evidence envelope and review UI. ALIVE owns the source, workspace,
workflow, model session, proposal, evaluation and decision. This module contains no
model call and no manuscript write. It only builds a bounded brief from Mission's
existing quality context and proxies a fixed ALIVE surface.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from mission_control.living_book import service as living_service
from mission_control.living_book.client import LivingBookError, LivingBookUnavailable
from mission_control.living_book.quality import build_quality_context

LivingBookProblem = living_service.LivingBookProblem

SCHEMA = "living-book-improvement-preview.v1"
INTENT_SCHEMA = "living-book-improvement-intent.v1"
RUN_SCHEMA = "living-book-improvement-run.v1"
FOCUSES = {"economy": "economy"}
PROSE_MEASURE = "mission.prose.manuscript-prose-v1"
MAX_BRIEF = 600
MAX_QUOTE = 180
AUTHORITY = {
    "read": "Approved source, exact capture",
    "model": "Separate workspace workflow admission; owner confirms model and budget",
    "action": "Workspace Chapter Improvement, proposal only",
    "write": "None",
}
NOTICE = (
    "A decision records the author's judgement of this exact proposal. It never writes, "
    "applies or overwrites the chapter."
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, limit: int = 600) -> str:
    text = value if isinstance(value, str) else str(value or "")
    text = text.replace("\x00", "").strip()
    return text[:limit]


def _blocker(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail[:600]}


def _source_matches(book: dict[str, Any], workspace: dict[str, Any]) -> bool:
    source = book.get("source") or {}
    binding = source.get("binding_ref")
    approval = source.get("approval_ref")
    capture = source.get("capture_ref")
    for item in workspace.get("sources") or []:
        if item.get("binding_ref") != binding:
            continue
        return bool(
            item.get("approval_ref") == approval and item.get("capture_ref") == capture
        )
    return False


async def _book_detail(client, context: dict[str, Any]) -> dict[str, Any]:
    listed = await living_service._book_for(client, context)
    return await client.book(str(listed["id"]))


def _chapter(book: dict[str, Any], chapter_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in book.get("chapters") or [] if item.get("chapter_id") == chapter_id),
        None,
    )


def _prose_measure(quality: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (item for item in quality.get("measures") or [] if item.get("id") == PROSE_MEASURE),
        None,
    )


def _economy(measure: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict]]:
    blockers: list[dict] = []
    if measure is None:
        return None, [_blocker("quality_not_recorded", "No prose measure is recorded for this chapter.")]
    if str(measure.get("status", "")).upper() != "CURRENT":
        blockers.append(
            _blocker(
                "quality_not_current",
                f"The prose measure is {measure.get('status', 'unknown')}, not CURRENT.",
            )
        )
    # ``chapter_revision`` belongs to Mission's quality system. It is not the ALIVE
    # source-file SHA-256; both are retained as provenance, and ``CURRENT`` is the
    # freshness authority for the quality evidence.
    revision = measure.get("chapter_revision")
    if not revision:
        blockers.append(
            _blocker(
                "quality_revision_missing",
                "The prose measure does not name the revision it evaluated.",
            )
        )
    dimension = ((measure.get("value") or {}).get("dimensions") or {}).get("economy")
    if not isinstance(dimension, dict):
        return None, blockers + [
            _blocker("quality_dimension_missing", "The prose measure has no economy observation.")
        ]
    score = dimension.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        blockers.append(
            _blocker("quality_score_missing", "The economy observation has no numeric score.")
        )
    evidence = {
        "ref": "mission:quality:"
        + ":".join(
            [
                PROSE_MEASURE,
                str(measure.get("chapter_id") or ""),
                str(measure.get("observed_at") or ""),
            ]
        ),
        "kind": "model_judgment",
        "status": measure.get("status"),
        "measure_id": PROSE_MEASURE,
        "rubric": measure.get("rubric"),
        "observed_at": measure.get("observed_at"),
        "chapter_revision": revision,
        "quote": _text(dimension.get("evidence"), MAX_QUOTE),
        "quote_validated": bool(dimension.get("evidence_validated")),
        "value": {"overall": (measure.get("value") or {}).get("overall"), "economy": score},
        "limitations": [_text(item, 300) for item in (measure.get("limitations") or [])[:6]],
    }
    return evidence, blockers


def _excluded(quality: dict[str, Any]) -> list[dict[str, str]]:
    excluded = []
    for measure in quality.get("measures") or []:
        if measure.get("id") == PROSE_MEASURE:
            continue
        status = str(measure.get("status") or "unknown").upper()
        reason = "NOT_RUN is missing evidence, not zero." if status == "NOT_RUN" else status.lower()
        excluded.append(
            {
                "ref": "mission:quality:" + str(measure.get("id") or "measure"),
                "label": _text(measure.get("label"), 160),
                "status": status,
                "reason": reason,
            }
        )
    return excluded


def _brief(chapter: dict[str, Any], measure: dict[str, Any], evidence: dict[str, Any]) -> str:
    title = _text(chapter.get("title") or chapter.get("chapter_id"), 120)
    observed = _text(evidence.get("observed_at"), 10)
    overall = (measure.get("value") or {}).get("overall")
    score = (evidence.get("value") or {}).get("economy")
    quote = _text(evidence.get("quote"), MAX_QUOTE)
    quote_text = f' quoted evidence "{quote}"' if quote else " no quoted evidence"
    text = (
        f'Improve economy in "{title}" without dropping technical claims, source citations '
        f"or uncertainty. Mission prose evidence (CURRENT, observed {observed}): overall "
        f"{overall}; economy {score};{quote_text} "
        f"(evidence_validated={str(bool(evidence.get('quote_validated'))).lower()}; not chapter text). "
        "Preserve the chapter's argument, technical qualifications, examples and references. Keep "
        "each section's full substance and approximate length; do not omit material. Return a "
        "complete proposal; do not write the source."
    )
    if len(text) > MAX_BRIEF:
        raise LivingBookProblem(
            "The selected quality evidence produces a brief longer than 600 characters. "
            "Choose a shorter focus or evidence set.",
            state="brief_too_long",
            status=422,
        )
    return text


def _plan_view(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": plan.get("mode"),
        "workflow_version": plan.get("workflow_version"),
        "workflow_definition_id": plan.get("workflow_definition_id"),
        "workflow_definition_sha256": plan.get("workflow_definition_sha256"),
        "workflow_binding_sha256": plan.get("workflow_binding_sha256"),
        "model_calls": plan.get("model_calls"),
        "output_tokens": plan.get("output_tokens"),
        "wall_seconds": plan.get("wall_seconds"),
        "characters": plan.get("characters"),
        "section_count": len(plan.get("sections") or []),
        "plan_sha256": plan.get("sha256"),
        "governor": plan.get("governor"),
    }


def _experience_view(value: dict[str, Any], requested: bool) -> dict[str, Any]:
    retrieval = value.get("retrieval") or {}
    selected = retrieval.get("selected") or []
    items = value.get("items") or []
    return {
        "requested": requested,
        "eligible_candidates": retrieval.get("eligible_candidates", 0),
        "selected": selected,
        "items": items,
        "abstained": not selected,
        "context_sha256": retrieval.get("context_sha256"),
        "retrieval": retrieval,
    }


def _intent(
    project_id: str,
    book: dict[str, Any],
    chapter: dict[str, Any],
    source: dict[str, Any],
    evidence: dict[str, Any] | None,
    excluded: list[dict[str, str]],
    focus: str,
    criteria: str,
) -> dict[str, Any]:
    return {
        "schema": INTENT_SCHEMA,
        "project_id": project_id,
        "book_id": book.get("id"),
        "workspace_id": book.get("workspace_id"),
        "chapter": {
            "chapter_id": chapter.get("chapter_id"),
            "path": chapter.get("path"),
            "title": chapter.get("title"),
            "sha256": chapter.get("sha256"),
        },
        "source": {
            "binding_ref": source.get("binding_ref"),
            "approval_ref": source.get("approval_ref"),
            "capture_ref": source.get("capture_ref"),
            "status": source.get("status"),
            "mode": source.get("mode"),
        },
        "focus": focus,
        "evidence": [evidence] if evidence else [],
        "excluded": excluded,
        "author_note": "",
        "criteria": criteria,
        "criteria_sha256": hashlib.sha256(criteria.encode("utf-8")).hexdigest()
        if criteria
        else None,
    }


async def preview(
    session: Session,
    settings,
    project_id: str,
    chapter_id: str,
    *,
    focus: str = "economy",
    use_experience: bool = False,
) -> dict[str, Any]:
    context = living_service._project_context(session, project_id)
    client = living_service._client(session, settings)
    book = await _book_detail(client, context)
    chapter = _chapter(book, chapter_id)
    if chapter is None:
        raise LivingBookProblem(
            "That chapter is not in the approved book.",
            state="chapter_missing",
            status=404,
        )
    if focus not in FOCUSES:
        raise LivingBookProblem(
            "This journey supports the economy focus only.",
            state="focus_not_supported",
            status=422,
        )

    blockers: list[dict] = []
    warnings: list[str] = []
    source = dict(book.get("source") or {})
    if not book.get("ready"):
        blockers.append(_blocker("book_not_ready", book.get("error") or "The book is not ready."))
    if str(chapter.get("status") or "") != "current":
        blockers.append(_blocker("chapter_changed", "The chapter is not current in the capture."))
    if str(source.get("status") or "") != "current":
        blockers.append(_blocker("source_not_current", "The approved source is not current."))
    if not (book.get("model") or {}).get("ready"):
        blockers.append(_blocker("model_unavailable", "The governed model is not ready."))

    try:
        workspace = await client.workspace(str(book["workspace_id"]))
    except (LivingBookUnavailable, LivingBookError) as error:
        workspace = {"sources": []}
        blockers.append(_blocker("workspace_unavailable", str(error)))
    attachment_current = _source_matches(book, workspace)
    if not attachment_current:
        blockers.append(
            _blocker(
                "source_attachment_stale",
                "The reading workspace is attached to an older approval or capture than the book. "
                "Refresh the book source explicitly, then preview again.",
            )
        )

    quality = build_quality_context(session, settings, project_id, chapter_id)
    measure = _prose_measure(quality)
    evidence, quality_blockers = _economy(measure)
    blockers.extend(quality_blockers)
    excluded = _excluded(quality)

    criteria = ""
    if evidence is not None and measure is not None:
        try:
            criteria = _brief(chapter, measure, evidence)
        except LivingBookProblem as error:
            blockers.append(_blocker("brief_too_long", str(error)))

    plan: dict[str, Any] | None = None
    if not blockers:
        try:
            plan = await client.workflow_plan(
                str(book["workspace_id"]), str(chapter["path"])
            )
        except LivingBookError as error:
            code = str(error)
            if "conversation_source_not_in_workspace" in code:
                blockers.append(
                    _blocker(
                        "source_attachment_stale",
                        "ALIVE refused the plan because the workspace attachment is not current. "
                        "Refresh the book source explicitly, then preview again.",
                    )
                )
            else:
                blockers.append(_blocker("plan_unavailable", code))
        except LivingBookUnavailable as error:
            blockers.append(_blocker("alive_unavailable", str(error)))

    recent: list[dict[str, Any]] = []
    try:
        retained = await client.improvements(str(book["workspace_id"]))
        recent = [
            {
                "run_id": item.get("run_id"),
                "improvement_id": item.get("improvement_id"),
                "chapter_path": item.get("chapter_path"),
                "decision": item.get("decision"),
                "evaluation_status": item.get("evaluation_status"),
                "verdict": item.get("verdict"),
                "created_at": item.get("created_at"),
                "source_version": item.get("source_version"),
            }
            for item in (retained.get("improvements") or [])
            if item.get("chapter_path") == chapter.get("path")
        ][:6]
    except (LivingBookError, LivingBookUnavailable) as error:
        warnings.append(f"Recent improvements could not be listed: {error}")

    experience: dict[str, Any] | None = None
    if criteria:
        try:
            raw = await client.experience(
                str(book["workspace_id"]), str(chapter["path"]), criteria
            )
            experience = _experience_view(raw, use_experience)
        except (LivingBookError, LivingBookUnavailable) as error:
            experience = {
                "requested": use_experience,
                "eligible_candidates": 0,
                "selected": [],
                "items": [],
                "abstained": True,
                "error": str(error)[:600],
            }
            warnings.append("Earlier-decision experience could not be previewed.")
            if use_experience:
                blockers.append(_blocker("experience_unavailable", str(error)))
    else:
        experience = {
            "requested": use_experience,
            "eligible_candidates": 0,
            "selected": [],
            "items": [],
            "abstained": True,
        }

    intent = _intent(
        project_id,
        book,
        chapter,
        source,
        evidence,
        excluded,
        focus,
        criteria,
    )
    intent_sha256 = _digest(intent)
    plan_view = _plan_view(plan) if plan else None
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "eligible": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "focus": focus,
        "project_id": project_id,
        "book_id": book.get("id"),
        "workspace_id": book.get("workspace_id"),
        "chapter": {
            "chapter_id": chapter.get("chapter_id"),
            "path": chapter.get("path"),
            "title": chapter.get("title"),
            "sha256": chapter.get("sha256"),
            "word_count": chapter.get("word_count"),
            "status": chapter.get("status"),
        },
        "source": {
            **source,
            "chapter_current": str(chapter.get("status") or "") == "current",
            "workspace_attachment_current": attachment_current,
        },
        "model": book.get("model"),
        "quality": {
            "schema": quality.get("schema"),
            "coverage": quality.get("coverage"),
            "summary": quality.get("summary"),
            "limitations": quality.get("limitations"),
        },
        "evidence": evidence,
        "excluded": excluded,
        "brief": criteria,
        "criteria_sha256": intent.get("criteria_sha256"),
        "intent": intent,
        "intent_sha256": intent_sha256,
        "plan": plan_view,
        "experience": experience,
        "recent_improvements": recent,
        "authority": AUTHORITY,
        "notice": NOTICE,
        "use_experience": use_experience,
    }


def _require_preview(
    value: dict[str, Any],
    body: dict[str, Any],
    *,
    require_confirmation: bool,
) -> None:
    if not value.get("eligible"):
        codes = ", ".join(item["code"] for item in value.get("blockers") or [])
        raise LivingBookProblem(
            f"This chapter cannot be improved yet: {codes}.",
            state="not_eligible",
            status=409,
        )
    if require_confirmation and not body.get("confirmed"):
        raise LivingBookProblem(
            "Confirm the exact plan and model budget before the run starts.",
            state="confirmation_required",
            status=409,
        )
    if body.get("intent_sha256") != value.get("intent_sha256"):
        raise LivingBookProblem(
            "The quality evidence changed after the preview. Preview again.",
            state="intent_changed",
            status=409,
        )
    plan = value.get("plan") or {}
    if not plan or body.get("plan_sha256") != plan.get("plan_sha256"):
        raise LivingBookProblem(
            "The chapter plan changed after the preview. Preview again.",
            state="plan_changed",
            status=409,
        )
    if body.get("criteria") != value.get("brief"):
        raise LivingBookProblem(
            "The editorial brief changed after the preview. Preview again.",
            state="brief_changed",
            status=409,
        )
    model = (value.get("model") or {}).get("name")
    if body.get("model") and body.get("model") != model:
        raise LivingBookProblem(
            "The selected model is not the model shown in the preview.",
            state="model_changed",
            status=409,
        )


async def launch(
    session: Session,
    settings,
    project_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    chapter_id = str(body.get("chapter_id") or "")
    focus = str(body.get("focus") or "economy")
    use_experience = bool(body.get("use_experience"))
    value = await preview(
        session,
        settings,
        project_id,
        chapter_id,
        focus=focus,
        use_experience=use_experience,
    )
    _require_preview(value, body, require_confirmation=True)
    plan = value["plan"]
    model = body.get("model") or value["model"]["name"]
    key = ("m02b-" + str(body.get("idempotency_key") or ""))[:80]
    if len(key) <= 5:
        raise LivingBookProblem(
            "An idempotency key is required.",
            state="idempotency_required",
            status=422,
        )
    context = living_service._project_context(session, project_id)
    client = living_service._client(session, settings)
    book = await _book_detail(client, context)
    chapter = _chapter(book, chapter_id)
    if chapter is None:
        raise LivingBookProblem("That chapter is not in the approved book.", status=404)
    alive_body = {
        "chapter_path": chapter["path"],
        "criteria": value["brief"],
        "model": model,
        "use_experience": use_experience,
        "plan_sha256": plan["plan_sha256"],
        "confirmed": True,
        "workflow_version": plan["workflow_version"],
        "workflow_definition_id": plan["workflow_definition_id"],
        "workflow_definition_sha256": plan["workflow_definition_sha256"],
        "workflow_binding_sha256": plan["workflow_binding_sha256"],
        "idempotency_key": key,
    }
    run = await client.launch_workflow(str(value["workspace_id"]), alive_body)
    run_id = str(run.get("id") or "")
    if not run_id:
        raise LivingBookProblem(
            "ALIVE accepted the run but returned no run id.",
            state="launch_response_invalid",
            status=502,
        )
    return await detail(session, settings, project_id, run_id)


def _status_label(run: dict[str, Any], improvement: dict[str, Any]) -> str:
    status = str(run.get("status") or "UNKNOWN")
    if not run.get("terminal"):
        return "Running"
    if improvement.get("provenance") != "complete":
        if status == "COMPLETED":
            return "Completed without a retained proposal"
        return f"Stopped ({status})"
    decision = (improvement.get("state") or {}).get("decision") or "pending"
    if decision == "pending":
        if status == "COMPLETED":
            return "Proposal retained; awaiting author decision"
        return "Proposal retained; evaluation did not complete"
    return str(decision).replace("_", " ").capitalize()


async def detail(
    session: Session,
    settings,
    project_id: str,
    run_id: str,
) -> dict[str, Any]:
    context = living_service._project_context(session, project_id)
    client = living_service._client(session, settings)
    book = await _book_detail(client, context)
    workspace_id = str(book["workspace_id"])
    try:
        run = await client.workflow_run(workspace_id, run_id)
    except LivingBookError as error:
        if error.status == 404:
            raise LivingBookProblem(
                "That improvement run is not in this book's workspace.",
                state="run_not_found",
                status=404,
            ) from None
        raise
    improvement = await client.improvement(workspace_id, run_id)
    view_run = run.get("run") or {}
    order = {
        "review": 0,
        **{f"section_{index}": index for index in range(1, 7)},
        "check_proposal": 7,
        "save_proposal": 8,
        "evaluate": 9,
        "check_outcome": 10,
        "record_outcome": 11,
    }
    stages = sorted(
        [
            {
                "stage_id": item.get("stage_id"),
                "state": item.get("state"),
                "error_category": item.get("error_category"),
                "model_invocation_id": item.get("model_invocation_id"),
                "pi_run_id": item.get("pi_run_id"),
            }
            for item in (run.get("stages") or [])
        ],
        key=lambda item: order.get(str(item["stage_id"]), 99),
    )
    return {
        "schema": RUN_SCHEMA,
        "book_id": book.get("id"),
        "workspace_id": workspace_id,
        "run_id": run_id,
        "status": view_run.get("status"),
        "terminal": view_run.get("terminal"),
        "status_label": _status_label(view_run, improvement),
        "reason": run.get("reason"),
        "workflow": view_run.get("workflow"),
        "budget": view_run.get("budget"),
        "usage": run.get("usage"),
        "stages": stages,
        "chapter_path": improvement.get("chapter_path"),
        "provenance": improvement.get("provenance"),
        "missing": improvement.get("missing") or [],
        "original": {
            "path": (improvement.get("original") or {}).get("path"),
            "sha256": (improvement.get("original") or {}).get("sha256"),
        },
        "proposal": improvement.get("proposal"),
        "change": improvement.get("change"),
        "evaluation": improvement.get("evaluation"),
        "source_version": improvement.get("source_version"),
        "state": improvement.get("state"),
        "history": improvement.get("history") or [],
        "experience": run.get("experience"),
        "plan": run.get("plan"),
        "notice": NOTICE,
        "applied": False,
    }


async def decide(
    session: Session,
    settings,
    project_id: str,
    run_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    decision = str(body.get("decision") or "")
    if decision not in {"accepted", "rejected"}:
        raise LivingBookProblem(
            "This journey records accept or reject only; it does not write an edited chapter.",
            state="decision_not_available_without_write_authority",
            status=422,
        )
    context = living_service._project_context(session, project_id)
    client = living_service._client(session, settings)
    book = await _book_detail(client, context)
    workspace_id = str(book["workspace_id"])
    improvement = await client.improvement(workspace_id, run_id)
    if improvement.get("provenance") != "complete":
        raise LivingBookProblem(
            "This run has no complete retained proposal, so no decision can be recorded.",
            state="proposal_missing",
            status=409,
        )
    proposal = improvement.get("proposal") or {}
    if body.get("proposal_sha256") != proposal.get("sha256"):
        raise LivingBookProblem(
            "The proposal shown is not the retained proposal. Reload and decide again.",
            state="proposal_changed",
            status=409,
        )
    freshness = improvement.get("source_version") or {}
    if (
        decision == "accepted"
        and freshness.get("status") != "current"
        and not body.get("acknowledge_earlier_version")
    ):
        raise LivingBookProblem(
            "This proposal was generated from an earlier or unverifiable version of the chapter. "
            "Confirm that you are accepting it against that earlier version.",
            state="earlier_version_acknowledgement_required",
            status=409,
        )
    key = ("m02b-decision-" + str(body.get("idempotency_key") or ""))[:80]
    if len(key) <= 15:
        raise LivingBookProblem(
            "An idempotency key is required.",
            state="idempotency_required",
            status=422,
        )
    await client.decide(
        workspace_id,
        run_id,
        {
            "decision": decision,
            "proposal_sha256": proposal["sha256"],
            "comment": _text(body.get("comment"), 1000),
            "acknowledge_earlier_version": bool(body.get("acknowledge_earlier_version")),
            "idempotency_key": key,
        },
    )
    return await detail(session, settings, project_id, run_id)
