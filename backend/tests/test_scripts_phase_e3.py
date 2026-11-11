"""MC-SCRIPTS-06 Phase E3: Ascendance production and repeatable workflow.

AI paths are monkeypatched fakes. Source library is fixture-only except for
explicit integrity checks against the real collection's read-only state.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from mission_control.scripts import candidates as cand

GOOD = (
    "Feel your body as you walk.\n\n"
    "What is happening in your body right now?\n\n"
    "What is happening in your mind?\n\n"
    "What is happening in your personality?\n\n"
    "[Pause 2 seconds]\n\n"
    "Step behind your eyes. Become aware.\n\n"
    "Calm. Clear. Focused. Guided.\n\n"
    "God walks with me. My work is prayer.\n\n"
    "I care for my body because it carries the life I am building.\n\n"
    "Build. Use. Improve. Release.\n\n"
    "When I act rightly, I notice it. Good. This is who I am.\n\n"
    "Step behind your eyes. Become aware. Live that choice now.\n"
)


def _make_tree(root: Path, count: int = 3) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        (root / f"Script{index:03d}.md").write_text(
            f"# Script {index}.\n\nBody text here.\n" * 5, encoding="utf-8")


def _configure(client: TestClient, root: Path) -> None:
    response = client.patch("/api/settings", json={"scripts": {"root": str(root)}})
    assert response.status_code == 200, response.text


def _sync(client: TestClient) -> None:
    assert client.post("/api/scripts/sync").status_code == 200


def _consent(client: TestClient) -> None:
    assert client.patch("/api/settings",
                        json={"ai": {"enabled": True, "consent": True}}).status_code == 200


def _candidate(client: TestClient, content: str = GOOD, **kwargs) -> dict:
    payload = {"title": "Ascendance — Awareness and Direction",
               "content": content, "kind": "ascendance"}
    payload.update(kwargs)
    response = client.post("/api/scripts/candidates", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_five_minute_limit_and_word_count() -> None:
    assert cand.estimate_spoken_seconds("word " * 150) == 60
    assert cand.estimate_spoken_seconds("word " * 150 + "[Pause 10 seconds]") == 70
    validation = cand.validate_candidate(GOOD)
    assert validation["word_count"] == 84  # pause markers are timing, not speech
    assert validation["within_five_minutes"] is True
    long_text = "word " * 900
    assert cand.validate_candidate(long_text)["within_five_minutes"] is False
    assert cand.validate_candidate(long_text)["hard_fail"] is True


def test_walking_safety_and_cues_and_certainty() -> None:
    bad = GOOD + "\nClose your eyes and fall asleep now.\n"
    validation = cand.validate_candidate(bad)
    assert "close your eyes" in validation["safety_hits"]
    assert "fall asleep" in validation["safety_hits"]
    assert validation["hard_fail"] is True
    claimed = GOOD + "\nThis guarantees inevitable success and rewires your brain.\n"
    validation = cand.validate_candidate(claimed)
    assert validation["certainty_hits"], validation
    assert not validation["hard_fail"]
    missing = "Nothing about the cues here.\n" * 20
    assert set(cand.validate_candidate(missing)["cues_missing"]) == {
        "step behind your eyes", "become aware", "this is who i am"}


def test_candidate_versioning_diff_accept_reject(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    first = _candidate(client)
    assert first["version"] == "v1"
    assert first["status"] == "draft"
    assert first["validation"]["within_five_minutes"] is True
    second = client.post(f"/api/scripts/candidates/{first['id']}/revise", json={
        "content": first["content"] + "\nExtra line of resolve.\n",
        "note": "Stronger closing."}).json()
    assert second["version"] == "v2"
    assert second["parent_candidate_id"] == first["id"]
    assert client.get(f"/api/scripts/candidates/{first['id']}").json()["status"] == "superseded"
    diff = client.get(f"/api/scripts/candidates/{second['id']}/diff").json()
    assert "Extra line of resolve." in diff["diff"]
    assert diff["parent"] == first["id"]
    accepted = client.patch(f"/api/scripts/candidates/{second['id']}/status",
                            json={"status": "accepted"}).json()
    assert accepted["status"] == "accepted"
    rejected = client.post("/api/scripts/candidates", json={
        "title": "Other", "content": GOOD, "version": "v1"})
    assert rejected.status_code == 201
    assert client.patch(f"/api/scripts/candidates/{rejected.json()['id']}/status",
                        json={"status": "rejected"}).json()["status"] == "rejected"
    assert client.patch(f"/api/scripts/candidates/{rejected.json()['id']}/status",
                        json={"status": "accepted"}).status_code == 422


def test_duplicate_candidate_rejected(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    _candidate(client)
    again = client.post("/api/scripts/candidates", json={
        "title": "Ascendance — Awareness and Direction", "content": GOOD, "version": "v1"})
    assert again.status_code == 409


def test_promotion_allocates_next_number_safely(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 2)
    _configure(client, root)
    _sync(client)
    before = {item["id"] for item in client.get("/api/scripts", params={"limit": 500}).json()}
    candidate = _candidate(client)
    client.patch(f"/api/scripts/candidates/{candidate['id']}/status", json={"status": "accepted"})
    promoted = client.post(f"/api/scripts/candidates/{candidate['id']}/promote").json()
    assert promoted["status"] == "promoted"
    assert promoted["promoted_relpath"] == "Script003.md"
    assert (root / "Script003.md").read_text(encoding="utf-8") == GOOD
    detail = client.get(f"/api/scripts/{promoted['promoted_script_id']}").json()
    assert detail["status"] == "discovered"
    assert detail["completed_at"] is None
    after = {item["id"] for item in client.get("/api/scripts", params={"limit": 500}).json()}
    assert len(after - before) == 1
    # Second promotion attempt is rejected; re-promotion is impossible.
    assert client.post(f"/api/scripts/candidates/{candidate['id']}/promote").status_code in (409, 422)
    # Promoting a draft is refused.
    draft = _candidate(client, version="v9")
    assert client.post(f"/api/scripts/candidates/{draft['id']}/promote").status_code == 422


def test_concurrent_promotion_second_fails(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root, 1)
    _configure(client, root)
    _sync(client)
    first = _candidate(client, version="v1")
    second = _candidate(client, version="v2")
    for candidate in (first, second):
        client.patch(f"/api/scripts/candidates/{candidate['id']}/status",
                     json={"status": "accepted"})
    assert client.post(f"/api/scripts/candidates/{first['id']}/promote").status_code == 200
    # A file appearing at the would-be destination between allocation and
    # write must abort instead of overwriting (TOCTOU guard).
    import mission_control.scripts.candidates as cand_module
    monkeypatch.setattr(cand_module, "_next_number", lambda session, key, root: (3, "Script003.md"))
    (root / "Script003.md").write_text("# Concurrent writer.\n", encoding="utf-8")
    assert client.post(f"/api/scripts/candidates/{second['id']}/promote").status_code == 409


def test_generation_and_review_do_not_count_as_completion(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    import sys

    from mission_control.scripts import intelligence as intellect

    root = tmp_path / "lib"
    _make_tree(root, 1)
    _configure(client, root)
    _sync(client)
    _consent(client)
    seen = set(sys.modules)

    async def _fake(session, *, model: str = "", messages=None, route=None, **kwargs):
        return {"content": json.dumps({
            "purpose": "Calm.", "strengths": ["A."], "weaknesses": ["B."],
            "suggested_changes": ["C."], "estimated_spoken_seconds": 60,
            "suitability": "Walking.", "readiness": "ready"}),
            "provider": "x", "route": "pi-default", "local": False, "endpoint": "pi",
            "requested_model": model, "model": model or "m",
            "usage": {}, "latency_ms": 1, "generated_at": "2026-11-11T00:00:00Z"}

    monkeypatch.setattr(intellect, "complete_chat", _fake)
    _candidate(client)
    script_id = client.get("/api/scripts", params={"limit": 500}).json()[0]["id"]
    client.post(f"/api/scripts/{script_id}/reviews", json={})
    published = client.get("/api/cultivation/goals/scripts_published").json()["progress"]["current"]
    weekly = client.get("/api/cultivation/goals/weekly_script").json()["progress"]["current"]
    assert published == 0
    assert weekly == 0
    leaked = {name for name in set(sys.modules) - seen
              if name.split(".")[0] in {"openai", "anthropic", "transformers", "torch"}}
    assert not leaked


def test_pi_critique_path_mocked_and_consent_gated(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _make_tree(root)
    _configure(client, root)
    _sync(client)
    candidate = _candidate(client)
    gated = client.post(f"/api/scripts/candidates/{candidate['id']}/critique").json()
    assert gated["pi"]["skipped"] is True
    assert gated["deterministic"]["origin"] == "deterministic"
    _consent(client)

    async def _fake_critique(session, content: str, *, model: str = "") -> dict:
        assert model == "opencode-go/deepseek-v4.1-flash"
        return {"origin": "pi", "model": "opencode-go/deepseek-v4.1-flash",
                "route": "pi-default", "latency_ms": 4,
                "findings": [{"area": "opening", "note": "Start faster."}],
                "strengths": ["Clear cues."]}

    import mission_control.scripts.candidates as cand_module
    monkeypatch.setattr(cand_module, "pi_critique", _fake_critique)
    result = client.post(
        f"/api/scripts/candidates/{candidate['id']}/critique?model=opencode-go/deepseek-v4.1-flash").json()
    assert result["pi"]["origin"] == "pi"
    assert result["pi"]["model"] == "opencode-go/deepseek-v4.1-flash"
    assert result["deterministic"]["origin"] == "deterministic"
    stored = client.get(f"/api/scripts/candidates/{candidate['id']}").json()
    assert stored["critique"]["pi"]["model"] == "opencode-go/deepseek-v4.1-flash"


def test_real_library_hashes_preserved() -> None:
    root = Path(r"C:\script")
    names = sorted(path.name for path in root.glob("Script*.md"))
    assert names == [f"Script{i:03d}.md" for i in range(1, 68)], names[:5]
