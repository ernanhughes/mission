"""Verified PostgreSQL backup helper (MC-POSTGRES-02 Phase 8).

Creates a timestamped ``pg_dump`` of the operational database into
``data/backups/`` (git-ignored) and records restore-validation metadata for
``GET /api/diagnostics/database``. Credentials come from ``MC_DSN`` only and
are passed via ``PGPASSWORD`` (never the command line).

Usage:
    python scripts/pg_backup.py [--verify]

``--verify`` additionally restores the dump into a scratch database
(``mc_verify``, created and dropped automatically), compares table lists and
row counts against the live database, and writes
``data/backups/last_verified_backup.json`` on success.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

PG_BIN_CANDIDATES = [
    Path(r"E:\Program Files\PostgreSQL\16\bin"),
    Path(r"C:\Program Files\PostgreSQL\16\bin"),
    Path(r"E:\Program Files\PostgreSQL\18\bin"),
]


def _pg_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for directory in PG_BIN_CANDIDATES:
        candidate = directory / (name + ".exe")
        if candidate.exists():
            return str(candidate)
    raise SystemExit(f"{name} not found on PATH or in known PostgreSQL bin directories")


def _dsn_parts(dsn: str) -> dict:
    from sqlalchemy.engine.url import make_url

    url = make_url(dsn)
    return {
        "host": url.host or "localhost",
        "port": str(url.port or 5432),
        "user": url.username or "",
        "database": url.database or "",
        "password": url.password or "",
    }


def main() -> int:
    verify = "--verify" in sys.argv[1:]
    dsn = os.environ.get("MC_DSN", "").strip()
    if not dsn:
        raise SystemExit("MC_DSN is not set")
    parts = _dsn_parts(dsn)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = REPO_ROOT / "data" / "backups" / f"mc-pg-{stamp}.dump"
    dest.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PGPASSWORD"] = parts["password"]
    try:
        proc = subprocess.run(
            [_pg_tool("pg_dump"), "-h", parts["host"], "-p", parts["port"],
             "-U", parts["user"], "-d", parts["database"], "-f", str(dest)],
            capture_output=True, text=True, env=env, timeout=1200,
        )
    finally:
        env["PGPASSWORD"] = ""
    if proc.returncode != 0:
        raise SystemExit(f"pg_dump failed: {proc.stderr[-2000:]}")
    digest = hashlib.sha256()
    with dest.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    print(f"backup: {dest} bytes={dest.stat().st_size} sha256={digest.hexdigest()}")
    if not verify:
        print("skipped restore validation (pass --verify to validate)")
        return 0
    # Restore into a scratch database and compare.
    import psycopg

    admin = dict(parts)
    admin_dsn = f"postgresql://{admin['user']}:{admin['password']}@{admin['host']}:{admin['port']}/postgres"
    scratch = "mc_verify"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname='mc_verify'")
            if cur.fetchone():
                cur.execute("DROP DATABASE mc_verify")
            cur.execute("CREATE DATABASE mc_verify OWNER mc")
    proc = subprocess.run(
        [_pg_tool("psql"), "-h", parts["host"], "-p", parts["port"], "-U", parts["user"],
         "-d", scratch, "-f", str(dest), "-q"],
        capture_output=True, text=True, env={**os.environ, "PGPASSWORD": parts["password"]},
        timeout=1200,
    )
    if proc.returncode != 0:
        raise SystemExit(f"restore validation failed: {proc.stderr[-2000:]}")
    live_dsn = f"postgresql://{parts['user']}:{parts['password']}@{parts['host']}:{parts['port']}/{parts['database']}"
    scratch_dsn = f"postgresql://{parts['user']}:{parts['password']}@{parts['host']}:{parts['port']}/{scratch}"
    with psycopg.connect(live_dsn) as live, psycopg.connect(scratch_dsn) as copy:
        live_tables = {r[0] for r in live.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
        copy_tables = {r[0] for r in copy.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
        assert live_tables == copy_tables, "table list mismatch"
        for table in sorted(live_tables):
            n1 = live.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            n2 = copy.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            assert n1 == n2, f"count mismatch {table}: {n1} vs {n2}"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute("DROP DATABASE mc_verify")
    record = {
        "path": str(dest.relative_to(REPO_ROOT)).replace("\\", "/"),
        "bytes": dest.stat().st_size,
        "sha256": digest.hexdigest(),
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "method": "pg_dump; restored into scratch mc_verify; table lists and row counts matched; scratch dropped",
    }
    (dest.parent / "last_verified_backup.json").write_text(json.dumps(record, indent=2))
    print("restore validation OK; scratch database dropped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
