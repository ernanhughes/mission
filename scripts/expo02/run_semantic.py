"""EXPO-02 Stage B/C: real model-backed semantic evaluation of calibration passages.

Uses the Writer detector's own hybrid-capable path end to end
(ArtifactDetectionExecutionContext + model_runner + prompt_builder), with a
thin adapter over the ai OpenCode provider (Pi-default route). No new model
gateway, no silent substitution: requested vs actual route recorded per call.

Semantic-only runs use llm mode WITHOUT prior rule results, so the model never
sees deterministic scores (blind per spec C4-B).

Caching: scripts/expo02/cache/<sha>_<modelslug>_<promptver>.json keyed by
(passage sha, prompt version, model route). Resume-safe; bounded by
--max-calls; failures recorded as BLOCKED-style rows, never fabricated.

Usage:
  python scripts/expo02/run_semantic.py --limit 2          # plumbing check
  python scripts/expo02/run_semantic.py --all              # full sweep
  python scripts/expo02/run_semantic.py --only P01,P44 --repeat 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, "C:/Projects/writer/packages/writer-runtime")
sys.path.insert(0, "C:/Projects/writer/packages/writer-core")
sys.path.insert(0, "C:/Projects/ai/src")

from ai.inference.dto import InferenceProfile, ReasoningRequest  # noqa: E402
from ai.inference.providers.opencode import OpenCodeCLIReasoningProvider  # noqa: E402
from writer_runtime.domains.artifact.artifact_engine.context import (  # noqa: E402
    ArtifactAnalysisContext,
)
from writer_runtime.domains.artifact.artifact_engine.detectors.base import (  # noqa: E402
    ArtifactDetectionExecutionContext,
)
from writer_runtime.domains.artifact.artifact_engine.detectors.expository_overload import (  # noqa: E402
    DETECTOR_VERSION,
    ExpositoryOverloadDetector,
)

MODEL_ROUTE = "opencode-go/deepseek-v4.1-flash"
BUILDER_VERSION = "expo-sem-builder-v1"
CACHE = BASE / "cache"
RESULTS = BASE / "semantic_results.jsonl"


class OpenCodeModelRunner:
    """Adapter: detector run_model() -> ai OpenCode provider."""

    def __init__(self, route: str, timeout_s: int = 300):
        profile = InferenceProfile(
            provider="opencode-go",
            model=route,
            route=route,
            temperature=0.0,
            max_output_tokens=1200,
            timeout_s=timeout_s,
        )
        self.last_telemetry: dict = {}
        self.last_raw_response: str = ""
        self.provider = OpenCodeCLIReasoningProvider(profile=profile, max_argv_chars=0)
        # NOTE (Stage B finding): argv transport breaks when the prompt contains
        # shell metacharacters (the detector template has `|` alternations and
        # quotes; cmd.exe split the command line). Force --file transport, the
        # same path manuscript_cli uses for chapters. max_prompt_chars stays.
        self.route = route

    def run_model(self, model_name=None, prompt="", temperature=None, max_tokens=None):
        req = ReasoningRequest(
            request_id=f"expo02-{uuid.uuid4().hex[:10]}",
            purpose="expository-overload semantic evaluation (calibration, candidate-only)",
            prompt=prompt,
            timeout_s=300,
            metadata={"requested_model": model_name or self.route},
        )
        t0 = time.perf_counter()
        result = self.provider.generate(req)
        latency = round(time.perf_counter() - t0, 1)
        self.last_raw_response = result.content or "" if result.status == "ok" else ""
        self.last_telemetry = {
            "latency_s": latency,
            "usage": result.usage.model_dump() if result.usage else None,
            "transport": (result.raw_metadata or {}).get("transport"),
            "requested_model": model_name or self.route,
            "actual_model": result.route or self.route,
            "route_resolution": result.route_resolution,
            "status": result.status,
            "error": result.error,
        }
        if result.status != "ok":
            return SimpleNamespace(
                output_text="",
                error=f"{result.status}: {result.error}",
                model_name=self.route,
                provider="opencode-go",
                execution_id=None,
            )
        return SimpleNamespace(
            output_text=result.content or "",
            error=None,
            model_name=result.route or self.route,
            provider="opencode-go",
            execution_id=(result.execution_refs or [None])[0],
        )


class ExpoPromptBuilder:
    """Minimal prompt builder: task prompt + delimited source. No secrets."""

    def build_artifact_detector_prompt(
        self, *, detector_name, issue_type, task_prompt, source_text,
        profile, metadata,
    ):
        ref = metadata.get("passage_ref", "calibration passage")
        return (
            f"{task_prompt}\n\n"
            f"---\n"
            f"## Passage under review ({ref}; profile {profile})\n\n"
            f"{source_text}\n"
        )


def prompt_version(detector: ExpositoryOverloadDetector) -> str:
    h = hashlib.sha256(
        (detector.prompt_template + "\n" + BUILDER_VERSION).encode()
    ).hexdigest()[:8]
    return f"expo-sem-v1+{h}"


def cache_key(sha: str, model_slug: str, pver: str) -> Path:
    return CACHE / f"{sha}_{model_slug}_{pver}.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--max-calls", type=int, default=200)
    args = ap.parse_args()

    recs = [json.loads(line) for line in (BASE / "passages.jsonl").read_text(encoding="utf-8").splitlines()]
    if args.only:
        want = set(args.only.split(","))
        recs = [r for r in recs if r["id"] in want]
    elif not args.all:
        recs = recs[: args.limit or 2]

    CACHE.mkdir(exist_ok=True)
    detector = ExpositoryOverloadDetector()
    pver = prompt_version(detector)
    model_slug = MODEL_ROUTE.replace("/", "-").replace(":", "-")
    print(f"prompt_version={pver} model={MODEL_ROUTE} passages={len(recs)} repeat={args.repeat}")
    runner = OpenCodeModelRunner(MODEL_ROUTE)
    builder = ExpoPromptBuilder()

    calls = 0
    rows: list[dict] = []
    for rep in range(args.repeat):
        for rec in recs:
            sha = rec["sha"] + (f"-r{rep}" if args.repeat > 1 else "")
            if not cache_key(sha, model_slug, pver).exists():
                if calls >= args.max_calls:
                    print(f"BUDGET EXHAUSTED at {calls} calls; stopping (resume later).")
                    break
                calls += 1
            row = evaluate_repeat(detector, rec, runner, builder, pver, model_slug, rep, args.repeat)
            row["rep"] = rep
            rows.append(row)
            print(f"[{row.get('cache_hit') and 'cache' or 'live'}] {rec['id']} rep={rep} -> "
                  f"{row['verdict']}/{row['severity']} ({row['validation_state']})")
    with RESULTS.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"appended {len(rows)} rows to {RESULTS} ({calls} live calls)")


def evaluate_repeat(detector, passage, runner, builder, pver, model_slug, rep, nrep):
    sha = passage["sha"] + (f"-r{rep}" if nrep > 1 else "")
    key = cache_key(sha, model_slug, pver)
    if key.exists():
        cached = json.loads(key.read_text(encoding="utf-8"))
        # Same text evaluated once: relabel to the requesting passage id so
        # byte-identical samples (e.g. revised==as-found) keep their own rows.
        cached["id"] = passage["id"]
        cached["cache_hit"] = True
        return cached
    context = ArtifactAnalysisContext.from_text(passage["text"], passage["id"], "technical")
    exec_ctx = ArtifactDetectionExecutionContext(
        profile="technical", execution_mode="llm", model_runner=runner,
        prompt_builder=builder, llm_model_name=MODEL_ROUTE, llm_temperature=0.0,
        llm_max_tokens=1200,
        metadata={"passage_ref": f"{passage['id']} {passage['source']} L{passage['start_line']}-{passage['end_line']}"},
    )
    det_result = detector.run(context, execution_context=exec_ctx)
    provider_error = det_result.metrics.get("error")
    issues = det_result.issues
    if provider_error and not issues:
        verdict = {
            "verdict": "NOT_RUN", "severity": "NONE", "confidence": None,
            "main_explanation": "", "diagnosis": f"provider error: {provider_error}",
            "quote": "", "validation_state": "PROVIDER_ERROR", "model": MODEL_ROUTE,
        }
    if issues:
        i = issues[0]
        verdict = {
            "verdict": i.stats.get("subtype", "MIXED"), "severity": i.severity,
            "confidence": i.stats.get("confidence"), "main_explanation": i.stats.get("main_explanation", ""),
            "diagnosis": i.why_fix, "quote": (i.evidence or [""])[0],
            "validation_state": i.stats.get("validation_state"), "model": i.stats.get("model"),
        }
    elif provider_error:
        pass  # verdict already set to NOT_RUN/PROVIDER_ERROR above
    else:
        verdict = {
            "verdict": "NO_ISSUE", "severity": "NONE", "confidence": None,
            "main_explanation": "", "diagnosis": det_result.metrics.get("validation_state", "SEMANTICALLY_REJECTED"),
            "quote": "", "validation_state": det_result.metrics.get("validation_state"), "model": MODEL_ROUTE,
        }
    record = {"id": passage["id"], "sha": passage["sha"], "detector_version": DETECTOR_VERSION,
              "prompt_version": pver, "requested_model": MODEL_ROUTE,
              "actual_model": (runner.last_telemetry.get("actual_model") or MODEL_ROUTE),
              "route_resolution": runner.last_telemetry.get("route_resolution"),
              "transport": runner.last_telemetry.get("transport"),
              "latency_s": runner.last_telemetry.get("latency_s"),
              "usage": runner.last_telemetry.get("usage"),
              "provider_status": runner.last_telemetry.get("status"),
              "provider_error": runner.last_telemetry.get("error"),
              "status": "provider_error" if provider_error else "ok",
              "score": det_result.score, **verdict,
              # Stage B: the actual model response is preserved verbatim as
              # evidence (analysis reads this, never the parsed verdict alone).
              "raw_response": runner.last_raw_response}
    key.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    record["cache_hit"] = False
    return record


if __name__ == "__main__":
    main()
