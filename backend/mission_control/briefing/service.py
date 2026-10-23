"""Daily briefing generation.

The deterministic briefing is always available and is the source of truth for
the ranked items. An optional OpenAI-compatible model may add an interpretation
only after explicit configuration, consent and a request. The model never
overwrites user priorities or creates tasks.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.models import (
    AdapterStatus,
    Briefing,
    Project,
    Recommendation,
    Setting,
    Task,
    WorkCheckpoint,
)
from mission_control.persistence.db import Database, now_iso
from mission_control.projects.service import current_focus
from mission_control.schemas import BriefingItem, BriefingRead

logger = logging.getLogger(__name__)


def _project_name(session: Session, project_id: str | None) -> str | None:
    if not project_id:
        return None
    project = session.get(Project, project_id)
    return project.name if project else None


def _build_items(session: Session) -> tuple[list[BriefingItem], list[dict[str, Any]]]:
    items: list[BriefingItem] = []
    observations: list[dict[str, Any]] = []
    focus = current_focus(session)
    ranked_projects = list(
        session.scalars(
            select(Project)
            .where(Project.pinned.is_(True), Project.archived.is_(False))
            .order_by(Project.display_order, Project.priority)
        ).all()
    )
    if focus:
        ranked_projects = [project for project in ranked_projects if project.id != focus.id]
        ranked_projects.insert(0, focus)

    for project in ranked_projects:
        checkpoint = session.scalar(
            select(WorkCheckpoint)
            .where(WorkCheckpoint.project_id == project.id)
            .order_by(desc(WorkCheckpoint.created_at))
        )
        if checkpoint and checkpoint.next_action:
            title = f"Resume {project.name}: {checkpoint.next_action[:220]}"
            rationale = checkpoint.summary
            provenance = "recorded_checkpoint"
            evidence = [f"checkpoint:{checkpoint.id}"] + checkpoint.evidence_refs[:5]
            source = "latest saved checkpoint"
        elif project.next_action:
            title = f"{project.name}: {project.next_action[:220]}"
            rationale = project.current_milestone or "Recorded next action for this priority project."
            provenance = "user_priority"
            evidence = [f"project:{project.id}", f"milestone:{project.current_milestone[:120]}"]
            source = "user-maintained project state"
        else:
            title = f"Choose the next action for {project.name}"
            rationale = project.current_milestone or "This is a pinned priority, but no next action is recorded."
            provenance = "user_priority"
            evidence = [f"project:{project.id}"]
            source = "pinned project"
        items.append(
            BriefingItem(
                rank=0,
                title=title,
                project_id=project.id,
                project_name=project.name,
                rationale=rationale,
                provenance=provenance,
                evidence=evidence,
                source=source,
            )
        )

    tasks = session.scalars(
        select(Task)
        .where(Task.status.in_(["open", "in_progress", "blocked"]))
        .order_by(Task.priority, desc(Task.created_at))
        .limit(8)
    ).all()
    for task in tasks:
        project_name = _project_name(session, task.project_id)
        items.append(
            BriefingItem(
                rank=0,
                title=f"Task: {task.title}",
                project_id=task.project_id,
                project_name=project_name,
                rationale=(
                    f"Recorded task with status {task.status}."
                    + (f" {task.description[:300]}" if task.description else "")
                ),
                provenance="user_task",
                evidence=[f"task:{task.id}"],
                source="user-entered task",
            )
        )

    recommendations = session.scalars(
        select(Recommendation)
        .where(Recommendation.review_state == "pending")
        .order_by(desc(Recommendation.created_at))
        .limit(6)
    ).all()
    for rec in recommendations:
        items.append(
            BriefingItem(
                rank=0,
                title=f"Review: {rec.title[:220]}",
                project_id=rec.project_id,
                project_name=_project_name(session, rec.project_id),
                rationale=rec.rationale,
                provenance=rec.provenance,
                evidence=rec.evidence[:8],
                source=rec.source_application or "adapter evidence",
            )
        )

    adapters = session.scalars(select(AdapterStatus)).all()
    unavailable = [item.adapter for item in adapters if not item.available]
    observations.extend(
        [
            {"kind": "focus", "project": focus.name if focus else None, "detail": "Current focus from persisted workspace state."},
            {
                "kind": "counts",
                "priority_projects": len(ranked_projects),
                "open_tasks": len(tasks),
                "pending_recommendations": len(recommendations),
                "unavailable_adapters": unavailable,
            },
        ]
    )
    for index, item in enumerate(items[:12], start=1):
        item.rank = index
    return items[:12], observations


def _render(items: list[BriefingItem], observations: list[dict[str, Any]]) -> str:
    if not items:
        return (
            "No grounded priorities are recorded yet. Pin a project, add a task or save a "
            "checkpoint so the briefing has evidence to work from."
        )
    lines = ["Suggested focus", ""]
    for item in items:
        project = f" — {item.project_name}" if item.project_name else ""
        lines.append(f"{item.rank}. {item.title}{project}")
        if item.rationale:
            lines.append(f"   {item.rationale[:500]}")
        lines.append(f"   Source: {item.source or item.provenance}.")
        lines.append("")
    return "\n".join(lines).strip()


def _extract_json(content: str) -> Any:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


async def _ai_interpretation(
    session: Session,
    items: list[BriefingItem],
) -> tuple[list[BriefingItem], str | None, str | None, str, str]:
    setting = session.get(Setting, "ai")
    config = setting.value if setting and isinstance(setting.value, dict) else {}
    if not (config.get("enabled") and config.get("consent")):
        return [], None, "AI is disabled or consent has not been recorded.", "ai_not_configured", ""
    base_url = str(config.get("base_url") or "").rstrip("/")
    model = str(config.get("model") or "")
    if not base_url or not model:
        return [], None, "AI base_url or model is missing.", "ai_not_configured", ""
    timeout = float(config.get("timeout_seconds", 45))
    key_env = str(config.get("api_key_env") or "")
    api_key = os.environ.get(key_env) if key_env else None
    payload_items = [
        {
            "rank": item.rank,
            "title": item.title,
            "project": item.project_name,
            "rationale": item.rationale[:1000],
            "provenance": item.provenance,
            "evidence": item.evidence[:5],
        }
        for item in items
    ]
    prompt = (
        "You are advising a human-directed local AI work environment. Use ONLY the observations "
        "below. Do not invent tasks, deadlines, progress, or completed work. Preserve the existing "
        "priority order. Return strict JSON with keys 'summary' (a short paragraph) and 'items' "
        "(at most 3 additional suggestions, each with title, rationale and evidence_refs drawn from "
        "the observations). Suggestions are advisory and must not claim to replace the user's decisions.\n\n"
        + json.dumps(payload_items, ensure_ascii=False)
    )
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = base_url if base_url.endswith("/chat/completions") else base_url + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(
                url,
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Return only grounded JSON. Never invent evidence or overwrite human priorities.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
        if response.status_code != 200:
            return [], model, f"AI provider returned HTTP {response.status_code}.", "ai_unavailable", ""
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        if not isinstance(parsed, dict):
            return [], model, "AI response was not valid JSON; deterministic briefing retained.", "ai_unavailable", ""
        ai_items: list[BriefingItem] = []
        for raw in list(parsed.get("items") or [])[:3]:
            if not isinstance(raw, dict) or not raw.get("title"):
                continue
            evidence = [str(value)[:500] for value in list(raw.get("evidence_refs") or [])[:5]]
            ai_items.append(
                BriefingItem(
                    rank=0,
                    title=str(raw["title"])[:300],
                    rationale=str(raw.get("rationale") or "")[:1200],
                    project_id=None,
                    project_name=None,
                    provenance="ai_recommendation",
                    evidence=evidence,
                    source="AI interpretation of recorded evidence",
                )
            )
        summary = str(parsed.get("summary") or "")[:4000]
        return ai_items, model, None, "complete", summary
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        return [], model, f"AI request failed ({exc.__class__.__name__}); deterministic briefing retained.", "ai_unavailable", ""


def _to_read(briefing: Briefing) -> BriefingRead:
    return BriefingRead(
        id=briefing.id,
        created_at=briefing.created_at,
        mode=briefing.mode,
        provider=briefing.provider,
        model=briefing.model,
        status=briefing.status,
        content=briefing.content,
        items=[BriefingItem(**item) for item in briefing.items],
        observations=briefing.observations,
        error=briefing.error,
    )


def latest_briefing(session: Session) -> BriefingRead | None:
    briefing = session.scalar(select(Briefing).order_by(desc(Briefing.created_at)).limit(1))
    return _to_read(briefing) if briefing else None


async def generate_briefing(database: Database, *, use_ai: bool) -> BriefingRead:
    with database.session() as session:
        items, observations = _build_items(session)
        deterministic_content = _render(items, observations)
        mode = "deterministic"
        provider = None
        model = None
        status = "complete"
        error = None
        content = deterministic_content
        if use_ai:
            ai_items, model, error, status, summary = await _ai_interpretation(session, items)
            if ai_items:
                next_rank = len(items) + 1
                for ai_item in ai_items:
                    ai_item.rank = next_rank
                    next_rank += 1
                items.extend(ai_items)
            if status == "complete":
                mode = "ai"
                provider = "openai-compatible"
                content = deterministic_content
                if summary:
                    content = content + "\n\nAI interpretation (advisory):\n" + summary
            else:
                content = deterministic_content + (
                    f"\n\nAI interpretation unavailable: {error}" if error else ""
                )
        briefing = Briefing(
            id=f"brief-{uuid.uuid4().hex[:16]}",
            created_at=now_iso(),
            mode=mode,
            provider=provider,
            model=model,
            status=status,
            content=content,
            items=[item.model_dump() for item in items],
            observations=observations,
            error=error,
        )
        session.add(briefing)
        record_activity(
            session,
            event_type="briefing_generated",
            title="Daily briefing generated",
            detail=(
                f"{len(items)} grounded items; mode {mode}; sources include checkpoints, "
                "user tasks, recommendations and priority books."
            ),
            source="mission-control",
            provenance="ai_recommendation" if mode == "ai" else "derived_observation",
            metadata={"mode": mode, "status": status, "item_count": len(items)},
        )
        session.flush()
        return _to_read(briefing)
