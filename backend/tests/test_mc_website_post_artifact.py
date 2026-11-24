"""BLOG-01 D3: deterministic Writer Artifact post observations.

All Writer evidence comes from the real deterministic Artifact detector
(read-only import from the Writer checkout); the editorial side only is
faked (``run_pi_evaluation`` double, as in D1/D2). Disposable Hugo site +
tmp DB only. No model calls, no QC, no auto-improvement.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


from helpers import open_client
from mission_control.config import RuntimeSettings
from test_mc_website_posts_context import _outcome as _editorial_outcome

SITE_ID = "website-programmer-ie"
IDENTITY = "alpha.md"

FRONT = '+++\ntitle = "Alpha"\ndate = "2024-03-10T10:00:00+00:00"\n+++\n\n'
# Rev1 chants one starter three times -> deterministic ANAPHORA_RUN (MED).
BODY_REV1 = (
    "The city wakes slowly. The city stretches its avenues. The city hums with bicycles.\n"
    "\n"
    "The thesis of this note is simple: small habits compound into durable skill.\n"
)
# Rev2 varies every starter -> detector finds nothing (status "empty").
BODY_REV2 = (
    "Rain found the loose shutter before I did. It rattled twice, then held.\n"
    "\n"
    "The thesis of this note is simple: small habits compound into durable skill.\n"
    "\n"
    "The ledger listed flour, lamp oil, and an apology I had not yet written down.\n"
)

OBS1 = "2026-11-23T17:41:00+00:00"
OBS2 = "2026-11-23T17:42:00+00:00"


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


def _write_post(site: Path, body: str, *, front: str = FRONT) -> bytes:
    raw = (front + body).encode("utf-8")
    (site / "content" / "post" / IDENTITY).write_bytes(raw)
    return raw


def _evaluate(client, payload=None):
    response = client.post(f"/api/websites/{SITE_ID}/posts/{IDENTITY}/evaluate", json=payload or {})
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------- envelope binding


def test_artifact_envelope_binds_body_bytes() -> None:
    from mission_control.websites import post_artifact as pa
    from mission_control.websites.context import validate_post_envelope

    body = BODY_REV1.encode("utf-8")
    raw = (FRONT + BODY_REV1).encode("utf-8")
    envelope = pa.build_artifact_envelope(
        identity=IDENTITY,
        body=body,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        body_offset_bytes=len(FRONT.encode("utf-8")) - 1,
        evaluation_id="artifact-rev1",
        observed_at=OBS1,
    )
    # validate_post_envelope path: returns the envelope unchanged.
    assert validate_post_envelope(envelope, identity=IDENTITY) is envelope
    work = envelope["work_object"]
    assert work["kind"] == "post"
    assert work["target_id"] == IDENTITY
    assert work["source_hash"] == hashlib.sha256(body).hexdigest()
    assert work["text_sha256"] == work["source_hash"]
    assert work["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert work["content_sha256"] != work["source_hash"]  # raw vs body never interchanged
    assert envelope["producer"]["runtime_name"] == "artifact"
    assert envelope["status"] == "complete"
    codes = [finding["code"] for finding in envelope["findings"]]
    assert "ANAPHORA_RUN" in codes
    native_scores = {
        dimension["dimension"]: dimension["score"] for dimension in envelope["dimensions"]
    }
    assert native_scores["artifact_score"] == 90.0  # verbatim detector output
    assert envelope["provenance"]["persist"] is False
    assert envelope["limitations"]  # honest limits travel with the evidence


def test_envelope_matches_direct_detector_run_verbatim() -> None:
    import importlib.util
    import sys as _sys

    from mission_control.websites import post_artifact as pa

    path = pa.artifact_service_path()
    spec = importlib.util.spec_from_file_location("writer_artifact_probe", str(path))
    module = importlib.util.module_from_spec(spec)
    _sys.modules["writer_artifact_probe"] = module
    spec.loader.exec_module(module)
    direct = module.ArtifactDetectionService().analyze_text(
        text=BODY_REV1, source_name=IDENTITY, persist=False
    )
    envelope = pa.build_artifact_envelope(
        identity=IDENTITY, body=BODY_REV1.encode("utf-8"), observed_at=OBS1
    )
    assert [finding["code"] for finding in envelope["findings"]] == [
        issue.type for issue in direct.issues
    ]
    assert [finding["claim"] for finding in envelope["findings"]] == [
        issue.title for issue in direct.issues
    ]
    assert [finding["evidence"] for finding in envelope["findings"]] == [
        list(issue.evidence) for issue in direct.issues
    ]
    by_dimension = {
        dimension["dimension"]: dimension["score"] for dimension in envelope["dimensions"]
    }
    for key, value in direct.detector_stats.items():
        assert by_dimension[key] == value


def test_envelope_is_deterministic() -> None:
    from mission_control.websites import post_artifact as pa

    kwargs = {"identity": IDENTITY, "body": BODY_REV1.encode("utf-8"), "observed_at": OBS1}
    first = pa.build_artifact_envelope(evaluation_id="artifact-rev1", **kwargs)
    second = pa.build_artifact_envelope(evaluation_id="artifact-rev1", **kwargs)
    assert first == second
    # Hash-derived default id is stable too.
    assert (
        pa.build_artifact_envelope(**kwargs)["evaluation_id"]
        == pa.build_artifact_envelope(**kwargs)["evaluation_id"]
    )


def test_undecodable_body_yields_unavailable_never_current() -> None:
    from mission_control.websites import post_artifact as pa

    body = b"\xff\xfe\x00not text\xff"
    envelope = pa.build_artifact_envelope(identity=IDENTITY, body=body, observed_at=OBS1)
    assert envelope["status"] == "unavailable"
    assert envelope["work_object"]["source_hash"] == hashlib.sha256(body).hexdigest()
    assert envelope["findings"] == [] and envelope["dimensions"] == []


def test_detector_failure_degrades_to_unavailable(monkeypatch) -> None:
    from mission_control.websites import post_artifact as pa

    def _boom() -> None:
        raise RuntimeError("detector exploded")

    monkeypatch.setattr(pa, "_load_service_class", _boom)
    envelope = pa.build_artifact_envelope(
        identity=IDENTITY, body=BODY_REV1.encode("utf-8"), observed_at=OBS1
    )
    assert envelope["status"] == "unavailable"
    assert envelope["findings"] == []


# ------------------------------------------------------- spans


def test_spans_are_explicitly_unavailable_never_fabricated() -> None:
    from mission_control.websites import post_artifact as pa

    envelope = pa.build_artifact_envelope(
        identity=IDENTITY, body=BODY_REV1.encode("utf-8"), observed_at=OBS1
    )
    assert envelope["findings"], "fixture must produce at least one finding"
    for finding in envelope["findings"]:
        assert finding["span"]["available"] is False
        assert finding["span"]["reason"]
        assert finding["native"]["start_line"] >= 1  # native line evidence kept verbatim

    def _walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                assert "byte_start" not in key and "byte_end" not in key
                assert key not in {"raw_byte", "raw_bytes", "byte_offset"}
                yield from _walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from _walk(item)

    list(_walk(envelope))  # raises on any fabricated byte-offset key


# ------------------------------------------------------- end to end


def test_wrapper_binds_live_post_and_context_marks_current(tmp_path: Path) -> None:
    from mission_control.websites import context as ctx
    from mission_control.websites import post_artifact as pa

    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, BODY_REV1)
    blog_dir = site / "content" / "post"
    envelope = pa.artifact_envelope_for_live_post(
        blog_dir, identity=IDENTITY, observed_at=OBS1, evaluation_id="artifact-rev1"
    )
    assert envelope is not None
    with open_client(_runtime(tmp_path)) as client:
        with client.app.state.database.session() as session:
            built = ctx.build_site_post_context(
                session,
                website_id=SITE_ID,
                blog_dir=blog_dir,
                identity=IDENTITY,
                writer_envelopes=[envelope],
            )
    assert built["post"]["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (
        built["post"]["text_sha256"]
        == hashlib.sha256(
            (FRONT + BODY_REV1).encode("utf-8")[built["post"]["body_offset_bytes"] :]
        ).hexdigest()
    )
    writer = next(m for m in built["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "CURRENT"
    current = writer["value"]["evaluations"][0]
    assert current["derived"] == "CURRENT" and current["provider"] == "artifact"
    assert current["envelope"]["work_object"]["source_hash"] == built["post"]["text_sha256"]


def test_unterminated_front_matter_yields_no_envelope(tmp_path: Path) -> None:
    from mission_control.websites import context as ctx
    from mission_control.websites import post_artifact as pa

    site = _hugo_site(tmp_path / "websites")
    (site / "content" / "post" / IDENTITY).write_bytes(b'+++\ntitle = "No end"\n')
    assert (
        pa.artifact_envelope_for_live_post(
            site / "content" / "post", identity=IDENTITY, observed_at=OBS1
        )
        is None
    )
    with open_client(_runtime(tmp_path)) as client:
        with client.app.state.database.session() as session:
            built = ctx.build_site_post_context(
                session,
                website_id=SITE_ID,
                blog_dir=site / "content" / "post",
                identity=IDENTITY,
                writer_envelopes=[],
            )
    writer = next(m for m in built["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "NOT_RUN"  # nothing observed, nothing fabricated


def test_front_matter_churn_keeps_writer_current_editorial_stale(
    tmp_path: Path, monkeypatch
) -> None:
    import mission_control.websites.evaluate as eval_mod
    from mission_control.websites import context as ctx
    from mission_control.websites import post_artifact as pa

    site = _hugo_site(tmp_path / "websites")
    _write_post(site, BODY_REV1)
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _editorial_outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        _evaluate(client)
        envelope = pa.artifact_envelope_for_live_post(
            site / "content" / "post",
            identity=IDENTITY,
            observed_at=OBS1,
            evaluation_id="artifact-rev1",
        )
        front2 = FRONT.replace('title = "Alpha"', 'title = "Alpha, revised"')
        _write_post(site, BODY_REV1, front=front2)
        with client.app.state.database.session() as session:
            built = ctx.build_site_post_context(
                session,
                website_id=SITE_ID,
                blog_dir=site / "content" / "post",
                identity=IDENTITY,
                writer_envelopes=[envelope],
            )
    editorial = next(m for m in built["measures"] if m["id"] == "mission.site.post.editorial")
    assert editorial["status"] == "STALE"  # editorial binds raw bytes
    writer = next(m for m in built["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "CURRENT"  # Writer binds evaluated body bytes
    assert writer["value"]["evaluations"][0]["body_match"] is True
    assert writer["value"]["evaluations"][0]["location_match"] is False


def test_provider_separation_no_second_editorial_score(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod
    from mission_control.websites import context as ctx
    from mission_control.websites import post_artifact as pa

    site = _hugo_site(tmp_path / "websites")
    _write_post(site, BODY_REV1)
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _editorial_outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        _evaluate(client)
        envelope = pa.artifact_envelope_for_live_post(
            site / "content" / "post",
            identity=IDENTITY,
            observed_at=OBS1,
            evaluation_id="artifact-rev1",
        )
        with client.app.state.database.session() as session:
            built = ctx.build_site_post_context(
                session,
                website_id=SITE_ID,
                blog_dir=site / "content" / "post",
                identity=IDENTITY,
                writer_envelopes=[envelope],
            )
    assert [measure["id"] for measure in built["measures"]] == [
        "mission.site.post.evaluations",
        "mission.site.post.editorial",
    ]
    writer, editorial = built["measures"]
    assert writer["value"]["coverage"]["providers"] == ["artifact"]
    assert editorial["value"]["current"]["overall"] == 800.0
    # No QC envelope, no second editorial score, no auto-improvement inside Writer evidence.
    assert "improvements" not in writer["value"]
    assert writer["value"]["evaluations"][0]["envelope"]["dimensions"][0]["scale"][
        "description"
    ].startswith("Writer Artifact native")
    assert "blog-editorial-v1" in editorial["value"]["current"]["rubric_id"]


def test_unavailable_envelope_marks_context_unavailable(tmp_path: Path, monkeypatch) -> None:
    from mission_control.websites import context as ctx
    from mission_control.websites import post_artifact as pa

    site = _hugo_site(tmp_path / "websites")
    _write_post(site, BODY_REV1)

    def _boom() -> None:
        raise RuntimeError("detector exploded")

    monkeypatch.setattr(pa, "_load_service_class", _boom)
    envelope = pa.artifact_envelope_for_live_post(
        site / "content" / "post",
        identity=IDENTITY,
        observed_at=OBS1,
        evaluation_id="artifact-rev1",
    )
    assert envelope is not None and envelope["status"] == "unavailable"
    with open_client(_runtime(tmp_path)) as client:
        with client.app.state.database.session() as session:
            built = ctx.build_site_post_context(
                session,
                website_id=SITE_ID,
                blog_dir=site / "content" / "post",
                identity=IDENTITY,
                writer_envelopes=[envelope],
            )
    writer = next(m for m in built["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "UNAVAILABLE"
    assert writer["value"]["evaluations"][0]["derived"] == "UNAVAILABLE"


def test_two_revisions_form_current_plus_history(tmp_path: Path) -> None:
    from mission_control.websites import context as ctx
    from mission_control.websites import post_artifact as pa

    site = _hugo_site(tmp_path / "websites")
    blog_dir = site / "content" / "post"
    _write_post(site, BODY_REV1)
    old = pa.artifact_envelope_for_live_post(
        blog_dir, identity=IDENTITY, observed_at=OBS1, evaluation_id="artifact-rev1"
    )
    _write_post(site, BODY_REV2)
    new = pa.artifact_envelope_for_live_post(
        blog_dir, identity=IDENTITY, observed_at=OBS2, evaluation_id="artifact-rev2"
    )
    assert old["status"] == "complete" and new["status"] == "empty"
    with open_client(_runtime(tmp_path)) as client:
        with client.app.state.database.session() as session:
            built = ctx.build_site_post_context(
                session,
                website_id=SITE_ID,
                blog_dir=blog_dir,
                identity=IDENTITY,
                writer_envelopes=[old, new],
            )
    writer = next(m for m in built["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "CURRENT"
    assert [item["evaluation_id"] for item in writer["value"]["evaluations"]] == ["artifact-rev2"]
    assert [item["evaluation_id"] for item in writer["value"]["history"]] == ["artifact-rev1"]
    assert writer["value"]["history"][0]["finding_codes"] == ["ANAPHORA_RUN"]
    assert writer["value"]["evaluations"][0]["envelope"]["findings"] == []
