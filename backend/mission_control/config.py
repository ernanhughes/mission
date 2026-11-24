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


class DatabaseConfigurationError(RuntimeError):
    """Raised when the operational database configuration is missing or invalid."""


def _redact_url(url: str) -> str:
    """Redact credentials from a database URL for safe logging."""
    try:
        from sqlalchemy.engine.url import make_url

        parsed = make_url(url)
        if parsed.password:
            return str(parsed.set(password="***"))
        return str(parsed)
    except Exception:
        return "<unparseable-database-url>"


def normalize_database_url(url: str) -> str:
    """Normalize a database URL to the SQLAlchemy driver form in use.

    ``postgresql://`` (the portable libpq form used in ``MC_DSN``) is mapped
    to ``postgresql+psycopg://`` so SQLAlchemy uses the Psycopg 3 driver
    already declared in ``pyproject.toml``. SQLite URLs pass through
    unchanged. Whitespace is stripped; empty input raises.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        raise DatabaseConfigurationError("Empty database URL")
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql://" + cleaned[len("postgres://"):]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg://" + cleaned[len("postgresql://"):]
    return cleaned


def is_postgres_url(url: str) -> bool:
    lowered = (url or "").lower()
    return lowered.startswith("postgresql") or lowered.startswith("postgres://")


def resolve_database_url(
    *,
    explicit: str | None = None,
    allow_sqlite_fallback: bool = True,
) -> str:
    """Resolve the authoritative operational database URL.

    Precedence: explicit argument > ``MC_DSN`` > ``MISSION_CONTROL_DATABASE_URL``
    > SQLite fallback at ``data/mission_control.db``.

    ``MC_DSN`` is the single authoritative operational configuration.
    ``MISSION_CONTROL_DATABASE_URL`` remains as a backwards-compatible
    override (used by tests and the migration utility). SQLite fallback is
    only permitted when ``allow_sqlite_fallback`` is true; production startup
    passes false semantics via :func:`require_operational_database_url`.
    """
    if explicit:
        return normalize_database_url(explicit)
    dsn = os.environ.get("MC_DSN", "").strip()
    if dsn:
        return normalize_database_url(dsn)
    legacy = os.environ.get("MISSION_CONTROL_DATABASE_URL", "").strip()
    if legacy:
        return normalize_database_url(legacy)
    if not allow_sqlite_fallback:
        raise DatabaseConfigurationError(
            "MC_DSN is required for Mission Control operation. "
            "Set the MC_DSN environment variable to the PostgreSQL connection string."
        )
    return f"sqlite:///{(_repo_root() / 'data' / 'mission_control.db').as_posix()}"


def require_operational_database_url(explicit: str | None = None) -> str:
    """Resolve the operational URL, refusing silent SQLite fallback."""
    url = resolve_database_url(explicit=explicit, allow_sqlite_fallback=False)
    if not is_postgres_url(url):
        raise DatabaseConfigurationError(
            "Mission Control operational database must be PostgreSQL "
            f"(got backend {url.split(':')[0]!r}). Set MC_DSN to the PostgreSQL DSN."
        )
    return url


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default.resolve()


@dataclass(slots=True)
class RuntimeSettings:
    repo_root: Path = field(default_factory=_repo_root)
    data_dir: Path = field(
        default_factory=lambda: _env_path("MISSION_CONTROL_DATA_DIR", _repo_root() / "data")
    )
    config_dir: Path = field(
        default_factory=lambda: _env_path("MISSION_CONTROL_CONFIG_DIR", _repo_root() / "config")
    )
    frontend_dist: Path = field(
        default_factory=lambda: _env_path(
            "MISSION_CONTROL_FRONTEND_DIST", _repo_root() / "frontend" / "dist"
        )
    )
    book_root: Path = field(
        default_factory=lambda: _env_path("MISSION_CONTROL_BOOKS_ROOT", Path(r"C:\books"))
    )
    fiction_book_root: Path = field(
        default_factory=lambda: _env_path(
            "MISSION_CONTROL_FICTION_BOOKS_ROOT", Path(r"C:\fiction-books")
        )
    )
    writer_registry_path: Path = field(
        default_factory=lambda: _env_path(
            "MISSION_CONTROL_WRITER_REGISTRY",
            Path(r"C:\Projects\writer\config\web\projects.yaml"),
        )
    )
    websites_root: Path = field(
        default_factory=lambda: _env_path(
            "MISSION_CONTROL_WEBSITES_ROOT", Path(r"C:\websites")
        )
    )
    bookbuilder_root: Path = field(
        default_factory=lambda: _env_path(
            "MISSION_CONTROL_BOOKBUILDER_ROOT", Path(r"C:\Projects\bookbuilder")
        )
    )
    host: str = field(default_factory=lambda: os.environ.get("MISSION_CONTROL_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("MISSION_CONTROL_PORT", "8790")))
    log_level: str = field(
        default_factory=lambda: os.environ.get("MISSION_CONTROL_LOG_LEVEL", "INFO")
    )
    seed_defaults: bool = field(
        default_factory=lambda: os.environ.get("MISSION_CONTROL_SEED", "1") != "0"
    )
    start_monitor: bool = field(
        default_factory=lambda: os.environ.get("MISSION_CONTROL_MONITOR", "1") != "0"
    )
    # Inspect consumer snapshot (MC-INSPECT-01): read-only JSON snapshot root.
    # Mission Control never writes here, never launches Pi, and never executes
    # anything from the snapshot data.
    inspect_dir: Path = field(
        default_factory=lambda: _env_path(
            "MISSION_CONTROL_INSPECT_DIR",
            Path(r"C:\Projects\inspect\output\consumers\mission"),
        )
    )
    # OpenCode usage database (MC-COST-01): read-only local SQLite copy of
    # OpenCode's own records. Mission Control never writes, migrates,
    # checkpoints or vacuums this file; it opens `mode=ro` per query.
    # Configured locally via MISSION_CONTROL_OPENCODE_DB, never from browser.
    opencode_db_path: Path = field(
        default_factory=lambda: _env_path(
            "MISSION_CONTROL_OPENCODE_DB",
            Path(r"C:\Users\ernan\.local\share\opencode\opencode.db"),
        )
    )
    # Workbench owns editorial decisions and the selected book. Mission Control
    # reads those files read-only; it never writes them.
    workbench_decisions_path: Path = field(
        default_factory=lambda: _env_path(
            "MISSION_CONTROL_WORKBENCH_DECISIONS",
            Path(r"C:\Projects\workbench\.workbench\editorial-decisions.jsonl"),
        )
    )
    workbench_preferences_path: Path = field(
        default_factory=lambda: _env_path(
            "MISSION_CONTROL_WORKBENCH_PREFERENCES",
            Path(r"C:\Projects\workbench\.workbench\preferences.json"),
        )
    )
    workbench_url: str = field(
        default_factory=lambda: os.environ.get(
            "MISSION_CONTROL_WORKBENCH_URL", "http://127.0.0.1:7420"
        )
    )
    # Python executable whose environment provides the `ai` package for
    # manuscript quality evaluation subprocesses. Unset means evaluation
    # execution is unavailable (recorded as blocked, never silently skipped).
    quality_eval_python: str | None = field(
        default_factory=lambda: os.environ.get("MISSION_CONTROL_QUALITY_EVAL_PYTHON")
    )
    # Writer quality runner for strategy-commanded chapters (WRITER-QUALITY-02):
    # "<python> | <writer repo root> | <db url or empty>". The python must
    # import writer_cli from the Writer checkout; the repo root is the CLI
    # working directory (config/models.yaml, writer.toml). Unset means
    # Writer-commanded execution is unavailable (blocked, never faked).
    writer_quality_runner: str | None = field(
        default_factory=lambda: os.environ.get("MISSION_CONTROL_WRITER_QUALITY_RUNNER")
    )
    # ALIVE is the living-book engine. The gateway refuses a non-loopback URL.
    alive_url: str = field(
        default_factory=lambda: os.environ.get("MISSION_CONTROL_ALIVE_URL", "http://127.0.0.1:8000")
    )
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
        # Authoritative precedence: MC_DSN > MISSION_CONTROL_DATABASE_URL >
        # SQLite file under data_dir. MC_DSN carries the portable libpq form
        # (postgresql://...); normalize to the psycopg driver URL internally.
        # Never log or persist the raw value; use _redact_url() at call sites.
        dsn = os.environ.get("MC_DSN", "").strip()
        if dsn:
            return normalize_database_url(dsn)
        configured = os.environ.get("MISSION_CONTROL_DATABASE_URL", "").strip()
        if configured:
            return normalize_database_url(configured)
        return f"sqlite:///{self.db_path.as_posix()}"

    @property
    def database_backend(self) -> str:
        url = self.database_url
        if is_postgres_url(url):
            return "postgresql"
        if url.startswith("sqlite"):
            return "sqlite"
        return "unknown"

    @property
    def redacted_database_url(self) -> str:
        return _redact_url(self.database_url)

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
