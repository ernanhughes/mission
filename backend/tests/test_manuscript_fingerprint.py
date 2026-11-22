"""Fingerprint tests (MC-PUBLISH-02 Phase J, items 13-21). Read-only."""

from __future__ import annotations

from pathlib import Path

from mission_control.publication.fingerprint import (
    SCOPE_VERSION,
    fingerprint_manuscript,
    git_revision,
    writer_source_digest,
)


def _book(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "book"
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def test_deterministic_for_unchanged_content(tmp_path: Path) -> None:
    root = _book(tmp_path, {"01-chapter.md": "# a\n", "02-chapter.md": "# b\n"})
    first = fingerprint_manuscript(root, "*.md")
    second = fingerprint_manuscript(root, "*.md")
    assert first["ok"] and second["ok"]
    assert first["fingerprint"] == second["fingerprint"]
    assert first["scope_version"] == SCOPE_VERSION
    assert first["file_count"] == 2


def test_changed_content_changes_fingerprint(tmp_path: Path) -> None:
    root = _book(tmp_path, {"01-chapter.md": "# a\n"})
    before = fingerprint_manuscript(root, "*.md")["fingerprint"]
    (root / "01-chapter.md").write_text("# edited\n", encoding="utf-8")
    after = fingerprint_manuscript(root, "*.md")["fingerprint"]
    assert before != after


def test_rename_changes_scoped_fingerprint(tmp_path: Path) -> None:
    root = _book(tmp_path, {"01-chapter.md": "# same\n"})
    before = fingerprint_manuscript(root, "*.md")["fingerprint"]
    (root / "01-chapter.md").rename(root / "02-chapter.md")
    after = fingerprint_manuscript(root, "*.md")["fingerprint"]
    assert before != after


def test_line_ending_normalization(tmp_path: Path) -> None:
    lf = _book(tmp_path / "lf", {"01-chapter.md": "# a\n# b\n"})
    crlf_root = tmp_path / "crlf"
    crlf_root.mkdir(parents=True, exist_ok=True)
    (crlf_root / "01-chapter.md").write_bytes(b"# a\r\n# b\r\n")
    assert (
        fingerprint_manuscript(lf, "*.md")["fingerprint"]
        == fingerprint_manuscript(crlf_root, "*.md")["fingerprint"]
    )


def test_scope_excludes_subdirectories_and_other_patterns(tmp_path: Path) -> None:
    root = _book(tmp_path, {"01-chapter.md": "# a\n", "notes.txt": "# a\n"})
    (root / "out").mkdir()
    (root / "out" / "01-chapter.md").write_text("# different\n", encoding="utf-8")
    scoped = fingerprint_manuscript(root, "*-chapter.md")
    assert scoped["ok"] and scoped["file_count"] == 1
    (root / "notes.txt").write_text("# changed\n", encoding="utf-8")
    assert fingerprint_manuscript(root, "*-chapter.md")["fingerprint"] == scoped["fingerprint"]


def test_missing_and_unreadable_produce_diagnostics(tmp_path: Path) -> None:
    missing = fingerprint_manuscript(tmp_path / "gone", "*.md")
    assert missing["ok"] is False and "diagnostics" in missing
    root = _book(tmp_path, {"01-chapter.md": "# a\n"})
    (root / "01-chapter.md").unlink()
    (root / "01-chapter.md").mkdir()  # directory where a chapter file is expected
    blocked = fingerprint_manuscript(root, "01-chapter.md")
    assert blocked["ok"] is False and "diagnostics" in blocked


def test_scope_version_distinguishes_file_sets(tmp_path: Path) -> None:
    root = _book(tmp_path, {"01-chapter.md": "# a\n", "_index.md": "# i\n"})
    narrow = fingerprint_manuscript(root, "*-chapter.md")
    wide = fingerprint_manuscript(root, "*.md")
    assert narrow["ok"] and wide["ok"]
    assert narrow["file_count"] != wide["file_count"]
    assert narrow["scope_version"] == wide["scope_version"] == SCOPE_VERSION


def test_git_revision_kept_separate(tmp_path: Path) -> None:
    info = git_revision(tmp_path / "missing")
    assert info["ok"] is False and "diagnostics" in info
    # Content fingerprint never consults git: identical content, any repo state.
    root = _book(tmp_path, {"01-chapter.md": "# a\n"})
    assert fingerprint_manuscript(root, "*.md")["ok"] is True


def test_writer_digest_is_stable_and_prefixed() -> None:
    text = "+++\ntitle = \"T\"\n+++\n\nBody\n"
    first = writer_source_digest(text)
    assert first.startswith("sha256:")
    assert writer_source_digest(text) == first
    assert writer_source_digest(text + "more\n") != first
