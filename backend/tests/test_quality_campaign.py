"""MC-QUALITY-03A: whole-book campaign contracts, durability and recovery."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mission_control.models import Book
from mission_control.persistence.db import Database
from mission_control.quality.service import (
    eligibility,
    resolve_book_root,
    run_campaign,
)
from mission_control.schemas import QualityEvaluationCreate

REPO = Path(__file__).resolve().parents[2]


def _chapter_text(title: str) -> str:
    return (
        "+++\n"
        f'title = "{title}"\n'
        "+++\n\n"
        f"Body text for {title}. One run can be fast but wrong.\n"
    )


def _make_book(client: TestClient, runtime, name: str = "fixture") -> str:
    root = Path(runtime.data_dir).parent / name
    (root).mkdir(parents=True, exist_ok=True)
    for number, title in (("01", "Alpha"), ("02", "Beta"), ("03", "Gamma")):
        (root / f"{number}-chapter.md").write_text(
            _chapter_text(title), encoding="utf-8"
        )
    database = Database(runtime)
    with database.session() as session:
        book = session.get(Book, "book-math")
        assert book is not None
        book.manuscript_paths = [str(root)]
        session.flush()
    return str(root)


def _dims(**overrides):
    base = {"clarity": 4, "argument": 4, "precision": 5, "economy": 3, "voice": 4, "structure": 4}
    base.update(overrides)
    return {
        name: {"dimension": name, "score": score, "evidence": "e", "evidence_validated": False}
        for name, score in base.items()
    }


def _eval_payload(chapter_id: str, revision: str, **overrides):
    body = {
        "project_id": "math",
        "book_id": "book-math",
        "chapter_id": chapter_id,
        "source_path": f"C:/books/{chapter_id}",
        "chapter_revision": revision,
        "status": "CURRENT",
        "overall": 4.0,
        "dimensions": _dims(),
        "execution": {"actual_model": "m", "status": "succeeded", "token_usage": "unknown"},
    }
    body.update(overrides)
    return body


def _hashes(root: str) -> dict[str, str]:
    out = {}
    for name in ("01-chapter.md", "02-chapter.md", "03-chapter.md"):
        data = (Path(root) / name).read_bytes().replace(b"\r\n", b"\n")
        out[name] = hashlib.sha256(data).hexdigest()
    return out


def test_discovery_lists_fixture_chapters(client: TestClient, runtime) -> None:
    root = _make_book(client, runtime)
    response = client.get("/api/quality/discovery?project_id=math")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [r["chapter_id"] for r in rows] == ["01-chapter.md", "02-chapter.md", "03-chapter.md"]
    assert rows[0]["title"] == "Alpha"
    assert rows[0]["eligibility"] == "missing"
    assert rows[0]["revision"] == _hashes(root)["01-chapter.md"]


def test_create_missing_campaign_selects_only_unevaluated(client: TestClient, runtime) -> None:
    root = _make_book(client, runtime)
    hashes = _hashes(root)
    client.post("/api/quality/evaluations", json=_eval_payload("01-chapter.md", hashes["01-chapter.md"]))
    created = client.post(
        "/api/quality/campaigns",
        json={"project_id": "math", "book_id": "book-math", "mode": "missing", "model": "m"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["chapter_selection"] == ["02-chapter.md", "03-chapter.md"]
    assert body["fingerprints"]["02-chapter.md"] == hashes["02-chapter.md"]
    assert body["status"] == "pending"
    assert body["remaining"] == 2


def test_duplicate_active_campaign_rejected(client: TestClient, runtime) -> None:
    _make_book(client, runtime)
    first = client.post("/api/quality/campaigns", json={"project_id": "math", "mode": "missing"})
    assert first.status_code == 201, first.text
    second = client.post("/api/quality/campaigns", json={"project_id": "math", "mode": "full"})
    assert second.status_code in (400, 409, 422)


def test_outdated_mode_targets_changed_source(client: TestClient, runtime) -> None:
    root = _make_book(client, runtime)
    hashes = _hashes(root)
    client.post("/api/quality/evaluations", json=_eval_payload("01-chapter.md", hashes["01-chapter.md"]))
    client.post("/api/quality/evaluations", json=_eval_payload("02-chapter.md", hashes["02-chapter.md"]))
    (Path(root) / "02-chapter.md").write_text(_chapter_text("Beta changed") + "More.\n", encoding="utf-8")
    created = client.post(
        "/api/quality/campaigns", json={"project_id": "math", "mode": "outdated", "model": "m"}
    )
    assert created.status_code == 201, created.text
    assert created.json()["chapter_selection"] == ["02-chapter.md"]


def test_selected_mode_rejects_unknown_chapters(client: TestClient, runtime) -> None:
    _make_book(client, runtime)
    response = client.post(
        "/api/quality/campaigns",
        json={"project_id": "math", "mode": "selected", "chapters": ["99-chapter.md"]},
    )
    assert response.status_code in (400, 422)


def _run_factory(runtime):
    database = Database(runtime)
    return database.session


def test_run_campaign_persists_and_skips_nothing_unless_done(client: TestClient, runtime) -> None:
    root = _make_book(client, runtime)
    hashes = _hashes(root)
    before = {name: (Path(root) / name).read_bytes() for name in hashes}
    created = client.post("/api/quality/campaigns", json={"project_id": "math", "mode": "missing", "model": "m"}).json()

    def evaluate_fn(chapter_id: str) -> dict:
        return {
            "status": "CURRENT",
            "overall": 4.0,
            "dimensions": _dims(),
            "source_path": str(Path(root) / chapter_id),
            "chapter_revision": hashes[chapter_id],
            "requested_model": "m",
            "actual_model": "m",
            "execution": {"actual_model": "m", "status": "succeeded", "token_usage": "unknown"},
        }

    record = run_campaign(_run_factory(runtime), created["id"], evaluate_fn)
    assert record.status == "completed"
    assert (record.completed, record.failed, record.remaining) == (3, 0, 0)
    assert record.usage == {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "failures": {}}
    for name, digest in before.items():
        assert (Path(root) / name).read_bytes() == digest  # no manuscript writes


def test_run_campaign_isolates_single_failure(client: TestClient, runtime) -> None:
    root = _make_book(client, runtime)
    hashes = _hashes(root)
    created = client.post("/api/quality/campaigns", json={"project_id": "math", "mode": "missing", "model": "m"}).json()

    def evaluate_fn(chapter_id: str) -> dict:
        if chapter_id == "02-chapter.md":
            raise RuntimeError("model exploded")
        return {
            "status": "CURRENT", "overall": 4.0, "dimensions": _dims(),
            "source_path": str(Path(root) / chapter_id), "chapter_revision": hashes[chapter_id],
            "requested_model": "m", "actual_model": "m",
            "execution": {"actual_model": "m", "status": "succeeded", "token_usage": "unknown"},
        }

    record = run_campaign(_run_factory(runtime), created["id"], evaluate_fn)
    assert record.status == "partial"
    assert (record.completed, record.failed) == (2, 1)
    assert "02-chapter.md" in dict(record.usage.get("failures", {}))
    assert "model exploded" in dict(record.usage.get("failures", {})).get("02-chapter.md", "")


def test_stop_then_resume_skips_completed(client: TestClient, runtime) -> None:
    root = _make_book(client, runtime)
    hashes = _hashes(root)
    created = client.post("/api/quality/campaigns", json={"project_id": "math", "mode": "missing", "model": "m"}).json()
    calls: list[str] = []

    def evaluate_fn(chapter_id: str) -> dict:
        calls.append(chapter_id)
        if len(calls) == 1:
            from mission_control.persistence.db import Database as Database_
            from mission_control.quality.service import stop_campaign

            database = Database_(runtime)
            with database.session() as session:
                stop_campaign(session, created["id"])
                session.commit()
        return {
            "status": "CURRENT", "overall": 4.0, "dimensions": _dims(),
            "source_path": str(Path(root) / chapter_id), "chapter_revision": hashes[chapter_id],
            "requested_model": "m", "actual_model": "m",
            "execution": {"actual_model": "m", "status": "succeeded", "token_usage": "unknown"},
        }

    record = run_campaign(_run_factory(runtime), created["id"], evaluate_fn)
    assert record.status == "partial"
    resumed = client.post(f"/api/quality/campaigns/{created['id']}/resume")
    assert resumed.status_code == 200
    record2 = run_campaign(_run_factory(runtime), created["id"], evaluate_fn)
    assert record2.status == "completed"
    assert sorted(set(calls)) == ["01-chapter.md", "02-chapter.md", "03-chapter.md"]


def test_run_endpoint_without_evaluator_blocks_transparently(client: TestClient, runtime) -> None:
    _make_book(client, runtime)
    created = client.post("/api/quality/campaigns", json={"project_id": "math", "mode": "selected", "chapters": ["01-chapter.md"], "model": "m"}).json()
    assert created["status"] == "pending"
    response = client.post(f"/api/quality/campaigns/{created['id']}/run")
    assert response.status_code == 200
    final = client.get(f"/api/quality/campaigns/{created['id']}").json()
    assert final["status"] == "partial"
    assert final["failed"] == 1
    failures = (final.get("usage") or {}).get("failures", {})
    assert "MISSION_CONTROL_QUALITY_EVAL_PYTHON" in failures.get("01-chapter.md", "")


def test_model_pinning_recorded_and_compared(client: TestClient, runtime) -> None:
    root = _make_book(client, runtime)
    hashes = _hashes(root)
    first = client.post("/api/quality/evaluations", json=_eval_payload("01-chapter.md", hashes["01-chapter.md"])).json()
    assert first["actual_model"] == "m"
    created = client.post(
        "/api/quality/campaigns", json={"project_id": "math", "mode": "missing", "model": "other"}
    ).json()
    # 01 has a current eval but under a different model: not comparable, so selected.
    # A same-model campaign would preserve it (covered by duplicate-guard below).
    assert created["chapter_selection"] == ["01-chapter.md", "02-chapter.md", "03-chapter.md"]
    same = client.post(
        "/api/quality/campaigns", json={"project_id": "math", "mode": "missing", "model": "m"}
    )
    assert same.status_code in (400, 409, 422)


def test_missing_mode_preserves_comparable_current(client: TestClient, runtime) -> None:
    root = _make_book(client, runtime)
    hashes = _hashes(root)
    client.post("/api/quality/evaluations", json=_eval_payload("01-chapter.md", hashes["01-chapter.md"]))
    created = client.post(
        "/api/quality/campaigns", json={"project_id": "math", "mode": "missing", "model": "m"}
    ).json()
    # 01 already has a comparable current result under the campaign model: preserved.
    assert created["chapter_selection"] == ["02-chapter.md", "03-chapter.md"]


def test_no_manuscript_writes_during_run(client: TestClient, runtime, tmp_path) -> None:
    root = _make_book(client, runtime, name="fixture-ro")
    hashes = _hashes(root)
    digest_before = {name: hashlib.sha256((Path(root) / name).read_bytes()).hexdigest() for name in hashes}
    created = client.post("/api/quality/campaigns", json={"project_id": "math", "mode": "missing", "model": "m"}).json()

    def evaluate_fn(chapter_id: str) -> dict:
        return {
            "status": "CURRENT", "overall": 4.0, "dimensions": _dims(),
            "source_path": str(Path(root) / chapter_id), "chapter_revision": hashes[chapter_id],
            "requested_model": "m", "actual_model": "m",
            "execution": {"actual_model": "m", "status": "succeeded", "token_usage": "unknown"},
        }

    run_campaign(_run_factory(runtime), created["id"], evaluate_fn)
    for name in hashes:
        assert hashlib.sha256((Path(root) / name).read_bytes()).hexdigest() == digest_before[name]
