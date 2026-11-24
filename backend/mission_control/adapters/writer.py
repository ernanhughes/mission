"""Writer Editing integration.

Mission Control consumes Writer's versioned CLI JSON contract. It does not
import Writer's parser or scoring code, and it does not edit manuscripts.

The adapter reads ``writer editing summary --json``. A separately approved
``audit_registered_books`` action runs Writer's read-only audit; the action
writes Writer-owned report artifacts only.
"""

from __future__ import annotations

import json
import re
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
from mission_control.publication.maintenance import MAINTENANCE_POLICY_VERSION

CLI_SCHEMA = "writer.editing.cli.v1"
SUMMARY_SCHEMA = "writer-editing-summary-v1"
REPORT_SCHEMA = "writer-editing-report-v1"
RESOURCE_TYPE = "writer_editing_book"
PROFILE = "technical-nonfiction-v1"
_BOOK_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")

#: Receipt schema for the governed deterministic MRI observation (M3).
#: This is Mission Control's execution record, not a Writer contract: it
#: proves the operation ran with model usage disabled and where its
#: artifacts landed. Current-ness is decided exclusively by the read-only
#: projection, never by this receipt.
MRI_OBSERVE_RECEIPT_SCHEMA = "mc.mri_observe_chapter.v1"

#: Receipt schema for the automatic deterministic Writer post observation
#: (BLOG-01 D5). Same contract as the governed M3 receipt: proves the
#: operation ran with model usage disabled. Current-ness is decided
#: exclusively by the read-only projection, never by this receipt.
POST_OBSERVE_RECEIPT_SCHEMA = "mc.writer_observe_post.v1"

#: Hard bound for automatic in-process post analysis. Larger files are
#: refused with an explicit reason instead of consuming unbounded resources.
BLOG_AUTO_MAX_BYTES = 2_000_000


