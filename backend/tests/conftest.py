from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MISSION_CONTROL_MONITOR", "0")
os.environ.setdefault("MISSION_CONTROL_SEED", "1")

from helpers import open_client  # noqa: E402
from mission_control.config import RuntimeSettings  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolate_operational_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hard test-isolation invariant (MC-POSTGRES-02 Phase 2).

    No test inherits the operational database configuration implicitly: the
    production ``MC_DSN`` (and the legacy ``MISSION_CONTROL_DATABASE_URL``
    override) are removed for every test. Tests needing PostgreSQL must
    explicitly opt in via ``MC_TEST_DSN`` (see test_postgres_integration.py);
    everything else runs on isolated tmp SQLite files. Combined with the
    :class:`Database` constructor guard, a test can only reach an explicitly
    isolated database.
    """
    monkeypatch.delenv("MC_DSN", raising=False)
    monkeypatch.delenv("MISSION_CONTROL_DATABASE_URL", raising=False)


@pytest.fixture
def runtime(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        repo_root=REPO_ROOT,
        data_dir=tmp_path / "data",
        config_dir=REPO_ROOT / "config",
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "books",
        fiction_book_root=tmp_path / "fiction-books",
        host="127.0.0.1",
        port=8790,
        start_monitor=False,
        seed_defaults=True,
        workbench_decisions_path=tmp_path / "workbench-decisions.jsonl",
        workbench_preferences_path=tmp_path / "workbench-preferences.json",
        workbench_url="http://workbench.test",
    )


@pytest.fixture
def client(runtime: RuntimeSettings) -> Iterator[TestClient]:
    with open_client(runtime) as test_client:
        yield test_client
