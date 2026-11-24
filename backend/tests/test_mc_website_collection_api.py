"""BLOG-01 D4: collection endpoint (read-only projection over stored rows)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from helpers import open_client
from mission_control.config import RuntimeSettings
from mission_control.models import WebsitePostEvaluation, WebsitePostReview

SITE_ID = "website-programmer-ie"


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


def _post(path: Path, name: str, *, date: str | None = "2026-01-05T10:00:00+00:00") -> None:
    lines = ["+++", f'title = "{name}"']
    if date is not None:
        lines.append(f'date = "{date}"')
    lines += ["+++", "", "Body text for the article under test."]
    path.write_text("\n".join(lines), encoding="utf-8")


def _row_counts(client) -> tuple[int, int]:
    with client.app.state.database.session() as session:
        evals = session.scalar(select(func.count()).select_from(WebsitePostEvaluation)) or 0
        reviews = session.scalar(select(func.count()).select_from(WebsitePostReview)) or 0
    return evals, reviews


def test_collection_endpoint_shape_and_read_only(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    (site / "content" / "post" / "alpha.md").write_text(
        '+++\ntitle = "Alpha"\ndate = "2024-03-10T10:00:00+00:00"\n+++\n\nBody here.\n',
        encoding="utf-8",
    )
    raw_before = (site / "content" / "post" / "alpha.md").read_bytes()
    with open_client(_runtime(tmp_path)) as client:
        before = _row_counts(client)
        response = client.get(f"/api/websites/{SITE_ID}/collection/quality")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["schema"] == "site-collection-quality.v1"
        assert payload["site"]["website_id"] == SITE_ID
        assert payload["inventory"]["published"] == 1
        assert payload["coverage"]["denominator"].startswith("published posts only")
        assert payload["scores"]["rubric_id"] == "blog-editorial-v1"
        assert payload["review_queues"]["stale_oldest_first"] == []
        assert len(payload["review_queues"]["unevaluated_oldest_first"]) == 1
        assert payload["duplication_candidates"] == []
        assert payload["provisional"]["contradictions"]["status"] == "unavailable"
        assert _row_counts(client) == before
        assert (site / "content" / "post" / "alpha.md").read_bytes() == raw_before


def test_collection_endpoint_reflects_stored_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mission_control.websites.evaluate as eval_mod
    from test_mc_website_posts import _outcome

    site = _hugo_site(tmp_path / "websites")
    _post(site / "content" / "post" / "alpha.md", "Alpha")
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        client.post(f"/api/websites/{SITE_ID}/posts/alpha.md/evaluate", json={})
        payload = client.get(f"/api/websites/{SITE_ID}/collection/quality").json()
        assert payload["coverage"]["evaluated_current"] == 1
        assert payload["scores"]["n_scored"] == 1
        assert payload["scores"]["average"] == 800
        assert [entry["identity"] for entry in payload["scores"]["weakest"]] == ["alpha.md"]
        assert payload["limitations"]


def test_collection_endpoint_unknown_site_404(tmp_path: Path) -> None:
    _hugo_site(tmp_path / "websites")
    with open_client(_runtime(tmp_path)) as client:
        response = client.get("/api/websites/no-such-site/collection/quality")
        assert response.status_code == 404