def _require_identity(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    if text.startswith("/") or text.startswith("\\") or ".." in Path(text).parts:
        raise ValueError(f"{name} must be a site-relative post path")
    if any(not part for part in Path(text).parts):
        raise ValueError(f"{name} must not contain empty segments")
    return text


def _validate_post_observe(parameters: dict[str, Any]) -> tuple[str, str, str]:
    """Prerequisite checks before an automatic post observation may run."""
    from mission_control.websites import maintenance as _blog_maintenance

    policy = str(parameters.get("policy_version") or "").strip()
    if policy != _blog_maintenance.BLOG_AUTO_POLICY_VERSION:
        raise ValueError(
            "policy_version must name the current automatic-maintenance "
            f"policy ({_blog_maintenance.BLOG_AUTO_POLICY_VERSION})."
        )
    website_id = str(parameters.get("website_id") or "").strip()
    if not website_id:
        raise ValueError("website_id is required")
    identity = _require_identity(parameters.get("article_identity"), "article_identity")
    _require_existing_dir(parameters.get("blog_dir"), "blog_dir")
    return website_id, identity, str(parameters.get("blog_dir"))


#: Pinned deterministic flags. Every flag that could enable model, embedding,
#: or semantic-adjudication spend is fixed here; adding spend requires a new
#: action, never a parameter.
_MRI_DETERMINISTIC_FLAGS = [
    "--observer",
    "deterministic",
    "--quality-model",
    "none",
    "--semantic-model",
    "none",
    "--beat-mode",
    "deterministic",
]
_MRI_PROFILES = ("technical", "fiction")


def _mri_observe_argv(
    chapter_file: str, output_dir: str, profile: str, metadata_file: str | None
) -> list[str]:
    """Exact Writer CLI argv for a deterministic chapter observation."""
    argv = ["mri", "chapter", chapter_file, "--format", "json"]
    argv.extend(_MRI_DETERMINISTIC_FLAGS)
    argv.extend(["--profile", profile])
    if metadata_file:
        argv.extend(["--metadata", metadata_file])
    argv.extend(["--output-dir", output_dir])
    return argv


def _require_existing_file(value: Any, name: str, suffixes: tuple[str, ...]) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    path = Path(text)
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if path.suffix.casefold() not in suffixes:
        raise ValueError(f"{name} must end in {', '.join(suffixes)}")
    try:
        if not path.is_file():
            raise ValueError(f"{name} does not exist: {path}")
    except OSError as exc:
        raise ValueError(f"{name} cannot be accessed: {exc}") from exc
    return path


def _require_existing_dir(value: Any, name: str) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    path = Path(text)
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    try:
        if not path.is_dir():
            raise ValueError(f"{name} does not exist: {path}")
    except OSError as exc:
        raise ValueError(f"{name} cannot be accessed: {exc}") from exc
    return path


def _validate_mri_observe_chapter(parameters: dict[str, Any]) -> None:
    """Prerequisite checks before a deterministic observation may be queued."""
    profile = str(parameters.get("profile") or "technical")
    if profile not in _MRI_PROFILES:
        raise ValueError(f"Unsupported MRI profile: {profile}")
    _require_existing_file(parameters.get("chapter_file"), "chapter_file", (".md",))
    metadata = parameters.get("metadata_file")
    if metadata is not None and str(metadata).strip():
        _require_existing_file(metadata, "metadata_file", (".yaml", ".yml"))
    _require_existing_dir(parameters.get("output_dir"), "output_dir")


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
            id="audit_registered_book",
            title="Run a Writer editing audit for one registered book",
            description=(
                "Runs Writer's actual read-only editing audit for one registered "
                "book. Writer writes its own report artifacts under .writer/editing; "
                "no manuscript is edited. book_id must be a registered book "
                "identifier resolved by Mission Control."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "book_id": {"type": "string"},
                    "profile": {
                        "type": "string",
                        "enum": [PROFILE],
                        "default": PROFILE,
                    },
                },
                "required": ["book_id"],
                "additionalProperties": False,
            },
        ),
        ActionSpec(
            id="mri_observe_chapter",
            title="Run deterministic MRI observation for one chapter file",
            description=(
                "Runs Writer's MRI chapter command with model usage disabled "
                "by construction (--observer deterministic --quality-model none "
                "--semantic-model none --beat-mode deterministic). Writes "
                "<stem>.mri.{json,md} under output_dir only; never modifies "
                "manuscripts. The persisted execution receipt records "
                "provenance only: whether the analysis is current is decided "
                "exclusively by the read-only projection comparing the stored "
                "report against the live chapter, never by this receipt."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "chapter_file": {"type": "string"},
                    "metadata_file": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "profile": {
                        "type": "string",
                        "enum": ["technical", "fiction"],
                        "default": "technical",
                    },
                },
                "required": ["chapter_file", "output_dir"],
                "additionalProperties": False,
            },
        ),
        ActionSpec(
            id="mri_observe_chapter_auto",
            title="Automatic deterministic MRI observation for one chapter file",
            description=(
                "Standing-policy twin of mri_observe_chapter: identical "
                "deterministic flags and receipt contract, but authorized "
                "once by the automatic-maintenance policy instead of per "
                "run. Runs only when the maintenance scheduler dispatches "
                "it for eligible work; every run persists a full receipt row."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=False,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "chapter_file": {"type": "string"},
                    "metadata_file": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "profile": {
                        "type": "string",
                        "enum": ["technical", "fiction"],
                        "default": "technical",
                    },
                    "policy_version": {"type": "string"},
                },
                "required": ["chapter_file", "output_dir", "policy_version"],
                "additionalProperties": False,
            },
        ),
        ActionSpec(
            id="writer_observe_post_auto",
            title="Automatic deterministic Writer observation for one blog post",
            description=(
                "Runs Writer's deterministic artifact detector in-process "
                "against one post's live body bytes (no models, no writes, "
                "no manuscripts modified). Authorized once by the "
                "automatic-maintenance policy instead of per run; runs only "
                "when the blog maintenance scheduler dispatches it for "
                "eligible work. The persisted receipt records provenance "
                "only: current-ness is decided by the read-only projection."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=False,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "website_id": {"type": "string"},
                    "article_identity": {"type": "string"},
                    "blog_dir": {"type": "string"},
                    "policy_version": {"type": "string"},
                },
                "required": [
                    "website_id",
                    "article_identity",
                    "blog_dir",
                    "policy_version",
                ],
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
                    "mode": {
                        "type": "string",
                        "enum": ["DISCOVER", "ASSESS", "PLAN", "IMPROVE_CANDIDATES", "REVIEW"],
                        "default": "PLAN",
                    },
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
                    "selective": {
                        "type": "string",
                        "enum": ["all", "new", "eligible", "author", "mixed"],
                        "default": "all",
                    },
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
        if action_id == "audit_registered_book":
            book_id = str(parameters.get("book_id") or "").strip()
            if not book_id:
                raise ValueError("book_id is required")
            if not _BOOK_ID.match(book_id):
                raise ValueError("book_id is not a valid registered book identifier")
            profile = str(parameters.get("profile") or PROFILE)
            if profile != PROFILE:
                raise ValueError(f"Unsupported Writer editing profile: {profile}")
            return
        if action_id == "audit_registered_books":
            profile = str(parameters.get("profile") or PROFILE)
            if profile != PROFILE:
                raise ValueError(f"Unsupported Writer editing profile: {profile}")
            return
        if action_id == "mri_observe_chapter":
            _validate_mri_observe_chapter(parameters)
            return
        if action_id == "mri_observe_chapter_auto":
            policy = str(parameters.get("policy_version") or "").strip()
            if policy != MAINTENANCE_POLICY_VERSION:
                raise ValueError(
                    "policy_version must name the current automatic-maintenance "
                    f"policy ({MAINTENANCE_POLICY_VERSION})."
                )
            _validate_mri_observe_chapter(parameters)
            return
        if action_id == "writer_observe_post_auto":
            _validate_post_observe(parameters)
            return
        if action_id in {
            "book_campaign_create",
            "book_campaign_manifest",
            "book_campaign_plan",
            "book_campaign_run_chunk",
            "book_campaign_pause",
            "book_campaign_resume",
            "book_campaign_cancel",
            "book_campaign_status",
            "book_strategy_experiment_run",
        }:
            if action_id in {"book_campaign_manifest", "book_campaign_plan"} and not parameters.get(
                "campaign_id"
            ):
                raise ValueError(f"{action_id} requires campaign_id")
            if action_id in {
                "book_campaign_run_chunk",
                "book_campaign_pause",
                "book_campaign_resume",
                "book_campaign_cancel",
                "book_campaign_status",
            } and not parameters.get("run_id"):
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
            args = [
                "book-campaign",
                "create",
                "--book-root",
                book_root,
                "--mode",
                str(parameters.get("mode") or "PLAN"),
            ]
            if parameters.get("book_id"):
                args += ["--book-id", str(parameters["book_id"])]
            for key, flag in (
                ("max_chapters", "--max-chapters"),
                ("max_total_opportunities", "--max-total-opportunities"),
                ("max_attempts_per_opportunity", "--max-attempts"),
                ("max_total_candidates", "--max-total-candidates"),
                ("max_model_calls", "--max-model-calls"),
            ):
                if parameters.get(key) is not None:
                    args += [flag, str(parameters[key])]
            return args
        if action_id == "book_campaign_manifest":
            return [
                "book-campaign",
                "manifest",
                str(parameters["campaign_id"]),
                "--book-root",
                book_root,
            ]
        if action_id == "book_campaign_plan":
            args = [
                "book-campaign",
                "plan",
                str(parameters["campaign_id"]),
                "--book-root",
                book_root,
            ]
            selective = str(parameters.get("selective", "all") or "all")
            if selective not in ("all", "new", "eligible", "author", "mixed"):
                raise ValueError(
                    "book_campaign_plan requires selective in all|new|eligible|author|mixed"
                )
            if selective != "all":
                args += ["--selective", selective]
            return args
        if action_id == "book_campaign_run_chunk":
            return [
                "book-campaign",
                "run",
                str(parameters["run_id"]),
                "--book-root",
                book_root,
                "--max-wall-seconds",
                str(parameters.get("max_wall_seconds", 240)),
            ]
        if action_id == "book_campaign_pause":
            return ["book-campaign", "pause", str(parameters["run_id"]), "--book-root", book_root]
        if action_id == "book_campaign_resume":
            return ["book-campaign", "resume", str(parameters["run_id"]), "--book-root", book_root]
        if action_id == "book_campaign_cancel":
            return ["book-campaign", "cancel", str(parameters["run_id"]), "--book-root", book_root]
        if action_id == "book_campaign_status":
            return ["book-campaign", "status", str(parameters["run_id"]), "--book-root", book_root]
        if action_id == "book_strategy_experiment_run":
            return [
                "strategy-evolution",
                "run-experiment",
                str(parameters["experiment_id"]),
                "--arm",
                str(parameters["arm"]),
                "--book-root",
                book_root,
                "--max-wall-seconds",
                str(parameters.get("max_wall_seconds", 900)),
            ]
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
        if action_id == "audit_registered_book":
            return await self._execute_scoped_audit(action_id, parameters, context)
        if action_id in ("mri_observe_chapter", "mri_observe_chapter_auto"):
            return await self._execute_mri_observe_chapter(action_id, parameters, context)
        if action_id == "writer_observe_post_auto":
            return await self._execute_post_observe(action_id, parameters, context)
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

    async def _execute_scoped_audit(
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
        book_id = str(parameters.get("book_id"))
        profile = str(parameters.get("profile") or PROFILE)
        target = AdapterTarget(
            name="Writer",
            application_id="writer",
            repository_paths=[(str(repo), "primary")],
            config=dict(context.config or {}),
        )
        executable, arguments, working_directory, timeout = self._command(
            target,
            repo,
            ["editing", "audit", book_id, "--profile", profile, "--json"],
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
        report = (envelope or {}).get("result")
        meta = (envelope or {}).get("meta") or {}
        valid = (
            result.exit_code == 0
            and envelope is not None
            and bool(envelope.get("ok"))
            and str(meta.get("schema_version") or "") == CLI_SCHEMA
            and isinstance(report, dict)
            and str(report.get("schema_version") or "") == REPORT_SCHEMA
        )
        if not valid:
            return ActionResult(
                status="failed",
                output=(result.stdout or "")[-8000:],
                result={"stderr": (result.stderr or "")[-2000:]},
                exit_code=result.exit_code,
                error=(
                    "Writer scoped audit failed or did not return the editing report contract."
                    if result.exit_code == 0
                    else (result.stderr or result.stdout or "Writer audit failed")[-1200:]
                ),
            )
        findings = [f for f in (report.get("findings") or []) if isinstance(f, dict)]
        counts: dict[str, int] = {}
        for finding in findings:
            severity = str(finding.get("severity") or "unknown").casefold()
            counts[severity] = counts.get(severity, 0) + 1
        artifacts = [str(item) for item in (envelope.get("artifacts") or [])]
        return ActionResult(
            status="succeeded",
            output=(
                f"Writer audit for {book_id}: {len(findings)} finding(s) "
                f"(high={counts.get('high', 0)}, medium={counts.get('medium', 0)}, "
                f"low={counts.get('low', 0)}), partial={bool(report.get('partial'))}."
            ),
            result={
                "schema_version": REPORT_SCHEMA,
                "book_id": book_id,
                "title": (report.get("book") or {}).get("title"),
                "report_id": report.get("report_id"),
                "profile": report.get("profile"),
                "canonical_fingerprint": report.get("canonical_fingerprint"),
                "scope": report.get("scope"),
                "source_revision": (report.get("book") or {}).get("source_revision"),
                "source_dirty": (report.get("book") or {}).get("source_dirty"),
                "partial": bool(report.get("partial")),
                "finding_counts": counts,
                "findings_total": len(findings),
                "findings": findings[:200],
                "limitations": list(report.get("limitations") or [])[:10],
                "generated_at": report.get("generated_at"),
            },
            artifact_ref=(artifacts[0] if artifacts else "writer:editing"),
            exit_code=0,
        )

    async def _execute_mri_observe_chapter(
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
        chapter_file = str(parameters.get("chapter_file"))
        metadata_file = parameters.get("metadata_file")
        metadata_text = str(metadata_file).strip() if metadata_file else ""
        output_dir = str(parameters.get("output_dir"))
        profile = str(parameters.get("profile") or "technical")
        target = AdapterTarget(
            name="Writer",
            application_id="writer",
            repository_paths=[(str(repo), "primary")],
            config=dict(context.config or {}),
        )
        executable, arguments, working_directory, timeout = self._command(
            target,
            repo,
            _mri_observe_argv(
                chapter_file,
                output_dir,
                profile,
                metadata_text or None,
            ),
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
        return self._parse_mri_observe_result(
            result.stdout,
            result.stderr,
            result.exit_code,
            chapter_file=chapter_file,
            output_dir=output_dir,
            metadata_file=metadata_text or None,
            profile=profile,
        )

    @staticmethod
    def _parse_mri_observe_result(
        stdout: str | None,
        stderr: str | None,
        exit_code: int | None,
        *,
        chapter_file: str,
        output_dir: str,
        metadata_file: str | None = None,
        profile: str = "technical",
    ) -> ActionResult:
        """Strict receipt parsing for a deterministic MRI chapter run.

        Success requires: exit 0, a single JSON document, status
        ``succeeded`` or ``succeeded_with_warnings`` (explicit deterministic
        fallbacks are preserved, never laundered into a clean success), a
        report carrying a non-empty ``snapshot_hash`` and a provenance block,
        and the referenced JSON artifact on disk. Anything else is a failed
        execution with diagnostics. The receipt records what ran; it never
        declares the analysis current.
        """
        try:
            payload = json.loads((stdout or "").strip())
        except (TypeError, ValueError):
            payload = None
        report = (payload or {}).get("report") if isinstance(payload, dict) else None
        provenance = (report or {}).get("provenance") if isinstance(report, dict) else {}
        snapshot = (report or {}).get("snapshot_hash") if isinstance(report, dict) else None
        status = str((payload or {}).get("status") or "") if isinstance(payload, dict) else ""
        raw_warnings = provenance.get("warnings")
        warnings = list(raw_warnings) if isinstance(raw_warnings, list) else []
        json_path = (payload or {}).get("json_path") if isinstance(payload, dict) else None
        md_path = (payload or {}).get("markdown_path") if isinstance(payload, dict) else None
        artifact_ok = False
        if isinstance(json_path, str) and json_path:
            try:
                artifact_ok = Path(json_path).is_file()
            except OSError:
                artifact_ok = False
        valid = (
            exit_code == 0
            and isinstance(payload, dict)
            and status in ("succeeded", "succeeded_with_warnings")
            and isinstance(report, dict)
            and isinstance(snapshot, str)
            and bool(snapshot)
            and isinstance(provenance, dict)
            and artifact_ok
        )
        if not valid:
            detail = ""
            if isinstance(payload, dict):
                detail = f" Writer status: {status}; report errors: {report.get('errors') if isinstance(report, dict) else 'absent'}."
            return ActionResult(
                status="failed",
                output=(stdout or "")[-8000:],
                result={"stderr": (stderr or "")[-2000:]},
                exit_code=exit_code,
                error=(
                    "Writer deterministic MRI observation did not succeed:"
                    + detail
                    + " No artifact was accepted; the projection is unchanged."
                    if exit_code == 0
                    else (stderr or stdout or "Writer MRI observation failed")[-1200:]
                ),
            )
        try:
            live_text = Path(chapter_file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ActionResult(
                status="failed",
                error=f"Report was written but the chapter cannot be re-read: {exc}.",
            )
        import hashlib as _hashlib

        live_digest = _hashlib.sha256(live_text.encode("utf-8")).hexdigest()
        clean = status == "succeeded"
        from mission_control.publication.maintenance import build_auto_inputs

        auto_inputs = build_auto_inputs(
            source_digest=live_digest,
            metadata_file=metadata_file,
            profile=profile,
        )
        return ActionResult(
            status="succeeded",
            output=(
                f"Deterministic MRI observation complete ({status}): "
                f"{Path(chapter_file).name} -> {json_path} (snapshot {snapshot[:12]}…). "
                + (
                    "Warnings preserved in the receipt; review them before relying on the analysis. "
                    if not clean
                    else ""
                )
                + "Receipt only: current-ness is decided by the projection, not this run."
            ),
            result={
                "schema_version": MRI_OBSERVE_RECEIPT_SCHEMA,
                "status": status,
                "clean": clean,
                "warnings": list(warnings) if isinstance(warnings, list) else [],
                "snapshot_hash": snapshot,
                "live_source_digest": live_digest,
                "receipt_digest_match": snapshot == live_digest,
                "auto_inputs": auto_inputs,
                "auto_fingerprint": auto_inputs["fingerprint"],
                "json_path": json_path,
                "md_path": md_path,
                "chapter_file": chapter_file,
                "output_dir": output_dir,
                "provenance": {
                    "observer_mode": provenance.get("observer_mode"),
                    "observer_model": provenance.get("observer_model"),
                    "quality_model": provenance.get("quality_model"),
                    "beat_mode": provenance.get("beat_mode"),
                    "semantic_model": provenance.get("semantic_model"),
                    "embed_runtime_used": provenance.get("embed_runtime_used"),
                    "fallback_used": provenance.get("fallback_used"),
                    "alignment_version": provenance.get("alignment_version"),
                    "observer_prompt_version": provenance.get("observer_prompt_version"),
                    "generated_at": provenance.get("generated_at"),
                },
            },
            artifact_ref=str(json_path),
            exit_code=0,
        )

    async def _execute_post_observe(
        self, action_id: str, parameters: dict[str, Any], context: ActionContext
    ) -> ActionResult:
        from datetime import datetime, timezone

        from mission_control.websites import post_artifact as _post_artifact
        from mission_control.websites import maintenance as _blog_maintenance

        _auto_fingerprint = _blog_maintenance.auto_fingerprint

        try:
            self.validate_action(action_id, parameters, context)
        except ValueError as exc:
            return ActionResult(status="failed", error=str(exc))
        website_id = str(parameters.get("website_id"))
        identity = str(parameters.get("article_identity"))
        blog_dir = Path(str(parameters.get("blog_dir")))
        try:
            candidate = blog_dir / Path(*Path(identity).parts)
        except (OSError, ValueError) as exc:
            return ActionResult(status="failed", error=f"Identity does not map to a file: {exc}")
        try:
            size = candidate.stat().st_size
        except OSError as exc:
            return ActionResult(status="failed", error=f"Post file is not accessible: {exc}")
        if size > BLOG_AUTO_MAX_BYTES:
            return ActionResult(
                status="failed",
                error=(
                    f"Post file is {size} bytes, over the automatic-observation "
                    f"budget of {BLOG_AUTO_MAX_BYTES}; refusing instead of "
                    "consuming unbounded resources."
                ),
            )
        observed_at = datetime.now(timezone.utc).isoformat()
        try:
            envelope = _post_artifact.artifact_envelope_for_live_post(
                blog_dir, identity=identity, observed_at=observed_at
            )
        except FileNotFoundError as exc:
            return ActionResult(status="failed", error=str(exc))
        except Exception as exc:
            return ActionResult(
                status="failed", error=f"{exc.__class__.__name__}: {str(exc)[:800]}"
            )
        if envelope is None:
            return ActionResult(
                status="failed",
                error="Post body cannot be mapped to evaluated bytes; no observation was made.",
            )
        work = envelope.get("work_object", {})
        provenance = envelope.get("provenance", {})
        fingerprint = _auto_fingerprint(
            source_digest=str(work.get("source_hash") or ""),
            metadata_digest=str(work.get("content_sha256") or ""),
            profile="post",
            flags_version=_blog_maintenance.BLOG_FLAGS_VERSION,
            policy_version=_blog_maintenance.BLOG_AUTO_POLICY_VERSION,
        )
        return ActionResult(
            status="succeeded",
            output=(
                f"Deterministic Writer observation complete for {identity} "
                f"(status {envelope.get('status')}, "
                f"{len(envelope.get('findings') or [])} finding(s)). "
                "Receipt only: current-ness is decided by the projection, not this run."
            ),
            result={
                "schema_version": POST_OBSERVE_RECEIPT_SCHEMA,
                "status": envelope.get("status"),
                "evaluation_id": envelope.get("evaluation_id"),
                "source_digest": work.get("source_hash"),
                "content_digest": work.get("content_sha256"),
                "auto_inputs": {
                    "source_digest": work.get("source_hash"),
                    "metadata_digest": work.get("content_sha256"),
                    "profile": "post",
                    "flags_version": _blog_maintenance.BLOG_FLAGS_VERSION,
                    "policy_version": _blog_maintenance.BLOG_AUTO_POLICY_VERSION,
                    "fingerprint": fingerprint,
                },
                "auto_fingerprint": fingerprint,
                "producer": provenance
                and {
                    "runtime_name": (envelope.get("producer") or {}).get("runtime_name"),
                    "method": (envelope.get("producer") or {}).get("method"),
                    "method_version": (envelope.get("producer") or {}).get("method_version"),
                },
                "finding_count": len(envelope.get("findings") or []),
                "observed_at": envelope.get("observed_at"),
            },
            artifact_ref=f"writer-post-observation:{website_id}:{identity}:{str(work.get('source_hash') or '')[:12]}",
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
                error=detail
                or (result.stderr or result.stdout or "Writer campaign failed")[-1200:],
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
        executable = str(config.get("executable") or (repo / "venv" / "Scripts" / "writer.exe"))
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
