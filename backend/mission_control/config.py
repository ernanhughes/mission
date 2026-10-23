"""Runtime paths and environment-derived settings.

Secrets are deliberately absent from this module's persisted configuration. A
provider key, if needed, is read from an explicitly named environment variable
at the moment a request is made.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default.resolve()


@dataclass(slots=True)
class RuntimeSettings:
    repo_root: Path = field(default_factory=_repo_root)
    data_dir: Path = field(default_factory=lambda: _env_path("MISSION_CONTROL_DATA_DIR", _repo_root() / "data"))
    config_dir: Path = field(default_factory=lambda: _env_path("MISSION_CONTROL_CONFIG_DIR", _repo_root() / "config"))
    frontend_dist: Path = field(default_factory=lambda: _env_path("MISSION_CONTROL_FRONTEND_DIST", _repo_root() / "frontend" / "dist"))
    host: str = field(default_factory=lambda: os.environ.get("MISSION_CONTROL_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("MISSION_CONTROL_PORT", "8790")))
    log_level: str = field(default_factory=lambda: os.environ.get("MISSION_CONTROL_LOG_LEVEL", "INFO"))
    seed_defaults: bool = field(default_factory=lambda: os.environ.get("MISSION_CONTROL_SEED", "1") != "0")
    start_monitor: bool = field(default_factory=lambda: os.environ.get("MISSION_CONTROL_MONITOR", "1") != "0")
    dev_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8790",
        "http://localhost:8790",
    )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "mission_control.db"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def database_url(self) -> str:
        configured = os.environ.get("MISSION_CONTROL_DATABASE_URL")
        if configured:
            return configured
        return f"sqlite:///{self.db_path.as_posix()}"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
