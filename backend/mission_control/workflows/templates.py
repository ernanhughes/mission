"""Versioned workflow templates for bounded experiments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TemplateSpec:
    id: str
    version: str
    title: str
    source_kind: str
    source_contract: str
    sandbox_relative: str
    scope: tuple[str, ...]
    entrypoint: str
    tests_path: str
    measure_command: tuple[str, ...]
    success_key: str
    expected_result: str
    worker_algorithm: tuple[str, ...]
    test_command: tuple[str, ...] | None = None
    required_functions: tuple[str, ...] = ()
    worker_parameters: dict[str, Any] = field(default_factory=dict)
    allow_read_only_open: bool = False
    baseline_tag: str = "mc11-baseline"
    stop_conditions: tuple[str, ...] = field(
        default_factory=lambda: (
            "Worker is unavailable or blocked",
            "The patch changes a path outside the approved scope",
            "Generated Python is invalid or uses forbidden operations",
            "Deterministic tests fail",
            "The expected result is not met",
            "CoCoder reports a high or medium finding",
            "The approved scope or baseline becomes stale",
            "Cancellation is requested",
        )
    )
    evaluation_criteria: tuple[str, ...] = field(
        default_factory=lambda: (
            "pytest passes in the sandbox",
            "The measurement target is met",
            "git diff contains exactly the approved scope",
            "CoCoder reviews the exact result commit",
        )
    )


TEMPLATES: dict[str, TemplateSpec] = {
    "trace_reduce_v1": TemplateSpec(
        id="trace_reduce_v1",
        version="1.0",
        title="TraceLite trace-reduction proxy",
        source_kind="next_export",
        source_contract="next-research-export-v1",
        sandbox_relative="experiments/tracelite-spike",
        scope=("tracelite/reduce.py",),
        entrypoint="reduce_trace",
        tests_path="tests/test_reduce.py",
        measure_command=("python", "scripts/measure.py"),
        success_key="meets_reduction_target",
        expected_result=(
            "All sandbox tests pass and the duplicate-heavy fixture is reduced "
            "from 21 events to 3 events."
        ),
        worker_algorithm=(
            "start with an empty result list",
            "iterate over every event in order",
            "append the event only when the result is empty or the event differs from the last result item",
            "return the result list",
            "do not append the last event a second time",
        ),
        baseline_tag="mc10-baseline",
    ),
    "brightness_observation_v1": TemplateSpec(
        id="brightness_observation_v1",
        version="1.0",
        title="Brightness progression fixture",
        source_kind="fixture_manifest",
        source_contract="mc11.fixture-evidence.v1",
        sandbox_relative="experiments/brightness-fixture",
        scope=("brightness/analyze.py",),
        entrypoint="analyze_frames",
        tests_path="tests/test_analyze.py",
        measure_command=("python", "scripts/measure.py"),
        success_key="meets_target",
        expected_result=(
            "All fixture tests pass; mean brightness is [0.0, 128.0, 255.0], "
            "max brightness is [0, 128, 255], and the progression is monotonic."
        ),
        worker_algorithm=(
            "open each file in binary read mode and read all bytes",
            "compute mean as sum(bytes)/len(bytes) as a float and max as max(bytes) as an int",
            "each fixture is a 2x2 raw grayscale frame",
            "return a list of dicts with width=2, height=2, mean and max in input order",
            "do not mutate paths or write any file",
        ),
        allow_read_only_open=True,
        baseline_tag="mc11-brightness-baseline",
    ),
    "writer_quantity_units_v1": TemplateSpec(
        id="writer_quantity_units_v1",
        version="1.0",
        title="Writer semantic-loss quantity-unit normalization",
        source_kind="local_repo",
        source_contract="mission.local-repo.v1",
        sandbox_relative="experiments/writer-semantic-loss",
        scope=(
            "packages/writer-runtime/writer_runtime/domains/artifact/"
            "artifact_engine/revision/quantity_units.py",
        ),
        entrypoint="quantity_unit_token",
        tests_path=(
            "tests/runtime/artifact/test_semantic_loss_quantity_units.py"
        ),
        measure_command=(
            "python",
            "-c",
            "import json,subprocess,sys;"
            "cmd=[sys.executable,'-m','pytest','--noconftest',"
            "'tests/runtime/artifact/test_semantic_loss_quantity_units.py',"
            "'-q','-p','no:cacheprovider'];"
            "r=subprocess.run(cmd,capture_output=True,text=True);"
            "print(json.dumps({'meets_target': r.returncode==0,"
            "'exit_code': r.returncode,"
            "'tail': (r.stdout+r.stderr)[-4000:]}));"
            "sys.exit(r.returncode)",
        ),
        test_command=(
            "python",
            "-m",
            "pytest",
            "--noconftest",
            "tests/runtime/artifact/test_semantic_loss_quantity_units.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ),
        success_key="meets_target",
        expected_result=(
            "The quantity-unit regression tests pass: plural/hyphenated units "
            "compare equal, prose words after numbers are not units, and real "
            "unit changes remain distinct."
        ),
        worker_algorithm=(
            "read the helper and the regression tests",
            "lowercase units before comparison",
            "singularize plain plural unit words such as bits, seconds, tokens, units and logits",
            "leave known short abbreviations and symbols unchanged",
            "return None for common prose words and verbs such as has, is, are, apart, and, in, matched",
            "preserve genuinely different units such as bits versus tokens",
            "do not add imports or change the public function signatures",
            "return the complete file including the module docstring, NON_UNIT_WORDS, _SINGULAR_EXCEPTIONS, normalize_quantity_unit and quantity_unit_token; do not return only one function",
        ),
        required_functions=("normalize_quantity_unit", "quantity_unit_token"),
        worker_parameters={"reasoning_effort": "low", "temperature": 0},
        baseline_tag="mission01-writer-baseline",
    ),
}


def get_template(template_id: str) -> TemplateSpec:
    try:
        return TEMPLATES[template_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported workflow template: {template_id}") from exc
