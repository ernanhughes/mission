"""WORK-OUTCOME-01 W9E: per-project Work Evaluation operating policies.

Reuses the existing ``settings`` key/value store (no new policy
infrastructure, no migration): one JSON document per project under
``wo_policy:<project_key>``. Policy levels map onto the capabilities
the pipeline already has — registration of a project never enables
anything by itself.

Levels (ordered by what they permit):
  disabled            no Work Evaluation processing at all
  observe             deterministic observation of new activity only
  reconstruct         + episode reconstruction / association
  manual_evaluation   + on-demand evaluation (mechanical or semantic)
  continuous_mechanical  + scheduled deterministic evaluation
  continuous_semantic    + scheduled semantic evaluation (still gated by
                          the global auto flag, budget and capability)

Backfill, incremental observation, reconstruction, mechanical
evaluation, semantic evaluation and corrective execution are SEPARATE
switches: this policy only covers the observation→evaluation ladder.
Corrective execution is never authorized by a policy level.
"""

from __future__ import annotations

import os
from typing import Any

from mission_control import models as orm
from mission_control.persistence.db import Database, now_iso

LEVELS = ("disabled", "observe", "reconstruct", "manual_evaluation",
          "continuous_mechanical", "continuous_semantic")

_RANK = {level: i for i, level in enumerate(LEVELS)}

PREFIX = "wo_policy:"

# W9E default rollout: ai is the pilot; Wave 1 is prepared but not enabled.
# One canonical key per project — path spellings resolve to it.
DEFAULT_POLICIES: dict[str, str] = {
    "ai": "manual_evaluation",
}


def _env_allowed(project_key: str) -> bool:
    """Optional operator allowlist so a broad environment cannot silently
    pull every project into evaluation. Empty/unset = no restriction."""
    raw = os.environ.get("MC_WORK_EVAL_PROJECTS", "").strip()
    if not raw:
        return True
    allowed = {p.strip() for p in raw.split(",") if p.strip()}
    return project_key in allowed


def resolve_project_key(session: Any, scope: str | None) -> str:
    """Map a caller's scope string onto a policy key.

    Network-free and deterministic: exact project id, then exact stored
    policy key, then basename match against known project ids. Unknown
    scopes resolve to themselves, whose default policy is `disabled`
    (fail closed). This keeps 'work/ai', 'Projects/ai' and 'ai' on the
    same policy instead of silently disabling a project because of a
    path spelling (W9 review F10).
    """
    raw = (scope or "").strip().replace("\\", "/")
    if not raw:
        return ""
    known = {p.id for p in session.query(orm.Project).all()}
    stored = {row.key[len(PREFIX):] for row in session.query(orm.Setting).filter(
        orm.Setting.key.like(PREFIX + "%")).all()}
    candidates = known | stored | set(DEFAULT_POLICIES)
    if raw in candidates:
        return raw
    base = raw.rstrip("/").rsplit("/", 1)[-1]
    if base in candidates:
        return base
    for cand in candidates:
        if cand.replace("\\", "/").endswith("/" + base):
            return cand
    return raw


def get_policy(session: Any, project_key: str) -> dict[str, Any]:
    row = session.get(orm.Setting, PREFIX + project_key)
    if row is not None and isinstance(row.value, dict):
        doc = dict(row.value)
        level = str(doc.get("level") or "disabled")
        if level not in _RANK:
            level = "disabled"
        try:
            lookback = int(doc.get("lookback_days") or 30)
        except (TypeError, ValueError):
            lookback = 30
        return {"project_key": project_key, "level": level,
                "lookback_days": max(1, min(lookback, 365)),
                "source": "explicit"}
    default = DEFAULT_POLICIES.get(project_key, "disabled")
    return {"project_key": project_key, "level": default,
            "lookback_days": 30, "source": "default"}


