"""Writer Editing integration.

Mission Control consumes Writer's versioned CLI JSON contract. It does not
import Writer's parser or scoring code, and it does not edit manuscripts.

The adapter reads ``writer editing summary --json``. A separately approved
``audit_registered_books`` action runs Writer's read-only audit; the action
writes Writer-owned report artifacts only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mission_control.adapters.base import (
    ActionContext,
    ActionSpec,
    ActionResult,
    Adapter,
    AdapterResult,
    AdapterTarget,
    Observation,
    ResourceSeed,
)
from mission_control.integrations.runner import run_tool

CLI_SCHEMA = "writer.editing.cli.v1"
SUMMARY_SCHEMA = "writer-editing-summary-v1"
RESOURCE_TYPE = "writer_editing_book"
PROFILE = "technical-nonfiction-v1"


def _book_summary(book: dict[str, Any]) -> str:
    risk = book.get("highest_risk") or {}
    if risk:
        risk_text = (
            f"Highest risk: {risk.get('chapter_title') or risk.get('chapter_id') or 'book'}"
            f" / {risk.get('label') or risk.get('subdimension') or risk.get('code')}"
            f" ({risk.get('status_band') or risk.get('severity') or 'review'})."
        )
    else:
        risk_text = "No readability review signal recorded."
    chapters = book.get("chapters_available", 0)
    return f"{chapters} chapter(s). {risk_text}"


def _resource(book: dict[str, Any], generated_at: str) -> ResourceSeed:
    status = str(book.get("status") or "UNKNOWN")
    report_id = book.get("report_id")
    evidence = [str(item) for item in (book.get("limitations") or [])][:4]
    if report_id:
        evidence.insert(0, f"writer-editing-report:{report_id}")
    return ResourceSeed(
        resource_type=RESOURCE_TYPE,
        external_id=str(book.get("project_id") or ""),
        title=str(book.get("title") or book.get("project_id") or "Writer book"),
        summary=_book_summary(book),
        state=status,
        evidence=evidence,
        data=book,
        source_version=SUMMARY_SCHEMA,
        source_timestamp=generated_at or None,
        stale_after_seconds=3600,
    )


class WriterAdapter(Adapter):
    name = "writer"
    capabilities = [
        "writer_editing_summary",
        "writer_editing_books",
        "writer_editing_chapters",
        "writer_editing_reports",
        "writer_book_campaigns",
        "list_actions",
        "execute_action",
        "list_events",
    ]
    actions = [
        ActionSpec(
            id="audit_registered_books",
            title="Run Writer editing audits",
            description=(
                "Runs Writer's read-only editing audit over every registered book "
                "with recognised Markdown chapters. Writer writes its own report "
                "artifacts under .writer/editing; no manuscript is edited."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "string",
                        "enum": [PROFILE],
                        "default": PROFILE,
                    }
                },
                "additionalProperties": False,
            },
        ),
        ActionSpec(
            id="book_campaign_create",
            title="Create a book improvement campaign",
            description=(
                "Creates a durable, bounded book campaign record in Writer's "
                "own store. No model calls, no repairs, no manuscript changes."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "book_root": {"type": "string"},
                    "book_id": {"type": "string"},
                    "mode": {"type": "string", "enum": ["DISCOVER", "ASSESS", "PLAN",
                                                        "IMPROVE_CANDIDATES", "REVIEW"],
                             "default": "PLAN"},
                },
                "required": ["book_root"],
                "additionalProperties": True,
            },
        ),
        ActionSpec(
            id="book_campaign_manifest",
            title="Build the campaign source manifest",
            description=(
                "Discovers registered chapters and freezes source hashes for one "
                "campaign revision. Read-only with respect to the manuscript."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "book_root": {"type": "string"},
                },
                "required": ["campaign_id", "book_root"],
                "additionalProperties": True,
            },
        ),
        ActionSpec(
            id="book_campaign_plan",
            title="Build the book improvement plan",
            description=(
                "Runs deterministic chapter snapshots and opportunity synthesis "
                "to produce a bounded, inspectable book plan. No candidate generation."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "book_root": {"type": "string"},
                    "selective": {"type": "string",
                                  "enum": ["all", "new", "eligible", "author", "mixed"],
                                  "default": "all"},
                },
                "required": ["campaign_id", "book_root"],
                "additionalProperties": True,
            },
        ),
        ActionSpec(
            id="book_campaign_run_chunk",
            title="Run a bounded campaign chunk",
            description=(
                "Executes one bounded chunk of a campaign run (wall-clock capped). "
                "Safe to re-invoke: completed chapters are skipped (idempotent resume)."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "book_root": {"type": "string"},
                    "max_wall_seconds": {"type": "integer", "default": 240},
                },
                "required": ["run_id", "book_root"],
                "additionalProperties": True,
            },
        ),
        ActionSpec(
            id="book_strategy_experiment_run",
            title="Run one bounded strategy-experiment arm",
            description=(
                "Executes the baseline or candidate arm of a frozen matched experiment "
                "(wall-clock capped, source-frozen, ledger-linked). Safe to re-invoke "
                "per arm; the other arm runs separately for comparison."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "experiment_id": {"type": "string"},
                    "arm": {"type": "string", "enum": ["baseline", "candidate"]},
                    "book_root": {"type": "string"},
                    "max_wall_seconds": {"type": "integer", "default": 900},
                },
                "required": ["experiment_id", "arm", "book_root"],
                "additionalProperties": True,
            },
        ),
        ActionSpec(
            id="book_campaign_pause",
            title="Pause a campaign run",
            description="Requests a pause; the current chapter finishes, then scheduling stops.",
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "book_root": {"type": "string"},
                },
                "required": ["run_id", "book_root"],
                "additionalProperties": True,
            },
        ),
        ActionSpec(
            id="book_campaign_resume",
            title="Resume a paused campaign run",
            description="Clears pause flags; the next run chunk continues where it stopped.",
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "book_root": {"type": "string"},
                },
                "required": ["run_id", "book_root"],
                "additionalProperties": True,
            },
        ),
        ActionSpec(
            id="book_campaign_cancel",
            title="Cancel a campaign run",
            description="Cancels a run; history and completed evidence are preserved.",
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "book_root": {"type": "string"},
                },
                "required": ["run_id", "book_root"],
                "additionalProperties": True,
            },
        ),
        ActionSpec(
            id="book_campaign_status",
            title="Show campaign run state",
            description="Reads the durable run state. No model calls, no writes.",
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=False,
            side_effect="read_only",
            parameters_schema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "book_root": {"type": "string"},
                },
                "required": ["run_id", "book_root"],
                "additionalProperties": True,
            },
        ),
    ]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        repo = target.repo_by_name("writer") or target.primary_repository
        if repo is None or not repo.is_dir():
            return AdapterResult(
                available=False,
                detail="Writer repository is unavailable at the configured path.",
                capabilities=self.capabilities,
                actions=self.actions,
                error="Writer repository unavailable",
            )
        executable, arguments, working_directory, timeout = self._command(
            target, repo, ["editing", "summary", "--json"]
        )
        try:
            result = await run_tool(
                executable,
                arguments,
                working_directory=working_directory,
                env_names=list(target.config.get("env_names") or []),
                timeout_seconds=timeout,
            )
        except Exception as exc:
            return AdapterResult(
                available=False,
                detail="Writer CLI could not be executed; no editing data was invented.",
                capabilities=self.capabilities,
                actions=self.actions,
                error=f"{exc.__class__.__name__}: {str(exc)[:500]}",
            )
        if result.exit_code != 0:
            return AdapterResult(
                available=False,
                detail="Writer CLI returned a non-zero exit code; no editing data was imported.",
                capabilities=self.capabilities,
                actions=self.actions,
                error=(result.stderr or result.stdout or "No diagnostic output")[-1600:],
            )
        parsed = self._parse_summary(result.stdout)
        if parsed is None:
            return AdapterResult(
                available=False,
                detail="Writer CLI output did not match the versioned editing contract.",
                capabilities=self.capabilities,
                actions=self.actions,
                error="Unsupported or malformed Writer editing summary",
            )
        summary, books = parsed
        generated_at = str(summary.get("generated_at") or "")
        resources = [_resource(book, generated_at) for book in books]
        totals = summary.get("totals") or {}
        detail = (
            f"Read {len(books)} Writer book summaries: "
            f"{totals.get('audited', 0)} audited, "
            f"{totals.get('needs_review', 0)} need review, "
            f"{totals.get('stale', 0)} stale, "
            f"{totals.get('not_run', 0)} not run. "
            "Writer remains the source of the reports; no manuscript was edited."
        )
        observations: list[Observation] = []
        queue = summary.get("review_queue") or []
        if queue:
            top = queue[0]
            risk = top.get("highest_risk") or {}
            observations.append(
                Observation(
                    title=f"Writer review queue: {len(queue)} project(s) with editing evidence",
                    detail=(
                        f"First: {top.get('title')} ({top.get('status')}). "
                        f"Highest risk: {risk.get('subdimension') or risk.get('code') or 'not stated'}."
                    ),
                    external_id=(
                        "writer-editing-queue-"
                        + "-".join(str(item.get("project_id")) for item in queue[:5])
                        + "-"
                        + str(totals.get("needs_review", 0))
                    ),
                    evidence_ref=str(summary.get("store_path") or "writer:editing"),
                    provenance="derived_observation",
                    metadata={"totals": totals},
                )
            )
        return AdapterResult(
            available=True,
            detail=detail,
            capabilities=self.capabilities,
            actions=self.actions,
            resources=resources,
            observations=observations,
        )

    def validate_action(
        self, action_id: str, parameters: dict[str, Any], context: ActionContext
    ) -> None:
        if action_id == "audit_registered_books":
            profile = str(parameters.get("profile") or PROFILE)
            if profile != PROFILE:
                raise ValueError(f"Unsupported Writer editing profile: {profile}")
            return
        if action_id in {
            "book_campaign_create", "book_campaign_manifest", "book_campaign_plan",
            "book_campaign_run_chunk", "book_campaign_pause", "book_campaign_resume",
            "book_campaign_cancel", "book_campaign_status",
            "book_strategy_experiment_run",
        }:
            if action_id in {"book_campaign_manifest", "book_campaign_plan"} and not parameters.get("campaign_id"):
                raise ValueError(f"{action_id} requires campaign_id")
            if action_id in {"book_campaign_run_chunk", "book_campaign_pause",
                             "book_campaign_resume", "book_campaign_cancel",
                             "book_campaign_status"} and not parameters.get("run_id"):
                raise ValueError(f"{action_id} requires run_id")
            if action_id == "book_strategy_experiment_run":
                if not parameters.get("experiment_id"):
                    raise ValueError(f"{action_id} requires experiment_id")
                if parameters.get("arm") not in ("baseline", "candidate"):
                    raise ValueError(f"{action_id} requires arm baseline|candidate")
            if not parameters.get("book_root"):
                raise ValueError(f"{action_id} requires book_root")
            return
        raise ValueError(f"Unsupported Writer action: {action_id}")

    def _campaign_args(self, action_id: str, parameters: dict[str, Any]) -> list[str]:
        book_root = str(parameters.get("book_root") or "")
        if action_id == "book_campaign_create":
            args = ["book-campaign", "create", "--book-root", book_root,
                    "--mode", str(parameters.get("mode") or "PLAN")]
            if parameters.get("book_id"):
                args += ["--book-id", str(parameters["book_id"])]
            for key, flag in (("max_chapters", "--max-chapters"),
                              ("max_total_opportunities", "--max-total-opportunities"),
                              ("max_attempts_per_opportunity", "--max-attempts"),
                              ("max_total_candidates", "--max-total-candidates"),
                              ("max_model_calls", "--max-model-calls")):
                if parameters.get(key) is not None:
                    args += [flag, str(parameters[key])]
            return args
        if action_id == "book_campaign_manifest":
            return ["book-campaign", "manifest", str(parameters["campaign_id"]),
                    "--book-root", book_root]
        if action_id == "book_campaign_plan":
            args = ["book-campaign", "plan", str(parameters["campaign_id"]),
                    "--book-root", book_root]
            selective = str(parameters.get("selective", "all") or "all")
            if selective not in ("all", "new", "eligible", "author", "mixed"):
                raise ValueError(f"book_campaign_plan requires selective in "
                                 "all|new|eligible|author|mixed")
            if selective != "all":
                args += ["--selective", selective]
            return args
        if action_id == "book_campaign_run_chunk":
            return ["book-campaign", "run", str(parameters["run_id"]),
                    "--book-root", book_root,
                    "--max-wall-seconds", str(parameters.get("max_wall_seconds", 240))]
        if action_id == "book_campaign_pause":
            return ["book-campaign", "pause", str(parameters["run_id"]),
                    "--book-root", book_root]
        if action_id == "book_campaign_resume":
            return ["book-campaign", "resume", str(parameters["run_id"]),
                    "--book-root", book_root]
        if action_id == "book_campaign_cancel":
            return ["book-campaign", "cancel", str(parameters["run_id"]),
                    "--book-root", book_root]
        if action_id == "book_campaign_status":
            return ["book-campaign", "status", str(parameters["run_id"]),
                    "--book-root", book_root]
        if action_id == "book_strategy_experiment_run":
            return ["strategy-evolution", "run-experiment", str(parameters["experiment_id"]),
                    "--arm", str(parameters["arm"]), "--book-root", book_root,
                    "--max-wall-seconds", str(parameters.get("max_wall_seconds", 900))]
        raise ValueError(f"Unsupported Writer action: {action_id}")

    @staticmethod
    def _parse_envelope(output: str) -> dict[str, Any] | None:
        try:
            payload = json.loads((output or "").strip().splitlines()[-1])
        except (TypeError, ValueError, IndexError):
            return None
        return payload if isinstance(payload, dict) and "ok" in payload else None

    async def execute_action(
        self, action_id: str, parameters: dict[str, Any], context: ActionContext
    ) -> ActionResult:
        if action_id.startswith(("book_campaign_", "book_strategy_")):
            return await self._execute_campaign_action(action_id, parameters, context)
        if action_id != "audit_registered_books":
            raise ValueError(f"Unsupported Writer action: {action_id}")
        repo = (
            Path(context.application_repository_path)
            if context.application_repository_path
            else None
        )
        if repo is None or not repo.is_dir():
            return ActionResult(
                status="failed",
                error="Writer repository is not configured or unavailable.",
            )
        profile = str(parameters.get("profile") or PROFILE)
        if profile != PROFILE:
            return ActionResult(status="failed", error="Unsupported Writer editing profile.")
        target = AdapterTarget(
            name="Writer",
            application_id="writer",
            repository_paths=[(str(repo), "primary")],
            config=dict(context.config or {}),
        )
        executable, arguments, working_directory, timeout = self._command(
            target,
            repo,
            ["editing", "audit", "--all", "--profile", profile, "--json"],
        )
        try:
            result = await run_tool(
                executable,
                arguments,
                working_directory=working_directory,
                env_names=list((context.config or {}).get("env_names") or []),
                timeout_seconds=timeout,
            )
        except Exception as exc:
            return ActionResult(
                status="failed",
                error=f"{exc.__class__.__name__}: {str(exc)[:800]}",
            )
        parsed = self._parse_summary(result.stdout)
        if result.exit_code != 0 or parsed is None:
            return ActionResult(
                status="failed",
                output=(result.stdout or "")[-8000:],
                result={"stderr": (result.stderr or "")[-2000:]},
                exit_code=result.exit_code,
                error=(
                    "Writer audit failed or did not return the editing summary contract."
                    if result.exit_code == 0
                    else (result.stderr or result.stdout or "Writer audit failed")[-1200:]
                ),
            )
        summary, _books = parsed
        totals = summary.get("totals") or {}
        return ActionResult(
            status="succeeded",
            output=(
                f"Writer editing audit complete: {totals.get('audited', 0)} audited, "
                f"{totals.get('needs_review', 0)} need review, "
                f"{totals.get('stale', 0)} stale."
            ),
            result={
                "schema_version": SUMMARY_SCHEMA,
                "totals": totals,
                "store_path": summary.get("store_path"),
                "generated_at": summary.get("generated_at"),
            },
            artifact_ref=str(summary.get("store_path") or "writer:editing"),
            exit_code=0,
        )

    async def _execute_campaign_action(
        self, action_id: str, parameters: dict[str, Any], context: ActionContext
    ) -> ActionResult:
        repo = (
            Path(context.application_repository_path)
            if context.application_repository_path
            else None
        )
        if repo is None or not repo.is_dir():
            return ActionResult(
                status="failed",
                error="Writer repository is not configured or unavailable.",
            )
        try:
            self.validate_action(action_id, parameters, context)
        except ValueError as exc:
            return ActionResult(status="failed", error=str(exc))
        target = AdapterTarget(
            name="Writer",
            application_id="writer",
            repository_paths=[(str(repo), "primary")],
            config=dict(context.config or {}),
        )
        executable, arguments, working_directory, timeout = self._command(
            target, repo, self._campaign_args(action_id, parameters)
        )
        try:
            result = await run_tool(
                executable,
                arguments,
                working_directory=working_directory,
                env_names=list((context.config or {}).get("env_names") or []),
                timeout_seconds=timeout,
            )
        except Exception as exc:
            return ActionResult(
                status="failed",
                error=f"{exc.__class__.__name__}: {str(exc)[:800]}",
            )
        envelope = self._parse_envelope(result.stdout)
        if result.exit_code != 0 or envelope is None or not envelope.get("ok"):
            detail = ""
            if envelope is not None:
                detail = str((envelope.get("result") or {}).get("error", "") or "")[:800]
            return ActionResult(
                status="failed",
                output=(result.stdout or "")[-8000:],
                result={"stderr": (result.stderr or "")[-2000:]},
                exit_code=result.exit_code,
                error=detail or (result.stderr or result.stdout or "Writer campaign failed")[-1200:],
            )
        return ActionResult(
            status="succeeded",
            output=f"Writer {action_id} complete.",
            result=envelope.get("result") or {},
            artifact_ref="writer:book-campaigns",
            exit_code=0,
        )

    @staticmethod
    def _command(
        target: AdapterTarget, repo: Path, default_arguments: list[str]
    ) -> tuple[str, list[str], str, float]:
        config = target.config or {}
        executable = str(
            config.get("executable") or (repo / "venv" / "Scripts" / "writer.exe")
        )
        if default_arguments[:2] == ["editing", "summary"]:
            arguments = list(config.get("arguments") or default_arguments)
        else:
            arguments = default_arguments
        working_directory = str(config.get("working_directory") or repo)
        timeout = float(config.get("timeout_seconds", 300))
        return executable, arguments, working_directory, timeout

    @staticmethod
    def _parse_summary(
        output: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        try:
            payload = json.loads(output)
        except (TypeError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        if not bool(payload.get("ok")):
            return None
        meta = payload.get("meta") or {}
        if str(meta.get("schema_version") or "") != CLI_SCHEMA:
            return None
        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        if str(result.get("schema_version") or "") != SUMMARY_SCHEMA:
            return None
        books = result.get("books")
        if not isinstance(books, list):
            return None
        parsed_books = [book for book in books if isinstance(book, dict)]
        if len(parsed_books) != len(books):
            return None
        for book in parsed_books:
            if not isinstance(book.get("project_id"), str) or not book.get("project_id"):
                return None
            if not isinstance(book.get("title"), str) or not book.get("title"):
                return None
            if not isinstance(book.get("status"), str) or not book.get("status"):
                return None
        return result, parsed_books
