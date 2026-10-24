"""CoCoder review integration.

Reads CoCoder's documented JSON review artifacts and can execute a bounded,
explicit assessment using the configured CoCoder CLI. Artifacts and CoCoder's
own state are written only under Mission Control's integration directory, never
inside the reviewed repository.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mission_control.adapters.base import (
    ActionContext,
    ActionSpec,
    ActionResult,
    Adapter,
    AdapterResult,
    AdapterTarget,
    ResourceSeed,
)
from mission_control.integrations.runner import run_tool

_REF = re.compile(r"^[A-Za-z0-9._~^/@{}:+-]{1,120}$")


def _iso_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


class CoCoderAdapter(Adapter):
    name = "cocoder"
    capabilities = [
        "health",
        "list_resources",
        "get_resource",
        "search_resources",
        "list_actions",
        "validate_action",
        "execute_action",
        "list_events",
    ]
    actions = [
        ActionSpec(
            id="run_review",
            title="Run a bounded CoCoder review",
            description=(
                "Runs the configured CoCoder CLI against a registered repository and "
                "writes the JSON artifact under Mission Control's data directory."
            ),
            risk="bounded_local_computation",
            capability="execute_action",
            approval_required=True,
            side_effect="local_generated_artifacts",
            parameters_schema={
                "type": "object",
                "required": ["repo_path"],
                "properties": {
                    "repo_path": {"type": "string", "description": "Registered repository path"},
                    "base": {"type": "string", "default": "HEAD~1"},
                    "head": {"type": "string", "default": "HEAD"},
                    "request": {"type": "string", "description": "Optional intent text"},
                    "timeout_seconds": {"type": "integer", "minimum": 10, "maximum": 300},
                },
                "additionalProperties": False,
            },
        )
    ]

    async def refresh(self, target: AdapterTarget) -> AdapterResult:
        artifact_dir = self._artifact_dir(target)
        configured_paths = list(target.config.get("artifact_paths") or [])
        legacy_path = str(target.config.get("review_json_path") or "").strip()
        if legacy_path:
            configured_paths.append(legacy_path)
        explicit = [
            Path(value)
            for value in configured_paths
            if isinstance(value, str) and value.strip()
        ]
        paths: list[Path] = []
        for path in explicit:
            if path.is_file() and path.suffix.casefold() == ".json":
                paths.append(path)
        if artifact_dir.is_dir():
            paths.extend(
                sorted(
                    (
                        item
                        for item in artifact_dir.glob("*.json")
                        if not item.name.endswith(".meta.json")
                    ),
                    key=lambda item: item.stat().st_mtime,
                    reverse=True,
                )[:8]
            )
        # Deduplicate while preserving newest-first order.
        seen: set[str] = set()
        unique_paths: list[Path] = []
        for path in paths:
            key = str(path.resolve(strict=False)).casefold()
            if key not in seen:
                seen.add(key)
                unique_paths.append(path)
        resources: list[ResourceSeed] = []
        errors: list[str] = []
        for path in unique_paths[:8]:
            try:
                resources.extend(self._read_artifact(path, target))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{path.name}: {exc.__class__.__name__}: {str(exc)[:200]}")
        if not unique_paths:
            return AdapterResult(
                available=False,
                detail=(
                    "No CoCoder review artifact is available. Run a bounded review from "
                    "the CoCoder workspace or configure an artifact path."
                ),
                capabilities=self.capabilities,
                actions=self.actions,
                error="No review artifacts",
            )
        available = bool(resources)
        detail = (
            f"Read {len([item for item in resources if item.resource_type == 'cocoder_review'])} "
            f"CoCoder review artifact(s) and {len([item for item in resources if item.resource_type == 'cocoder_finding'])} "
            "finding records. Acknowledging a finding is not code verification."
        )
        return AdapterResult(
            available=available,
            detail=detail,
            capabilities=self.capabilities,
            actions=self.actions,
            resources=resources,
            error="; ".join(errors[:3]) if errors and not resources else None,
        )

    def _artifact_dir(self, target: AdapterTarget) -> Path:
        configured = target.config.get("artifact_dir")
        if configured:
            path = Path(str(configured))
            if not path.is_absolute() and target.data_dir:
                path = Path(target.data_dir) / path
            return path
        if target.data_dir:
            return Path(target.data_dir) / "integrations" / "cocoder"
        return Path("data") / "integrations" / "cocoder"

    def _read_artifact(self, path: Path, target: AdapterTarget) -> list[ResourceSeed]:
        raw = path.read_bytes()
        if len(raw) > 20_000_000:
            raise ValueError("Review artifact exceeds 20 MB")
        review = json.loads(raw.decode("utf-8"))
        if not isinstance(review, dict):
            raise ValueError("Review artifact is not a JSON object")
        if "findings" not in review or "changed_files" not in review:
            raise ValueError("File is not a CoCoder review artifact")
        base = str(review.get("base") or "")
        head = str(review.get("head") or "")
        schema = str(review.get("schema_version") or "unknown")
        changed_files = review.get("changed_files") or []
        findings = review.get("findings") or []
        if not isinstance(findings, list):
            raise ValueError("Findings field is not a list")
        evidence = {
            str(item.get("fact_id")): item
            for item in (review.get("evidence") or [])
            if isinstance(item, dict) and item.get("fact_id")
        }
        observed_at = _iso_mtime(path)
        review_id = "review-" + hashlib.sha1(
            f"{path.resolve(strict=False)}:{path.stat().st_mtime_ns}".encode("utf-8")
        ).hexdigest()[:16]
        metadata_path = path.with_name(f"{path.stem}.meta.json")
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            try:
                loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    metadata = loaded
            except (OSError, ValueError):
                metadata = {}
        repo_path = str(metadata.get("repository_path") or target.primary_repository or "")
        summary = (
            f"{len(changed_files)} changed files; {len(findings)} findings; "
            f"schema {schema}; artifact {path.name}."
        )
        resources = [
            ResourceSeed(
                resource_type="cocoder_review",
                external_id=review_id,
                title=f"CoCoder review {base or '?'}..{head or '?'}",
                summary=summary,
                state="completed",
                evidence=[str(path)],
                data={
                    "artifact_path": str(path),
                    "repository_path": repo_path,
                    "schema_version": schema,
                    "base": base,
                    "head": head,
                    "working_tree": bool(review.get("working_tree")),
                    "changed_file_count": len(changed_files),
                    "finding_count": len(findings),
                    "change_shape": review.get("change_shape") or {},
                    "structural_analysis": review.get("structural_analysis"),
                    "unknowns": list(review.get("unknowns") or [])[:30],
                    "analysis_limitations": list(review.get("analysis_limitations") or [])[:30],
                    "source_timestamp": observed_at,
                },
                source_version=f"cocoder-review-{schema}",
                source_timestamp=observed_at,
                stale_after_seconds=3600,
            )
        ]
        for finding in findings[:400]:
            if not isinstance(finding, dict):
                continue
            finding_id = str(finding.get("finding_id") or "")
            if not finding_id:
                continue
            evidence_ids = [str(value) for value in (finding.get("evidence_ids") or [])]
            evidence_refs = [
                value for value in evidence_ids if value in evidence
            ]
            affected_paths = sorted(
                {
                    str(evidence[evidence_id].get("path"))
                    for evidence_id in evidence_refs
                    if evidence.get(evidence_id, {}).get("path")
                }
            )
            detail_evidence = [
                {
                    "fact_id": evidence_id,
                    "kind": evidence[evidence_id].get("kind"),
                    "description": evidence[evidence_id].get("description"),
                    "path": evidence[evidence_id].get("path"),
                    "symbol": evidence[evidence_id].get("symbol"),
                    "after_line": evidence[evidence_id].get("after_line"),
                }
                for evidence_id in evidence_refs
            ]
            severity = str(finding.get("severity") or "unknown")
            title = str(finding.get("title") or "CoCoder finding")
            resources.append(
                ResourceSeed(
                    resource_type="cocoder_finding",
                    external_id=f"{review_id}:{finding_id}",
                    title=f"{severity.upper()}: {title}"[:300],
                    summary=str(finding.get("statement") or "")[:1800],
                    state=f"{severity} / {finding.get('confidence') or 'unknown'}",
                    evidence=[str(path), *affected_paths],
                    data={
                        "review_id": review_id,
                        "finding_id": finding_id,
                        "rule_code": finding.get("rule_code"),
                        "category": finding.get("category"),
                        "severity": severity,
                        "confidence": finding.get("confidence"),
                        "claim_type": finding.get("claim_type"),
                        "statement": finding.get("statement"),
                        "assumptions": list(finding.get("assumptions") or []),
                        "unknowns": list(finding.get("unknowns") or []),
                        "question": finding.get("question"),
                        "remediation": finding.get("remediation"),
                        "affected_paths": affected_paths,
                        "evidence": detail_evidence,
                        "artifact_path": str(path),
                        "repository_path": repo_path,
                        "base": base,
                        "head": head,
                        "source_timestamp": observed_at,
                    },
                    source_version=f"cocoder-finding-{schema}",
                    source_timestamp=observed_at,
                    stale_after_seconds=3600,
                )
            )
        return resources

    def _review_parameters(
        self, action_id: str, parameters: dict[str, Any], context: ActionContext
    ) -> tuple[str, Path, str, str, str, int]:
        if action_id != "run_review":
            raise ValueError(f"Unknown CoCoder action: {action_id}")
        repo_value = str(parameters.get("repo_path") or "").strip()
        allowed = {
            str(Path(item).resolve(strict=False)).casefold()
            for item in context.allowed_repository_paths
        }
        if not repo_value:
            raise ValueError("repo_path is required")
        repo = Path(repo_value).resolve(strict=False)
        if str(repo).casefold() not in allowed:
            raise ValueError("repo_path is not a registered repository")
        base = str(parameters.get("base") or "HEAD~1").strip()
        head = str(parameters.get("head") or "HEAD").strip()
        for label, value in (("base", base), ("head", head)):
            if not _REF.match(value):
                raise ValueError(f"Invalid {label} ref")
        request_text = str(parameters.get("request") or "").strip()
        timeout = int(parameters.get("timeout_seconds") or 180)
        timeout = max(10, min(timeout, 300))
        return action_id, repo, base, head, request_text, timeout

    def validate_action(
        self, action_id: str, parameters: dict[str, Any], context: ActionContext
    ) -> None:
        self._review_parameters(action_id, parameters, context)

    def _engine_config(self, output_dir: Path) -> Path:
        """Keep CoCoder's SQLite/artifacts out of the reviewed repository.

        CoCoder resolves ``cqrs.database`` and ``cqrs.artifact_directory``
        relative to the reviewed repository. Absolute paths in an explicit
        config redirect both into Mission Control's data directory.
        """

        engine_dir = output_dir / "engine"
        engine_dir.mkdir(parents=True, exist_ok=True)
        config_path = output_dir / "cocoder-config.toml"
        content = (
            "[cqrs]\n"
            f'database = "{(engine_dir / "cocoder.db").as_posix()}"\n'
            f'artifact_directory = "{(engine_dir / "artifacts").as_posix()}"\n'
        )
        if not config_path.exists() or config_path.read_text(encoding="utf-8") != content:
            config_path.write_text(content, encoding="utf-8")
        return config_path

    async def execute_action(
        self, action_id: str, parameters: dict[str, Any], context: ActionContext
    ) -> ActionResult:
        _, repo, base, head, request_text, timeout = self._review_parameters(
            action_id, parameters, context
        )
        executable = str(
            context.config.get("executable")
            or (Path(context.application_repository_path or r"C:\Projects\cocoder") / "venv" / "Scripts" / "cocoder.exe")
        )
        output_dir = context.data_dir / "integrations" / "cocoder"
        output_dir.mkdir(parents=True, exist_ok=True)
        engine_config = self._engine_config(output_dir)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        artifact = output_dir / f"review-{stamp}-{uuid.uuid4().hex[:6]}.json"
        arguments = [
            "review",
            "--config",
            str(engine_config),
            "--repo",
            str(repo),
            "--base",
            base,
            "--head",
            head,
            "--format",
            "json",
            "--output",
            str(artifact),
        ]
        if request_text:
            arguments.extend(["--request", request_text[:2000]])
        result = await run_tool(
            executable,
            arguments,
            working_directory=str(output_dir),
            env_names=list(context.config.get("env_names") or []),
            timeout_seconds=timeout,
        )
        output = (result.stdout[-8000:] + "\n" + result.stderr[-4000:]).strip()
        if result.exit_code != 0 or not artifact.exists():
            return ActionResult(
                status="failed",
                output=output,
                result={"duration_seconds": result.duration_seconds},
                exit_code=result.exit_code,
                artifact_ref=str(artifact) if artifact.exists() else None,
            )
        metadata_path = artifact.with_name(f"{artifact.stem}.meta.json")
        metadata_path.write_text(
            json.dumps(
                {
                    "repository_path": str(repo),
                    "base": base,
                    "head": head,
                    "request": request_text,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        review = json.loads(artifact.read_text(encoding="utf-8"))
        return ActionResult(
            status="succeeded",
            output=output or f"Wrote {artifact.name}",
            result={
                "repository_path": str(repo),
                "base": base,
                "head": head,
                "changed_files": len(review.get("changed_files") or []),
                "findings": len(review.get("findings") or []),
                "duration_seconds": result.duration_seconds,
            },
            exit_code=result.exit_code,
            artifact_ref=str(artifact),
        )
