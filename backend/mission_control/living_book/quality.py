"""Bounded quality evidence for a Living Book request.

Mission is the quality broker. This module preserves each measure's identity, scale,
coverage, freshness and limitations. It never creates a composite book score and never
turns NOT_RUN into zero.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.models import (
    AdapterStatus,
    Application,
    ArtifactLoadObservation,
    Book,
    IntegrationRecord,
    Project,
    PublicationAssessment,
)
from mission_control.quality.service import workspace as quality_workspace
from mission_control.quality.service import resolve_book_root
from mission_control.technical import service as technical


def _clip(value: Any, limit: int = 600) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = text.replace("\x00", "")
    return text[:limit]


def _norm(path: str | None) -> str:
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(path))


def _writer_book(workspace: dict[str, Any], project_id: str, manuscript_root: str) -> dict | None:
    wanted = _norm(manuscript_root)
    for book in workspace.get("books", []):
        if not isinstance(book, dict):
            continue
        if book.get("project_id") == project_id:
            return book
        roots = [
            book.get("content_dir"),
            book.get("project_root"),
            book.get("repository_path"),
        ]
        if any(_norm(str(root)) and _norm(str(root)) in wanted for root in roots if root):
            return book
    return None


def _writer_chapter(book: dict | None, chapter_id: str | None) -> dict | None:
    if not book or not chapter_id:
        return None
    wanted = chapter_id.replace("\\", "/")
    for chapter in book.get("chapters", []):
        if not isinstance(chapter, dict):
            continue
        relative = str(chapter.get("relative_path") or "").replace("\\", "/")
        source = str(chapter.get("source_path") or "").replace("\\", "/")
        if relative.endswith(wanted) or source.endswith(wanted):
            return chapter
        if Path(relative or source).name == Path(wanted).name:
            return chapter
    return None


def _prose_measure(chapter: dict[str, Any] | None) -> dict[str, Any]:
    if chapter is None:
        return {
            "id": "mission.prose.manuscript-prose-v1",
            "kind": "model_judgment",
            "scope": "book",
            "status": "NOT_RUN",
            "label": "Manuscript prose evaluation",
            "detail": "No chapter is selected, so no chapter-level prose observation is supplied.",
            "limitations": [
                "Prose scores are single-run model judgments, not independent verification.",
                "A missing observation is NOT_RUN, not zero.",
            ],
        }
    current = chapter.get("current")
    if current is None:
        return {
            "id": "mission.prose.manuscript-prose-v1",
            "kind": "model_judgment",
            "scope": "chapter",
            "chapter_id": chapter.get("chapter_id"),
            "status": "NOT_RUN",
            "label": "Manuscript prose evaluation",
            "detail": "No current prose evaluation is recorded for this chapter.",
            "limitations": [
                "A missing observation is NOT_RUN, not zero.",
                "Running a campaign in Mission Control records a new observation; it does not change the manuscript.",
            ],
        }

    def field(name, default=None):
        if isinstance(current, dict):
            return current.get(name, default)
        return getattr(current, name, default)

    dimensions = {}
    for name, row in (field("dimensions") or {}).items():
        if not isinstance(row, dict):
            row = row.model_dump(mode="json") if hasattr(row, "model_dump") else {}
        dimensions[name] = {
            "score": row.get("score"),
            "evidence": _clip(row.get("evidence", ""), 500),
            "evidence_validated": bool(row.get("evidence_validated")),
        }
    return {
        "id": "mission.prose.manuscript-prose-v1",
        "kind": "model_judgment",
        "scope": "chapter",
        "chapter_id": field("chapter_id"),
        "status": str(field("derived_state", "current")).upper(),
        "label": "Manuscript prose evaluation",
        "rubric": field("rubric_id"),
        "rubric_version": field("rubric_version"),
        "model": field("actual_model"),
        "observed_at": field("created_at"),
        "chapter_revision": field("chapter_revision"),
        "value": {
            "overall": field("overall"),
            "aggregation": field("aggregation_method"),
            "dimensions": dimensions,
        },
        "findings": [
            {
                "code": item.get("code") or item.get("dimension") or "finding",
                "severity": item.get("severity", ""),
                "reason": _clip(item.get("reason", item.get("detail", "")), 500),
                "recommendation": _clip(item.get("recommendation", ""), 400),
            }
            for item in (field("findings") or [])[:5]
            if isinstance(item, dict)
        ],
        "limitations": list(field("limitations") or [])[:6]
        + ([field("uncertainty")] if field("uncertainty") else []),
    }


def _writer_measure(
    workspace: dict[str, Any],
    project_id: str,
    manuscript_root: str,
    chapter_id: str | None,
) -> dict[str, Any]:
    if not workspace.get("available"):
        return {
            "id": "mission.writer.readability",
            "kind": "deterministic_measure",
            "scope": "chapter" if chapter_id else "book",
            "status": "UNAVAILABLE",
            "label": "Writer readability",
            "detail": _clip(
                workspace.get("detail") or workspace.get("error") or "Writer is unavailable."
            ),
            "limitations": ["Writer is a separate read-only integration."],
        }
    book = _writer_book(workspace, project_id, manuscript_root)
    if book is None:
        return {
            "id": "mission.writer.readability",
            "kind": "deterministic_measure",
            "scope": "chapter" if chapter_id else "book",
            "status": "NOT_RUN",
            "label": "Writer readability",
            "detail": "Writer has no editing report registered for this book.",
            "limitations": [
                "Registering the book in Writer and running its read-only audit adds this measure.",
            ],
        }
    chapter = _writer_chapter(book, chapter_id)
    if chapter is not None:
        dimensions = [
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "score": item.get("score"),
                "status_band": item.get("status_band"),
                "finding_codes": list(item.get("finding_codes") or [])[:8],
                "limitations": list(item.get("limitations") or [])[:4],
            }
            for item in (chapter.get("dimensions") or [])
            if isinstance(item, dict)
        ]
        return {
            "id": "mission.writer.readability",
            "kind": "deterministic_measure",
            "scope": "chapter",
            "chapter_id": chapter_id,
            "status": "CURRENT" if chapter.get("current") else "STALE",
            "label": "Writer readability",
            "observed_at": book.get("last_checked"),
            "report_id": book.get("report_id"),
            "value": {
                "status_band": chapter.get("status_band"),
                "word_count": chapter.get("word_count"),
                "finding_count": chapter.get("finding_count"),
                "dimensions": dimensions,
            },
            "findings": [
                {
                    "code": item.get("code"),
                    "severity": item.get("severity"),
                    "reason": _clip(item.get("reason", ""), 500),
                    "recommendation": _clip(item.get("recommendation", ""), 400),
                    "line_start": (item.get("locator") or {}).get("line_start"),
                    "line_end": (item.get("locator") or {}).get("line_end"),
                }
                for item in (chapter.get("findings") or [])[:5]
                if isinstance(item, dict)
            ],
            "limitations": list(book.get("limitations") or [])[:6],
        }
    return {
        "id": "mission.writer.readability",
        "kind": "deterministic_measure",
        "scope": "book",
        "status": "CURRENT" if book.get("report_id") else "NOT_RUN",
        "label": "Writer readability",
        "observed_at": book.get("last_checked"),
        "report_id": book.get("report_id"),
        "value": {
            "chapters_available": book.get("chapters_available"),
            "status": book.get("status"),
            "highest_risk": book.get("highest_risk"),
            "findings_preview": (book.get("findings_preview") or [])[:5],
        },
        "limitations": list(book.get("limitations") or [])[:6],
    }


def _technical_measure(session: Session, project_id: str, chapter_id: str | None) -> dict[str, Any]:
    overview = technical.book_overview(session, project_id)
    value: dict[str, Any] = {"book": overview}
    status = "NOT_RUN" if overview.get("claims_total", 0) == 0 else "CURRENT"
    if chapter_id:
        assessment = technical.chapter_assessment(session, project_id, chapter_id)
        try:
            book_root = resolve_book_root(session, project_id)
        except Exception:
            book_root = None
        completeness = technical.chapter_completeness(
            session, project_id, chapter_id, book_root=book_root
        )
        value["chapter"] = {
            "claims_total": assessment.claims_total,
            "claims_source_verified": assessment.claims_source_verified,
            "claims_unresolved": assessment.claims_unresolved,
            "by_status": assessment.by_status,
            "completeness": completeness,
        }
        if assessment.claims_total:
            status = "CURRENT"
    return {
        "id": "mission.technical.claims",
        "kind": "verified_evidence",
        "scope": "chapter" if chapter_id else "book",
        "chapter_id": chapter_id,
        "status": status,
        "label": "Technical claims and completeness",
        "value": value,
        "limitations": [
            "Technical verification is a separate measurement from prose quality.",
            "No claims or no verification is NOT_RUN, not a pass.",
        ],
    }


def _publication_measure(session: Session, project_id: str) -> dict[str, Any]:
    row = session.scalar(
        select(PublicationAssessment)
        .where(PublicationAssessment.project_id == project_id)
        .order_by(PublicationAssessment.created_at.desc())
        .limit(1)
    )
    if row is None:
        return {
            "id": "mission.publication.readiness",
            "kind": "gate",
            "scope": "book",
            "status": "NOT_RUN",
            "label": "Publication readiness",
            "detail": "No publication assessment is recorded for this book.",
            "limitations": [
                "Publication readiness is a gate-based decision, not an average of quality scores.",
                "NOT_RUN is not a release approval.",
            ],
        }
    return {
        "id": "mission.publication.readiness",
        "kind": "gate",
        "scope": "book",
        "status": row.freshness,
        "label": "Publication readiness",
        "observed_at": row.created_at,
        "value": {
            "assessment_status": row.assessment_status,
            "freshness": row.freshness,
            "readiness_detail": _clip(row.readiness_detail, 1000),
            "chapter_count": row.chapter_count,
            "manuscript_fingerprint": row.manuscript_fingerprint,
        },
        "limitations": [
            "A missing gate is not a passed gate.",
            "Readiness is one exact manuscript snapshot, not a claim about every future revision.",
        ],
    }


def _artifact_measure(session: Session, project_id: str, chapter_id: str | None) -> dict[str, Any]:
    query = select(ArtifactLoadObservation).where(ArtifactLoadObservation.project_id == project_id)
    if chapter_id:
        query = query.where(ArtifactLoadObservation.chapter_id == chapter_id)
    row = session.scalar(query.order_by(ArtifactLoadObservation.created_at.desc()).limit(1))
    if row is None:
        return {
            "id": "mission.artifact_load",
            "kind": "deterministic_measure",
            "scope": "chapter" if chapter_id else "book",
            "status": "NOT_RUN",
            "label": "Artifact Load",
            "detail": "No Artifact Load observation is recorded for this scope.",
            "limitations": ["Artifact Load is independent of prose scores."],
        }
    return {
        "id": "mission.artifact_load",
        "kind": "deterministic_measure",
        "scope": "chapter" if chapter_id else "book",
        "chapter_id": row.chapter_id,
        "status": row.status,
        "label": "Artifact Load",
        "observed_at": row.created_at,
        "value": {
            "weighted_load": row.weighted_load,
            "mechanical_pressure": row.mechanical_pressure,
            "confirmed": row.confirmed,
            "high": row.high,
            "medium": row.medium,
            "coverage_mechanical": row.coverage_mechanical,
            "coverage_semantic": row.coverage_semantic,
        },
        "limitations": list(row.limitations or [])[:6],
    }


def _prose_summary(quality) -> dict[str, Any]:
    overalls = []
    weakest = []
    dimensions: dict[str, list[float]] = {}
    current = 0
    for chapter in quality.chapters:
        if chapter.current is None:
            continue
        current += 1
        evaluation = chapter.current
        if evaluation.overall is not None:
            overalls.append(evaluation.overall)
            weakest.append(
                {
                    "chapter_id": chapter.chapter_id,
                    "overall": evaluation.overall,
                    "model": evaluation.actual_model,
                    "observed_at": evaluation.created_at,
                }
            )
        for name, row in (evaluation.dimensions or {}).items():
            score = row.get("score") if isinstance(row, dict) else getattr(row, "score", None)
            if isinstance(score, (int, float)):
                dimensions.setdefault(name, []).append(float(score))
    weakest.sort(key=lambda item: item["overall"])
    means = {
        name: round(sum(values) / len(values), 2) for name, values in dimensions.items() if values
    }
    return {
        "rubric": "manuscript-prose-v1",
        "chapters_total": quality.chapters_total,
        "chapters_current": current,
        "chapters_evaluated": quality.chapters_evaluated,
        "overall_min": min(overalls) if overalls else None,
        "overall_max": max(overalls) if overalls else None,
        "dimension_means": means,
        "weakest_chapters": weakest[:6],
        "limitations": list(quality.limitations or [])[:6],
    }


def _writer_workspace(session: Session) -> dict[str, Any]:
    application = session.get(Application, "writer")
    status = session.get(AdapterStatus, "adapter-app-writer")
    if application is None or not application.enabled or status is None or not status.available:
        return {
            "available": False,
            "detail": "Writer is not configured or its last observation is unavailable.",
            "books": [],
        }
    rows = session.scalars(
        select(IntegrationRecord)
        .where(
            IntegrationRecord.application_id == "writer",
            IntegrationRecord.resource_type == "writer_editing_book",
            IntegrationRecord.current.is_(True),
        )
        .order_by(IntegrationRecord.source_timestamp.desc())
    ).all()
    books = [dict(row.data) for row in rows if isinstance(row.data, dict)]
    return {"available": True, "detail": status.detail if status else "", "books": books}


def build_quality_context(
    session: Session,
    settings,
    project_id: str,
    chapter_id: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    project = session.get(Project, project_id)
    book = session.scalar(select(Book).where(Book.project_id == project_id))
    try:
        manuscript_root = resolve_book_root(session, project_id)
    except Exception:
        manuscript_root = next(
            (str(path) for path in (book.manuscript_paths if book else []) if path), ""
        )
    quality = quality_workspace(session, project_id)
    chapter_summary = next(
        (item for item in quality.chapters if item.chapter_id == chapter_id), None
    )
    chapter_value = chapter_summary.model_dump(mode="json") if chapter_summary else None
    if chapter_value is None and chapter_id:
        chapter_value = {
            "chapter_id": chapter_id,
            "chapter_title": None,
            "current": None,
            "evaluations": [],
            "sections": [],
        }
    try:
        writer = _writer_workspace(session)
    except Exception as error:
        writer = {
            "available": False,
            "detail": f"Writer could not be read: {type(error).__name__}.",
            "books": [],
        }
    measures = [
        _prose_measure(chapter_value),
        _writer_measure(writer, project_id, manuscript_root, chapter_id),
        _technical_measure(session, project_id, chapter_id),
        _publication_measure(session, project_id),
        _artifact_measure(session, project_id, chapter_id),
    ]
    summary = _prose_summary(quality)
    coverage = {
        "prose": {
            "status": "CURRENT" if summary["chapters_current"] else "NOT_RUN",
            "current": summary["chapters_current"],
            "total": summary["chapters_total"],
            "rubric": summary["rubric"],
        },
        "writer": {
            "status": measures[1]["status"],
            "label": measures[1]["label"],
            "detail": measures[1].get("detail", ""),
        },
        "technical": {
            "status": measures[2]["status"],
            "claims_total": measures[2]["value"]["book"].get("claims_total", 0),
        },
        "publication": {
            "status": measures[3]["status"],
            "detail": measures[3].get("detail", ""),
        },
        "artifact_load": {"status": measures[4]["status"]},
    }
    context = {
        "schema": "book-quality-context.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "book": {
            "project_id": project_id,
            "title": book.title if book else (project.name if project else project_id),
            "manuscript_root": manuscript_root,
        },
        "chapter": {
            "chapter_id": chapter_id,
            "title": (chapter_value or {}).get("chapter_title"),
        }
        if chapter_id
        else None,
        "coverage": coverage,
        "measures": measures,
        "summary": summary,
        "limitations": [
            "Prose scores are single-run model judgments; quoted evidence is not independently verified merely because it is quoted.",
            "Writer readability, technical verification, Artifact Load and publication readiness are separate measures.",
            "Do not average incompatible rubrics. NOT_RUN is not zero and STALE is not current.",
            "This context describes recorded evidence, not a publication decision.",
        ],
    }
    raw = json.dumps(context, ensure_ascii=False, default=str)
    if len(raw.encode("utf-8")) > 60_000:
        context["measures"] = context["measures"][:3]
        context["limitations"].append("Some measures were omitted to keep the context bounded.")
    return context


def quality_summary(session: Session, settings, project_id: str) -> dict[str, Any]:
    context = build_quality_context(session, settings, project_id)
    return {
        "schema": context["schema"],
        "coverage": context["coverage"],
        "summary": context["summary"],
        "limitations": context["limitations"],
    }
