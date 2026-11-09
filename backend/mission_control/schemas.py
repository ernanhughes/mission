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
    pinned: bool = False
    latest_checkpoint: "CheckpointRead | None" = None
    repository_action: ActionState | None = None


class BookDetectionRead(BaseModel):
    created: list[str]
    count: int


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


class IntegrationActionRead(BaseModel):
    id: str
    title: str
    description: str
    risk: str
    capability: str
    approval_required: bool
    side_effect: str
    parameters_schema: dict[str, Any]
    enabled: bool
    unavailable_reason: str | None


class IntegrationRead(BaseModel):
    application_id: str
    name: str
    adapter: str
    protocol_version: str
    mode: str
    enabled: bool
    available: bool
    detail: str
    error: str | None
    capabilities: list[str]
    actions: list[IntegrationActionRead]
    last_checked_at: str | None
    resource_counts: dict[str, int]
    repository_path: str | None
    config: dict[str, Any] = Field(default_factory=dict)
    repositories: list[dict[str, str]] = Field(default_factory=list)


class IntegrationConfigUpdate(RawModel):
    adapter_config: dict[str, Any]
    adapter_enabled: bool | None = None


class IntegrationDecisionRead(BaseModel):
    id: str
    application_id: str
    resource_type: str
    external_id: str
    decision: str
    reason: str
    sync_state: str
    source_decision_id: str | None
    decided_at: str
    created_at: str


class IntegrationRecordRead(BaseModel):
    id: str
    application_id: str
    application_name: str | None
    resource_type: str
    external_id: str
    title: str
    summary: str
    state: str
    project_id: str | None
    project_name: str | None
    source_version: str | None
    source_timestamp: str | None
    observed_at: str
    stale_after_seconds: int
    stale: bool
    current: bool
    evidence: list[str]
    data: dict[str, Any]
    local_decision: IntegrationDecisionRead | None
    decision_options: list[str]


class IntegrationResourcePatch(RawModel):
    project_id: str | None = None


class IntegrationDecisionCreate(RawModel):
    decision: str = Field(min_length=1, max_length=40)
    reason: str = Field(default="", max_length=4000)


class IntegrationExecutionCreate(RawModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class IntegrationExecutionRead(BaseModel):
    id: str
    application_id: str
    application_name: str | None
    action_id: str
    parameters: dict[str, Any]
    status: str
    risk: str
    approval_required: bool
    approved_at: str | None
    started_at: str | None
    ended_at: str | None
    exit_code: int | None
    output: str
    error: str | None
    result: dict[str, Any]
    artifact_ref: str | None
    created_at: str


class InboxItemRead(BaseModel):
    id: str
    source_application: str
    source_name: str
    item_type: str
    title: str
    summary: str
    project_id: str | None
    project_name: str | None
    priority: int
    priority_label: str
    evidence: list[str]
    observed_at: str
    state: str
    actions: list[str]
    target_path: str
    resource_id: str | None
    decision_state: str


class SearchResultRead(BaseModel):
    id: str
    source: str
    source_id: str
    title: str
    subtitle: str
    project_id: str | None
    target_path: str
    observed_at: str | None


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
    repos_discovered: int | None = None
    repos_indexed: int | None = None
    commits_new: int | None = None
    backfill_pending: int | None = None
    total_repos: int | None = None
    total_commits: int | None = None


# ------------------------------------------------------- git activity (MC-ACTIVITY-01)
class GitRootCreate(RawModel):
    path: str
    name: str = Field(default="", max_length=120)
    category: str = Field(default="software", max_length=60)
    enabled: bool = True

    @field_validator("path")
    @classmethod
    def check_path(cls, value: str) -> str:
        return normalize_absolute_path(value, field="activity root")


class GitRootUpdate(RawModel):
    name: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=60)
    enabled: bool | None = None
    git_enabled: bool | None = None


class GitRootRead(BaseModel):
    path: str
    name: str
    category: str
    enabled: bool
    git_enabled: bool
    added_at: str | None = None
    last_git_sync_at: str | None = None
    last_git_error: str | None = None


class GitRepoRead(BaseModel):
    id: str
    root_path: str
    path: str
    name: str
    branch: str | None = None
    head_sha: str | None = None
    accessible: bool = True
    is_bare: bool = False
    is_shallow: bool = False
    last_indexed_at: str | None = None
    backfill_complete: bool = False
    total_commits: int = 0
    has_agents: bool = False
    has_description: bool = False
    context_status: str = "missing"
    error: str | None = None


