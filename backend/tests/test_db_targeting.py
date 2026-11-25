"""W9A: database-target fail-closed behaviour (no live connections made).

The pytest isolation guard runs first (non-test PG is refused outright);
with MC_TEST_DSN set, the guard passes and the W9A target gate is what
is under test. Construction never connects, so PostgreSQL URLs are
safe to use as inert strings.
"""

import pytest

from mission_control.config import DatabaseConfigurationError, RuntimeSettings
from mission_control.persistence.db import Database


def _settings(tmp_path) -> RuntimeSettings:
    return RuntimeSettings(
        repo_root=tmp_path,
        data_dir=tmp_path / "data",
        config_dir=tmp_path,
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "books",
        fiction_book_root=tmp_path / "fiction",
        host="127.0.0.1",
        port=8799,
        start_monitor=False,
        seed_defaults=False,
        workbench_decisions_path=tmp_path / "d.jsonl",
        workbench_preferences_path=tmp_path / "p.json",
        workbench_url="http://workbench.test",
        opencode_db_path=tmp_path / "oc.db",
    )


def _test_pg(monkeypatch, tmp_path, dbname: str):
    dsn = f"postgresql+psycopg://mc:mc@localhost:5432/{dbname}"
    monkeypatch.setenv("MC_DSN", dsn)
    monkeypatch.setenv("MC_TEST_DSN", dsn)
    return dsn


def test_pg_without_target_fails_closed(tmp_path, monkeypatch) -> None:
    _test_pg(monkeypatch, tmp_path, "mc_test")
    with pytest.raises(DatabaseConfigurationError, match="target="):
        Database(_settings(tmp_path))


def test_pg_error_hides_credentials(tmp_path, monkeypatch) -> None:
    dsn = "postgresql+psycopg://mc:s3cret@localhost:5432/mc_test"
    monkeypatch.setenv("MC_DSN", dsn)
    monkeypatch.setenv("MC_TEST_DSN", dsn)
    try:
        Database(_settings(tmp_path))
    except DatabaseConfigurationError as exc:
        assert "s3cret" not in str(exc)
        assert "localhost" in str(exc)
    else:  # pragma: no cover - must raise
        raise AssertionError("expected refusal")


def test_pg_with_explicit_target_constructs(tmp_path, monkeypatch) -> None:
    _test_pg(monkeypatch, tmp_path, "w6e")
    db = Database(_settings(tmp_path), target="scratch:w6e")
    assert db.target == "scratch:w6e"
    assert db.backend == "postgresql"
    db.dispose()


def test_sqlite_needs_no_target(tmp_path) -> None:
    db = Database(_settings(tmp_path))
    assert db.backend == "sqlite"
    db.dispose()
