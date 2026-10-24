"""SQLAlchemy models mirroring the explicit SQL migrations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

from mission_control.persistence.db import now_iso


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String, default="supporting", nullable=False)
    icon: Mapped[str] = mapped_column(String, default="", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    repository_path: Mapped[str | None] = mapped_column(Text)
    additional_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    working_directory: Mapped[str | None] = mapped_column(Text)
    documentation_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    output_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    integration_adapter: Mapped[str | None] = mapped_column(String)
    adapter_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    adapter_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    related_projects: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_books: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    outcomes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    control_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String, default="default", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_launch_success_at: Mapped[str | None] = mapped_column(String)
    last_launch_failure_at: Mapped[str | None] = mapped_column(String)
    last_failure_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class LaunchDefinition(Base):
    __tablename__ = "launch_definitions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    launch_type: Mapped[str] = mapped_column(String, default="none", nullable=False)
    executable: Mapped[str | None] = mapped_column(Text)
    arguments: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    working_directory: Mapped[str | None] = mapped_column(Text)
    env_names: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    browser_url: Mapped[str | None] = mapped_column(Text)
    health_type: Mapped[str] = mapped_column(String, default="none", nullable=False)
    health_url: Mapped[str | None] = mapped_column(Text)
    expected_port: Mapped[int | None] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    shutdown_behavior: Mapped[str] = mapped_column(String, default="terminate", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ProcessInstance(Base):
    __tablename__ = "process_instances"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    launch_definition_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("launch_definitions.id", ondelete="SET NULL")
    )
    pid: Mapped[int | None] = mapped_column(Integer)
    create_time: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    ended_at: Mapped[str | None] = mapped_column(String)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    log_path: Mapped[str | None] = mapped_column(Text)
    working_directory: Mapped[str | None] = mapped_column(Text)
    command_preview: Mapped[str | None] = mapped_column(Text)
    owned: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reattached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class HealthObservation(Base):
    __tablename__ = "health_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    process_instance_id: Mapped[str | None] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String, default="health_check", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    stale_after_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kind: Mapped[str] = mapped_column(String, default="project", nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    current_milestone: Mapped[str] = mapped_column(Text, default="", nullable=False)
    next_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_activity_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="planned", nullable=False)
    current_milestone: Mapped[str] = mapped_column(Text, default="", nullable=False)
    next_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    manuscript_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    implementation_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    published_url: Mapped[str | None] = mapped_column(Text)
    local_url: Mapped[str | None] = mapped_column(Text)
    quality_review_state: Mapped[str] = mapped_column(
        String, default="not_reviewed", nullable=False
    )
    last_activity_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    classification: Mapped[str] = mapped_column(String, default="unknown", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_root: Mapped[str] = mapped_column(String, default="", nullable=False)
    is_git: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    branch: Mapped[str | None] = mapped_column(String)
    commit_hash: Mapped[str | None] = mapped_column(String)
    last_commit_at: Mapped[str | None] = mapped_column(String)
    dirty: Mapped[bool | None] = mapped_column(Boolean)
    accessible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_seen_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    last_observed_at: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class ProjectRepository(Base):
    __tablename__ = "project_repositories"

    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    repository_id: Mapped[str] = mapped_column(
        String, ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String, default="supporting", nullable=False)


class ProjectRelationship(Base):
    __tablename__ = "project_relationships"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    relationship: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    project_id: Mapped[str | None] = mapped_column(String)
    application_id: Mapped[str | None] = mapped_column(String)
    process_id: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="mission-control", nullable=False)
    source_id: Mapped[str | None] = mapped_column(String)
    evidence_ref: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(String, default="user", nullable=False)
    occurred_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String, unique=True)


class WorkCheckpoint(Base):
    __tablename__ = "work_checkpoints"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    last_completed: Mapped[str] = mapped_column(Text, default="", nullable=False)
    next_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    blockers: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    milestone: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String, default="user", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    source: Mapped[str] = mapped_column(String, default="user", nullable=False)
    due_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_application: Mapped[str | None] = mapped_column(String)
    source_ref: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String)
    provenance: Mapped[str] = mapped_column(
        String, default="derived_observation", nullable=False
    )
    review_state: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String, unique=True)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="accepted", nullable=False)
    source: Mapped[str] = mapped_column(String, default="user", nullable=False)
    decided_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class AdapterStatus(Base):
    __tablename__ = "adapter_statuses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    adapter: Mapped[str] = mapped_column(String, nullable=False)
    application_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("applications.id", ondelete="CASCADE")
    )
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[str | None] = mapped_column(String)
    stale_after_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class DiscoveryRoot(Base):
    __tablename__ = "discovery_roots"

    path: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    added_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class IntegrationRecord(Base):
    __tablename__ = "integration_records"
    __table_args__ = (
        UniqueConstraint("application_id", "resource_type", "external_id", name="uq_integration_resource"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    state: Mapped[str] = mapped_column(String, default="", nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="SET NULL")
    )
    source_version: Mapped[str | None] = mapped_column(String)
    source_timestamp: Mapped[str | None] = mapped_column(String)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    stale_after_seconds: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class IntegrationDecision(Base):
    __tablename__ = "integration_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sync_state: Mapped[str] = mapped_column(String, default="local_only", nullable=False)
    source_decision_id: Mapped[str | None] = mapped_column(String)
    decided_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class IntegrationExecution(Base):
    __tablename__ = "integration_executions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[str] = mapped_column(String, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    risk: Mapped[str] = mapped_column(String, default="read_only", nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[str | None] = mapped_column(String)
    ended_at: Mapped[str | None] = mapped_column(String)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    artifact_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ExperimentWorkflow(Base):
    __tablename__ = "experiment_workflows"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    template: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="proposed", nullable=False)
    next_record_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("integration_records.id", ondelete="SET NULL")
    )
    next_external_id: Mapped[str] = mapped_column(String, nullable=False)
    next_title: Mapped[str] = mapped_column(String, nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="SET NULL")
    )
    next_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    proposal: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    language_intention: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    repository_path: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_commit: Mapped[str] = mapped_column(String, nullable=False)
    approved_scope: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    approval_hash: Mapped[str | None] = mapped_column(String)
    approved_at: Mapped[str | None] = mapped_column(String)
    approved_by: Mapped[str | None] = mapped_column(String)
    worker_request_id: Mapped[str | None] = mapped_column(String)
    worker_status: Mapped[str | None] = mapped_column(String)
    worker_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    patch: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_commit: Mapped[str | None] = mapped_column(String)
    measurement: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_execution_id: Mapped[str | None] = mapped_column(String)
    review_artifact_path: Mapped[str | None] = mapped_column(Text)
    review_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    adverse_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    final_decision: Mapped[str | None] = mapped_column(String)
    final_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    override_adverse: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failure: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (
        UniqueConstraint("workflow_id", "sequence", name="uq_workflow_event_sequence"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiment_workflows.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class Briefing(Base):
    __tablename__ = "briefings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    mode: Mapped[str] = mapped_column(String, default="deterministic", nullable=False)
    provider: Mapped[str | None] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="complete", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    observations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
