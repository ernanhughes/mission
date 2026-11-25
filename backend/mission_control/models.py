"""SQLAlchemy models mirroring the explicit SQL migrations.

Persistence convention (MC-POSTGRES-02): models declare column-level
``ForeignKey`` constraints but no ``relationship()`` attributes. SQLAlchemy
orders pending inserts via relationship dependency processors, so bare
foreign keys alone do NOT order a flush: adding a transient parent and child
in one flush emits the child INSERT first and any FK-enforcing backend
rejects it. Always ``flush()`` parents before adding children in a session
(see ``seed_defaults``). Pinned by ``tests/test_persistence_conventions.py``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, TEXT, TypeDecorator

from mission_control.persistence.db import now_iso


class _SafeJSONBase(TypeDecorator):
    """JSON that survives TEXT-column DDL on PostgreSQL (W9A audit).

    Work Outcome migrations create TEXT columns; on PostgreSQL the
    generic JSON result processor does not run for them, so ORM reads
    returned raw strings while SQLite deserialized. This boundary
    serializes on write and parses on read on both backends, falling
    back to an empty container (never None, never a string) for missing
    or malformed values.

    W9 review F6: coercion of malformed content is logged once per
    class so corruption is observable instead of silently looking like
    an empty list. Reads still fail soft (a bad row must not break a
    listing), but the operator gets a warning naming the column type.
    """

    impl = TEXT
    cache_ok = True
    _factory = list
    _warned = False

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        import json as _json

        if value is None:
            return _json.dumps(self._factory())
        return _json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        import json as _json

        want_type = dict if isinstance(self._factory(), dict) else list
        if value is None:
            return self._factory()
        if isinstance(value, want_type):
            return value
        try:
            parsed = _json.loads(value)
        except (ValueError, TypeError):
            self._warn(value)
            return self._factory()
        if isinstance(parsed, want_type):
            return parsed
        self._warn(value)
        return self._factory()

    def _warn(self, value: Any) -> None:
        if not _SafeJSONBase._warned:
            _SafeJSONBase._warned = True
            import logging

            logging.getLogger(__name__).warning(
                "SafeJSON coerced malformed stored value to empty "
                "container (further occurrences suppressed). This "
                "indicates corrupted or wrong-shaped JSON in a TEXT "
                "column; inspect the affected rows.",
            )


class SafeJSONList(_SafeJSONBase):
    """JSON list column with identical behavior on SQLite and PG."""

    _factory = list


class SafeJSONDict(_SafeJSONBase):
    """JSON dict column with identical behavior on SQLite and PG."""

    _factory = dict


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
    # Windows reports some terminations as unsigned 32-bit codes (up to
    # 4294967295), which exceeds PG INT4: use BIGINT.
    exit_code: Mapped[int | None] = mapped_column(BigInteger)
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
    origin: Mapped[str] = mapped_column(String, default="curated", nullable=False)
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
    repo_uid: Mapped[str] = mapped_column(Text, default="", nullable=False)
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
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
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
    provenance: Mapped[str] = mapped_column(String, default="derived_observation", nullable=False)
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
    display_name: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(Text, default="software", nullable=False)
    git_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_git_sync_at: Mapped[str | None] = mapped_column(Text)
    last_git_error: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class GitRepository(Base):
    __tablename__ = "git_repositories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    root_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, default="", nullable=False)
    git_dir: Mapped[str] = mapped_column(Text, default="", nullable=False)
    repo_uid: Mapped[str] = mapped_column(Text, default="", nullable=False)
    branch: Mapped[str | None] = mapped_column(Text)
    head_sha: Mapped[str | None] = mapped_column(Text)
    refs_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    accessible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_bare: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_shallow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_indexed_at: Mapped[str | None] = mapped_column(Text)
    backfill_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    backfill_before: Mapped[str | None] = mapped_column(Text)
    total_commits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    has_agents: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_description: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    context_status: Mapped[str] = mapped_column(String, default="missing", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class GitCommit(Base):
    __tablename__ = "git_commits"

    repo_id: Mapped[str] = mapped_column(
        String, ForeignKey("git_repositories.id", ondelete="CASCADE"), primary_key=True
    )
    sha: Mapped[str] = mapped_column(String, primary_key=True)
    short_sha: Mapped[str] = mapped_column(String, default="", nullable=False)
    subject: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    author_name: Mapped[str] = mapped_column(Text, default="", nullable=False)
    author_email: Mapped[str] = mapped_column(Text, default="", nullable=False)
    author_ts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    author_tz: Mapped[str] = mapped_column(Text, default="", nullable=False)
    committer_ts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    committer_tz: Mapped[str] = mapped_column(Text, default="", nullable=False)
    parents: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    branches: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    files_changed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    insertions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_merge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_root: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reachable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    first_seen_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class GitReview(Base):
    __tablename__ = "git_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_id: Mapped[str] = mapped_column(
        String, ForeignKey("git_repositories.id", ondelete="CASCADE"), nullable=False
    )
    review_type: Mapped[str] = mapped_column(String, default="single", nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String)
    base_sha: Mapped[str | None] = mapped_column(String)
    target_sha: Mapped[str | None] = mapped_column(String)
    commit_shas: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reviewer_type: Mapped[str] = mapped_column(String, default="local", nullable=False)
    requested_model: Mapped[str] = mapped_column(String, default="", nullable=False)
    observed_model: Mapped[str | None] = mapped_column(String)
    model_route: Mapped[str] = mapped_column(String, default="", nullable=False)
    profile: Mapped[str] = mapped_column(String, default="code", nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    verdict: Mapped[str | None] = mapped_column(String)
    findings: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tests: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    architecture: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    diff_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    evidence_coverage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    usage_info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String)


class GitReviewFeedback(Base):
    __tablename__ = "git_review_feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    review_id: Mapped[str] = mapped_column(
        String, ForeignKey("git_reviews.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[str] = mapped_column(String, default="", nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationSkill(Base):
    __tablename__ = "cultivation_skills"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    icon: Mapped[str] = mapped_column(String, default="sprout", nullable=False)
    category: Mapped[str] = mapped_column(String, default="general", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pin_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    state: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationSource(Base):
    __tablename__ = "cultivation_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, default="hugo_blog", nullable=False)
    skill_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("cultivation_skills.id", ondelete="SET NULL")
    )
    goal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("cultivation_goals.id", ondelete="SET NULL")
    )
    path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_sync_at: Mapped[str | None] = mapped_column(String)
    last_status: Mapped[str] = mapped_column(String, default="never_synced", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    observed: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationCycle(Base):
    __tablename__ = "cultivation_cycles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, default="", nullable=False)
    length_days: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    start_date: Mapped[str | None] = mapped_column(String)
    snapshot_day: Mapped[int | None] = mapped_column(Integer)
    snapshot_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    state: Mapped[str] = mapped_column(String, default="active", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationCycleGoal(Base):
    __tablename__ = "cultivation_cycle_goals"

    cycle_id: Mapped[str] = mapped_column(
        String, ForeignKey("cultivation_cycles.id", ondelete="CASCADE"), primary_key=True
    )
    goal_id: Mapped[str] = mapped_column(
        String, ForeignKey("cultivation_goals.id", ondelete="CASCADE"), primary_key=True
    )


class CultivationRepoState(Base):
    """Owner-maintained qualification of one Activity repository.

    The Activity row (git_repositories) stays authoritative for Git facts.
    Everything here is Cultivation-side judgement, reconciliation and history
    pointers — never written back into Activity tables.
    """

    __tablename__ = "cultivation_repo_states"

    repo_id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_uid: Mapped[str] = mapped_column(Text, default="", nullable=False)
    qualification: Mapped[str] = mapped_column(String, default="discovered", nullable=False)
    lifecycle_stage: Mapped[str | None] = mapped_column(String)
    classification: Mapped[str] = mapped_column(String, default="unclassified", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    decided_by: Mapped[str] = mapped_column(String, default="undecided", nullable=False)
    decided_at: Mapped[str | None] = mapped_column(String)
    accessible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[str | None] = mapped_column(String)
    last_head: Mapped[str | None] = mapped_column(String)
    last_commit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationGitHubRepo(Base):
    """Local read-only snapshot of one GitHub repository.

    GitHub owns the remote facts; Mission Control owns nothing here except
    the cached observation. Owner judgement (qualification, lifecycle,
    classification, rationale) lives in ``cultivation_repo_states`` under
    ``repo_id = 'gh-' + node_id``. Never written back to GitHub.
    """

    __tablename__ = "cultivation_github_repos"

    node_id: Mapped[str] = mapped_column(String, primary_key=True)
    numeric_id: Mapped[int | None] = mapped_column(Integer)
    owner: Mapped[str] = mapped_column(String, default="", nullable=False)
    name: Mapped[str] = mapped_column(String, default="", nullable=False)
    full_name: Mapped[str] = mapped_column(String, default="", nullable=False)
    url: Mapped[str] = mapped_column(String, default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    visibility: Mapped[str] = mapped_column(String, default="PUBLIC", nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_fork: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    language: Mapped[str | None] = mapped_column(String)
    languages: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String)
    pushed_at: Mapped[str | None] = mapped_column(String)
    created_at_github: Mapped[str | None] = mapped_column(String)
    updated_at_github: Mapped[str | None] = mapped_column(String)
    missing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationApplication(Base):
    __tablename__ = "cultivation_applications"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    lifecycle_stage: Mapped[str] = mapped_column(String, default="idea", nullable=False)
    release_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationAppRepo(Base):
    __tablename__ = "cultivation_app_repos"

    app_id: Mapped[str] = mapped_column(
        String, ForeignKey("cultivation_applications.id", ondelete="CASCADE"), primary_key=True
    )
    repo_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationGoal(Base):
    __tablename__ = "cultivation_goals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String, default="general", nullable=False)
    unit: Mapped[str] = mapped_column(String, default="items", nullable=False)
    target_value: Mapped[float] = mapped_column(Float, default=100, nullable=False)
    measurement_type: Mapped[str] = mapped_column(String, default="count", nullable=False)
    baseline_value: Mapped[float | None] = mapped_column(Float)
    baseline_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    baseline_provenance: Mapped[str] = mapped_column(String, default="none", nullable=False)
    qualifying_stage: Mapped[str] = mapped_column(String, default="published", nullable=False)
    window_days: Mapped[int | None] = mapped_column(Integer)
    recurring_mode: Mapped[str] = mapped_column(String, default="daily", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    state: Mapped[str] = mapped_column(String, default="active", nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pin_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    privacy: Mapped[str] = mapped_column(String, default="standard", nullable=False)
    completion_criteria: Mapped[str] = mapped_column(Text, default="", nullable=False)
    milestones: Mapped[list[float]] = mapped_column(JSON, default=list, nullable=False)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_source: Mapped[str] = mapped_column(String, default="manual", nullable=False)
    skill_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("cultivation_skills.id", ondelete="SET NULL")
    )
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationItem(Base):
    __tablename__ = "cultivation_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    item_type: Mapped[str] = mapped_column(String, default="work", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provenance: Mapped[str] = mapped_column(String, default="unclassified", nullable=False)
    source_application: Mapped[str | None] = mapped_column(String)
    source_project_id: Mapped[str | None] = mapped_column(String)
    source_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationMembership(Base):
    __tablename__ = "cultivation_memberships"

    item_id: Mapped[str] = mapped_column(
        String, ForeignKey("cultivation_items.id", ondelete="CASCADE"), primary_key=True
    )
    goal_id: Mapped[str] = mapped_column(
        String, ForeignKey("cultivation_goals.id", ondelete="CASCADE"), primary_key=True
    )
    stage: Mapped[str] = mapped_column(String, default="idea", nullable=False)
    evidence_status: Mapped[str] = mapped_column(String, default="none", nullable=False)
    quality_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    qualified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qualified_at: Mapped[str | None] = mapped_column(String)
    completed_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationMeasurement(Base):
    __tablename__ = "cultivation_measurements"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    goal_id: Mapped[str] = mapped_column(
        String, ForeignKey("cultivation_goals.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String, default="manual", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationEvent(Base):
    __tablename__ = "cultivation_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    goal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("cultivation_goals.id", ondelete="CASCADE")
    )
    item_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("cultivation_items.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    from_value: Mapped[str | None] = mapped_column(Text)
    to_value: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_ref: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class CultivationEvidence(Base):
    __tablename__ = "cultivation_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    goal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("cultivation_goals.id", ondelete="CASCADE")
    )
    item_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("cultivation_items.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String, default="reference", nullable=False)
    reference: Mapped[str] = mapped_column(Text, default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class IntegrationRecord(Base):
    __tablename__ = "integration_records"
    __table_args__ = (
        UniqueConstraint(
            "application_id", "resource_type", "external_id", name="uq_integration_resource"
        ),
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
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancelled_at: Mapped[str | None] = mapped_column(String)
    failure: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class LanguageObservation(Base):
    __tablename__ = "language_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String, ForeignKey("experiment_workflows.id", ondelete="CASCADE"), nullable=False
    )
    schema: Mapped[str] = mapped_column(String, nullable=False)
    template: Mapped[str] = mapped_column(String, nullable=False)
    intention_ref: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    properties: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    measurement_method: Mapped[str | None] = mapped_column(String)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    uncertainty: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    constraint_result: Mapped[str] = mapped_column(String, nullable=False)
    evaluation_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


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


class ResearchChatSession(Base):
    __tablename__ = "research_chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    record_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("integration_records.id", ondelete="SET NULL")
    )
    opportunity_title: Mapped[str] = mapped_column(String, nullable=False)
    context_schema: Mapped[str] = mapped_column(String, nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    context_observed_at: Mapped[str | None] = mapped_column(String)
    model_route: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    model_local: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    provider: Mapped[str] = mapped_column(String, default="openai-compatible", nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ResearchChatMessage(Base):
    __tablename__ = "research_chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_research_chat_message_sequence"),
        UniqueConstraint("session_id", "request_key", name="uq_research_chat_message_request"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("research_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="completed", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String)
    route: Mapped[str | None] = mapped_column(String)
    request_key: Mapped[str | None] = mapped_column(String)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
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


class QualityEvaluation(Base):
    """One manuscript-quality evaluation observation (MC-QUALITY-02).

    Append-only history: a new observation never overwrites an old one.
    Staleness is derived at read time by comparing chapter_revision values,
    never by mutation.
    """

    __tablename__ = "quality_evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    book_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    chapter_revision: Mapped[str] = mapped_column(String, nullable=False)
    rubric_id: Mapped[str] = mapped_column(String, default="manuscript-prose-v1", nullable=False)
    rubric_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, default="1", nullable=False)
    requested_model: Mapped[str | None] = mapped_column(String)
    actual_model: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="CURRENT", nullable=False)
    overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    aggregation_method: Mapped[str] = mapped_column(
        String, default="mean_equal_weights_v1", nullable=False
    )
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    findings: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    uncertainty: Mapped[str] = mapped_column(Text, default="", nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    execution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    previous_evaluation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quality_evaluations.id", ondelete="SET NULL")
    )
    supersedes: Mapped[str | None] = mapped_column(String)
    workbench_url: Mapped[str | None] = mapped_column(Text)
    section_id: Mapped[str | None] = mapped_column(String)
    section_title: Mapped[str | None] = mapped_column(String)
    char_span: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    section_sha: Mapped[str | None] = mapped_column(String)
    campaign_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quality_campaigns.id", ondelete="SET NULL")
    )
    strategy: Mapped[str] = mapped_column(String, default="direct", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class QualityCampaign(Base):
    """Durable whole-book evaluation campaign (MC-QUALITY-03A).

    Per-chapter observations stay in quality_evaluations; the campaign row
    carries selection, progress and recovery state only.
    """

    __tablename__ = "quality_campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    book_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    book_root: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mode: Mapped[str] = mapped_column(String, default="missing", nullable=False)
    chapter_selection: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    fingerprints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rubric_id: Mapped[str] = mapped_column(String, default="manuscript-prose-v1", nullable=False)
    rubric_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, default="1", nullable=False)
    model: Mapped[str | None] = mapped_column(String)
    max_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    remaining: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    costs_unknown: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    current_chapter: Mapped[str | None] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(Text)
    heartbeat_at: Mapped[str | None] = mapped_column(String)
    strategy: Mapped[str] = mapped_column(String, default="direct", nullable=False)
    assessment_type: Mapped[str] = mapped_column(String, default="prose", nullable=False)
    max_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String)


class TechnicalClaim(Base):
    """One independently inspectable technical assertion (MC-QUALITY-03B).

    Append-only; staleness derived at read time from source_revision.
    """

    __tablename__ = "technical_claims"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    book_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_revision: Mapped[str] = mapped_column(String, nullable=False)
    source_start_line: Mapped[int | None] = mapped_column(Integer)
    source_end_line: Mapped[int | None] = mapped_column(Integer)
    source_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_assertion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    claim_type: Mapped[str] = mapped_column(String, nullable=False)
    epistemic_role: Mapped[str] = mapped_column(String, nullable=False)
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    qualifications: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String, default="llm_extract_v1", nullable=False)
    model_id: Mapped[str | None] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String, default="1", nullable=False)
    extraction_status: Mapped[str] = mapped_column(String, default="CURRENT", nullable=False)
    quote_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anchor_method: Mapped[str] = mapped_column(String, default="none", nullable=False)
    source_char_start: Mapped[int | None] = mapped_column(Integer)
    source_char_end: Mapped[int | None] = mapped_column(Integer)
    campaign_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quality_campaigns.id", ondelete="SET NULL")
    )
    extraction_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("technical_extraction_runs.id", ondelete="SET NULL")
    )
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalEvidence(Base):
    """One supporting-evidence record for a claim (MC-QUALITY-03B)."""

    __tablename__ = "technical_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_id: Mapped[str] = mapped_column(
        String, ForeignKey("technical_claims.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    source_location: Mapped[str] = mapped_column(Text, nullable=False)
    source_revision: Mapped[str] = mapped_column(String, default="", nullable=False)
    source_span: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    discovery_method: Mapped[str] = mapped_column(String, default="", nullable=False)
    verification_method: Mapped[str] = mapped_column(String, default="", nullable=False)
    verification_status: Mapped[str] = mapped_column(String, default="NOT_RUN", nullable=False)
    limitations: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalVerification(Base):
    """One verification outcome for a claim (MC-QUALITY-03B)."""

    __tablename__ = "technical_verifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_id: Mapped[str] = mapped_column(
        String, ForeignKey("technical_claims.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("technical_evidence.id", ondelete="SET NULL")
    )
    method: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    spec_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    spec_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    model_id: Mapped[str | None] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String, default="", nullable=False)
    prompt_hash: Mapped[str | None] = mapped_column(String)
    token_usage: Mapped[str] = mapped_column(String, default="unknown", nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    campaign_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quality_campaigns.id", ondelete="SET NULL")
    )
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalRegion(Base):
    """Deterministic source region for coverage accounting (MC-QUALITY-03C)."""

    __tablename__ = "technical_regions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    book_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, default="", nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    byte_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    byte_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    parent_region_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("technical_regions.id", ondelete="SET NULL")
    )
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_kind: Mapped[str] = mapped_column(String, default="section", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalExtractionCoverage(Base):
    """One extraction attempt against a region (MC-QUALITY-03C)."""

    __tablename__ = "technical_extraction_coverage"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    region_id: Mapped[str] = mapped_column(
        String, ForeignKey("technical_regions.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quality_campaigns.id", ondelete="SET NULL")
    )
    source_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    extractor_version: Mapped[str] = mapped_column(
        String, default="technical-claim-v1", nullable=False
    )
    model_id: Mapped[str | None] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String, default="1", nullable=False)
    requested_limit: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    returned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="NOT_STARTED", nullable=False)
    limit_reached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalExtractionRun(Base):
    """One bounded extraction request under a strategy (MC-QUALITY-04A-03).

    Strategy is one of whole_continuation, region_single, region_grouped.
    Quarantined (over-limit/truncated) runs persist with accepted_count 0;
    their claims must never be stored as complete extraction."""

    __tablename__ = "technical_extraction_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quality_campaigns.id", ondelete="SET NULL")
    )
    strategy: Mapped[str] = mapped_column(String, default="whole_continuation", nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, nullable=False)
    region_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    requested_limit: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    returned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="NOT_RUN", nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_id: Mapped[str | None] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String, default="1", nullable=False)
    source_revision: Mapped[str] = mapped_column(String, default="", nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    transport: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalEvidenceRequirement(Base):
    """An evidence obligation for one claim (MC-QUALITY-03C)."""

    __tablename__ = "technical_evidence_requirements"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_id: Mapped[str] = mapped_column(
        String, ForeignKey("technical_claims.id", ondelete="CASCADE"), nullable=False
    )
    requirement_key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, default="", nullable=False)
    requirement_type: Mapped[str] = mapped_column(String, default="", nullable=False)
    acceptance_rule: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    spec_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    applicability: Mapped[str] = mapped_column(String, default="UNDETERMINED", nullable=False)
    applicability_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    satisfaction: Mapped[str] = mapped_column(String, default="NOT_ASSESSED", nullable=False)
    satisfaction_detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    waived_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quality_campaigns.id", ondelete="SET NULL")
    )
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalRequirementLink(Base):
    """Evidence-to-requirement relationship with explicit semantics."""

    __tablename__ = "technical_requirement_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    requirement_id: Mapped[str] = mapped_column(
        String, ForeignKey("technical_evidence_requirements.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("technical_evidence.id", ondelete="SET NULL")
    )
    relation: Mapped[str] = mapped_column(String, default="satisfies", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalClaimLink(Base):
    """Claim-to-claim relationship (depends_on, restates, contradicts, refines)."""

    __tablename__ = "technical_claim_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    from_claim_id: Mapped[str] = mapped_column(
        String, ForeignKey("technical_claims.id", ondelete="CASCADE"), nullable=False
    )
    to_claim_id: Mapped[str] = mapped_column(
        String, ForeignKey("technical_claims.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String, default="depends_on", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalGap(Base):
    """A recorded evidence gap (MC-QUALITY-03C). Gaps describe missing or
    insufficient evidence; they are not technical-defect verdicts."""

    __tablename__ = "technical_gaps"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    book_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, nullable=False)
    claim_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("technical_claims.id", ondelete="SET NULL")
    )
    requirement_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("technical_evidence_requirements.id", ondelete="SET NULL")
    )
    gap_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, default="", nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    searched_scope: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="OPEN", nullable=False)
    priority_rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quality_campaigns.id", ondelete="SET NULL")
    )
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalObjective(Base):
    """A chapter-level objective, explicit or provisional (MC-QUALITY-03C)."""

    __tablename__ = "technical_objectives"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    book_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, default="inferred", nullable=False)
    status: Mapped[str] = mapped_column(String, default="proposed", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class TechnicalObjectiveClaim(Base):
    """Objective-to-claim support link."""

    __tablename__ = "technical_objective_claims"

    objective_id: Mapped[str] = mapped_column(
        String, ForeignKey("technical_objectives.id", ondelete="CASCADE"), primary_key=True
    )
    claim_id: Mapped[str] = mapped_column(
        String, ForeignKey("technical_claims.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String, default="supports", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class QualityReview(Base):
    """Author decision on one finding (WRITER-QUALITY-02).

    Append-only and stored separately from AI judgments and policy outcomes.
    The finding, evidence and model verdict are never mutated by a review.
    """

    __tablename__ = "quality_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    evaluation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("quality_evaluations.id", ondelete="CASCADE")
    )
    finding_id: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewer: Mapped[str] = mapped_column(String, default="", nullable=False)
    source_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ArtifactLoadObservation(Base):
    """Independent Artifact Load burden observation (ARTIFACT-EXPO-01 Stage 08).

    Append-only history: a new observation never overwrites an old one.
    Kept fully separate from the six-dimension prose-quality scores.
    Higher weighted_load means more confirmed burden; it is never a
    percentage and never a 0-100 health score.
    """

    __tablename__ = "artifact_load_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    book_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    chapter_id: Mapped[str] = mapped_column(String, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    chapter_revision: Mapped[str] = mapped_column(String, nullable=False)
    aggregation_version: Mapped[str] = mapped_column(
        String, default="artifact-load-v1", nullable=False
    )
    detector_version: Mapped[str] = mapped_column(String, default="expo-v1", nullable=False)
    status: Mapped[str] = mapped_column(String, default="CURRENT", nullable=False)
    eligible_words: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evaluated_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_candidates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confirmed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    medium: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unreviewed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_evidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    affected_regions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    findings_per_1k: Mapped[float | None] = mapped_column(Float, nullable=True)
    findings_per_100_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    region_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_mechanical: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    coverage_semantic: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weighted_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    mechanical_pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_eligible_words: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revised_eligible_words: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    findings: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    regions: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    execution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    previous_observation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("artifact_load_observations.id", ondelete="SET NULL")
    )
    supersedes: Mapped[str | None] = mapped_column(String)
    workbench_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ScriptRecord(Base):
    """Stable script identity (MC-SCRIPTS-02 Phase B).

    The filename is observation, not identity: ``current_relpath`` moves on
    rename while ``id`` and ``original_relpath`` stay fixed. Two files may
    share a content hash and remain separate historical records.
    Identity is scoped to a library (MC-SCRIPTS-03): different roots never
    share records even when relative paths match.
    """

    __tablename__ = "script_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    library_key: Mapped[str] = mapped_column(String, default="", nullable=False)
    current_relpath: Mapped[str] = mapped_column(Text, nullable=False)
    original_relpath: Mapped[str] = mapped_column(Text, nullable=False)
    script_number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String, default="", nullable=False)
    content_sha256: Mapped[str] = mapped_column(String, default="", nullable=False)
    # Nanosecond mtimes (~1.8e18) and large files exceed INT4: use BIGINT.
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    mtime_ns: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="discovered", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    missing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discovered_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    last_seen_at: Mapped[str | None] = mapped_column(String)
    completed_at: Mapped[str | None] = mapped_column(String)
    review_status: Mapped[str] = mapped_column(String, default="none", nullable=False)
    last_review_at: Mapped[str | None] = mapped_column(String)
    legacy_item_id: Mapped[str | None] = mapped_column(String)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    personal_rating: Mapped[float | None] = mapped_column(Float)
    personal_target: Mapped[str] = mapped_column(String, default="", nullable=False)
    personal_effect: Mapped[str] = mapped_column(String, default="", nullable=False)
    last_used_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ScriptReview(Base):
    """One AI review of a script (MC-SCRIPTS-05 Phase E1).

    Append-only: a new review never overwrites an old one. Freshness is
    derived at read time by comparing ``content_sha256`` with the record's
    current hash (CURRENT vs STALE). Reviews never change lifecycle,
    completion, or effectiveness — those need explicit human action.
    """

    __tablename__ = "script_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    script_id: Mapped[str] = mapped_column(
        String, ForeignKey("script_records.id", ondelete="CASCADE"), nullable=False
    )
    content_sha256: Mapped[str] = mapped_column(String, default="", nullable=False)
    model: Mapped[str] = mapped_column(String, default="", nullable=False)
    route: Mapped[str] = mapped_column(String, default="", nullable=False)
    provider: Mapped[str] = mapped_column(String, default="", nullable=False)
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    raw_response: Mapped[str] = mapped_column(Text, default="", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ScriptEvent(Base):
    """Append-only script history. Completion is recorded here, never inferred."""

    __tablename__ = "script_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    script_id: Mapped[str] = mapped_column(
        String, ForeignKey("script_records.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    from_value: Mapped[str | None] = mapped_column(Text)
    to_value: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ScriptLink(Base):
    """Unconfirmed or confirmed relationships: revision, alternative, duplicate."""

    __tablename__ = "script_links"

    source_id: Mapped[str] = mapped_column(
        String, ForeignKey("script_records.id", ondelete="CASCADE"), primary_key=True
    )
    target_id: Mapped[str] = mapped_column(
        String, ForeignKey("script_records.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String, default="possible_duplicate", primary_key=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[str] = mapped_column(String, default="unconfirmed", nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ScriptMigration(Base):
    """Durable renumbering manifest (MC-SCRIPTS-04 Phase D).

    Preview first: the manifest binds exact source fingerprints so a stale
    preview cannot be applied. Filesystem renames and SQLite updates are not
    one atomic transaction, so the row also carries step-by-step recovery
    state for resume and rollback.
    """

    __tablename__ = "script_migrations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    library_key: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="preview", nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    approved_at: Mapped[str | None] = mapped_column(String)
    applied_at: Mapped[str | None] = mapped_column(String)
    rolled_back_at: Mapped[str | None] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(Text)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ScriptBatch(Base):
    """Bounded, resumable review batch (MC-SCRIPTS-05 Phase E2).

    Items carry their own status so a cancelled or failed batch resumes
    without duplicating successful reviews. No lifecycle, completion, or
    effectiveness changes ever result from batch execution.
    """

    __tablename__ = "script_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    library_key: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    model: Mapped[str] = mapped_column(String, default="", nullable=False)
    rubric_version: Mapped[str] = mapped_column(String, default="", nullable=False)
    schema_version: Mapped[str] = mapped_column(String, default="", nullable=False)
    selection: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ScriptBatchItem(Base):
    __tablename__ = "script_batch_items"

    batch_id: Mapped[str] = mapped_column(
        String, ForeignKey("script_batches.id", ondelete="CASCADE"), primary_key=True
    )
    script_id: Mapped[str] = mapped_column(
        String, ForeignKey("script_records.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    review_id: Mapped[str | None] = mapped_column(String)
    reused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ScriptTag(Base):
    """Purpose/effect tags with origin. AI-inferred vs user-confirmed stay distinct."""

    __tablename__ = "script_tags"

    script_id: Mapped[str] = mapped_column(
        String, ForeignKey("script_records.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String, primary_key=True)
    origin: Mapped[str] = mapped_column(String, default="ai", primary_key=True)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class LibrarySynthesis(Base):
    """Versioned whole-library synthesis (MC-SCRIPTS-05 Phase E2).

    Append-only: a new synthesis never rewrites history. Freshness is derived
    from the source manifest (review IDs + content hashes), never by mutation.
    """

    __tablename__ = "library_syntheses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    library_key: Mapped[str] = mapped_column(String, default="", nullable=False)
    kind: Mapped[str] = mapped_column(String, default="full", nullable=False)
    status: Mapped[str] = mapped_column(String, default="complete", nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ScriptCandidate(Base):
    """Versioned script candidate (MC-SCRIPTS-06 Phase E3).

    Drafts live here, never in the numbered library, until an explicit
    promotion allocates the next safe filename and registers (not completes)
    the new script. Revision chains link through parent_candidate_id.
    """

    __tablename__ = "script_candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    library_key: Mapped[str] = mapped_column(String, default="", nullable=False)
    title: Mapped[str] = mapped_column(String, default="", nullable=False)
    version: Mapped[str] = mapped_column(String, default="v1", nullable=False)
    kind: Mapped[str] = mapped_column(String, default="ascendance", nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    est_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    critique: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    parent_candidate_id: Mapped[str | None] = mapped_column(String)
    promoted_script_id: Mapped[str | None] = mapped_column(String)
    promoted_relpath: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class PublicationAssessment(Base):
    """One release-candidate assessment bound to an exact manuscript snapshot
    and a versioned release policy (MC-QUALITY-03D). Append-only."""

    __tablename__ = "publication_assessments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    book_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    book_root: Mapped[str] = mapped_column(Text, default="", nullable=False)
    policy_version: Mapped[str] = mapped_column(
        String, default="publication-readiness-v1", nullable=False
    )
    technical_scope: Mapped[str] = mapped_column(String, default="pilot", nullable=False)
    manuscript_fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    input_manifest_fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    chapter_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assessment_status: Mapped[str] = mapped_column(
        String, default="NOT_YET_ASSESSED", nullable=False
    )
    freshness: Mapped[str] = mapped_column(String, default="CURRENT", nullable=False)
    readiness_detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    preflight_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class PublicationPreflight(Base):
    """A consumed Workbench publication-preflight report (MC-QUALITY-03D).

    The full report is stored as a dossier file; only the identity,
    fingerprints, counts and status live in the row. Never truncated."""

    __tablename__ = "publication_preflights"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    assessment_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("publication_assessments.id", ondelete="CASCADE")
    )
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    schema_id: Mapped[str] = mapped_column(
        String, default="workbench-publication-preflight-v1", nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String, default="", nullable=False)
    book_root: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scope: Mapped[str] = mapped_column(String, default="book", nullable=False)
    manuscript_fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    input_manifest_fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    chapters_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    snapshot_consistent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String, default="NOT_RUN", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class PublicationGateResult(Base):
    """One gate outcome for one assessment (MC-QUALITY-03D). Deterministic
    given the same snapshot and policy; history is never rewritten."""

    __tablename__ = "publication_gate_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        String, ForeignKey("publication_assessments.id", ondelete="CASCADE"), nullable=False
    )
    gate_id: Mapped[str] = mapped_column(String, nullable=False)
    gate_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    gate_group: Mapped[str] = mapped_column(String, default="", nullable=False)
    result: Mapped[str] = mapped_column(String, default="NOT_RUN", nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    waivable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    limitations: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class PublicationIssue(Base):
    """A normalized release issue (MC-QUALITY-03D). Blocking classification
    comes from gate policy and verified facts, never from AI severity."""

    __tablename__ = "publication_issues"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        String, ForeignKey("publication_assessments.id", ondelete="CASCADE"), nullable=False
    )
    gate_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    issue_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, default="advisory", nullable=False)
    verification_method: Mapped[str] = mapped_column(
        String, default="deterministic", nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="OPEN", nullable=False)
    waiver_eligibility: Mapped[str] = mapped_column(String, default="waivable", nullable=False)
    author_review_status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    source_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class PublicationApproval(Base):
    """Author approval of one exact release snapshot (MC-QUALITY-03D).
    Approval is not deployment and never carries across snapshots."""

    __tablename__ = "publication_approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        String, ForeignKey("publication_assessments.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    decision: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    manuscript_fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    input_manifest_fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    policy_version: Mapped[str] = mapped_column(
        String, default="publication-readiness-v1", nullable=False
    )
    accepted_limitation_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    freshness: Mapped[str] = mapped_column(String, default="CURRENT", nullable=False)
    reviewer: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class PublicationCalibrationReview(Base):
    """One human calibration verdict on a sampled 03C requirement (03D-01).
    Records what the requirement got right and what must change; the
    historical requirement rows themselves are never rewritten here."""

    __tablename__ = "publication_calibration_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    requirement_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("technical_evidence_requirements.id", ondelete="SET NULL")
    )
    sample_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    sample_reason: Mapped[str] = mapped_column(String, default="", nullable=False)
    claim_accurate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requirement_applicable: Mapped[str] = mapped_column(
        String, default="UNDETERMINED", nullable=False
    )
    necessary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    strictness_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    satisfied_by_evidence: Mapped[str] = mapped_column(String, default="unknown", nullable=False)
    gap_justified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority_proportionate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    would_block: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qualification_sufficient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_of: Mapped[str] = mapped_column(String, default="", nullable=False)
    verdict: Mapped[str] = mapped_column(String, default="", nullable=False)
    correction: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewer: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class ProjectIdentityDecision(Base):
    """Audit trail for software-project identity cutover (MC-PROJECTS-QUALITY-01).

    One row per repository path decision: automatic registration, explicit owner
    approval/rejection, or held-for-review. Append-mostly: rollback marks rows
    ``rolled_back`` instead of deleting them. ``path_norm`` is the normalized
    absolute path and carries a uniqueness constraint so repeated scans and
    repeated approvals are idempotent. ``repo_uid`` is the Git technical
    identity where available, never a display name or bare directory name.
    """

    __tablename__ = "project_identity_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_uid: Mapped[str] = mapped_column(Text, default="", nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    path_norm: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String, default="auto_registered", nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WebsitePostEvaluation(Base):
    """One blog-post editorial evaluation observation (MC-WEBSITES-POSTS-01).

    Website-scoped and chapter-independent: blog articles are not forced into
    book-specific records and no fictitious Project entries are introduced.
    Append-only history; staleness is derived at read time by comparing
    content_sha256 against the live file hash, never by mutation. Blocked,
    error and partial outcomes carry no scores (overall NULL).
    """

    __tablename__ = "website_post_evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    website_id: Mapped[str] = mapped_column(String, nullable=False)
    article_identity: Mapped[str] = mapped_column(String, nullable=False)
    relpath: Mapped[str] = mapped_column(String, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String, nullable=False)
    rubric_id: Mapped[str] = mapped_column(String, default="blog-editorial-v1", nullable=False)
    rubric_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, default="1", nullable=False)
    requested_model: Mapped[str | None] = mapped_column(String)
    actual_model: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="CURRENT", nullable=False)
    overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    aggregation_method: Mapped[str] = mapped_column(
        String, default="sum_dimensions_v1", nullable=False
    )
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    assessment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    improvements: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    findings: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    uncertainty: Mapped[str] = mapped_column(Text, default="", nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    execution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    previous_evaluation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("website_post_evaluations.id", ondelete="SET NULL")
    )
    supersedes: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WebsitePostReview(Base):
    """Author decision on one evaluation finding (MC-WEBSITES-POSTS-01).

    Append-only and separate from AI judgments: ACCEPT / REJECT / DEFER /
    INVESTIGATE mirror the quality-review conventions.
    """

    __tablename__ = "website_post_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    evaluation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("website_post_evaluations.id", ondelete="CASCADE")
    )
    finding_id: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewer: Mapped[str] = mapped_column(String, default="", nullable=False)
    source_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WebsitePostWriterObservation(Base):
    """Deterministic Writer artifact observation for a blog post (BLOG-01 D5).

    Append-only and deliberately separate from editorial evaluations:
    editorial readers are rubric-blind in places, so Writer evidence gets
    its own table and can never masquerade as an editorial verdict.
    Freshness is derived at read time (body_sha256 vs the live evaluated
    body), never by overwriting. A rename creates a new identity with no
    transferred history.
    """

    __tablename__ = "website_post_writer_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    website_id: Mapped[str] = mapped_column(String, nullable=False)
    article_identity: Mapped[str] = mapped_column(String, nullable=False)
    relpath: Mapped[str] = mapped_column(String, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String, nullable=False)
    body_sha256: Mapped[str] = mapped_column(String, nullable=False)
    producer_runtime: Mapped[str] = mapped_column(String, default="artifact", nullable=False)
    method: Mapped[str] = mapped_column(String, default="analyze_text", nullable=False)
    method_version: Mapped[str] = mapped_column(
        String, default="writer-artifact-detection.v1", nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="complete", nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String, nullable=False)
    envelope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String)
    policy_version: Mapped[str] = mapped_column(String, default="blog-auto-v1", nullable=False)
    flags_version: Mapped[str] = mapped_column(
        String, default="writer-artifact-detection.v1", nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class PublicationFollowup(Base):
    """Governed follow-up promoting a publishing blocker to explicit work
    (MC-PUBLISH-03).

    Carries provenance (evidence type, source reference, fingerprint,
    observed_at) so the follow-up can be re-checked against fresh evidence:
    open -> re-evidenced -> closed. History is append-only; closing never
    deletes the record. The actual work item lives in the linked task or
    decision; this row is the traceable bridge between evidence and action.
    """

    __tablename__ = "publication_followups"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=False)
    book_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    target_type: Mapped[str] = mapped_column(String, default="task", nullable=False)
    target_id: Mapped[str | None] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, default="", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    reviewer: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class SoftwareCharter(Base):
    """Owner-editable project purpose contract (MC-PROJECTS-QUALITY-02 Phase 1).

    Persisted in Mission Control; no repository files required. ``draft`` rows
    are unconfirmed inference; only ``confirmed`` rows express owner intent.
    Revisions are append-only (``supersedes``); evaluations pin the revision
    they used so charter edits make prior assessments stale, never wrong.
    """

    __tablename__ = "software_charters"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)
    purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    users: Mapped[str] = mapped_column(Text, default="", nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    interfaces: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    acceptance: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    non_goals: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    constraints: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    lifecycle: Mapped[str] = mapped_column(Text, default="", nullable=False)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    verification_expectations: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    supersedes: Mapped[str | None] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class SoftwareEvaluation(Base):
    """One evidence-backed software quality assessment (MC-PROJECTS-QUALITY-02).

    Append-only observation. Scores live in ``dimensions``; ``overall`` is NULL
    unless the aggregation policy is satisfied. Freshness is derived at read
    time (head/charter/rubric drift), never by overwriting.
    """

    __tablename__ = "software_evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    charter_id: Mapped[str | None] = mapped_column(String)
    charter_revision: Mapped[int | None] = mapped_column(Integer)
    repo_uid: Mapped[str] = mapped_column(Text, default="", nullable=False)
    repo_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    head_sha: Mapped[str | None] = mapped_column(String)
    evidence_fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    evidence_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rubric_id: Mapped[str] = mapped_column(String, default="software-quality-v1", nullable=False)
    rubric_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, default="1", nullable=False)
    requested_model: Mapped[str | None] = mapped_column(String)
    observed_model: Mapped[str | None] = mapped_column(String)
    model_route: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_attainable: Mapped[float] = mapped_column(Float, default=1000, nullable=False)
    coverage_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    uncertainty: Mapped[str] = mapped_column(Text, default="", nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    execution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    prompt_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    previous_evaluation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("software_evaluations.id", ondelete="SET NULL")
    )
    supersedes: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String)


class SoftwareEvalReview(Base):
    """Independent second review of one evaluation (MC-PROJECTS-QUALITY-02).

    Judges the original evidence, not the first model's conclusions.
    Disagreements are recorded here, never by editing the evaluation.
    """

    __tablename__ = "software_eval_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    evaluation_id: Mapped[str] = mapped_column(
        String, ForeignKey("software_evaluations.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_model: Mapped[str] = mapped_column(String, default="", nullable=False)
    model_route: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    verdict: Mapped[str] = mapped_column(String, default="", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    finding_verdicts: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    usage_info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String)


class SoftwareFinding(Base):
    """Persistent, deduplicated quality finding (MC-PROJECTS-QUALITY-02).

    Identity is ``project_id + fingerprint`` (stable across evaluations).
    Owner decisions live in ``software_finding_reviews``; verification state
    advances only on evidence, never on implementation claims.
    """

    __tablename__ = "software_findings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String, default="medium", nullable=False)
    component: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    expected: Mapped[str] = mapped_column(Text, default="", nullable=False)
    observed: Mapped[str] = mapped_column(Text, default="", nullable=False)
    impact: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proposal: Mapped[str] = mapped_column(Text, default="", nullable=False)
    verification_required: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_evaluations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String, default="proposed", nullable=False)
    resolution_evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    history: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class SoftwareFindingReview(Base):
    """Owner decision on one finding (ACCEPT/REJECT/DEFER/INVESTIGATE)."""

    __tablename__ = "software_finding_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    finding_id: Mapped[str] = mapped_column(
        String, ForeignKey("software_findings.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewer: Mapped[str] = mapped_column(String, default="", nullable=False)
    source_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class SoftwarePrompt(Base):
    """Saved implementation prompt with provenance (MC-PROJECTS-QUALITY-02).

    Generating a prompt never modifies a repository or launches an agent;
    execution stays an explicit, separately authorized action.
    """

    __tablename__ = "software_prompts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    finding_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scope: Mapped[str] = mapped_column(Text, default="", nullable=False)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoObservationSource(Base):
    """WORK-OUTCOME-01 W1: identity of an observed source system.

    ``kind`` is ``opencode`` or ``git``; ``identity`` is the source path
    (OpenCode DB path or repository worktree). No conversation bodies here.
    """

    __tablename__ = "wo_observation_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    identity: Mapped[str] = mapped_column(String, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String, default="", nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoObservationRun(Base):
    """WORK-OUTCOME-01 W1: one bounded observation pass with stats.

    Append-only. ``status`` is ``completed`` | ``locked`` |
    ``source_unavailable`` | ``failed``. Checkpoints advance only on
    ``completed`` runs (see service).
    """

    __tablename__ = "wo_observation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_kind: Mapped[str] = mapped_column(String, default="opencode", nullable=False)
    status: Mapped[str] = mapped_column(String, default="running", nullable=False)
    window_from_ms: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    window_to_ms: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sessions_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    messages_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parts_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signals_produced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    finished_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoCheckpoint(Base):
    """WORK-OUTCOME-01 W1: durable high-water mark per (source, cursor).

    Cursors: ``session_updated`` (time_updated,id) and ``message_created``
    (time_created,id). Persisted only after a successful run.
    """

    __tablename__ = "wo_checkpoints"

    source_kind: Mapped[str] = mapped_column(String, primary_key=True)
    cursor_key: Mapped[str] = mapped_column(String, primary_key=True)
    cursor_value_ms: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tiebreak_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoSignal(Base):
    """WORK-OUTCOME-01 W1: deterministic candidate signal with provenance.

    W1 extracts only; nothing here is a verified relationship. Stable id is
    ``sha1(source_ref|signal_type|value_digest)`` so replays are idempotent.
    """

    __tablename__ = "wo_signals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str | None] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(String, default="opencode", nullable=False)
    source_ref: Mapped[str] = mapped_column(String, nullable=False)
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    value_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    evidence_class: Mapped[str] = mapped_column(String, default="inferred", nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(SafeJSONDict, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoEpisode(Base):
    """WORK-OUTCOME-01 W2: coherent unit of purposeful work.

    ``status`` is reconstruction status (candidate/established) — never
    outcome completion (W4 owns that). ``parent_id`` is a plain text
    reference with cycle rejection in the service (no FK ordering hazard).
    """

    __tablename__ = "wo_episodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_key: Mapped[str] = mapped_column(String, default="", nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kind: Mapped[str] = mapped_column(String, default="cluster", nullable=False)
    status: Mapped[str] = mapped_column(String, default="candidate", nullable=False)
    parent_id: Mapped[str | None] = mapped_column(Text)
    first_seen_ms: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_seen_ms: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    source_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoEpisodeAssociation(Base):
    """WORK-OUTCOME-01 W2: one explainable episode link.

    ``method`` is explicit|derived|candidate|rejected; ``confidence`` is
    explicit|strong|moderate|weak (heuristic labels, never probabilities).
    ``valid=0`` retires superseded links without deleting history.
    """

    __tablename__ = "wo_episode_associations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    assoc_type: Mapped[str] = mapped_column(String, nullable=False)
    target_ref: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, default="candidate", nullable=False)
    confidence: Mapped[str] = mapped_column(String, default="weak", nullable=False)
    reason: Mapped[str] = mapped_column(String, default="", nullable=False)
    signals: Mapped[list[str]] = mapped_column(SafeJSONList, nullable=False)
    recon_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valid: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoReconRun(Base):
    """WORK-OUTCOME-01 W2: one bounded deterministic reconstruction pass."""

    __tablename__ = "wo_recon_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="running", nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(SafeJSONDict, nullable=False)
    episodes_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    associations_made: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unresolved_observations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    finished_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoObjective(Base):
    """WORK-OUTCOME-01 W3: extracted work objective (intent, not verdict)."""

    __tablename__ = "wo_objectives"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    authority: Mapped[str] = mapped_column(String, default="inferred", nullable=False)
    status: Mapped[str] = mapped_column(String, default="current", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supersedes: Mapped[str | None] = mapped_column(Text)
    source_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    extractor: Mapped[str] = mapped_column(String, default="", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoRequirement(Base):
    """WORK-OUTCOME-01 W3: atomic requirement with authority and provenance."""

    __tablename__ = "wo_requirements"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    objective_id: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    authority: Mapped[str] = mapped_column(String, default="ambiguous", nullable=False)
    mandatory: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    kind: Mapped[str] = mapped_column(String, default="functional", nullable=False)
    state: Mapped[str] = mapped_column(String, default="proposed", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supersedes: Mapped[str | None] = mapped_column(Text)
    source_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    extractor: Mapped[str] = mapped_column(String, default="", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoClaim(Base):
    """WORK-OUTCOME-01 W3: material participant claim (never a verdict)."""

    __tablename__ = "wo_claims"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    claimant: Mapped[str] = mapped_column(String, default="", nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scope: Mapped[str] = mapped_column(String, default="", nullable=False)
    source_ref: Mapped[str] = mapped_column(String, default="", nullable=False)
    qualified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoEvidenceLink(Base):
    """WORK-OUTCOME-01 W3: candidate evidence binding (W3 proposes, W4 judges)."""

    __tablename__ = "wo_evidence_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    requirement_id: Mapped[str | None] = mapped_column(Text)
    claim_id: Mapped[str | None] = mapped_column(Text)
    evidence_kind: Mapped[str] = mapped_column(String, default="", nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    method: Mapped[str] = mapped_column(String, default="candidate", nullable=False)
    confidence: Mapped[str] = mapped_column(String, default="weak", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoTriageResult(Base):
    """WORK-OUTCOME-01 W3: deterministic or model triage verdict per session."""

    __tablename__ = "wo_triage_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    classification: Mapped[str] = mapped_column(String, default="AMBIGUOUS", nullable=False)
    method: Mapped[str] = mapped_column(String, default="deterministic", nullable=False)
    reason: Mapped[str] = mapped_column(String, default="", nullable=False)
    queued_for_model: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    run_id: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoExtractionRun(Base):
    """WORK-OUTCOME-01 W3: extraction ledger + cache key + cost record."""

    __tablename__ = "wo_extraction_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String, default="", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, default="", nullable=False)
    extractor: Mapped[str] = mapped_column(String, default="", nullable=False)
    input_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="accepted", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoRequirementAssessment(Base):
    """WORK-OUTCOME-01 W4: one requirement verdict with provenance."""

    __tablename__ = "wo_requirement_assessments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String, nullable=False)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    verdict: Mapped[str] = mapped_column(String, default="insufficient_evidence",
                                         nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(SafeJSONList, nullable=False)
    method: Mapped[str] = mapped_column(String, default="deterministic", nullable=False)
    evaluator: Mapped[str] = mapped_column(String, default="", nullable=False)
    rubric_version: Mapped[str] = mapped_column(String, default="w4-v1", nullable=False)
    confidence: Mapped[str] = mapped_column(String, default="weak", nullable=False)
    limitations: Mapped[str] = mapped_column(Text, default="", nullable=False)
    missing_evidence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoClaimVerification(Base):
    """WORK-OUTCOME-01 W4: one claim verification (never upgrades a claim
    by itself; verification is the evidence row)."""

    __tablename__ = "wo_claim_verifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_id: Mapped[str] = mapped_column(String, nullable=False)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    verdict: Mapped[str] = mapped_column(String, default="reported_only", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(SafeJSONList, nullable=False)
    source_digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    method: Mapped[str] = mapped_column(String, default="deterministic", nullable=False)
    evaluator: Mapped[str] = mapped_column(String, default="", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoEpisodeAssessment(Base):
    """WORK-OUTCOME-01 W4: three independent perspectives per episode."""

    __tablename__ = "wo_episode_assessments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    execution_verdict: Mapped[str] = mapped_column(String, default="unknown",
                                                   nullable=False)
    execution_rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    outcome_verdict: Mapped[str] = mapped_column(String, default="unknown",
                                                nullable=False)
    outcome_rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    completion_verdict: Mapped[str] = mapped_column(String, default="unknown",
                                                   nullable=False)
    completion_rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evaluator: Mapped[str] = mapped_column(String, default="", nullable=False)
    rubric_version: Mapped[str] = mapped_column(String, default="w4-v1", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoFinding(Base):
    """WORK-OUTCOME-01 W4: actionable finding or obligation, deduplicated by
    (episode, requirement, kind) — never by wording alone."""

    __tablename__ = "wo_findings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    requirement_id: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String, default="verification_gap",
                                      nullable=False)
    severity: Mapped[str] = mapped_column(String, default="minor", nullable=False)
    status: Mapped[str] = mapped_column(String, default="suspected", nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(SafeJSONList, nullable=False)
    next_action: Mapped[str] = mapped_column(Text, default="", nullable=False)
    closure_evidence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoEvalRun(Base):
    """WORK-OUTCOME-01 W4: one bounded evaluation pass."""

    __tablename__ = "wo_eval_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[dict[str, Any]] = mapped_column(SafeJSONDict, nullable=False)
    status: Mapped[str] = mapped_column(String, default="running", nullable=False)
    episodes_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requirements_assessed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claims_verified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    findings_raised: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    finished_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoRequirementSource(Base):
    """WORK-OUTCOME-01 W6A: provenance for one recovered requirement or
    objective — repo doc, git commit, session message, or human attestation.
    Authority is never inferred from existence alone; authority_basis records
    why (e.g. pre-change review, explicit commissioning message)."""

    __tablename__ = "wo_requirement_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    requirement_id: Mapped[str | None] = mapped_column(Text)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    source_kind: Mapped[str] = mapped_column(String, default="repo_doc", nullable=False)
    path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    revision: Mapped[str] = mapped_column(String, default="", nullable=False)
    digest: Mapped[str] = mapped_column(String, default="", nullable=False)
    authority_basis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoFindingGroup(Base):
    """WORK-OUTCOME-01 W6B: presentation/reconciliation layer over findings.
    Members are preserved; closing a group requires closing evidence per
    member finding. Severity = max member severity (never inflated)."""

    __tablename__ = "wo_finding_groups"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_key: Mapped[str] = mapped_column(String, default="", nullable=False)
    subject: Mapped[str] = mapped_column(String, default="", nullable=False)
    gap_class: Mapped[str] = mapped_column(String, default="", nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String, default="minor", nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoFindingGroupMember(Base):
    """WORK-OUTCOME-01 W6B: group membership (finding never deleted)."""

    __tablename__ = "wo_finding_group_members"

    group_id: Mapped[str] = mapped_column(String, primary_key=True)
    finding_id: Mapped[str] = mapped_column(String, primary_key=True)


class WoEvalState(Base):
    """WORK-OUTCOME-01 W6C: freshness + queue state per episode.
    queue_status is current|stale|queued|running|blocked|failed."""

    __tablename__ = "wo_eval_state"

    episode_id: Mapped[str] = mapped_column(String, primary_key=True)
    last_assessment_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    stale: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stale_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    queue_status: Mapped[str] = mapped_column(String, default="current", nullable=False)
    last_observed_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoProposal(Base):
    """WORK-OUTCOME-01 W7: evidence-bound corrective work proposal.

    Drafts live here; authorization is an explicit event (never self).
    Approval binds (version, scope_hash); scope edits after
    ready_for_review bump version and void prior approval."""

    __tablename__ = "wo_proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    group_id: Mapped[str | None] = mapped_column(Text)
    project_key: Mapped[str] = mapped_column(String, default="", nullable=False)
    action_category: Mapped[str] = mapped_column(String, default="", nullable=False)
    objective: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scope: Mapped[str] = mapped_column(Text, default="", nullable=False)
    exclusions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="", nullable=False)
    required_verification: Mapped[str] = mapped_column(Text, default="", nullable=False)
    suggested_route: Mapped[str] = mapped_column(String, default="", nullable=False)
    cost_constraints: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risk: Mapped[str] = mapped_column(String, default="unknown", nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    scope_hash: Mapped[str] = mapped_column(String, default="", nullable=False)
    closure_status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoProposalFinding(Base):
    """WORK-OUTCOME-01 W7: proposal↔finding linkage (findings never moved)."""

    __tablename__ = "wo_proposal_findings"

    proposal_id: Mapped[str] = mapped_column(String, primary_key=True)
    finding_id: Mapped[str] = mapped_column(String, primary_key=True)


class WoProposalEvent(Base):
    """WORK-OUTCOME-01 W7: append-only proposal lifecycle history."""

    __tablename__ = "wo_proposal_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String, nullable=False)
    from_status: Mapped[str] = mapped_column(String, default="", nullable=False)
    to_status: Mapped[str] = mapped_column(String, default="", nullable=False)
    actor: Mapped[str] = mapped_column(String, default="", nullable=False)
    reason: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoRequirementConfirmation(Base):
    """WORK-OUTCOME-01 W7: human requirement decision with provenance.
    Amendments create new WoRequirement versions via the service; this row
    records the decision itself."""

    __tablename__ = "wo_requirement_confirmations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String, nullable=False)
    episode_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    decision: Mapped[str] = mapped_column(String, default="", nullable=False)
    reviewer: Mapped[str] = mapped_column(String, default="", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    amended_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoExecutionLink(Base):
    """WORK-OUTCOME-01 W7: proposal↔execution trace (manual handoff included)."""
    __tablename__ = "wo_execution_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String, nullable=False)
    route: Mapped[str] = mapped_column(String, default="", nullable=False)
    external_ref: Mapped[str] = mapped_column(String, default="", nullable=False)
    model: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="", nullable=False)
    started_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    finished_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    session_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    commit_sha: Mapped[str] = mapped_column(String, default="", nullable=False)
    test_receipt_ref: Mapped[str] = mapped_column(String, default="",
                                                  nullable=False)
    review_ref: Mapped[str] = mapped_column(String, default="", nullable=False)
    envelope_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class WoWorkEnvelope(Base):
    """WORK-OUTCOME-01 W8: prospective work envelope (metadata, not context)."""

    __tablename__ = "wo_work_envelopes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String, default="work-envelope.v1", nullable=False)
    programme_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    stage_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    objective_ref: Mapped[str] = mapped_column(String, default="", nullable=False)
    requirement_refs: Mapped[list[str]] = mapped_column(SafeJSONList,
                                                        nullable=False)
    repositories: Mapped[list[str]] = mapped_column(SafeJSONList,
                                                   nullable=False)
    commission_digest: Mapped[str] = mapped_column(String, default="",
                                                   nullable=False)
    authorization_ref: Mapped[str] = mapped_column(Text, default="",
                                                   nullable=False)
    acceptance_policy_ref: Mapped[str] = mapped_column(
        String, default="", nullable=False)
    parent_work_id: Mapped[str | None] = mapped_column(Text)
    originating_findings: Mapped[list[str]] = mapped_column(
        SafeJSONList, default=list, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    supersedes: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class AitestProject(Base):
    """AITEST-02 R12: a pytest project registered for central testing visibility."""

    __tablename__ = "aitest_projects"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="", nullable=False)
    root: Mapped[str] = mapped_column(String, default="", nullable=False)
    remote_url: Mapped[str] = mapped_column(String, default="", nullable=False)
    mc_project_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    integration_state: Mapped[str] = mapped_column(String, default="observation", nullable=False)
    policy: Mapped[str] = mapped_column(String, default="observe", nullable=False)
    aitest_version: Mapped[str] = mapped_column(String, default="", nullable=False)
    last_receipt_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    last_status: Mapped[str] = mapped_column(String, default="", nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class AitestTest(Base):
    """AITEST-02 R12: one inventoried test with measured classification."""

    __tablename__ = "aitest_tests"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    logical_id: Mapped[str] = mapped_column(String, primary_key=True)
    relpath: Mapped[str] = mapped_column(String, default="", nullable=False)
    class_name: Mapped[str] = mapped_column(String, default="", nullable=False)
    func_name: Mapped[str] = mapped_column(String, default="", nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    band: Mapped[str] = mapped_column(String, default="UNASSESSED", nullable=False)
    lifecycle: Mapped[str] = mapped_column(String, default="DISCOVERED", nullable=False)
    last_outcome: Mapped[str] = mapped_column(String, default="", nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String, default="", nullable=False)


class AitestReceipt(Base):
    """AITEST-02 R12: execution receipts (partial runs never read as passes)."""

    __tablename__ = "aitest_receipts"

    execution_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="PENDING", nullable=False)
    discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    executed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quarantined: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deferred: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timed_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unobserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    receipt_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class AitestIssue(Base):
    """AITEST-02 R12/R15: unresolved testing problems (deduplicated by project+test+kind)."""

    __tablename__ = "aitest_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    test_logical_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    kind: Mapped[str] = mapped_column(String, default="UNKNOWN", nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class AitestEventSeen(Base):
    """AITEST-02 R12: idempotent event ingestion (exactly-once per event_id)."""

    __tablename__ = "aitest_events_seen"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    received_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)


class InspectRun(Base):
    """MC-INSPECT-04: durable, cancellable Inspect CLI operations requested from the UI.

    One row per requested operation (inspect, enrich, validate, export, stamp,
    refresh). Reconciliation happens on read via pid liveness; a finished run
    records the CLI's own reported result parsed from its log. Runs never
    modify inspected source repos and never replace published Inspect outputs.
    """

    __tablename__ = "inspect_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    repository_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    mission_application_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    operation: Mapped[str] = mapped_column(String, default="inspect", nullable=False)
    scope: Mapped[str] = mapped_column(String, default="full", nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    command: Mapped[str] = mapped_column(String, default="", nullable=False)
    log_path: Mapped[str] = mapped_column(String, default="", nullable=False)
    head_sha: Mapped[str] = mapped_column(String, default="", nullable=False)
    requested_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    started_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    finished_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_status: Mapped[str] = mapped_column(String, default="", nullable=False)
    result_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)


class AitestQuality(Base):
    """AITEST-03: latest per-project quality assessment summary."""

    __tablename__ = "aitest_quality"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    mode: Mapped[str] = mapped_column(String, default="", nullable=False)
    snapshot: Mapped[str] = mapped_column(String, default="", nullable=False)
    tests_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    findings_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    recommendations_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    verification_gaps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    redundancy_candidates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coverage_percent: Mapped[float | None] = mapped_column(Float)
    mutations_attempted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mutations_killed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latest_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    cost_ms: Mapped[float] = mapped_column(Float, default=0, nullable=False)


class AitestRun(Base):
    """AITEST-02D-UI: one UI-requested testing execution (durable, cancellable)."""

    __tablename__ = "aitest_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    pid: Mapped[int | None] = mapped_column(Integer)
    command: Mapped[str] = mapped_column(Text, default="", nullable=False)
    requested_at: Mapped[str] = mapped_column(String, default=now_iso, nullable=False)
    started_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    finished_at: Mapped[str] = mapped_column(String, default="", nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    receipt_execution_id: Mapped[str] = mapped_column(String, default="", nullable=False)
    verification_status: Mapped[str] = mapped_column(String, default="", nullable=False)
    counts_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    log_path: Mapped[str] = mapped_column(String, default="", nullable=False)
