"""WORK-OUTCOME-01 W6D: governed continuous pass (manual-first).

One bounded pass over the AI project: deterministic observation (W1
checkpoints, read-only source) -> episode reconciliation (W2) -> staleness
marking (W6C, targeted only) -> queue selection -> deterministic evaluation
of queued episodes -> finding-group refresh. Semantic evaluation runs only
when explicitly enabled AND a governed free route is available AND budget
remains; paid inference budget is hard zero and cannot be raised through
this path. Never performs corrective execution, never touches OpenCode
source records, never scans the ecosystem (project-scoped only).

The scheduled loop that would call run_pass on a timer is intentionally
NOT started here: scheduling lives with the existing maintenance pattern
(see W6D-SCHEDULING-ARCHITECTURE) and stays disabled by default. Tests and
W6E drive run_pass directly (manual invocation), which is the supported
W6 operation until an operator enables the timer.
"""

from __future__ import annotations

import time
from typing import Any

PASS_VERSION = "w6d-v1"
MAX_EVAL_PER_PASS = 10


def run_pass(database: Any, services: dict[str, Any], *,
             project_contains: str | None = None,
             allow_semantic: bool = False,
             max_eval: int = MAX_EVAL_PER_PASS) -> dict[str, Any]:
    """Execute one governed pass. Returns a receipt; raises nothing for
    expected source/model outages (records blocked/failed instead)."""
    started = time.monotonic()
    receipt: dict[str, Any] = {
        "pass_version": PASS_VERSION, "status": "completed",
        "observed": {}, "reconciled": {}, "stale_marked": 0,
        "evaluated": [], "semantic_calls": 0, "groups": {},
        "blocked": [], "errors": [],
    }
    obs = services.get("observation")
    eps = services.get("episodes")
    evalu = services.get("evaluation")
    policies = services.get("policies")

    def _gated(capability: str) -> bool:
        """W9E: project policies gate capabilities.

        W9 review F1: this must not fail open. Semantic evaluation is
        refused unless a policy service AND a project scope are present
        (absence is a configuration error, never consent). The
        deterministic capabilities keep their historical manual
        behaviour when unscoped, but the receipt records that policy
        was not consulted so an operator can see it.
        """
        if policies is None or not project_contains:
            if capability.startswith("evaluate_semantic"):
                return False
            receipt["blocked"].append(f"{capability}:policy_unscoped")
            return True
        try:
            return bool(policies.gate(project_contains, capability)["allowed"])
        except Exception:
            return False

    # 1. Deterministic observation (bounded, checkpointed, read-only).
    if obs is not None and _gated("observe"):
        try:
            out = obs.run_observation(project_contains=project_contains,
                                      limit_sessions=500)
            receipt["observed"] = {
                "status": out.get("status"), "triaged": out.get("triaged", 0)}
            if out.get("status") not in ("completed", "cached"):
                receipt["blocked"].append(f"observation:{out.get('status')}")
        except Exception as exc:
            receipt["blocked"].append(f"observation:failed:{type(exc).__name__}")
            receipt["errors"].append(str(exc)[:200])
    elif obs is not None:
        receipt["blocked"].append("observation:policy_disallows")
    # 2. Episode reconciliation (existing W2 service).
    if eps is not None and _gated("reconstruct"):
        try:
            out = eps.run_reconstruction(project_contains=project_contains) \
                if hasattr(eps, "run_reconstruction") else {"status": "skipped"}
            receipt["reconciled"] = {"status": out.get("status")}
        except Exception as exc:
            receipt["blocked"].append(f"recon:failed:{type(exc).__name__}")
            receipt["errors"].append(str(exc)[:200])
    elif eps is not None:
        receipt["blocked"].append("reconstruct:policy_disallows")
    # 3-5. Queue -> deterministic evaluation of queued episodes.
    evaluated: list[str] = []
    sem_calls = 0
    eval_allowed = _gated("evaluate_mechanical")
    if allow_semantic and not _gated("evaluate_semantic"):
        allow_semantic = False
        receipt["blocked"].append("semantic:policy_disallows")
    if evalu is not None and eval_allowed:
        try:
            queue = evalu.eval_queue(limit=max(1, min(max_eval, 50)))
        except Exception as exc:
            queue = []
            receipt["blocked"].append(f"queue:failed:{type(exc).__name__}")
        for item in queue:
            eid = item.get("episode_id", "")
            if not eid or len(evaluated) >= max_eval:
                break
            try:
                out = evalu.evaluate_episode(eid, semantic=bool(allow_semantic))
                evaluated.append(eid)
                sem_calls += int(out.get("model_calls", 0) or 0)
            except Exception as exc:
                receipt["blocked"].append(f"eval:{eid}:failed:{type(exc).__name__}")
                receipt["errors"].append(str(exc)[:200])
    elif evalu is not None:
        # W9 review F2: a policy-blocked queue must be visible, not look
        # like "nothing was queued".
        receipt["blocked"].append("evaluate_mechanical:policy_disallows")
    receipt["evaluated"] = evaluated
    receipt["semantic_calls"] = sem_calls
    # 6. Finding-group refresh (presentation layer, idempotent).
    if evalu is not None and hasattr(evalu, "persist_groups"):
        try:
            receipt["groups"] = evalu.persist_groups()
        except Exception as exc:
            receipt["blocked"].append(f"groups:failed:{type(exc).__name__}")
    receipt["duration_ms"] = int((time.monotonic() - started) * 1000)
    return receipt
