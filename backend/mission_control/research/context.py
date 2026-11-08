"""Research context and export construction for Next opportunities.

The export package and the contextual chat deliberately share this module.  A
single representation of an opportunity keeps the copied review package and the
conversation grounding from drifting apart.

Everything here is read-only.  The builder never writes to Next, never calls a
model, and never invents a source link or finding that Next did not record.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.integrations.store import latest_decision
from mission_control.models import IntegrationRecord, Project

CONTEXT_SCHEMA = "mc.research-context.v1"
EXPORT_SCHEMA = "mc.research-export.v1"
_SOURCE_NOTES = {
    "github": "GitHub implementation or reference repository",
    "arxiv": "Original research source (arXiv)",
    "huggingface_daily": "Original research source (Hugging Face daily feed)",
    "huggingface": "Original research source (Hugging Face)",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any, limit: int = 12_000) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _is_http_url(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith(("http://", "https://"))


def _source_kind(item: dict[str, Any]) -> str:
    channel = str(item.get("source") or "").casefold()
    url = str(item.get("url") or "").casefold()
    if channel == "github" or "github.com" in url:
        return _SOURCE_NOTES["github"]
    return _SOURCE_NOTES.get(channel, "Source item recorded by Next")


def _decision_value(decision: Any) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "decision": decision.decision,
        "reason": decision.reason,
        "sync_state": decision.sync_state,
        "decided_at": decision.decided_at,
        "source_decision_id": decision.source_decision_id,
        "owner": "Mission Control (local only)",
    }


def _score_entries(scores: dict[str, Any]) -> list[dict[str, Any]]:
    labels = {
        "score": "Overall score",
        "capability_gain": "Capability gain",
        "feasibility": "Feasibility",
        "cost_efficiency": "Cost efficiency",
        "evidence_strength": "Evidence strength",
        "novelty": "Novelty",
        "uncertainty": "Uncertainty",
        "overall_confidence": "Overall confidence",
    }
    entries: list[dict[str, Any]] = []
    for key, label in labels.items():
        if key not in scores:
            continue
        value = scores.get(key)
        entries.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "recorded": value is not None,
            }
        )
    return entries


def _stable_source(source: dict[str, Any]) -> dict[str, Any]:
    # Freshness metadata changes on every refresh even when the content does
    # not.  The fingerprint is over the evidence, not the observation clock.
    return {
        key: value
        for key, value in source.items()
        if key not in {"observed_at", "stale", "source_timestamp"}
    }


def _fingerprint(package: dict[str, Any]) -> str:
    stable = {
        "schema": package.get("schema"),
        "source": _stable_source(package.get("source") or {}),
        "identity": package.get("identity"),
        "description": package.get("description"),
        "sources_and_evidence": package.get("sources_and_evidence"),
        "evaluation": package.get("evaluation"),
        "experiment": package.get("experiment"),
        "decisions": package.get("decisions"),
    }
    encoded = json.dumps(stable, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _related_records(
    session: Session, record: IntegrationRecord
) -> tuple[list[IntegrationRecord], list[IntegrationRecord]]:
    gaps = [
        row
        for row in session.scalars(
            select(IntegrationRecord).where(
                IntegrationRecord.application_id == "next",
                IntegrationRecord.resource_type == "next_evidence_gap",
                IntegrationRecord.current.is_(True),
            )
        ).all()
        if str((row.data or {}).get("opportunity_id") or "") == record.external_id
    ]
    experiments = [
        row
        for row in session.scalars(
            select(IntegrationRecord).where(
                IntegrationRecord.application_id == "next",
                IntegrationRecord.resource_type == "next_experiment",
                IntegrationRecord.current.is_(True),
            )
        ).all()
        if str((row.data or {}).get("opportunity_id") or "") == record.external_id
    ]
    return gaps, experiments


def build_context_package(
    session: Session,
    record: IntegrationRecord,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a self-contained review package for one Next opportunity."""

    if record.application_id != "next" or record.resource_type != "next_opportunity":
        raise ValueError("Research context is only available for Next opportunities")

    data = dict(record.data or {})
    scores = dict(data.get("scores") or {})
    source_items = [
        item for item in list(data.get("items") or []) if isinstance(item, dict)
    ]
    gaps, experiments = _related_records(session, record)
    local_decision = latest_decision(
        session, record.application_id, record.resource_type, record.external_id
    )
    project = session.get(Project, record.project_id) if record.project_id else None

    mode = str(data.get("mode") or "unknown")
    is_combination = mode.casefold() == "combine"
    basis = _clean_text(data.get("evaluation_basis"), 2_000)
    basis_lower = (basis or "").casefold()
    provisional = any(
        marker in basis_lower
        for marker in ("provisional", "estimate", "heuristic", "rule-based")
    )
    assessment_status = "Provisional" if provisional else "Recorded" if basis else "Not recorded"

    items: list[dict[str, Any]] = []
    missing_fields: list[str] = []
    for source_item in source_items:
        recorded_url = _clean_text(source_item.get("url"), 2_000)
        item = {
            "id": _clean_text(source_item.get("id"), 500) or "not recorded",
            "title": _clean_text(source_item.get("title"), 1_000) or "Untitled source item",
            "source": _clean_text(source_item.get("source"), 200) or "not recorded",
            "source_kind": _source_kind(source_item),
            "description": _clean_text(source_item.get("description"), 4_000),
            "url": recorded_url if _is_http_url(recorded_url) else None,
            "recorded_reference": recorded_url,
            "url_recorded": bool(recorded_url),
        }
        if recorded_url and not item["url"]:
            item["reference_note"] = (
                "Next recorded a source identifier rather than a full URL. "
                "No link was invented."
            )
        if not recorded_url:
            item["reference_note"] = (
                "No URL or source identifier was recorded by Next. "
                "No link was invented."
            )
        items.append(item)

    if not items:
        missing_fields.append("No source items were recorded for this opportunity.")
    if any(not item["url"] for item in items):
        missing_fields.append(
            "At least one source item has no recorded URL; a citation cannot be opened "
            "from this package."
        )
    if not data.get("evidence") and not record.evidence:
        missing_fields.append("No supporting evidence text was recorded.")
    if not gaps:
        missing_fields.append("No evidence-gap analysis was associated with this opportunity.")
    if not experiments:
        missing_fields.append("No experiment has been run for this opportunity.")
        missing_fields.append("No experiment success criteria were recorded.")

    evidence_gaps = [
        {
            "current_verdict": _clean_text((gap.data or {}).get("current_verdict"), 4_000),
            "gaps": list((gap.data or {}).get("gaps") or [])[:20],
            "analyzed_at": (gap.data or {}).get("analyzed_at"),
            "source_timestamp": gap.source_timestamp,
        }
        for gap in gaps
    ]
    prior_experiments = [
        {
            "id": experiment.external_id,
            "title": experiment.title,
            "status": experiment.state,
            "hypothesis": _clean_text((experiment.data or {}).get("hypothesis"), 4_000),
            "baseline_metric": _clean_text(
                (experiment.data or {}).get("baseline_metric"), 2_000
            ),
            "expected_improvement": _clean_text(
                (experiment.data or {}).get("expected_improvement"), 2_000
            ),
            "actual_result": _clean_text(
                (experiment.data or {}).get("actual_result"), 4_000
            ),
            "created_at": (experiment.data or {}).get("created_at"),
        }
        for experiment in experiments
    ]

    source_decision_history = [
        item
        for item in list(data.get("source_decision_history") or [])
        if isinstance(item, dict)
    ]

    age_seconds: float | None = None
    try:
        observed = datetime.fromisoformat(str(record.observed_at).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - observed).total_seconds()
    except (TypeError, ValueError):
        pass
    stale = age_seconds is None or age_seconds > record.stale_after_seconds

    package: dict[str, Any] = {
        "schema": CONTEXT_SCHEMA,
        "generated_at": generated_at or _now(),
        "source": {
            "application": "next",
            "application_name": "Next",
            "resource_id": record.id,
            "opportunity_id": record.external_id,
            "resource_type": record.resource_type,
            "source_version": record.source_version,
            "source_mode": data.get("source_mode"),
            "source_ref": data.get("source_ref"),
            "observed_at": record.observed_at,
            "source_timestamp": record.source_timestamp,
            "stale_after_seconds": record.stale_after_seconds,
            "stale": stale,
            "read_only": True,
        },
        "identity": {
            "title": record.title,
            "opportunity_id": record.external_id,
            "opportunity_type": mode,
            "queue_type": data.get("queue_type"),
            "status": record.state,
            "research_status": data.get("research_status"),
            "is_proposed_combination": is_combination,
            "themes": list(data.get("themes") or []),
            "source_channels": list(data.get("sources") or []),
            "project_id": record.project_id,
            "project_name": project.name if project else None,
        },
        "description": {
            "recorded_summary": record.summary,
            "recorded_description": _clean_text(data.get("description")),
            "what_discovered": _clean_text(data.get("what_discovered")),
            "next_interpretation": {
                "what_is_new": _clean_text(data.get("what_is_new")),
                "capability_hypothesis": _clean_text(data.get("capability_unlocked")),
                "relation_to_existing": _clean_text(data.get("relation_to_existing")),
                "why_not": _clean_text(data.get("why_not")),
            },
        },
        "sources_and_evidence": {
            "items": items,
            "source_channels": list(data.get("sources") or []),
            "supporting_evidence": list(record.evidence or [])[:30],
            "evidence_gaps": evidence_gaps,
            "missing_evidence": missing_fields,
            "full_source_content_retrieved": False,
            "note": (
                "Mission Control has only the source metadata recorded by Next. "
                "Full paper, repository or README content was not retrieved and a "
                "summary must not be treated as a complete reading."
            ),
        },
        "evaluation": {
            "assessment_status": assessment_status,
            "evaluation_basis": basis,
            "scores": _score_entries(scores),
            "uncertainty": scores.get("uncertainty"),
            "provisional": provisional,
            "missing_dimensions": [
                entry["label"] for entry in _score_entries(scores) if entry["value"] is None
            ],
            "known_limitations": [
                value
                for value in [
                    _clean_text(data.get("why_not"), 4_000),
                    "Scores were produced by Next and are not independent verification.",
                    (
                        "This is a provisional rule-based estimate, not a measured "
                        "experimental result."
                        if provisional
                        else None
                    ),
                ]
                if value
            ],
            "zero_value_caution": (
                "A recorded 0.0 on a provisional combined record may mean "
                "'not assessed'; it must not be read as measured zero performance."
                if is_combination and provisional
                else None
            ),
        },
        "experiment": {
            "proposed_test": _clean_text(data.get("simplest_experiment")),
            "success_criteria": None,
            "falsification": _clean_text(data.get("falsification")),
            "prior_experiments": prior_experiments,
            "experiment_run": bool(prior_experiments),
            "status": "No experiment has been run." if not prior_experiments else "Recorded experiments exist.",
        },
        "decisions": {
            "source_decision_history": source_decision_history[-10:],
            "local_decision": _decision_value(local_decision),
            "note": (
                "Next's recorded decision history and Mission Control's local-only "
                "human decision are distinct. A local decision does not modify Next."
            ),
        },
        "review_questions": [
            "Explain the research and the underlying technical mechanisms in plain language.",
            "Evaluate whether the claimed opportunity is genuinely novel, and compare it with existing approaches.",
            "Separate demonstrated findings from speculation, assumptions and missing evidence.",
            "Assess relevance to local LLMs, coding agents, recursive self-improvement, evaluation and autonomous workflows where applicable.",
            "Propose a small, falsifiable experiment with a baseline, measurement and stop condition.",
            "Recommend whether to investigate, prototype, defer or reject, with confidence and unresolved questions.",
        ],
    }
    package["fingerprint"] = _fingerprint(package)
    return package


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- None recorded."


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return "Not recorded"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _table(rows: list[tuple[str, Any]]) -> str:
    lines = ["| Field | Recorded value |", "| --- | --- |"]
    for label, value in rows:
        rendered = _format_value(value).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {label} | {rendered} |")
    return "\n".join(lines)


