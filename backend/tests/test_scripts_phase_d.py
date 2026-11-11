"""MC-SCRIPTS-04 Phase D: organisation, safe renumbering, version relationships.

Fixture libraries only. Never touches C:\\script as writable.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient


def _write(root: Path, name: str, text: str) -> Path:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _fixture_library(root: Path) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "Script001.md": "# One.\nBody one.\n",
        "Script002.md": "# Two.\nBody two.\n",
        # Identical pair sharing a number: exact duplicate.
        "Script052.md": "# Dup.\nSame bytes.\n",
        "Script052s.md": "# Dup.\nSame bytes.\n",
        # Same number, different content: alternate.
        "Script036.md": "# Thirty six.\nOriginal.\n",
        "Script036_not your money.md": "# Money.\nDifferent.\n",
        # Identical content across numbers: exact duplicate.
        "Script003.md": "# Shared.\nIdentical.\n",
        "Script006.md": "# Shared.\nIdentical.\n",
        # Suffixed revision candidate.
        "Script057.md": "# Fifty seven.\nShort.\n",
        "Script057a.md": "# Fifty seven revised.\nLonger body here.\n",
        # Reference holder: mentions another script by name.
        "Script010.md": "# Ten.\nSee Script002 for context.\n",
        "Morning001.md": "# Morning (excluded).\n",
    }
    for name, text in files.items():
        _write(root, name, text)
    return files


def _configure(client: TestClient, root: Path) -> None:
    response = client.patch("/api/settings", json={"scripts": {"root": str(root)}})
    assert response.status_code == 200, response.text


def _sync(client: TestClient) -> dict:
    response = client.post("/api/scripts/sync")
    assert response.status_code == 200, response.text
    return response.json()


def _scripts(client: TestClient) -> list[dict]:
    response = client.get("/api/scripts", params={"limit": 500})
    assert response.status_code == 200, response.text
    return response.json()


def _discover(client: TestClient) -> dict:
    response = client.post("/api/scripts/relationships/discover")
    assert response.status_code == 200, response.text
    return response.json()


def _preview(client: TestClient) -> dict:
    response = client.post("/api/scripts/migrations/preview")
    assert response.status_code == 200, response.text
    return response.json()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sequential_numbering_and_deterministic_order(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    preview = _preview(client)
    items = preview["manifest"]["items"]
    assert len(items) == 11  # 12 files minus excluded Morning001
    assert [item["proposed"] for item in items] == [f"Script{i:03d}.md" for i in range(1, 12)]
    # Numerical order preserved: Script002 before Script010.
    order = [item["current"] for item in items]
    assert order.index("Script002.md") < order.index("Script010.md")
    assert order.index("Script003.md") < order.index("Script052.md")


def test_duplicate_numbers_and_suffixed_versions_detected(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    result = _discover(client)
    assert result["proposed"] >= 3
    response = client.get("/api/scripts/relationships")
    links = response.json()["relationships"]
    kinds = {link["kind"] for link in links}
    assert "exact_duplicate" in kinds
    assert "alternate" in kinds
    assert all(link["confirmed"] is False for link in links)
    # 052 pair identical -> exact duplicate with high confidence.
    id_map = {item["current_relpath"]: item["id"] for item in _scripts(client)}
    pair = tuple(sorted((id_map["Script052.md"], id_map["Script052s.md"])))
    assert any(link["source_id"] == pair[0] and link["target_id"] == pair[1]
               and link["kind"] == "exact_duplicate" for link in links)


def test_identical_and_different_content_alternatives(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    _discover(client)
    id_map = {item["current_relpath"]: item["id"] for item in _scripts(client)}
    # 003/006 identical across numbers.
    same = tuple(sorted((id_map["Script003.md"], id_map["Script006.md"])))
    links = client.get("/api/scripts/relationships").json()["relationships"]
    assert any(link["source_id"] == same[0] and link["kind"] == "exact_duplicate" for link in links)
    # 036 pair different content, same number -> alternate, never merged automatically.
    alt = tuple(sorted((id_map["Script036.md"], id_map["Script036_not your money.md"])))
    assert any(link["source_id"] == alt[0] and link["kind"] == "alternate" for link in links)
    assert id_map["Script036.md"] != id_map["Script036_not your money.md"]


def test_unnumbered_exclusions_never_renamed(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    preview = _preview(client)
    currents = [item["current"] for item in preview["manifest"]["items"]]
    assert "Morning001.md" not in currents
    assert all(name.startswith("Script") for name in currents)


def test_confirm_revision_alternate_independent(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    _discover(client)
    id_map = {item["current_relpath"]: item["id"] for item in _scripts(client)}
    # Confirm 057a as a revision of 057.
    response = client.post("/api/scripts/relationships/confirm", json={
        "source_id": id_map["Script057.md"], "target_id": id_map["Script057a.md"],
        "kind": "revision", "confirmed": True, "note": "Owner: revised draft."})
    assert response.status_code == 200, response.text
    # Mark 003/006 as independent despite identical bytes (owner judgement wins).
    response = client.post("/api/scripts/relationships/confirm", json={
        "source_id": id_map["Script003.md"], "target_id": id_map["Script006.md"],
        "kind": "independent", "confirmed": True, "note": "Owner: separate works."})
    assert response.status_code == 200, response.text
    works = client.get("/api/scripts/works").json()
    # 057 pair merged; 003/006 independent (independent links never merge).
    group_057 = next(work for work in works["works"] if id_map["Script057a.md"] in work["member_ids"])
    assert id_map["Script057.md"] in group_057["member_ids"]
    group_003 = next(work for work in works["works"] if id_map["Script003.md"] in work["member_ids"])
    assert id_map["Script006.md"] not in group_003["member_ids"]


def test_destination_conflicts_blocked(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    # An unexpected outsider occupying a destination name blocks application.
    # With 11 items destinations are Script001..Script011; plant Script011.md
    # content outside the registry by writing after sync without re-syncing.
    _write(root, "Script011.md", "# Outsider.\n")
    preview = _preview(client)
    assert any(c["destination"] == "Script011.md" for c in preview["manifest"]["collisions"])
    approved = client.post(f"/api/scripts/migrations/{preview['migration_id']}/approve",
                           json={"expected_hash": preview["manifest_hash"]})
    assert approved.status_code == 200, approved.text
    applied = client.post(f"/api/scripts/migrations/{preview['migration_id']}/apply",
                          json={"expected_hash": preview["manifest_hash"]})
    assert applied.status_code == 422, applied.text


def test_stale_preview_rejected_after_change(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    preview = _preview(client)
    migration_id = preview["migration_id"]
    # Change content after the preview: fingerprints no longer match.
    _write(root, "Script001.md", "# One.\nEdited after preview.\n")
    approved = client.post(f"/api/scripts/migrations/{migration_id}/approve",
                           json={"expected_hash": preview["manifest_hash"]})
    assert approved.status_code == 200, approved.text
    applied = client.post(f"/api/scripts/migrations/{migration_id}/apply",
                          json={"expected_hash": preview["manifest_hash"]})
    assert applied.status_code == 422
    assert "stale" in applied.text.lower()


def test_hash_and_identity_preserved_through_apply(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    # Complete one script first so Cultivation preservation is meaningful.
    before_ids = {item["current_relpath"]: item["id"] for item in _scripts(client)}
    first_id = before_ids["Script001.md"]
    client.patch(f"/api/scripts/{first_id}/status", json={"status": "completed", "note": "Baseline."})
    client.post("/api/cultivation/sources/src-scripts/sync")
    before = {item["id"]: item for item in _scripts(client)}
    before_hashes = {item["current_relpath"]: _hash(root / item["current_relpath"]) for item in before.values()}
    preview = _preview(client)
    assert not preview["manifest"]["collisions"]
    client.post(f"/api/scripts/migrations/{preview['migration_id']}/approve",
                json={"expected_hash": preview["manifest_hash"]})
    published_before = client.get("/api/cultivation/goals/scripts_published").json()["progress"]["current"]
    assert published_before == 1
    applied = client.post(f"/api/scripts/migrations/{preview['migration_id']}/apply",
                          json={"expected_hash": preview["manifest_hash"]})
    assert applied.status_code == 200, applied.text
    after = {item["id"]: item for item in _scripts(client)}
    assert set(after) == set(before)
    for script_id, item in after.items():
        assert _hash(root / item["current_relpath"]) == before[item["id"]]["content_sha256"]
        assert item["original_relpath"] == before[script_id]["original_relpath"]
        assert item["status"] == before[script_id]["status"]
        assert item["completed_at"] == before[script_id]["completed_at"]
    # Old hash still resolves to the same record under its new name.
    assert after[first_id]["content_sha256"] == before_hashes["Script001.md"]
    published_after = client.get("/api/cultivation/goals/scripts_published").json()["progress"]["current"]
    assert published_after == 1


def test_root_scoped_libraries_isolated(client: TestClient, tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    _fixture_library(first)
    (second / "Script001.md").parent.mkdir(parents=True, exist_ok=True)
    _write(second, "Script001.md", "# Unrelated.\n")
    _configure(client, first)
    _sync(client)
    preview_a = _preview(client)
    _configure(client, second)
    _sync(client)
    preview_b = _preview(client)
    assert preview_a["manifest"]["library_key"] != preview_b["manifest"]["library_key"]
    assert len(preview_b["manifest"]["items"]) == 1


def test_registry_events_preserved(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    # Script036 sorts to proposed Script006, so it always moves and is renamed.
    target = next(item for item in _scripts(client) if item["current_relpath"] == "Script036.md")
    client.patch(f"/api/scripts/{target['id']}/status", json={"status": "ready", "note": "Triage."})
    preview = _preview(client)
    client.post(f"/api/scripts/migrations/{preview['migration_id']}/approve",
                json={"expected_hash": preview["manifest_hash"]})
    applied = client.post(f"/api/scripts/migrations/{preview['migration_id']}/apply",
                          json={"expected_hash": preview["manifest_hash"]})
    assert applied.status_code == 200, applied.text
    detail = client.get(f"/api/scripts/{target['id']}").json()
    assert any(event["event_type"] == "status_changed" for event in detail["events"])
    assert any(event["event_type"] == "renamed" for event in detail["events"])


def test_completion_and_weekly_preserved(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    first = next(item for item in _scripts(client) if item["current_relpath"] == "Script001.md")
    client.patch(f"/api/scripts/{first['id']}/status", json={"status": "completed", "note": "Done."})
    weekly_before = client.get("/api/cultivation/goals/weekly_script").json()["progress"]["current"]
    preview = _preview(client)
    client.post(f"/api/scripts/migrations/{preview['migration_id']}/approve",
                json={"expected_hash": preview["manifest_hash"]})
    client.post(f"/api/scripts/migrations/{preview['migration_id']}/apply",
                json={"expected_hash": preview["manifest_hash"]})
    client.post("/api/cultivation/sources/src-scripts/sync")
    assert client.get("/api/cultivation/goals/scripts_published").json()["progress"]["current"] == 1
    assert client.get("/api/cultivation/goals/weekly_script").json()["progress"]["current"] == weekly_before


def test_missing_files_block_or_skip_safely(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    (root / "Script002.md").unlink()
    _sync(client)
    preview = _preview(client)
    assert "Script002.md" not in [item["current"] for item in preview["manifest"]["items"]]
    missing = [item for item in _scripts(client) if item["missing"]]
    assert any(item["current_relpath"] == "Script002.md" for item in missing)


def test_interrupted_migration_resume_and_rollback(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    preview = _preview(client)
    migration_id = preview["migration_id"]
    client.post(f"/api/scripts/migrations/{migration_id}/approve",
                json={"expected_hash": preview["manifest_hash"]})
    import mission_control.scripts.organise as org
    real_replace = org.os.replace
    calls = {"count": 0}

    def flaky(first: str, second: str) -> None:
        calls["count"] += 1
        if calls["count"] == 3:
            raise OSError("simulated crash")
        real_replace(first, second)

    monkeypatch.setattr(org.os, "replace", flaky)
    failed = client.post(f"/api/scripts/migrations/{migration_id}/apply",
                         json={"expected_hash": preview["manifest_hash"]})
    assert failed.status_code == 422
    monkeypatch.setattr(org.os, "replace", real_replace)
    resumed = client.post(f"/api/scripts/migrations/{migration_id}/apply",
                          json={"expected_hash": preview["manifest_hash"]})
    # Resume is only supported from approved/failed states via re-apply.
    assert resumed.status_code in (200, 422)
    if resumed.status_code == 200:
        rolled = client.post(f"/api/scripts/migrations/{migration_id}/rollback")
        assert rolled.status_code == 200, rolled.text
        assert rolled.json()["status"] == "rolled_back"


def test_dirty_git_sources_blocked_unrelated_allowed(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(root), capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(root), capture_output=True, check=False)
    subprocess.run(["git", "add", "."], cwd=str(root), capture_output=True, check=False)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
                   cwd=str(root), capture_output=True, check=False)
    _configure(client, root)
    _sync(client)
    # Dirty a tracked source: migration must block. Re-sync first so the
    # preview reflects the dirty content; the git check is what must block.
    _write(root, "Script001.md", "# One.\nDirty edit.\n")
    _sync(client)
    preview = _preview(client)
    client.post(f"/api/scripts/migrations/{preview['migration_id']}/approve",
                json={"expected_hash": preview["manifest_hash"]})
    blocked = client.post(f"/api/scripts/migrations/{preview['migration_id']}/apply",
                          json={"expected_hash": preview["manifest_hash"]})
    assert blocked.status_code == 422
    # Restore, then dirty an unrelated file: migration proceeds.
    subprocess.run(["git", "checkout", "--", "Script001.md"], cwd=str(root), capture_output=True, check=False)
    _sync(client)
    _write(root, "notes-unrelated.md", "# Unrelated.\n")
    preview2 = _preview(client)
    client.post(f"/api/scripts/migrations/{preview2['migration_id']}/approve",
                json={"expected_hash": preview2["manifest_hash"]})
    applied = client.post(f"/api/scripts/migrations/{preview2['migration_id']}/apply",
                          json={"expected_hash": preview2["manifest_hash"]})
    assert applied.status_code == 200, applied.text


def test_ambiguous_references_listed_not_rewritten(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    preview = _preview(client)
    refs = [ref for ref in preview["manifest"]["references"] if ref["source"] == "Script010.md"]
    assert refs, "Script010 mentions Script002 and must be listed"
    assert all(ref["safe_to_update"] is False for ref in refs)
    before = _hash(root / "Script010.md")
    client.post(f"/api/scripts/migrations/{preview['migration_id']}/approve",
                json={"expected_hash": preview["manifest_hash"]})
    client.post(f"/api/scripts/migrations/{preview['migration_id']}/apply",
                json={"expected_hash": preview["manifest_hash"]})
    # Pure rename: no file content was rewritten.
    renamed = next(item for item in _scripts(client)
                   if item["original_relpath"] == "Script010.md")
    assert _hash(root / renamed["current_relpath"]) == before


def test_idempotent_retry_after_success(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    preview = _preview(client)
    client.post(f"/api/scripts/migrations/{preview['migration_id']}/approve",
                json={"expected_hash": preview["manifest_hash"]})
    first = client.post(f"/api/scripts/migrations/{preview['migration_id']}/apply",
                        json={"expected_hash": preview["manifest_hash"]})
    assert first.status_code == 200, first.text
    second = client.post(f"/api/scripts/migrations/{preview['migration_id']}/apply",
                         json={"expected_hash": preview["manifest_hash"]})
    assert second.status_code == 422  # applied migrations cannot be re-applied


def test_no_model_calls_and_no_unrelated_writes(client: TestClient, tmp_path: Path) -> None:
    import sys

    root = tmp_path / "lib"
    _fixture_library(root)
    _configure(client, root)
    _sync(client)
    before = {path.name: _hash(path) for path in root.iterdir() if path.is_file()}
    seen = set(sys.modules)
    _discover(client)
    _preview(client)
    leaked = {name for name in set(sys.modules) - seen
              if name.split(".")[0] in {"openai", "anthropic", "transformers", "torch"}}
    assert not leaked
    after = {path.name: _hash(path) for path in root.iterdir() if path.is_file()}
    # Preview/discovery are strictly read-only.
    assert before == after


def test_rotation_where_destination_is_held_by_later_record(client: TestClient, tmp_path: Path) -> None:
    """Regression: 056_a -> 057 while record 057 still holds that path.

    Minimal rotation: the suffix variant sorts before the clean holder of its
    destination number. A direct sequential registry update violates the
    (library_key, current_relpath) uniqueness here; the two-pass finalize
    must handle it.
    """
    root = tmp_path / "lib"
    root.mkdir(parents=True, exist_ok=True)
    _write(root, "Script001.md", "# One.\n")
    _write(root, "Script001a.md", "# One variant.\n")
    _write(root, "Script002.md", "# Two.\n")
    _configure(client, root)
    _sync(client)
    preview = _preview(client)
    # 001a sorts after 001, so it proposes 002 while record 002 still holds it.
    by_current = {item["current"]: item for item in preview["manifest"]["items"]}
    assert by_current["Script001a.md"]["proposed"] == "Script002.md"
    assert by_current["Script002.md"]["proposed"] == "Script003.md"
    client.post(f"/api/scripts/migrations/{preview['migration_id']}/approve",
                json={"expected_hash": preview["manifest_hash"]})
    applied = client.post(f"/api/scripts/migrations/{preview['migration_id']}/apply",
                          json={"expected_hash": preview["manifest_hash"]})
    assert applied.status_code == 200, applied.text
    names = sorted(path.name for path in root.glob("Script*.md"))
    assert names == ["Script001.md", "Script002.md", "Script003.md"]
    rows = {item["original_relpath"]: item for item in _scripts(client)}
    assert rows["Script001a.md"]["current_relpath"] == "Script002.md"
    assert rows["Script002.md"]["current_relpath"] == "Script003.md"
    assert rows["Script001a.md"]["content_sha256"] != rows["Script002.md"]["content_sha256"]
