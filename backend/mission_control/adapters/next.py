"""Next local SQLite snapshot adapter.

Next supports SQLite and PostgreSQL. Mission Control reads the configured local
SQLite file read-only and labels it as a snapshot. It does not inspect
PostgreSQL, infer a production state, or create coding work from a research
finding.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from mission_control.adapters.base import Adapter, AdapterResult, AdapterTarget, Observation
from mission_control.core.paths import is_within


class NextAdapter(Adapter):
    name = "next"
    capabilities = ["status", "opportunities_snapshot", "source_evidence"]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        repo = target.primary_repository
        if repo is None:
            return AdapterResult(
                available=False,
                detail="Next repository is unavailable.",
                capabilities=self.capabilities,
            )
        raw_path = str(target.config.get("database_path") or "data/next.db")
        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = (repo / db_path).resolve(strict=False)
        else:
            db_path = db_path.resolve(strict=False)
        if not is_within(db_path, repo):
            return AdapterResult(
                available=False,
                detail="Next database path must remain inside the Next repository.",
                capabilities=self.capabilities,
                error="Unsafe database path",
            )
        if not db_path.exists():
            return AdapterResult(
                available=False,
                detail=f"No local Next SQLite snapshot found at {db_path}.",
                capabilities=self.capabilities,
                error="SQLite snapshot missing",
            )
        limit = max(1, min(int(target.config.get("limit", 8)), 25))
        try:
            con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=2.0)
            con.row_factory = sqlite3.Row
            try:
                rows = con.execute(
                    "SELECT id, title, status, queue_type, score, created_at, evaluation_basis, evidence "
                    "FROM opportunities ORDER BY created_at DESC, CAST(score AS REAL) DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                total = con.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
            finally:
                con.close()
        except (sqlite3.Error, ValueError) as exc:
            return AdapterResult(
                available=False,
                detail="Next SQLite snapshot could not be read read-only.",
                capabilities=self.capabilities,
                error=str(exc)[:500],
            )
        observations: list[Observation] = []
        for row in rows:
            item = dict(row)
            external_id = f"next-opportunity-{item.get('id')}-{item.get('status')}"
            score = item.get("score")
            detail = (
                f"Status {item.get('status') or 'unknown'}; queue {item.get('queue_type') or 'unknown'}; "
                f"recorded score {score if score is not None else 'not recorded'}. "
                f"Evaluation basis: {str(item.get('evaluation_basis') or 'not stated')[:300]}. "
                f"Evidence: {str(item.get('evidence') or 'not stated')[:400]}"
            )
            observations.append(
                Observation(
                    title=f"Next: {str(item.get('title') or 'untitled opportunity')[:220]}",
                    detail=detail,
                    external_id=external_id,
                    evidence_ref=str(db_path),
                    provenance="external_claim",
                    occurred_at=str(item.get("created_at")) if item.get("created_at") else None,
                    metadata={
                        "next_id": item.get("id"),
                        "status": item.get("status"),
                        "queue_type": item.get("queue_type"),
                        "score": score,
                    },
                )
            )
        dsn_note = (
            " NEXT_DSN is present in this environment, so the SQLite snapshot may not be the active store."
            if os.environ.get("NEXT_DSN")
            else ""
        )
        detail = (
            f"Read {len(rows)} of {total} opportunities from the local SQLite snapshot "
            f"({db_path.name}). This is not a confirmed recommendation and not a production/PostgreSQL view."
            + dsn_note
        )
        return AdapterResult(
            available=True,
            detail=detail,
            capabilities=self.capabilities,
            observations=observations,
        )
