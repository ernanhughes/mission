"""Regression tests for the Writer registry adapter (MC-BOOK-REGISTRY-01).

Read-only: no test mutates a manuscript directory on disk.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import select

from mission_control.config import RuntimeSettings
from mission_control.models import Book, Project
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import seed_defaults
from mission_control.writer_registry.adapter import (
    is_book_entry,
    load_writer_registry,
)
from mission_control.writer_registry.sync import (
    book_source_diagnostic,
    sync_writer_books,
)

MATH_YAML = """\
projects:
  math:
    id: math
    label: math
    name: math
    active: true
    project_root: {root}
    content_dir: {root}/content
    profile: technical
    tags: [book, technical]
    repo:
      provider: github
      local_path: {root}
    chapters:
      path: content/books/math
      pattern: "*.md"
    book:
      manuscript: math.md
      publication_status: research
    preview:
      route_prefix: /books/math/
"""


def _write_registry(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "projects.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _make_chapters(chapter_dir: Path, count: int = 3) -> None:
    chapter_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        (chapter_dir / f"{index:02d}-chapter.md").write_text("# c\n", encoding="utf-8")


def test_windows_path_handling(tmp_path: Path) -> None:
    root = tmp_path / "math"
    _make_chapters(root / "content" / "books" / "math", 2)
    # Backslash relative chapters.path joined to project_root (Writer semantics).
    text = (
        "projects:\n"
        "  math:\n"
        "    id: math\n"
        "    active: true\n"
        f"    project_root: {root}\n"
        "    profile: technical\n"
        "    tags: [book]\n"
        "    chapters:\n"
        "      path: content\\books\\math\n"
        "      pattern: '*.md'\n"
        "    book:\n"
        "      manuscript: math.md\n"
        "      publication_status: research\n"
    )
    snapshot = load_writer_registry(_write_registry(tmp_path, text))
    definition = snapshot.books["math"]
    assert definition.chapter_dir == root / "content" / "books" / "math"
    assert definition.available is True
    assert definition.chapter_count == 2
    assert definition.manuscript == "math.md"
    assert definition.publication_status == "research"


def test_standalone_and_shared_repositories(tmp_path: Path) -> None:
    standalone = tmp_path / "memory"
    _make_chapters(standalone / "content" / "books" / "memory", 2)
    shared = tmp_path / "new-books"
    _make_chapters(shared / "content" / "books" / "applied-ai", 4)
    text = (
        "projects:\n"
        "  memory:\n"
        f"    project_root: {standalone}\n"
        "    active: true\n"
        "    profile: technical\n"
        "    tags: [book]\n"
        "    repo:\n"
        f"      local_path: {standalone}\n"
        "    chapters:\n"
        "      path: content/books/memory\n"
        "      pattern: '*.md'\n"
        "    book:\n"
        "      manuscript: memory.md\n"
        "      publication_status: published\n"
        "  applied-ai:\n"
        f"    project_root: {shared}\n"
        "    active: true\n"
        "    profile: technical\n"
        "    tags: [book]\n"
        "    repo:\n"
        f"      local_path: {shared}\n"
        "    chapters:\n"
        "      path: content/books/applied-ai\n"
        "      pattern: '*.md'\n"
        "    book:\n"
        "      manuscript: applied-ai.md\n"
        "      publication_status: published\n"
    )
    snapshot = load_writer_registry(_write_registry(tmp_path, text))
    assert snapshot.books["memory"].chapter_dir == standalone / "content" / "books" / "memory"
    assert snapshot.books["memory"].repo_path == standalone
    assert snapshot.books["applied-ai"].chapter_dir == shared / "content" / "books" / "applied-ai"
    assert snapshot.books["applied-ai"].repo_path == shared
    assert snapshot.books["applied-ai"].chapter_count == 4


def test_book_vs_non_book_classification() -> None:
    assert is_book_entry({"tags": ["book", "technical"], "active": True}) is True
    assert is_book_entry({"tags": ["book", "fiction"], "active": True}) is True
    # programmer.ie posts: blog / non-book, no exact book tag
    assert is_book_entry({"tags": ["blog", "technical", "non-book"]}) is False
    # writer application: no book tag
    assert is_book_entry({"tags": ["application", "technical", "writer-runtime"]}) is False
    # inactive books are not live
    assert is_book_entry({"tags": ["book"], "active": False}) is False


def test_missing_folders_reported_not_inferred(tmp_path: Path) -> None:
    missing = tmp_path / "latent" / "chapters"
    text = (
        "projects:\n"
        "  latent:\n"
        f"    project_root: {tmp_path / 'latent'}\n"
        "    active: true\n"
        "    profile: fiction\n"
        "    tags: [book, fiction]\n"
        "    chapters:\n"
        "      path: chapters\n"
        "      pattern: '*.md'\n"
        "    book:\n"
        "      manuscript: latent.md\n"
    )
    snapshot = load_writer_registry(_write_registry(tmp_path, text))
    definition = snapshot.books["latent"]
    assert definition.available is False
    assert definition.chapter_count is None
    assert definition.error is not None
    assert str(missing) in definition.error
    # No alternative manuscript is inferred.
    assert definition.manuscript == "latent.md"


def test_invalid_yaml_reports_errors(tmp_path: Path) -> None:
    path = _write_registry(tmp_path, "projects: [unclosed\n")
    snapshot = load_writer_registry(path)
    assert snapshot.books == {}
    assert snapshot.errors, "invalid YAML must be reported"


def test_duplicate_ids_reported(tmp_path: Path) -> None:
    text = "projects:\n  math:\n    project_root: C:/a\n  math:\n    project_root: C:/b\n"
    snapshot = load_writer_registry(_write_registry(tmp_path, text))
    assert snapshot.books == {}
    assert any("Duplicate" in error for error in snapshot.errors)


def test_stable_identity_and_metadata_preservation(
    runtime: RuntimeSettings, tmp_path: Path
) -> None:
    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, runtime)
    root = tmp_path / "math"
    _make_chapters(root / "content" / "books" / "math", 3)
    _write_registry(tmp_path, MATH_YAML.format(root=root))
    # MATH_YAML helper wrote to tmp_path/projects.yaml; use it directly.
    snapshot = load_writer_registry(tmp_path / "projects.yaml")
    before_files = sorted(p.name for p in (root / "content" / "books" / "math").iterdir())
    with database.session() as session:
        book = session.scalar(select(Book).where(Book.project_id == "math"))
        assert book is not None
        book.status = "verification"
        book.current_milestone = "Keep this milestone."
        book.next_action = "Keep this action."
        session.flush()
    with database.session() as session:
        summary = sync_writer_books(session, snapshot)
        assert "math" in summary["updated"] or "math" not in summary["created"]
    with database.session() as session:
        book = session.scalar(select(Book).where(Book.project_id == "math"))
        assert book is not None
        assert book.manuscript_paths[0] == str(root / "content" / "books" / "math")
        # Operational planning state preserved.
        assert book.status == "verification"
        assert book.current_milestone == "Keep this milestone."
        assert book.next_action == "Keep this action."
        # Stable identity: still one book row for math.
        rows = session.scalars(select(Book).where(Book.project_id == "math")).all()
        assert len(rows) == 1
    after_files = sorted(p.name for p in (root / "content" / "books" / "math").iterdir())
    assert before_files == after_files, "sync must never mutate manuscripts"
    database.dispose()


def test_ambiguous_manuscript_never_guessed(tmp_path: Path) -> None:
    root = tmp_path / "multi"
    root.mkdir(parents=True)
    (root / "a.md").write_text("# a\n", encoding="utf-8")
    (root / "b.md").write_text("# b\n", encoding="utf-8")
    text = (
        "projects:\n"
        "  multi:\n"
        f"    project_root: {root}\n"
        "    active: true\n"
        "    tags: [book]\n"
        "    chapters:\n"
        "      path: .\n"
        "      pattern: '*.md'\n"
    )
    snapshot = load_writer_registry(_write_registry(tmp_path, text))
    # No book.manuscript and multiple candidates: manuscript stays None (no guess).
    assert snapshot.books["multi"].manuscript is None


def test_source_diagnostic_reports_unavailable(
    runtime: RuntimeSettings, tmp_path: Path
) -> None:
    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, runtime)
    root = tmp_path / "gone"
    registry_text = (
        "projects:\n"
        "  math:\n"
        f"    project_root: {root}\n"
        "    active: true\n"
        "    tags: [book]\n"
        "    chapters:\n"
        "      path: content/books/math\n"
        "      pattern: '*.md'\n"
        "    book:\n"
        "      manuscript: math.md\n"
        "      publication_status: research\n"
    )
    snapshot = load_writer_registry(_write_registry(tmp_path, registry_text))
    with database.session() as session:
        diagnostic = book_source_diagnostic(session, "math", snapshot)
        assert diagnostic["writer_registered"] is True
        assert diagnostic["writer_integration_status"] == "registered_unavailable"
        assert diagnostic["configuration_error"] is not None
        assert diagnostic["registry_source"] == str(tmp_path / "projects.yaml")
    database.dispose()


def test_seven_layout_classification(tmp_path: Path) -> None:
    math_root = tmp_path / "math"
    _make_chapters(math_root / "content" / "books" / "math", 2)
    memory_root = tmp_path / "memory"
    _make_chapters(memory_root / "content" / "books" / "memory", 2)
    shared = tmp_path / "new-books"
    _make_chapters(shared / "content" / "books" / "applied-ai", 2)
    latent_chapters = tmp_path / "latent" / "chapters"
    latent_chapters.mkdir(parents=True)  # empty: no chapter files
    text = (
        "projects:\n"
        "  math:\n"
        f"    project_root: {math_root}\n"
        "    active: true\n"
        "    tags: [book]\n"
        "    chapters:\n"
        "      path: content/books/math\n"
        "    book:\n"
        "      manuscript: math.md\n"
        "      publication_status: research\n"
        "  memory:\n"
        f"    project_root: {memory_root}\n"
        "    active: true\n"
        "    tags: [book]\n"
        "    chapters:\n"
        "      path: content/books/memory\n"
        "    book:\n"
        "      manuscript: memory.md\n"
        "  applied-ai:\n"
        f"    project_root: {shared}\n"
        "    active: true\n"
        "    tags: [book]\n"
        "    chapters:\n"
        "      path: content/books/applied-ai\n"
        "  latent:\n"
        f"    project_root: {tmp_path / 'latent'}\n"
        "    active: true\n"
        "    profile: fiction\n"
        "    tags: [book, fiction]\n"
        "    chapters:\n"
        "      path: chapters\n"
        "  advanced-agents-from-first-principles:\n"
        f"    project_root: {tmp_path / 'programmer'}\n"
        "    active: true\n"
        "    tags: [book]\n"
        "    chapters:\n"
        "      path: content/books/advanced-agents-from-first-principles\n"
        "  programmer_ie:\n"
        f"    project_root: {tmp_path / 'programmer'}\n"
        "    active: true\n"
        "    tags: [blog, technical, non-book]\n"
        "    chapters:\n"
        "      path: content/books/digital-life\n"
        "  writer:\n"
        f"    project_root: {tmp_path / 'writer'}\n"
        "    active: true\n"
        "    tags: [application]\n"
        "    chapters:\n"
        "      path: .\n"
        "      pattern: '*.py'\n"
    )
    snapshot = load_writer_registry(_write_registry(tmp_path, text))
    assert set(snapshot.books) == {
        "math",
        "memory",
        "applied-ai",
        "latent",
        "advanced-agents-from-first-principles",
    }
    assert "programmer_ie" in snapshot.skipped_non_book
    assert "writer" in snapshot.skipped_non_book
    assert snapshot.books["math"].available is True
    assert snapshot.books["memory"].available is True
    assert snapshot.books["applied-ai"].available is True
    # latent dir exists but empty, advanced-agents dir missing: both unavailable.
    assert snapshot.books["latent"].available is False
    assert snapshot.books["advanced-agents-from-first-principles"].available is False
    # Fiction vs technical profiles preserved.
    assert snapshot.books["latent"].profile == "fiction"
    assert snapshot.books["math"].profile == "technical"


def test_no_manuscript_mutations_on_sync(runtime: RuntimeSettings, tmp_path: Path) -> None:
    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, runtime)
    root = tmp_path / "math"
    _make_chapters(root / "content" / "books" / "math", 2)
    target = root / "content" / "books" / "math" / "01-chapter.md"
    before = target.read_bytes()
    snapshot = load_writer_registry(
        _write_registry(tmp_path, MATH_YAML.format(root=root))
    )
    with database.session() as session:
        sync_writer_books(session, snapshot)
    assert target.read_bytes() == before
    assert os.path.isfile(root / "content" / "books" / "math" / "02-chapter.md")
    database.dispose()


def test_working_source_preserved_when_registry_unavailable(
    runtime: RuntimeSettings, tmp_path: Path
) -> None:
    """A working configured source is never replaced by a missing registry path."""
    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, runtime)
    working = tmp_path / "working-fiction"
    _make_chapters(working / "chapters", 2)
    missing_root = tmp_path / "missing-latent"
    registry_text = (
        "projects:\n"
        "  math:\n"
        f"    project_root: {missing_root}\n"
        "    active: true\n"
        "    tags: [book]\n"
        "    chapters:\n"
        "      path: chapters\n"
        "      pattern: '*.md'\n"
        "    book:\n"
        "      manuscript: math.md\n"
    )
    snapshot = load_writer_registry(_write_registry(tmp_path, registry_text))
    assert snapshot.books["math"].available is False
    with database.session() as session:
        book = session.scalar(select(Book).where(Book.project_id == "math"))
        assert book is not None
        book.manuscript_paths = [str(working / "chapters")]
        session.flush()
    with database.session() as session:
        summary = sync_writer_books(session, snapshot)
        assert "math" not in summary["updated"]
        assert any("math" in item for item in summary["ambiguities"])
    with database.session() as session:
        book = session.scalar(select(Book).where(Book.project_id == "math"))
        assert book is not None
        assert book.manuscript_paths[0] == str(working / "chapters")
    database.dispose()
