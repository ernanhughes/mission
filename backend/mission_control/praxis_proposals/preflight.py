"""MC-PRAXIS-09: advisory preflight from authoritative Mission Control data.

Findings are advisory only. They never decide execution eligibility; the
authoritative import validation does that. Every finding cites its evidence and
separates the current environment from historical observations.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from mission_control.adapters.service import get_app_adapter
from mission_control.models import Application, IntegrationExecution, IntegrationRecord
from mission_control.persistence.db import now_iso

_TIMEOUT_TEXT = re.compile(r"timed out after ([\d.]+)\s*seconds", re.IGNORECASE)
RUNTIME_WINDOW = 50


def _duration_seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    try:
        a = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        return round(max(0.0, (b - a).total_seconds()), 2)
    except ValueError:
        return None


def _finding(*, finding_id: str, severity: str, capability_id: str,
             message: str, evidence: list[str], environment: dict[str, Any],
             remediation: str = "", confidence: str = "measured") -> dict[str, Any]:
    return {
        "id": finding_id,
        "severity": severity,
        "capability_id": capability_id,
        "message": message,
        "evidence": evidence[:10],
        "observed_at": now_iso(),
        "environment_ref": environment,
        "remediation": remediation,
        "confidence": confidence,
        "blocking": False,
        "advisory": True,
    }


def compute_preflight(session: Session, row: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for index, step in enumerate(row.steps_json or []):
        capability_id = str(step.get("capability_id", ""))
        if "." not in capability_id:
            continue
        application_id, action_id = capability_id.split(".", 1)
        application = session.get(Application, application_id)
        if application is None:
            findings.append(_finding(
                finding_id=f"preflight[{index}].application_missing",
                severity="warning", capability_id=capability_id,
                message="Application is not registered in Mission Control.",
                evidence=[], environment={}, confidence="unknown"))
            continue
        config = dict(application.adapter_config or {})
        timeout = config.get("timeout_seconds")
        environment = {"timeout_seconds": timeout,
                       "adapter": application.integration_adapter}
        executions = session.scalars(
            select(IntegrationExecution)
            .where(IntegrationExecution.application_id == application_id,
                   IntegrationExecution.action_id == action_id)
            .order_by(desc(IntegrationExecution.created_at))
            .limit(RUNTIME_WINDOW)
        ).all()
        samples = [(execution.id, _duration_seconds(execution.started_at,
                                                   execution.ended_at),
                    execution.status, execution.error or "")
                   for execution in executions]
        durations = [d for _, d, _, _ in samples if d is not None]
        timeout_failures = [
            (execution_id, error) for execution_id, _, status, error in samples
            if status == "failed" and "timed out" in error.casefold()
        ]
        if durations:
            findings.append(_finding(
                finding_id=f"preflight[{index}].runtime_observed",
                severity="info", capability_id=capability_id,
                message=(f"Observed runtime from {len(durations)} execution(s): "
                         f"min={min(durations)}s, max={max(durations)}s."),
                evidence=[execution_id for execution_id, _, _, _ in samples
                          if execution_id][:10],
                environment=environment))
            if timeout is not None:
                if max(durations) >= float(timeout):
                    findings.append(_finding(
                        finding_id=f"preflight[{index}].timeout_risk",
                        severity="warning", capability_id=capability_id,
                        message=(f"Observed maximum {max(durations)}s meets or "
                                 f"exceeds the current timeout {timeout}s; "
                                 "failure is plausible, not certain."),
                        evidence=[execution_id for execution_id, _, _, _ in samples
                                  if execution_id][:10],
                        environment=environment,
                        remediation=("Raise this integration's timeout via the "
                                     "supported configuration API or reduce the "
                                     "workload scope.")))
                elif max(durations) >= 0.8 * float(timeout):
                    findings.append(_finding(
                        finding_id=f"preflight[{index}].timeout_margin_thin",
                        severity="warning", capability_id=capability_id,
                        message=(f"Observed maximum {max(durations)}s is within "
                                 f"20% of the {timeout}s timeout; variance may "
                                 "exceed it."),
                        evidence=[execution_id for execution_id, _, _, _ in samples
                                  if execution_id][:10],
                        environment=environment))
                else:
                    findings.append(_finding(
                        finding_id=f"preflight[{index}].runtime_within_timeout",
                        severity="info", capability_id=capability_id,
                        message=(f"Observed maximum {max(durations)}s is below "
                                 f"the {timeout}s timeout."),
                        evidence=[], environment=environment))
        else:
            findings.append(_finding(
                finding_id=f"preflight[{index}].runtime_evidence_missing",
                severity="info", capability_id=capability_id,
                message="No recorded runtime samples; timing risk is unknown.",
                evidence=[], environment=environment, confidence="unknown"))

        if timeout_failures:
            historical: list[str] = []
            for execution_id, error in timeout_failures[:5]:
                match = _TIMEOUT_TEXT.search(error)
                label = (f"{execution_id} (historical timeout "
                         f"{match.group(1)}s)" if match else execution_id)
                historical.append(label)
            findings.append(_finding(
                finding_id=f"preflight[{index}].historical_timeout_failures",
                severity="warning", capability_id=capability_id,
                message=(f"{len(timeout_failures)} prior timeout failure(s); "
                         "historical configuration may differ from the current "
                         "environment."),
                evidence=historical, environment=environment,
                remediation="Review the historical failure before approving a run.",
                confidence="measured"))

        # Authoritative resource resolution is validated at import; preflight
        # restates it as advisory context for the reviewer.
        parameters = dict(step.get("parameters") or {})
        book_id = parameters.get("book_id")
        if book_id:
            record = session.scalar(
                select(IntegrationRecord).where(
                    IntegrationRecord.application_id == "writer",
                    IntegrationRecord.resource_type == "writer_editing_book",
                    IntegrationRecord.external_id == str(book_id))
            )
            if record is None:
                findings.append(_finding(
                    finding_id=f"preflight[{index}].book_unresolved",
                    severity="warning", capability_id=capability_id,
                    message=f"Book {book_id!r} has no registered resource.",
                    evidence=[], environment=environment, confidence="unknown"))
            else:
                root = str((record.data or {}).get("project_root") or "")
                supplied = str(parameters.get("book_root") or "")
                agreed = bool(root) and supplied.replace("\\", "/").casefold() \
                    == root.replace("\\", "/").casefold()
                findings.append(_finding(
                    finding_id=f"preflight[{index}].book_resolved",
                    severity="info" if agreed else "warning",
                    capability_id=capability_id,
                    message=(f"Book {book_id!r} resolves to {root!r}; supplied "
                             f"book_root {'matches' if agreed else 'differs'}."),
                    evidence=[f"writer_editing_book:{record.external_id}"],
                    environment=environment))
                try:
                    from datetime import datetime as _dt

                    observed = _dt.fromisoformat(
                        str(record.observed_at).replace("Z", "+00:00"))
                    age = (datetime.now(observed.tzinfo) - observed).total_seconds()
                    if age > float(record.stale_after_seconds or 3600):
                        findings.append(_finding(
                            finding_id=f"preflight[{index}].book_resource_stale",
                            severity="warning", capability_id=capability_id,
                            message=(f"Book resource was last observed "
                                     f"{int(age)}s ago; registration may have "
                                     "changed."),
                            evidence=[f"writer_editing_book:{record.external_id}"],
                            environment=environment,
                            remediation="Refresh the Writer integration before "
                                        "approving.",
                            confidence="measured"))
                except (TypeError, ValueError):
                    pass
    return findings


def capability_metadata(session: Session, row: Any) -> list[dict[str, Any]]:
    """Approval-facing capability facts: version, permissions, side effects."""
    out: list[dict[str, Any]] = []
    for step in row.steps_json or []:
        capability_id = str(step.get("capability_id", ""))
        if "." not in capability_id:
            continue
        application_id, action_id = capability_id.split(".", 1)
        application = session.get(Application, application_id)
        adapter = get_app_adapter(
            (application.integration_adapter if application else "") or "")
        action = next((item for item in (adapter.actions if adapter else [])
                       if item.id == action_id), None)
        out.append({
            "capability_id": capability_id,
            "adapter_protocol": "mc09.1",
            "risk": action.risk if action else "unknown",
            "side_effect": action.side_effect if action else "unknown",
            "approval_required": action.approval_required if action else True,
            "enabled": action.enabled if action else False,
        })
    return out
