"""Persistence conventions for relationship-less ORM mappings (MC-POSTGRES-02).

Finding (Phase 3): Mission Control's ORM models declare column-level
``ForeignKey`` constraints but no ``relationship()`` attributes. SQLAlchemy's
unit-of-work save ordering is driven by relationship dependency processors;
bare foreign keys alone do not order pending inserts. Consequently, adding a
transient parent and child in one flush emits the child INSERT first, which
any FK-enforcing backend (SQLite with ``PRAGMA foreign_keys=ON``,
PostgreSQL) rejects with ``IntegrityError``.

This is expected SQLAlchemy behaviour for this modelling style — not a
SQLAlchemy bug and not PostgreSQL-specific (proven: vanilla SQLAlchemy
mappers fail identically with enforced FKs). The application convention is
therefore: **flush parents before adding children within a session**
(as ``seed_defaults`` and the service layers already do). These tests pin
that convention for representative parent-child pairs so future code and
agents cannot silently depend on single-flush nesting.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from mission_control.models import Application, Book, LaunchDefinition, Project


def _db(runtime):
    from mission_control.persistence.db import Database
    from mission_control.persistence.migrations import apply_migrations

    database = Database(runtime)
    apply_migrations(database)
    return database


def test_single_flush_parent_child_is_rejected(runtime):
    # Documents the boundary: one flush must never mix transient parent+child.
    database = _db(runtime)
    session = database.session_factory()
    try:
        session.add(Project(id="conv-proj", name="Convention"))
        session.add(Book(id="conv-book", project_id="conv-proj", title="Convention"))
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()
        database.dispose()


def test_parent_flush_then_child_project_book(runtime):
    database = _db(runtime)
    with database.session() as session:
        session.add(Project(id="conv-proj", name="Convention"))
        session.flush()
        session.add(Book(id="conv-book", project_id="conv-proj", title="Convention"))
    with database.session() as session:
        assert session.get(Book, "conv-book") is not None
        assert session.get(Book, "conv-book").project_id == "conv-proj"
    database.dispose()


def test_parent_flush_then_child_application_definition(runtime):
    database = _db(runtime)
    with database.session() as session:
        session.add(Application(id="conv-app", name="Convention"))
        session.flush()
        session.add(
            LaunchDefinition(
                id="conv-def", application_id="conv-app", name="web",
                launch_type="server",
            )
        )
    with database.session() as session:
        assert session.get(LaunchDefinition, "conv-def") is not None
    database.dispose()


def test_goal_item_membership_convention(runtime):
    from mission_control.models import CultivationGoal, CultivationItem, CultivationMembership

    database = _db(runtime)
    with database.session() as session:
        session.add(CultivationGoal(id="conv-goal", name="Convention"))
        session.add(CultivationItem(id="conv-item", title="Convention"))
        session.flush()
        session.add(CultivationMembership(item_id="conv-item", goal_id="conv-goal"))
    with database.session() as session:
        assert (
            session.get(CultivationMembership, ("conv-item", "conv-goal")) is not None
        )
    database.dispose()
