"""Next research integration.

Preferred source: a read-only PostgreSQL session over Next's documented
research store. The Next web dashboard exposes no JSON resource API, and its
ResearchStore performs schema migrations on construction, so Mission Control
uses SELECT-only queries and never invokes that constructor. A read-only local
SQLite snapshot remains as an explicit fallback.

The missing source contract is recorded in docs/MC09-INTEGRATION-AUDIT.md:
Next should expose a versioned read-only JSON export. Until then this adapter is
marked as a read-only database compatibility integration, not a stable public
API.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from mission_control.adapters.base import (
    ActionSpec,
    Adapter,
    AdapterResult,
    AdapterTarget,
    Observation,
    ResourceSeed,
)

_RESOURCE_FIELDS = [
    "id",
    "run_id",
    "title",
    "description",
    "mode",
    "themes",
    "sources",
    "item_ids",
    "what_discovered",
    "evidence",
    "what_is_new",
    "capability_unlocked",
    "relation_to_existing",
    "combinable_with",
    "simplest_experiment",
    "falsification",
    "cost_estimate",
    "why_not",
    "capability_gain",
    "feasibility",
    "cost_efficiency",
    "evidence_strength",
    "novelty",
    "score",
    "uncertainty",
    "evaluation_basis",
    "rank",
    "status",
    "decision_reason",
    "decided_at",
    "decided_by",
    "created_at",
    "queue_type",
    "research_status",
    "overall_confidence",
]


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row)


class NextAdapter(Adapter):
    name = "next"
    capabilities = [
        "health",
        "list_resources",
        "get_resource",
        "search_resources",
        "list_actions",
        "list_events",
    ]
    actions = [
        ActionSpec(
            id="run_discovery",
            title="Run Next discovery",
            description=(
                "Next discovery fetches external sources, may call models, and writes "
                "to Next's authoritative store. It is not enabled without a dedicated "
                "approved Next operation contract."
            ),
            risk="external_network",
            capability="execute_action",
            approval_required=True,
            side_effect="external_communication",
            enabled=False,
            unavailable_reason=(
                "Blocked by design: no reviewed Next operation contract. Use Next's own "
                "interface for discovery until a bounded export/run contract is approved."
            ),
        )
    ]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        repo = target.repo_by_name("next") or target.primary_repository
        if repo is None:
            return AdapterResult(
                available=False,
                detail="Next repository is unavailable.",
                capabilities=self.capabilities,
                actions=self.actions,
            )
        dsn_env = str(target.config.get("dsn_env") or "NEXT_DSN")
        dsn = os.environ.get(dsn_env)
        limit = max(1, min(int(target.config.get("limit", 200)), 500))
        try:
            if dsn:
                resources, mode, counts = self._read_postgres(dsn, limit)
            else:
                sqlite_path = Path(
                    target.config.get("sqlite_path")
                    or target.config.get("database_path")
                    or (repo / "data" / "next.db")
                )
                resources, mode, counts = self._read_sqlite(sqlite_path, limit)
        except Exception as exc:
            return AdapterResult(
                available=False,
                detail=(
                    "Next live read failed. Mission Control did not write to Next and "
                    "did not fall back to invented data."
                ),
                capabilities=self.capabilities,
                actions=self.actions,
                error=f"{exc.__class__.__name__}: {str(exc)[:400]}",
            )
        latest_run = next((item for item in resources if item.resource_type == "next_run"), None)
        detail = (
            f"Read {counts['opportunities']} opportunities, {counts['runs']} runs, "
            f"{counts['gaps']} evidence-gap records and {counts['experiments']} experiments "
            f"from Next {mode}. PostgreSQL reads use a read-only transaction. "
            "This is a database compatibility integration, not a stable Next API."
        )
        observations: list[Observation] = []
        if latest_run:
            observations.append(
                Observation(
                    title=f"Next research store: {counts['opportunities']} opportunities",
                    detail=detail,
                    external_id=f"next-store-{counts['opportunities']}-{counts['runs']}",
                    evidence_ref=latest_run.data.get("source_ref"),
                    provenance="external_claim",
                    metadata={"mode": mode, **counts},
                )
            )
        return AdapterResult(
            available=True,
            detail=detail,
            capabilities=self.capabilities,
            observations=observations,
            resources=resources,
        )

    # ------------------------------------------------------------------ read
    def _read_postgres(self, dsn: str, limit: int) -> tuple[list[ResourceSeed], str, dict[str, int]]:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(
            dsn,
            options="-c default_transaction_read_only=on",
            connect_timeout=6,
        ) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"SELECT {', '.join(_RESOURCE_FIELDS)} FROM opportunities "
                    "ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                opportunities = [dict(row) for row in cursor.fetchall()]
                cursor.execute(
                    "SELECT id, started_at, completed_at, status, items_retrieved, items_new, "
                    "candidates, recommendations, sources_queried, sources_failed "
                    "FROM discovery_runs ORDER BY started_at DESC LIMIT 20"
                )
                runs = [dict(row) for row in cursor.fetchall()]
                cursor.execute(
                    "SELECT opportunity_id, opportunity_title, current_verdict, gaps_json, analyzed_at "
                    "FROM evidence_gaps ORDER BY analyzed_at DESC LIMIT 50"
                )
                gaps = [dict(row) for row in cursor.fetchall()]
                cursor.execute(
                    "SELECT id, opportunity_id, hypothesis, baseline_metric, expected_improvement, "
                    "actual_result, status, cost_usd, created_at FROM experiments "
                    "ORDER BY created_at DESC LIMIT 50"
                )
                experiments = [dict(row) for row in cursor.fetchall()]
                opp_ids = [item["id"] for item in opportunities]
                decisions: list[dict[str, Any]] = []
                if opp_ids:
                    cursor.execute(
                        "SELECT opportunity_id, status, reason, decided_by, decided_at "
                        "FROM decisions WHERE opportunity_id = ANY(%s) "
                        "ORDER BY decided_at ASC",
                        (opp_ids,),
                    )
                    decisions = [dict(row) for row in cursor.fetchall()]
                item_ids = sorted(
                    {
                        item_id
                        for opp in opportunities
                        for item_id in _json_list(opp.get("item_ids"))
                        if isinstance(item_id, str)
                    }
                )
                items: list[dict[str, Any]] = []
                if item_ids:
                    cursor.execute(
                        "SELECT id, title, url, source, published_at FROM items "
                        "WHERE id = ANY(%s) LIMIT 500",
                        (item_ids,),
                    )
                    items = [dict(row) for row in cursor.fetchall()]
        return self._build_resources(
            opportunities,
            runs,
            gaps,
            experiments,
            decisions,
            items,
            source_mode="postgres-readonly",
            source_ref="next-postgres:opportunities",
        )

    def _read_sqlite(
        self, path: Path, limit: int
    ) -> tuple[list[ResourceSeed], str, dict[str, int]]:
        if not path.exists():
            raise FileNotFoundError(f"Next SQLite snapshot not found: {path}")
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=3)
        connection.row_factory = sqlite3.Row
        try:
            def fetch(sql: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
                return [dict(row) for row in connection.execute(sql, parameters).fetchall()]

            opportunities = fetch(
                f"SELECT {', '.join(_RESOURCE_FIELDS)} FROM opportunities "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            runs = fetch(
                "SELECT id, started_at, completed_at, status, items_retrieved, items_new, "
                "candidates, recommendations, sources_queried, sources_failed "
                "FROM discovery_runs ORDER BY started_at DESC LIMIT 20"
            )
            gaps = fetch(
                "SELECT opportunity_id, opportunity_title, current_verdict, gaps_json, analyzed_at "
                "FROM evidence_gaps ORDER BY analyzed_at DESC LIMIT 50"
            )
            experiments = fetch(
                "SELECT id, opportunity_id, hypothesis, baseline_metric, expected_improvement, "
                "actual_result, status, cost_usd, created_at FROM experiments "
                "ORDER BY created_at DESC LIMIT 50"
            )
            opp_ids = [item["id"] for item in opportunities]
            decisions: list[dict[str, Any]] = []
            if opp_ids:
                placeholders = ",".join("?" for _ in opp_ids)
                decisions = fetch(
                    f"SELECT opportunity_id, status, reason, decided_by, decided_at "
                    f"FROM decisions WHERE opportunity_id IN ({placeholders}) "
                    "ORDER BY decided_at ASC",
                    tuple(opp_ids),
                )
            item_ids = sorted(
                {
                    item_id
                    for opp in opportunities
                    for item_id in _json_list(opp.get("item_ids"))
                    if isinstance(item_id, str)
                }
            )
            items: list[dict[str, Any]] = []
            if item_ids:
                placeholders = ",".join("?" for _ in item_ids[:500])
                items = fetch(
                    f"SELECT id, title, url, source, published_at FROM items "
                    f"WHERE id IN ({placeholders}) LIMIT 500",
                    tuple(item_ids[:500]),
                )
        finally:
            connection.close()
        return self._build_resources(
            opportunities,
            runs,
            gaps,
            experiments,
            decisions,
            items,
            source_mode="sqlite-snapshot",
            source_ref=str(path),
        )

    def _build_resources(
        self,
        opportunities: list[dict[str, Any]],
        runs: list[dict[str, Any]],
        gaps: list[dict[str, Any]],
        experiments: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        items: list[dict[str, Any]],
        *,
        source_mode: str,
        source_ref: str,
    ) -> tuple[list[ResourceSeed], str, dict[str, int]]:
        items_by_id = {item["id"]: item for item in items}
        decisions_by_opp: dict[str, list[dict[str, Any]]] = {}
        for decision in decisions:
            decisions_by_opp.setdefault(str(decision["opportunity_id"]), []).append(decision)
        resources: list[ResourceSeed] = []
        for opp in opportunities:
            opp_id = str(opp["id"])
            source_items = [
                {
                    "id": item_id,
                    "title": items_by_id.get(item_id, {}).get("title"),
                    "url": items_by_id.get(item_id, {}).get("url"),
                    "source": items_by_id.get(item_id, {}).get("source"),
                }
                for item_id in _json_list(opp.get("item_ids"))
                if item_id in items_by_id
            ]
            history = [
                {
                    "status": row.get("status"),
                    "reason": row.get("reason"),
                    "decided_by": row.get("decided_by"),
                    "decided_at": row.get("decided_at"),
                }
                for row in decisions_by_opp.get(opp_id, [])
            ]
            summary = str(opp.get("what_discovered") or opp.get("description") or "")[:1200]
            evidence = [
                value
                for value in [opp.get("evidence"), opp.get("what_is_new")]
                if isinstance(value, str) and value.strip()
            ]
            data = {
                "source_mode": source_mode,
                "source_ref": source_ref,
                "queue_type": opp.get("queue_type"),
                "mode": opp.get("mode"),
                "themes": _json_list(opp.get("themes")),
                "sources": _json_list(opp.get("sources")),
                "description": opp.get("description"),
                "what_discovered": opp.get("what_discovered"),
                "what_is_new": opp.get("what_is_new"),
                "capability_unlocked": opp.get("capability_unlocked"),
                "relation_to_existing": opp.get("relation_to_existing"),
                "simplest_experiment": opp.get("simplest_experiment"),
                "falsification": opp.get("falsification"),
                "cost_estimate": opp.get("cost_estimate"),
                "why_not": opp.get("why_not"),
                "evaluation_basis": opp.get("evaluation_basis"),
                "scores": {
                    key: opp.get(key)
                    for key in (
                        "score",
                        "capability_gain",
                        "feasibility",
                        "cost_efficiency",
                        "evidence_strength",
                        "novelty",
                        "uncertainty",
                        "overall_confidence",
                    )
                },
                "research_status": opp.get("research_status"),
                "decision_reason": opp.get("decision_reason"),
                "decided_at": opp.get("decided_at"),
                "decided_by": opp.get("decided_by"),
                "source_decision_history": history[-10:],
                "items": source_items[:10],
            }
            resources.append(
                ResourceSeed(
                    resource_type="next_opportunity",
                    external_id=opp_id,
                    title=str(opp.get("title") or "Untitled Next opportunity")[:300],
                    summary=summary,
                    state=str(opp.get("status") or "NEW"),
                    evidence=evidence[:10],
                    data=data,
                    source_version=f"next-{source_mode}-v1",
                    source_timestamp=str(opp.get("created_at") or "") or None,
                    stale_after_seconds=900,
                )
            )
        for run in runs:
            run_id = str(run["id"])
            resources.append(
                ResourceSeed(
                    resource_type="next_run",
                    external_id=run_id,
                    title=f"Next run {run_id[:12]} — {run.get('status') or 'unknown'}",
                    summary=(
                        f"{run.get('items_retrieved') or 0} items retrieved; "
                        f"{run.get('items_new') or 0} new; "
                        f"{run.get('candidates') or 0} candidates; "
                        f"{run.get('recommendations') or 0} recommendations."
                    ),
                    state=str(run.get("status") or ""),
                    evidence=[source_ref],
                    data={
                        "source_mode": source_mode,
                        "started_at": run.get("started_at"),
                        "completed_at": run.get("completed_at"),
                        "items_retrieved": run.get("items_retrieved"),
                        "items_new": run.get("items_new"),
                        "candidates": run.get("candidates"),
                        "recommendations": run.get("recommendations"),
                        "sources_queried": run.get("sources_queried"),
                        "sources_failed": run.get("sources_failed"),
                        "source_ref": source_ref,
                    },
                    source_version=f"next-{source_mode}-v1",
                    source_timestamp=str(run.get("completed_at") or run.get("started_at") or "") or None,
                    stale_after_seconds=3600,
                )
            )
        for gap in gaps:
            opp_id = str(gap.get("opportunity_id") or "")
            gaps_value = _json_list(gap.get("gaps_json"))
            resources.append(
                ResourceSeed(
                    resource_type="next_evidence_gap",
                    external_id=f"gap-{opp_id}",
                    title=f"Evidence gaps: {gap.get('opportunity_title') or opp_id[:12]}",
                    summary=str(gap.get("current_verdict") or "")[:1200],
                    state=str(gap.get("current_verdict") or ""),
                    evidence=[source_ref],
                    data={
                        "source_mode": source_mode,
                        "opportunity_id": opp_id,
                        "opportunity_title": gap.get("opportunity_title"),
                        "current_verdict": gap.get("current_verdict"),
                        "gaps": gaps_value[:20],
                        "analyzed_at": gap.get("analyzed_at"),
                        "source_ref": source_ref,
                    },
                    source_version=f"next-{source_mode}-v1",
                    source_timestamp=str(gap.get("analyzed_at") or "") or None,
                    stale_after_seconds=3600,
                )
            )
        for experiment in experiments:
            experiment_id = str(experiment.get("id") or "")
            resources.append(
                ResourceSeed(
                    resource_type="next_experiment",
                    external_id=experiment_id,
                    title=f"Next experiment: {str(experiment.get('hypothesis') or 'untitled')[:220]}",
                    summary=str(experiment.get("actual_result") or experiment.get("expected_improvement") or "")[:1200],
                    state=str(experiment.get("status") or ""),
                    evidence=[source_ref],
                    data={
                        "source_mode": source_mode,
                        "opportunity_id": experiment.get("opportunity_id"),
                        "hypothesis": experiment.get("hypothesis"),
                        "baseline_metric": experiment.get("baseline_metric"),
                        "expected_improvement": experiment.get("expected_improvement"),
                        "actual_result": experiment.get("actual_result"),
                        "cost_usd": experiment.get("cost_usd"),
                        "created_at": experiment.get("created_at"),
                        "source_ref": source_ref,
                    },
                    source_version=f"next-{source_mode}-v1",
                    source_timestamp=str(experiment.get("created_at") or "") or None,
                    stale_after_seconds=3600,
                )
            )
        return resources, source_mode, {
            "opportunities": len(opportunities),
            "runs": len(runs),
            "gaps": len(gaps),
            "experiments": len(experiments),
        }
