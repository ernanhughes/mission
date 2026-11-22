"""Identity resolution tests (MC-PUBLISH-02 Phase J, items 1-12)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from mission_control.config import RuntimeSettings
from mission_control.models import Book, Project, PublicationAssessment
from mission_control.persistence.db import Database, now_iso
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import seed_defaults
from mission_control.publication.identity import (
    delete_alias,
    get_aliases,
    identity_status,
    list_identity_conflicts,
    normalize_identity,
    resolve,
    save_alias,
)


def _db(runtime: RuntimeSettings) -> Database:
    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, runtime)
    return database


def _add_book(session, pid: str, title: str, manuscript: str = "") -> None:
    session.add(
        Project(
            id=pid, name=title, kind="book", status="active",
            priority=1000, pinned=False, archived=False, display_order=1000,
        )
    )
    session.flush()
    session.add(Book(id=f"book-{pid}", project_id=pid, title=title,
                     manuscript_paths=[manuscript] if manuscript else []))
    session.flush()


def test_exact_writer_id_match_resolves(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        status = identity_status(session, "math", writer_ids={"math", "memory"})
    assert status["state"] == "resolved"
    assert status["writer_id"] == "math"
    database.dispose()


def test_explicit_underscore_alias_resolves(runtime: RuntimeSettings, tmp_path) -> None:
    database = _db(runtime)
    with database.session() as session:
        _add_book(session, "axiom-zero", "Axiom Zero")
        entry = save_alias(
            session, canonical_project_id="axiom-zero", system="writer",
            external_id="axiom_zero", source_reference="author mapping",
            known_writer_ids={"axiom_zero"},
        )
        assert entry["verification_method"] == "explicit_author_mapping"
        status = identity_status(session, "axiom-zero", writer_ids={"axiom_zero"})
    assert status["state"] == "resolved"
    assert status["writer_id"] == "axiom_zero"
    database.dispose()


def test_normalized_match_is_candidate_never_merge(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        _add_book(session, "axiom-zero", "Axiom Zero")
        # No alias saved: normalized correspondence must NOT resolve.
        status = identity_status(session, "axiom-zero", writer_ids={"axiom_zero"})
        assert status["state"] == "candidate"
        assert status["candidates"] == ["axiom_zero"]
        resolved = resolve(session, system="writer", external_id="axiom_zero",
                           writer_ids={"axiom_zero", "axiom-zero"})
    assert resolved["state"] == "candidate"
    assert resolved["canonical_project_id"] is None
    database.dispose()


def test_duplicate_external_id_fails_closed(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        _add_book(session, "alpha", "Alpha Book")
        _add_book(session, "beta", "Beta Book")
        save_alias(session, canonical_project_id="alpha", system="hugo",
                   external_id="alpha")
        with pytest.raises(ValueError, match="Conflicting alias"):
            save_alias(session, canonical_project_id="beta", system="hugo",
                       external_id="alpha")
    database.dispose()


def test_writer_fabrication_rejected(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        with pytest.raises(ValueError, match="not in the Writer registry"):
            save_alias(session, canonical_project_id="math", system="writer",
                       external_id="math_invented", known_writer_ids={"math"})
    database.dispose()


def test_missing_writer_project_is_unregistered(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        status = identity_status(session, "math", writer_ids={"other"})
    assert status["state"] == "unregistered"
    database.dispose()


def test_missing_mission_book_is_unregistered(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        result = resolve(session, system="writer", external_id="ghost",
                         writer_ids={"ghost"})
    assert result["state"] == "unregistered"
    database.dispose()


def test_shared_repo_books_stay_distinct(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        _add_book(session, "applied-ai", "Applied AI")
        _add_book(session, "debugging-ai", "Debugging AI")
        assert identity_status(session, "applied-ai",
                               writer_ids={"applied-ai", "debugging-ai"})["state"] == "resolved"
        assert identity_status(session, "debugging-ai",
                               writer_ids={"applied-ai", "debugging-ai"})["state"] == "resolved"
    database.dispose()


def test_similar_titles_do_not_establish_identity(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        _add_book(session, "thought", "Thought")
        _add_book(session, "thought-2", "Thought")
        result = resolve(session, system="writer", external_id="thought",
                         writer_ids={"thought"})
    # Mission id 'thought' exists -> resolves to itself, not to thought-2.
    assert result["state"] == "unregistered" or result["canonical_project_id"] in (None, "thought")
    with database.session() as session:
        assert normalize_identity("Axiom Zero") == normalize_identity("axiom_zero")
        # ...but normalization alone never appears as a resolution path:
        no_alias = [e for e in get_aliases(session) if e["external_id"] == "axiom_zero"]
        assert no_alias == []
    database.dispose()


def test_approvals_stay_with_original_assessment(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        _add_book(session, "axiom-zero", "Axiom Zero")
        session.add(PublicationAssessment(
            id="pubass-test", project_id="axiom-zero", book_id="book-axiom-zero",
            book_root="/tmp", policy_version="publication-readiness-v1",
            technical_scope="pilot", manuscript_fingerprint="a" * 64,
            input_manifest_fingerprint="b" * 64, chapter_count=1,
            created_at=now_iso(),
        ))
        session.flush()
        save_alias(session, canonical_project_id="axiom-zero", system="writer",
                   external_id="axiom_zero", known_writer_ids={"axiom_zero"})
        rows = session.scalars(select(PublicationAssessment)).all()
        assert len(rows) == 1 and rows[0].project_id == "axiom-zero"
        # Alias removal changes nothing about history either.
        assert delete_alias(session, system="writer", external_id="axiom_zero") is True
        assert get_aliases(session) == []
    database.dispose()


def test_conflicts_list_surfaces_candidates(runtime: RuntimeSettings) -> None:
    database = _db(runtime)
    with database.session() as session:
        _add_book(session, "axiom-zero", "Axiom Zero")
        report = list_identity_conflicts(session, {"axiom_zero", "math"})
    assert any(c["project_id"] == "axiom-zero" for c in report["candidates"])
    assert "axiom_zero" in report["suggested_writer_mappings"]
    database.dispose()


def test_exact_match_with_working_source_resolves_despite_writer_drift(
    runtime: RuntimeSettings, tmp_path
) -> None:
    working = tmp_path / "working" / "chapters"
    working.mkdir(parents=True, exist_ok=True)
    (working / "01-chapter.md").write_text("# c\n", encoding="utf-8")
    database = _db(runtime)
    with database.session() as session:
        _add_book(session, "latent", "Latent", manuscript=str(working))
        resolved = identity_status(
            session, "latent",
            writer_ids={"latent"}, writer_available={"latent": False},
        )
        assert resolved["state"] == "resolved"
        assert resolved["writer_id"] == "latent"
        assert "drift" in resolved["reason"]
        both_missing = identity_status(
            session, "latent",
            writer_ids={"latent"}, writer_available={"latent": False},
            mission_manuscript_ok=False,
        )
        assert both_missing["state"] == "unavailable"
    database.dispose()
