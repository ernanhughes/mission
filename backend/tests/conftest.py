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


@pytest.fixture
def runtime(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        repo_root=REPO_ROOT,
        data_dir=tmp_path / "data",
        config_dir=REPO_ROOT / "config",
        frontend_dist=tmp_path / "dist",
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