class GitCommitRead(BaseModel):
    repo_id: str
    repo_name: str
    repo_path: str
    root_path: str
    sha: str
    short_sha: str
    subject: str
    author_name: str
    author_email: str
    author_ts: int = 0
    committer_ts: int = 0
    committer_tz: str = ""
    parents: list[str] = Field(default_factory=list)
    branches: list[str] = Field(default_factory=list)
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    is_merge: bool = False
    is_root: bool = False
    reachable: bool = True
    review_count: int = 0
    review_status: str = "awaiting"


class GitTimelineRead(BaseModel):
    items: list[GitCommitRead]
    total: int
    partial: bool
    limit: int
    offset: int


class GitSummaryRead(BaseModel):
    commits_today: int = 0
    projects_today: int = 0
    commits_week: int = 0
    commits_reviewed: int = 0
    commits_indexed: int = 0
    repos_indexed: int = 0
    backfill_pending: int = 0
    complete: bool = True
    generated_at: str


class GitReviewCreate(RawModel):
    repo_id: str = Field(min_length=1, max_length=120)
    sha: str | None = Field(default=None, max_length=64)
    commit_shas: list[str] | None = None
    base_sha: str | None = Field(default=None, max_length=64)
    target_sha: str | None = Field(default=None, max_length=64)
    model: str = Field(default="", max_length=200)
    profile: str = Field(default="code", max_length=20)


class GitReviewRead(BaseModel):
    id: str
    repo_id: str
    review_type: str
    commit_sha: str | None = None
    base_sha: str | None = None
    target_sha: str | None = None
    commit_shas: list[str] = Field(default_factory=list)
    reviewer_type: str
    requested_model: str
    observed_model: str | None = None
    model_route: str = ""
    profile: str = "code"
    status: str
    verdict: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    tests: dict[str, Any] = Field(default_factory=dict)
    architecture: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    prompt_hash: str = ""
    diff_hash: str = ""
    context_fingerprint: str = ""
    evidence_coverage: dict[str, Any] = Field(default_factory=dict)
    usage_info: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str
    completed_at: str | None = None
    feedback: list[dict[str, Any]] = Field(default_factory=list)


class GitReviewFeedbackCreate(RawModel):
    rating: str = Field(min_length=1, max_length=40)
    detail: str = Field(default="", max_length=4000)


# --------------------------------------------------- cultivation (MC-CULTIVATION-01)
CultivationMeasurementType = str
CultivationGoalState = str


class CultivationStageDef(BaseModel):
    id: str
    label: str
    color: str = "grey"


class CultivationRankDef(BaseModel):
    id: str
    name: str
    concept: str = ""
    requires: dict[str, Any] = Field(default_factory=dict)


class CultivationConfig(BaseModel):
    stages: list[CultivationStageDef] = Field(default_factory=list)
    ranks: list[CultivationRankDef] = Field(default_factory=list)


