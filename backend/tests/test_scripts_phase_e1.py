"""MC-SCRIPTS-05 Phase E1: intelligence foundation.

All AI calls are monkeypatched fakes. No network, no model, no source writes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from mission_control.scripts import intelligence as intellect

REVIEW_JSON = {
    "purpose": "A short calming script for steady breathing before work.",
    "strengths": ["Clear spoken rhythm.", "Concrete breath cues."],
    "weaknesses": ["The middle drifts without an anchor."],
    "suggested_changes": ["Repeat the step-behind-your-eyes cue once more."],
    "estimated_spoken_seconds": 290,
    "suitability": "Seated or walking; beginners.",
    "readiness": "needs_work",
}


def _make_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "Script001.md").write_text(
        "# Calm.\n\nBreathe in slowly. Step behind your eyes. Become aware.\n" * 40,
        encoding="utf-8",
    )
    (root / "Script002.md").write_text("# Brief.\n\nSit still.\n", encoding="utf-8")


def _configure(client: TestClient, root: Path) -> None:
    response = client.patch("/api/settings", json={"scripts": {"root": str(root)}})
    assert response.status_code == 200, response.text


def _consent(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"ai": {"enabled": True, "consent": True}})
    assert response.status_code == 200, response.text


def _sync(client: TestClient) -> dict:
    response = client.post("/api/scripts/sync")
    assert response.status_code == 200, response.text
    return response.json()


def _scripts(client: TestClient) -> list[dict]:
    response = client.get("/api/scripts", params={"limit": 500})
    assert response.status_code == 200, response.text
    return response.json()


def _fake_complete(content: str = "", *, model: str = "opencode-go/deepseek-v4.1-flash",
                   route: str = "pi-default") -> object:
    async def _fake(session, *, model: str = "", messages=None, route=None, **kwargs):
        return {"content": content or json.dumps(REVIEW_JSON),
                "provider": "opencode-go", "route": route,
                "local": False, "endpoint": "pi",
                "requested_model": model or "opencode-go/deepseek-v4.1-flash",
                "model": model or "opencode-go/deepseek-v4.1-flash",
                "usage": {}, "latency_ms": 123,
                "generated_at": "2026-11-11T00:00:00Z"}
    return _fake


def test_review_requires_consent(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_complete())
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script001.md")
    response = client.post(f"/api/scripts/{item['id']}/reviews", json={})
    assert response.status_code == 422, response.text
    assert client.get(f"/api/scripts/{item['id']}/reviews").json()["reviews"] == []


def test_successful_review_stores_provenance_and_event(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_complete())
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script001.md")
    before_hash = hashlib.sha256((root / "Script001.md").read_bytes()).hexdigest()
    response = client.post(f"/api/scripts/{item['id']}/reviews", json={})
    assert response.status_code == 201, response.text
    review = response.json()
    assert review["model"] == "opencode-go/deepseek-v4.1-flash"
    assert review["route"] == "pi-default"
    assert review["freshness"] == "CURRENT"
    assert review["assessment"]["purpose"] == REVIEW_JSON["purpose"]
    assert review["assessment"]["word_count"] > 0
    assert review["assessment"]["rule_spoken_seconds"] > 0
    assert hashlib.sha256((root / "Script001.md").read_bytes()).hexdigest() == before_hash
    detail = client.get(f"/api/scripts/{item['id']}").json()
    assert detail["status"] == "discovered"
    assert detail["completed_at"] is None
    assert detail["latest_review"]["id"] == review["id"]
    assert any(e["event_type"] == "reviewed" for e in detail["events"])
    history = client.get(f"/api/scripts/{item['id']}/reviews").json()["reviews"]
    assert len(history) == 1


def test_malformed_ai_output_records_nothing(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_complete("not json at all {{{"))
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script001.md")
    response = client.post(f"/api/scripts/{item['id']}/reviews", json={})
    assert response.status_code == 502, response.text
    assert client.get(f"/api/scripts/{item['id']}/reviews").json()["reviews"] == []


def test_stale_review_after_content_change(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_complete())
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script001.md")
    first = client.post(f"/api/scripts/{item['id']}/reviews", json={}).json()
    assert first["freshness"] == "CURRENT"
    (root / "Script001.md").write_text("# Calm.\n\nEntirely new words here.\n", encoding="utf-8")
    client.post("/api/scripts/sync")
    history = client.get(f"/api/scripts/{item['id']}/reviews").json()["reviews"]
    assert history[0]["freshness"] == "STALE"
    second = client.post(f"/api/scripts/{item['id']}/reviews", json={}).json()
    assert second["freshness"] == "CURRENT"
    assert second["id"] != first["id"]
    assert len(client.get(f"/api/scripts/{item['id']}/reviews").json()["reviews"]) == 2


def test_review_never_changes_lifecycle(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_complete())
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script002.md")
    client.patch(f"/api/scripts/{item['id']}/status", json={"status": "ready", "note": "Owner triage."})
    review = client.post(f"/api/scripts/{item['id']}/reviews", json={}).json()
    assert review["assessment"]["readiness"] in {"draft", "needs_work", "ready", "unsuitable"}
    detail = client.get(f"/api/scripts/{item['id']}").json()
    assert detail["status"] == "ready"
    assert detail["completed_at"] is None
    assert detail["archived"] is False


def test_duration_rule_based_estimate(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    assert intellect.estimate_spoken_seconds(0) == 0
    assert intellect.estimate_spoken_seconds(150) == 60
    assert intellect.estimate_spoken_seconds(300) == 120
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_complete())
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script001.md")
    review = client.post(f"/api/scripts/{item['id']}/reviews", json={}).json()
    assert review["assessment"]["rule_spoken_seconds"] == intellect.estimate_spoken_seconds(
        review["assessment"]["word_count"])


def test_effectiveness_is_human_only(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_complete())
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script001.md")
    client.post(f"/api/scripts/{item['id']}/reviews", json={})
    detail = client.get(f"/api/scripts/{item['id']}").json()
    assert detail["usage_count"] == 0
    assert detail["personal_rating"] is None
    assert detail["personal_target"] == ""
    updated = client.patch(f"/api/scripts/{item['id']}/effectiveness", json={
        "usage_count": 3, "personal_rating": 4.5,
        "personal_target": "focus", "personal_effect": "calmer",
        "last_used_at": "2026-11-10T08:00:00+00:00"}).json()
    assert updated["usage_count"] == 3
    assert updated["personal_rating"] == 4.5
    assert any(e["event_type"] == "effectiveness_recorded" for e in updated["events"])
    bad = client.patch(f"/api/scripts/{item['id']}/effectiveness", json={"personal_rating": 9})
    assert bad.status_code == 422


def test_missing_file_review_fails_without_model_call(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    import sys
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _consent(client)
    seen = set(sys.modules)
    monkeypatch.setattr(intellect, "complete_chat", _fake_complete())
    (root / "Script002.md").unlink()
    client.post("/api/scripts/sync")
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script002.md")
    response = client.post(f"/api/scripts/{item['id']}/reviews", json={})
    assert response.status_code in (404, 422), response.text
    assert client.get(f"/api/scripts/{item['id']}/reviews").json()["reviews"] == []
    leaked = {n for n in set(sys.modules) - seen
              if n.split(".")[0] in {"openai", "anthropic", "transformers", "torch"}}
    assert not leaked


def test_model_override_recorded_not_rewritten(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _consent(client)

    async def _fake(session, *, model: str = "", messages=None, route=None, **kwargs):
        assert model == "opencode-go/other-model"
        return {"content": json.dumps(REVIEW_JSON), "provider": "opencode-go",
                "route": "pi-default", "local": False, "endpoint": "pi",
                "requested_model": model, "model": model,
                "usage": {}, "latency_ms": 5, "generated_at": "2026-11-11T00:00:00Z"}

    monkeypatch.setattr(intellect, "complete_chat", _fake)
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script001.md")
    review = client.post(f"/api/scripts/{item['id']}/reviews",
                         json={"model": "opencode-go/other-model"}).json()
    assert review["model"] == "opencode-go/other-model"


def test_review_needs_fresh_sync_after_edit(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _consent(client)
    monkeypatch.setattr(intellect, "complete_chat", _fake_complete())
    item = next(i for i in _scripts(client) if i["current_relpath"] == "Script001.md")
    (root / "Script001.md").write_text("# Changed without sync.\n", encoding="utf-8")
    response = client.post(f"/api/scripts/{item['id']}/reviews", json={})
    assert response.status_code == 422, response.text
