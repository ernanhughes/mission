"""WRITER-QUALITY-02: Writer-commanded execution, findings records, reviews."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mission_control.quality.service import run_campaign
from test_quality_campaign import _dims, _make_book  # noqa: F401


def _writer_payload(chapter_id: str, revision: str, **overrides):
    body = {
        "project_id": "math",
        "book_id": "book-math",
        "chapter_id": chapter_id,
        "status": "CURRENT",
        "overall": None,
        "dimensions": {},
        "findings": [
            {
                "family": "clarity",
                "dimension": "clarity",
                "claim": "Lease term ambiguous.",
                "evidence_ids": ["a" * 20],
                "verification": "EXACT_MATCH",
            }
        ],
        "uncertainty": "",
        "limitations": [],
        "execution": {
            "transport": "writer-cli",
            "strategy": "direct",
            "run_id": "run-1",
            "worker_tasks": 1,
            "usage": [
                {
                    "execution_id": "model-exec-1",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                    "catalog_estimate_usd": 0.001,
                }
            ],
            "source_fingerprint": "f" * 64,
        },
        "requested_model": "writer-quality/direct",
        "source_path": f"C:/books/{chapter_id}",
        "chapter_revision": revision,
    }
    body.update(overrides)
    return body


def test_writer_findings_observation_accepted_without_scores(
    client: TestClient, runtime
) -> None:
    _make_book(client, runtime)
    response = client.post(
        "/api/quality/evaluations", json=_writer_payload("01-chapter.md", "rev-1")
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["overall"] is None
    assert body["dimensions"] == {}
    assert body["strategy"] == "direct"
    assert len(body["findings"]) == 1


def test_writer_findings_require_family_and_claim(
    client: TestClient, runtime
) -> None:
    _make_book(client, runtime)
    bad = _writer_payload("01-chapter.md", "rev-1")
    bad["findings"] = [{"claim": "no family"}]
    response = client.post("/api/quality/evaluations", json=bad)
    assert response.status_code in (400, 404, 422), response.text


def test_scorer_guard_intact_for_non_writer_records(
    client: TestClient, runtime
) -> None:
    _make_book(client, runtime)
    bad = _writer_payload("01-chapter.md", "rev-1")
    bad["execution"] = {"transport": "other"}
    response = client.post("/api/quality/evaluations", json=bad)
    assert response.status_code in (400, 404, 422), response.text


def test_run_campaign_records_writer_usage_once(
    client: TestClient, runtime
) -> None:
    from mission_control.persistence.db import Database

    _make_book(client, runtime)
    created = client.post(
        "/api/quality/campaigns",
        json={
            "project_id": "math",
            "mode": "selected",
            "chapters": ["01-chapter.md"],
            "strategy": "direct",
        },
    )
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]
    run_campaign(
        Database(runtime).session,
        campaign_id,
        lambda chapter: _writer_payload(chapter, "rev-1"),
    )
    campaign = client.get(f"/api/quality/campaigns/{campaign_id}").json()
    assert campaign["status"] == "completed"
    assert campaign["usage"]["input_tokens"] == 10
    assert campaign["usage"]["output_tokens"] == 5
    assert campaign["usage"]["cost_usd"] == 0.001
    evaluations = client.get(
        "/api/quality/evaluations",
        params={"project_id": "math", "chapter_id": "01-chapter.md"},
    ).json()
    assert evaluations[0]["execution"]["usage"][0]["execution_id"] == "model-exec-1"


def test_review_lifecycle_preserves_finding(client: TestClient, runtime) -> None:
    _make_book(client, runtime)
    created = client.post(
        "/api/quality/evaluations", json=_writer_payload("01-chapter.md", "rev-1")
    )
    assert created.status_code == 201, created.text
    evaluation = created.json()

    listed = client.get(f"/api/quality/evaluations/{evaluation['id']}/reviews").json()
    assert listed == []

    review = client.post(
        f"/api/quality/evaluations/{evaluation['id']}/reviews",
        json={
            "evaluation_id": evaluation["id"],
            "finding_id": "Q-" + "0" * 16,
            "decision": "ACCEPT",
            "reason": "Useful catch.",
            "reviewer": "author",
        },
    )
    assert review.status_code == 201, review.text
    body = review.json()
    assert body["decision"] == "ACCEPT"
    assert body["source_digest"] == "rev-1"
    assert body["source_status"] == "CURRENT"

    listed = client.get(f"/api/quality/evaluations/{evaluation['id']}/reviews").json()
    assert len(listed) == 1
    # The finding itself is untouched by the review.
    reread = client.get(f"/api/quality/evaluations/{evaluation['id']}").json()
    assert len(reread["findings"]) == 1

    bad = client.post(
        f"/api/quality/evaluations/{evaluation['id']}/reviews",
        json={
            "evaluation_id": evaluation["id"],
            "finding_id": "Q-" + "0" * 16,
            "decision": "MAYBE",
        },
    )
    assert bad.status_code in (400, 404, 422), bad.text


RUNNER_ENV = "MISSION_CONTROL_WRITER_QUALITY_RUNNER"
needs_runner = pytest.mark.skipif(
    not os.environ.get(RUNNER_ENV),
    reason=f"{RUNNER_ENV} not configured (live Writer CLI path)",
)


def _duplicate_book(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "01-chapter.md").write_text(
        "+++\ntitle = \"Pilot\"\n+++\n\n# Pilot\n\nSame paragraph twice.\n\nSame paragraph twice.\n",
        encoding="utf-8",
    )


@needs_runner
def test_writer_commanded_deterministic_campaign_end_to_end(
    client: TestClient, runtime
) -> None:
    """Mission -> Writer CLI -> record -> review, no model, real processes."""
    from mission_control.models import Book
    from mission_control.persistence.db import Database

    book_root = Path(runtime.data_dir).parent / "writer-pilot"
    _duplicate_book(book_root)
    before = (book_root / "01-chapter.md").read_bytes()
    database = Database(runtime)
    with database.session() as session:
        book = session.get(Book, "book-math")
        assert book is not None
        book.manuscript_paths = [str(book_root)]
        session.flush()
    created = client.post(
        "/api/quality/campaigns",
        json={
            "project_id": "math",
            "mode": "selected",
            "chapters": ["01-chapter.md"],
            "strategy": "deterministic",
        },
    )
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]
    assert created.json()["strategy"] == "deterministic"

    def evaluate_fn(chapter_id: str) -> dict:
        from mission_control.api.quality import _writer_quality_evaluate

        return _writer_quality_evaluate(
            runtime, str(book_root), chapter_id, "rev-x", "deterministic",
            campaign_id,
        ) or {"status": "BLOCKED", "error": "runner unconfigured"}

    run_campaign(database.session, campaign_id, evaluate_fn)
    campaign = client.get(f"/api/quality/campaigns/{campaign_id}").json()
    assert campaign["status"] == "completed", campaign
    evaluations = client.get(
        "/api/quality/evaluations",
        params={"project_id": "math", "chapter_id": "01-chapter.md"},
    ).json()
    assert len(evaluations) == 1
    evaluation = evaluations[0]
    assert evaluation["strategy"] == "deterministic"
    assert evaluation["overall"] is None
    assert any(f["family"] == "redundancy" for f in evaluation["findings"])
    # Restart survival: a fresh handle on the same data dir sees the record.
    fresh = Database(runtime)
    with fresh.session() as session:
        from mission_control.quality.service import get_evaluation

        assert get_evaluation(session, evaluation["id"]).chapter_id == "01-chapter.md"
    # Review round-trip on the recorded finding.
    finding_id = evaluation["findings"][0].get("finding_id") or "Q-" + "0" * 16
    review = client.post(
        f"/api/quality/evaluations/{evaluation['id']}/reviews",
        json={
            "evaluation_id": evaluation["id"],
            "finding_id": finding_id,
            "decision": "ACCEPT",
            "reviewer": "author",
        },
    )
    assert review.status_code == 201, review.text
    assert review.json()["decision"] == "ACCEPT"
    # No manuscript modification at any point.
    assert (book_root / "01-chapter.md").read_bytes() == before