class CultivationGoalCreate(RawModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    category: str = Field(default="general", max_length=60)
    unit: str = Field(default="items", max_length=60)
    target_value: float = Field(default=100)
    measurement_type: str = Field(default="count", max_length=40)
    baseline_value: float | None = None
    baseline_note: str = ""
    baseline_provenance: str = Field(default="none", max_length=20)
    qualifying_stage: str = Field(default="published", max_length=60)
    window_days: int | None = Field(default=None, ge=1, le=3650)
    priority: int = 100
    state: str = Field(default="active", max_length=20)
    pinned: bool = False
    pin_order: int = 100
    privacy: str = Field(default="standard", max_length=20)
    completion_criteria: str = ""
    milestones: list[float] | None = None
    dependencies: list[str] = Field(default_factory=list)
    evidence_source: str = Field(default="manual", max_length=60)


class CultivationGoalUpdate(RawModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    category: str | None = Field(default=None, max_length=60)
    unit: str | None = Field(default=None, max_length=60)
    target_value: float | None = None
    measurement_type: str | None = Field(default=None, max_length=40)
    baseline_value: float | None = None
    baseline_note: str | None = None
    baseline_provenance: str | None = Field(default=None, max_length=20)
    qualifying_stage: str | None = Field(default=None, max_length=60)
    window_days: int | None = Field(default=None, ge=1, le=3650)
    priority: int | None = None
    state: str | None = Field(default=None, max_length=20)
    pinned: bool | None = None
    pin_order: int | None = None
    privacy: str | None = Field(default=None, max_length=20)
    completion_criteria: str | None = None
    milestones: list[float] | None = None
    dependencies: list[str] | None = None
    evidence_source: str | None = Field(default=None, max_length=60)


class CultivationProgress(BaseModel):
    current: float | None = None
    target: float
    unit: str
    percent: float | None = None
    unknown_reason: str | None = None
    achieved: bool = False
    estimate_label: str | None = None
    item_count: int = 0
    pipeline: dict[str, int] = Field(default_factory=dict)
    milestones_reached: list[float] = Field(default_factory=list)
    next_milestone: float | None = None


class CultivationGoalRead(BaseModel):
    id: str
    name: str
    description: str
    category: str
    unit: str
    target_value: float
    measurement_type: str
    baseline_value: float | None
    baseline_note: str
    baseline_provenance: str
    qualifying_stage: str
    window_days: int | None
    priority: int
    state: str
    pinned: bool
    pin_order: int
    privacy: str
    completion_criteria: str
    milestones: list[float]
    dependencies: list[str]
    evidence_source: str
    created_at: str
    updated_at: str
    progress: CultivationProgress


class CultivationItemCreate(RawModel):
    id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    item_type: str = Field(default="work", max_length=60)
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    provenance: str = Field(default="unclassified", max_length=40)
    source_application: str | None = None
    source_project_id: str | None = None
    source_ref: str | None = None
    goal_ids: list[str] = Field(default_factory=list)
    stage: str = Field(default="idea", max_length=60)


class CultivationItemUpdate(RawModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    item_type: str | None = Field(default=None, max_length=60)
    notes: str | None = None
    tags: list[str] | None = None
    provenance: str | None = Field(default=None, max_length=40)
    source_application: str | None = None
    source_project_id: str | None = None
    source_ref: str | None = None


class CultivationMembershipRead(BaseModel):
    item_id: str
    goal_id: str
    goal_name: str | None = None
    stage: str
    evidence_status: str
    quality_evidence: dict[str, Any] = Field(default_factory=dict)
    qualified: bool
    qualified_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


class CultivationItemRead(BaseModel):
    id: str
    title: str
    item_type: str
    notes: str
    tags: list[str]
    provenance: str
    source_application: str | None
    source_project_id: str | None
    source_project_name: str | None = None
    source_ref: str | None
    created_at: str
    updated_at: str
    memberships: list[CultivationMembershipRead] = Field(default_factory=list)


class CultivationStageUpdate(RawModel):
    stage: str = Field(min_length=1, max_length=60)
    note: str = ""
    evidence_ref: str | None = None


class CultivationQualifyUpdate(RawModel):
    qualified: bool = True
    quality_evidence: dict[str, Any] = Field(default_factory=dict)
    note: str = ""


class CultivationMeasurementCreate(RawModel):
    value: float
    observed_at: str | None = None
    note: str = Field(default="", max_length=2000)
    source: str = Field(default="manual", max_length=60)


class CultivationMeasurementRead(BaseModel):
    id: str
    goal_id: str
    value: float
    observed_at: str
    note: str
    source: str
    created_at: str


class CultivationEventRead(BaseModel):
    id: str
    goal_id: str | None
    item_id: str | None
    item_title: str | None = None
    event_type: str
    from_value: str | None
    to_value: str | None
    note: str
    evidence_ref: str | None
    occurred_at: str | None
    created_at: str


class CultivationEvidenceCreate(RawModel):
    item_id: str | None = None
    kind: str = Field(default="reference", max_length=60)
    reference: str = Field(default="", max_length=2000)
    note: str = Field(default="", max_length=4000)
    verified: bool = False


class CultivationEvidenceRead(BaseModel):
    id: str
    goal_id: str | None
    item_id: str | None
    kind: str
    reference: str
    note: str
    verified: bool
    created_at: str


class CultivationRankStatus(BaseModel):
    id: str
    name: str
    concept: str
    qualified: bool
    requires: dict[str, Any]


class CultivationHudGoal(BaseModel):
    id: str
    name: str
    unit: str
    state: str
    privacy: str
    progress: CultivationProgress


class CultivationHudRead(BaseModel):
    primary: CultivationHudGoal | None
    pinned: list[CultivationHudGoal]
    rank: CultivationRankStatus | None
    recent_completions: list[CultivationEventRead]
    generated_at: str


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


class WorkflowEventRead(BaseModel):
    id: str
    workflow_id: str
    sequence: int
    event_type: str
    source: str
    summary: str
    payload: dict[str, Any]
    source_ref: str | None
    created_at: str


class LanguageObservationRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    workflow_id: str
    schema_name: str = Field(alias="schema", serialization_alias="schema")
    template: str
    intention_ref: str
    subject: str
    properties: list[dict[str, Any]]
    measurement_method: str | None
    evidence: list[str]
    provenance: dict[str, Any]
    uncertainty: list[str]
    constraint_result: str
    evaluation_version: str
    created_at: str


class ExperimentWorkflowRead(BaseModel):
    id: str
    title: str
    template: str
    status: str
    next_record_id: str | None
    next_external_id: str
    next_title: str
    project_id: str | None
    project_name: str | None
    next_evidence: dict[str, Any]
    proposal: dict[str, Any]
    language_intention: dict[str, Any]
    repository_path: str
    baseline_commit: str
    approved_scope: list[str]
    approval_hash: str | None
    approved_at: str | None
    approved_by: str | None
    worker_request_id: str | None
    worker_status: str | None
    worker_result: dict[str, Any]
    patch: dict[str, Any]
    result_commit: str | None
    measurement: dict[str, Any]
    review_execution_id: str | None
    review_artifact_path: str | None
    review_summary: dict[str, Any]
    adverse_review: bool
    final_decision: str | None
    final_reason: str
    override_adverse: bool
    cancel_requested: bool
    cancelled_at: str | None
    failure: str | None
    created_at: str
    updated_at: str
    events: list[WorkflowEventRead] = Field(default_factory=list)
    language_observations: list[LanguageObservationRead] = Field(default_factory=list)


class ProjectEvidenceTimeline(BaseModel):
    project_id: str
    workflows: list[ExperimentWorkflowRead]
    observations: list[LanguageObservationRead]


class WriterWorkspaceRead(BaseModel):
    available: bool
    detail: str
    error: str | None = None
    last_checked_at: str | None = None
    generated_at: str | None = None
    totals: dict[str, Any] = Field(default_factory=dict)
    review_queue: list[dict[str, Any]] = Field(default_factory=list)
    decision_queue: list[dict[str, Any]] = Field(default_factory=list)
    decision_totals: dict[str, Any] = Field(default_factory=dict)
    workbench: dict[str, Any] = Field(default_factory=dict)
    books: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class WriterAuditRequest(RawModel):
    profile: Literal["technical-nonfiction-v1"] = "technical-nonfiction-v1"


class WorkflowCreate(RawModel):
    record_id: str | None = Field(default=None, max_length=200)
    template: Literal["trace_reduce_v1", "brightness_observation_v1"] = "trace_reduce_v1"
    project_id: str | None = None
    force_new: bool = False


class WorkflowApprove(RawModel):
    confirm: bool = False
    approved_by: str = Field(default="user", max_length=120)
    scope_acknowledged: bool = False


class WorkflowExecute(RawModel):
    confirm: bool = False


class WorkflowCancel(RawModel):
    reason: str = Field(default="", max_length=2000)


class WorkflowProjectUpdate(RawModel):
    project_id: str | None = None


class WorkflowDecision(RawModel):
    decision: Literal["accept", "reject", "investigate"]
    reason: str = Field(default="", max_length=4000)
    override_adverse: bool = False


class ResearchModelInfo(BaseModel):
    id: str
    label: str
    local: bool
    configured: bool
    available: bool


class ResearchModelCatalogue(BaseModel):
    provider: str
    route: str
    configured: bool
    local: bool
    available: bool
    endpoint: str | None
    selected: str | None
    models: list[ResearchModelInfo]
    detail: str
    error: str | None = None


class ResearchContextRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(alias="schema", serialization_alias="schema")
    fingerprint: str
    markdown: str
    context: dict[str, Any]


class ResearchChatSessionCreate(RawModel):
    model_id: str = Field(min_length=1, max_length=200)
    model_route: str = Field(default="configured-local-openai", max_length=120)


class ResearchChatMessageCreate(RawModel):
    content: str = Field(min_length=1, max_length=8000)
    request_key: str | None = Field(default=None, max_length=120)


class ResearchChatMessageRead(BaseModel):
    id: str
    session_id: str
    sequence: int
    role: str
    content: str
    status: str
    error: str | None
    provider: str | None
    model: str | None
    route: str | None
    metadata: dict[str, Any]
    created_at: str


class ResearchChatSessionRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    application_id: str
    resource_type: str
    external_id: str
    record_id: str | None
    opportunity_title: str
    context_schema_name: str = Field(alias="context_schema", serialization_alias="context_schema")
    context_fingerprint: str
    context_observed_at: str | None
    model_route: str
    model_id: str
    model_local: bool
    provider: str
    endpoint: str | None
    created_at: str
    updated_at: str
    message_count: int
    messages: list[ResearchChatMessageRead]
    context_stale: bool
    current_fingerprint: str | None = None
    freshness_notice: str | None = None


class ResearchChatSessionSummary(BaseModel):
    id: str
    opportunity_title: str
    model_id: str
    model_local: bool
    provider: str
    created_at: str
    updated_at: str
    message_count: int
    last_message: str | None
    context_stale: bool


BookRead.model_rebuild()
ProjectDetail.model_rebuild()
