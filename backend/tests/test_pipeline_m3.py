"""M3 governed execution tests (MC-BOOK-PIPELINE-01).

Hermetic: tmp registry, tmp manuscripts, fake Writer CLI (monkeypatched
run_tool). The live pilot (real writer.exe, isolated fixture) is recorded in
the M3 report; these tests pin the contracts the pilot relies on:
deterministic argv, strict receipt parsing, approval + duplicate guards, and
the rule that a receipt never implies current-ness.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from mission_control.adapters.base import ActionContext
from mission_control.adapters.writer import (
    MRI_OBSERVE_RECEIPT_SCHEMA,
    WriterAdapter,
    _mri_observe_argv,
    _validate_mri_observe_chapter,
)
from mission_control.integrations.runner import CommandResult
from mission_control.models import Application
from mission_control.publication import pipeline as pipe


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def pilot_book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    repo = tmp_path / "pilotbook"
    chapters = repo / "content"
    chapters.mkdir(parents=True)
    (chapters / "01-chapter.md").write_text("# Pilot\n\nDeterministic text.\n", encoding="utf-8")
    metadata = repo / "metadata"
    metadata.mkdir(parents=True)
    (metadata / "01-chapter.yaml").write_text("title: Pilot\n", encoding="utf-8")
    out = repo / "out"
    out.mkdir(parents=True)
    registry = {
        "projects": {
            "pilot": {
                "project_root": repo.as_posix(),
                "active": True,
                "tags": ["book"],
                "profile": "technical",
                "chapters": {"path": "content", "pattern": "*.md"},
                "metadata": {"path": "metadata", "pattern": "*.yaml"},
                "book": {"manuscript": "pilot.md", "publication_status": "research"},
                "validation": {"enabled": False, "checks": []},
            }
        }
    }
    registry_path = tmp_path / "projects.yaml"
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    monkeypatch.setenv("MISSION_CONTROL_WRITER_REGISTRY", str(registry_path))
    return {"repo": repo, "chapters": chapters, "out": out}


def _params(pilot_book: dict, **overrides) -> dict:
    payload = {
        "chapter_file": str(pilot_book["chapters"] / "01-chapter.md"),
        "metadata_file": str(pilot_book["repo"] / "metadata" / "01-chapter.yaml"),
        "output_dir": str(pilot_book["out"]),
        "profile": "technical",
    }
    payload.update(overrides)
    return payload


def _context(tmp_path: Path) -> ActionContext:
    repo = tmp_path / "writer-checkout"
    repo.mkdir(exist_ok=True)
    return ActionContext(
        application_id="writer",
        data_dir=tmp_path / "data",
        application_repository_path=str(repo),
        config={},
    )


# --- validation ---------------------------------------------------------------


def test_validate_accepts_well_formed_parameters(pilot_book: dict):
    _validate_mri_observe_chapter(_params(pilot_book))


def test_validate_rejects_unsafe_or_missing_inputs(pilot_book: dict, tmp_path: Path):
    with pytest.raises(ValueError):
        _validate_mri_observe_chapter(_params(pilot_book, chapter_file="relative.md"))
    with pytest.raises(ValueError):
        _validate_mri_observe_chapter(_params(pilot_book, chapter_file=str(tmp_path / "nope.md")))
    with pytest.raises(ValueError):
        _validate_mri_observe_chapter(
            _params(pilot_book, chapter_file=str(pilot_book["chapters"] / "01-chapter.txt"))
        )
    with pytest.raises(ValueError):
        _validate_mri_observe_chapter(_params(pilot_book, output_dir=str(tmp_path / "missing-dir")))
    with pytest.raises(ValueError):
        _validate_mri_observe_chapter(_params(pilot_book, profile="horror"))
    with pytest.raises(ValueError):
        _validate_mri_observe_chapter(
            _params(pilot_book, metadata_file=str(tmp_path / "absent.yaml"))
        )


# --- deterministic argv (zero-model construction) ------------------------------


def test_argv_pins_deterministic_flags_and_nothing_else(pilot_book: dict):
    argv = _mri_observe_argv(
        str(pilot_book["chapters"] / "01-chapter.md"),
        str(pilot_book["out"]),
        "technical",
        str(pilot_book["repo"] / "metadata" / "01-chapter.yaml"),
    )
    assert argv[:3] == ["mri", "chapter", str(pilot_book["chapters"] / "01-chapter.md")]
    for flag, value in (
        ("--observer", "deterministic"),
        ("--quality-model", "none"),
        ("--semantic-model", "none"),
        ("--beat-mode", "deterministic"),
    ):
        assert flag in argv and argv[argv.index(flag) + 1] == value
    joined = " ".join(argv)
    for banned in ("auto", "provider", "llm", "embedding", "hybrid", "openai", "Muse"):
        assert banned not in joined
    assert "--repair" not in argv and "--apply" not in argv


# --- strict receipt parsing -----------------------------------------------------


def _payload(snapshot: str, out: Path, status: str = "succeeded") -> dict:
    return {
        "status": status,
        "markdown_path": str(out / "01-chapter.mri.md"),
        "json_path": str(out / "01-chapter.mri.json"),
        "report": {
            "target_id": "01-chapter",
            "snapshot_hash": snapshot,
            "observation": {},
            "alignment": {},
            "provenance": {
                "observer_mode": "deterministic",
                "observer_model": None,
                "quality_model": "none",
                "beat_mode": None,
                "semantic_model": None,
                "embed_runtime_used": True,
                "fallback_used": True,
                "alignment_version": "v1",
                "observer_prompt_version": "p1",
                "generated_at": "2026-01-03T00:00:00Z",
                "warnings": ["deterministic_section_observer"],
            },
        },
    }


def test_parse_accepts_complete_success_receipt(pilot_book: dict):
    out = pilot_book["out"]
    live = (pilot_book["chapters"] / "01-chapter.md").read_text(encoding="utf-8")
    (out / "01-chapter.mri.json").write_text("{}", encoding="utf-8")
    action_result = WriterAdapter._parse_mri_observe_result(
        json.dumps(_payload(_sha_text(live), out)),
        "",
        0,
        chapter_file=str(pilot_book["chapters"] / "01-chapter.md"),
        output_dir=str(out),
    )
    assert action_result.status == "succeeded"
    assert action_result.result["schema_version"] == MRI_OBSERVE_RECEIPT_SCHEMA
    assert action_result.result["status"] == "succeeded"
    assert action_result.result["clean"] is True
    assert action_result.result["receipt_digest_match"] is True
    assert action_result.result["provenance"]["quality_model"] == "none"
    assert action_result.artifact_ref == str(out / "01-chapter.mri.json")


def test_parse_accepts_succeeded_with_warnings_and_preserves_them(pilot_book: dict):
    out = pilot_book["out"]
    live = (pilot_book["chapters"] / "01-chapter.md").read_text(encoding="utf-8")
    (out / "01-chapter.mri.json").write_text("{}", encoding="utf-8")
    payload = _payload(_sha_text(live), out, status="succeeded_with_warnings")
    action_result = WriterAdapter._parse_mri_observe_result(
        json.dumps(payload),
        "",
        0,
        chapter_file=str(pilot_book["chapters"] / "01-chapter.md"),
        output_dir=str(out),
    )
    assert action_result.status == "succeeded"
    assert action_result.result["status"] == "succeeded_with_warnings"
    assert action_result.result["clean"] is False
    assert action_result.result["warnings"] == ["deterministic_section_observer"]
    assert "Warnings preserved" in action_result.output


def test_parse_rejects_everything_else(pilot_book: dict):
    out = pilot_book["out"]
    chapter = str(pilot_book["chapters"] / "01-chapter.md")
    (out / "01-chapter.mri.json").write_text("{}", encoding="utf-8")
    live = (pilot_book["chapters"] / "01-chapter.md").read_text(encoding="utf-8")
    good = json.dumps(_payload(_sha_text(live), out))
    assert (
        WriterAdapter._parse_mri_observe_result(
            "not json", "", 0, chapter_file=chapter, output_dir=str(out)
        ).status
        == "failed"
    )
    assert (
        WriterAdapter._parse_mri_observe_result(
            good, "boom", 1, chapter_file=chapter, output_dir=str(out)
        ).status
        == "failed"
    )
    incomplete = json.dumps(_payload(_sha_text(live), out, status="METADATA_UNAVAILABLE"))
    assert (
        WriterAdapter._parse_mri_observe_result(
            incomplete, "", 0, chapter_file=chapter, output_dir=str(out)
        ).status
        == "failed"
    )
    no_snapshot = _payload("", out)
    no_snapshot["report"].pop("snapshot_hash")
    assert (
        WriterAdapter._parse_mri_observe_result(
            json.dumps(no_snapshot), "", 0, chapter_file=chapter, output_dir=str(out)
        ).status
        == "failed"
    )
    (out / "01-chapter.mri.json").unlink()
    assert (
        WriterAdapter._parse_mri_observe_result(
            good, "", 0, chapter_file=chapter, output_dir=str(out)
        ).status
        == "failed"
    )


# --- adapter execution with a fake Writer CLI ------------------------------------


def _fake_writer(payload: dict, hold: asyncio.Event | None = None):
    async def fake_run_tool(executable, arguments, **kwargs):
        assert arguments[:2] == ["mri", "chapter"]
        assert "--observer" in arguments
        if hold is not None:
            await hold.wait()
        return CommandResult(
            exit_code=0,
            stdout=json.dumps(payload),
            stderr="",
            duration_seconds=0.01,
            executable=executable,
        )

    return fake_run_tool


def test_execute_records_receipt_without_claiming_current(
    pilot_book: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import mission_control.adapters.writer as writer_module

    out = pilot_book["out"]
    live = (pilot_book["chapters"] / "01-chapter.md").read_text(encoding="utf-8")
    (out / "01-chapter.mri.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(writer_module, "run_tool", _fake_writer(_payload(_sha_text(live), out)))
    action_result = asyncio.run(
        WriterAdapter().execute_action(
            "mri_observe_chapter", _params(pilot_book), _context(tmp_path)
        )
    )
    assert action_result.status == "succeeded"
    assert action_result.artifact_ref == str(out / "01-chapter.mri.json")
    # The receipt alone changes nothing: the projection still sees no Writer
    # report in the fixture output dir (the fake wrote none).
    (out / "01-chapter.mri.json").unlink()
    detail = pipe.get_stage_detail(None, None, "pilot", "mri")
    assert detail is not None
    assert detail["cells"][0]["has_evidence"] is False


def test_execute_failure_when_tool_raises(
    pilot_book: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import mission_control.adapters.writer as writer_module

    async def boom(executable, arguments, **kwargs):
        raise OSError("writer exploded")

    monkeypatch.setattr(writer_module, "run_tool", boom)
    action_result = asyncio.run(
        WriterAdapter().execute_action(
            "mri_observe_chapter", _params(pilot_book), _context(tmp_path)
        )
    )
    assert action_result.status == "failed"
    assert "writer exploded" in (action_result.error or "")


# --- durable lifecycle through the real integration service -----------------------


def _ensure_writer_app(client: TestClient, tmp_path: Path) -> None:
    with client.app.state.database.session() as session:
        app = session.get(Application, "writer")
        repo = tmp_path / "writer-checkout"
        repo.mkdir(exist_ok=True)
        if app is None:
            session.add(
                Application(
                    id="writer",
                    name="Writer",
                    description="Writer",
                    category="supporting",
                    enabled=True,
                    archived=False,
                    pinned=False,
                    display_order=100,
                    repository_path=str(repo),
                    integration_adapter="writer",
                    adapter_enabled=True,
                    adapter_config={},
                )
            )
        else:
            app.adapter_enabled = True
            app.integration_adapter = "writer"
            app.repository_path = str(repo)
        session.flush()


def test_governed_lifecycle_approval_duplicate_and_receipt(
    client: TestClient, pilot_book: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import mission_control.adapters.writer as writer_module

    _ensure_writer_app(client, tmp_path)
    out = pilot_book["out"]
    live = (pilot_book["chapters"] / "01-chapter.md").read_text(encoding="utf-8")
    (out / "01-chapter.mri.json").write_text("{}", encoding="utf-8")
    hold = asyncio.Event()
    monkeypatch.setattr(
        writer_module, "run_tool", _fake_writer(_payload(_sha_text(live), out), hold)
    )
    params = _params(pilot_book)
    denied = client.post(
        "/api/integrations/writer/actions/mri_observe_chapter/execute",
        json={"parameters": params, "confirm": False},
    )
    assert denied.status_code == 409
    started = client.post(
        "/api/integrations/writer/actions/mri_observe_chapter/execute",
        json={"parameters": params, "confirm": True},
    )
    assert started.status_code == 200, started.text
    execution_id = started.json()["id"]
    duplicate = client.post(
        "/api/integrations/writer/actions/mri_observe_chapter/execute",
        json={"parameters": params, "confirm": True},
    )
    assert duplicate.status_code == 409
    hold.set()
    import time as _time

    deadline = _time.time() + 15
    execution = started.json()
    while _time.time() < deadline:
        execution = client.get(f"/api/integrations/executions/{execution_id}").json()
        if execution["status"] not in {"queued", "running"}:
            break
        _time.sleep(0.1)
    assert execution["status"] == "succeeded", execution
    assert execution["approved_at"]
    assert execution["artifact_ref"] == str(out / "01-chapter.mri.json")
    assert execution["result"]["schema_version"] == MRI_OBSERVE_RECEIPT_SCHEMA
    assert execution["result"]["provenance"]["observer_mode"] == "deterministic"


# --- projection still owns current-ness --------------------------------------------


def test_receipt_does_not_imply_current_but_matching_artifact_does(pilot_book: dict):
    detail = pipe.get_stage_detail(None, None, "pilot", "mri")
    assert detail is not None
    assert detail["cells"][0]["has_evidence"] is False
    # Simulate Writer's real output: a digest-matching stored report in the
    # Writer-owned location the projection reads.
    writer_dir = pilot_book["repo"] / ".writer" / "mri" / "pilot"
    writer_dir.mkdir(parents=True, exist_ok=True)
    live = (pilot_book["chapters"] / "01-chapter.md").read_text(encoding="utf-8")
    (writer_dir / "01-chapter.mri.json").write_text(
        json.dumps(
            {
                "target_id": "01-chapter",
                "snapshot_hash": _sha_text(live),
                "observation": {},
                "alignment": {},
                "provenance": {
                    "observer_mode": "deterministic",
                    "quality_model": "none",
                    "stage_status": {
                        "observer": "pass",
                        "quality": "skipped",
                        "sections": "ok",
                        "alignment": "pass",
                    },
                    "generated_at": "2026-01-03T00:00:00Z",
                },
            }
        ),
        encoding="utf-8",
    )
    rerun = pipe.get_stage_detail(None, None, "pilot", "mri")
    assert rerun is not None
    assert (rerun["cells"][0]["result"], rerun["cells"][0]["freshness"]) == ("passed", "current")


def test_skipped_quality_stage_is_neutral_not_failed(pilot_book: dict):
    writer_dir = pilot_book["repo"] / ".writer" / "mri" / "pilot"
    writer_dir.mkdir(parents=True, exist_ok=True)
    (writer_dir / "01-chapter.mri.json").write_text(
        json.dumps(
            {
                "target_id": "01-chapter",
                "snapshot_hash": "different",
                "observation": {},
                "alignment": {},
                "provenance": {
                    "stage_status": {
                        "observer": "pass",
                        "quality": "skipped",
                        "sections": "ok",
                        "alignment": "pass",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    detail = pipe.get_stage_detail(None, None, "pilot", "mri")
    assert detail is not None
    # Stale source, but the completed deterministic analysis still reads passed.
    assert (detail["cells"][0]["result"], detail["cells"][0]["freshness"]) == ("passed", "stale")