def set_policy(session: Any, project_key: str, level: str, *,
               lookback_days: int = 30, actor: str = "") -> dict[str, Any]:
    level = (level or "").strip().lower()
    if level not in _RANK:
        return {"status": "rejected",
                "error": f"unknown policy level: {level[:40]}"}
    if not project_key.strip():
        return {"status": "rejected", "error": "project_key is required"}
    if not actor.strip() or actor.strip().lower() in ("system", "model"):
        return {"status": "rejected",
                "error": "policy change requires a human actor"}
    lookback = max(1, min(int(lookback_days or 30), 365))
    doc = {"level": level, "lookback_days": lookback,
           "actor": actor.strip()[:80], "updated_at": now_iso()}
    row = session.get(orm.Setting, PREFIX + project_key)
    if row is None:
        session.add(orm.Setting(key=PREFIX + project_key, value=doc,
                                updated_at=now_iso()))
    else:
        row.value = doc
        row.updated_at = now_iso()
    return {"status": "completed", "project_key": project_key,
            "level": level, "lookback_days": lookback}


def allows(policy_level: str, capability: str) -> bool:
    """Capability gate. Unknown capability or level → False (fail closed).

    Semantic evaluation is split by mode (W9 review F11):
    ``evaluate_semantic_manual`` needs an operator at
    ``manual_evaluation`` or above; ``evaluate_semantic_scheduled``
    needs ``continuous_semantic``.
    """
    need = {
        "observe": "observe",
        "reconstruct": "reconstruct",
        "evaluate_manual": "manual_evaluation",
        "evaluate_mechanical": "continuous_mechanical",
        "evaluate_semantic": "continuous_semantic",
        "evaluate_semantic_scheduled": "continuous_semantic",
        "evaluate_semantic_manual": "manual_evaluation",
    }.get(capability)
    if need is None:
        return False
    return _RANK.get(policy_level, -1) >= _RANK[need]


def list_policies(session: Any) -> list[dict[str, Any]]:
    keys = {p.id for p in session.query(orm.Project).all()}
    for row in session.query(orm.Setting).filter(
            orm.Setting.key.like(PREFIX + "%")).all():
        keys.add(row.key[len(PREFIX):])
    keys |= set(DEFAULT_POLICIES)
    out = []
    for key in sorted(keys):
        doc = get_policy(session, key)
        doc["allowed"] = _env_allowed(key)
        out.append(doc)
    return out


def scope_gate(service: Any, scope: str | None, capability: str) -> bool:
    """Policy gate for manual endpoints (W9 review F3).

    An unscoped manual action stays allowed (the operator asked for the
    whole store explicitly, and no project policy can speak for it); a
    scoped action must be permitted by that project's policy. No policy
    service wired at all keeps historical behaviour so isolated tests
    and embedded callers are unaffected.
    """
    if service is None or not (scope or "").strip():
        return True
    try:
        return bool(service.gate(scope, capability)["allowed"])
    except Exception:
        return False


def policy_service(request: Any) -> Any:
    return getattr(request.app.state, "policy_service", None)


def require_scope_allowed(request: Any, scope: str | None,
                          capability: str) -> None:
    from fastapi import HTTPException

    if not scope_gate(policy_service(request), scope, capability):
        raise HTTPException(
            status_code=403,
            detail=(f"Project policy does not permit '{capability}' for "
                    f"{scope!r}. Set a policy at "
                    "/api/work-evaluation/policies first."))


class PolicyService:
    def __init__(self, database: Database) -> None:
        self._database = database

    def list(self) -> dict[str, Any]:
        with self._database.session() as session:
            return {"policies": list_policies(session),
                    "levels": list(LEVELS)}

    def get(self, project_key: str) -> dict[str, Any]:
        with self._database.session() as session:
            return get_policy(session, project_key)

    def set(self, project_key: str, level: str, *,
            lookback_days: int = 30, actor: str = "") -> dict[str, Any]:
        with self._database.session() as session:
            key = resolve_project_key(session, project_key) or project_key
            return set_policy(session, key, level,
                              lookback_days=lookback_days, actor=actor)

    def gate(self, project_key: str, capability: str) -> dict[str, Any]:
        with self._database.session() as session:
            key = resolve_project_key(session, project_key)
            doc = get_policy(session, key) if key else {
                "level": "disabled"}
        ok = bool(key) and _env_allowed(key) and allows(doc["level"], capability)
        return {"project_key": project_key, "resolved_key": key,
                "capability": capability, "level": doc["level"],
                "allowed": ok}
