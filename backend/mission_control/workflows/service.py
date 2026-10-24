"""Durable, evidence-preserving cross-application experiments.

The first template is a bounded TraceLite proxy spike derived from a real Next
candidate. It uses Worker's supported HTTP interface with a local Ollama model,
applies only the approved file scope, measures deterministic tests, asks CoCoder
to review the resulting commit, and records a human decision.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.config import RuntimeSettings
from mission_control.core.errors import Conflict, NotFound, ValidationProblem
from mission_control.integrations.service import IntegrationService
from mission_control.models import (
    Application,
    Decision,
    ExperimentWorkflow,
    IntegrationRecord,
    LanguageObservation,
    Project,
    WorkflowEvent,
)
from mission_control.persistence.db import Database, now_iso
from mission_control.schemas import (
    ExperimentWorkflowRead,
    LanguageObservationRead,
    WorkflowEventRead,
)
from mission_control.workflows.sandbox import (
    DockerSandboxRunner,
    SandboxRunner,
    SandboxUnavailable,
)
from mission_control.workflows.templates import TemplateSpec, get_template

TRACE_TEMPLATE = "trace_reduce_v1"
EXPORT_SCHEMA = "next-research-export-v1"
PATCH_SCHEMA = "mc10.patch.v1"
DEFAULT_WORKER_URL = "http://127.0.0.1:7317"
DEFAULT_WORKER_MODEL = "qwen2.5-coder:latest"
DEFAULT_WORKER_BACKEND = "direct"
FORBIDDEN_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "memoryview",
    "open",
    "setattr",
    "vars",
}


class WorkerClient(Protocol):
    async def run(self, request: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        ...


class HttpWorkerClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def run(self, request: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=timeout_seconds, trust_env=False
        ) as client:
            response = await client.post(f"{self.base_url}/v1/work", json=request)
        if response.status_code != 200:
            raise ValueError(
                f"Worker returned HTTP {response.status_code}: {response.text[:1000]}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Worker response was not a JSON object")
        return payload


class WorkflowService:
    def __init__(
        self,
        database: Database,
        settings: RuntimeSettings,
        integration_service: IntegrationService,
        *,
        worker_client: WorkerClient | None = None,
        sandbox_runner: SandboxRunner | None = None,
    ) -> None:
        self.database = database
        self.settings = settings
        self.integration_service = integration_service
        self.worker_client = worker_client
        self.sandbox = sandbox_runner or DockerSandboxRunner()
        self._active_workflows: set[str] = set()

    # --------------------------------------------------------------- creation
    def create(
        self,
        record_id: str | None,
        template: str = TRACE_TEMPLATE,
        project_id: str | None = None,
        *,
        force_new: bool = False,
    ) -> ExperimentWorkflowRead:
        try:
            spec = get_template(template)
        except ValueError as exc:
            raise ValidationProblem(str(exc)) from exc
        with self.database.session() as session:
            source = self._source_for_create(session, spec, record_id)
            repository = self._sandbox_path(spec)
            self._require_repository(repository)
            baseline_commit = self._prepare_baseline(
                repository, spec, force_new=force_new
            )
            baseline_hash = self._scope_hash(repository, spec.scope)
            proposal = self._proposal(
                spec=spec,
                source=source,
                repository=repository,
                baseline_commit=baseline_commit,
                baseline_hash=baseline_hash,
                project_id=project_id,
            )
            idempotency_key = self._idempotency_key(source["source_id"], template)
            if force_new:
                idempotency_key = f"{idempotency_key}#retry-{uuid.uuid4().hex[:12]}"
            else:
                existing = session.scalar(
                    select(ExperimentWorkflow)
                    .where(
                        ExperimentWorkflow.next_external_id == source["source_id"],
                        ExperimentWorkflow.template == template,
                    )
                    .order_by(desc(ExperimentWorkflow.created_at))
                    .limit(1)
                )
                if existing is not None:
                    return self._read(session, existing)
            workflow = ExperimentWorkflow(
                id=f"wf-{uuid.uuid4().hex[:16]}",
                title=f"{spec.title}: {source['title'][:220]}",
                template=template,
                status="proposed",
                next_record_id=source["record_id"],
                next_external_id=source["source_id"],
                next_title=source["title"],
                project_id=project_id or source["project_id"],
                next_evidence=source["evidence"],
                proposal=proposal,
                language_intention=self._language_intention(proposal),
                repository_path=str(repository),
                baseline_commit=baseline_commit,
                approved_scope=[],
                worker_result={},
                patch={},
                measurement={},
                review_summary={},
                adverse_review=False,
                final_reason="",
                override_adverse=False,
                idempotency_key=idempotency_key,
                created_at=now_iso(),
                updated_at=now_iso(),
            )
            session.add(workflow)
            session.flush()
            self._event(
                session,
                workflow,
                "research_imported",
                source["source_kind"],
                f"Imported {source['source_id']} from {spec.source_contract}.",
                {
                    "schema": source["evidence"].get("schema"),
                    "generated_at": source["evidence"].get("generated_at"),
                    "export_path": source["evidence"].get("export_path"),
                    "source_kind": source["source_kind"],
                },
                source_ref=source["evidence"].get("export_path"),
            )
            self._event(
                session,
                workflow,
                "proposal_created",
                "mission-control",
                "Created a bounded experiment proposal for human approval.",
                proposal,
            )
            self._event(
                session,
                workflow,
                "baseline_observed",
                "sandbox",
                "Observed the baseline tests and measurement.",
                proposal.get("baseline", {}),
            )
            return self._read(session, workflow)

    # --------------------------------------------------------------- approval
    def approve(
        self,
        workflow_id: str,
        *,
        confirm: bool,
        approved_by: str,
        scope_acknowledged: bool,
    ) -> ExperimentWorkflowRead:
        if not confirm or not scope_acknowledged:
            raise Conflict(
                "Approval requires explicit confirmation and acknowledgement of the file scope"
            )
        with self.database.session() as session:
            workflow = self._require(session, workflow_id)
            if workflow.status == "approved" and workflow.approval_hash:
                return self._read(session, workflow)
            if workflow.status != "proposed":
                raise Conflict(f"Workflow cannot be approved from status {workflow.status}")
            self._assert_approval_inputs_current(workflow)
            approval_hash = self._approval_hash(workflow)
            workflow.approved_scope = list(workflow.proposal.get("scope") or [])
            workflow.approval_hash = approval_hash
            workflow.approved_at = now_iso()
            workflow.approved_by = approved_by[:120] or "user"
            workflow.status = "approved"
            workflow.updated_at = now_iso()
            self._event(
                session,
                workflow,
                "approved",
                "user",
                f"Approved by {workflow.approved_by} for scope {', '.join(workflow.approved_scope)}.",
                {
                    "approval_hash": approval_hash,
                    "scope": workflow.approved_scope,
                    "approved_by": workflow.approved_by,
                },
            )
            return self._read(session, workflow)

    # -------------------------------------------------------------- execution
    async def execute(
        self, workflow_id: str, *, confirm: bool
    ) -> ExperimentWorkflowRead:
        if workflow_id in self._active_workflows:
            raise Conflict("This workflow is already executing or reviewing")
        self._active_workflows.add(workflow_id)
        try:
            return await self._execute_impl(workflow_id, confirm=confirm)
        finally:
            self._active_workflows.discard(workflow_id)

    def cancel(self, workflow_id: str, reason: str = "") -> ExperimentWorkflowRead:
        with self.database.session() as session:
            workflow = self._require(session, workflow_id)
            if workflow.status == "cancelled":
                return self._read(session, workflow)
            if workflow.final_decision is not None:
                raise Conflict("A decided workflow cannot be cancelled")
            if workflow.status in {"proposed", "approved"}:
                workflow.cancel_requested = True
                workflow.cancelled_at = now_iso()
                workflow.status = "cancelled"
                workflow.updated_at = now_iso()
                self._event(
                    session,
                    workflow,
                    "cancelled",
                    "user",
                    "Workflow cancelled before execution.",
                    {"reason": reason[:1000]},
                )
                return self._read(session, workflow)
            if workflow.status in {"executing", "reviewing"}:
                workflow.cancel_requested = True
                workflow.updated_at = now_iso()
                self._event(
                    session,
                    workflow,
                    "cancellation_requested",
                    "user",
                    "Cancellation requested; it will be observed at the next safe boundary.",
                    {"reason": reason[:1000]},
                )
                return self._read(session, workflow)
            raise Conflict(f"Workflow cannot be cancelled from status {workflow.status}")

    async def _execute_impl(
        self, workflow_id: str, *, confirm: bool
    ) -> ExperimentWorkflowRead:
        if not confirm:
            raise Conflict("Execution requires explicit confirmation")
        with self.database.session() as session:
            workflow = self._require(session, workflow_id)
            if workflow.worker_request_id and workflow.status in {
                "executed",
                "reviewing",
                "reviewed",
                "review_failed",
                "decided",
            }:
                return self._read(session, workflow)
            if workflow.cancel_requested:
                return self._mark_cancelled(session, workflow, "Cancelled before execution")
            if workflow.status != "approved":
                raise Conflict(f"Workflow cannot execute from status {workflow.status}")
            self._assert_approval_current(workflow)
            self._assert_approval_inputs_current(workflow)
            if self._git(Path(workflow.repository_path), "status", "--porcelain").strip():
                raise Conflict("The experiment repository is not clean at execution time")
            workflow.status = "executing"
            workflow.updated_at = now_iso()
            self._event(
                session,
                workflow,
                "execution_started",
                "mission-control",
                "Approval verified; Worker execution started.",
                {"approval_hash": workflow.approval_hash},
            )
            # Do not hold a SQLite write transaction while Worker is running.
            session.commit()
            repository = Path(workflow.repository_path)
            spec = get_template(workflow.template)
            proposal = dict(workflow.proposal or {})
            prompt = str(proposal.get("prompt") or "")
            worker = dict(proposal.get("worker") or {})
            base_url = str(worker.get("base_url") or self._worker_base_url())
            model = str(worker.get("model") or DEFAULT_WORKER_MODEL)
            backend = str(worker.get("backend") or DEFAULT_WORKER_BACKEND)
            timeout_seconds = float(worker.get("timeout_seconds") or 180)
            request = {
                "schema": "worker.work-request.v1",
                "app": "mission-control",
                "objective": prompt,
                "workspace": {
                    "root": str(repository),
                    "project_id": workflow.id,
                },
                "execution": {"backend": backend, "model": model},
                "metadata": {
                    "workflow_id": workflow.id,
                    "operation_id": workflow.id,
                    "stage_id": "EXPERIMENT",
                    "next_external_id": workflow.next_external_id,
                },
                "options": {"acceptance": "human"},
            }
            try:
                result = await self._worker_client(base_url).run(
                    request, timeout_seconds
                )
            except Exception as exc:
                workflow.status = "failed"
                workflow.failure = f"Worker request failed: {exc.__class__.__name__}: {str(exc)[:1500]}"
                workflow.updated_at = now_iso()
                self._event(
                    session,
                    workflow,
                    "execution_failed",
                    "worker",
                    "Worker request failed before a patch was applied.",
                    {"error": workflow.failure},
                )
                return self._read(session, workflow)
            workflow.worker_request_id = str(result.get("request_id") or "")
            workflow.worker_status = str(result.get("status") or "unknown")
            workflow.worker_result = self._bounded_worker_result(result)
            workflow.updated_at = now_iso()
            self._event(
                session,
                workflow,
                "worker_responded",
                "worker",
                f"Worker returned {workflow.worker_status} using {backend}/{model}.",
                {
                    "request_id": workflow.worker_request_id,
                    "status": workflow.worker_status,
                    "execution": result.get("execution"),
                    "provenance": result.get("provenance"),
                },
            )
            session.commit()
            session.refresh(workflow)
            if workflow.cancel_requested:
                return self._mark_cancelled(
                    session, workflow, "Cancelled after Worker response; patch was not applied"
                )
            if workflow.worker_status in {"BLOCKED", "FAILED"}:
                workflow.status = "failed"
                workflow.failure = (
                    f"Worker returned {workflow.worker_status}: "
                    f"{str(result.get('message') or result.get('unresolved') or '')[:1500]}"
                )
                self._event(
                    session,
                    workflow,
                    "execution_failed",
                    "worker",
                    "Worker did not produce an applicable experiment result.",
                    {"status": workflow.worker_status, "failure": workflow.failure},
                )
                return self._read(session, workflow)
            try:
                patch = self._parse_patch(str(result.get("output") or ""), spec)
                self._validate_patch(patch, spec)
                self._apply_patch(repository, patch, spec)
                workflow.patch = {
                    "schema": patch["schema"],
                    "summary": patch.get("summary", ""),
                    "expected_result": patch.get("expected_result", ""),
                    "files": [
                        {
                            "path": item["path"],
                            "sha256": hashlib.sha256(
                                item["content"].encode("utf-8")
                            ).hexdigest(),
                        }
                        for item in patch["files"]
                    ],
                }
                self._event(
                    session,
                    workflow,
                    "patch_applied",
                    "mission-control",
                    "Applied the model patch within the approved file scope.",
                    workflow.patch,
                )
            except Exception as exc:
                workflow.status = "failed"
                workflow.failure = f"Patch rejected: {exc.__class__.__name__}: {str(exc)[:1500]}"
                workflow.updated_at = now_iso()
                self._event(
                    session,
                    workflow,
                    "execution_failed",
                    "mission-control",
                    "Patch was rejected before any commit.",
                    {"error": workflow.failure},
                )
                return self._read(session, workflow)
            try:
                measurement = self._measure(
                    spec, repository, baseline=proposal.get("baseline", {}), workflow=workflow
                )
            except Exception as exc:
                workflow.status = "failed"
                workflow.failure = (
                    f"Sandbox measurement failed: {exc.__class__.__name__}: "
                    f"{str(exc)[:1500]}"
                )
                workflow.updated_at = now_iso()
                self._event(
                    session,
                    workflow,
                    "execution_failed",
                    "sandbox",
                    "Deterministic measurement could not be completed.",
                    {"error": workflow.failure},
                )
                return self._read(session, workflow)
            workflow.measurement = measurement
            workflow.updated_at = now_iso()
            self._event(
                session,
                workflow,
                "measurement_recorded",
                "sandbox",
                (
                    "Tests passed and the measurement target was met."
                    if measurement.get("passed")
                    else "The experiment did not meet all deterministic criteria."
                ),
                measurement,
            )
            observation = measurement.get("language_observation") or {}
            if observation:
                session.add(
                    LanguageObservation(
                        id=f"lobs-{uuid.uuid4().hex[:16]}",
                        workflow_id=workflow.id,
                        schema=str(observation.get("schema") or "language.observation.v1"),
                        template=str(observation.get("template") or spec.id),
                        intention_ref=str(observation.get("intention_ref") or ""),
                        subject=str(observation.get("subject") or ""),
                        properties=list(observation.get("properties") or []),
                        measurement_method=observation.get("measurement_method"),
                        evidence=list(observation.get("evidence") or []),
                        provenance=dict(observation.get("provenance") or {}),
                        uncertainty=list(observation.get("uncertainty") or []),
                        constraint_result=str(
                            observation.get("constraint_result") or "unknown"
                        ),
                        evaluation_version=str(
                            observation.get("evaluation_version")
                            or "language.observation.v1"
                        ),
                        created_at=now_iso(),
                    )
                )
                self._event(
                    session,
                    workflow,
                    "language_observation_recorded",
                    "language",
                    (
                        "Recorded language.observation.v1 without changing the "
                        "intention or controlling execution."
                    ),
                    observation,
                )
            session.commit()
            session.refresh(workflow)
            if workflow.cancel_requested:
                return self._mark_cancelled(
                    session, workflow, "Cancelled after measurement; result was not committed"
                )
            try:
                commit = self._commit(repository, workflow, spec)
                workflow.result_commit = commit
                self._event(
                    session,
                    workflow,
                    "result_committed",
                    "sandbox",
                    f"Committed the experiment result as {commit[:12]}.",
                    {"commit": commit, "scope": workflow.approved_scope},
                    source_ref=commit,
                )
            except Exception as exc:
                workflow.status = "failed"
                workflow.failure = f"Result commit failed: {exc.__class__.__name__}: {str(exc)[:1500]}"
                self._event(
                    session,
                    workflow,
                    "execution_failed",
                    "sandbox",
                    "The result could not be committed.",
                    {"error": workflow.failure},
                )
                return self._read(session, workflow)
            workflow.status = "executed"
            return self._read(session, workflow)

    # ----------------------------------------------------------------- review
    async def review(self, workflow_id: str) -> ExperimentWorkflowRead:
        with self.database.session() as session:
            workflow = self._require(session, workflow_id)
            if workflow.cancel_requested:
                return self._mark_cancelled(
                    session, workflow, "Cancelled before CoCoder review"
                )
            if workflow.review_execution_id and workflow.status in {
                "reviewed",
                "review_failed",
                "decided",
            }:
                return self._read(session, workflow)
            if workflow.status != "executed":
                raise Conflict(f"Workflow cannot be reviewed from status {workflow.status}")
            if not workflow.result_commit:
                raise Conflict("Workflow has no result commit to review")
            workflow.status = "reviewing"
            workflow.updated_at = now_iso()
            self._event(
                session,
                workflow,
                "review_requested",
                "mission-control",
                "Requested a CoCoder review of the actual result commit.",
                {
                    "repository_path": workflow.repository_path,
                    "base": workflow.baseline_commit,
                    "head": workflow.result_commit,
                },
            )
            session.commit()
            try:
                execution = await self.integration_service.start_action(
                    "cocoder",
                    "run_review",
                    {
                        "repo_path": workflow.repository_path,
                        "base": workflow.baseline_commit,
                        "head": workflow.result_commit,
                        "timeout_seconds": 120,
                    },
                    confirm=True,
                )
            except Exception as exc:
                workflow.status = "review_failed"
                workflow.failure = (
                    f"CoCoder review could not start: {exc.__class__.__name__}: "
                    f"{str(exc)[:1500]}"
                )
                workflow.updated_at = now_iso()
                self._event(
                    session,
                    workflow,
                    "review_failed",
                    "cocoder",
                    "CoCoder review could not start.",
                    {"error": workflow.failure},
                )
                return self._read(session, workflow)
            workflow.review_execution_id = execution.id
            workflow.updated_at = now_iso()
            self._event(
                session,
                workflow,
                "review_started",
                "cocoder",
                f"CoCoder execution {execution.id} queued.",
                {"execution_id": execution.id},
            )
            session.commit()
        deadline = datetime.now(timezone.utc).timestamp() + 240
        while datetime.now(timezone.utc).timestamp() < deadline:
            await _sleep(2)
            execution = self.integration_service.get_execution(
                workflow.review_execution_id or ""
            )
            if execution.status not in {"queued", "running"}:
                break
        else:
            with self.database.session() as session:
                workflow = self._require(session, workflow_id)
                workflow.status = "review_failed"
                workflow.failure = "CoCoder review timed out"
                workflow.updated_at = now_iso()
                self._event(
                    session,
                    workflow,
                    "review_failed",
                    "cocoder",
                    "CoCoder review timed out.",
                    {},
                )
                return self._read(session, workflow)
        with self.database.session() as session:
            workflow = self._require(session, workflow_id)
            if workflow.cancel_requested:
                return self._mark_cancelled(
                    session, workflow, "Cancelled during CoCoder review"
                )
            execution = self.integration_service.get_execution(
                workflow.review_execution_id or ""
            )
            workflow.review_artifact_path = execution.artifact_ref
            if execution.status != "succeeded":
                workflow.status = "review_failed"
                workflow.failure = (
                    f"CoCoder review {execution.status}: "
                    f"{str(execution.error or execution.output or '')[:1500]}"
                )
                workflow.updated_at = now_iso()
                self._event(
                    session,
                    workflow,
                    "review_failed",
                    "cocoder",
                    "CoCoder review did not complete successfully.",
                    {
                        "execution_id": execution.id,
                        "status": execution.status,
                        "error": execution.error,
                    },
                )
                return self._read(session, workflow)
            summary = self._review_summary(execution.artifact_ref)
            workflow.review_summary = summary
            workflow.adverse_review = bool(summary.get("adverse"))
            workflow.status = "reviewed"
            workflow.updated_at = now_iso()
            self._event(
                session,
                workflow,
                "review_completed",
                "cocoder",
                (
                    f"CoCoder reviewed {summary.get('changed_files', 0)} changed file(s): "
                    f"{summary.get('findings', 0)} finding(s), "
                    f"{summary.get('high', 0)} high, {summary.get('medium', 0)} medium."
                ),
                summary,
                source_ref=execution.artifact_ref,
            )
            return self._read(session, workflow)

    # --------------------------------------------------------------- decision
    def decide(
        self,
        workflow_id: str,
        *,
        decision: str,
        reason: str,
        override_adverse: bool = False,
    ) -> ExperimentWorkflowRead:
        if decision not in {"accept", "reject", "investigate"}:
            raise ValidationProblem("Decision must be accept, reject or investigate")
        with self.database.session() as session:
            workflow = self._require(session, workflow_id)
            if workflow.final_decision == decision:
                return self._read(session, workflow)
            if workflow.final_decision is not None:
                raise Conflict(
                    f"Workflow already decided as {workflow.final_decision}; a different decision requires a new workflow"
                )
            if workflow.status not in {"reviewed", "review_failed", "executed", "failed"}:
                raise Conflict(f"Workflow cannot be decided from status {workflow.status}")
            if decision == "accept":
                if workflow.status != "reviewed" or not bool(
                    (workflow.review_summary or {}).get("available")
                ):
                    raise Conflict("Cannot accept without a completed CoCoder review")
                if not bool((workflow.measurement or {}).get("passed")):
                    raise Conflict(
                        "Cannot accept: deterministic tests or reduction criteria did not pass"
                    )
                if workflow.adverse_review and not override_adverse:
                    raise Conflict(
                        "Cannot accept: CoCoder reported high/medium findings. "
                        "An explicit override with a reason is required."
                    )
                if override_adverse and not reason.strip():
                    raise Conflict("An adverse-review override requires a reason")
            workflow.final_decision = decision
            workflow.final_reason = reason[:4000]
            workflow.override_adverse = bool(override_adverse and workflow.adverse_review)
            workflow.status = "decided"
            workflow.updated_at = now_iso()
            self._event(
                session,
                workflow,
                "human_decision",
                "user",
                f"Human decision: {decision}.",
                {
                    "decision": decision,
                    "reason": workflow.final_reason,
                    "override_adverse": workflow.override_adverse,
                },
            )
            project = session.get(Project, workflow.project_id) if workflow.project_id else None
            session.add(
                Decision(
                    id=f"dec-{uuid.uuid4().hex[:16]}",
                    project_id=workflow.project_id,
                    title=f"MC10 workflow {decision}: {workflow.title[:220]}",
                    rationale=reason or f"Human decision on {workflow.id}.",
                    status="accepted" if decision == "accept" else "rejected" if decision == "reject" else "revised",
                    source="user",
                    decided_at=now_iso(),
                    created_at=now_iso(),
                )
            )
            record_activity(
                session,
                event_type="system",
                title=f"MC10 workflow {decision}",
                detail=f"{workflow.title[:400]}. {reason[:1000]}",
                project_id=project.id if project else None,
                application_id="worker",
                source="mission-control",
                source_id=workflow.id,
                evidence_ref=workflow.review_artifact_path,
                provenance="user",
                metadata={"workflow_id": workflow.id, "decision": decision},
            )
            return self._read(session, workflow)

    def associate_project(
        self, workflow_id: str, project_id: str | None
    ) -> ExperimentWorkflowRead:
        with self.database.session() as session:
            workflow = self._require(session, workflow_id)
            if project_id and session.get(Project, project_id) is None:
                raise NotFound("Project not found")
            workflow.project_id = project_id
            workflow.updated_at = now_iso()
            self._event(
                session,
                workflow,
                "project_associated",
                "user",
                f"Associated with project {project_id or 'none'}.",
                {"project_id": project_id},
            )
            return self._read(session, workflow)

    def project_timeline(self, project_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise NotFound("Project not found")
            workflows = session.scalars(
                select(ExperimentWorkflow)
                .where(ExperimentWorkflow.project_id == project_id)
                .order_by(desc(ExperimentWorkflow.created_at))
            ).all()
            reads = [self._read(session, workflow) for workflow in workflows]
            observations = [
                observation
                for read in reads
                for observation in read.language_observations
            ]
            return {
                "project_id": project_id,
                "workflows": reads,
                "observations": observations,
            }

    # ------------------------------------------------------------------ reads
    def list(self, limit: int = 50) -> list[ExperimentWorkflowRead]:
        with self.database.session() as session:
            rows = session.scalars(
                select(ExperimentWorkflow)
                .order_by(desc(ExperimentWorkflow.created_at))
                .limit(max(1, min(limit, 200)))
            ).all()
            return [self._read(session, row) for row in rows]

    def get(self, workflow_id: str) -> ExperimentWorkflowRead:
        with self.database.session() as session:
            return self._read(session, self._require(session, workflow_id))

    # -------------------------------------------------------------- internals
    def _require(self, session: Session, workflow_id: str) -> ExperimentWorkflow:
        workflow = session.get(ExperimentWorkflow, workflow_id)
        if workflow is None:
            raise NotFound("Workflow not found")
        return workflow

    def _read(
        self, session: Session, workflow: ExperimentWorkflow
    ) -> ExperimentWorkflowRead:
        project = (
            session.get(Project, workflow.project_id)
            if workflow.project_id
            else None
        )
        events = session.scalars(
            select(WorkflowEvent)
            .where(WorkflowEvent.workflow_id == workflow.id)
            .order_by(WorkflowEvent.sequence)
        ).all()
        observations = session.scalars(
            select(LanguageObservation)
            .where(LanguageObservation.workflow_id == workflow.id)
            .order_by(LanguageObservation.created_at)
        ).all()
        return ExperimentWorkflowRead(
            id=workflow.id,
            title=workflow.title,
            template=workflow.template,
            status=workflow.status,
            next_record_id=workflow.next_record_id,
            next_external_id=workflow.next_external_id,
            next_title=workflow.next_title,
            project_id=workflow.project_id,
            project_name=project.name if project else None,
            next_evidence=workflow.next_evidence,
            proposal=workflow.proposal,
            language_intention=workflow.language_intention,
            repository_path=workflow.repository_path,
            baseline_commit=workflow.baseline_commit,
            approved_scope=workflow.approved_scope,
            approval_hash=workflow.approval_hash,
            approved_at=workflow.approved_at,
            approved_by=workflow.approved_by,
            worker_request_id=workflow.worker_request_id,
            worker_status=workflow.worker_status,
            worker_result=workflow.worker_result,
            patch=workflow.patch,
            result_commit=workflow.result_commit,
            measurement=workflow.measurement,
            review_execution_id=workflow.review_execution_id,
            review_artifact_path=workflow.review_artifact_path,
            review_summary=workflow.review_summary,
            adverse_review=workflow.adverse_review,
            final_decision=workflow.final_decision,
            final_reason=workflow.final_reason,
            override_adverse=workflow.override_adverse,
            cancel_requested=workflow.cancel_requested,
            cancelled_at=workflow.cancelled_at,
            failure=workflow.failure,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            events=[
                WorkflowEventRead(
                    id=event.id,
                    workflow_id=event.workflow_id,
                    sequence=event.sequence,
                    event_type=event.event_type,
                    source=event.source,
                    summary=event.summary,
                    payload=event.payload,
                    source_ref=event.source_ref,
                    created_at=event.created_at,
                )
                for event in events
            ],
            language_observations=[
                LanguageObservationRead(
                    id=obs.id,
                    workflow_id=obs.workflow_id,
                    schema_name=obs.schema,
                    template=obs.template,
                    intention_ref=obs.intention_ref,
                    subject=obs.subject,
                    properties=obs.properties,
                    measurement_method=obs.measurement_method,
                    evidence=obs.evidence,
                    provenance=obs.provenance,
                    uncertainty=obs.uncertainty,
                    constraint_result=obs.constraint_result,
                    evaluation_version=obs.evaluation_version,
                    created_at=obs.created_at,
                )
                for obs in observations
            ],
        )

    def _mark_cancelled(
        self, session: Session, workflow: ExperimentWorkflow, summary: str
    ) -> ExperimentWorkflowRead:
        repository = Path(workflow.repository_path)
        try:
            if self._git(repository, "status", "--porcelain").strip():
                self._git(repository, "checkout", "--", ".")
        except Exception:
            pass
        workflow.status = "cancelled"
        workflow.cancel_requested = True
        workflow.cancelled_at = now_iso()
        workflow.updated_at = now_iso()
        self._event(
            session,
            workflow,
            "cancelled",
            "user",
            summary,
            {"cancel_requested": True},
        )
        return self._read(session, workflow)

    def _event(
        self,
        session: Session,
        workflow: ExperimentWorkflow,
        event_type: str,
        source: str,
        summary: str,
        payload: dict[str, Any],
        *,
        source_ref: str | None = None,
    ) -> None:
        sequence = int(
            session.scalar(
                select(func.max(WorkflowEvent.sequence)).where(
                    WorkflowEvent.workflow_id == workflow.id
                )
            )
            or 0
        ) + 1
        session.add(
            WorkflowEvent(
                id=f"wev-{uuid.uuid4().hex[:16]}",
                workflow_id=workflow.id,
                sequence=sequence,
                event_type=event_type,
                source=source,
                summary=summary,
                payload=payload,
                source_ref=source_ref,
                created_at=now_iso(),
            )
        )
        session.flush()

    def _source_for_create(
        self, session: Session, spec: TemplateSpec, record_id: str | None
    ) -> dict[str, Any]:
        if spec.source_kind == "next_export":
            if not record_id:
                raise ValidationProblem("record_id is required for a Next workflow template")
            record = session.get(IntegrationRecord, record_id)
            if (
                record is None
                or record.application_id != "next"
                or record.resource_type != "next_opportunity"
            ):
                raise NotFound("Next opportunity not found")
            export_path = self._export_path()
            export = self._load_export(export_path)
            candidate = self._find_candidate(export, record.external_id)
            if candidate is None:
                raise ValidationProblem(
                    "The Next research export does not contain this opportunity. "
                    "Refresh the next-research-export-v1 file first."
                )
            return {
                "source_id": record.external_id,
                "title": record.title,
                "record_id": record.id,
                "project_id": record.project_id,
                "source_kind": "next",
                "evidence": {
                    "schema": export.get("schema"),
                    "source_kind": "next",
                    "generated_at": export.get("generated_at"),
                    "export_path": str(export_path),
                    "opportunity": self._evidence_subset(candidate),
                },
                "candidate": candidate,
            }
        repository = self._sandbox_path(spec)
        evidence_path = repository / "evidence.json"
        if not evidence_path.is_file():
            raise ValidationProblem(
                f"Fixture evidence manifest not found: {evidence_path}"
            )
        try:
            fixture = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValidationProblem(f"Fixture evidence is unreadable: {exc}") from exc
        if fixture.get("schema") != spec.source_contract:
            raise ValidationProblem(
                f"Fixture evidence schema must be {spec.source_contract}, "
                f"got {fixture.get('schema')!r}"
            )
        expected = fixture.get("expected") or {}
        opportunity = {
            "id": fixture.get("id"),
            "title": fixture.get("title"),
            "status": "FIXTURE",
            "queue_type": "fixture",
            "score": None,
            "what_discovered": fixture.get("intention"),
            "evidence": json.dumps(expected, sort_keys=True),
            "simplest_experiment": "Measure the defined fixture property without altering media.",
            "falsification": "; ".join(fixture.get("uncertainty") or []),
            "evaluation_basis": "local fixture",
            "uncertainty": fixture.get("uncertainty"),
            "items": [],
            "evidence_gaps": None,
        }
        return {
            "source_id": str(fixture.get("id")),
            "title": str(fixture.get("title") or spec.title),
            "record_id": None,
            "project_id": None,
            "source_kind": "fixture",
            "evidence": {
                "schema": fixture.get("schema"),
                "source_kind": "fixture",
                "generated_at": fixture.get("generated_at") or now_iso(),
                "export_path": str(evidence_path),
                "opportunity": opportunity,
                "fixture_evidence": fixture,
            },
            "candidate": opportunity,
        }

    def _export_path(self) -> Path:
        configured = os.environ.get("MC10_NEXT_EXPORT")
        return (
            Path(configured).expanduser().resolve()
            if configured
            else self.settings.data_dir / "integrations" / "next" / "next-research-export-v1.json"
        )

    def _load_export(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise ValidationProblem(
                f"Next research export not found: {path}. Run `next export --output ...` first."
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValidationProblem(f"Next research export is unreadable: {exc}") from exc
        if payload.get("schema") != EXPORT_SCHEMA:
            raise ValidationProblem(
                f"Next export schema must be {EXPORT_SCHEMA}, got {payload.get('schema')!r}"
            )
        return payload

    def _find_candidate(
        self, export: dict[str, Any], external_id: str
    ) -> dict[str, Any] | None:
        for opportunity in export.get("opportunities") or []:
            if isinstance(opportunity, dict) and opportunity.get("id") == external_id:
                return opportunity
        return None

    def _sandbox_path(self, spec: TemplateSpec) -> Path:
        env_name = f"MC11_SANDBOX_{spec.id.upper()}"
        configured = os.environ.get(env_name)
        if not configured and spec.id == TRACE_TEMPLATE:
            configured = os.environ.get("MC10_SANDBOX")
        if configured:
            return Path(configured).expanduser().resolve()
        return (self.settings.data_dir / spec.sandbox_relative).resolve()

    def _require_repository(self, repository: Path) -> None:
        if not repository.is_dir():
            raise ValidationProblem(f"Experiment repository not found: {repository}")
        if not (repository / ".git").is_dir():
            raise ValidationProblem(f"Experiment repository is not a Git repository: {repository}")
        if self._git(repository, "status", "--porcelain").strip():
            raise Conflict("Experiment repository must be clean before creating a workflow")

    def _prepare_baseline(
        self, repository: Path, spec: TemplateSpec, *, force_new: bool
    ) -> str:
        """Keep every attempt anchored to the same clean baseline.

        Result commits are tagged by workflow id before a retry resets the
        sandbox, so prior evidence remains reachable while the next experiment
        starts from the original failing code.
        """

        baseline_tag = spec.baseline_tag
        try:
            baseline = self._git(
                repository, "rev-parse", "--verify", f"refs/tags/{baseline_tag}"
            ).strip()
        except ValueError:
            baseline = self._git(repository, "rev-parse", "HEAD").strip()
            self._git(repository, "tag", "-f", baseline_tag, baseline)
        if force_new:
            current = self._git(repository, "rev-parse", "HEAD").strip()
            if current != baseline:
                self._git(
                    repository,
                    "tag",
                    "-f",
                    f"mc11-before-retry-{uuid.uuid4().hex[:10]}",
                    current,
                )
                self._git(repository, "reset", "--hard", baseline)
                self._git(repository, "clean", "-fd")
        return baseline

    def _proposal(
        self,
        *,
        spec: TemplateSpec,
        source: dict[str, Any],
        repository: Path,
        baseline_commit: str,
        baseline_hash: str,
        project_id: str | None,
    ) -> dict[str, Any]:
        candidate = source["candidate"]
        current_file = (repository / spec.scope[0]).read_text(encoding="utf-8")
        tests = (repository / spec.tests_path).read_text(encoding="utf-8")
        try:
            baseline = {
                "tests": self._run_tests(repository),
                "measurement": self._run_measure(repository),
                "scope_sha256": baseline_hash,
            }
        except SandboxUnavailable as exc:
            raise ValidationProblem(str(exc)) from exc
        prompt = self._prompt(spec, candidate, current_file, tests)
        return {
            "schema": "mc11.experiment-proposal.v1",
            "template": spec.id,
            "template_version": spec.version,
            "objective": f"Execute the bounded {spec.title} experiment, changing only {spec.scope[0]}.",
            "hypothesis": str(candidate.get("what_discovered") or candidate.get("description") or "")[:2000],
            "source_experiment": str(candidate.get("simplest_experiment") or ""),
            "falsification": str(candidate.get("falsification") or ""),
            "scope": list(spec.scope),
            "repository_path": str(repository),
            "baseline_commit": baseline_commit,
            "baseline_scope_sha256": baseline_hash,
            "project_id": project_id,
            "expected_result": spec.expected_result,
            "stop_conditions": list(spec.stop_conditions),
            "evaluation_criteria": list(spec.evaluation_criteria),
            "worker": {
                "backend": DEFAULT_WORKER_BACKEND,
                "model": os.environ.get("MC10_WORKER_MODEL", DEFAULT_WORKER_MODEL),
                "base_url": self._worker_base_url(),
                "max_model_calls": 1,
                "timeout_seconds": 180,
            },
            "sandbox": self.sandbox.describe(),
            "prompt": prompt,
            "baseline": baseline,
            "source_contract": {
                "kind": spec.source_kind,
                "contract": spec.source_contract,
                "path": source["evidence"].get("export_path"),
                "schema": source["evidence"].get("schema"),
                "generated_at": source["evidence"].get("generated_at"),
            },
            "provenance": {
                "source_id": source["source_id"],
                "source_title": source["title"],
                "source_kind": source["source_kind"],
                "next_record_id": source["record_id"],
            },
        }

    def _prompt(
        self,
        spec: TemplateSpec,
        candidate: dict[str, Any],
        current_file: str,
        tests: str,
    ) -> str:
        algorithm = "\n".join(f"- {item}." for item in spec.worker_algorithm)
        return f"""You are executing a bounded experiment from the {spec.title} template.
