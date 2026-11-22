"""MC-WEBSITES-POSTS-01: blog-post listing, rubric, evaluation history, reviews.

All AI execution is faked: no test may invoke a real model. The pilot (real
execution against the two newest articles) is a manual, explicitly authorized
step outside this suite.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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


def _hugo_site(root: Path) -> Path:
    site = root / "programmer.ie"
    (site / "content" / "post").mkdir(parents=True, exist_ok=True)
    (site / "layouts").mkdir(parents=True, exist_ok=True)
    (site / "hugo.toml").write_text(
        'baseURL = "http://example.test/"\ntitle = "Programmer.ie"\n'
        '[params]\npostSections = ["post"]\n', encoding="utf-8")
    return site


def _post(path: Path, name: str, *, date: str | None = "2026-01-05T10:00:00+00:00",
          draft: bool = False) -> None:
    lines = ["+++", f'title = "{name}"']
    if date is not None:
        lines.append(f'date = "{date}"')
    if draft:
        lines.append("draft = true")
    lines += ["+++", "", "Body text for the article under test."]
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


def _outcome(**overrides):
    scores = {"thesis_purpose": 120, "substance_depth": 140, "argument_reasoning": 120,
              "evidence_attribution": 120, "structure_flow": 80, "clarity_precision": 80,
              "reader_value": 80, "style_economy": 60}
    base = {
        "status": "CURRENT",
        "overall": 800,
        "scores": scores,
        "explanations": {key: f"Why {key}." for key in scores},
        "assessment": "Solid technical article with room to sharpen the thesis.",
        "strengths": ["Clear examples", "Honest scope", "Good pacing"],
        "weaknesses": ["Thin evidence", "Weak ending", "Jargon"],
        "improvements": [
            {"rank": 1, "title": "Sharpen thesis", "problem": "Vague claim",
             "why_it_matters": "Focus", "suggestion": "State it upfront",
             "source_heading": "Intro", "source_quote": "Body text for the article under test."},
            {"rank": 2, "title": "Add data", "problem": "No numbers",
             "why_it_matters": "Trust", "suggestion": "Add a table",
             "source_heading": None, "source_quote": None},
            {"rank": 3, "title": "Cut filler", "problem": "Repeats",
             "why_it_matters": "Economy", "suggestion": "Delete paragraph two",
             "source_heading": None, "source_quote": None},
        ],
        "findings": [{"finding_id": "f1", "kind": "observation", "title": "Note",
                      "detail": "Worth a follow-up.",
                      "source_heading": "Intro",
                      "source_quote": "Body text for the article under test."}],
        "uncertainty": "Whether readers share the premise.",
        "limitations": ["Single-model review, no external verification."],
        "actual_model": "fake-model",
        "execution": {"transport": "fake"},
    }
    base.update(overrides)
    return base


# ------------------------------------------------------- rubric


def test_rubric_weights_sum_to_1000() -> None:
    from mission_control.websites import rubric

    assert sum(dim.max_points for dim in rubric.DIMENSIONS) == 1000
    assert rubric.RUBRIC_ID == "blog-editorial-v1"
    assert len({dim.id for dim in rubric.DIMENSIONS}) == 8


def test_rubric_rejects_bad_scores() -> None:
    from mission_control.websites import rubric

    total, _cleaned, errors = rubric.validate_scores(dict(_outcome()["scores"]))
    assert errors == []
    assert total == 800
    _total, _c, bad = rubric.validate_scores({"thesis_purpose": 999})
    assert bad  # out of range
    _total, _c, unknown = rubric.validate_scores({"nope": 5, **_outcome()["scores"]})
    assert unknown  # unknown dimension, never silently dropped
    _total, _c, missing = rubric.validate_scores({"thesis_purpose": 10})
    assert missing  # missing dimensions reported


def test_quote_anchoring() -> None:
    from mission_control.websites import rubric

    assert rubric.quote_anchored("Body text here.", "Body  text\nhere.")
    assert not rubric.quote_anchored("Body text here.", "Invented passage.")


# ------------------------------------------------------- listing


def test_posts_list_counts_match_cultivation(tmp_path: Path) -> None:
    from mission_control.cultivation.sources import blog_observation, scan_hugo_blog

    site = _site_with_posts(tmp_path / "websites")
    blog_dir = site / "content" / "post"
    scan = scan_hugo_blog(blog_dir)
    observed = blog_observation(scan)
    with open_client(_runtime(tmp_path)) as client:
        listed = client.get("/api/websites/website-programmer-ie/posts?limit=200").json()
        assert listed["published"] == observed["published"] == 3  # alpha, beta, bundle
        assert listed["drafts"] == 1
        assert listed["scheduled"] == 1
        assert listed["unknown"] == 1
        assert listed["total"] == 6
        by_rel = {item["relpath"]: item for item in listed["items"]}
        assert by_rel["bundle/index.md"]["identity"] == "bundle"
        assert by_rel["alpha.md"]["post_status"] == "published"
        assert by_rel["future.md"]["post_status"] == "scheduled"


def test_posts_filters_search_sort_pagination(tmp_path: Path) -> None:
    _site_with_posts(tmp_path / "websites")
    with open_client(_runtime(tmp_path)) as client:
        base = "/api/websites/website-programmer-ie/posts"
        assert client.get(base + "?status=draft").json()["total"] == 1
        assert client.get(base + "?status=published").json()["total"] == 3
        assert client.get(base + "?search=alpha").json()["total"] == 1
        titles = [item["title"] for item in client.get(base + "?sort=title_asc&limit=200").json()["items"]]
        assert titles == sorted(titles, key=str.casefold)
        page = client.get(base + "?sort=title_asc&limit=2&offset=1").json()
        assert page["total"] == 6 and len(page["items"]) == 2
        assert client.get(base + "?status=bogus").status_code == 422


def test_posts_only_for_blog_sites(tmp_path: Path) -> None:
    root = tmp_path / "websites"
    plain = root / "notes"
    (plain / "notebooks").mkdir(parents=True, exist_ok=True)
    with open_client(_runtime(tmp_path)) as client:
        response = client.get("/api/websites/website-notes/posts")
        assert response.status_code in (409, 422)
        assert client.get("/api/websites/website-nope/posts").status_code == 404


# ------------------------------------------------------- evaluation lifecycle


def test_evaluate_records_current_and_dedupes(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        url = "/api/websites/website-programmer-ie/posts/alpha.md/evaluate"
        first = client.post(url, json={}).json()
        assert first["overall"] == 800
        assert first["status"] == "CURRENT"
        assert first["freshness"] == "current" and not first["stale"]
        assert len(first["dimensions"]) == 8
        assert first["dimensions"][0]["max_points"] == 150
        # Quote anchored against the real source text.
        assert first["improvements"][0]["quote_anchored"] is True
        # Repeated identical request returns the same observation, no duplicate.
        second = client.post(url, json={}).json()
        assert second["id"] == first["id"]
        detail = client.get("/api/websites/website-programmer-ie/posts/alpha.md").json()
        assert len(detail["evaluations"]) == 1
        # Explicit re-evaluation links history.
        third = client.post(url, json={"force": True}).json()
        assert third["id"] != first["id"]
        assert third["previous_evaluation_id"] == first["id"]
        assert len(client.get(
            "/api/websites/website-programmer-ie/posts/alpha.md").json()["evaluations"]) == 2


def test_evaluate_requires_published_and_model(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    with open_client(_runtime(tmp_path)) as client:
        monkeypatch.delenv("MISSION_CONTROL_BLOG_EVAL_MODEL", raising=False)
        blocked = client.post("/api/websites/website-programmer-ie/posts/alpha.md/evaluate", json={})
        assert blocked.status_code == 409
        assert "MISSION_CONTROL_BLOG_EVAL_MODEL" in blocked.json()["error"]["message"]
        monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
        refused = client.post("/api/websites/website-programmer-ie/posts/draft.md/evaluate", json={})
        assert refused.status_code == 422


def test_blocked_and_error_outcomes_carry_no_scores(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    _site_with_posts(tmp_path / "websites")
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation",
                        lambda **kwargs: {"status": "BLOCKED", "error": "No model today."})
    with open_client(_runtime(tmp_path)) as client:
        result = client.post("/api/websites/website-programmer-ie/posts/alpha.md/evaluate", json={}).json()
        assert result["status"] == "BLOCKED"
        assert result["overall"] is None
        summary = client.get("/api/websites/website-programmer-ie/posts/summary").json()
        # Blocked attempts are not current, not averaged, not zero-filled.
        assert summary["evaluated_current"] == 0
        assert summary["unevaluated"] == summary["published"]
        assert summary["average_score"] is None


def test_staleness_on_edit_preserves_history(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        base = "/api/websites/website-programmer-ie/posts"
        first = client.post(base + "/alpha.md/evaluate", json={}).json()
        assert first["stale"] is False
        (site / "content" / "post" / "alpha.md").write_text(
            "+++\ntitle = \"Alpha\"\ndate = \"2026-01-05T10:00:00+00:00\"\n+++\n\nEdited body.\n",
            encoding="utf-8")
        detail = client.get(base + "/alpha.md").json()
        assert detail["current"] is None
        assert detail["evaluations"][0]["stale"] is True
        assert detail["evaluations"][0]["id"] == first["id"]
        assert detail["post"]["evaluation"]["freshness"] == "stale"


def test_reviews_accept_reject_defer(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        evaluation = client.post(
            "/api/websites/website-programmer-ie/posts/alpha.md/evaluate", json={}).json()
        review_url = (f"/api/websites/website-programmer-ie/evaluations/{evaluation['id']}/reviews")
        created = client.post(review_url, json={
            "finding_id": "f1", "decision": "ACCEPT", "reason": "Fair.", "reviewer": "author"}).json()
        assert created["decision"] == "ACCEPT"
        assert created["source_digest"] == evaluation["content_sha256"]
        refused = client.post(review_url, json={"finding_id": "nope", "decision": "ACCEPT"})
        assert refused.status_code == 422
        bad = client.post(review_url, json={"finding_id": "f1", "decision": "MAYBE"})
        assert bad.status_code == 422
        history = client.get(review_url).json()
        assert len(history) == 1 and history[0]["finding_id"] == "f1"


def test_summary_reports_denominator_and_coverage(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    _site_with_posts(tmp_path / "websites")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        base = "/api/websites/website-programmer-ie"
        summary = client.get(base + "/posts/summary").json()
        assert summary["published"] == 3 and summary["evaluated_current"] == 0
        assert summary["coverage_percent"] == 0.0
        client.post(base + "/posts/alpha.md/evaluate", json={})
        client.post(base + "/posts/beta.md/evaluate", json={})
        summary = client.get(base + "/posts/summary").json()
        assert summary["evaluated_current"] == 2
        assert summary["average_denominator"] == 2
        assert summary["average_score"] == 800
        assert summary["rubric_id"] == "blog-editorial-v1"
        assert summary["coverage_percent"] == pytest.approx(200 / 3)


# ------------------------------------------------------- evaluator unit


def test_evaluator_rejects_over_budget(monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    monkeypatch.setattr(eval_mod, "MAX_EVAL_CHARS", 10)
    outcome = eval_mod.run_pi_evaluation(
        model="m", title="T", relpath="x.md", article_text="way too long for budget")
    assert outcome["status"] == "BLOCKED"
    assert "budget" in outcome["error"]


def test_evaluator_reports_missing_pi(monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod
    from mission_control.research import pi_backend as pi_mod

    def _missing():
        raise FileNotFoundError("no pi")

    monkeypatch.setattr(eval_mod, "MAX_EVAL_CHARS", 10_000_000)
    monkeypatch.setattr(pi_mod, "resolve_pi_command", _missing)
    outcome = eval_mod.run_pi_evaluation(
        model="m", title="T", relpath="x.md", article_text="short")
    assert outcome["status"] == "BLOCKED"
    assert "Pi command" in outcome["error"]


def test_evaluator_validates_model_output() -> None:
    import mission_control.websites.evaluate as eval_mod

    def _raw(**overrides):
        outcome = _outcome()
        raw = dict(outcome)
        raw["dimensions"] = {
            key: {"score": value, "explanation": outcome["explanations"][key]}
            for key, value in outcome["scores"].items()
        }
        raw.pop("scores", None)
        raw.pop("explanations", None)
        raw.update(overrides)
        return raw

    payload, error = eval_mod._extract_json('```json\n{"a": 1}\n```')
    assert error is None and payload == {"a": 1}
    _payload, error = eval_mod._extract_json("no json here")
    assert error is not None
    validated, error = eval_mod._validate_payload(_raw())
    assert error is None and validated is not None and validated["overall"] == 800
    broken = _raw()
    broken["overall"] = 1
    _validated, error = eval_mod._validate_payload(broken)
    assert error is not None  # overall must equal the dimension sum
    short = _raw()
    short["strengths"] = ["only one"]
    _validated, error = eval_mod._validate_payload(short)
    assert error is not None  # exactly three strengths required
