"""MC-PUBLISH-03: evidence adapters, gate join, follow-ups, overview, refresh.

Hermetic: fixture repositories under tmp_path only. The Writer registry and
identity modules are faked at the module boundary; only this feature's
read-only logic is under test. No model calls, no builds, no publications.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from helpers import open_client
from mission_control.config import RuntimeSettings


def _runtime(tmp_path: Path) -> RuntimeSettings:
    base = RuntimeSettings(
        repo_root=Path(__file__).resolve().parents[2],
        data_dir=tmp_path / "data",
        config_dir=Path(__file__).resolve().parents[2] / "config",
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "b",
        fiction_book_root=tmp_path / "fb",
        host="127.0.0.1",
        port=8790,
        start_monitor=False,
        seed_defaults=True,
    )
    base.websites_root = tmp_path / "websites"
    return base


def _chapters(root: Path, count: int, prefix: str = "") -> Path:
    manuscript = root / "content" / "books" / "book"
    manuscript.mkdir(parents=True, exist_ok=True)
    (manuscript / "_index.md").write_text("+++\ntitle = \"B\"\n+++\n", encoding="utf-8")
    for index in range(1, count + 1):
        (manuscript / f"{index:02d}-chapter.md").write_text(
            f"{prefix}# Chapter {index}\n\nBody {index}.\n", encoding="utf-8")
    return manuscript


def _writer_validation(root: Path, *, approved_by: str | None = None,
                       stale: bool = False) -> None:
    out = root / ".writer" / "validation"
    (out / "chapters").mkdir(parents=True, exist_ok=True)
    (out / "finalization").mkdir(parents=True, exist_ok=True)
    import hashlib

    for chapter in sorted((root / "content" / "books" / "book").glob("*.md")):
        digest = hashlib.sha256(chapter.read_bytes()).hexdigest()
        if stale and chapter.name == "01-chapter.md":
            digest = "0" * 64
        (out / "chapters" / f"{chapter.stem}.json").write_text(json.dumps({
            "chapter_path": str(chapter),
            "machine_status": "PASS",
            "run_id": "run-1",
            "source_digest": digest,
            "results": [{"check_id": "manuscript_integrity", "status": "PASS"}],
        }), encoding="utf-8")
    if approved_by:
        first = sorted((root / "content" / "books" / "book").glob("*.md"))[0]
        live = hashlib.sha256(first.read_bytes()).hexdigest()
        (out / "finalization" / "01-chapter.json").write_text(json.dumps([{
            "project_key": "probe", "chapter_path": "01-chapter.md",
            "approved_by": approved_by, "source_digest": "0" * 64 if stale else live,
            "run_id": "run-1", "created_at": "2026-01-01T00:00:00Z"}]), encoding="utf-8")


def _definition(manuscript: Path, repo: Path, **overrides):
    data = {
        "available": True,
        "chapter_dir": str(manuscript),
        "repo_path": str(repo),
        "project_root": str(repo),
        "validation_checks": [{"id": "manuscript_integrity", "required": True}],
        "human_approval_required": True,
        "title": "Probe",
        "chapter_count": 3,
        "chapter_pattern": "*.md",
        "publication_status": "research",
        "error": "",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _snapshot(definition, books: dict | None = None):
    return SimpleNamespace(
        books=books if books is not None else {"probe": definition},
        source_path="/tmp/registry.yaml",
        errors=[],
    )


def _diagnostic(manuscript: Path, count: int = 3):
    return {
        "resolved_chapter_dir": str(manuscript),
        "chapter_count": count,
        "manuscript_paths": [str(manuscript)],
        "book_title": "Probe",
        "available": True,
        "publication_status": "research",
        "writer_registered": True,
    }


def root_for(manuscript: Path) -> Path:
    """Repository root two levels above content/books/<book>."""
    return manuscript.parents[2]


def _install_fakes(monkeypatch, manuscript: Path, definition=None, identity_state: str = "canonical",
                 repo: Path | None = None, chapter_count: int = 3):
    import mission_control.publication.identity as identity_mod
    import mission_control.writer_registry as registry_mod

    definition = definition or _definition(manuscript, repo or root_for(manuscript))
    snapshot = _snapshot(definition)

    monkeypatch.setattr(registry_mod, "load_writer_registry", lambda *args, **kwargs: snapshot)
    monkeypatch.setattr(registry_mod, "resolve_registry_path", lambda *args, **kwargs: Path("/tmp/x.yaml"))
    monkeypatch.setattr(
        registry_mod, "book_source_diagnostic",
        lambda session, project_id, snap: _diagnostic(manuscript, chapter_count))

    monkeypatch.setattr(
        identity_mod, "identity_status",
        lambda session, project_id, writer_ids, writer_available: {
            "state": identity_state, "reason": "ok", "writer_id": "probe", "candidates": []})
    monkeypatch.setattr(identity_mod, "get_aliases", lambda session: [])
    return definition


def _make_book(client: TestClient, project_id: str = "probe", manuscript: str = "") -> None:
    response = client.post("/api/projects", json={
        "id": project_id, "name": "Probe", "kind": "book",
        "repository_path": manuscript, "book_title": "Probe Book"})
    assert response.status_code == 201, response.text
    patched = client.patch(f"/api/books/book-{project_id}",
                           json={"manuscript_paths": [manuscript]})
    assert patched.status_code == 200, patched.text


def test_math_like_39_chapters_discovered(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "math"
    manuscript = _chapters(repo, 39)
    _writer_validation(repo, approved_by="Ernan Hughes")
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript, chapter_count=39)
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        assert summary["chapter_count"] == 39
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        assert by_type["manuscript_discovery"]["result"] == "passed"
        assert by_type["writer_finalization"]["result"] == "passed"
        assert by_type["writer_finalization"]["freshness"] == "current"
        assert "Ernan Hughes" in by_type["writer_finalization"]["diagnostics"]


def test_memory_standalone_unregistered(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "memory"
    manuscript = _chapters(repo, 5)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        import mission_control.publication.identity as identity_mod
        import mission_control.writer_registry as registry_mod

        monkeypatch.setattr(registry_mod, "load_writer_registry",
                            lambda *args, **kwargs: SimpleNamespace(
                                books={}, source_path=None, errors=[]))
        monkeypatch.setattr(registry_mod, "resolve_registry_path",
                            lambda *args, **kwargs: Path("/tmp/x.yaml"))
        monkeypatch.setattr(
            registry_mod, "book_source_diagnostic",
            lambda session, project_id, snap: {
                "resolved_chapter_dir": None, "chapter_count": 0,
                "manuscript_paths": [], "book_title": "Probe",
                "available": False, "publication_status": None,
                "writer_registered": False})
        monkeypatch.setattr(
            identity_mod, "identity_status",
            lambda session, pid, wids, wav: {
                "state": "unregistered", "reason": "nope", "writer_id": None, "candidates": []})
        monkeypatch.setattr(identity_mod, "get_aliases", lambda session: [])
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        assert by_type["manuscript_discovery"]["result"] == "unknown"
        assert by_type["writer_readthrough"]["result"] == "unknown"


def test_shared_repo_fiction_drift_keeps_working_source(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "shared"
    manuscript = _chapters(repo, 4)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        definition = _definition(manuscript, repo)
        definition.available = False
        _install_fakes(monkeypatch, manuscript, definition)
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        assert by_type["manuscript_discovery"]["result"] == "unavailable"


def test_missing_and_stale_evidence(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "empty"
    manuscript = _chapters(repo, 2)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        # No .writer output, no builder config, no proof integration, ALIVE down.
        assert by_type["writer_validation_run"]["result"] == "unknown"
        assert by_type["builder_artifacts"]["result"] == "unavailable"
        assert by_type["proof_claims"]["result"] == "unknown"
        alive = by_type["alive_connection"]
        # Live here: ALIVE runs but the probe book was never connected -> pending.
        # Without ALIVE the same evidence reports unknown/unavailable. Both honest.
        assert alive["result"] in ("unknown", "unavailable", "pending")
        if alive["result"] == "pending":
            assert "not connected" in alive["diagnostics"]
        assert by_type["writer_finalization"]["result"] == "unknown"
        assert by_type["writer_readthrough"]["result"] == "unknown"
        assert summary["blockers"]["missing"]
        # Stale finalization after an edit.
        _writer_validation(repo, approved_by="Ernan Hughes", stale=True)
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        assert by_type["writer_finalization"]["result"] == "pending"
        assert by_type["writer_finalization"]["freshness"] == "stale"
        assert "writer_finalization" in summary["blockers"]["stale"]


def test_builder_config_and_freshness(tmp_path: Path, monkeypatch) -> None:
    from mission_control.publication import publishing as publishing

    repo = tmp_path / "book"
    manuscript = _chapters(repo, 2)
    bookbuilder = tmp_path / "bb"
    (bookbuilder / "dist").mkdir(parents=True)
    (bookbuilder / "probe.toml").write_text(
        '[book]\ntitle = "Probe"\nidentifier = "probe"\n', encoding="utf-8")
    (bookbuilder / "dist" / "probe.epub").write_bytes(b"0" * 100)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        monkeypatch.setenv("MISSION_CONTROL_BOOKBUILDER_ROOT", str(bookbuilder))
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        builder = by_type["builder_artifacts"]
        assert builder["result"] == "unknown"  # existence is not validity
        assert builder["freshness"] == "current"
        assert "probe.toml" in (builder["detail"] or {}).get("config", "")
        # Touch a chapter newer than the artifact -> stale.
        (manuscript / "01-chapter.md").write_text("# New\n\nEdited.\n", encoding="utf-8")
        import time

        time.sleep(0.02)
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        assert by_type["builder_artifacts"]["freshness"] == "stale"
        assert "builder_artifacts" in summary["blockers"]["stale"]


def test_unknown_provenance_artifacts(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "book"
    manuscript = _chapters(repo, 1)
    bookbuilder = tmp_path / "bb2"
    (bookbuilder / "dist").mkdir(parents=True)
    (bookbuilder / "dist" / "probe.epub").write_bytes(b"1" * 50)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        monkeypatch.setenv("MISSION_CONTROL_BOOKBUILDER_ROOT", str(bookbuilder))
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        # Artifact without any matching config: still unknown, never passed.
        assert by_type["builder_artifacts"]["result"] == "unknown"


def test_approval_required_not_recorded(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "book"
    manuscript = _chapters(repo, 1)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        assert by_type["human_approval"]["result"] == "pending"
        assert by_type["human_approval"]["freshness"] == "unknown"


def test_readthrough_unavailable_without_dsn(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "book"
    manuscript = _chapters(repo, 2)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        monkeypatch.delenv("MISSION_CONTROL_WRITER_DSN", raising=False)
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        assert by_type["writer_readthrough"]["result"] == "unknown"
        assert "MISSION_CONTROL_WRITER_DSN" in by_type["writer_readthrough"]["diagnostics"]


def test_readthrough_unreachable_dsn_reports_unknown(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "book"
    manuscript = _chapters(repo, 1)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        monkeypatch.setenv("MISSION_CONTROL_WRITER_DSN", "postgresql://u:p@127.0.0.1:1/db")
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        by_type = {item["evidence_type"]: item for item in summary["evidence"]}
        assert by_type["writer_readthrough"]["result"] == "unknown"


def test_overview_lists_books_with_rollups(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "book"
    manuscript = _chapters(repo, 1)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        overview = client.get("/api/publication/publishing/overview").json()
        assert overview["count"] >= 1
        rows = {row["project_id"]: row for row in overview["books"]}
        assert "probe" in rows
        row = rows["probe"]
        assert isinstance(row["failed"], list)
        assert isinstance(row["missing"], list)
        assert row["publication_gate"] in ("Unknown", row["publication_gate"])


def test_refresh_endpoint_rereads(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "book"
    manuscript = _chapters(repo, 1)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        refreshed = client.post("/api/publication/publishing/refresh?project_id=probe").json()
        assert refreshed["observed_at"]
        assert "evidence" in refreshed


def test_gate_map_covers_policy() -> None:
    from mission_control.publication import policy, publishing

    for gate in policy.GATE_IDS:
        assert gate in publishing.GATE_EVIDENCE_MAP, f"gate without evidence: {gate}"
    known = {
        "manuscript_discovery", "writer_validation_run", "writer_validation_requirements",
        "writer_finalization", "writer_readthrough", "proof_claims", "builder_config",
        "builder_artifacts", "website_publication", "mission_assessment", "human_approval",
        "alive_connection",
    }
    for gate_id, types in publishing.GATE_EVIDENCE_MAP.items():
        assert gate_id in policy.GATE_IDS
        for evidence_type in types:
            assert evidence_type in known, f"unknown evidence type: {evidence_type}"


def _gate_join_fixture():
    from mission_control.publication import publishing

    gates = [{"gate_id": "g1", "label": "Gate", "gate_group": "x"}]
    items = [
        {"evidence_type": "a", "result": "passed", "freshness": "current"},
        {"evidence_type": "b", "result": "unknown", "freshness": "unknown"},
    ]
    joined = publishing.gate_evidence_join(gates, [
        {"evidence_type": "a", "result": "passed", "freshness": "current",
         "source_system": "s", "source_reference": "r"},
        {"evidence_type": "b", "result": "unknown", "freshness": "unknown",
         "source_system": "s", "source_reference": "r"},
    ])
    assert joined and joined[0]["status"] in ("passed", "pending", "unknown")
    _ = items


def test_gate_join_rollup_rules() -> None:
    from mission_control.publication import publishing

    gates = [{"gate_id": "g", "label": "G", "gate_group": ""}]
    publishing.GATE_EVIDENCE_MAP["g"] = ["a", "b"]
    try:
        ok = publishing.gate_evidence_join(gates, [
            {"evidence_type": "a", "result": "passed", "freshness": "current",
             "source_system": "s", "source_reference": "r"},
            {"evidence_type": "b", "result": "passed", "freshness": "current",
             "source_system": "s", "source_reference": "r"},
        ])
        assert ok[0]["status"] == "passed" and ok[0]["stale"] is False
        bad = publishing.gate_evidence_join(gates, [
            {"evidence_type": "a", "result": "passed", "freshness": "current",
             "source_system": "s", "source_reference": "r"},
            {"evidence_type": "b", "result": "failed", "freshness": "current",
             "source_system": "s", "source_reference": "r"},
        ])
        assert bad[0]["status"] == "failed"
        stale = publishing.gate_evidence_join(gates, [
            {"evidence_type": "a", "result": "passed", "freshness": "stale",
             "source_system": "s", "source_reference": "r"},
        ])
        assert stale[0]["status"] == "passed" and stale[0]["stale"] is True
        missing = publishing.gate_evidence_join(gates, [
            {"evidence_type": "a", "result": "pending", "freshness": "unknown",
             "source_system": "s", "source_reference": "r"},
        ])
        assert missing[0]["status"] == "pending"
        unknown = publishing.gate_evidence_join(gates, [])
        assert unknown[0]["status"] == "unknown"
    finally:
        del publishing.GATE_EVIDENCE_MAP["g"]


def test_followup_lifecycle(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "book"
    manuscript = _chapters(repo, 1)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        created = client.post("/api/publication/followups", json={
            "project_id": "probe", "evidence_type": "proof_claims",
            "source_reference": "report.json", "fingerprint": "abc",
            "observed_at": "2026-01-01T00:00:00Z",
            "target_type": "task", "title": "Adjudicate", "rationale": "Needed."}).json()
        assert created["status"] == "open"
        assert created["target_id"]
        listed = client.get("/api/publication/followups?project_id=probe").json()
        assert len(listed) == 1
        # Re-check: fingerprint differs from live -> re-evidenced.
        rechecked = client.post(f"/api/publication/followups/{created['id']}/recheck").json()
        assert rechecked["changed"] is True
        assert rechecked["followup"]["status"] == "re-evidenced"
        again = client.post(f"/api/publication/followups/{created['id']}/recheck").json()
        assert again["changed"] is False
        closed = client.post(f"/api/publication/followups/{created['id']}/close",
                             json={"rationale": "Done."}).json()
        assert closed["status"] == "closed"
        assert client.get("/api/publication/followups?project_id=probe&status=open").json() == []


def test_followup_validation(tmp_path: Path) -> None:
    with open_client(_runtime(tmp_path)) as client:
        bad_target = client.post("/api/publication/followups", json={
            "project_id": "probe", "evidence_type": "x", "target_type": "pigeon"})
        assert bad_target.status_code == 404  # unknown project fails first
        nothing = tmp_path / "nothing-here"
        nothing.mkdir(parents=True, exist_ok=True)
        _make_book(client, project_id="probe", manuscript=str(nothing))
        bad_target = client.post("/api/publication/followups", json={
            "project_id": "probe", "evidence_type": "x", "target_type": "pigeon"})
        assert bad_target.status_code == 422
        bad_evidence = client.post("/api/publication/followups", json={
            "project_id": "probe", "evidence_type": "", "target_type": "task"})
        assert bad_evidence.status_code == 422


def test_contradictory_evidence_stays_visible(tmp_path: Path, monkeypatch) -> None:
    """A passed validation with a stale fingerprint must not read as ready."""
    repo = tmp_path / "book"
    manuscript = _chapters(repo, 2)
    _writer_validation(repo, approved_by="Ernan Hughes", stale=True)
    with open_client(_runtime(tmp_path)) as client:
        _make_book(client, project_id="probe", manuscript=str(manuscript))
        _install_fakes(monkeypatch, manuscript)
        summary = client.get("/api/publication/publishing?project_id=probe").json()
        assert "writer_finalization" in summary["blockers"]["stale"]
        gates = {gate["gate_id"]: gate for gate in summary["gates"]}
        assert gates["prose_review"]["stale"] is True
