"""Versioned workflow templates for bounded experiments."""

from __future__ import annotations

from dataclasses import dataclass, field


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
}


def get_template(template_id: str) -> TemplateSpec:
    try:
        return TEMPLATES[template_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported workflow template: {template_id}") from exc
