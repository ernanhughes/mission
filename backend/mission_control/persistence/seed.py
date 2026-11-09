"""Seed shipped defaults without ever overwriting user configuration."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from mission_control.activity.service import record_activity
from mission_control.config import RuntimeSettings
from mission_control.models import (
    Application,
    Book,
    CultivationGoal,
    DiscoveryRoot,
    LaunchDefinition,
    Outcome,
    Project,
    ProjectRelationship,
    ProjectRepository,
    Repository,
    Setting,
)
from mission_control.persistence.db import now_iso

logger = logging.getLogger(__name__)

DEFAULT_EXCLUSIONS = [
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".next",
    "dist",
    "build",
    "coverage",
    ".coverage",
    ".workbench",
    ".roborev",
    "*.egg-info",
    "*-review-pack",
    "*-review-pack-v3",
    "*-bundles",
    "p1-runs",
    "worker-smoke",
    "*.tmp",
    "*.log",
]

DEFAULT_SETTINGS: dict[str, Any] = {
    "discovery": {
        "exclusions": DEFAULT_EXCLUSIONS,
        "max_depth": 1,
        "max_candidates": 500,
        "timeout_seconds": 120,
        "git_timeout_seconds": 5,
    },
    "editor": {
        "command": "",
        "arguments": [],
        "append_path": True,
    },
    "browser": {
        "open_mode": "new_tab",
    },
    "processes": {
        "max_managed": 5,
        "health_check_interval_seconds": 30,
        "log_tail_lines": 200,
    },
    "adapters": {
        "refresh_interval_minutes": 10,
        "timeout_seconds": 5,
    },
    "retention": {
        "activity_days": 365,
        "briefing_days": 90,
        "log_days": 30,
    },
    "ai": {
        "enabled": False,
        "consent": False,
        "provider": "openai-compatible",
        "base_url": "",
        "model": "",
        "api_key_env": "OPENAI_API_KEY",
        "timeout_seconds": 45,
    },
    "startup": {
        "profile_enabled": False,
        "profile_applications": [],
    },
}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Default configuration is missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Default configuration is not a mapping: {path}")
    return data


def repository_id(path: str) -> str:
    return "repo-" + hashlib.sha1(path.casefold().encode("utf-8")).hexdigest()[:16]


def seed_cultivation(session) -> None:
    """Seed the starter goal catalogue without ever overwriting user goals.

    Estimates stay labelled estimates. The blog-post milestone is a
    user-attested baseline with no invented date. Nothing else is pre-filled.
    """
    from mission_control.cultivation.service import (
        DEFAULT_RANKS,
        DEFAULT_STAGES,
        create_goal,
    )

    _get_or_create_setting(
        session, "cultivation",
        {"stages": [dict(stage) for stage in DEFAULT_STAGES],
         "ranks": [dict(rank) for rank in DEFAULT_RANKS]})

    catalogue = [
        {"id": "published_books", "name": "Published Books",
         "description": "Distinct published book titles across all collections.",
         "category": "books", "unit": "books", "target_value": 100,
         "measurement_type": "count", "qualifying_stage": "published",
         "baseline_value": 30.0,
         "baseline_note": ("Owner estimate of ~30 published books; awaiting inventory "
                           "verification. Reduce this starting count as historical titles "
                           "are backfilled as tracked items."),
         "baseline_provenance": "estimate",
         "completion_criteria": ("A distinct published book title. Different formats or "
                                 "editions of the same book do not count separately unless "
                                 "the owner defines them as separate items."),
         "milestones": [1.0, 10.0, 25.0, 50.0, 75.0, 100.0],
         "priority": 10, "pinned": True, "pin_order": 0, "evidence_source": "manual"},
        {"id": "fiction_books", "name": "Fiction Books",
         "description": "Published fiction titles. Also counts toward Published Books.",
         "category": "books", "unit": "books", "target_value": 100,
         "measurement_type": "count", "qualifying_stage": "published",
         "milestones": [1.0, 10.0, 25.0, 50.0, 75.0, 100.0],
         "priority": 200, "pinned": False, "evidence_source": "manual"},
        {"id": "technical_books", "name": "Technical Books",
         "description": "Published technical titles. Also counts toward Published Books.",
         "category": "books", "unit": "books", "target_value": 100,
         "measurement_type": "count", "qualifying_stage": "published",
         "milestones": [1.0, 10.0, 25.0, 50.0, 75.0, 100.0],
         "priority": 200, "pinned": False, "evidence_source": "manual"},
        {"id": "blog_posts", "name": "Blog Posts",
         "description": "Published blog posts.",
         "category": "writing", "unit": "posts", "target_value": 100,
         "measurement_type": "count", "qualifying_stage": "published",
         "baseline_value": 100.0,
         "baseline_note": ("Reported achieved during the previous year. User-attested; "
                           "exact completion date not recorded and not independently verified."),
         "baseline_provenance": "user_assertion",
         "milestones": [1.0, 10.0, 25.0, 50.0, 75.0, 100.0],
         "priority": 20, "pinned": True, "pin_order": 10,
         "state": "achieved", "evidence_source": "manual"},
        {"id": "movies", "name": "Movies",
         "description": "Completed/released films.",
         "category": "film", "unit": "films", "target_value": 100,
         "measurement_type": "count", "qualifying_stage": "published",
         "milestones": [1.0, 10.0, 25.0, 50.0, 75.0, 100.0],
         "priority": 200, "pinned": False, "evidence_source": "manual"},
        {"id": "songs", "name": "Songs",
         "description": "Completed/released compositions.",
         "category": "music", "unit": "songs", "target_value": 100,
         "measurement_type": "count", "qualifying_stage": "published",
         "milestones": [1.0, 10.0, 25.0, 50.0, 75.0, 100.0],
         "priority": 200, "pinned": False, "evidence_source": "manual"},
        {"id": "research_papers", "name": "Research Papers",
         "description": "Completed papers meeting a chosen publication standard.",
         "category": "research", "unit": "papers", "target_value": 100,
         "measurement_type": "count", "qualifying_stage": "published",
         "completion_criteria": "A completed paper meeting the publication standard named in its evidence.",
         "milestones": [1.0, 10.0, 25.0, 50.0, 75.0, 100.0],
         "priority": 200, "pinned": False, "evidence_source": "manual"},
        {"id": "applications", "name": "Applications",
         "description": "Shipped, usable applications.",
         "category": "software", "unit": "apps", "target_value": 100,
         "measurement_type": "count", "qualifying_stage": "published",
         "milestones": [1.0, 10.0, 25.0, 50.0, 75.0, 100.0],
         "priority": 200, "pinned": False, "evidence_source": "manual"},
        {"id": "repositories", "name": "Repositories",
         "description": "Substantive, distinct Git repositories.",
         "category": "software", "unit": "repos", "target_value": 1000,
         "measurement_type": "count", "qualifying_stage": "published",
         "milestones": [100.0, 250.0, 500.0, 750.0, 1000.0],
         "priority": 200, "pinned": False, "evidence_source": "manual"},
        {"id": "perfect_repositories", "name": "Perfect Repositories",
         "description": "Repositories meeting an explicit, independently checked quality standard.",
         "category": "software", "unit": "repos", "target_value": 100,
         "measurement_type": "qualified_count", "qualifying_stage": "published",
         "completion_criteria": ("Revisable qualification standard: passing automated tests, "
                                 "documentation complete, architectural compliance, no unresolved "
                                 "critical review findings, relevant security checks, accepted "
                                 "independent review. Qualification may need renewal; it is not a "
                                 "guarantee the repository stays defect-free."),
         "milestones": [1.0, 10.0, 25.0, 50.0, 75.0, 100.0],
         "priority": 200, "pinned": False, "evidence_source": "manual"},
        {"id": "body_weight", "name": "Body Weight",
         "description": "Optional private decreasing-weight target.",
         "category": "health", "unit": "lb", "target_value": 150,
         "measurement_type": "threshold_down",
         "completion_criteria": "Optional, private. No baseline recorded yet.",
         "priority": 300, "pinned": False, "privacy": "private", "evidence_source": "manual"},
        {"id": "press_ups", "name": "Press-ups",
         "description": "Press-ups achieved in a day (switch to recurring for a sustained habit).",
         "category": "health", "unit": "press-ups", "target_value": 100,
         "measurement_type": "threshold_up",
         "priority": 300, "pinned": False, "privacy": "private", "evidence_source": "manual"},
    ]
    for entry in catalogue:
        if session.get(CultivationGoal, entry["id"]) is None:
            create_goal(session, entry)
    logger.info("Seeded cultivation starter catalogue")


def _get_or_create_setting(session: Session, key: str, value: Any) -> None:
    if session.get(Setting, key) is None:
        session.add(Setting(key=key, value=value, updated_at=now_iso()))


def seed_defaults(session: Session, settings: RuntimeSettings) -> None:
    if not settings.seed_defaults:
        return

    # Root discovery paths are editable and survive restarts.
    for root, display, category in (
        ("C:\\Projects", "Projects", "software"),
        ("C:\\books", "Books", "books"),
        ("C:\\book-projects", "Book Projects", "books"),
    ):
        if Path(root).exists():
            existing = session.get(DiscoveryRoot, root)
            if existing is None:
                session.add(DiscoveryRoot(path=root, enabled=True, added_at=now_iso(),
                                          display_name=display, category=category, git_enabled=True))
            else:
                if not (existing.display_name or "").strip():
                    existing.display_name = display
                if not (existing.category or "").strip():
                    existing.category = category
    for key, value in DEFAULT_SETTINGS.items():
        _get_or_create_setting(session, key, value)
    _get_or_create_setting(session, "ui", {"theme": "system"})
    _get_or_create_setting(session, "workspace", {"current_project_id": None})

    defaults_dir = settings.config_dir / "defaults"
    outcomes = _read_yaml(defaults_dir / "outcomes.yaml").get("outcomes", [])
    for item in outcomes:
        if session.get(Outcome, item["id"]) is None:
            session.add(
                Outcome(
                    id=item["id"],
                    name=item["name"],
                    description=item.get("description", ""),
                    status=item.get("status", "active"),
                    url=item.get("url"),
                    notes=item.get("notes", ""),
                    created_at=now_iso(),
                    updated_at=now_iso(),
                )
            )

    projects = _read_yaml(defaults_dir / "projects.yaml").get("projects", [])
    for item in projects:
        project = session.get(Project, item["id"])
        if project is None:
            project = Project(
                id=item["id"],
                name=item["name"],
                description=item.get("description", ""),
                kind=item.get("kind", "project"),
                status=item.get("status", "active"),
                priority=int(item.get("priority", 100)),
                pinned=bool(item.get("pinned", False)),
                archived=False,
                display_order=int(item.get("display_order", 100)),
                current_milestone=item.get("current_milestone", ""),
                next_action=item.get("next_action", ""),
                notes=item.get("notes", ""),
                created_at=now_iso(),
                updated_at=now_iso(),
            )
            session.add(project)
        for repo_item in item.get("repositories", []):
            path = repo_item["path"]
            repo = session.scalar(select(Repository).where(Repository.path == path))
            if repo is None:
                repo = Repository(
                    id=repository_id(path),
                    path=path,
                    name=repo_item.get("name") or Path(path).name,
                    classification=repo_item.get("classification", "unknown"),
                    confidence=float(repo_item.get("confidence", 0.0)),
                    evidence=repo_item.get("evidence", []),
                    source_root=str(Path(path).parent),
                    is_git=(Path(path) / ".git").exists(),
                    accessible=Path(path).exists(),
                    candidate=False,
                    first_seen_at=now_iso(),
                    last_observed_at=None,
                )
                session.add(repo)
            elif session.get(ProjectRepository, (project.id, repo.id)) is None:
                pass
            session.flush()
            link = session.get(ProjectRepository, (project.id, repo.id))
            if link is None:
                session.add(
                    ProjectRepository(
                        project_id=project.id,
                        repository_id=repo.id,
                        role=repo_item.get("role", "supporting"),
                    )
                )
        outcome_map = {
            "language": ["books", "programmer-ie"],
            "inference": ["books"],
            "math": ["books"],
        }.get(project.id, [])
        for outcome_id in outcome_map:
            target = f"{project.id}-outcome-{outcome_id}"
            if session.scalar(select(ProjectRelationship).where(ProjectRelationship.id == target)) is None:
                session.add(
                    ProjectRelationship(
                        id=target,
                        project_id=project.id,
                        target_type="outcome",
                        target_id=outcome_id,
                        relationship="contributes_to",
                        created_at=now_iso(),
                    )
                )

    books = _read_yaml(defaults_dir / "books.yaml").get("books", [])
    for item in books:
        existing = session.scalar(select(Book).where(Book.project_id == item["project_id"]))
        if existing is not None:
            continue
        session.add(
            Book(
                id=item["id"],
                project_id=item["project_id"],
                title=item["title"],
                status=item.get("status", "planned"),
                current_milestone=item.get("current_milestone", ""),
                next_action=item.get("next_action", ""),
                manuscript_paths=item.get("manuscript_paths", []),
                implementation_paths=item.get("implementation_paths", []),
                published_url=item.get("published_url"),
                local_url=item.get("local_url"),
                quality_review_state=item.get("quality_review_state", "not_reviewed"),
                last_activity_at=None,
                created_at=now_iso(),
                updated_at=now_iso(),
            )
        )

    applications = _read_yaml(defaults_dir / "applications.yaml").get("applications", [])
    for item in applications:
        if session.get(Application, item["id"]) is not None:
            continue
        integration = item.get("integration") or {}
        relationships = item.get("relationships") or {}
        app = Application(
            id=item["id"],
            name=item["name"],
            description=item.get("description", ""),
            category=item.get("category", "supporting"),
            icon=item.get("icon", ""),
            tags=item.get("tags", []),
            enabled=bool(item.get("enabled", True)),
            archived=False,
            pinned=bool(item.get("pinned", False)),
            display_order=int(item.get("display_order", 100)),
            repository_path=item.get("repository_path"),
            additional_paths=item.get("additional_paths", []),
            working_directory=item.get("working_directory"),
            documentation_paths=item.get("documentation_paths", []),
            output_paths=item.get("output_paths", []),
            integration_adapter=integration.get("adapter"),
            adapter_enabled=bool(integration.get("enabled", False)),
            adapter_config=integration.get("config") or {},
            related_projects=relationships.get("projects", []),
            related_books=relationships.get("books", []),
            outcomes=relationships.get("outcomes", []),
            dependencies=relationships.get("dependencies", []),
            control_policy=item.get("control_policy") or {},
            source=item.get("source", "default"),
            notes=item.get("notes", ""),
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        session.add(app)
        app_repo_path = item.get("repository_path")
        if app_repo_path and session.scalar(select(Repository).where(Repository.path == app_repo_path)) is None:
            session.add(
                Repository(
                    id=repository_id(app_repo_path),
                    path=app_repo_path,
                    name=Path(app_repo_path).name,
                    classification="supporting_repository",
                    confidence=0.6,
                    evidence=[f"Registered as the repository for the {item['name']} application"],
                    source_root=str(Path(app_repo_path).parent),
                    is_git=(Path(app_repo_path) / ".git").exists(),
                    accessible=Path(app_repo_path).exists(),
                    candidate=False,
                    first_seen_at=now_iso(),
                    last_observed_at=None,
                )
            )
        for index, launch in enumerate(item.get("launch_definitions", [])):
            launch_id = launch.get("id") or f"{item['id']}-launch-{index + 1}"
            session.add(
                LaunchDefinition(
                    id=launch_id,
                    application_id=item["id"],
                    name=launch.get("name", "Launch"),
                    launch_type=launch.get("launch_type", "none"),
                    executable=launch.get("executable"),
                    arguments=launch.get("arguments", []),
                    working_directory=launch.get("working_directory"),
                    env_names=launch.get("env_names", []),
                    browser_url=launch.get("browser_url"),
                    health_type=launch.get("health_type", "none"),
                    health_url=launch.get("health_url"),
                    expected_port=launch.get("expected_port"),
                    is_primary=bool(launch.get("is_primary", index == 0)),
                    enabled=bool(launch.get("enabled", False)),
                    verified=bool(launch.get("verified", False)),
                    verification_note=launch.get("verification_note", ""),
                    shutdown_behavior=launch.get("shutdown_behavior", "terminate"),
                    created_at=now_iso(),
                    updated_at=now_iso(),
                )
            )

    seed_cultivation(session)

    # One honest seed activity, not synthetic user work.
    record_activity(
        session,
        event_type="system",
        title="Workspace initialised with three priority books",
        detail=(
            "Language, Inference and Math are pinned. Application launch definitions "
            "remain disabled until their commands are verified."
        ),
        source="mission-control",
        provenance="verified_observation",
        dedupe_key="seed-initial-workspace-v1",
    )
    logger.info("Seeded Mission Control defaults")
