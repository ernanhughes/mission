"""Evidence adapters for the three priority books."""

from __future__ import annotations

import hashlib
import json
import re
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


def _read_text(path: Path, limit: int = 64_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _chapter_count(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(
        1
        for item in path.iterdir()
        if item.is_file() and re.match(r"^\d{2,3}-.*\.md$", item.name, re.IGNORECASE)
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LanguageBookAdapter(Adapter):
    name = "language"
    capabilities = ["book_manuscript_summary", "repository_evidence", "status_claim"]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        repo = target.repo_by_name("language") or target.primary_repository
        if repo is None or not repo.exists():
            return AdapterResult(
                available=False,
                detail="Language manuscript repository is not available at the configured path.",
                capabilities=self.capabilities,
            )
        chapter_dir = repo / "content" / "books" / "language"
        chapters = _chapter_count(chapter_dir)
        observations: list[Observation] = []
        if chapters:
            observations.append(
                Observation(
                    title=f"Language manuscript: {chapters} chapter files present",
                    detail=(
                        f"Observed {chapters} numbered chapter source files in "
                        f"{chapter_dir}. File presence is not a measure of editorial quality "
                        "or completion."
                    ),
                    external_id=f"language-chapter-count-{chapters}",
                    evidence_ref=str(chapter_dir),
                    metadata={"chapter_count": chapters},
                    occurred_at=_iso_now(),
                )
            )
        status_path = repo / "planning" / "STATUS.md"
        if status_path.exists():
            text = _read_text(status_path, 20_000)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            summary = next((line.lstrip("# ").strip() for line in lines if line.startswith("#")), "")
            date_match = re.search(r"As of (\d{4}-\d{2}-\d{2})", text)
            detail = summary[:500] if summary else "Planning status file is present."
            if date_match:
                detail = f"{detail} (status dated {date_match.group(1)})"
            observations.append(
                Observation(
                    title="Language planning status is available",
                    detail=detail,
                    external_id=f"language-status-{date_match.group(1) if date_match else status_path.stat().st_mtime_ns}",
                    evidence_ref=str(status_path),
                    provenance="external_claim",
                    metadata={"status_date": date_match.group(1) if date_match else None},
                    occurred_at=_iso_now(),
                )
            )
        detail = f"Read-only manuscript evidence from {repo}."
        if not chapters:
            detail += " No numbered chapter files were found in content/books/language."
        return AdapterResult(
            available=True,
            detail=detail,
            capabilities=self.capabilities,
            observations=observations,
        )


class InferenceBookAdapter(Adapter):
    name = "inference"
    capabilities = ["book_manuscript_summary", "repository_evidence", "status_claim"]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        repo = target.repo_by_name("inference") or target.primary_repository
        if repo is None or not repo.exists():
            return AdapterResult(
                available=False,
                detail="Inference repository is not available at C:\\books\\inference.",
                capabilities=self.capabilities,
            )
        chapter_dir = repo / "content" / "books" / "inference"
        chapters = _chapter_count(chapter_dir)
        observations: list[Observation] = []
        if chapters:
            observations.append(
                Observation(
                    title=f"Inference manuscript: {chapters} chapter files present",
                    detail=(
                        f"Observed {chapters} numbered chapter source files in {chapter_dir}. "
                        "File presence does not establish technical or editorial verification."
                    ),
                    external_id=f"inference-chapter-count-{chapters}",
                    evidence_ref=str(chapter_dir),
                    metadata={"chapter_count": chapters},
                    occurred_at=_iso_now(),
                )
            )
        readme = repo / "README.md"
        if readme.exists():
            text = _read_text(readme, 20_000)
            clean = re.sub(r"[*_`]", "", text)
            match = re.search(r"Status\s*\(([^)]+)\):\s*(.+)", clean)
            if match:
                date = match.group(1).strip()
                statement = " ".join(match.group(2).split())[:700]
                observations.append(
                    Observation(
                        title=f"Inference repository status claim ({date})",
                        detail=statement,
                        external_id=f"inference-status-{date}",
                        evidence_ref=str(readme),
                        provenance="external_claim",
                        metadata={"status_date": date},
                        occurred_at=_iso_now(),
                    )
                )
        return AdapterResult(
            available=True,
            detail=f"Read-only manuscript evidence from {repo}.",
            capabilities=self.capabilities,
            observations=observations,
        )


class MathBookAdapter(Adapter):
    name = "math"
    capabilities = ["book_manuscript_summary", "qualification_evidence", "open_obligations"]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        repo = target.repo_by_name("math") or target.primary_repository
        if repo is None or not repo.exists():
            return AdapterResult(
                available=False,
                detail="Math repository is not available at the configured path.",
                capabilities=self.capabilities,
            )
        relative_report = str(target.config.get("report_path", "artifacts/math01/report.json"))
        report_path = (repo / relative_report).resolve(strict=False)
        if not is_within(report_path, repo):
            return AdapterResult(
                available=False,
                detail="Configured MATH01 report path escapes the Math repository.",
                capabilities=self.capabilities,
                error="Unsafe report path",
            )
        chapter_dir = repo / "book"
        # Chapter count is advisory; the present book tree uses planning docs.
        manuscript_files = (
            [item for item in chapter_dir.rglob("*.md") if item.is_file()]
            if chapter_dir.exists()
            else []
        )
        observations: list[Observation] = []
        recommendations: list[RecommendationSeed] = []
        if report_path.exists():
            try:
                raw = report_path.read_bytes()
                if len(raw) > 10_000_000:
                    raise ValueError("Report exceeds the 10 MB read limit")
                report = json.loads(raw.decode("utf-8"))
                if not isinstance(report, dict):
                    raise ValueError("Report is not a JSON object")
                schema = str(report.get("schema_version", ""))
                if not schema.startswith("math-investigation-report-v1"):
                    raise ValueError(f"Unsupported MATH01 report schema: {schema or 'missing'}")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return AdapterResult(
                    available=False,
                    detail="MATH01 report exists but could not be read safely.",
                    capabilities=self.capabilities,
                    error=str(exc)[:500],
                )
            generated_at = str(report.get("generated_at") or _iso_now())
            assessments = report.get("assessments") or []
            for assessment in assessments[:6]:
                if not isinstance(assessment, dict):
                    continue
                claim = str(assessment.get("claim_id") or "unknown claim")
                status = str(assessment.get("overall_status") or "unknown")
                rationale = str(assessment.get("rationale") or "")[:600]
                external_id = f"math-claim-{claim}-{status}"
                observations.append(
                    Observation(
                        title=f"MATH01: {claim} — {status}",
                        detail=rationale,
                        external_id=external_id,
                        evidence_ref=str(report_path),
                        provenance="external_claim",
                        occurred_at=generated_at,
                        metadata={"claim_id": claim, "status": status},
                    )
                )
                obligations = assessment.get("unresolved_obligations") or []
                for obligation in obligations[:2]:
                    if not isinstance(obligation, str) or not obligation.strip():
                        continue
                    digest = hashlib.sha1(
                        f"{claim}:{obligation}".encode("utf-8")
                    ).hexdigest()[:10]
                    recommendations.append(
                        RecommendationSeed(
                            title=f"Review MATH01 obligation: {obligation.strip()[:180]}",
                            rationale=(
                                f"The recorded MATH01 assessment for {claim} is {status}. "
                                f"Its unresolved obligation is: {obligation.strip()}"
                            ),
                            evidence=[str(report_path), f"claim:{claim}"],
                            external_id=f"math-obligation-{digest}",
                            project_id=target.project_id,
                            provenance="derived_observation",
                            source_ref=str(report_path),
                        )
                    )
            capabilities = report.get("capabilities") or []
            available_tools = [
                str(item.get("system"))
                for item in capabilities
                if isinstance(item, dict) and item.get("available")
            ]
            if available_tools:
                observations.append(
                    Observation(
                        title="MATH01 tool capabilities observed",
                        detail="Available at the recorded run: " + ", ".join(available_tools),
                        external_id="math-capabilities-" + "-".join(sorted(available_tools)),
                        evidence_ref=str(report_path),
                        provenance="external_claim",
                        occurred_at=generated_at,
                        metadata={"systems": available_tools},
                    )
                )
            detail = (
                f"Read {len(assessments)} MATH01 claim assessments from {report_path.name}. "
                "Results remain evidence from the recorded run, not an independent re-verification."
            )
        else:
            detail = f"No MATH01 report found at {report_path}."
        if manuscript_files:
            observations.append(
                Observation(
                    title=f"Math book tree: {len(manuscript_files)} Markdown planning/source files",
                    detail=(
                        "File presence is reported for orientation only; it is not treated as "
                        "manuscript completion."
                    ),
                    external_id=f"math-book-files-{len(manuscript_files)}",
                    evidence_ref=str(chapter_dir),
                    provenance="verified_observation",
                    occurred_at=_iso_now(),
                    metadata={"file_count": len(manuscript_files)},
                )
            )
        return AdapterResult(
            available=report_path.exists(),
            detail=detail,
            capabilities=self.capabilities,
            error=None if report_path.exists() else "MATH01 report not found",
            observations=observations,
            recommendations=recommendations[:4],
        )
