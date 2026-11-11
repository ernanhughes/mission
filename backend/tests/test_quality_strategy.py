"""WRITER-QUALITY-01 Increment 04: strategy recorded per campaign and evaluation.

Additive tests only; existing quality contracts in test_quality.py and
test_quality_campaign.py are untouched.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from mission_control.quality.service import run_campaign
from test_quality_campaign import _dims, _make_book  # noqa: F401  (shared fixtures)


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


def test_campaign_strategy_round_trip(client: TestClient, runtime) -> None:
    _make_book(client, runtime)
    created = client.post(
        "/api/quality/campaigns",
        json={"project_id": "math", "mode": "full", "strategy": "bounded_judge"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["strategy"] == "bounded_judge"
    fetched = client.get(f"/api/quality/campaigns/{body['id']}")
    assert fetched.json()["strategy"] == "bounded_judge"


def test_campaign_strategy_defaults_to_direct(client: TestClient, runtime) -> None:
    _make_book(client, runtime)
    created = client.post(
        "/api/quality/campaigns", json={"project_id": "math", "mode": "full"}
    )
    assert created.status_code == 201, created.text
    assert created.json()["strategy"] == "direct"


def test_unknown_strategy_refused(client: TestClient, runtime) -> None:
    _make_book(client, runtime)
    created = client.post(
        "/api/quality/campaigns",
        json={"project_id": "math", "mode": "full", "strategy": "oracle"},
    )
    assert created.status_code in (400, 409, 422), created.text


def test_run_campaign_stamps_strategy_on_evaluations(
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
            "strategy": "deterministic",
        },
    )
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]
    database = Database(runtime)

    def evaluate_fn(chapter_id: str) -> dict:
        return {
            "status": "CURRENT",
            "overall": 4.0,
            "dimensions": _dims(),
            "source_path": f"C:/books/{chapter_id}",
            "chapter_revision": "rev-1",
            "execution": {"status": "succeeded", "token_usage": "unknown"},
        }

    run_campaign(database.session, campaign_id, evaluate_fn)
    evaluations = client.get(
        "/api/quality/evaluations",
        params={"project_id": "math", "chapter_id": "01-chapter.md"},
    ).json()
    assert len(evaluations) == 1
    assert evaluations[0]["strategy"] == "deterministic"


def test_evaluation_strategy_validated(client: TestClient, runtime) -> None:
    _make_book(client, runtime)
    bad = _eval_payload("01-chapter.md", "rev-1", strategy="oracle")
    response = client.post("/api/quality/evaluations", json=bad)
    assert response.status_code in (400, 404, 422), response.text


def test_campaign_usage_counts_cached_input_tokens(client: TestClient, runtime) -> None:
    from mission_control.persistence.db import Database

    _make_book(client, runtime)
    created = client.post(
        "/api/quality/campaigns",
        json={
            "project_id": "math",
            "mode": "selected",
            "chapters": ["01-chapter.md"],
            "strategy": "bounded_judge",
        },
    )
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]

    def evaluate_fn(chapter_id: str) -> dict:
        body = {
            "status": "CURRENT",
            "overall": None,
            "dimensions": {},
            "findings": [
                {"family": "clarity", "claim": "c",
                 "evidence_ids": ["a" * 20], "verification": "EXACT_MATCH"}
            ],
            "source_path": f"C:/books/{chapter_id}",
            "chapter_revision": "rev-1",
            "execution": {
                "transport": "writer-cli",
                "strategy": "bounded_judge",
                "usage": [
                    {"usage": {"input_tokens": 4, "cached_input_tokens": 12672,
                               "output_tokens": 18020},
                     "catalog_estimate_usd": 0.0109},
                    {"usage": {"input_tokens": 324, "output_tokens": 165},
                     "catalog_estimate_usd": 0.0001},
                ],
            },
        }
        return body

    run_campaign(Database(runtime).session, campaign_id, evaluate_fn)
    campaign = client.get(f"/api/quality/campaigns/{campaign_id}").json()
    assert campaign["status"] == "completed"
    assert campaign["usage"]["input_tokens"] == 4 + 12672 + 324
    assert campaign["usage"]["output_tokens"] == 18020 + 165
    assert campaign["usage"]["cost_usd"] == round(0.0109 + 0.0001, 4)
    assert campaign["costs_unknown"] is False
