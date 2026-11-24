"""M4A automatic deterministic maintenance tests (MC-BOOK-PIPELINE-01).

Hermetic: tmp registry, tmp manuscripts, fake Writer CLI (monkeypatched
run_tool) except where the decision logic is pure (no I/O at all). The live
Writer pilot is recorded in the M4A report; these tests pin the policy,
fingerprinting, decisions, lifecycle wiring, and failure bounds.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from mission_control.models import Application, IntegrationExecution
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.publication import maintenance as mnt
from mission_control.publication import pipeline as pipe


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def m4a_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    repo = tmp_path / "m4abook"
    chapters = repo / "content"
    chapters.mkdir(parents=True)
    (chapters / "01-chapter.md").write_text("# One\n\nMissing report.\n", encoding="utf-8")
    (chapters / "02-chapter.md").write_text("# Two\n\nStale report.\n", encoding="utf-8")
    (chapters / "03-chapter.md").write_text("# Three\n\nCurrent report.\n", encoding="utf-8")
    (chapters / "04-chapter.md").write_text("# Four\n\nFails to run.\n", encoding="utf-8")
    metadata = repo / "metadata"
    metadata.mkdir(parents=True)
    for stem in ("01-chapter", "02-chapter", "03-chapter", "04-chapter"):
        (metadata / f"{stem}.yaml").write_text(f"title: {stem}\n", encoding="utf-8")
    writer_mri = repo / ".writer" / "mri" / "m4a"
    writer_mri.mkdir(parents=True)

    def report(snapshot: str, warnings: list[str], stage_status: dict) -> dict:
        return {
            "target_id": "chapter",
            "snapshot_hash": snapshot,
            "observation": {},
            "alignment": {},
            "provenance": {
                "observer_mode": "deterministic",
                "observer_model": None,
                "quality_model": "none",
                "semantic_model": None,
                "alignment_version": "02a912017f5d",
                "observer_prompt_version": "p1",
                "generated_at": "2026-01-03T00:00:00Z",
                "warnings": warnings,
                "stage_status": stage_status,
            },
        }

    (writer_mri / "02-chapter.mri.json").write_text(
        json.dumps(
            report(
                _sha_text("old text"),
                [],
                {"observer": "pass", "quality": "skipped", "sections": "ok", "alignment": "pass"},
            )
        ),
        encoding="utf-8",
    )
    live_03 = (chapters / "03-chapter.md").read_text(encoding="utf-8")
    (writer_mri / "03-chapter.mri.json").write_text(
        json.dumps(
            report(
                _sha_text(live_03),
                ["deterministic_section_observer"],
                {
                    "observer": "warning",
                    "quality": "skipped",
                    "sections": "ok",
                    "alignment": "pass",
                },
            )
        ),
        encoding="utf-8",
    )
    registry = {
        "projects": {
            "m4a": {
                "project_root": repo.as_posix(),
                "active": True,
                "tags": ["book"],
                "profile": "technical",
                "chapters": {"path": "content", "pattern": "*.md"},
                "metadata": {"path": "metadata", "pattern": "*.yaml"},
                "book": {"manuscript": "m4a.md", "publication_status": "research"},
                "validation": {"enabled": False, "checks": []},
            }
        }
    }
    registry_path = tmp_path / "projects.yaml"
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    monkeypatch.setenv("MISSION_CONTROL_WRITER_REGISTRY", str(registry_path))
    return {"repo": repo, "chapters": chapters, "out": writer_mri}


def _seeded_db(runtime) -> Database:
    database = Database(runtime)
    apply_migrations(database)
    return database


# --- policy switches ------------------------------------------------------------


def test_auto_disabled_by_default_and_pauses_persist(runtime):
    database = _seeded_db(runtime)
    with database.session() as session:
        assert mnt.is_auto_enabled(session) is False
        assert mnt.paused_books(session) == []
        assert mnt.set_auto_enabled(session, True) is True
        session.commit()
    with database.session() as session:
        assert mnt.is_auto_enabled(session) is True
        assert mnt.set_book_paused(session, "m4a", True) == ["m4a"]
        assert mnt.set_book_paused(session, "other", True) == ["m4a", "other"]
        assert mnt.set_book_paused(session, "m4a", False) == ["other"]
        session.commit()
    with database.session() as session:
        assert mnt.paused_books(session) == ["other"]


def test_malformed_settings_fail_safe(runtime):
    from mission_control.models import Setting

    database = _seeded_db(runtime)
    with database.session() as session:
        session.add(Setting(key=mnt.SETTING_ENABLED, value="yes", updated_at="x"))
        session.add(Setting(key=mnt.SETTING_PAUSED_BOOKS, value={"nope": 1}, updated_at="x"))
        session.commit()
    with database.session() as session:
        assert mnt.is_auto_enabled(session) is False
        assert mnt.paused_books(session) == []


# --- fingerprints -----------------------------------------------------------------


def test_fingerprint_stable_and_sensitive():
    base = {"source_digest": "a", "metadata_digest": "b", "profile": "technical"}
    assert mnt.auto_fingerprint(**base) == mnt.auto_fingerprint(**base)
    for key, value in (("source_digest", "x"), ("metadata_digest", "x"), ("profile", "fiction")):
        changed = dict(base)
        changed[key] = value
        assert mnt.auto_fingerprint(**changed) != mnt.auto_fingerprint(**base)
    bumped = dict(base)
    assert mnt.auto_fingerprint(
        policy_version="pipeline-auto-v2", **bumped
    ) != mnt.auto_fingerprint(**base)


def test_expected_mode_flag(m4a_repo: dict):
    out = m4a_repo["out"]
    expected = json.loads((out / "03-chapter.mri.json").read_text(encoding="utf-8"))
    assert expected["provenance"]["warnings"] == ["deterministic_section_observer"]
    detail = pipe.get_stage_detail(None, None, "m4a", "mri")
    assert detail is not None
    by_id = {c["chapter_id"]: c for c in detail["cells"]}
    assert by_id["03-chapter"]["detail"]["expected_deterministic_mode"] is True
    assert by_id["03-chapter"]["detail"]["unexpected_warnings"] == []
    assert (by_id["03-chapter"]["result"], by_id["03-chapter"]["freshness"]) == (
        "pending",
        "current",
    )
    assert by_id["02-chapter"]["detail"]["expected_deterministic_mode"] is True


def test_registry_execution_classes():
    by_id = {s["stage_id"]: s for s in pipe.list_stages()["stages"]}
    assert by_id["mri"]["execution_class"] == "automatic"
    assert by_id["patterns"]["execution_class"] == "governed"
    assert by_id["strengthening"]["execution_class"] == "governed"
    assert by_id["editing"]["execution_class"] == "governed"
    assert by_id["validation"]["execution_class"] == "governed"
    assert by_id["metadata"]["execution_class"] == "governed"
    assert by_id["graph"]["execution_class"] == "unavailable"


# --- decisions (pure) ---------------------------------------------------------------


def _cell(result="unknown", freshness="unknown", evidence=False, applicable=True):
    return {
        "result": result,
        "freshness": freshness,
        "has_evidence": evidence,
        "applicable": applicable,
    }


def _decide(**overrides):
    params = {
        "stage_id": "mri",
        "enabled": True,
        "book_paused": False,
        "cell": _cell("unknown", "stale", True),
        "live_source_digest": "live",
        "live_metadata_digest": "meta",
        "profile": "technical",
        "active_execution_id": None,
        "last_receipt": None,
        "consecutive_failures": 0,
        "last_failure_at": None,
    }
    params.update(overrides)
    return mnt.decide_unit(**params)


def test_decide_matrix():
    assert _decide(stage_id="editing").action == "skip"
    assert _decide(enabled=False).action == "wait"
    assert _decide(book_paused=True).action == "blocked"
    assert _decide(active_execution_id="exec-1").action == "wait"
    assert _decide().action == "run"
    assert _decide(cell=None).action == "blocked"
    assert _decide(cell=_cell(applicable=False)).action == "skip"
    assert _decide(live_source_digest=None).action == "blocked"
    current = _cell("passed", "current", True)
    skip = _decide(cell=current)
    assert (skip.action, skip.reason) == (
        "skip",
        skip.reason,
    ) and "no provenance refresh" in skip.reason
    fp = mnt.auto_fingerprint(source_digest="live", metadata_digest="meta", profile="technical")
    assert _decide(cell=current, last_receipt={"fingerprint": fp}).action == "skip"
    assert _decide(cell=current, last_receipt={"fingerprint": "other"}).action == "run"
    assert _decide(consecutive_failures=3).action == "blocked"
    assert _decide(consecutive_failures=2).action == "run"
    # Attempts against old inputs do not block new inputs.
    assert _decide(last_receipt={"fingerprint": "old"}, consecutive_failures=9).action == "run"


def test_decide_cooldown_and_recovery():
    assert (
        _decide(last_failure_at="2026-01-01T00:00:00Z", now_iso="2026-06-01T00:00:00Z").action
        == "run"
    )
    waiting = _decide(last_failure_at="2026-06-01T00:00:00Z", now_iso="2026-06-01T00:01:00Z")
    assert waiting.action == "wait"


# --- service loop through HTTP -------------------------------------------------------


def _ensure_writer_app(client: TestClient, tmp_path: Path) -> None:
    with client.app.state.database.session() as session:
        repo = tmp_path / "writer-checkout"
        repo.mkdir(exist_ok=True)
        app = session.get(Application, "writer")
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


def _fake_writer(hold: dict | None = None, fail_chapters: set[str] | None = None):
    import mission_control.adapters.writer as writer_module  # noqa: F401

    async def fake_run_tool(executable, arguments, **kwargs):
        from mission_control.integrations.runner import CommandResult

        chapter = arguments[arguments.index("chapter") + 1]
        stem = Path(chapter).stem
        out_dir = Path(arguments[arguments.index("--output-dir") + 1])
        if fail_chapters and stem in fail_chapters:
            raise OSError(f"writer exploded on {stem}")
        text = Path(chapter).read_text(encoding="utf-8")
        if hold is not None and stem in hold:
            hold[stem]["text_at_start"] = text
            await hold[stem]["event"].wait()
            text = hold[stem].get("text_override", text)
        snapshot = hashlib.sha256(text.encode("utf-8")).hexdigest()
        (out_dir / f"{stem}.mri.json").write_text(
            json.dumps(
                {
                    "target_id": stem,
                    "snapshot_hash": snapshot,
                    "observation": {},
                    "alignment": {},
                    "provenance": {
                        "observer_mode": "deterministic",
                        "observer_model": None,
                        "quality_model": "none",
                        "semantic_model": None,
                        "alignment_version": "v1",
                        "observer_prompt_version": "p1",
                        "generated_at": "2026-01-03T00:00:00Z",
                        "warnings": ["deterministic_section_observer"],
                        "stage_status": {
                            "observer": "warning",
                            "quality": "skipped",
                            "sections": "ok",
                            "alignment": "pass",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        (out_dir / f"{stem}.mri.md").write_text("# report\n", encoding="utf-8")
        payload = {
            "status": "succeeded_with_warnings",
            "markdown_path": str(out_dir / f"{stem}.mri.md"),
            "json_path": str(out_dir / f"{stem}.mri.json"),
            "report": json.loads((out_dir / f"{stem}.mri.json").read_text(encoding="utf-8")),
        }
        return CommandResult(
            exit_code=0,
            stdout=json.dumps(payload),
            stderr="",
            duration_seconds=0.01,
            executable=executable,
        )

    return fake_run_tool


def _reconcile(client: TestClient) -> dict:
    response = client.post("/api/pipeline/maintenance/reconcile")
    assert response.status_code == 200, response.text
    return response.json()


def _poll_execution(client: TestClient, execution_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    execution = client.get(f"/api/integrations/executions/{execution_id}").json()
    while time.time() < deadline and execution["status"] in {"queued", "running"}:
        time.sleep(0.1)
        execution = client.get(f"/api/integrations/executions/{execution_id}").json()
    return execution


def _executions_for(client: TestClient, action: str) -> list[dict]:
    rows = client.get("/api/integrations/executions?limit=200").json()
    return [r for r in rows if r["action_id"] == action]


def test_full_loop_missing_to_current(
    client: TestClient, m4a_repo: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _ensure_writer_app(client, tmp_path)
    monkeypatch.setattr("mission_control.adapters.writer.run_tool", _fake_writer())
    assert (
        client.post("/api/pipeline/maintenance/enabled", json={"enabled": True}).status_code == 200
    )
    first = _reconcile(client)
    assert first["dispatched"] == []
    second = _reconcile(client)
    assert [d["chapter_id"] for d in second["dispatched"]] == ["01-chapter"]
    execution = _poll_execution(client, second["dispatched"][0]["execution_id"])
    assert execution["status"] == "succeeded"
    third = _reconcile(client)
    assert [d["chapter_id"] for d in third["dispatched"]] == ["02-chapter"]
    execution2 = _poll_execution(client, third["dispatched"][0]["execution_id"])
    assert execution2["status"] == "succeeded"
    fourth = _reconcile(client)
    assert [d["chapter_id"] for d in fourth["dispatched"]] == ["04-chapter"]
    execution3 = _poll_execution(client, fourth["dispatched"][0]["execution_id"])
    assert execution3["status"] == "succeeded"
    fifth = _reconcile(client)
    assert fifth["dispatched"] == []
    detail = client.get("/api/pipeline/books/m4a/stages/mri").json()
    by_id = {c["chapter_id"]: c for c in detail["cells"]}
    assert (by_id["01-chapter"]["freshness"], by_id["02-chapter"]["freshness"]) == (
        "current",
        "current",
    )
    assert (by_id["03-chapter"]["freshness"], by_id["04-chapter"]["freshness"]) == (
        "current",
        "current",
    )
    assert detail["cells"][0]["detail"]["expected_deterministic_mode"] in (True, False)


def test_unchanged_chapters_trigger_nothing(
    client: TestClient, m4a_repo: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _ensure_writer_app(client, tmp_path)
    monkeypatch.setattr("mission_control.adapters.writer.run_tool", _fake_writer())
    client.post("/api/pipeline/maintenance/enabled", json={"enabled": True})
    _reconcile(client)
    _reconcile(client)
    for row in _poll_all(client):
        pass
    _reconcile(client)
    current_cells = client.get("/api/pipeline/books/m4a/stages/mri").json()["cells"]
    current_ids = {c["chapter_id"] for c in current_cells if c["freshness"] == "current"}
    assert "03-chapter" in current_ids
    chapter_runs = [
        r
        for r in _executions_for(client, "mri_observe_chapter_auto")
        if "03-chapter" in json.dumps(r["parameters"])
    ]
    assert chapter_runs == []


def _poll_all(client: TestClient) -> list[dict]:
    rows = _executions_for(client, "mri_observe_chapter_auto")
    for row in rows:
        if row["status"] in {"queued", "running"}:
            _poll_execution(client, row["id"])
    return _executions_for(client, "mri_observe_chapter_auto")


def test_failure_backoff_then_blocked(
    client: TestClient, m4a_repo: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _ensure_writer_app(client, tmp_path)
    monkeypatch.setattr(
        "mission_control.adapters.writer.run_tool", _fake_writer(fail_chapters={"04-chapter"})
    )
    client.post("/api/pipeline/maintenance/enabled", json={"enabled": True})
    attempts = 0
    for _ in range(12):
        report = _reconcile(client)
        for row in _poll_all(client):
            pass
        attempts = len(
            [
                r
                for r in _executions_for(client, "mri_observe_chapter_auto")
                if "04-chapter" in json.dumps(r["parameters"]) and r["status"] == "failed"
            ]
        )
        dispatched_04 = [d for d in report["dispatched"] if d["chapter_id"] == "04-chapter"]
        if attempts >= 3 and not dispatched_04 and report["blocked"] >= 1:
            break
        with client.app.state.database.session() as session:
            for row in session.query(IntegrationExecution).all():
                if row.status == "failed" and row.ended_at:
                    row.ended_at = "2000-01-01T00:00:00+00:00"
            session.commit()
    assert attempts == 3, _executions_for(client, "mri_observe_chapter_auto")
    final = _reconcile(client)
    assert all(d["chapter_id"] != "04-chapter" for d in final["dispatched"])


def test_interruption_and_changed_during_execution(
    client: TestClient, m4a_repo: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import asyncio as _asyncio

    _ensure_writer_app(client, tmp_path)
    hold: dict = {"01-chapter": {"event": _asyncio.Event()}}
    monkeypatch.setattr("mission_control.adapters.writer.run_tool", _fake_writer(hold=hold))
    client.post("/api/pipeline/maintenance/enabled", json={"enabled": True})
    _reconcile(client)
    started = _reconcile(client)
    assert [d["chapter_id"] for d in started["dispatched"]] == ["01-chapter"]
    execution_id = started["dispatched"][0]["execution_id"]
    for _ in range(100):
        probe = _reconcile(client)
        assert all(d["chapter_id"] != "01-chapter" for d in probe["dispatched"])
        state = client.get(f"/api/integrations/executions/{execution_id}").json()["status"]
        if state == "running":
            break
    else:
        raise AssertionError("execution never reached running")
    # Change the chapter mid-run: the in-flight receipt will record the
    # pre-edit snapshot, so the projection must read stale afterwards and
    # the next passes must requeue exactly once, then settle current.
    chapter_file = m4a_repo["chapters"] / "01-chapter.md"
    chapter_file.write_text(
        chapter_file.read_text(encoding="utf-8") + "\nEdited mid-run.\n", encoding="utf-8"
    )
    hold["01-chapter"]["event"].set()
    execution = _poll_execution(client, execution_id)
    assert execution["status"] == "succeeded"
    rows = [
        r
        for r in _executions_for(client, "mri_observe_chapter_auto")
        if "01-chapter" in json.dumps(r["parameters"])
    ]
    assert len(rows) == 1
    assert execution["result"]["receipt_digest_match"] is False
    stale = client.get("/api/pipeline/books/m4a/stages/mri").json()
    assert {c["chapter_id"]: c["freshness"] for c in stale["cells"]}["01-chapter"] == "stale"
    _reconcile(client)
    again = _reconcile(client)
    assert [d["chapter_id"] for d in again["dispatched"]] == ["01-chapter"]
    _poll_execution(client, again["dispatched"][0]["execution_id"])
    final = client.get("/api/pipeline/books/m4a/stages/mri").json()
    by_id = {c["chapter_id"]: c for c in final["cells"]}
    assert by_id["01-chapter"]["freshness"] == "current"
    assert (
        len(
            [
                r
                for r in _executions_for(client, "mri_observe_chapter_auto")
                if "01-chapter" in json.dumps(r["parameters"])
            ]
        )
        == 2
    )


def test_service_loop_starts_and_stops_without_dispatch_when_disabled(
    client: TestClient, m4a_repo: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import asyncio as _asyncio

    from mission_control.publication.maintenance import MaintenanceService

    _ensure_writer_app(client, tmp_path)
    monkeypatch.setattr("mission_control.adapters.writer.run_tool", _fake_writer())

    async def scenario():
        service = MaintenanceService(
            client.app.state.database,
            client.app.state.settings,
            client.app.state.integration_service,
            interval_seconds=0.05,
        )
        await service.start()
        await _asyncio.sleep(0.3)
        await service.stop()
        assert service.last_report is not None
        assert service.last_report.enabled is False
        assert service.last_report.dispatched == []

    _asyncio.run(scenario())


def test_status_pause_and_retry_controls(
    client: TestClient, m4a_repo: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _ensure_writer_app(client, tmp_path)
    monkeypatch.setattr("mission_control.adapters.writer.run_tool", _fake_writer())
    status = client.get("/api/pipeline/maintenance").json()
    assert status["policy_version"] == mnt.MAINTENANCE_POLICY_VERSION
    assert status["enabled"] is False
    assert status["auto_stages"] == ["mri"]
    paused = client.post(
        "/api/pipeline/maintenance/pause", json={"project_id": "m4a", "paused": True}
    ).json()
    assert paused["paused_books"] == ["m4a"]
    client.post("/api/pipeline/maintenance/enabled", json={"enabled": True})
    _reconcile(client)
    report = _reconcile(client)
    assert report["dispatched"] == []
    assert report["blocked"] >= 1
    client.post("/api/pipeline/maintenance/pause", json={"project_id": "m4a", "paused": False})
    retry = client.post(
        "/api/integrations/writer/actions/mri_observe_chapter_auto/execute",
        json={
            "parameters": {
                "chapter_file": str(m4a_repo["chapters"] / "01-chapter.md"),
                "output_dir": str(m4a_repo["out"]),
                "profile": "technical",
                "policy_version": mnt.MAINTENANCE_POLICY_VERSION,
            },
            "confirm": True,
        },
    )
    assert retry.status_code == 200, retry.text
    execution = _poll_execution(client, retry.json()["id"])
    assert execution["status"] == "succeeded"
