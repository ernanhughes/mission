"""BLOG-01 D3: on-demand deterministic Writer post observation (endpoint).

The endpoint runs the real deterministic Writer Artifact detector against the
post's live body bytes and returns the validated envelope. No storage, no
manuscript changes, no models: a governed manual operation, never automatic.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from helpers import open_client
from mission_control.config import RuntimeSettings
from mission_control.models import WebsitePostEvaluation, WebsitePostReview

SITE_ID = "website-programmer-ie"
IDENTITY = "alpha.md"
FRONT = '+++\ntitle = "Alpha"\ndate = "2024-03-10T10:00:00+00:00"\n+++\n\n'
BODY = (
    "The city wakes slowly. The city stretches its avenues. The city hums with bicycles.\n"
    "\n"
    "The thesis of this note is simple: small habits compound into durable skill.\n"
)


def _runtime(tmp_path: Path) -> RuntimeSettings:
    base = RuntimeSettings(
        repo_root=Path(__file__).resolve().parents[2],
        data_dir=tmp_path / "data",
        config_dir=Path(__file__).resolve().parents[2] / "config",
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "b",
        fiction_book_root=tmp_path / "fb",
        host="127.0.0.1",
        port=8791,
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


def _row_counts(client) -> tuple[int, int]:
    with client.app.state.database.session() as session:
        from sqlalchemy import func, select

        evals = session.scalar(select(func.count()).select_from(WebsitePostEvaluation)) or 0
        reviews = session.scalar(select(func.count()).select_from(WebsitePostReview)) or 0
    return evals, reviews


def test_observe_returns_validated_writer_evidence(tmp_path: Path) -> None:
    from mission_control.websites import context as _context

    site = _hugo_site(tmp_path / "websites")
    raw = (FRONT + BODY).encode("utf-8")
    (site / "content" / "post" / IDENTITY).write_bytes(raw)
    evaluated = _context.split_post_body(raw)["body"]
    assert evaluated is not None
    with open_client(_runtime(tmp_path)) as client:
        before = _row_counts(client)
        response = client.post(f"/api/websites/{SITE_ID}/posts/{IDENTITY}/writer-observation")
        assert response.status_code == 200, response.text
        envelope = response.json()
        assert envelope["producer"]["runtime_name"] == "artifact"
        assert envelope["producer"]["method"] == "analyze_text"
        work = envelope["work_object"]
        assert work["kind"] == "post"
        assert work["target_id"] == IDENTITY
        # Binds the actually evaluated bytes (split output), never the raw file.
        assert work["source_hash"] == hashlib.sha256(evaluated).hexdigest()
        assert work["text_sha256"] == work["source_hash"]
        assert work["content_sha256"] == hashlib.sha256(raw).hexdigest()
        assert work["content_sha256"] != work["source_hash"]
        assert envelope["status"] in ("complete", "empty")
        assert response.json() == envelope  # stable shape, no hidden fields
        assert _row_counts(client) == before  # nothing stored
        assert (site / "content" / "post" / IDENTITY).read_bytes() == raw  # untouched


def test_observe_rejects_unknown_identity(tmp_path: Path) -> None:
    _hugo_site(tmp_path / "websites")
    with open_client(_runtime(tmp_path)) as client:
        response = client.post(f"/api/websites/{SITE_ID}/posts/missing.md/writer-observation")
        assert response.status_code == 404


def test_observe_refuses_unmappable_body_without_fabrication(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    (site / "content" / "post" / IDENTITY).write_text(
        "+++\ntitle = unterminated\n", encoding="utf-8"
    )
    with open_client(_runtime(tmp_path)) as client:
        before = _row_counts(client)
        response = client.post(f"/api/websites/{SITE_ID}/posts/{IDENTITY}/writer-observation")
        assert response.status_code == 422, response.text
        assert _row_counts(client) == before


def test_observe_undecodable_body_is_unavailable_never_current(tmp_path: Path) -> None:
    from mission_control.websites import context as _context

    site = _hugo_site(tmp_path / "websites")
    raw = b'+++\ntitle = "X"\n+++\n\n' + b"\xff\xfe\x00not text\xff"
    evaluated = _context.split_post_body(raw)["body"]
    assert evaluated is not None
    (site / "content" / "post" / IDENTITY).write_bytes(raw)
    with open_client(_runtime(tmp_path)) as client:
        envelope = client.post(
            f"/api/websites/{SITE_ID}/posts/{IDENTITY}/writer-observation"
        ).json()
        assert envelope["status"] == "unavailable"
        assert envelope["findings"] == [] and envelope["dimensions"] == []
        assert envelope["work_object"]["source_hash"] == hashlib.sha256(evaluated).hexdigest()


def test_observe_carries_no_editorial_scores(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    (site / "content" / "post" / IDENTITY).write_bytes((FRONT + BODY).encode("utf-8"))
    with open_client(_runtime(tmp_path)) as client:
        envelope = client.post(
            f"/api/websites/{SITE_ID}/posts/{IDENTITY}/writer-observation"
        ).json()
        assert "overall" not in envelope
        assert "scores" not in envelope or envelope.get("scores") in (None, [], {})
        for dimension in envelope.get("dimensions", []):
            assert dimension.get("scale", {}).get("type") != "blog-editorial-v1"
