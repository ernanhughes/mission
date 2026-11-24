"""BLOG-01 D3: deterministic Writer Artifact post observations.

Builds a validated Writer post envelope from the deterministic Writer
Artifact detector run in-memory on extracted post body bytes. The detector
is imported read-only from the Writer checkout (never copied, never
modified here); the run is pure (``persist=False``), model-free, and
editorial-free: no second editorial score, no QC, no auto-improvement.

Binding contract (never interchanged):

- ``work_object.source_hash`` is the sha256 of the EVALUATED body bytes
  (the bytes the Artifact detector actually observed).
- ``work_object.content_sha256`` is the sha256 of the RAW file bytes
  (front matter included) and stays authoritative for location/editorial
  freshness via the D2 ``split_post_body`` binding.
- ``work_object.text_sha256`` repeats the body sha as a non-authoritative
  hint, mirroring the D2 context post block.

Span honesty: Artifact findings carry body-relative LINE spans
(``start_line``/``end_line``). Byte-exact raw spans are never inferred, so
every finding carries an explicit span-unavailable marker with the native
line evidence preserved verbatim. An undecodable body yields a
status-``unavailable`` envelope bound to the exact observed bytes (never a
fabricated CURRENT). A post with unmappable body bytes (unterminated front
matter) yields no envelope at all (``None``) — the D2 measure then honestly
reports ``NOT_RUN``.

Feed envelopes through ``build_site_post_context(writer_envelopes=[...])``
(the D2 ``validate_post_envelope`` path) so the context carries Writer
evidence under its own provider/scale alongside editorial.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from mission_control.core.errors import NotFound
from mission_control.websites import posts as _posts
from mission_control.websites.context import (
    WRITER_ENVELOPE_VERSION,
    split_post_body,
    validate_post_envelope,
)

PROVIDER = "artifact"
METHOD = "analyze_text"
METHOD_VERSION = "writer-artifact-detection.v1"

DEFAULT_ARTIFACT_SERVICE_PATH = Path(
    "C:/Projects/writer/packages/writer-runtime/writer_runtime/domains"
    "/book/services/artifact_detection_service.py"
)
ARTIFACT_SERVICE_PATH_ENV = "WRITER_ARTIFACT_SERVICE_PATH"

RUBRIC = {"rubric_id": "artifact-detectors", "profile": "post"}

ENVELOPE_LIMITATIONS = [
    "Deterministic stylistic detector only; no semantic or factual judgment.",
    "Scores use Writer Artifact native scales; never average across providers.",
    "Artifact line spans are not byte-exact mappings; raw-byte positions are never inferred.",
    "An empty result means no detector pattern fired, not verified clean prose.",
    "Unavailable means analysis could not run, not a clean bill.",
]

SPAN_UNAVAILABLE_REASON = (
    "Artifact reports body-relative line spans (start_line/end_line); "
    "byte-exact raw spans are not inferred — see native evidence lines."
)

# Native Writer Artifact detector measures, carried verbatim. Scale wording is
# fixed here (the detector ships scores without scale descriptors); values
# are never rescaled or reinterpreted. Each entry maps to
# (minimum, maximum, scale_type, description); count measures omit bounds.
DIMENSION_SCALES = {
    "artifact_score": (
        0.0,
        100.0,
        "continuous",
        "Writer Artifact native artifact score 0-100; higher is cleaner",
    ),
    "ai_smell_score": (
        0.0,
        1.0,
        "continuous",
        "Writer Artifact native ai-smell score 0-1; higher smells more synthetic",
    ),
    "cadence_score": (0.0, 1.0, "continuous", "Writer Artifact native cadence component 0-1"),
    "entropy_score": (0.0, 1.0, "continuous", "Writer Artifact native entropy component 0-1"),
    "repetition_score": (0.0, 1.0, "continuous", "Writer Artifact native repetition component 0-1"),
    "prefix_tic_score": (0.0, 1.0, "continuous", "Writer Artifact native prefix-tic component 0-1"),
    "mantra_score": (0.0, 1.0, "continuous", "Writer Artifact native mantra component 0-1"),
    "separator_score": (0.0, 1.0, "continuous", "Writer Artifact native separator component 0-1"),
    "variance_score": (
        0.0,
        1.0,
        "continuous",
        "Writer Artifact native sentence-variance component (coefficient of variation)",
    ),
    "paragraphs_analyzed": (None, None, "count", "Writer Artifact native paragraph count analyzed"),
    "flagged_paragraphs": (
        None,
        None,
        "count",
        "Writer Artifact native paragraph count at/above the smell threshold",
    ),
}

_service_class: Any = None


def artifact_service_path() -> Path:
    """Resolved detector source. Env override exists for isolated checkouts."""
    override = os.environ.get(ARTIFACT_SERVICE_PATH_ENV)
    return Path(override) if override else DEFAULT_ARTIFACT_SERVICE_PATH


def _load_service_class() -> Any:
    """Read-only import of Writer's ArtifactDetectionService (cached)."""
    global _service_class
    if _service_class is not None:
        return _service_class
    path = artifact_service_path()
    if not path.is_file():
        raise RuntimeError(
            f"Writer Artifact detector not found at {path} "
            f"(override via {ARTIFACT_SERVICE_PATH_ENV}); refusing to substitute a copy."
        )
    module_name = "writer_artifact_detection_ro"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"Cannot import Writer Artifact detector from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _service_class = module.ArtifactDetectionService
    return _service_class


