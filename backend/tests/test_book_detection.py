from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from mission_control.config import RuntimeSettings
from mission_control.discovery.books import detect_books, sync_detected_books
from mission_control.models import Book, Project
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import seed_defaults


def make_book(
    root: Path,
    project: str,
    book: str,
    title: str,
    *,
    status: str = "published",
    chapters: int = 2,
) -> Path:
    book_dir = root / project / "content" / "books" / book
    book_dir.mkdir(parents=True)
    (book_dir / "_index.md").write_text(
        "\n".join(
            [
                "+++",
                f'title = "{title}"',
                f'publication_status = "{status}"',
                "+++",
                "",
                "Body",
            ]
        ),
        encoding="utf-8",
    )
    for index in range(max(0, chapters - 1)):
        (book_dir / f"{index + 1:02d}-chapter.md").write_text("# Chapter", encoding="utf-8")
    return book_dir


def test_detection_prefers_standalone_copy_and_maps_status(tmp_path: Path) -> None:
    root = tmp_path / "books"
    standalone = make_book(
        root, "alpha", "alpha", "Alpha From First Principles", status="development", chapters=3
    )
    make_book(
        root, "aggregator", "alpha", "Alpha From First Principles", status="development", chapters=1
    )
    make_book(root, "aggregator", "beta", "Beta Book", status="published", chapters=2)

    detected = detect_books([root])

    assert [book.title for book in detected] == ["Alpha From First Principles", "Beta Book"]
    alpha = next(book for book in detected if book.title.startswith("Alpha"))
    assert alpha.book_dir == standalone
    assert alpha.publication_status == "drafting"
    beta_book = next(book for book in detected if book.title == "Beta Book")
    assert beta_book.publication_status == "published"


def test_detection_reads_yaml_and_malformed_toml_front_matter(tmp_path: Path) -> None:
    root = tmp_path / "books"
    yaml_book = root / "yaml-book" / "content" / "books" / "yaml-book"
    yaml_book.mkdir(parents=True)
    (yaml_book / "_index.md").write_text(
        "---\ntitle: YAML Book\npublication_status: published\n---\n",
        encoding="utf-8",
    )
    toml_book = root / "toml-book" / "content" / "books" / "toml-book"
    toml_book.mkdir(parents=True)
    (toml_book / "_index.md").write_text(
        "\n".join(
            [
                "+++",
                'title = "TOML Book"',
                "publication_status = 'research'",
                "publication_google ='https://example.invalid/book'",
                "+++",
            ]
        ),
        encoding="utf-8",
    )

    detected = {book.title: book for book in detect_books([root])}

    assert detected["YAML Book"].publication_status == "published"
    assert detected["TOML Book"].publication_status == "drafting"


def test_sync_creates_missing_books_once_and_preserves_user_state(
    runtime: RuntimeSettings,
) -> None:
    database = Database(runtime)
    apply_migrations(database)
    make_book(runtime.book_root, "alpha", "alpha", "Alpha From First Principles", chapters=3)
    make_book(
        runtime.book_root, "aggregator", "beta", "Beta Book", status="published", chapters=2
    )

    with database.session() as session:
        seed_defaults(session, runtime)
        created = sync_detected_books(session, [runtime.book_root])
        assert created == ["Alpha From First Principles", "Beta Book"]

    with database.session() as session:
        books = session.scalars(select(Book).order_by(Book.title)).all()
        assert len(books) == 5
        alpha = session.scalar(select(Book).where(Book.title == "Alpha From First Principles"))
        assert alpha is not None
        project = session.get(Project, alpha.project_id)
        assert project is not None
        assert project.kind == "book"
        assert project.pinned is False
        assert alpha.manuscript_paths[0].endswith(r"alpha\content\books\alpha")
        alpha.status = "editorial_review"
        alpha.next_action = "Keep this user edit."
        session.flush()

    with database.session() as session:
        created = sync_detected_books(session, [runtime.book_root])
        assert created == []
        alpha = session.scalar(select(Book).where(Book.title == "Alpha From First Principles"))
        assert alpha is not None
        assert alpha.status == "editorial_review"
        assert alpha.next_action == "Keep this user edit."

    database.dispose()


def test_detect_endpoint_adds_new_books_and_is_idempotent(
    client: TestClient, runtime: RuntimeSettings
) -> None:
    make_book(runtime.book_root, "gamma", "gamma", "Gamma Book", chapters=2)

    response = client.post("/api/books/detect")

    assert response.status_code == 200
    assert response.json() == {"created": ["Gamma Book"], "count": 1}
    assert client.post("/api/books/detect").json() == {"created": [], "count": 0}
    titles = {book["title"] for book in client.get("/api/books").json()}
    assert "Gamma Book" in titles
