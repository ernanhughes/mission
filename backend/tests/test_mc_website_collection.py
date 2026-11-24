"""BLOG-01 D4: website collection quality map (read-only).

Focused collection tests (fixture/tmp data, no live models: the fake
evaluator from the posts suite stands in for Pi) plus regression cover for
the touched areas. The builder under test performs zero writes: one test
asserts DB row counts are unchanged.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from helpers import open_client
from mission_control.config import RuntimeSettings
from mission_control.models import WebsitePostEvaluation, WebsitePostReview

SITE_ID = "website-programmer-ie"

SHARED_PASSAGE = (
    "The shared verbatim passage for duplication tracing spans well over forty characters."
)
assert len(SHARED_PASSAGE) >= 40


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


def _hugo_site(root: Path) -> Path:
    site = root / "programmer.ie"
    (site / "content" / "post").mkdir(parents=True, exist_ok=True)
    (site / "layouts").mkdir(parents=True, exist_ok=True)
    (site / "hugo.toml").write_text(
        'baseURL = "http://example.test/"\ntitle = "Programmer.ie"\n'
        '[params]\npostSections = ["post"]\n',
        encoding="utf-8",
    )
    return site


def _post(
    path: Path,
    name: str,
    body: str = "Body text for the article under test.",
    *,
    date: str | None = "2026-01-05T10:00:00+00:00",
    draft: bool = False,
) -> None:
    lines = ["+++", f'title = "{name}"']
    if date is not None:
        lines.append(f'date = "{date}"')
    if draft:
        lines.append("draft = true")
    lines += ["+++", "", body]
    path.write_text("\n".join(lines), encoding="utf-8")


def _site_with_posts(root: Path) -> Path:
    site = _hugo_site(root)
    post = site / "content" / "post"
    now = datetime.now(timezone.utc)
    _post(post / "alpha.md", "Alpha", date=(now - timedelta(days=1)).isoformat())
    _post(post / "beta.md", "Beta", date=(now - timedelta(days=2)).isoformat())
    _post(post / "draft.md", "Draft", draft=True)
    future = (now + timedelta(days=30)).isoformat()
    _post(post / "future.md", "Future", date=future)
    _post(post / "mystery.md", "Mystery", date=None)
    bundle = post / "bundle"
    bundle.mkdir(exist_ok=True)
    _post(bundle / "index.md", "Bundle", date="2024-03-10T10:00:00Z")
    return site


def _scores_for(total: int) -> dict[str, int]:
    table = {
        800: {
            "thesis_purpose": 120,
            "substance_depth": 140,
            "argument_reasoning": 120,
            "evidence_attribution": 120,
            "structure_flow": 80,
            "clarity_precision": 80,
            "reader_value": 80,
            "style_economy": 60,
        },
        500: {
            "thesis_purpose": 75,
            "substance_depth": 87,
            "argument_reasoning": 75,
            "evidence_attribution": 75,
            "structure_flow": 50,
            "clarity_precision": 50,
            "reader_value": 50,
            "style_economy": 38,
        },
        900: {
            "thesis_purpose": 135,
            "substance_depth": 157,
            "argument_reasoning": 135,
            "evidence_attribution": 135,
            "structure_flow": 90,
            "clarity_precision": 90,
            "reader_value": 90,
            "style_economy": 68,
        },
    }
    assert sum(table[total].values()) == total
    return dict(table[total])


def _fake_evaluator_factory(
    quotes: dict[str, str] | None = None, totals: dict[str, int] | None = None
):
    totals = totals or {}
    quotes = quotes or {}

    def _run(**kwargs):
        from mission_control.websites import rubric as _rubric

        title = kwargs.get("title", "")
        total = totals.get(title, 800)
        scores = _scores_for(total)
        quote = quotes.get(title)
        return {
            "status": "CURRENT",
            "overall": total,
            "scores": scores,
            "explanations": {key: f"Why {key}." for key in scores},
            "assessment": "Fake assessment.",
            "strengths": ["s1"],
            "weaknesses": ["w1"],
            "improvements": [
                {
                    "rank": 1,
                    "title": "Fix",
                    "problem": "p",
                    "why_it_matters": "w",
                    "suggestion": "s",
                    "source_heading": None,
                    "source_quote": quote,
                },
            ],
            "findings": [],
            "uncertainty": "",
            "limitations": [],
            "actual_model": "fake-model",
            "execution": {"transport": "fake"},
            "rubric_check": _rubric.RUBRIC_ID,
        }

    return _run


def _evaluate(client, identity: str):
    response = client.post(f"/api/websites/{SITE_ID}/posts/{identity}/evaluate", json={})
    assert response.status_code == 200, response.text
    return response.json()


def _collection(client, site: Path, **kwargs):
    from mission_control.websites import collection as coll

    with client.app.state.database.session() as session:
        return coll.build_collection_quality_map(
            session, website_id=SITE_ID, blog_dir=site / "content" / "post", **kwargs
        )


def _row_counts(client) -> tuple[int, int]:
    with client.app.state.database.session() as session:
        evals = session.scalar(select(func.count()).select_from(WebsitePostEvaluation))
        reviews = session.scalar(select(func.count()).select_from(WebsitePostReview))
    return evals, reviews


# ------------------------------------------------------- counts + coverage


def test_collection_counts_and_coverage(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", _fake_evaluator_factory())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        before = _collection(client, site)
        assert before["schema"] == "site-collection-quality.v1"
        assert before["inventory"] == {
            "discovered": 6,
            "published": 3,
            "draft": 1,
            "scheduled": 1,
            "unknown": 1,
        }
        assert before["coverage"]["published"] == 3
        assert before["coverage"]["evaluated_current"] == 0
        assert before["coverage"]["evaluated_stale"] == 0
        assert before["coverage"]["unevaluated"] == 3
        assert before["coverage"]["coverage_percent"] == 0.0
        assert before["scores"]["average"] is None
        assert before["scores"]["min"] is None and before["scores"]["max"] is None
        assert before["scores"]["weakest"] == []
        assert before["scores"]["n_scored"] == 0

        _evaluate(client, "alpha.md")
        _evaluate(client, "beta.md")
        after = _collection(client, site)
        assert after["coverage"]["evaluated_current"] == 2
        assert after["coverage"]["evaluated_stale"] == 0
        assert after["coverage"]["unevaluated"] == 1
        assert after["coverage"]["coverage_percent"] == pytest.approx(200 / 3)


# --------------------------------------- single-rubric distributions


def test_collection_scores_single_rubric_only(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _site_with_posts(tmp_path / "websites")
    totals = {"Alpha": 800, "Beta": 500, "Bundle": 900}
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", _fake_evaluator_factory(totals=totals))
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        _evaluate(client, "alpha.md")
        _evaluate(client, "beta.md")
        _evaluate(client, "bundle")
        # A blocked attempt carries no scores and must not enter the average.
        monkeypatch.setattr(
            eval_mod,
            "run_pi_evaluation",
            lambda **kwargs: {"status": "BLOCKED", "error": "no model"},
        )
        blocked = client.post(
            f"/api/websites/{SITE_ID}/posts/alpha.md/evaluate", json={"force": True}
        )
        assert blocked.status_code == 200
        # A foreign-rubric row must never merge into blog-editorial-v1 stats.
        with client.app.state.database.session() as session:
            session.add(
                WebsitePostEvaluation(
                    id="wpe-foreign-1",
                    website_id=SITE_ID,
                    article_identity="beta.md",
                    relpath="beta.md",
                    content_sha256="0" * 64,
                    rubric_id="foreign-rubric-v9",
                    rubric_version=9,
                    status="CURRENT",
                    overall=100.0,
                )
            )
            session.commit()
        collection = _collection(client, site)
        scores = collection["scores"]
        assert scores["rubric_id"] == "blog-editorial-v1"
        assert scores["n_scored"] == 3
        assert scores["average"] == pytest.approx((800 + 500 + 900) / 3)
        assert scores["min"] == 500.0 and scores["max"] == 900.0
        assert [w["identity"] for w in scores["weakest"]] == ["beta.md", "alpha.md", "bundle"]
        assert scores["weakest"][0]["overall"] == 500.0
        assert scores["excluded"]["non_current_status"] >= 1  # the BLOCKED row
        assert scores["excluded"]["other_rubric"] == 1
        assert scores["excluded"]["stale_or_superseded"] == 0

        top2 = _collection(client, site, weakest_n=2)
        assert [w["identity"] for w in top2["scores"]["weakest"]] == ["beta.md", "alpha.md"]


# ------------------------------------------------------- ageing queues


def test_collection_review_queues_oldest_first(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", _fake_evaluator_factory())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        first = _evaluate(client, "alpha.md")
        # Editing the file flips the editorial assessment to stale.
        (site / "content" / "post" / "alpha.md").write_text(
            '+++\ntitle = "Alpha"\ndate = "2026-01-05T10:00:00+00:00"\n+++\n\nEdited body.\n',
            encoding="utf-8",
        )
        collection = _collection(client, site)
        assert collection["coverage"]["evaluated_stale"] == 1
        assert collection["coverage"]["evaluated_current"] == 0
        stale = collection["review_queues"]["stale_oldest_first"]
        assert [entry["identity"] for entry in stale] == ["alpha.md"]
        assert stale[0]["evaluation_id"] == first["id"]
        assert stale[0]["evaluated_digest"] == first["content_sha256"]
        assert stale[0]["live_digest"] != first["content_sha256"]
        # Stale rows never enter the single-rubric average.
        assert collection["scores"]["n_scored"] == 0
        assert collection["scores"]["excluded"]["stale_or_superseded"] == 1
        unevaluated = collection["review_queues"]["unevaluated_oldest_first"]
        # Oldest post date first: bundle (2024) before beta (2 days ago).
        assert [entry["identity"] for entry in unevaluated] == ["bundle", "beta.md"]
        assert all("evaluation_id" not in entry for entry in unevaluated)


# --------------------------------------- duplication traceability


def test_collection_duplication_shared_title(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    post = site / "content" / "post"
    _post(post / "one.md", "Same Title", date="2026-01-04T10:00:00+00:00")
    _post(post / "two.md", "  same   TITLE ", date="2026-01-03T10:00:00+00:00")
    _post(post / "other.md", "Different", date="2026-01-02T10:00:00+00:00")
    with open_client(_runtime(tmp_path)) as client:
        collection = _collection(client, site)
    titles = [c for c in collection["duplication_candidates"] if c["kind"] == "shared_title"]
    assert len(titles) == 1
    candidate = titles[0]
    assert candidate["decision"] == "pending"
    assert candidate["evidence"]["normalized_title"] == "same title"
    identities = {p["identity"] for p in candidate["evidence"]["posts"]}
    assert identities == {"one.md", "two.md"}
    for member in candidate["evidence"]["posts"]:
        assert (
            member["relpath"] and member["content_sha256"] and len(member["content_sha256"]) == 64
        )


def test_collection_duplication_shared_quote(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _hugo_site(tmp_path / "websites")
    post = site / "content" / "post"
    body = f"Intro line.\n\n{SHARED_PASSAGE}\n\nTrailing line.\n"
    _post(post / "alpha.md", "Alpha", body=body, date="2026-01-04T10:00:00+00:00")
    _post(post / "beta.md", "Beta", body=body, date="2026-01-03T10:00:00+00:00")
    _post(
        post / "gamma.md",
        "Gamma",
        body="Unrelated body text here.",
        date="2026-01-02T10:00:00+00:00",
    )
    quotes = {"Alpha": SHARED_PASSAGE, "Beta": SHARED_PASSAGE, "Gamma": None}
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", _fake_evaluator_factory(quotes=quotes))
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        _evaluate(client, "alpha.md")
        _evaluate(client, "beta.md")
        _evaluate(client, "gamma.md")
        collection = _collection(client, site)
    quotes_found = [c for c in collection["duplication_candidates"] if c["kind"] == "shared_quote"]
    assert len(quotes_found) == 1
    candidate = quotes_found[0]
    assert candidate["decision"] == "pending"
    assert SHARED_PASSAGE in candidate["evidence"]["quote"]
    assert len(candidate["evidence"]["digest"]) == 64
    identities = {p["identity"] for p in candidate["evidence"]["posts"]}
    assert identities == {"alpha.md", "beta.md"}
    for member in candidate["evidence"]["posts"]:
        assert member["evaluation_id"] and member["finding_id"]
        assert member["content_sha256"] and len(member["content_sha256"]) == 64


def test_collection_no_duplication_without_shared_evidence(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", _fake_evaluator_factory())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        _evaluate(client, "alpha.md")
        _evaluate(client, "beta.md")
        collection = _collection(client, site)
    # Default fixture quotes are short (<40 chars) and titles distinct.
    assert collection["duplication_candidates"] == []


# ------------------------------------------------------- provisional gating


def test_collection_provisional_sections_unavailable(tmp_path: Path) -> None:
    site = _site_with_posts(tmp_path / "websites")
    with open_client(_runtime(tmp_path)) as client:
        collection = _collection(client, site)
    for key in ("contradictions", "topic_gaps", "outdated_claims"):
        section = collection["provisional"][key]
        assert section["status"] == "unavailable"
        assert isinstance(section["reason"], str) and len(section["reason"]) > 20
    assert "paired" in collection["provisional"]["contradictions"]["reason"]
    assert collection["duplication_unmapped"] == []


# ------------------------------------------------------- read-only + regression


def test_collection_builder_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", _fake_evaluator_factory())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        _evaluate(client, "alpha.md")
        before = _row_counts(client)
        files_before = sorted(p.name for p in (site / "content" / "post").iterdir())
        _collection(client, site)
        _collection(client, site, weakest_n=1)
        assert _row_counts(client) == before
        assert sorted(p.name for p in (site / "content" / "post").iterdir()) == files_before


def test_collection_summary_endpoint_unchanged(tmp_path: Path, monkeypatch) -> None:
    """Regression: per-post summary contract still holds alongside D4."""
    import mission_control.websites.evaluate as eval_mod

    _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", _fake_evaluator_factory())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        base = f"/api/websites/{SITE_ID}"
        summary = client.get(base + "/posts/summary").json()
        assert summary["published"] == 3 and summary["evaluated_current"] == 0
        client.post(base + "/posts/alpha.md/evaluate", json={})
        summary = client.get(base + "/posts/summary").json()
        assert summary["evaluated_current"] == 1
        assert summary["average_denominator"] == 1
        assert summary["rubric_id"] == "blog-editorial-v1"
        listed = client.get(base + "/posts?limit=200").json()
        assert listed["total"] == 6
        assert listed["published"] == 3
