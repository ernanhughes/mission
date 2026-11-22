"""MC-PROJECTS-QUALITY-01: classification distinguishes purpose from subject matter.

A repository that *discusses* books in its documentation is not a book unless a
manuscript tree is its deliverable. Software that supports book production
classifies by what it builds or runs.
"""

from __future__ import annotations

from pathlib import Path

from mission_control.discovery.classifier import classify


def _software_repo(root: Path) -> Path:
    repo = root / "author-cli"
    repo.mkdir(parents=True)
    (repo / "README.md").write_text(
        "# Author CLI\n\nA command-line tool for drafting book chapters, "
        "rewriting book sections and managing the book manuscript pipeline.\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        "[project]\nname='author-cli'\n[project.scripts]\nauthor = 'author:main'\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    return repo


def test_book_discussing_software_is_not_a_book(tmp_path: Path) -> None:
    repo = _software_repo(tmp_path)
    result = classify(repo)
    assert result.classification == "executable_application"
    assert any("subject matter" in item for item in result.evidence)
    assert result.reason


def test_library_discussing_books_stays_a_library(tmp_path: Path) -> None:
    repo = tmp_path / "prose-kit"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# Prose Kit\n\nHelpers for book manuscript processing.\n", encoding="utf-8"
    )
    (repo / "pyproject.toml").write_text("[project]\nname='prose-kit'\n", encoding="utf-8")
    result = classify(repo)
    assert result.classification == "library"
    assert any("subject matter" in item for item in result.evidence)


def test_manuscript_tree_is_still_a_book(tmp_path: Path) -> None:
    book = tmp_path / "some-book"
    (book / "content" / "books" / "some-book").mkdir(parents=True)
    (book / "README.md").write_text("# A Book\n\nChapters of a real book.\n", encoding="utf-8")
    (book / "content" / "books" / "some-book" / "01-chapter.md").write_text("# One", encoding="utf-8")
    result = classify(book)
    assert result.classification == "book"
    assert result.confidence >= 0.9


def test_book_keywords_without_manuscript_are_not_a_book(tmp_path: Path) -> None:
    repo = tmp_path / "notes"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# Notes\n\nIdeas about a future book and its chapters.\n", encoding="utf-8"
    )
    (repo / ".git").mkdir()
    result = classify(repo)
    assert result.classification != "book"


def test_every_classification_carries_a_reason(tmp_path: Path) -> None:
    repo = _software_repo(tmp_path)
    assert classify(repo).reason
    plain = tmp_path / "empty"
    plain.mkdir()
    assert classify(plain).reason