def render_export_markdown(package: dict[str, Any]) -> str:
    """Render the same context package as a portable Markdown review prompt."""

    source = package.get("source") or {}
    identity = package.get("identity") or {}
    description = package.get("description") or {}
    interpretation = description.get("next_interpretation") or {}
    sources = package.get("sources_and_evidence") or {}
    evaluation = package.get("evaluation") or {}
    experiment = package.get("experiment") or {}
    decisions = package.get("decisions") or {}

    title = identity.get("title") or "Untitled Next opportunity"
    lines: list[str] = [
        f"# Research review package — {title}",
        "",
        "> Prepared by Mission Control from Next's read-only research store. "
        "This package is review context, not a verified finding. No model was "
        "invoked to create it.",
        "",
        "## A. Review instructions",
        "",
        "You are receiving a research opportunity recorded by Next. Treat it as a "
        "candidate for critical review, not as a validated result. Do not assume the "
        "opportunity is valid, novel or technically sound.",
        "",
        "Please:",
        "",
        "- Explain the research and the underlying technical mechanisms.",
        "- Evaluate whether the claimed opportunity is genuinely novel.",
        "- Distinguish demonstrated findings from speculation.",
        "- Identify assumptions, weaknesses and missing evidence.",
        "- Assess relevance to local LLMs, coding agents, recursive self-improvement, evaluation and autonomous workflows where applicable.",
        "- Propose a small, falsifiable experiment.",
        "- Recommend whether to investigate, prototype, defer or reject.",
        "",
    ]
    if identity.get("is_proposed_combination"):
        lines.extend(
            [
                "> **Proposed research combination.** This record was generated by Next "
                "by combining separate source items. Neither source proposes this "
                "combination. It is not an experimentally demonstrated improvement or a "
                "standalone published paper.",
                "",
            ]
        )

    lines.extend(
        [
            "## B. Opportunity identity",
            "",
            _table(
                [
                    ("Title", identity.get("title")),
                    ("Stable opportunity ID", identity.get("opportunity_id")),
                    ("Opportunity type", identity.get("opportunity_type")),
                    ("Queue type", identity.get("queue_type")),
                    ("Status", identity.get("status")),
                    ("Research status", identity.get("research_status")),
                    ("Source application", source.get("application_name")),
                    ("Record provenance", source.get("source_ref")),
                    ("Source version", source.get("source_version")),
                    ("Source mode", source.get("source_mode")),
                    ("Observed at", source.get("observed_at")),
                    ("Source timestamp", source.get("source_timestamp")),
                    ("Freshness", "Stale" if source.get("stale") else "Current observation"),
                    ("Mission Control resource", source.get("resource_id")),
                    ("Project context", identity.get("project_name")),
                ]
            ),
            "",
            f"**Themes recorded by Next:** {', '.join(identity.get('themes') or []) or 'None recorded.'}",
            "",
            f"**Source channels:** {', '.join(identity.get('source_channels') or []) or 'None recorded.'}",
            "",
            "## C. Research description",
            "",
            "### Recorded research summary",
            "",
            description.get("recorded_summary") or "Not recorded.",
            "",
        ]
    )
    if description.get("recorded_description"):
        lines.extend(
            [
                "### Recorded description",
                "",
                description["recorded_description"],
                "",
            ]
        )
    if description.get("what_discovered"):
        lines.extend(
            [
                "### What Next recorded as discovered",
                "",
                description["what_discovered"],
                "",
            ]
        )
    lines.extend(
        [
            "### Next-derived interpretation",
            "",
            "The following fields are Next's interpretation. They are not statements "
            "made by the source authors.",
            "",
            f"- What Next says is new: {interpretation.get('what_is_new') or 'Not recorded.'}",
            f"- Capability hypothesis: {interpretation.get('capability_hypothesis') or 'Not recorded.'}",
            f"- Relation to existing work: {interpretation.get('relation_to_existing') or 'Not recorded.'}",
            f"- Recorded caution: {interpretation.get('why_not') or 'Not recorded.'}",
            "",
            "## D. Sources and evidence",
            "",
        ]
    )
    items = sources.get("items") or []
    if items:
        for index, item in enumerate(items, start=1):
            lines.extend(
                [
                    f"### {index}. {item.get('title')}",
                    "",
                    f"- **Classification:** {item.get('source_kind')}",
                    f"- **Source channel:** {item.get('source')}",
                    f"- **Recorded identifier:** {item.get('id')}",
                    f"- **URL:** {item.get('url') or 'Not recorded by Next. No link was invented.'}",
                ]
            )
            if item.get("recorded_reference") and not item.get("url"):
                lines.append(
                    f"- **Recorded reference:** {item.get('recorded_reference')} "
                    "(treated as an identifier, not a clickable URL)"
                )
            if item.get("description"):
                lines.append(f"- **Description:** {item.get('description')}")
            if item.get("reference_note"):
                lines.append(f"- **Link note:** {item.get('reference_note')}")
            lines.append("")
    else:
        lines.extend(["No source items were recorded for this opportunity.", ""])
    lines.extend(
        [
            "### Supporting evidence",
            "",
            _bullets(list(sources.get("supporting_evidence") or [])),
            "",
        ]
    )
    gaps = sources.get("evidence_gaps") or []
    if gaps:
        lines.extend(["### Recorded evidence gaps", ""])
        for gap in gaps:
            lines.extend(
                [
                    f"- **Verdict:** {gap.get('current_verdict') or 'Not recorded.'}",
                    f"  - Gaps: {'; '.join(str(item) for item in gap.get('gaps') or []) or 'None recorded.'}",
                    f"  - Analyzed at: {gap.get('analyzed_at') or gap.get('source_timestamp') or 'Not recorded.'}",
                ]
            )
        lines.append("")
    else:
        lines.extend(["### Recorded evidence gaps", "", "No evidence-gap analysis was recorded.", ""])
    lines.extend(
        [
            "### Missing evidence",
            "",
            _bullets(list(sources.get("missing_evidence") or [])),
            "",
            f"**Full source content retrieved:** {'Yes' if sources.get('full_source_content_retrieved') else 'No'}. "
            f"{sources.get('note') or ''}",
            "",
            "## E. Evaluation",
            "",
            _table(
                [
                    ("Assessment status", evaluation.get("assessment_status")),
                    ("Evaluation basis", evaluation.get("evaluation_basis")),
                    ("Uncertainty", evaluation.get("uncertainty")),
                ]
            ),
            "",
        ]
    )
    score_rows = evaluation.get("scores") or []
    if score_rows:
        lines.extend(["### Scoring dimensions", "", "| Dimension | Recorded value |", "| --- | --- |"])
        for entry in score_rows:
            lines.append(
                f"| {entry.get('label')} | {_format_value(entry.get('value'))} |"
            )
        lines.append("")
    else:
        lines.extend(["No scoring dimensions were recorded.", ""])
    if evaluation.get("missing_dimensions"):
        lines.extend(
            [
                "**Not recorded:** "
                + ", ".join(evaluation["missing_dimensions"])
                + ". Missing dimensions are not zero-confidence conclusions.",
                "",
            ]
        )
    if evaluation.get("zero_value_caution"):
        lines.extend([f"> {evaluation['zero_value_caution']}", ""])
    lines.extend(
        [
            "### Known limitations",
            "",
            _bullets(list(evaluation.get("known_limitations") or [])),
            "",
            "## F. Experiment and falsification",
            "",
            f"- **Proposed test:** {experiment.get('proposed_test') or 'Not recorded.'}",
            f"- **Success criteria:** {experiment.get('success_criteria') or 'Not recorded by Next.'}",
            f"- **Falsification conditions:** {experiment.get('falsification') or 'Not recorded.'}",
            f"- **Experiment status:** {experiment.get('status') or 'Not recorded.'}",
            "",
        ]
    )
    prior_experiments = experiment.get("prior_experiments") or []
    if prior_experiments:
        lines.extend(["### Prior experiment records", ""])
        for prior in prior_experiments:
            lines.extend(
                [
                    f"- **{prior.get('title')}** ({prior.get('status') or 'status not recorded'})",
                    f"  - Hypothesis: {prior.get('hypothesis') or 'Not recorded.'}",
                    f"  - Baseline: {prior.get('baseline_metric') or 'Not recorded.'}",
                    f"  - Expected: {prior.get('expected_improvement') or 'Not recorded.'}",
                    f"  - Actual result: {prior.get('actual_result') or 'Not recorded.'}",
                ]
            )
        lines.append("")
    else:
        lines.extend(
            [
                "No experiment has been run for this opportunity in the data available "
                "to Mission Control.",
                "",
            ]
        )
    lines.extend(
        [
            "## G. Review questions",
            "",
            "Please answer the following, using only the material above and clearly "
            "marking any general knowledge or inference:",
            "",
        ]
    )
    for index, question in enumerate(package.get("review_questions") or [], start=1):
        lines.append(f"{index}. {question}")
    lines.extend(["", "## Decisions and provenance", ""])
    local = decisions.get("local_decision")
    if local:
        lines.extend(
            [
                "### Mission Control human decision (local only)",
                "",
                f"- Decision: {local.get('decision')}",
                f"- Reason: {local.get('reason') or 'No reason recorded.'}",
                f"- Decided at: {local.get('decided_at')}",
                f"- Sync state: {local.get('sync_state')}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "### Mission Control human decision",
                "",
                "No local human decision has been recorded.",
                "",
            ]
        )
    history = decisions.get("source_decision_history") or []
    if history:
        lines.extend(["### Next's recorded decision history", ""])
        for item in history:
            lines.append(
                f"- {item.get('status') or 'status not recorded'} at "
                f"{item.get('decided_at') or 'time not recorded'} by "
                f"{item.get('decided_by') or 'actor not recorded'}: "
                f"{item.get('reason') or 'No reason recorded.'}"
            )
        lines.append("")
    lines.extend(
        [
            "---",
            "",
            f"- Context fingerprint: `{package.get('fingerprint')}`",
            f"- Generated by Mission Control: {package.get('generated_at')}",
            f"- Source application: {source.get('application_name') or 'Next'} "
            f"({source.get('source_mode') or 'mode not recorded'})",
            f"- Source reference: {source.get('source_ref') or 'not recorded'}",
            "- Boundary: Next's database was read only. Copying this package invoked no model and modified no source state.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_export(
    session: Session, record: IntegrationRecord, *, generated_at: str | None = None
) -> dict[str, Any]:
    package = build_context_package(session, record, generated_at=generated_at)
    return {
        "schema": EXPORT_SCHEMA,
        "fingerprint": package["fingerprint"],
        "markdown": render_export_markdown(package),
        "context": package,
    }