def _unavailable_envelope(
    *,
    identity: str,
    body_sha: str,
    content_sha256: str | None,
    body_offset_bytes: int | None,
    evaluation_id: str,
    observed_at: str,
    note: str,
    source_path: str | None = None,
) -> dict[str, Any]:
    envelope = {
        "schema_version": WRITER_ENVELOPE_VERSION,
        "evaluation_id": evaluation_id,
        "observed_at": observed_at,
        "work_object": {
            "kind": "post",
            "target_id": identity,
            "source_path": source_path or identity,
            "source_hash": body_sha,
            "relpath": source_path or identity,
            "content_sha256": content_sha256,
            "text_sha256": body_sha,
            "body_offset_bytes": body_offset_bytes,
        },
        "producer": {
            "runtime_name": PROVIDER,
            "method": METHOD,
            "method_version": METHOD_VERSION,
        },
        "rubric": dict(RUBRIC),
        "status": "unavailable",
        "dimensions": [],
        "findings": [],
        "coverage": {"unit": "bytes", "note": note},
        "limitations": [*ENVELOPE_LIMITATIONS, note],
        "provenance": {
            "method": METHOD,
            "method_version": METHOD_VERSION,
            "source": "writer checkout (read-only import)",
            "persist": False,
            "note": note,
        },
        "supersedes": None,
    }
    return validate_post_envelope(envelope, identity=identity)


