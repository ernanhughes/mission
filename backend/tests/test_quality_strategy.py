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


def test_writer_runner_failure_is_blocked_not_faked(client: TestClient, runtime) -> None:
    import types
    from mission_control.api import quality as quality_api

    bogus = types.SimpleNamespace(
        writer_quality_runner="C:/nonexistent-python.exe | C:/nonexistent-repo | "
    )
    outcome = quality_api._writer_quality_evaluate(
        bogus, "C:/nonexistent", "01-chapter.md", "rev-1", "direct", "camp-1"
    )
    assert outcome is not None and outcome["status"] in ("BLOCKED", "ERROR")
    assert not outcome.get("findings"), "failures must not invent findings"


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
                    {"execution_id": "exec-seen-twice",
                     "usage": {"input_tokens": 4, "cached_input_tokens": 12672,
                               "output_tokens": 18020},
                     "catalog_estimate_usd": 0.0109},
                    {"execution_id": "exec-seen-twice",
                     "usage": {"input_tokens": 4, "cached_input_tokens": 12672,
                               "output_tokens": 18020},
                     "catalog_estimate_usd": 0.0109},
                    {"execution_id": "exec-no-cost",
                     "usage": {"input_tokens": 324, "output_tokens": 165}},
                ],
            },
        }
        return body

    run_campaign(Database(runtime).session, campaign_id, evaluate_fn)
    campaign = client.get(f"/api/quality/campaigns/{campaign_id}").json()
    assert campaign["status"] == "completed"
    # Duplicate sightings of one execution are counted once; missing cost
    # estimates keep costs_unknown true instead of inventing zero.
    assert campaign["usage"]["input_tokens"] == 4 + 12672 + 324
    assert campaign["usage"]["output_tokens"] == 18020 + 165
    assert campaign["usage"]["cost_usd"] == round(0.0109, 4)
    assert campaign["costs_unknown"] is True

def test_campaign_budget_cap_skips_remaining(client: TestClient, runtime) -> None:
    from mission_control.persistence.db import Database
    from test_quality_campaign import _make_book as _mk, _dims as _d

    _mk(client, runtime)
    created = client.post(
        "/api/quality/campaigns",
        json={
            "project_id": "math",
            "mode": "selected",
            "chapters": ["01-chapter.md", "02-chapter.md"],
            "strategy": "direct",
            "max_cost_usd": 0.0005,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["max_cost_usd"] == 0.0005
    campaign_id = created.json()["id"]

    def evaluate_fn(chapter_id: str) -> dict:
        return {
            "status": "CURRENT",
            "overall": None,
            "dimensions": {},
            "findings": [{"family": "clarity", "claim": "c"}],
            "source_path": f"C:/books/{chapter_id}",
            "chapter_revision": "rev-1",
            "execution": {
                "transport": "writer-cli",
                "strategy": "direct",
                "usage": [{"execution_id": f"exec-{chapter_id}",
                           "catalog_estimate_usd": 0.001}],
            },
        }

    run_campaign(Database(runtime).session, campaign_id, evaluate_fn)
    campaign = client.get(f"/api/quality/campaigns/{campaign_id}").json()
    assert campaign["status"] == "partial"
    assert campaign["completed"] == 1
    assert campaign["remaining"] == 0
    assert "budget exhausted" in (campaign["error"] or "")

def test_compare_campaigns_reports_presence_without_claiming_fixes(client: TestClient, runtime) -> None:
    from mission_control.persistence.db import Database
    from test_quality_campaign import _make_book as _mk

    _mk(client, runtime)

    def fake_eval(payload_claims, strategy="direct"):
        def evaluate_fn(chapter_id: str) -> dict:
            return {
                "status": "CURRENT",
                "overall": None,
                "dimensions": {},
                "findings": [
                    {"family": "clarity", "claim": claim} for claim in payload_claims
                ],
                "source_path": f"C:/books/{chapter_id}",
                "chapter_revision": "rev-1",
                "execution": {"transport": "writer-cli", "strategy": strategy},
            }

        return evaluate_fn

    first = client.post(
        "/api/quality/campaigns",
        json={"project_id": "math", "mode": "selected",
              "chapters": ["01-chapter.md"], "strategy": "direct"},
    ).json()
    run_campaign(Database(runtime).session, first["id"], fake_eval(["same issue", "old issue"]))
    second = client.post(
        "/api/quality/campaigns",
        json={"project_id": "math", "mode": "selected",
              "chapters": ["01-chapter.md"], "strategy": "bounded_judge"},
    ).json()
    run_campaign(Database(runtime).session, second["id"], fake_eval(["same issue", "new issue"], "bounded_judge"))

    diff = client.get(
        "/api/quality/campaigns/compare",
        params={"first_id": first["id"], "second_id": second["id"]},
    )
    assert diff.status_code == 200, diff.text
    body = diff.json()
    assert body["still_present"] == 1
    assert body["new_in_second"] == 1
    assert body["not_detected_in_second"] == 1
    assert body["same_strategy"] is False
    assert "not a fix" in body["note"]
