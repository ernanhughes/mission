"""PUB-09B: governed chapter-improvement dispatch tests.

Hermetic: fixture manuscript, faked Writer registry + Worker transport.
No model calls, no manuscript writes outside tmp, no paid inference.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from helpers import open_client
from mission_control import models as orm
from mission_control.api import harness as harness_api
from mission_control.config import RuntimeSettings
from mission_control.publication import improvements as pubimp


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
    return base


def _manuscript(tmp_path: Path, count: int = 2) -> Path:
    root = tmp_path / "content" / "books" / "book"
    root.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        (root / f"{index:02d}-chapter.md").write_text(
            f"+++ title = \"Chapter {index}\" +++\n\nBody {index}.\n",
            encoding="utf-8")
    return root


def _definition(manuscript: Path):
    return SimpleNamespace(available=True, chapter_dir=str(manuscript),
                           title="Probe", chapter_count=2,
                           chapter_pattern="*.md", error="")


def _install(monkeypatch, manuscript: Path, project_id: str = "probe") -> None:
    import mission_control.writer_registry as registry_mod

    definition = _definition(manuscript)
    snapshot = SimpleNamespace(books={project_id: definition},
                               source_path="/tmp/x.yaml", errors=[])
    monkeypatch.setattr(registry_mod, "load_writer_registry",
                        lambda *args, **kwargs: snapshot)
    monkeypatch.setattr(registry_mod, "resolve_registry_path",
                        lambda *args, **kwargs: Path("/tmp/x.yaml"))
    monkeypatch.setattr(harness_api, "_worker_base",
                        lambda request: "http://127.0.0.1:7317")
    monkeypatch.setattr(pubimp, "run_writer_scan",
                        lambda kind, book, chapter, book_root=None: {
                            "available": True,
                            "summary": f"{kind} ok (fake, 0 findings)"})


def _make_project(client, project_id: str = "probe") -> None:
    response = client.post("/api/projects", json={
        "id": project_id, "name": "Probe", "kind": "book",
        "repository_path": "", "book_title": "Probe"})
    assert response.status_code == 201, response.text


CATALOGUE = {
    "strategies": {"strategies": [{"key": "direct.v1"}]},
    "models": {
        "approved": [{"id": "local-free", "model": "fixture",
                      "economic_tier": "free", "data_policy": "local_only"}],
        "policies": {"local-only": {"routes": ["local-free"],
                                    "required_data_policy": "local_only",
                                    "attempts_per_route": 1}},
    },
}


def _fake_transport(monkeypatch, worker_result: dict | None = None,
                    http_status: int = 200):
    calls = {"work": 0}

    async def fake_get(client, base, path):
        if path == "/v1/strategies":
            return CATALOGUE["strategies"]
        if path == "/v1/models/catalogue":
            return CATALOGUE["models"]
        raise AssertionError(path)

    class FakeResponse:
        status_code = http_status

        def json(self):
            return dict(worker_result or {})

    class AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json=None):
            calls["work"] += 1
            return FakeResponse()

    monkeypatch.setattr(harness_api, "_get", fake_get)
    monkeypatch.setattr(harness_api.httpx, "AsyncClient", AsyncClient)
    return calls


def _post(client, **overrides):
    body = {"project_id": "probe", "chapter_id": "01-chapter",
            "strategy": "targeted", "mode": "inspect",
            "max_budget_usd": 0, "actor": "Owner",
            "authorization_note": "Probe authorized improvement"}
    body.update(overrides)
    return client.post("/api/publication/improvements", json=body)


def test_inspect_prepares_without_dispatch_or_episode(tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        calls = _fake_transport(monkeypatch)
        response = _post(client)
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["status"] == "prepared"
        assert payload["dispatched"] is False
        assert calls["work"] == 0
        assert payload["packet"]["chapter"]["chapter_fingerprint"]
        from mission_control.persistence.db import Database
        database = Database(client.app.state.settings, target="test:probe")
        with database.session() as session:
            assert session.query(orm.WoEpisode).count() == 0
        database.dispose()


def test_validation_rejects_bad_input(tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        _fake_transport(monkeypatch)
        assert _post(client, project_id="nope").status_code == 404
        assert _post(client, chapter_id="99-chapter").status_code == 404
        assert _post(client, chapter_id="nope").status_code == 422
        assert _post(client, strategy="rewrite-everything").status_code == 422
        assert _post(client, mode="auto").status_code == 422
        assert _post(client, max_budget_usd=-1).status_code == 422
        assert _post(client, actor="").status_code == 422
        assert _post(client, actor="system").status_code == 422
        assert _post(client, authorization_note="short").status_code == 422


def test_paid_route_is_refused_not_merely_unbudgeted(tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)

        async def private_catalogue(_client, _base, path):
            if path == "/v1/strategies":
                return {"strategies": [{"key": "direct.v1"}]}
            return {"approved": [{"id": "paid-route", "model": "m",
                                  "economic_tier": "subscription",
                                  "data_policy": "private"}],
                    "policies": {"p": {"routes": ["paid-route"],
                                       "required_data_policy": "private",
                                       "attempts_per_route": 1}}}

        class NeverClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def post(self, *args, **kwargs):
                raise AssertionError("paid dispatch must never be attempted")

        monkeypatch.setattr(harness_api, "_get", private_catalogue)
        monkeypatch.setattr(harness_api.httpx, "AsyncClient", NeverClient)
        response = _post(client, mode="generate")
        assert response.status_code == 503, response.text


def test_worker_unavailable_is_503_not_empty(tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)

        async def down(_client, _base, _path):
            raise harness_api.HTTPException(status_code=503,
                                            detail="Worker is unavailable")

        monkeypatch.setattr(harness_api, "_get", down)
        response = _post(client, mode="generate")
        assert response.status_code == 503, response.text
        assert "unavailable" in response.text.lower()


def test_generate_persists_candidate_links_execution_and_preserves_source(
        tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    before = {p.name: p.read_bytes() for p in manuscript.glob("*.md")}
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        calls = _fake_transport(monkeypatch, worker_result={
            "request_id": "wrq_abcdef1234567890", "status": "AWAITING_ACCEPTANCE",
            "output": "# Chapter 1\n\nImproved body.\n",
            "usage": {"cost_usd": 0.0, "input_tokens": 10, "output_tokens": 5}})
        response = _post(client, mode="generate")
        assert response.status_code == 201, response.text
        record = response.json()["improvement"]
        assert record["status"] == "reported_complete"
        assert record["verification"]["status"] == "pending"
        assert record["cost_usd"] == 0.0
        assert record["envelope_id"].startswith("we:")
        assert calls["work"] == 1
        listed = client.get("/api/publication/improvements").json()
        assert listed["count"] == 1
        fetched = client.get(
            f"/api/publication/improvements/{record['id']}").json()
        assert fetched["improvement"]["source_current"] is True
        body = client.get(
            f"/api/publication/improvements/{record['id']}/body").json()
        assert body["available"] is True
        assert "Improved body" in body["markdown"]
        assert client.get("/api/publication/improvements/nope/body").status_code == 404
        from mission_control.persistence.db import Database
        database = Database(client.app.state.settings, target="test:probe2")
        with database.session() as session:
            links = session.query(orm.WoExecutionLink).all()
            assert len(links) == 1
            assert links[0].external_ref == "wrq_abcdef1234567890"
            assert links[0].route == "manual"
        database.dispose()
    after = {p.name: p.read_bytes() for p in manuscript.glob("*.md")}
    assert before == after


def test_preservation_warnings_flag_material_loss() -> None:
    """A whole-chapter rewrite that drops measurements, sections,
    front matter and repeats itself must not read as a clean pass — while
    still not being a hard failure (removal can be deliberate)."""
    from mission_control.publication import improvements as imp

    original = (
        "+++\ntitle = \"Chapter 25\"\nweight = 25\n+++\n\n"
        "# Chapter 25: Pipeline Budgets\n\n"
        "## The question\n\nWhy 185,445 claims and 31.87% baseline?\n\n"
        "## The build\n\nTwo stages at 50.91% and 5.7 points.\n\n"
        "## Limitations\n\nNone measured.\n"
    )
    repeated = ("The relation stage is the one stage this chapter could "
                "not run with a real provider at all.")
    candidate = (
        "```\n# Chapter 25: Pipeline Budgets\n\n"
        f"## Limitations\n\n{repeated}\n\n"
        f"## Limitations\n\n{repeated}\n```\n"
    )
    result = imp.deterministic_validation(candidate, original)
    assert result["passed"] is True  # warnings, not hard failures
    assert result["warning_count"] >= 4
    checks = {c["check"]: c for c in result["checks"]}
    assert checks["quantitative_preserved"]["result"] == "warn"
    assert checks["sections_preserved"]["result"] == "warn"
    assert checks["no_repetition"]["result"] == "warn"
    assert checks["front_matter_preserved"]["result"] == "warn"
    assert result["semantic"] == "pending"


def test_preservation_warnings_absent_for_faithful_edit() -> None:
    from mission_control.publication import improvements as imp

    original = (
        "+++\ntitle = \"X\"\n+++\n\n## The build\n\nWe measured 31.87%.\n"
    )
    candidate = (
        "+++\ntitle = \"X\"\n+++\n\n## The build\n\nWe measured 31.87% precisely.\n"
    )
    result = imp.deterministic_validation(candidate, original)
    assert result["passed"] is True
    assert result["warning_count"] == 0


def test_revalidate_rewrites_checks_without_touching_source(
        tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    before = {p.name: p.read_bytes() for p in manuscript.glob("*.md")}
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        _fake_transport(monkeypatch, worker_result={
            "request_id": "wrq_reval00000000001", "status": "ok",
            "output": "# Chapter 1\n\nRewritten entirely.\n", "usage": {}})
        created = _post(client, mode="generate").json()["improvement"]
        response = client.post(
            f"/api/publication/improvements/{created['id']}/revalidate")
        assert response.status_code == 200, response.text
        record = response.json()["improvement"]
        assert record["revalidated_at"]
        assert record["validation"]["passed"] is True
        missing = client.post("/api/publication/improvements/nope/revalidate")
        assert missing.status_code == 404
    after = {p.name: p.read_bytes() for p in manuscript.glob("*.md")}
    assert before == after


def test_ceiling_bound_response_is_incomplete_and_ineligible(
        tmp_path, monkeypatch) -> None:
    """A response that consumed the output ceiling is a truncated
    transformation. It stays readable, but it is not eligible."""
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        _fake_transport(monkeypatch, worker_result={
            "request_id": "wrq_ceiling000000001", "status": "AWAITING_ACCEPTANCE",
            "output": "# Chapter 1\n\nShort rewrite.\n",
            "strategy_execution": {"resources": {
                "requested_output_tokens": 2000,
                "observed_output_tokens": 1973}},
            "usage": {}})
        record = _post(client, mode="generate").json()["improvement"]
        assert record["status"] == "incomplete"
        assert record["eligible"] is False
        assert record["truncation"]["suspected"] is True
        assert "ceiling-bound" in record["note"]
        # still readable — honesty, not deletion
        body = client.get(
            f"/api/publication/improvements/{record['id']}/body").json()
        assert body["available"] is True


def test_complete_response_stays_eligible(tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        _fake_transport(monkeypatch, worker_result={
            "request_id": "wrq_complete00000001", "status": "AWAITING_ACCEPTANCE",
            "output": "# Chapter 1\n\nFull rewrite.\n",
            "strategy_execution": {"resources": {
                "requested_output_tokens": 2000,
                "observed_output_tokens": 400}},
            "usage": {}})
        record = _post(client, mode="generate").json()["improvement"]
        assert record["status"] == "reported_complete"
        assert record["eligible"] is True
        assert record["truncation"]["suspected"] is False


def test_replayed_submission_is_refused_before_second_side_effect(
        tmp_path, monkeypatch) -> None:
    """Same submission id must not create a second episode/objective and
    must not dispatch a second Worker request."""
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        calls = _fake_transport(monkeypatch, worker_result={
            "request_id": "wrq_replay0000000001", "status": "ok",
            "output": "# Chapter 1\n\nReplay body.\n", "usage": {}})
        first = _post(client, mode="generate", submission_id="replay-submission-1")
        assert first.status_code == 201, first.text
        second = _post(client, mode="generate", submission_id="replay-submission-1")
        assert second.status_code == 409, second.text
        assert "DUPLICATE_SUBMISSION" in second.text
        assert calls["work"] == 1
        from mission_control.persistence.db import Database
        database = Database(client.app.state.settings, target="test:replay")
        with database.session() as session:
            assert session.query(orm.WoEpisode).count() == 1
            assert session.query(orm.WoObjective).count() == 1
        database.dispose()


def test_listing_rejects_tampered_and_foreign_records(
        tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        _fake_transport(monkeypatch, worker_result={
            "request_id": "wrq_good000000000001", "status": "ok",
            "output": "# Chapter 1\n\nGenuine body.\n", "usage": {}})
        good = _post(client, mode="generate").json()["improvement"]

        from mission_control.persistence.db import Database  # noqa: F401
        from pathlib import Path as _P

        directory = _P(client.app.state.settings.data_dir) / "publication_candidates"
        # 1. tampered body: record says one thing, file another
        (directory / f"{good['id']}.md").write_text(
            "# Chapter 1\n\nInjected text.\n", encoding="utf-8")
        # 2. foreign record: kind not a requested execution
        import json as _json
        (directory / "wrq_foreign000000001.json").write_text(_json.dumps({
            "id": "wrq_foreign000000001", "kind": "something-else",
            "project_id": "probe", "chapter_id": "01-chapter"}), encoding="utf-8")
        # 3. record whose id does not match its file name
        (directory / "wrq_mismatch00000001.json").write_text(_json.dumps({
            "id": "wrq_different0000001", "kind": "requested-execution",
            "project_id": "probe", "chapter_id": "01-chapter"}), encoding="utf-8")

        listing = client.get("/api/publication/improvements").json()
        assert listing["count"] == 0
        assert listing["rejected_records"] == 3
        reasons = " ".join(r["reason"] for r in listing["rejections"])
        assert "fingerprint" in reasons
        assert "kind" in reasons
        assert "file name" in reasons
        body = client.get(
            f"/api/publication/improvements/{good['id']}/body")
        assert body.status_code == 404


def test_listing_includes_staleness_and_candidate_fingerprint(
        tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        _fake_transport(monkeypatch, worker_result={
            "request_id": "wrq_stale0000000002", "status": "ok",
            "output": "# Chapter 1\n\nFresh body.\n", "usage": {}})
        _post(client, mode="generate").json()
        listing = client.get("/api/publication/improvements").json()
        row = listing["improvements"][0]
        assert row["source_current"] is True
        assert row.get("candidate_fingerprint")
        (manuscript / "01-chapter.md").write_text(
            "# Chapter 1\n\nEdited later.\n", encoding="utf-8")
        listing = client.get("/api/publication/improvements").json()
        assert listing["improvements"][0]["source_current"] is False


def test_worker_failure_is_recorded_not_invented(tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        _fake_transport(monkeypatch, worker_result={}, http_status=500)
        response = _post(client, mode="generate")
        # A Worker failure is recorded (visible), never reported as a candidate
        # and never silently dropped.
        assert response.status_code == 201, response.text
        record = response.json()["improvement"]
        assert record["status"] == "failed"
        assert record["worker_http_status"] == 500
        assert record["verification"]["status"] == "pending"
        listed = client.get("/api/publication/improvements").json()
        assert listed["count"] == 1
        assert listed["improvements"][0]["status"] == "failed"
        body = client.get(f"/api/publication/improvements/{record['id']}/body").json()
        assert body["available"] is False


def test_stale_source_is_flagged_on_read(tmp_path, monkeypatch) -> None:
    manuscript = _manuscript(tmp_path)
    with open_client(_runtime(tmp_path)) as client:
        _make_project(client)
        _install(monkeypatch, manuscript)
        _fake_transport(monkeypatch, worker_result={
            "request_id": "wrq_stale0000000001", "status": "ok",
            "output": "text", "usage": {}})
        created = _post(client, mode="generate").json()["improvement"]
        assert created["status"] == "reported_complete"
        (manuscript / "01-chapter.md").write_text(
            "# Chapter 1\n\nEdited after dispatch.\n", encoding="utf-8")
        fetched = client.get(
            f"/api/publication/improvements/{created['id']}").json()
        assert fetched["improvement"]["source_current"] is False
