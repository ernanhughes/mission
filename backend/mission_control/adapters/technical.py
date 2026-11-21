"""Bounded deterministic verification of registered technical claims.

This adapter derives results from a local verifier. It never trusts a
client-supplied verdict and never changes claim status.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from mission_control.adapters.base import (
    ActionContext,
    ActionSpec,
    ActionResult,
    Adapter,
    AdapterResult,
    AdapterTarget,
)
from mission_control.technical.arithmetic_verifier import (
    VERIFIER_VERSION,
    validate_proposition,
    verify_proposition,
)

_CLAIM_ID = re.compile(r"^tclaim:[a-f0-9]{8,32}$")
ACTION_ID = "verify_claim"
RESULT_SCHEMA = "mc-technical-verification-result.v1"


def _live_revision(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk.replace(b"\r\n", b"\n"))
    return digest.hexdigest()


class TechnicalAdapter(Adapter):
    name = "technical"
    capabilities = ["technical_claims", "list_actions", "execute_action"]
    actions = [
        ActionSpec(
            id=ACTION_ID,
            title="Verify a registered technical claim with a bounded method",
            description=(
                "Runs the MC bounded arithmetic verifier against a registered "
                "claim's frozen proposition. It does not trust a client verdict, "
                "does not execute arbitrary code and does not change claim status."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "source_revision": {"type": "string"},
                    "method": {"type": "string", "enum": ["deterministic"]},
                    "proposition": {"type": "object"},
                    "max_seconds": {"type": "integer", "minimum": 1,
                                    "maximum": 30, "default": 10},
                },
                "required": ["claim_id", "source_revision", "method",
                             "proposition"],
                "additionalProperties": False,
            },
        )
    ]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        return AdapterResult(
            available=True,
            detail=("Bounded arithmetic verification is available; it reads "
                    "registered claims read-only."),
            capabilities=self.capabilities,
            actions=self.actions,
        )

    def _claim_row(self, context: ActionContext, claim_id: str) -> dict[str, Any] | None:
        db = Path(context.data_dir) / "mission_control.db"
        if not db.is_file():
            return None
        connection = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "select * from technical_claims where id = ?", (claim_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def validate_action(self, action_id: str, parameters: dict[str, Any],
                        context: ActionContext) -> None:
        if action_id != ACTION_ID:
            raise ValueError(f"Unsupported Technical action: {action_id}")
        claim_id = str(parameters.get("claim_id") or "")
        if not _CLAIM_ID.match(claim_id):
            raise ValueError("claim_id is not a valid technical claim identifier")
        source_revision = str(parameters.get("source_revision") or "")
        if not source_revision:
            raise ValueError("source_revision is required")
        if parameters.get("method") != "deterministic":
            raise ValueError("only the deterministic method is enabled")
        max_seconds = int(parameters.get("max_seconds", 10))
        if max_seconds < 1 or max_seconds > 30:
            raise ValueError("max_seconds must be between 1 and 30")
        proposition = parameters.get("proposition")
        errors = validate_proposition(proposition)
        if errors:
            raise ValueError("invalid proposition: " + "; ".join(errors))
        if proposition.get("claim_id") != claim_id:
            raise ValueError("proposition claim_id does not match claim_id")
        if proposition.get("source_revision") != source_revision:
            raise ValueError("proposition source_revision does not match")
        claim = self._claim_row(context, claim_id)
        if claim is None:
            raise ValueError("unknown technical claim")
        if claim["source_revision"] != source_revision:
            raise ValueError("stale source revision: parameter does not match claim")
        source = Path(str(claim.get("source_path") or ""))
        if not source.is_file():
            raise ValueError("claim source file is unavailable")
        live = _live_revision(source)
        if live != claim["source_revision"]:
            raise ValueError(
                "stale source revision: current file fingerprint differs from claim")
        if claim.get("claim_type") not in {
                "MATHEMATICAL", "FACTUAL", "EXPERIMENTAL", "IMPLEMENTATION",
                "API_CONTRACT", "ALGORITHMIC"}:
            raise ValueError("claim type is not supported by the deterministic method")

    async def execute_action(self, action_id: str, parameters: dict[str, Any],
                             context: ActionContext) -> ActionResult:
        if action_id != ACTION_ID:
            raise ValueError(f"Unsupported Technical action: {action_id}")
        try:
            self.validate_action(action_id, parameters, context)
        except ValueError as exc:
            return ActionResult(status="failed", error=str(exc))
        claim = self._claim_row(context, str(parameters["claim_id"]))
        if claim is None:
            return ActionResult(status="failed", error="unknown technical claim")
        proposition = dict(parameters["proposition"])
        started = time.perf_counter()
        result = verify_proposition(proposition)
        elapsed = round(time.perf_counter() - started, 6)
        result.update({
            "claim_id": claim["id"],
            "claim_type": claim.get("claim_type"),
            "source_path": claim.get("source_path"),
            "source_revision": claim.get("source_revision"),
            "method": "deterministic",
            "method_version": VERIFIER_VERSION,
            "max_seconds": int(parameters.get("max_seconds", 10)),
            "latency_ms": round(elapsed * 1000, 3),
            "claim_status_changed": False,
            "provenance": {
                "verifier": VERIFIER_VERSION,
                "claim_revision": claim.get("source_revision"),
                "proposition_fidelity": proposition.get("fidelity"),
            },
        })
        artifact = Path(context.data_dir) / "integrations" / "technical"
        artifact.mkdir(parents=True, exist_ok=True)
        digest = result["proposition_digest"][:12]
        path = artifact / f"verify-{claim['id'][7:19]}-{digest}.json"
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["artifact_ref"] = str(path)
        if result["execution_status"] != "succeeded":
            return ActionResult(
                status="failed",
                output=json.dumps(result)[:2000],
                result=result,
                artifact_ref=str(path),
                exit_code=1,
                error="verification proposition is unsupported or invalid",
            )
        return ActionResult(
            status="succeeded",
            output=(f"{claim['id']}: proposition "
                    f"{'holds' if result['proposition_holds'] else 'does not hold'} "
                    f"({result['computed_exact']})"),
            result=result,
            artifact_ref=str(path),
            exit_code=0,
        )