def build_artifact_envelope(
    *,
    identity: str,
    body: bytes,
    content_sha256: str | None = None,
    body_offset_bytes: int | None = None,
    evaluation_id: str | None = None,
    observed_at: str,
    source_path: str | None = None,
) -> dict[str, Any]:
    """Run the deterministic Artifact detector on body bytes; return a valid envelope.

    Pure function: no DB, no model, no writes. Raises only for missing
    detector source or invalid caller binding (empty identity/observed_at);
    detector/decoder failures degrade to status-``unavailable``, never to a
    fabricated observation.
    """
    if not isinstance(identity, str) or not identity:
        raise ValueError("identity must be a non-empty string")
    if not isinstance(observed_at, str) or not observed_at:
        raise ValueError("observed_at must be a non-empty string")
    if not isinstance(body, bytes):
        raise ValueError("body must be bytes")
    body_sha = hashlib.sha256(body).hexdigest()
    if evaluation_id is None:
        evaluation_id = f"artifact-post-{body_sha[:16]}"
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return _unavailable_envelope(
            identity=identity,
            body_sha=body_sha,
            content_sha256=content_sha256,
            body_offset_bytes=body_offset_bytes,
            evaluation_id=evaluation_id,
            observed_at=observed_at,
            note="Body bytes are not valid UTF-8; Artifact text analysis cannot run.",
            source_path=source_path,
        )
    try:
        service_class = _load_service_class()
        result = service_class().analyze_text(text=text, source_name=identity, persist=False)
    except Exception as exc:
        return _unavailable_envelope(
            identity=identity,
            body_sha=body_sha,
            content_sha256=content_sha256,
            body_offset_bytes=body_offset_bytes,
            evaluation_id=evaluation_id,
            observed_at=observed_at,
            note=f"Artifact analysis could not run ({type(exc).__name__}); no observation fabricated.",
            source_path=source_path,
        )
    stats = dict(result.detector_stats or {})
    dimensions = []
    for name, (minimum, maximum, scale_type, description) in DIMENSION_SCALES.items():
        if name not in stats:
            continue
        scale: dict[str, Any] = {"scale_type": scale_type, "description": description}
        if minimum is not None:
            scale["minimum"] = minimum
        if maximum is not None:
            scale["maximum"] = maximum
        dimensions.append(
            {
                "dimension": name,
                "score": stats[name],
                "scale": scale,
                "rationale": "Writer Artifact native measure carried verbatim; not an editorial judgment.",
                "evidence_spans": [],
            }
        )
    findings = []
    for issue in result.issues or []:
        findings.append(
            {
                "family": "artifact",
                "code": issue.type,
                "claim": issue.title,
                "severity": issue.severity,
                "evidence": list(issue.evidence or []),
                "span": {"available": False, "reason": SPAN_UNAVAILABLE_REASON},
                "native": {
                    "issue_id": issue.issue_id,
                    "start_line": issue.start_line,
                    "end_line": issue.end_line,
                    "stats": dict(issue.stats or {}),
                },
            }
        )
    envelope = {
        "schema_version": WRITER_ENVELOPE_VERSION,
        "evaluation_id": evaluation_id,
        "observed_at": observed_at,
        "work_object": {
            "kind": "post",
            "target_id": identity,
            "source_path": source_path or identity,
            "source_hash": body_sha,
            "relpath": source_path or identity,
            "content_sha256": content_sha256,
            "text_sha256": body_sha,
            "body_offset_bytes": body_offset_bytes,
        },
        "producer": {
            "runtime_name": PROVIDER,
            "method": METHOD,
            "method_version": METHOD_VERSION,
        },
        "rubric": dict(RUBRIC),
        "status": "complete" if findings else "empty",
        "dimensions": dimensions,
        "findings": findings,
        "coverage": {
            "unit": "characters",
            "note": "single deterministic Artifact pass over extracted body bytes",
        },
        "limitations": list(ENVELOPE_LIMITATIONS),
        "provenance": {
            "method": METHOD,
            "method_version": METHOD_VERSION,
            "detector": "ArtifactDetectionService",
            "source": "writer checkout (read-only import)",
            "persist": False,
            "sentence_count": result.sentence_count,
            "paragraphs_analyzed": result.paragraphs_analyzed,
            "note": "in-memory run on extracted body bytes; no model, no writes",
        },
        "supersedes": None,
    }
    return validate_post_envelope(envelope, identity=identity)


def artifact_envelope_for_live_post(
    blog_dir: Path | str,
    *,
    identity: str,
    observed_at: str,
    evaluation_id: str | None = None,
) -> dict[str, Any] | None:
    """Bind-and-observe one live post: split raw bytes, run Artifact on the body.

    Returns ``None`` when no evaluated bytes exist (unmappable body) so the
    caller feeds zero envelopes and the D2 measure honestly reports
    ``NOT_RUN``. Raises ``NotFound`` for an unknown identity, mirroring the
    D2 builder.
    """
    directory = Path(blog_dir)
    live = {post["identity"]: post for post in _posts._live_posts(directory)}
    post = live.get(identity)
    if post is None:
        raise NotFound("Article not found in the blog directory.")
    candidate = directory / Path(*Path(post["relpath"]).parts)
    try:
        raw = candidate.read_bytes()
    except OSError:
        raise NotFound(f"Article is unavailable: {post['relpath']}") from None
    raw_sha = _posts.hash_content(raw)
    split = split_post_body(raw)
    if split["body"] is None:
        return None
    return build_artifact_envelope(
        identity=identity,
        body=split["body"],
        content_sha256=raw_sha,
        body_offset_bytes=split["offset"],
        evaluation_id=evaluation_id,
        observed_at=observed_at,
        source_path=post["relpath"],
    )
