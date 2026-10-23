"""CoCoder review-artifact adapter.

Reads the documented ``cocoder review --format json --output FILE`` artifact.
No CoCoder internals are imported and no repository is modified.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from mission_control.adapters.base import (
    Adapter,
    AdapterResult,
    AdapterTarget,
    Observation,
    RecommendationSeed,
)
from mission_control.core.paths import is_within


class CoCoderAdapter(Adapter):
    name = "cocoder"
    capabilities = ["review_summary", "findings", "quality_evidence"]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        repo = target.primary_repository
        raw_path = str(target.config.get("review_json_path") or "").strip()
        if not raw_path:
            return AdapterResult(
                available=False,
                detail=(
                    "CoCoder is enabled as an integration, but no review artifact is configured. "
                    "Run `cocoder review --format json --output FILE` and set review_json_path."
                ),
                capabilities=self.capabilities,
            )
        if repo is None:
            return AdapterResult(
                available=False,
                detail="CoCoder repository path is unavailable.",
                capabilities=self.capabilities,
            )
        report_path = Path(raw_path)
        if not report_path.is_absolute():
            report_path = (repo / report_path).resolve(strict=False)
        else:
            report_path = report_path.resolve(strict=False)
        if not is_within(report_path, repo):
            return AdapterResult(
                available=False,
                detail="Configured review artifact must remain inside the CoCoder repository.",
                capabilities=self.capabilities,
                error="Unsafe review artifact path",
            )
        if not report_path.exists():
            return AdapterResult(
                available=False,
                detail=f"Configured review artifact does not exist: {report_path}",
                capabilities=self.capabilities,
                error="Review artifact missing",
            )
        try:
            raw = report_path.read_bytes()
            if len(raw) > 5_000_000:
                raise ValueError("Review artifact exceeds the 5 MB read limit")
            review = json.loads(raw.decode("utf-8"))
            if not isinstance(review, dict) or "findings" not in review or "changed_files" not in review:
                raise ValueError("File is not a CoCoder review JSON artifact")
            findings = review.get("findings") or []
            if not isinstance(findings, list):
                raise ValueError("CoCoder findings field is not a list")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return AdapterResult(
                available=False,
                detail="CoCoder review artifact could not be parsed.",
                capabilities=self.capabilities,
                error=str(exc)[:500],
            )
        modified = datetime.fromtimestamp(report_path.stat().st_mtime, timezone.utc).isoformat()
        schema = str(review.get("schema_version") or "unknown")
        changed_files = review.get("changed_files") or []
        observation_id = hashlib.sha1(
            f"{report_path}:{modified}:{schema}".encode("utf-8")
        ).hexdigest()[:12]
        observations = [
            Observation(
                title=f"CoCoder review artifact: {len(changed_files)} changed files, {len(findings)} findings",
                detail=(
                    f"Review schema {schema}, artifact modified {modified}. "
                    f"Findings are CoCoder's evidence-backed claims, not a Mission Control verdict."
                ),
                external_id=f"cocoder-review-{observation_id}",
                evidence_ref=str(report_path),
                provenance="external_claim",
                occurred_at=modified,
                metadata={
                    "changed_files": len(changed_files),
                    "findings": len(findings),
                    "schema_version": schema,
                },
            )
        ]
        recommendations: list[RecommendationSeed] = []
        for finding in findings[:8]:
            if not isinstance(finding, dict):
                continue
            finding_id = str(finding.get("finding_id") or "")
            title = str(finding.get("title") or "CoCoder finding")
            statement = str(finding.get("statement") or "")
            severity = str(finding.get("severity") or "unknown")
            claim_type = str(finding.get("claim_type") or "unknown")
            observations.append(
                Observation(
                    title=f"CoCoder {severity}: {title[:200]}",
                    detail=(
                        f"{statement[:700]} (claim type: {claim_type}; confidence: "
                        f"{finding.get('confidence', 'unknown')})"
                    ),
                    external_id=f"cocoder-finding-{finding_id or hashlib.sha1(title.encode()).hexdigest()[:10]}",
                    evidence_ref=str(report_path),
                    provenance="external_claim",
                    occurred_at=modified,
                    metadata={"severity": severity, "claim_type": claim_type},
                )
            )
            if severity == "high" and len(recommendations) < 3:
                recommendations.append(
                    RecommendationSeed(
                        title=f"Review CoCoder finding: {title[:200]}",
                        rationale=statement[:900],
                        evidence=[str(report_path), f"finding:{finding_id}"] if finding_id else [str(report_path)],
                        external_id=f"cocoder-rec-{finding_id or hashlib.sha1(title.encode()).hexdigest()[:10]}",
                        project_id=target.project_id,
                        provenance="derived_observation",
                        source_ref=str(report_path),
                    )
                )
        detail = (
            f"Read CoCoder review artifact from {report_path.name}; "
            "availability is not a merge recommendation."
        )
        return AdapterResult(
            available=True,
            detail=detail,
            capabilities=self.capabilities,
            observations=observations,
            recommendations=recommendations,
        )
