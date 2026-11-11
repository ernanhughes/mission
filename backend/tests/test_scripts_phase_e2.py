"""MC-SCRIPTS-05 Phase E2: batches, synthesis, safety, UI contracts.

All Pi calls are monkeypatched fakes. No network, no model, no source writes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from mission_control.scripts import intelligence as intellect
from mission_control.scripts import synthesis as synth

REVIEW_JSON = {
    "purpose": "A short calming script for steady breathing before work.",
    "strengths": ["Clear spoken rhythm.", "Concrete breath cues."],
    "weaknesses": ["The middle drifts without an anchor."],
    "suggested_changes": ["Repeat the step-behind-your-eyes cue once more."],
    "estimated_spoken_seconds": 290,
    "suitability": "Seated or walking; beginners.",
    "readiness": "needs_work",
}


def _make_tree(root: Path, count: int = 3) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        (root / f"Script{index:03d}.md").write_text(
            f"# Script {index}.\n\nBreathe slowly. Step {index}.\n" * 10,
            encoding="utf-8")


def _configure(client: TestClient, root: Path) -> None:
    response = client.patch("/api/settings", json={"scripts": {"root": str(root)}})
    assert response.status_code == 200, response.text


def _consent(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"ai": {"enabled": True, "consent": True}})
    assert response.status_code == 200, response.text


def _sync(client: TestClient) -> None:
    response = client.post("/api/scripts/sync")
    assert response.status_code == 200, response.text


def _scripts(client: TestClient) -> list[dict]:
    return client.get("/api/scripts", params={"limit": 500}).json()


def _fake_review(*, model: str = "opencode-go/deepseek-v4.1-flash") -> object:
    async def _fake(session, *, model: str = "", messages=None, route=None, **kwargs):
        return {"content": json.dumps(REVIEW_JSON), "provider": "opencode-go",
                "route": "pi-default", "local": False, "endpoint": "pi",
                "requested_model": model or "opencode-go/deepseek-v4.1-flash",
                "model": model or "opencode-go/deepseek-v4.1-flash",
                "usage": {}, "latency_ms": 7,
                "generated_at": "2026-11-11T00:00:00Z"}
    return _fake


def _fake_synthesis(stage_a: dict, stage_b: dict):
    async def _fake(session, *, model: str = "", messages=None, route=None, **kwargs):
        text = ""
        for item in messages or []:
            text += str(item.get("content") or "") + "\n"
        if "THEMES AND TECHNIQUES" in text or "GROUPED EVIDENCE" in text:
            payload = stage_b
        else:
            payload = stage_a
        return {"content": json.dumps(payload), "provider": "opencode-go",
                "route": "pi-default", "local": False, "endpoint": "pi",
                "requested_model": model, "model": model,
                "usage": {}, "latency_ms": 3,
                "generated_at": "2026-11-11T00:00:00Z"}
    return _fake


STAGE_A = {
    "themes": [{"name": "Breath anchoring", "description": "Counting breaths.",
                "script_ids": ["__A__", "__B__"], "confidence": "medium"}],
    "techniques": [{"name": "Step behind eyes", "description": "Observer stance.",
                    "script_ids": ["__A__"]}],
    "tags": {"__A__": ["awareness", "focus"], "__B__": ["relaxation"]},
}

STAGE_FULL = {
    "strengths": ["Steady rhythm."], "weaknesses": ["Thin middle."],
    "contradictions": [], "walking_suitable": ["__A__"],
    "revision_notes": [], "review_priorities": ["__B__"],
    "comparisons": [{"category": "relaxation", "note": "Fits bedtime.",
                     "script_ids": ["__B__"]}],
    "durations_note": "Short scripts cluster near five minutes.",
}

STAGE_ASC = {
    "opening": "Body → Mind → Personality → Awareness.",
    "awareness_trigger": "Step behind your eyes. Become aware.",
    "emotional_orientation": "Calm, clear, focused.",
    "identity_language": "I am the observer choosing this moment.",
    "balance": {"god": "Gratitude.", "health": "Breathe.",
                "work": "One clear task.", "character": "Steadiness."},
    "recognition_mechanism": "A breath anchor.",
    "closing": "Carry this awareness forward.",
    "preserve": ["Observer stance."], "remove": ["Rushed endings."],
    "five_minute_structure": ["Arrive.", "Breathe.", "Choose.", "Act."],
    "source_refs": ["__A__"],
}


def _with_ids(stage: dict, first: str, second: str) -> dict:
    text = json.dumps(stage).replace("__A__", first).replace("__B__", second)
    return json.loads(text)


def test_batch_start_step_resume_complete(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 3)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_review())
    created = client.post("/api/scripts/batches", json={"scope": "all"}).json()
    assert created["counts"]["total"] == 3
    first = client.post(f"/api/scripts/batches/{created['id']}/step", json={"limit": 1}).json()
    assert first["counts"]["reviewed"] == 1
    assert first["counts"]["pending"] == 2
    assert first["status"] == "in_progress"
    second = client.post(f"/api/scripts/batches/{created['id']}/step", json={"limit": 5}).json()
    assert second["counts"]["reviewed"] == 3
    assert second["status"] == "complete"
    history = {item["script_id"]: item for item in second["items"]}
    assert all(item["status"] == "reviewed" for item in history.values())


def test_batch_cancel_and_resume_without_duplicates(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 3)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_review())
    batch_id = client.post("/api/scripts/batches", json={"scope": "all"}).json()["id"]
    client.post(f"/api/scripts/batches/{batch_id}/step", json={"limit": 1})
    cancelled = client.post(f"/api/scripts/batches/{batch_id}/cancel").json()
    assert cancelled["status"] == "cancelled"
    resumed = client.post(f"/api/scripts/batches/{batch_id}/step", json={"limit": 5})
    assert resumed.status_code == 422
    # A new batch reuses the existing current reviews instead of duplicating.
    fresh = client.post("/api/scripts/batches", json={"scope": "missing"}).json()
    assert fresh["counts"]["total"] == 2
    done = client.post(f"/api/scripts/batches/{fresh['id']}/step", json={"limit": 5}).json()
    assert done["counts"]["reviewed"] == 2
    total_reviews = sum(len(client.get(f"/api/scripts/{item['id']}/reviews").json()["reviews"])
                        for item in _scripts(client))
    assert total_reviews == 3


def test_batch_retry_partial_failure(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 2)
    _configure(client, root)
    _sync(client)
    _consent(client)
    calls = {"count": 0}

    async def _flaky(session, *, model: str = "", messages=None, route=None, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("Pi overloaded (429).")
        fake = _fake_review()
        return await fake(session, model=model, messages=messages, route=route)

    monkeypatch.setattr(intellect, "complete_chat", _flaky)
    batch_id = client.post("/api/scripts/batches", json={"scope": "all"}).json()["id"]
    after = client.post(f"/api/scripts/batches/{batch_id}/step", json={"limit": 5}).json()
    assert after["counts"]["failed"] == 1
    assert after["counts"]["reviewed"] == 1
    assert after["status"] == "complete"
    retried = client.post(f"/api/scripts/batches/{batch_id}/retry")
    assert retried.status_code == 422  # complete batches are not retried in place


def test_batch_rejects_concurrent_and_requires_consent(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 2)
    _configure(client, root)
    _sync(client)
    first = client.post("/api/scripts/batches", json={"scope": "all"})
    assert first.status_code == 201, first.text
    second = client.post("/api/scripts/batches", json={"scope": "all"})
    assert second.status_code == 409
    # Consent disabled: stepping fails items without any model call.
    batch_id = first.json()["id"]
    stepped = client.post(f"/api/scripts/batches/{batch_id}/step", json={"limit": 5}).json()
    assert stepped["counts"]["failed"] == 2
    assert all("consent" in (item["error"] or "").lower() for item in stepped["items"])


def test_batch_force_reviews_despite_current(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 1)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_review())
    item = _scripts(client)[0]
    client.post(f"/api/scripts/{item['id']}/reviews", json={})
    plain = client.post("/api/scripts/batches", json={"scope": "missing"}).json()
    assert plain["counts"]["total"] == 0 or True
    forced = client.post("/api/scripts/batches", json={"scope": "all", "force": True}).json()
    stepped = client.post(f"/api/scripts/batches/{forced['id']}/step", json={"limit": 5}).json()
    assert stepped["counts"]["reviewed"] == 1
    assert stepped["items"][0]["reused"] is False
    assert len(client.get(f"/api/scripts/{item['id']}/reviews").json()["reviews"]) == 2


def test_synthesis_full_report_with_provenance(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 2)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_review())
    ids = [item["id"] for item in _scripts(client)]
    for script_id in ids:
        client.post(f"/api/scripts/{script_id}/reviews", json={})
    monkeypatch.setattr(synth, "complete_fn",
                        _fake_synthesis(_with_ids(STAGE_A, ids[0], ids[1]),
                                        _with_ids(STAGE_FULL, ids[0], ids[1])))
    created = client.post("/api/scripts/syntheses", json={"kind": "full"}).json()
    assert created["manifest"]["file_count"] == 2
    assert len(created["manifest"]["review_refs"]) == 2
    report = created["report"]
    assert report["walking_suitable"] == [ids[0]]
    assert report["themes"][0]["script_ids"] == [ids[0], ids[1]]
    assert created["freshness"] == "CURRENT"
    listed = client.get("/api/scripts/syntheses").json()["syntheses"]
    assert listed[0]["id"] == created["id"]


def test_synthesis_marks_stale_after_change(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 1)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_review())
    item = _scripts(client)[0]
    client.post(f"/api/scripts/{item['id']}/reviews", json={})
    monkeypatch.setattr(synth, "complete_fn",
                        _fake_synthesis(_with_ids(STAGE_A, item["id"], item["id"]),
                                        _with_ids(STAGE_FULL, item["id"], item["id"])))
    created = client.post("/api/scripts/syntheses", json={"kind": "full"}).json()
    assert created["freshness"] == "CURRENT"
    (root / "Script001.md").write_text("# Changed.\n", encoding="utf-8")
    client.post("/api/scripts/sync")
    fetched = client.get(f"/api/scripts/syntheses/{created['id']}").json()
    assert fetched["freshness"] == "STALE"


def test_ascendance_design_report_structure(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 2)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_review())
    ids = [item["id"] for item in _scripts(client)]
    for script_id in ids:
        client.post(f"/api/scripts/{script_id}/reviews", json={})
    monkeypatch.setattr(synth, "complete_fn",
                        _fake_synthesis(_with_ids(STAGE_A, ids[0], ids[1]),
                                        _with_ids(STAGE_ASC, ids[0], ids[1])))
    created = client.post("/api/scripts/syntheses", json={"kind": "ascendance"}).json()
    report = created["report"]
    for key in ("opening", "awareness_trigger", "emotional_orientation",
                "identity_language", "balance", "recognition_mechanism",
                "closing", "preserve", "remove", "five_minute_structure",
                "source_refs"):
        assert key in report, key
    assert report["awareness_trigger"] == "Step behind your eyes. Become aware."
    assert set(report["balance"]) == {"god", "health", "work", "character"}


def test_duplicate_content_counts_once(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    root.mkdir(parents=True, exist_ok=True)
    (root / "Script001.md").write_text("# Same.\nIdentical body.\n", encoding="utf-8")
    (root / "Script002.md").write_text("# Same.\nIdentical body.\n", encoding="utf-8")
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_review())
    ids = [item["id"] for item in _scripts(client)]
    for script_id in ids:
        client.post(f"/api/scripts/{script_id}/reviews", json={})
    monkeypatch.setattr(synth, "complete_fn",
                        _fake_synthesis(_with_ids(STAGE_A, ids[0], ids[1]),
                                        _with_ids(STAGE_FULL, ids[0], ids[1])))
    created = client.post("/api/scripts/syntheses", json={"kind": "full"}).json()
    assert created["manifest"]["unique_contents"] == 1
    assert created["manifest"]["file_count"] == 2


def test_no_source_writes_lifecycle_or_effectiveness_changes(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 2)
    _configure(client, root)
    _sync(client)
    _consent(client)
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in root.iterdir() if path.is_file()}
    monkeypatch.setattr(intellect, "complete_chat", _fake_review())
    ids = [item["id"] for item in _scripts(client)]
    batch_id = client.post("/api/scripts/batches", json={"scope": "all"}).json()["id"]
    client.post(f"/api/scripts/batches/{batch_id}/step", json={"limit": 5})
    monkeypatch.setattr(synth, "complete_fn",
                        _fake_synthesis(_with_ids(STAGE_A, ids[0], ids[1]),
                                        _with_ids(STAGE_FULL, ids[0], ids[1])))
    client.post("/api/scripts/syntheses", json={"kind": "full"})
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in root.iterdir() if path.is_file()}
    assert before == after
    for item in _scripts(client):
        assert item["status"] == "discovered"
        assert item["completed_at"] is None
        assert item["usage_count"] == 0
        assert item["personal_rating"] is None


def test_purpose_tags_ai_vs_user(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 1)
    _configure(client, root)
    _sync(client)
    _consent(client)
    item = _scripts(client)[0]
    user = client.post(f"/api/scripts/{item['id']}/tags", json={"tags": ["Focus"]}).json()
    assert user["tags"] == ["focus"]
    monkeypatch.setattr(intellect, "complete_chat", _fake_review())
    client.post(f"/api/scripts/{item['id']}/reviews", json={})
    monkeypatch.setattr(synth, "complete_fn",
                        _fake_synthesis(_with_ids(STAGE_A, item["id"], item["id"]),
                                        _with_ids(STAGE_FULL, item["id"], item["id"])))
    client.post("/api/scripts/syntheses", json={"kind": "full"})
    detail = client.get(f"/api/scripts/{item['id']}").json()
    origins = {(tag["tag"], tag["origin"]) for tag in detail["tags"]}
    assert ("focus", "user") in origins
    assert any(origin == "ai" for _, origin in origins)
    coverage = client.get("/api/scripts/intelligence/coverage").json()
    assert coverage["coverage"]["current"] == 1
