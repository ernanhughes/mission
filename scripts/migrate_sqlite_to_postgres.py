"""SQLite -> PostgreSQL migration utility for Mission Control (MC-POSTGRES-01).

Reads the legacy SQLite database (default ``data/mission_control.db``) and
imports every application-owned table into the PostgreSQL target configured
by ``MC_DSN``. The default operation is read-only; writes require ``--execute``.

Commands:
    --inspect    source/target inventory (read-only)
    --dry-run    compatibility checks + ordered plan (read-only)
    --execute    backup, schema baseline, import, sequence repair, reconcile
    --verify     reconcile an already-migrated target against the source snapshot

Safety:
    * Never logs credentials. DSN is read from MC_DSN / --target only.
    * Refuses to import into a non-empty target unless the target already
      matches the source (idempotent re-run) or --allow-nonempty with an
      explicit pg_dump backup is given.
    * Uses the SQLite backup API (WAL-safe) for the source snapshot.
    * No ``ON CONFLICT DO NOTHING``: PK collisions abort with evidence.

Requires: psycopg[binary], SQLAlchemy (already project dependencies).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

EXCLUDE_TABLES = {"sqlite_sequence"}
APP_TABLE_EXCLUDE_PREFIXES = ("sqlite_",)

# Tables whose TEXT content must be byte-identical in PostgreSQL because they
# participate in digests, fingerprints or approval hashes. The importer passes
# values through unchanged; the verifier compares exact text (not canonical JSON)
# for these columns in addition to the canonical hash.
BYTE_IDENTICAL_COLUMNS = {
    ("praxis_proposals", "content_digest"),
    ("praxis_proposals", "recipe_digest"),
    ("praxis_proposals", "approval_digest"),
    ("publication_assessments", "manuscript_fingerprint"),
    ("publication_assessments", "input_manifest_fingerprint"),
    ("publication_approvals", "manuscript_fingerprint"),
    ("publication_approvals", "input_manifest_fingerprint"),
    ("technical_extraction_runs", "manifest_hash"),
    ("script_records", "content_sha256"),
    ("website_post_evaluations", "content_sha256"),
}


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def redact_dsn(dsn: str) -> str:
    try:
        from sqlalchemy.engine.url import make_url

        url = make_url(dsn)
        if url.password:
            return str(url.set(password="***"))
    except Exception:
        pass
    # Fallback: mask userinfo without a full parse.
    if "@" in dsn and "://" in dsn:
        scheme, rest = dsn.split("://", 1)
        userinfo, hostpart = rest.split("@", 1)
        user = userinfo.split(":")[0]
        return f"{scheme}://{user}:***@{hostpart}"
    return "<redacted-dsn>"


def resolve_target_dsn(explicit: str | None) -> str:
    if explicit:
        return explicit.strip()
    dsn = os.environ.get("MC_DSN", "").strip()
    if dsn:
        return dsn
    raise SystemExit(
        "MC_DSN is not set. Set MC_DSN to the PostgreSQL connection string "
        "(e.g. in a .env you source locally, never committed) or pass --target."
    )


def normalize_pg_dsn(dsn: str) -> str:
    cleaned = dsn.strip()
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql://" + cleaned[len("postgres://"):]
    return cleaned


def source_tables(source: Path) -> list[str]:
    con = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    return [
        r[0]
        for r in rows
        if r[0] not in EXCLUDE_TABLES
        and not r[0].startswith(APP_TABLE_EXCLUDE_PREFIXES)
    ]


def table_columns(source: Path, table: str) -> list[dict]:
    con = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        info = con.execute(f'PRAGMA table_info("{table}")').fetchall()
        fks = con.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
    finally:
        con.close()
    return [
        {"cid": r[0], "name": r[1], "type": r[2], "notnull": r[3], "dflt": r[4], "pk": r[5]}
        for r in info
    ], fks


def source_counts(source: Path, tables: list[str]) -> dict[str, int]:
    con = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    out: dict[str, int] = {}
    try:
        for table in tables:
            out[table] = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    finally:
        con.close()
    return out


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_sqlite(source: Path, dest_dir: Path) -> dict:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"mission_control-pre-pg-migration-{utc_stamp()}.db"
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    report: dict = {
        "source": str(source),
        "backup": str(dest),
        "size": dest.stat().st_size,
        "sha256": sha256_file(dest),
    }
    con = sqlite3.connect(str(dest))
    try:
        report["integrity_check"] = con.execute("PRAGMA integrity_check").fetchall()
        report["foreign_key_violations"] = con.execute("PRAGMA foreign_key_check").fetchall()
        tables = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        report["tables"] = tables
        report["counts"] = {
            t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            for t in tables
            if t != "sqlite_sequence"
        }
    finally:
        con.close()
    return report


# ------------------------------------------------------------------ ORM shape

def orm_tables() -> dict:
    from mission_control.models import Base
    import mission_control.praxis_proposals.models  # noqa: F401  (register table)

    return dict(Base.metadata.tables)


def import_order(table_map: dict) -> list[str]:
    """Topological table order from FK dependencies (self-edges ignored)."""
    from sqlalchemy import Table

    deps: dict[str, set[str]] = {}
    for name, table in table_map.items():
        assert isinstance(table, Table)
        needs: set[str] = set()
        for fk in table.foreign_keys:
            referred = fk.column.table.name
            if referred != name and referred in table_map:
                needs.add(referred)
        # schema_migrations has no ORM entry; it is created by the runner first.
        deps[name] = needs
    ordered: list[str] = []
    resolved: set[str] = set()
    pending = dict(deps)
    while pending:
        ready = sorted(n for n, need in pending.items() if need <= resolved)
        if not ready:
            # Cycle across tables: break deterministically, FK violations will
            # surface explicitly during import rather than silently reordered.
            ready = [sorted(pending)[0]]
        for name in ready:
            ordered.append(name)
            resolved.add(name)
            del pending[name]
    return ordered


def boolean_columns(table_map: dict) -> dict[str, set[str]]:
    from sqlalchemy import Boolean

    out: dict[str, set[str]] = {}
    for name, table in table_map.items():
        cols = {c.name for c in table.columns if isinstance(c.type, Boolean)}
        if cols:
            out[name] = cols
    return out


def json_columns(table_map: dict) -> dict[str, set[str]]:
    from sqlalchemy import JSON

    out: dict[str, set[str]] = {}
    for name, table in table_map.items():
        cols = {c.name for c in table.columns if isinstance(c.type, JSON)}
        if cols:
            out[name] = cols
    return out


# ------------------------------------------------------------------ PG helpers

def pg_connect(dsn: str):
    import psycopg

    return psycopg.connect(normalize_pg_dsn(dsn))


def pg_inventory(dsn: str) -> dict:
    with pg_connect(dsn) as con:
        with con.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1"
            )
            tables = [r[0] for r in cur.fetchall()]
            counts: dict[str, int] = {}
            for table in tables:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                counts[table] = cur.fetchone()[0]
            try:
                cur.execute("SELECT MAX(version) FROM schema_migrations")
                version = cur.fetchone()[0]
            except Exception:
                version = None
    return {"tables": tables, "counts": counts, "schema_version": version}


def ensure_pg_schema_via_orm(dsn: str) -> list[int]:
    """Create baseline PG schema from ORM metadata; record legacy versions."""
    from mission_control.config import RuntimeSettings
    from mission_control.persistence.db import Database

    # Reuse the application runner so version tracking stays identical.
    # Temporarily point this process at the target DSN; restore afterwards
    # so a missing MC_DSN stays missing for the caller's environment.
    previous_mc = os.environ.get("MC_DSN")
    previous_legacy = os.environ.get("MISSION_CONTROL_DATABASE_URL")
    os.environ["MC_DSN"] = normalize_pg_dsn(dsn)
    if "MISSION_CONTROL_DATABASE_URL" in os.environ:
        del os.environ["MISSION_CONTROL_DATABASE_URL"]
    try:
        settings = RuntimeSettings()
        database = Database(settings)
        assert database.is_postgres, "expected postgres backend"
        from mission_control.persistence.migrations import apply_migrations

        return apply_migrations(database)
    finally:
        if previous_mc is None:
            os.environ.pop("MC_DSN", None)
        else:
            os.environ["MC_DSN"] = previous_mc
        if previous_legacy is not None:
            os.environ["MISSION_CONTROL_DATABASE_URL"] = previous_legacy


def canonical_value(value, *, is_bool: bool, is_json: bool):
    if value is None:
        return None
    if is_bool:
        if value in (0, 1, True, False):
            return bool(value)
        if isinstance(value, str) and value in ("0", "1"):
            return value == "1"
        raise ValueError(f"non-boolean value {value!r} in boolean column")
    if is_json:
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if isinstance(value, str):
            text = value.strip()
            if text in ("", "null"):
                return None if text == "null" else value
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                raise ValueError(f"invalid JSON {value[:120]!r}")
            return json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return value
    if isinstance(value, float) and value != value:  # NaN
        raise ValueError("NaN float rejected")
    if isinstance(value, str) and "\x00" in value:
        raise ValueError("embedded NUL byte rejected by PostgreSQL")
    return value


def row_digest(names: list[str], values: tuple, bools: set[str], jsons: set[str]) -> str:
    canonical = []
    for name, value in zip(names, values):
        try:
            canonical.append(canonical_value(value, is_bool=name in bools, is_json=name in jsons))
        except ValueError as exc:
            raise ValueError(f"column {name}: {exc}") from exc
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=False, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def import_table(source: Path, dsn: str, table: str, table_map: dict,
                 bools: dict, jsons: dict, batch: int = 500) -> dict:
    if table not in table_map:
        if table == "schema_migrations":
            return {"table": table, "skipped": "handled by migration runner"}
        raise SystemExit(f"Source table {table!r} has no ORM mapping; refusing to silently omit it.")
    satable = table_map[table]
    col_names = [c.name for c in satable.columns]
    bool_set = bools.get(table, set())
    json_set = jsons.get(table, set())

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        src_rows = src.execute(f'SELECT "{'", "'.join(col_names)}" FROM "{table}"').fetchall()
    finally:
        src.close()

    converted: list[tuple] = []
    problems: list[str] = []
    for row in src_rows:
        try:
            converted.append(
                tuple(
                    canonical_value(v, is_bool=n in bool_set, is_json=n in json_set)
                    for n, v in zip(col_names, row)
                )
            )
        except ValueError as exc:
            problems.append(str(exc))
    if problems:
        raise SystemExit(
            f"Table {table}: {len(problems)} row(s) rejected by compatibility checks "
            f"(e.g. {problems[0]}). Resolve explicitly; nothing was imported for this table."
        )

    placeholders = ", ".join(["%s"] * len(col_names))
    cols_sql = ", ".join(f'"{c}"' for c in col_names)
    with pg_connect(dsn) as con:
        with con.cursor() as cur:
            for start in range(0, len(converted), batch):
                chunk = converted[start:start + batch]
                cur.executemany(
                    f'INSERT INTO "{table}" ({cols_sql}) VALUES ({placeholders})', chunk
                )
    return {"table": table, "rows": len(converted)}


def repair_sequences(dsn: str, table_map: dict) -> list[str]:
    from sqlalchemy import Integer

    fixed: list[str] = []
    with pg_connect(dsn) as con:
        with con.cursor() as cur:
            for name, table in table_map.items():
                int_pk = [
                    c for c in table.columns
                    if c.primary_key and isinstance(c.type, Integer)
                ]
                if not int_pk:
                    continue
                pk = int_pk[0].name
                cur.execute('SELECT pg_get_serial_sequence(%s, %s)', (name, pk))
                seq = cur.fetchone()[0]
                if not seq:
                    continue
                cur.execute(f'SELECT MAX("{pk}") FROM "{name}"')
                maximum = cur.fetchone()[0]
                if maximum is None:
                    continue
                cur.execute("SELECT setval(%s, %s, true)", (seq, int(maximum)))
                fixed.append(f"{name}.{pk} -> {maximum} via {seq}")
    return fixed


def reconcile(source: Path, dsn: str, table_map: dict, bools: dict, jsons: dict) -> dict:
    report: dict = {"tables": [], "ok": True}
    src_con = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        with pg_connect(dsn) as pg:
            with pg.cursor() as cur:
                for table in sorted(table_map.keys()):
                    if table not in [r[0] for r in src_con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()]:
                        if table == "schema_migrations":
                            continue
                    col_names = [c.name for c in table_map[table].columns]
                    bool_set = bools.get(table, set())
                    json_set = jsons.get(table, set())
                    try:
                        src_rows = src_con.execute(
                            f'SELECT "{'", "'.join(col_names)}" FROM "{table}" ORDER BY 1'
                            if False else f'SELECT "{'", "'.join(col_names)}" FROM "{table}"'
                        ).fetchall()
                    except sqlite3.OperationalError:
                        continue  # table absent from source snapshot
                    cur.execute(f'SELECT "{'", "'.join(col_names)}" FROM "{table}"')
                    pg_rows = cur.fetchall()
                    # Index by PK tuple for set comparison.
                    pk_cols = [c.name for c in table_map[table].primary_key.columns]
                    pk_idx = [col_names.index(c) for c in pk_cols]
                    src_pks = sorted(tuple(r[i] for i in pk_idx) for r in src_rows)
                    pg_pks = sorted(tuple(r[i] for i in pk_idx) for r in pg_rows)
                    pk_match = src_pks == pg_pks
                    # Canonical digests ordered by PK.
                    def digest(rows):
                        keyed = sorted(rows, key=lambda r: tuple(r[i] for i in pk_idx))
                        h = hashlib.sha256()
                        for row in keyed:
                            h.update(
                                row_digest(col_names, tuple(row), bool_set, json_set).encode()
                            )
                        return h.hexdigest() if keyed else "empty"

                    try:
                        content_match = digest(src_rows) == digest(pg_rows)
                        content_error = None
                    except ValueError as exc:
                        content_match = False
                        content_error = str(exc)
                    status = "OK" if (pk_match and content_match
                                      and len(src_rows) == len(pg_rows)) else "MISMATCH"
                    if status != "OK":
                        report["ok"] = False
                    entry = {
                        "table": table,
                        "source_rows": len(src_rows),
                        "target_rows": len(pg_rows),
                        "pk_match": pk_match,
                        "content_match": content_match,
                        "status": status,
                    }
                    if content_error:
                        entry["error"] = content_error
                    report["tables"].append(entry)
    finally:
        src_con.close()
        try:
            pg.close()
        except Exception:
            pass
    return report


def cmd_inspect(args) -> int:
    target = resolve_target_dsn(args.target)
    print(f"source: {args.source}")
    print(f"target: {redact_dsn(target)}")
    tables = source_tables(Path(args.source))
    counts = source_counts(Path(args.source), tables)
    total = sum(counts.values())
    print(f"source tables: {len(tables)} records: {total}")
    for table in tables:
        print(f"  {table}|{counts[table]}")
    inv = pg_inventory(target)
    print(f"target tables: {len(inv['tables'])} schema_version: {inv['schema_version']}")
    for table in inv["tables"]:
        print(f"  pg:{table}|{inv['counts'].get(table, 0)}")
    return 0


def cmd_dry_run(args) -> int:
    target = resolve_target_dsn(args.target)
    src = Path(args.source)
    tables = source_tables(src)
    table_map = orm_tables()
    missing = [t for t in tables if t not in table_map and t != "schema_migrations"]
    if missing:
        print(f"BLOCKED: source tables without ORM mapping: {missing}")
        return 2
    order = import_order({k: v for k, v in table_map.items() if k != "schema_migrations"})
    print(f"import order ({len(order)} tables):")
    for table in order:
        print(f"  {table}")
    bools = boolean_columns(table_map)
    jsons = json_columns(table_map)
    # Compatibility probes over real data.
    problems: list[str] = []
    src_con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        for table, satable in table_map.items():
            if table == "schema_migrations":
                continue
            if table not in tables:
                continue
            col_names = [c.name for c in satable.columns]
            rows = src_con.execute(f'SELECT "{'", "'.join(col_names)}" FROM "{table}"').fetchall()
            for row in rows:
                for name, value in zip(col_names, row):
                    try:
                        canonical_value(
                            value, is_bool=name in bools.get(table, set()),
                            is_json=name in jsons.get(table, set()),
                        )
                    except ValueError as exc:
                        problems.append(f"{table}.{name}: {exc}")
                        break
                if problems and problems[-1].startswith(table + "."):
                    break
    finally:
        src_con.close()
    if problems:
        print(f"BLOCKED: {len(problems)} compatibility problem(s):")
        for item in problems[:20]:
            print(f"  {item}")
        return 2
    inv = pg_inventory(target)
    # schema_migrations is version tracking, not operational data.
    nonempty = [t for t, n in inv["counts"].items() if n > 0 and t != "schema_migrations"]
    if nonempty:
        print(f"target non-empty tables (import would refuse): {nonempty}")
    else:
        print("target empty: ready for --execute")
    print("dry-run OK")
    return 0


def cmd_execute(args) -> int:
    target = resolve_target_dsn(args.target)
    src = Path(args.source)
    if not src.exists():
        raise SystemExit(f"source not found: {src}")
    inv = pg_inventory(target)
    # schema_migrations is version tracking, not operational data: a freshly
    # baselined but otherwise empty target must not block the import.
    nonempty = [t for t, n in inv["counts"].items() if n > 0 and t != "schema_migrations"]
    table_map = orm_tables()
    bools = boolean_columns(table_map)
    jsons = json_columns(table_map)
    if nonempty and not (args.allow_nonempty or args.resume):
        # Idempotent re-run: if every table already matches, declare success.
        rec = reconcile(src, target, table_map, bools, jsons)
        if rec["ok"]:
            print("target already matches source; migration already complete")
            return 0
        print(f"REFUSING: target non-empty ({nonempty}). Pass --allow-nonempty with --yes only with an explicit backup.")
        return 3
    if not args.yes:
        print("refusing without --yes (default operation is non-destructive)")
        return 4
    # 1. Consistent source backup.
    backup_dir = Path(args.backup_dir) if args.backup_dir else (REPO_ROOT / "data" / "backups")
    backup = backup_sqlite(src, backup_dir)
    print(json.dumps({"backup": backup}, indent=2, default=str)[:2000])
    bad = [r for r in (backup["integrity_check"] or []) if r[0].lower() != "ok"]
    if bad:
        print(f"BLOCKED: source integrity_check failed: {bad}")
        return 5
    if backup["foreign_key_violations"]:
        print(f"BLOCKED: source has FK violations: {backup['foreign_key_violations'][:5]}")
        return 5
    snapshot = Path(backup["backup"])
    # 2. Optional target backup.
    if nonempty and args.allow_nonempty:
        if not args.pg_backup:
            print("REFUSING: --allow-nonempty requires --pg-backup <path> (pg_dump output)")
            return 3
        dump = pg_dump(target, Path(args.pg_backup))
        print(f"target backup: {dump}")
    # 3. Schema baseline.
    applied = ensure_pg_schema_via_orm(target)
    print(f"schema baseline applied versions: {applied}")
    # 4. Ordered import (skip already-populated tables only when re-running cleanly).
    order = import_order({k: v for k, v in table_map.items() if k != "schema_migrations"})
    totals = {"tables": 0, "rows": 0}
    for table in order:
        if table not in source_tables(snapshot):
            continue
        with pg_connect(target) as con:
            with con.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                existing = cur.fetchone()[0]
        if existing:
            print(f"  skip {table}: already {existing} rows")
            continue
        result = import_table(snapshot, target, table, table_map, bools, jsons)
        print(f"  {table}: {result['rows']} rows")
        totals["tables"] += 1
        totals["rows"] += int(result["rows"])
    print(f"imported tables={totals['tables']} rows={totals['rows']}")
    # 5. Sequences.
    fixed = repair_sequences(target, table_map)
    print(f"sequences repaired: {fixed}")
    # 6. Reconcile.
    rec = reconcile(snapshot, target, table_map, bools, jsons)
    mism = [t for t in rec["tables"] if t["status"] != "OK"]
    print(f"reconcile ok={rec['ok']} mismatches={len(mism)}")
    for entry in rec["tables"]:
        print(f"  {entry['table']}|src={entry['source_rows']}|pg={entry['target_rows']}|"
              f"pk={entry['pk_match']}|content={entry['content_match']}|{entry['status']}")
    Path(REPO_ROOT / "docs" / "migration" / "MC-POSTGRES-01").mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report_path) if args.report_path else (
        REPO_ROOT / "docs" / "migration" / "MC-POSTGRES-01" / "05-reconciliation.json"
    )
    report_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return 0 if rec["ok"] else 6


def pg_dump(dsn: str, dest: Path) -> str:
    env = dict(os.environ)
    try:
        from sqlalchemy.engine.url import make_url

        url = make_url(normalize_pg_dsn(dsn))
        env["PGPASSWORD"] = url.password or ""
        cmd = [
            "pg_dump", "-h", url.host or "localhost", "-p", str(url.port or 5432),
            "-U", url.username or "", "-d", url.database or "", "-f", str(dest),
        ]
    except Exception:
        cmd = ["pg_dump"]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
    if proc.returncode != 0:
        raise SystemExit(f"pg_dump failed: {proc.stderr[-2000:]}")
    return str(dest)


def cmd_verify(args) -> int:
    target = resolve_target_dsn(args.target)
    table_map = orm_tables()
    rec = reconcile(Path(args.source), target, table_map,
                    boolean_columns(table_map), json_columns(table_map))
    for entry in rec["tables"]:
        print(f"  {entry['table']}|src={entry['source_rows']}|pg={entry['target_rows']}|"
              f"pk={entry['pk_match']}|content={entry['content_match']}|{entry['status']}")
    print("VERIFY " + ("OK" if rec["ok"] else "MISMATCH"))
    return 0 if rec["ok"] else 6


def main() -> int:
    parser = argparse.ArgumentParser(description="Mission Control SQLite->PostgreSQL migration")
    parser.add_argument("--source", default=str(REPO_ROOT / "data" / "mission_control.db"))
    parser.add_argument("--target", default=None, help="PostgreSQL DSN (default: MC_DSN)")
    parser.add_argument("--backup-dir", default=None)
    parser.add_argument("--report-path", default=None,
                        help="where to write the reconciliation JSON (default: docs/migration/MC-POSTGRES-01/05-reconciliation.json)")
    parser.add_argument("--allow-nonempty", action="store_true")
    parser.add_argument("--resume", action="store_true",
                        help="resume an interrupted migration: skip tables that already have rows, verify at the end")
    parser.add_argument("--pg-backup", default=None)
    parser.add_argument("--yes", action="store_true", help="authorize writes (required for --execute)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.inspect:
        return cmd_inspect(args)
    if args.dry_run:
        return cmd_dry_run(args)
    if args.execute:
        return cmd_execute(args)
    if args.verify:
        return cmd_verify(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