Source evidence: {str(candidate.get('title') or spec.title)[:300]}

Return ONLY the complete Python file content for {spec.scope[0]}. Do not use markdown fences. Do not add commentary.

Rules:
- Modify only {spec.scope[0]}.
- The file must be complete and valid Python.
- The function must satisfy every test below.
- Never mutate the input list.
- Use exactly this algorithm:
{algorithm}
- Do not add imports unless required.
- Do not read or write files outside the fixture inputs required by the tests.

Current file:
{current_file}

Tests:
{tests}
"""

    def _language_intention(self, proposal: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": "language.intention.v0",
            "silent": True,
            "intent": proposal.get("objective"),
            "constraints": proposal.get("stop_conditions", []),
            "scope": proposal.get("scope", []),
            "expected_result": proposal.get("expected_result"),
            "evaluation_criteria": proposal.get("evaluation_criteria", []),
            "observations": [],
            "decision": None,
            "note": "Structured intention only; no Language model or interpretation is used.",
        }

    def _evidence_subset(self, candidate: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "id",
            "title",
            "status",
            "queue_type",
            "score",
            "what_discovered",
            "evidence",
            "what_is_new",
            "capability_unlocked",
            "relation_to_existing",
            "simplest_experiment",
            "falsification",
            "cost_estimate",
            "why_not",
            "evaluation_basis",
            "uncertainty",
            "created_at",
            "items",
            "evidence_gaps",
        )
        return {key: candidate.get(key) for key in keys}

    def _idempotency_key(self, external_id: str, template: str) -> str:
        # Replaying the same Next opportunity must return the same workflow,
        # even after its own result commit moved the repository HEAD.
        raw = f"{template}\x1f{external_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _approval_payload(self, workflow: ExperimentWorkflow) -> dict[str, Any]:
        proposal = workflow.proposal or {}
        return {
            "objective": proposal.get("objective"),
            "scope": proposal.get("scope"),
            "repository_path": proposal.get("repository_path"),
            "baseline_commit": proposal.get("baseline_commit"),
            "baseline_scope_sha256": proposal.get("baseline_scope_sha256"),
            "expected_result": proposal.get("expected_result"),
            "stop_conditions": proposal.get("stop_conditions"),
            "evaluation_criteria": proposal.get("evaluation_criteria"),
            "worker": proposal.get("worker"),
            "prompt_sha256": hashlib.sha256(
                str(proposal.get("prompt") or "").encode("utf-8")
            ).hexdigest(),
        }

    def _approval_hash(self, workflow: ExperimentWorkflow) -> str:
        payload = self._approval_payload(workflow)
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _assert_approval_current(self, workflow: ExperimentWorkflow) -> None:
        if not workflow.approval_hash:
            raise Conflict("Workflow has no approval hash")
        if workflow.approval_hash != self._approval_hash(workflow):
            raise Conflict("Approval is stale: the proposal changed after approval")
        if workflow.approved_scope != list((workflow.proposal or {}).get("scope") or []):
            raise Conflict("Approval is stale: the approved scope changed")

    def _assert_approval_inputs_current(self, workflow: ExperimentWorkflow) -> None:
        repository = Path(workflow.repository_path)
        if not repository.is_dir():
            raise ValidationProblem(f"Experiment repository not found: {repository}")
        if not (repository / ".git").is_dir():
            raise ValidationProblem(
                f"Experiment repository is not a Git repository: {repository}"
            )
        head = self._git(repository, "rev-parse", "HEAD").strip()
        if head != workflow.baseline_commit:
            raise Conflict(
                f"Approval is stale: repository HEAD {head[:12]} does not match baseline {workflow.baseline_commit[:12]}"
            )
        expected = str((workflow.proposal or {}).get("baseline_scope_sha256") or "")
        spec = self._spec_for_workflow(workflow)
        if expected and self._scope_hash(repository, spec.scope) != expected:
            raise Conflict("Approval is stale: the approved file changed after proposal creation")
        if self._git(repository, "status", "--porcelain").strip():
            raise Conflict("Experiment repository must be clean before execution")

    def _spec_for_workflow(self, workflow: ExperimentWorkflow) -> TemplateSpec:
        return get_template(workflow.template)

    def _scope_hash(self, repository: Path, scope: tuple[str, ...]) -> str:
        digest = hashlib.sha256()
        for relative in scope:
            digest.update(relative.encode("utf-8"))
            digest.update(b"\x00")
            digest.update((repository / relative).read_bytes())
        return digest.hexdigest()

    def _worker_base_url(self) -> str:
        with self.database.session() as session:
            application = session.get(Application, "worker")
            config = application.adapter_config if application else {}
        return str((config or {}).get("base_url") or DEFAULT_WORKER_URL).rstrip("/")

    def _worker_client(self, base_url: str) -> WorkerClient:
        if self.worker_client is not None:
            return self.worker_client
        return HttpWorkerClient(base_url)

    def _bounded_worker_result(self, result: dict[str, Any]) -> dict[str, Any]:
        output = result.get("output")
        text = output if isinstance(output, str) else json.dumps(output, default=str)
        return {
            "schema": result.get("schema"),
            "request_id": result.get("request_id"),
            "status": result.get("status"),
            "execution": result.get("execution"),
            "provenance": result.get("provenance"),
            "message": result.get("message"),
            "unresolved": result.get("unresolved"),
            "output_excerpt": text[:4000],
            "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }

    def _parse_patch(self, raw: str, spec: TemplateSpec) -> dict[str, Any]:
        text = raw.strip()
        fenced = re.search(r"```(?:python|json)?\s*(.*?)```", text, flags=re.I | re.S)
        if fenced:
            text = fenced.group(1).strip()
        else:
            text = re.sub(r"^```(?:python|json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text).strip()
        if not text:
            raise ValueError("Worker output was empty")
        entrypoint = f"def {spec.entrypoint}"
        if entrypoint in text and not text.lstrip().startswith(("def ", "{")):
            text = text[text.find(entrypoint) :].strip()
        if text.startswith("{") and PATCH_SCHEMA in text:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("Worker output did not contain a JSON patch object")
            payload = json.loads(text[start : end + 1])
            if not isinstance(payload, dict) or payload.get("schema") != PATCH_SCHEMA:
                raise ValueError(f"Patch schema must be {PATCH_SCHEMA}")
            files = payload.get("files")
            if not isinstance(files, list) or len(files) != 1:
                raise ValueError("Patch must contain exactly one file")
            item = files[0]
            if not isinstance(item, dict):
                raise ValueError("Patch file entry must be an object")
            if item.get("path") not in spec.scope:
                raise ValueError(
                    f"Patch path is outside approved scope: {item.get('path')!r}"
                )
            if not isinstance(item.get("content"), str) or not item["content"].strip():
                raise ValueError("Patch content is empty")
            return payload
        # Worker's direct executor often returns a complete code file. The
        # approved scope already fixes the destination path, so no model-chosen
        # path is needed or trusted.
        return {
            "schema": PATCH_SCHEMA,
            "files": [{"path": spec.scope[0], "content": text}],
            "summary": "Worker generated code for the approved file scope.",
            "expected_result": "Deterministic tests and measurement target pass.",
        }

    def _validate_patch(self, patch: dict[str, Any], spec: TemplateSpec) -> None:
        content = str(patch["files"][0]["content"])
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            raise ValueError(f"Generated Python is invalid: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                raise ValueError("Generated Python must not import modules")
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                raise ValueError("Generated Python must not access dunder attributes")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    if node.func.id == "open" and spec.allow_read_only_open:
                        if len(node.args) != 2 or not isinstance(
                            node.args[1], ast.Constant
                        ) or node.args[1].value not in {"r", "rb"}:
                            raise ValueError(
                                "Generated Python may only open files in read-only mode"
                            )
                    else:
                        raise ValueError(
                            f"Generated Python calls forbidden function: {node.func.id}"
                        )
        if not any(
            isinstance(node, ast.FunctionDef) and node.name == spec.entrypoint
            for node in tree.body
        ):
            raise ValueError(
                f"Generated Python must define {spec.entrypoint}"
            )

    def _apply_patch(
        self, repository: Path, patch: dict[str, Any], spec: TemplateSpec
    ) -> None:
        relative = str(patch["files"][0]["path"])
        if relative not in spec.scope:
            raise ValueError("Patch path is outside approved scope")
        target = (repository / relative).resolve()
        root = repository.resolve()
        if root not in target.parents:
            raise ValueError("Patch path escaped the repository")
        target.write_text(str(patch["files"][0]["content"]), encoding="utf-8")
        changed = self._git(repository, "diff", "--name-only").splitlines()
        if sorted(path.strip() for path in changed if path.strip()) != sorted(spec.scope):
            self._git(repository, "checkout", "--", ".")
            raise ValueError(
                f"Repository changed outside approved scope: {sorted(changed)}"
            )

    def _run_tests(self, repository: Path) -> dict[str, Any]:
        result = self.sandbox.run(
            repository,
            ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            timeout_seconds=90,
        )
        return {
            "command": "python -m pytest -q -p no:cacheprovider",
            "exit_code": result.exit_code,
            "passed": result.exit_code == 0 and not result.timed_out,
            "output_tail": (result.stdout + result.stderr)[-4000:],
            "sandbox": result.limits,
            "duration_seconds": result.duration_seconds,
        }

    def _run_measure(self, repository: Path) -> dict[str, Any]:
        result = self.sandbox.run(
            repository,
            ["python", "scripts/measure.py"],
            timeout_seconds=60,
        )
        measurement: dict[str, Any] = {}
        for line in (result.stdout or "").splitlines():
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    measurement = parsed
            except ValueError:
                continue
        return {
            "command": "python scripts/measure.py",
            "exit_code": result.exit_code,
            "passed": result.exit_code == 0 and not result.timed_out,
            "metrics": measurement,
            "output_tail": (result.stdout + result.stderr)[-3000:],
            "sandbox": result.limits,
            "duration_seconds": result.duration_seconds,
        }

    def _measure(
        self,
        spec: TemplateSpec,
        repository: Path,
        *,
        baseline: dict[str, Any],
        workflow: ExperimentWorkflow,
    ) -> dict[str, Any]:
        tests = self._run_tests(repository)
        after = self._run_measure(repository)
        baseline_measurement = (baseline.get("measurement") or {}).get("metrics") or {}
        after_metrics = after.get("metrics") or {}
        passed = bool(
            tests.get("passed")
            and after.get("passed")
            and after_metrics.get(spec.success_key) is True
        )
        if spec.id == "trace_reduce_v1":
            comparison = {
                "baseline_events": baseline_measurement.get("baseline_events"),
                "baseline_reduced_events": baseline_measurement.get("reduced_events"),
                "after_events": after_metrics.get("baseline_events"),
                "after_reduced_events": after_metrics.get("reduced_events"),
                "after_reduction_ratio": after_metrics.get("reduction_ratio"),
            }
        else:
            comparison = {
                "expected_means": after_metrics.get("expected_means"),
                "observed_means": after_metrics.get("observed_means"),
                "expected_max": after_metrics.get("expected_max"),
                "observed_max": after_metrics.get("observed_max"),
                "monotonic": after_metrics.get("monotonic"),
                "within_tolerance": after_metrics.get("within_tolerance"),
            }
        measurement = {
            "schema": "mc11.measurement.v1",
            "template": spec.id,
            "passed": passed,
            "tests": tests,
            "after": after,
            "baseline": baseline_measurement,
            "sandbox": self.sandbox.describe(),
            "comparison": comparison,
        }
        measurement["language_observation"] = self._language_observation(
            spec, workflow, measurement
        )
        return measurement

    def _language_observation(
        self,
        spec: TemplateSpec,
        workflow: ExperimentWorkflow,
        measurement: dict[str, Any],
    ) -> dict[str, Any]:
        metrics = measurement.get("after", {}).get("metrics") or {}
        if spec.id == "trace_reduce_v1":
            expected = [metrics.get("expected_reduced_events", 3)]
            observed = [metrics.get("reduced_events")]
            properties = [
                {
                    "id": "reduced_event_count",
                    "expected": expected[0],
                    "observed": observed[0],
                    "difference": (
                        observed[0] - expected[0]
                        if isinstance(observed[0], (int, float))
                        and isinstance(expected[0], (int, float))
                        else None
                    ),
                    "within_constraint": observed[0] == expected[0],
                }
            ]
            uncertainty = [
                "Proxy trace fixture only; this does not establish general agent performance.",
            ]
        else:
            expected = metrics.get("expected_means") or []
            observed = metrics.get("observed_means") or []
            properties = [
                {
                    "id": "mean_brightness",
                    "expected": expected,
                    "observed": observed,
                    "difference": [
                        round(float(o) - float(e), 4)
                        for o, e in zip(observed, expected)
                        if isinstance(o, (int, float)) and isinstance(e, (int, float))
                    ],
                    "within_constraint": bool(metrics.get("within_tolerance")),
                },
                {
                    "id": "max_brightness",
                    "expected": metrics.get("expected_max") or [],
                    "observed": metrics.get("observed_max") or [],
                    "difference": [],
                    "within_constraint": metrics.get("expected_max")
                    == metrics.get("observed_max"),
                },
                {
                    "id": "monotonic_progression",
                    "expected": True,
                    "observed": bool(metrics.get("monotonic")),
                    "difference": None,
                    "within_constraint": bool(metrics.get("monotonic")),
                },
            ]
            uncertainty = [
                "Synthetic fixture only; not production media.",
                "Mean brightness is not a perceptual quality measurement.",
            ]
        return {
            "schema": "language.observation.v1",
            "workflow_id": workflow.id,
            "template": spec.id,
            "intention_ref": f"workflow:{workflow.id}:language.intention.v0",
            "subject": workflow.next_external_id,
            "properties": properties,
            "measurement_method": measurement.get("after", {}).get("command"),
            "evidence": [
                f"sandbox:{workflow.repository_path}",
                f"measurement:{spec.measure_command[-1]}",
            ],
            "provenance": {
                "source_kind": spec.source_kind,
                "source_contract": spec.source_contract,
                "source_id": workflow.next_external_id,
            },
            "uncertainty": uncertainty,
            "constraint_result": "pass" if all(
                item.get("within_constraint") for item in properties
            ) else "fail",
            "evaluation_version": "language.observation.v1",
            "created_at": now_iso(),
            "note": "Observation only; it does not control execution or rewrite the intention.",
        }

    def _git(self, repository: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repository), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            shell=False,
            check=False,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            raise ValueError(
                f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()[:1000]}"
            )
        return result.stdout

    def _commit(
        self, repository: Path, workflow: ExperimentWorkflow, spec: TemplateSpec
    ) -> str:
        self._git(repository, "add", *spec.scope)
        staged = self._git(repository, "diff", "--cached", "--name-only").splitlines()
        if sorted(path.strip() for path in staged if path.strip()) != sorted(spec.scope):
            raise ValueError("Staged files do not exactly match the approved scope")
        self._git(
            repository,
            "-c",
            "user.name=Mission Control",
            "-c",
            "user.email=mission-control@localhost",
            "commit",
            "-m",
            f"MC11 experiment {workflow.id}: {workflow.title[:120]}",
        )
        commit = self._git(repository, "rev-parse", "HEAD").strip()
        self._git(repository, "tag", "-f", f"mc11-result-{workflow.id}", commit)
        return commit

    def _review_summary(self, artifact_path: str | None) -> dict[str, Any]:
        if not artifact_path:
            return {
                "schema": "mc10.review-summary.v1",
                "available": False,
                "findings": 0,
                "high": 0,
                "medium": 0,
                "adverse": False,
                "note": "CoCoder returned no artifact path.",
            }
        path = Path(artifact_path)
        if not path.is_file():
            return {
                "schema": "mc10.review-summary.v1",
                "available": False,
                "findings": 0,
                "high": 0,
                "medium": 0,
                "adverse": False,
                "note": "CoCoder artifact path is not readable.",
                "artifact_path": artifact_path,
            }
        try:
            review = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return {
                "schema": "mc10.review-summary.v1",
                "available": False,
                "findings": 0,
                "high": 0,
                "medium": 0,
                "adverse": False,
                "note": f"CoCoder artifact is unreadable: {exc.__class__.__name__}",
                "artifact_path": artifact_path,
            }
        findings = review.get("findings") or []
        high = sum(1 for item in findings if str(item.get("severity")) == "high")
        medium = sum(1 for item in findings if str(item.get("severity")) == "medium")
        return {
            "schema": "mc10.review-summary.v1",
            "available": True,
            "artifact_path": artifact_path,
            "review_schema": review.get("schema_version"),
            "changed_files": len(review.get("changed_files") or []),
            "findings": len(findings),
            "high": high,
            "medium": medium,
            "low": sum(1 for item in findings if str(item.get("severity")) == "low"),
            "info": sum(1 for item in findings if str(item.get("severity")) == "info"),
            "adverse": high > 0 or medium > 0,
            "sample": [
                {
                    "finding_id": item.get("finding_id"),
                    "severity": item.get("severity"),
                    "title": item.get("title"),
                    "statement": item.get("statement"),
                }
                for item in findings[:20]
            ],
        }


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
