"""Mission-facing, bounded adapter for Worker's programmable harness.

Mission owns launch authorization and presentation. Worker owns catalogue,
strategy execution, runtime evidence, and the execution ledger. This adapter
does not retain a second copy of Worker execution history.
"""

from __future__ import annotations

import re
from ipaddress import ip_address
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from mission_control import models as orm
from mission_control.api.worker_runtime import _base_url

router = APIRouter(prefix="/api/harness", tags=["harness"])
MAX_TIMEOUT_MS = 60_000
MAX_OUTPUT_TOKENS = 2_048
STRATEGY_IDS = {"direct.v1", "structured.v1", "corrective.v1", "adaptive.v1"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


def _worker_base(request: Request) -> str:
    base = _base_url(request).rstrip("/")
    parsed = urlsplit(base)
    try:
        loopback = parsed.hostname == "localhost" or (parsed.hostname is not None and ip_address(parsed.hostname).is_loopback)
    except ValueError:
        loopback = False
    if parsed.scheme not in ("http", "https") or not loopback or parsed.username or parsed.password:
        raise HTTPException(503, detail="Harness integration permits a loopback Worker URL only")
    return base


class HarnessLaunch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_id: str = Field(min_length=1, max_length=160)
    objective_id: str = Field(min_length=1, max_length=160)
    strategy_id: Literal["direct.v1", "structured.v1", "corrective.v1", "adaptive.v1"]
    model_route: str = Field(min_length=1, max_length=128)
    policy: str = Field(min_length=1, max_length=128)
    normalization_policy: Literal["json-fence.v1"] | None = None
    timeout_ms: int = Field(default=30_000, ge=1, le=MAX_TIMEOUT_MS)
    max_output_tokens: int = Field(default=256, ge=1, le=MAX_OUTPUT_TOKENS)
    actor: str = Field(min_length=2, max_length=80)
    authorization_note: str = Field(min_length=8, max_length=200)
    submission_id: str = Field(min_length=8, max_length=80)
    project_key: str | None = Field(default=None, min_length=1, max_length=200)


async def _get(client: httpx.AsyncClient, base: str, path: str) -> Any:
    try:
        response = await client.get(f"{base}{path}")
    except httpx.TimeoutException as exc:
        raise HTTPException(504, detail="Worker request timed out; state is unknown") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail=f"Worker is unavailable ({type(exc).__name__})") from exc
    if response.status_code != 200:
        if response.status_code == 404:
            raise HTTPException(404, detail="Worker execution or retained artifact was not found")
        raise HTTPException(503, detail=f"Worker returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(502, detail="Worker returned invalid JSON") from exc


def _envelope_service(request: Request):
    service = getattr(request.app.state, "envelope_service", None)
    if service is None:
        raise HTTPException(503, detail="Work Outcome envelope service is unavailable")
    return service


def _canonical_project_key(value: str | None) -> str:
    """Shared basename identity for project comparison (W9 F10 reuse).

    ``Projects/ai`` and ``ai`` share a canonical key; distinct basenames
    never match (no fuzzy association — exact basename equality only).
    """
    return (value or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].strip().lower()


def _correlate_rows(request: Request, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verify Worker-supplied identity against Mission's pre-dispatch envelope."""
    database = getattr(request.app.state, "database", None)
    if database is None:
        return [{**row, "mission_correlation": {"status": "unavailable", "reason": "Mission database is unavailable"}} for row in rows]
    operation_ids = {row.get("operation_id") for row in rows if isinstance(row.get("operation_id"), str)}
    if not operation_ids:
        return [{**row, "mission_correlation": {"status": "unmatched", "reason": "No Mission operation ID"}} for row in rows]
    with database.session() as session:
        envelopes = {item.id: item for item in session.query(orm.WoWorkEnvelope).filter(orm.WoWorkEnvelope.id.in_(operation_ids)).all()}
        episode_ids = {item.episode_id for item in envelopes.values()}
        episodes = {item.id: item for item in session.query(orm.WoEpisode).filter(orm.WoEpisode.id.in_(episode_ids)).all()} if episode_ids else {}
    out: list[dict[str, Any]] = []
    for row in rows:
        envelope = envelopes.get(row.get("operation_id"))
        episode = episodes.get(envelope.episode_id) if envelope else None
        matches = bool(envelope and episode and row.get("episode_id") == envelope.episode_id
                       and row.get("task_id") == envelope.objective_ref)
        correlation: dict[str, Any] = {
            "status": "verified" if matches else "unmatched",
            "source": "mission_work_envelope" if matches else "none",
            "reason": "Worker identity matches Mission-authorized envelope" if matches else "Worker identity could not be matched to a Mission envelope",
        }
        if matches and envelope and episode:
            correlation.update({"envelope_id": envelope.id, "episode_id": envelope.episode_id,
                                "objective_id": envelope.objective_ref, "project_key": episode.project_key})
        out.append({**row, "mission_correlation": correlation})
    return out


@router.get("/catalogue")
async def catalogue(request: Request) -> dict[str, Any]:
    base = _worker_base(request)
    timeout = httpx.Timeout(4.0, connect=1.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        health = await _get(client, base, "/health")
        strategies_doc = await _get(client, base, "/v1/strategies")
        models_doc = await _get(client, base, "/v1/models/catalogue")
    strategies = strategies_doc.get("strategies") if isinstance(strategies_doc, dict) else None
    # Worker exposes configured routes as `approved`; this is a route list,
    # not a claim that model behavior or provider pricing has been qualified.
    models = models_doc.get("approved") if isinstance(models_doc, dict) else None
    policies = models_doc.get("policies") if isinstance(models_doc, dict) else None
    if not isinstance(strategies, list) or not isinstance(models, list) or not isinstance(policies, dict):
        raise HTTPException(502, detail="Worker catalogue contract is incomplete")
    return {
        "schema_version": "mission.harness-catalogue.v1",
        "worker": {"reachable": True, "status": health.get("status", "unknown"), "version": health.get("version", "unknown"), "base_url": base},
        "strategies": [
            {**row, "availability": "available" if row.get("key") in STRATEGY_IDS else "unknown",
             "qualification": "not_asserted_by_catalogue"}
            for row in strategies if isinstance(row, dict)
        ],
        "models": models,
        "policies": policies,
        "limits": {"maximum_execution_seconds": 60, "maximum_output_tokens_per_invocation": MAX_OUTPUT_TOKENS,
                   "maximum_strategy_invocations": 2, "paid_routes": "not offered"},
        "qualification_note": "Catalogue availability does not mean a strategy is qualified for production.",
    }


@router.get("/executions")
async def executions(request: Request, episode_id: str | None = None,
                     strategy_id: str | None = None, project_key: str | None = None,
                     limit: int = 100) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise HTTPException(422, detail="limit must be from 1 to 100")
    base = _worker_base(request)
    timeout = httpx.Timeout(5.0, connect=1.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            payload = await _get(client, base, "/v1/executions")
    except HTTPException as exc:
        if exc.status_code == 404:
            # Worker is reachable but its execution ledger has no readable
            # window (ledger not configured on this Worker process). This is
            # NOT zero executions: report unavailability explicitly so the
            # UI never renders it as an empty history.
            return {"schema_version": "mission.harness-executions.v1", "executions": [],
                    "coverage": {"source": "worker_h3_execution_ledger", "read_window": 0,
                                 "truncated": False, "unavailable_is_not_zero": True,
                                 "ledger": {"available": False, "worker_http_status": 404,
                                            "reason": "Worker execution ledger has no readable window on this Worker process"}},
                    "worker": {"reachable": True, "ledger": "unavailable"}}
        raise
    rows = payload.get("executions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(502, detail="Worker execution ledger contract is incomplete")
    rows = _correlate_rows(request, [row for row in rows if isinstance(row, dict)])
    if project_key:
        database = getattr(request.app.state, "database", None)
        if database is None:
            raise HTTPException(503, detail="Project registry is unavailable")
        with database.session() as session:
            known = {p.id for p in session.query(orm.Project).all()}
        if project_key not in known and _canonical_project_key(project_key) not in {
                _canonical_project_key(k) for k in known}:
            raise HTTPException(404, detail=f"Unknown project '{project_key}': no such project in the Mission registry")
        wanted = _canonical_project_key(project_key)
        rows = [row for row in rows
                if row.get("mission_correlation", {}).get("status") == "verified"
                and _canonical_project_key(row.get("mission_correlation", {}).get("project_key")) == wanted]
    if episode_id:
        rows = [row for row in rows if row.get("mission_correlation", {}).get("status") == "verified"
                and row.get("mission_correlation", {}).get("episode_id") == episode_id]
    if strategy_id:
        rows = [row for row in rows if ((row.get("strategy_execution") or {}).get("strategy") or {}).get("key") == strategy_id]
    return {"schema_version": "mission.harness-executions.v1", "executions": rows[-limit:],
            "coverage": {"source": "worker_h3_execution_ledger", "read_window": len(payload.get("executions", [])),
                         "truncated": bool(payload.get("more_in_read_window")), "unavailable_is_not_zero": False,
                         "ledger": {"available": True}},
            "worker": {"reachable": True, "ledger": "readable"}}


@router.get("/executions/{request_id}")
async def execution_detail(request: Request, request_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"^wrq_[a-fA-F0-9]{16,64}$", request_id):
        raise HTTPException(422, detail="Invalid Worker request id")
    base = _worker_base(request)
    timeout = httpx.Timeout(5.0, connect=1.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        summary = await _get(client, base, f"/v1/executions/{request_id}")
    if not isinstance(summary, dict):
        raise HTTPException(502, detail="Worker execution detail contract is incomplete")
    return _correlate_rows(request, [summary])[0]


@router.get("/jobs")
async def jobs(request: Request) -> dict[str, Any]:
    """Observe active Worker jobs; no cancellation capability is implied."""
    base = _worker_base(request)
    timeout = httpx.Timeout(4.0, connect=1.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        payload = await _get(client, base, "/v1/jobs")
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise HTTPException(502, detail="Worker job observation contract is incomplete")
    safe_jobs = []
    for row in payload["jobs"][:100]:
        if not isinstance(row, dict):
            continue
        safe_jobs.append({"job_id": row.get("job_id"), "operation_id": row.get("operation_id"),
                          "stage_id": row.get("stage_id"), "status": row.get("status"),
                          "started_at": row.get("started_at"), "completed_at": row.get("completed_at"),
                          "events": [{"type": event.get("type"), "timestamp": event.get("timestamp")}
                                     for event in row.get("events", []) if isinstance(event, dict)]})
    return {"schema_version": "mission.harness-jobs.v1", "jobs": safe_jobs,
            "cancellation": "unsupported_by_this_Worker_interface"}


@router.get("/executions/{request_id}/artifacts")
async def execution_artifacts(request: Request, request_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"^wrq_[a-fA-F0-9]{16,64}$", request_id):
        raise HTTPException(422, detail="Invalid Worker request id")
    base = _worker_base(request)
    timeout = httpx.Timeout(5.0, connect=1.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        summary = await _get(client, base, f"/v1/executions/{request_id}")
        jobs_doc = await _get(client, base, "/v1/jobs")
    if not isinstance(summary, dict):
        raise HTTPException(502, detail="Worker execution detail contract is incomplete")
    summary = _correlate_rows(request, [summary])[0]
    job_rows = jobs_doc.get("jobs") if isinstance(jobs_doc, dict) else None
    if not isinstance(summary, dict) or not isinstance(job_rows, list):
        raise HTTPException(502, detail="Worker artifact sources have an invalid shape")
    matching = next((row for row in job_rows if isinstance(row, dict) and isinstance(row.get("result"), dict)
                     and row["result"].get("request_id") == request_id), None)
    if matching is None:
        return {"request_id": request_id, "available": False,
                "reason": "raw result is not retained by the current Worker process; H3 summary remains available",
                "summary": summary}
    result = matching["result"]
    strategy = result.get("strategy_execution") if isinstance(result.get("strategy_execution"), dict) else {}
    invocations = strategy.get("invocations") if isinstance(strategy.get("invocations"), list) else []
    safe_strategy = {key: value for key, value in strategy.items() if key != "invocations"}
    safe_strategy["invocations"] = [
        {key: value for key, value in row.items() if key in {"invocation_id", "parent_request_id", "ordinal", "purpose", "status", "requested_route", "observed_model", "started_at", "completed_at", "latency_ms", "output_digest", "output", "usage", "cost", "failure"}}
        for row in invocations if isinstance(row, dict)
    ]
    return {"request_id": request_id, "available": True, "summary": summary,
            "output": result.get("output"), "strategy_execution": safe_strategy,
            "artifact_retention": "Worker process memory; may be unavailable after Worker restart"}


@router.post("/executions")
async def launch(payload: HarnessLaunch, request: Request) -> dict[str, Any]:
    if not IDENTIFIER.fullmatch(payload.episode_id) or not IDENTIFIER.fullmatch(payload.objective_id):
        raise HTTPException(422, detail="Episode and objective must be opaque identifiers")
    if payload.strategy_id == "adaptive.v1" and payload.normalization_policy != "json-fence.v1":
        raise HTTPException(422, detail="adaptive.v1 requires json-fence.v1")
    if payload.strategy_id != "adaptive.v1" and payload.normalization_policy is not None:
        raise HTTPException(422, detail="Normalization is only supported by adaptive.v1")
    # Resolve both identities from the existing Work Outcome authority before
    # authorizing execution. Never accept caller-supplied objective text.
    episode_service = getattr(request.app.state, "episode_service", None)
    intent_service = getattr(request.app.state, "intent_service", None)
    if episode_service is None or intent_service is None:
        raise HTTPException(503, detail="Work Outcome identity services are unavailable")
    episode = episode_service.get_episode(payload.episode_id)
    objectives = intent_service.list_objectives(episode_id=payload.episode_id, limit=500)
    objective = next((row for row in objectives if row.get("id") == payload.objective_id), None)
    if (episode is None or episode.get("status") == "superseded" or objective is None
            or objective.get("status") != "current" or not isinstance(objective.get("text"), str)
            or not objective["text"].strip()):
        raise HTTPException(422, detail="Selected objective is not verified as part of the selected episode")
    if payload.project_key is not None and episode.get("project_key") != payload.project_key:
        raise HTTPException(422, detail="Selected episode is outside the requested project scope")

    base = _worker_base(request)
    timeout = httpx.Timeout(5.0, connect=1.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        strategies_doc = await _get(client, base, "/v1/strategies")
        models_doc = await _get(client, base, "/v1/models/catalogue")
        strategies = strategies_doc.get("strategies", []) if isinstance(strategies_doc, dict) else []
        models = models_doc.get("approved", []) if isinstance(models_doc, dict) else []
        policies = models_doc.get("policies", {}) if isinstance(models_doc, dict) else {}
        strategy = next((row for row in strategies if isinstance(row, dict) and row.get("key") == payload.strategy_id), None)
        route = next((row for row in models if isinstance(row, dict) and row.get("id") == payload.model_route), None)
        policy = policies.get(payload.policy) if isinstance(policies, dict) else None
        if strategy is None:
            raise HTTPException(422, detail="Strategy is not present in the current Worker catalogue")
        if not isinstance(route, dict) or route.get("economic_tier") != "free" or route.get("data_policy") != "local_only":
            raise HTTPException(422, detail="H6 launcher permits only configured free local-only model routes")
        if not isinstance(policy, dict) or payload.model_route not in policy.get("routes", []) or policy.get("required_data_policy") != "local_only":
            raise HTTPException(422, detail="Selected policy does not authorize this local-only route")
        if not isinstance(policy.get("attempts_per_route"), int) or policy["attempts_per_route"] < 1 or policy["attempts_per_route"] > 2:
            raise HTTPException(422, detail="Selected policy exceeds the H6 two-attempt bound")

        # Existing Work Envelope is the pre-execution authorization record and
        # its digest makes retries with the same submission ID idempotent.
        envelope = _envelope_service(request).register_envelope(
            episode_id=payload.episode_id, objective_id=payload.objective_id,
            scope=f"worker-harness:{payload.submission_id}:{payload.strategy_id}:{payload.model_route}:{payload.policy}",
            acceptance_criteria=f"User-confirmed bounded Worker execution {payload.submission_id}",
            acceptance_policy_ref="h6-human-review.v1", programme_id="HARNESS-EVOLUTION-01",
            stage_id="H6", actor=payload.actor, authorization_note=payload.authorization_note,
        )
        if envelope.get("status") == "duplicate":
            raise HTTPException(409, detail={"code": "DUPLICATE_SUBMISSION", "envelope_id": envelope.get("envelope_id"),
                                               "message": "This submission ID was already authorized; no second Worker request was sent."})
        if envelope.get("status") != "completed":
            raise HTTPException(422, detail=envelope.get("error", "Work Envelope authorization failed"))

        worker_request = {
            "schema": "worker.work-request.v1", "task_id": payload.objective_id,
            "episode_id": payload.episode_id, "objective": objective["text"],
            "execution": {"backend": "model", "model": payload.model_route, "policy": payload.policy,
                          "strategy_id": payload.strategy_id,
                          **({"normalization_policy": payload.normalization_policy} if payload.normalization_policy else {})},
            "parameters": {"timeout_ms": payload.timeout_ms, "max_output_tokens": payload.max_output_tokens,
                           "data_policy": "local_only", "output_schema": {"type": "object", "additionalProperties": True}},
            "options": {"acceptance": "human"},
            "metadata": {"operation_id": envelope.get("envelope_id")},
        }
        try:
            response = await client.post(f"{base}/v1/work", json=worker_request,
                                         timeout=httpx.Timeout(payload.timeout_ms / 1000 + 5, connect=1.0))
        except httpx.TimeoutException as exc:
            raise HTTPException(504, detail={"code": "WORKER_OUTCOME_UNKNOWN", "envelope_id": envelope.get("envelope_id"),
                                                "message": "Worker timed out; request may have reached execution. Do not retry under a new submission ID."}) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(503, detail={"code": "WORKER_UNAVAILABLE", "envelope_id": envelope.get("envelope_id"),
                                                "message": f"Worker transport failed ({type(exc).__name__}); outcome unknown."}) from exc
        if response.status_code != 200:
            raise HTTPException(502, detail={"code": "WORKER_HTTP_ERROR", "envelope_id": envelope.get("envelope_id"),
                                              "message": f"Worker returned HTTP {response.status_code}; inspect Worker evidence before retry."})
        try:
            result = response.json()
        except ValueError as exc:
            raise HTTPException(502, detail={"code": "WORKER_PROTOCOL_ERROR", "envelope_id": envelope.get("envelope_id"),
                                              "message": "Worker returned invalid JSON; outcome cannot be inferred."}) from exc
        if not isinstance(result, dict):
            raise HTTPException(502, detail={"code": "WORKER_PROTOCOL_ERROR", "envelope_id": envelope.get("envelope_id"),
                                              "message": "Worker response was not an object."})
    return {"schema_version": "mission.harness-launch.v1", "authorization": envelope,
            "correlation": {"episode_id": payload.episode_id, "objective_id": payload.objective_id,
                            "linkage": "mission-work-envelope-correlated; Worker episode fields remain caller-supplied"},
            "worker_result": result,
            "acceptance": "separate_from_execution_and_evaluation; no automatic acceptance"}
