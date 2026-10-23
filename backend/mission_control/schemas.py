"""Pydantic contracts for the local REST API."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mission_control.core.paths import (
    normalize_absolute_path,
    validate_arguments,
    validate_env_names,
    validate_executable,
    validate_url,
)

ApplicationCategory = Literal[
    "research", "quality", "commercial", "writing", "publishing", "execution", "supporting", "other"
]
LaunchType = Literal["none", "command", "server", "url", "editor"]
HealthType = Literal["none", "http", "tcp", "process"]
ProjectKind = Literal["book", "project", "application", "research", "outcome", "supporting"]
ProjectStatus = Literal["active", "paused", "waiting", "complete", "archived"]
BookStatus = Literal["planned", "drafting", "editorial_review", "verification", "production", "published"]
TaskStatus = Literal["open", "in_progress", "done", "blocked", "cancelled"]
ReviewState = Literal["pending", "accepted", "deferred", "rejected"]
ApplicationState = Literal[
    "running", "stopped", "misconfigured", "not_checked", "stale", "launch_failed", "unavailable"
]

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class RawModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _clean_path(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    return normalize_absolute_path(str(value))


class LaunchDefinitionInput(RawModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    launch_type: LaunchType = "none"
    executable: str | None = None
    arguments: list[str] = Field(default_factory=list)
    working_directory: str | None = None
    env_names: list[str] = Field(default_factory=list)
    browser_url: str | None = None
    health_type: HealthType = "none"
    health_url: str | None = None
    expected_port: int | None = Field(default=None, ge=1, le=65535)
    is_primary: bool = False
    enabled: bool = False
    verified: bool = False
    verification_note: str = ""
    shutdown_behavior: Literal["terminate", "wait"] = "terminate"

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str | None) -> str | None:
        if value is not None and not _ID.match(value):
            raise ValueError("Launch definition id must be lowercase letters, numbers and hyphens")
        return value

    @field_validator("executable")
    @classmethod
    def check_executable(cls, value: str | None) -> str | None:
        return validate_executable(value)

    @field_validator("arguments")
    @classmethod
    def check_arguments(cls, value: list[str]) -> list[str]:
        return validate_arguments(value)

    @field_validator("env_names")
    @classmethod
    def check_env(cls, value: list[str]) -> list[str]:
        return validate_env_names(value)

    @field_validator("working_directory")
    @classmethod
    def check_working_directory(cls, value: str | None) -> str | None:
        return _clean_path(value)

    @field_validator("browser_url")
    @classmethod
    def check_browser_url(cls, value: str | None) -> str | None:
        return validate_url(value, field="browser_url")

    @field_validator("health_url")
    @classmethod
    def check_health_url(cls, value: str | None) -> str | None:
        return validate_url(value, field="health_url")

    @model_validator(mode="after")
    def check_required_fields(self) -> "LaunchDefinitionInput":
        if self.launch_type in {"command", "server"} and not self.executable:
            raise ValueError("An executable is required for command and server launches")
        if self.launch_type == "url" and not self.browser_url:
            raise ValueError("A browser_url is required for URL launches")
        if self.health_type == "http" and self.health_url and not self.health_url.startswith(("http://", "https://")):
            raise ValueError("HTTP health checks require an http(s) URL")
        return self


class ControlPolicy(RawModel):
    allow_launch: bool = True
    confirmation_required: bool = False


class ApplicationCreate(RawModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    category: ApplicationCategory = "supporting"
    icon: str = Field(default="", max_length=4)
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    pinned: bool = False
    display_order: int = 100
    repository_path: str | None = None
    additional_paths: list[str] = Field(default_factory=list)
    working_directory: str | None = None
    documentation_paths: list[str] = Field(default_factory=list)
    output_paths: list[str] = Field(default_factory=list)
    integration_adapter: str | None = None
    adapter_enabled: bool = False
    adapter_config: dict[str, Any] = Field(default_factory=dict)
    related_projects: list[str] = Field(default_factory=list)
    related_books: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    control_policy: ControlPolicy = Field(default_factory=ControlPolicy)
    notes: str = ""
    launch_definitions: list[LaunchDefinitionInput] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def check_id(cls, value: str | None) -> str | None:
        if value is not None and not _ID.match(value):
            raise ValueError("Application id must be lowercase letters, numbers and hyphens")
        return value

    @field_validator("repository_path", "working_directory")
    @classmethod
    def check_path(cls, value: str | None) -> str | None:
        return _clean_path(value)

    @field_validator("additional_paths", "documentation_paths", "output_paths")
    @classmethod
    def check_paths(cls, value: list[str]) -> list[str]:
        return [_clean_path(item) for item in value if item and str(item).strip()]  # type: ignore[misc]


class ApplicationUpdate(RawModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    category: ApplicationCategory | None = None
    icon: str | None = Field(default=None, max_length=4)
    tags: list[str] | None = None
    enabled: bool | None = None
    pinned: bool | None = None
    display_order: int | None = None
    repository_path: str | None = None
    additional_paths: list[str] | None = None
    working_directory: str | None = None
    documentation_paths: list[str] | None = None
    output_paths: list[str] | None = None
    integration_adapter: str | None = None
    adapter_enabled: bool | None = None
    adapter_config: dict[str, Any] | None = None
    related_projects: list[str] | None = None
    related_books: list[str] | None = None
    outcomes: list[str] | None = None
    dependencies: list[str] | None = None
    control_policy: ControlPolicy | None = None
    notes: str | None = None
    archived: bool | None = None
    launch_definitions: list[LaunchDefinitionInput] | None = None

    @field_validator("repository_path", "working_directory")
    @classmethod
    def check_path(cls, value: str | None) -> str | None:
        return _clean_path(value)

    @field_validator("additional_paths", "documentation_paths", "output_paths")
    @classmethod
    def check_paths(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [_clean_path(item) for item in value if item and str(item).strip()]  # type: ignore[misc]


class ActionState(BaseModel):
    enabled: bool
    reason: str | None = None


class ApplicationActions(BaseModel):
    launch: ActionState
    stop: ActionState
    restart: ActionState
    open_repository: ActionState
    open_documentation: ActionState
    open_url: ActionState
    logs: ActionState
    check_health: ActionState


class ApplicationStatus(BaseModel):
    state: ApplicationState
    label: str
    detail: str = ""
    ownership: Literal["managed", "external", "none", "unknown"] = "none"
    observed_at: str | None = None
    stale: bool = False
    health_state: str | None = None
    process_id: str | None = None


class LaunchDefinitionRead(BaseModel):
    id: str
    application_id: str
    name: str
    launch_type: LaunchType
    executable: str | None
    arguments: list[str]
    working_directory: str | None
    env_names: list[str]
    browser_url: str | None
    health_type: HealthType
    health_url: str | None
    expected_port: int | None
    is_primary: bool
    enabled: bool
    verified: bool
    verification_note: str
    shutdown_behavior: str


class LaunchRequest(RawModel):
    launch_id: str | None = None
    confirm: bool = False


class ApplicationRead(BaseModel):
    id: str
    name: str
    description: str
    category: ApplicationCategory
    icon: str
    tags: list[str]
    enabled: bool
    archived: bool
    pinned: bool
    display_order: int
    repository_path: str | None
    additional_paths: list[str]
    working_directory: str | None
    documentation_paths: list[str]
    output_paths: list[str]
    integration_adapter: str | None
    adapter_enabled: bool
    adapter_config: dict[str, Any]
    related_projects: list[str]
    related_books: list[str]
    outcomes: list[str]
    dependencies: list[str]
    control_policy: ControlPolicy
    source: str
    notes: str
    launch_definitions: list[LaunchDefinitionRead]
    status: ApplicationStatus
    actions: ApplicationActions
    last_launch_success_at: str | None
    last_launch_failure_at: str | None
    last_failure_detail: str | None
    created_at: str
    updated_at: str


class ProcessRead(BaseModel):
    id: str
    application_id: str
    application_name: str | None = None
    launch_definition_id: str | None
    pid: int | None
    status: str
    started_at: str
    ended_at: str | None
    exit_code: int | None
    log_available: bool
    working_directory: str | None
    command_preview: str | None
    owned: bool
    reattached: bool
    error: str | None


class LogRead(BaseModel):
    process_id: str
    lines: list[str]
    truncated: bool
    path: str | None


class RepositoryRead(BaseModel):
    id: str
    name: str
    path: str
    classification: str
    confidence: float
    evidence: list[str]
    role: str | None = None
    source_root: str
    is_git: bool
    branch: str | None
    commit_hash: str | None
    last_commit_at: str | None
    dirty: bool | None
    accessible: bool
    candidate: bool
    last_observed_at: str | None
    notes: str


class BookRead(BaseModel):
    id: str
    project_id: str
    project_name: str | None = None
    title: str
    status: BookStatus
    current_milestone: str
    next_action: str
    manuscript_paths: list[str]
    implementation_paths: list[str]
    published_url: str | None
    local_url: str | None
    quality_review_state: str
    last_activity_at: str | None
    priority: int | None = None
    latest_checkpoint: "CheckpointRead | None" = None
    repository_action: ActionState | None = None


class BookUpdate(RawModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: BookStatus | None = None
    current_milestone: str | None = None
    next_action: str | None = None
    manuscript_paths: list[str] | None = None
    implementation_paths: list[str] | None = None
    published_url: str | None = None
    local_url: str | None = None
    quality_review_state: str | None = None

    @field_validator("manuscript_paths", "implementation_paths")
    @classmethod
    def check_paths(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [_clean_path(item) for item in value if item and str(item).strip()]  # type: ignore[misc]

    @field_validator("published_url", "local_url")
    @classmethod
    def check_urls(cls, value: str | None) -> str | None:
        return validate_url(value)


class ProjectCreate(RawModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    kind: ProjectKind = "project"
    status: ProjectStatus = "active"
    pinned: bool = False
    display_order: int = 100
    current_milestone: str = ""
    next_action: str = ""
    notes: str = ""
    book_title: str | None = Field(default=None, max_length=200)
    repository_path: str | None = None

    @field_validator("repository_path")
    @classmethod
    def check_repository_path(cls, value: str | None) -> str | None:
        return _clean_path(value)


class BookCreate(RawModel):
    project_id: str
    title: str = Field(min_length=1, max_length=200)
    status: BookStatus = "planned"
    current_milestone: str = ""
    next_action: str = ""
    manuscript_paths: list[str] = Field(default_factory=list)
    implementation_paths: list[str] = Field(default_factory=list)
    published_url: str | None = None
    local_url: str | None = None
    quality_review_state: str = "not_reviewed"

    @field_validator("manuscript_paths", "implementation_paths")
    @classmethod
    def check_paths(cls, value: list[str]) -> list[str]:
        return [_clean_path(item) for item in value if item and str(item).strip()]  # type: ignore[misc]

    @field_validator("published_url", "local_url")
    @classmethod
    def check_urls(cls, value: str | None) -> str | None:
        return validate_url(value)


class ProjectUpdate(RawModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    kind: ProjectKind | None = None
    status: ProjectStatus | None = None
    pinned: bool | None = None
    display_order: int | None = None
    priority: int | None = None
    current_milestone: str | None = None
    next_action: str | None = None
    notes: str | None = None
    archived: bool | None = None


class CheckpointCreate(RawModel):
    project_id: str
    summary: str = Field(min_length=1, max_length=8000)
    last_completed: str = Field(default="", max_length=4000)
    next_action: str = Field(default="", max_length=4000)
    blockers: str = Field(default="", max_length=4000)
    evidence_refs: list[str] = Field(default_factory=list)
    milestone: str = Field(default="", max_length=500)


class CheckpointRead(BaseModel):
    id: str
    project_id: str
    project_name: str | None = None
    summary: str
    last_completed: str
    next_action: str
    blockers: str
    evidence_refs: list[str]
    milestone: str
    source: str
    created_at: str


class TaskCreate(RawModel):
    project_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    status: TaskStatus = "open"
    priority: int = 100
    due_at: str | None = None


class TaskUpdate(RawModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    status: TaskStatus | None = None
    priority: int | None = None
    due_at: str | None = None


class TaskRead(BaseModel):
    id: str
    project_id: str | None
    project_name: str | None = None
    title: str
    description: str
    status: TaskStatus
    priority: int
    source: str
    due_at: str | None
    created_at: str
    updated_at: str


class RecommendationRead(BaseModel):
    id: str
    project_id: str | None
    project_name: str | None = None
    title: str
    rationale: str
    evidence: list[str]
    source_application: str | None
    source_ref: str | None
    external_id: str | None
    provenance: str
    review_state: ReviewState
    created_at: str
    updated_at: str


class ReviewUpdate(RawModel):
    review_state: ReviewState
    note: str = ""


class DecisionCreate(RawModel):
    project_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    rationale: str = ""
    status: Literal["accepted", "rejected", "deferred", "revised"] = "accepted"


class DecisionRead(BaseModel):
    id: str
    project_id: str | None
    project_name: str | None = None
    title: str
    rationale: str
    status: str
    source: str
    decided_at: str
    created_at: str


class ActivityRead(BaseModel):
    id: str
    type: str
    title: str
    detail: str
    project_id: str | None
    project_name: str | None = None
    application_id: str | None
    application_name: str | None = None
    process_id: str | None
    source: str
    source_id: str | None
    evidence_ref: str | None
    provenance: str
    occurred_at: str
    observed_at: str
    metadata: dict[str, Any]


class ActivityNoteCreate(RawModel):
    project_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    detail: str = Field(default="", max_length=8000)
    evidence_ref: str | None = None


class OutcomeRead(BaseModel):
    id: str
    name: str
    description: str
    status: str
    url: str | None
    notes: str


class ProjectRead(BaseModel):
    id: str
    name: str
    description: str
    kind: ProjectKind
    status: ProjectStatus
    priority: int
    pinned: bool
    archived: bool
    display_order: int
    current_milestone: str
    next_action: str
    notes: str
    last_activity_at: str | None
    created_at: str
    updated_at: str
    repositories: list[RepositoryRead] = Field(default_factory=list)
    book: BookRead | None = None
    outcomes: list[OutcomeRead] = Field(default_factory=list)
    applications: list[dict[str, str]] = Field(default_factory=list)
    latest_checkpoint: CheckpointRead | None = None
    open_task_count: int = 0
    pending_recommendation_count: int = 0


class ProjectDetail(ProjectRead):
    repository_action: ActionState | None = None
    checkpoints: list[CheckpointRead] = Field(default_factory=list)
    tasks: list[TaskRead] = Field(default_factory=list)
    decisions: list[DecisionRead] = Field(default_factory=list)
    recommendations: list[RecommendationRead] = Field(default_factory=list)
    activity: list[ActivityRead] = Field(default_factory=list)
    adapters: list["AdapterRead"] = Field(default_factory=list)


class AdapterRead(BaseModel):
    id: str
    adapter: str
    application_id: str | None
    application_name: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    available: bool
    capabilities: list[str]
    detail: str
    error: str | None
    last_checked_at: str | None
    stale_after_seconds: int
    stale: bool = False


class BriefingItem(BaseModel):
    rank: int
    title: str
    project_id: str | None = None
    project_name: str | None = None
    rationale: str
    provenance: str
    evidence: list[str] = Field(default_factory=list)
    source: str | None = None


class BriefingRead(BaseModel):
    id: str
    created_at: str
    mode: str
    provider: str | None
    model: str | None
    status: str
    content: str
    items: list[BriefingItem]
    observations: list[dict[str, Any]]
    error: str | None


class BriefingRequest(RawModel):
    use_ai: bool = False


class SettingsPatch(RawModel):
    discovery: dict[str, Any] | None = None
    editor: dict[str, Any] | None = None
    browser: dict[str, Any] | None = None
    processes: dict[str, Any] | None = None
    adapters: dict[str, Any] | None = None
    retention: dict[str, Any] | None = None
    ai: dict[str, Any] | None = None
    startup: dict[str, Any] | None = None
    ui: dict[str, Any] | None = None


class SettingsRead(BaseModel):
    discovery: dict[str, Any]
    editor: dict[str, Any]
    browser: dict[str, Any]
    processes: dict[str, Any]
    adapters: dict[str, Any]
    retention: dict[str, Any]
    ai: dict[str, Any]
    startup: dict[str, Any]
    ui: dict[str, Any]
    discovery_roots: list[dict[str, Any]]
    ai_configured: bool
    ai_key_present: bool


class DiscoveryRootCreate(RawModel):
    path: str
    enabled: bool = True

    @field_validator("path")
    @classmethod
    def check_path(cls, value: str) -> str:
        return normalize_absolute_path(value, field="discovery root")


class DiscoveryRootRead(BaseModel):
    path: str
    enabled: bool
    added_at: str


class DiscoveryRootUpdate(RawModel):
    path: str
    enabled: bool = True

    @field_validator("path")
    @classmethod
    def check_path(cls, value: str) -> str:
        return normalize_absolute_path(value, field="discovery root")


class HealthRead(BaseModel):
    status: str
    version: str
    database: str
    schema_version: int
    ai_enabled: bool
    monitor_enabled: bool


class ScanRead(BaseModel):
    scan_id: str | None = None
    status: str
    running: bool
    started_at: str | None = None
    finished_at: str | None = None
    roots: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    errors: list[dict[str, str]] = Field(default_factory=list)
    truncated: bool = False
    cancelled: bool = False
    scanned_directories: int = 0
    elapsed_seconds: float | None = None
    candidate_count: int | None = None
    excluded_count: int | None = None
    skipped_links: list[str] = Field(default_factory=list)
    error: str | None = None


class CandidateRead(RepositoryRead):
    pass


class ResumeRead(BaseModel):
    project: ProjectRead | None
    checkpoint: CheckpointRead | None
    recent_projects: list[dict[str, Any]] = Field(default_factory=list)


class DashboardRead(BaseModel):
    generated_at: str
    date: str
    focus: ProjectRead | None
    checkpoint: CheckpointRead | None
    books: list[BookRead]
    applications: list[ApplicationRead]
    activity: list[ActivityRead]
    outcomes: list[OutcomeRead]
    tasks: list[TaskRead]
    recommendations: list[RecommendationRead]
    adapters: list[AdapterRead]
    briefing: BriefingRead | None
    stats: dict[str, int]


class ReorderRequest(RawModel):
    ids: list[str] = Field(min_length=1, max_length=100)


class StartupActivationEntry(BaseModel):
    application_id: str
    status: str
    process_id: str | None = None
    detail: str | None = None


class StartupActivationRead(BaseModel):
    activated: list[StartupActivationEntry]
    skipped: list[StartupActivationEntry]


class HealthCheckResponse(BaseModel):
    id: int
    application_id: str
    state: str
    detail: str
    source: str
    observed_at: str
    stale_after_seconds: int


class OpenUrlResponse(BaseModel):
    url: str
    application_id: str
    opened_externally: bool = False


class OkResponse(BaseModel):
    ok: bool = True
    detail: str | None = None


class AdapterRefreshResponse(BaseModel):
    adapters: list[AdapterRead]
    pending_recommendations: int = 0


BookRead.model_rebuild()
ProjectDetail.model_rebuild()
