"""MC-FICTION-01: Fiction Books as an independent Cultivation track.

Fiction manuscripts reuse the shared book-workspace engine (detection,
identity, dedupe, workspace creation) and feed the seeded ``fiction_books``
Cultivation goal through a read-only ``fiction_books`` source. Technical
Books behavior is unchanged.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from mission_control.config import RuntimeSettings
from mission_control.cultivation.sources import scan_fiction_books
from mission_control.discovery.books import (
    detect_books,
    detect_fiction_books,
    sync_detected_books,
    sync_fiction_books,
)
from mission_control.models import Book
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import seed_defaults


def make_fiction(root: Path, project: str, chapters: int = 2) -> Path:
    book_dir = root / project / "chapters"
    book_dir.mkdir(parents=True, exist_ok=True)
    for index in range(chapters):
        (book_dir / f"{index + 1:02d}-chapter.md").write_text("# Chapter\n", encoding="utf-8")
    return book_dir


def make_tech(root: Path, project: str, book: str, title: str, chapters: int = 2) -> Path:
    book_dir = root / project / "content" / "books" / book
    book_dir.mkdir(parents=True, exist_ok=True)
    (book_dir / "_index.md").write_text(
        f"+++\ntitle = \"{title}\"\npublication_status = \"draft\"\n+++\n",
        encoding="utf-8",
    )
    for index in range(max(0, chapters - 1)):
        (book_dir / f"{index + 1:02d}-chapter.md").write_text("# Chapter\n", encoding="utf-8")
    return book_dir


def test_fiction_registration_and_defaults(client: TestClient) -> None:
    goals = {goal["id"]: goal for goal in client.get("/api/cultivation/goals").json()}
    assert "fiction_books" in goals
    fiction = goals["fiction_books"]
    assert fiction["name"] == "Fiction Books"
    assert fiction["target_value"] == 100
    assert fiction["unit"] == "books"
    assert fiction["qualifying_stage"] == "published"
    assert fiction["measurement_type"] == "count"
    assert "technical_books" in goals
    assert "published_books" in goals
    # Existing Books goal untouched: still the owner-attested baseline.
    assert goals["published_books"]["baseline_value"] == 30


def test_fiction_discovery_multiple_projects(tmp_path: Path) -> None:
    root = tmp_path / "fiction"
    make_fiction(root, "axiom-zero", chapters=3)
    make_fiction(root, "goblins", chapters=2)
    detected = detect_fiction_books([root])
    assert [book.title for book in detected] == ["Axiom Zero", "Goblins"]
    assert all(book.publication_status == "drafting" for book in detected)
    assert all(book.published_url is None for book in detected)


def test_fiction_empty_and_missing_directories(tmp_path: Path) -> None:
    empty = tmp_path / "empty-fiction"
    empty.mkdir()
    assert detect_fiction_books([empty]) == []
    assert detect_fiction_books([tmp_path / "does-not-exist"]) == []
    assert scan_fiction_books(empty).published == 0
    missing = scan_fiction_books(tmp_path / "does-not-exist")
    assert missing.errors, "missing root must surface a diagnostic"


def test_fiction_missing_metadata_needs_review(tmp_path: Path) -> None:
    root = tmp_path / "fiction"
    make_fiction(root, "mystery-novel", chapters=1)
    (root / "research-notes" / "chapters").mkdir(parents=True)
    detected = {book.title: book for book in detect_fiction_books([root])}
    assert "Mystery Novel" in detected
    book = detected["Mystery Novel"]
    assert book.publication_status == "drafting"
    assert book.published_url is None
    # Empty chapter trees are not books at all.
    assert "Research Notes" not in detected


def test_fiction_duplicate_detection_prefers_most_chapters(tmp_path: Path) -> None:
    root = tmp_path / "fiction"
    first = root / "alpha" / "chapters"
    first.mkdir(parents=True)
    (first / "01-a.md").write_text("# A\n", encoding="utf-8")
    (first / "_index.md").write_text(
        "+++\ntitle = \"Same Title\"\npublication_status = \"draft\"\n+++\n",
        encoding="utf-8",
    )
    second = root / "beta" / "chapters"
    second.mkdir(parents=True)
    for name in ("01-a.md", "02-b.md", "03-c.md"):
        (second / name).write_text("# X\n", encoding="utf-8")
    (second / "_index.md").write_text(
        "+++\ntitle = \"Same Title\"\npublication_status = \"draft\"\n+++\n",
        encoding="utf-8",
    )
    detected = detect_fiction_books([root])
    assert len(detected) == 1
    assert detected[0].chapter_count == 4  # 3 chapters + _index.md


def test_fiction_published_counts_only_explicit_evidence(runtime: RuntimeSettings) -> None:
    database = Database(runtime)
    apply_migrations(database)
    fiction_root = runtime.fiction_book_root
    fiction_root.mkdir(parents=True, exist_ok=True)
    make_fiction(fiction_root, "draft-novel", chapters=2)
    with database.session() as session:
        seed_defaults(session, runtime)
        created = sync_fiction_books(session, [fiction_root])
        assert created == ["Draft Novel"]
        books = session.scalars(select(Book).order_by(Book.title)).all()
        assert len(books) == 4  # 3 seeded technical + 1 fiction
        novel = next(book for book in books if book.title == "Draft Novel")
        assert novel.status == "drafting"
    with database.session() as session:
        assert session.scalar(
            select(Book).where(Book.title == "Draft Novel")
        ) is not None
    database.dispose()


def test_fiction_stable_identity_across_refreshes(runtime: RuntimeSettings) -> None:
    database = Database(runtime)
    apply_migrations(database)
    fiction_root = runtime.fiction_book_root
    fiction_root.mkdir(parents=True, exist_ok=True)
    make_fiction(fiction_root, "stable-novel", chapters=2)
    with database.session() as session:
        seed_defaults(session, runtime)
        assert sync_fiction_books(session, [fiction_root]) == ["Stable Novel"]
        first_id = session.scalar(
            select(Book).where(Book.title == "Stable Novel")).project_id
    with database.session() as session:
        assert sync_fiction_books(session, [fiction_root]) == []
        second_id = session.scalar(
            select(Book).where(Book.title == "Stable Novel")).project_id
        assert first_id == second_id
    database.dispose()


def test_independent_books_and_fiction_progress(client: TestClient, runtime: RuntimeSettings) -> None:
    make_tech(runtime.book_root, "alpha", "alpha", "Alpha Tech", chapters=2)
    make_fiction(runtime.fiction_book_root, "beta-novel", chapters=2)
    tech = client.post("/api/books/detect").json()
    assert tech == {"created": ["Alpha Tech"], "count": 1}
    fiction = client.post("/api/fiction-books/detect").json()
    assert fiction == {"created": ["Beta Novel"], "count": 1}
    # Idempotent on both collections.
    assert client.post("/api/books/detect").json() == {"created": [], "count": 0}
    assert client.post("/api/fiction-books/detect").json() == {"created": [], "count": 0}
    # Fiction endpoint only lists fiction; technical endpoint lists everything
    # seeded plus both new workspaces (shared table, independent roots).
    fiction_titles = {book["title"] for book in client.get("/api/fiction-books").json()}
    assert fiction_titles == {"Beta Novel"}
    tech_titles = {book["title"] for book in client.get("/api/books").json()}
    assert {"Alpha Tech", "Beta Novel"} <= tech_titles
    # No fiction book counts as published: both goals stay at zero.
    goals = {goal["id"]: goal for goal in client.get("/api/cultivation/goals").json()}
    assert goals["fiction_books"]["progress"]["current"] == 0
    # Cultivation source sync discovers the fiction project without publishing it.
    source = client.post("/api/cultivation/sources", json={
        "id": "src-fiction-test", "name": "Fiction test", "kind": "fiction_books",
        "skill_id": "fiction-writing", "goal_id": "fiction_books",
        "path": str(runtime.fiction_book_root), "config": {},
    }).json()
    result = client.post(f"/api/cultivation/sources/{source['id']}/sync").json()
    assert result["status"] == "ok"
    assert result["observed"]["discovered"] == 1
    assert result["observed"]["published"] == 0
    progress = client.get("/api/cultivation/goals/fiction_books").json()["progress"]
    assert progress["current"] == 0
    assert progress["pipeline"]["draft"] == 1


def test_fiction_source_missing_root_is_stale_not_crash(
    client: TestClient, tmp_path: Path
) -> None:
    missing = tmp_path / "gone-fiction"
    assert not missing.exists()
    with client.app.state.database.session() as session:
        from mission_control.cultivation import service as cultivation_service
        from mission_control.core.errors import ValidationProblem
        import pytest as _pytest
        with _pytest.raises(ValidationProblem):
            cultivation_service.create_source(session, {
                "id": "src-missing", "name": "Missing", "kind": "fiction_books",
                "goal_id": "fiction_books", "path": str(missing), "config": {}})
    # Existing source pointed at a removed directory keeps last observation.
    import shutil
    doomed = tmp_path / "doomed"
    make_fiction(doomed, "doomed-novel", chapters=1)
    source = client.post("/api/cultivation/sources", json={
        "id": "src-doomed", "name": "Doomed", "kind": "fiction_books",
        "goal_id": "fiction_books", "path": str(doomed), "config": {}}).json()
    assert client.post(f"/api/cultivation/sources/{source['id']}/sync").json()["status"] == "ok"
    shutil.rmtree(doomed)
    stale = client.post(f"/api/cultivation/sources/{source['id']}/sync").json()
    assert stale["status"] == "stale"


def test_fiction_pinned_track_behavior(client: TestClient) -> None:
    response = client.patch("/api/cultivation/goals/fiction_books", json={"pinned": True})
    assert response.status_code == 200
    assert response.json()["pinned"] is True
    response = client.patch("/api/cultivation/goals/fiction_books", json={"pinned": False})
    assert response.json()["pinned"] is False


def test_fiction_persistence_across_restarts(runtime: RuntimeSettings) -> None:
    database = Database(runtime)
    apply_migrations(database)
    fiction_root = runtime.fiction_book_root
    fiction_root.mkdir(parents=True, exist_ok=True)
    make_fiction(fiction_root, "persistent-novel", chapters=2)
    with database.session() as session:
        seed_defaults(session, runtime)
        sync_fiction_books(session, [fiction_root])
    database.dispose()
    reopened = Database(runtime)
    with reopened.session() as session:
        book = session.scalar(select(Book).where(Book.title == "Persistent Novel"))
        assert book is not None
        assert "persistent-novel" in (book.manuscript_paths[0] or "")
    reopened.dispose()


def test_technical_books_regression(runtime: RuntimeSettings) -> None:
    database = Database(runtime)
    apply_migrations(database)
    make_tech(runtime.book_root, "alpha", "alpha", "Alpha From First Principles", chapters=3)
    with database.session() as session:
        seed_defaults(session, runtime)
        created = sync_detected_books(session, [runtime.book_root])
        assert created == ["Alpha From First Principles"]
    with database.session() as session:
        detected = detect_books([runtime.book_root])
        assert [book.title for book in detected] == ["Alpha From First Principles"]
    # Fiction sync never touches technical roots and vice versa.
    with database.session() as session:
        assert sync_fiction_books(session, [runtime.book_root]) == []
    database.dispose()


def test_no_unintended_filesystem_writes(runtime: RuntimeSettings) -> None:
    database = Database(runtime)
    apply_migrations(database)
    fiction_root = runtime.fiction_book_root
    target = make_fiction(fiction_root, "readonly-novel", chapters=2)
    before = {path: path.read_bytes() for path in sorted(target.iterdir())}
    with database.session() as session:
        seed_defaults(session, runtime)
        sync_fiction_books(session, [fiction_root])
    after = {path: path.read_bytes() for path in sorted(target.iterdir())}
    assert before == after
    digest_before = hashlib.sha256(b"".join(before[path] for path in sorted(before))).hexdigest()
    digest_after = hashlib.sha256(b"".join(after[path] for path in sorted(after))).hexdigest()
    assert digest_before == digest_after
    database.dispose()


def test_no_model_calls_in_fiction_paths() -> None:
    backend = Path(__file__).resolve().parents[1] / "mission_control"
    for relative in ("cultivation/service.py", "api/cultivation.py",
                     "discovery/books.py", "cultivation/sources.py"):
        source = (backend / relative).read_text(encoding="utf-8").casefold()
        assert "httpx" not in source, relative
        assert "chat/completions" not in source, relative
