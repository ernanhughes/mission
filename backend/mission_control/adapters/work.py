"""Work integration boundary.

Work is PostgreSQL-backed and exposes a documented CLI and local web dashboard.
No verified read-only opportunity export exists in this environment, so this
adapter reports the block instead of displaying fabricated commercial records.
"""

from __future__ import annotations

import os
from pathlib import Path

from mission_control.adapters.base import Adapter, AdapterResult, AdapterTarget


class WorkAdapter(Adapter):
    name = "work"
    capabilities = ["availability_diagnostics"]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        repo = Path("C:\\Projects\\work")
        env_present = bool(os.environ.get("WORK_DATABASE_URL"))
        if not repo.exists():
            return AdapterResult(
                available=False,
                detail="Work repository is not present at C:\\Projects\\work.",
                capabilities=self.capabilities,
                error="Repository missing",
            )
        return AdapterResult(
            available=False,
            detail=(
                "Work's documented opportunity service requires PostgreSQL. No verified read-only "
                "export is configured, so no opportunities, readiness states or income are displayed. "
                + (
                    "WORK_DATABASE_URL is present, but Mission Control does not couple directly to "
                    "another application's database."
                    if env_present
                    else "WORK_DATABASE_URL is not present."
                )
            ),
            capabilities=self.capabilities,
            error="Opportunity contract not available",
        )
