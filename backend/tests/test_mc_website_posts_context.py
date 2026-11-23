"""BLOG-01 D1: read-only site-posts-context.v1 builder.

All AI execution is faked: no test may invoke a real model. Writer
envelopes are hand-crafted dicts in the qualified post shape (validated
only, never scored). Disposable Hugo site + tmp DB only.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from helpers import open_client
from mission_control.config import RuntimeSettings

SITE_ID = "website-programmer-ie"
IDENTITY = "alpha.md"

FRONT = '+++\ntitle = "Alpha"\ndate = "2024-03-10T10:00:00+00:00"\n+++\n\n'
BODY_REV1 = (
    "The thesis of this note is simple: small habits compound into durable skill.\n\n"
    "Each section states one claim and shows one example.\n"
)
BODY_REV2 = (
    "The thesis of this note is simple: small habits compound into durable skill.\n\n"
    "Each section states one claim, shows one example, and names its limit.\n\n"
    "A second pass adds one worked example with a checked result.\n"
)
STABLE_QUOTE = "The thesis of this note is simple: small habits compound into durable skill."


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


def _write_post(site: Path, body: str, *, front: str = FRONT) -> bytes:
    raw = (front + body).encode("utf-8")
    # Bytes, not write_text: exact LF bytes so precomputed hashes bind the file.
    (site / "content" / "post" / IDENTITY).write_bytes(raw)
    return raw


def _outcome(**overrides):
    scores = {
        "thesis_purpose": 120,
        "substance_depth": 140,
        "argument_reasoning": 120,
        "evidence_attribution": 120,
        "structure_flow": 80,
        "clarity_precision": 80,
        "reader_value": 80,
        "style_economy": 60,
    }
    base = {
        "status": "CURRENT",
        "overall": 800,
        "scores": scores,
        "explanations": {key: f"Why {key}." for key in scores},
        "assessment": "Solid technical article with room to sharpen the thesis.",
        "strengths": ["Clear examples", "Honest scope", "Good pacing"],
        "weaknesses": ["Thin evidence", "Weak ending", "Jargon"],
        "improvements": [
            {
                "rank": 1,
                "title": "Sharpen thesis",
                "problem": "Vague claim",
                "why_it_matters": "Focus",
                "suggestion": "State it upfront",
                "source_heading": "Intro",
                "source_quote": STABLE_QUOTE,
            },
            {
                "rank": 2,
                "title": "Add data",
                "problem": "No numbers",
                "why_it_matters": "Trust",
                "suggestion": "Add a table",
                "source_heading": None,
                "source_quote": None,
            },
            {
                "rank": 3,
                "title": "Cut filler",
                "problem": "Repeats",
                "why_it_matters": "Economy",
                "suggestion": "Delete paragraph two",
                "source_heading": None,
                "source_quote": None,
            },
        ],
        "findings": [
            {
                "finding_id": "f1",
                "kind": "observation",
                "title": "Note",
                "detail": "Worth a follow-up.",
                "source_heading": "Intro",
                "source_quote": STABLE_QUOTE,
            }
        ],
        "uncertainty": "Whether readers share the premise.",
        "limitations": ["Single-model review, no external verification."],
        "actual_model": "fake-model",
        "execution": {"transport": "fake"},
    }
    base.update(overrides)
    return base


def _envelope(
    *,
    evaluation_id: str,
    observed_at: str,
    body_sha: str,
    raw_sha: str,
    offset: int,
    codes=("EM_DASH",),
    provider="artifact",
    status="complete",
    target: str = IDENTITY,
) -> dict:
    return {
        "schema_version": "writer.evaluation-envelope.v1",
        "evaluation_id": evaluation_id,
        "observed_at": observed_at,
        "work_object": {
            "kind": "post",
            "target_id": target,
            "source_path": IDENTITY,
            "source_hash": body_sha,
            "relpath": IDENTITY,
            "content_sha256": raw_sha,
            "text_sha256": body_sha,
            "body_offset_bytes": offset,
        },
        "producer": {
            "runtime_name": provider,
            "method": "analyze_text",
            "method_version": "artifact-adapter.v1",
        },
        "rubric": {"rubric_id": "artifact-detectors", "profile": "fiction"},
        "status": status,
        "dimensions": [
            {
                "dimension": "artifact_cleanliness",
                "score": 99.0,
                "scale": {
                    "scale_type": "continuous",
                    "minimum": 0.0,
                    "maximum": 100.0,
                    "description": "artifact score 0-100, higher is cleaner",
                },
                "rationale": "1 detector issue found",
                "evidence_spans": [],
            }
        ],
        "findings": [
            {"family": "artifact", "code": code, "claim": "", "severity": "MED", "spans": []}
            for code in codes
        ],
        "coverage": {"unit": "characters", "note": "single deterministic pass"},
        "limitations": ["Detector versions vary per detector."],
        "provenance": {"detectors": ["em_dash"]},
        "supersedes": None,
    }


def _shas(raw: bytes) -> tuple[str, str, int]:
    # Independent split: body starts after the closing-delimiter line's
    # newline, so the blank line following "+++" belongs to the body.
    end = raw.find(b"\n+++", 3)
    assert end != -1
    off = raw.find(b"\n", end + 1) + 1
    assert off > 0
    body = raw[off:]
    assert raw[off:] == body
    return (hashlib.sha256(raw).hexdigest(), hashlib.sha256(body).hexdigest(), off)


def _context(client, site: Path, envelopes=None, **kwargs):
    from mission_control.websites import context as ctx

    with client.app.state.database.session() as session:
        return ctx.build_site_post_context(
            session,
            website_id=SITE_ID,
            blog_dir=site / "content" / "post",
            identity=IDENTITY,
            writer_envelopes=envelopes,
            **kwargs,
        )


def _evaluate(client, identity: str = IDENTITY, payload=None):
    response = client.post(f"/api/websites/{SITE_ID}/posts/{identity}/evaluate", json=payload or {})
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------- measure presence


def test_context_neither_measure_not_run(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    _write_post(site, BODY_REV1)
    with open_client(_runtime(tmp_path)) as client:
        context = _context(client, site)
    assert context["schema"] == "site-posts-context.v1"
    assert context["site"] == {"website_id": SITE_ID, "blog_dir": "post"}
    assert context["post"]["article_identity"] == IDENTITY
    assert context["post"]["relpath"] == IDENTITY
    assert context["post"]["post_status"] == "published"
    by_id = {measure["id"]: measure for measure in context["measures"]}
    assert by_id["mission.site.post.evaluations"]["status"] == "NOT_RUN"
    assert by_id["mission.site.post.editorial"]["status"] == "NOT_RUN"
    assert by_id["mission.site.post.editorial"]["value"]["current"] is None


def test_context_editorial_only_current(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, BODY_REV1)
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        row = _evaluate(client)
        context = _context(client, site)
    post = context["post"]
    assert post["content_sha256"] == hashlib.sha256(raw).hexdigest() == row["content_sha256"]
    _raw_sha, body_sha, off = _shas(raw)
    assert post["text_sha256"] == body_sha
    assert post["text_sha256"] != post["content_sha256"]
    assert post["body_offset_bytes"] == off == len(FRONT.encode("utf-8")) - 1
    assert raw[post["body_offset_bytes"] :] == b"\n" + BODY_REV1.encode("utf-8")
    extraction = context["extraction"]
    assert extraction["version"] == "post-body-split.v1"
    assert extraction["body_offset_bytes"] == post["body_offset_bytes"]
    assert extraction["note"] is None

    editorial = next(m for m in context["measures"] if m["id"] == "mission.site.post.editorial")
    assert editorial["status"] == "CURRENT"
    assert editorial["scope"] == "post" and editorial["kind"] == "model_judgment"
    current = editorial["value"]["current"]
    assert current["overall"] == 800.0
    assert len(current["dimensions"]) == 8
    assert current["improvements"][0]["quote_anchored"] is True
    assert current["findings"][0]["quote_anchored"] is True
    assert current["reviews"] == []
    assert editorial["value"]["history_refs"] == []
    writer = next(m for m in context["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "NOT_RUN"
    assert writer["value"]["evaluations"] == [] and writer["value"]["rejected"] == []


def test_context_writer_only(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, BODY_REV1)
    raw_sha, body_sha, offset = _shas(raw)
    envelope = _envelope(
        evaluation_id="artifact-eval-1",
        observed_at="2026-11-23T17:42:00+00:00",
        body_sha=body_sha,
        raw_sha=raw_sha,
        offset=offset,
    )
    with open_client(_runtime(tmp_path)) as client:
        context = _context(client, site, [envelope])
    writer = next(m for m in context["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "CURRENT"
    assert writer["scope"] == "post" and writer["kind"] == "post_evaluations"
    current = writer["value"]["evaluations"]
    assert len(current) == 1
    assert current[0]["evaluation_id"] == "artifact-eval-1"
    assert current[0]["provider"] == "artifact"
    assert current[0]["current"] is True and current[0]["derived"] == "CURRENT"
    carried = current[0]["envelope"]
    assert carried == envelope  # whole envelope, native scale untouched
    assert carried["dimensions"][0]["scale"]["maximum"] == 100.0
    assert carried["dimensions"][0]["scale"]["scale_type"] == "continuous"
    assert writer["value"]["history"] == []
    editorial = next(m for m in context["measures"] if m["id"] == "mission.site.post.editorial")
    assert editorial["status"] == "NOT_RUN"


# ------------------------------------------------------- history + dual freshness


def test_context_force_eval_preserves_history(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _hugo_site(tmp_path / "websites")
    raw1 = _write_post(site, BODY_REV1)
    raw_sha1, body_sha1, off = _shas(raw1)
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        first = _evaluate(client)
        _write_post(site, BODY_REV2)
        raw2 = (site / "content" / "post" / IDENTITY).read_bytes()
        raw_sha2, body_sha2, _off2 = _shas(raw2)
        assert raw_sha2 != raw_sha1 and body_sha2 != body_sha1
        second = _evaluate(client, payload={"force": True})
        assert second["previous_evaluation_id"] == first["id"]
        env1 = _envelope(
            evaluation_id="artifact-eval-1",
            observed_at="2026-11-23T17:41:00+00:00",
            body_sha=body_sha1,
            raw_sha=raw_sha1,
            offset=off,
            codes=("EM_DASH",),
        )
        env2 = _envelope(
            evaluation_id="artifact-eval-2",
            observed_at="2026-11-23T17:42:00+00:00",
            body_sha=body_sha2,
            raw_sha=raw_sha2,
            offset=off,
            codes=("SINGLE_SENTENCE_PARAGRAPH_RUN",),
        )
        context = _context(client, site, [env1, env2])

    editorial = next(m for m in context["measures"] if m["id"] == "mission.site.post.editorial")
    assert editorial["status"] == "CURRENT"
    assert editorial["value"]["current"]["id"] == second["id"]
    refs = editorial["value"]["history_refs"]
    assert len(refs) == 1
    assert refs[0]["evaluation_id"] == first["id"]
    assert refs[0]["freshness"] == "stale" and refs[0]["stale"] is True
    assert refs[0]["content_sha256"] == raw_sha1
    assert refs[0]["overall"] == 800.0

    writer = next(m for m in context["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "CURRENT"
    assert len(writer["value"]["evaluations"]) == 1
    assert writer["value"]["evaluations"][0]["evaluation_id"] == "artifact-eval-2"
    history = writer["value"]["history"]
    assert len(history) == 1
    assert history[0]["evaluation_id"] == "artifact-eval-1"
    assert history[0]["finding_codes"] == ["EM_DASH"]
    assert history[0]["source_hash"] == body_sha1
    assert history[0]["content_sha256"] == raw_sha1


def test_context_front_matter_only_edit(tmp_path: Path, monkeypatch) -> None:
    """Editorial binds raw bytes (stale); Writer envelope binds body (current)."""
    import mission_control.websites.evaluate as eval_mod

    site = _hugo_site(tmp_path / "websites")
    raw1 = _write_post(site, BODY_REV1)
    raw_sha1, body_sha1, off = _shas(raw1)
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        _evaluate(client)
        envelope = _envelope(
            evaluation_id="artifact-eval-1",
            observed_at="2026-11-23T17:41:00+00:00",
            body_sha=body_sha1,
            raw_sha=raw_sha1,
            offset=off,
        )
        front2 = FRONT.replace('title = "Alpha"', 'title = "Alpha, revised"')
        _write_post(site, BODY_REV1, front=front2)
        raw2 = (site / "content" / "post" / IDENTITY).read_bytes()
        raw_sha2, body_sha2, _off2 = _shas(raw2)
        assert raw_sha2 != raw_sha1 and body_sha2 == body_sha1
        context = _context(client, site, [envelope])

    assert context["post"]["content_sha256"] == raw_sha2
    assert context["post"]["text_sha256"] == body_sha1
    editorial = next(m for m in context["measures"] if m["id"] == "mission.site.post.editorial")
    assert editorial["status"] == "STALE"
    assert editorial["value"]["current"] is None
    assert len(editorial["value"]["history_refs"]) == 1
    writer = next(m for m in context["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "CURRENT"
    current = writer["value"]["evaluations"][0]
    assert current["derived"] == "CURRENT"
    assert current["body_match"] is True
    assert current["location_match"] is False
    assert any("Location binding drifted" in line for line in writer["limitations"])


def test_raw_and_body_hashes_not_interchangeable(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, BODY_REV1)
    raw_sha, body_sha, off = _shas(raw)
    assert raw_sha != body_sha
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        row = _evaluate(client)
        envelope = _envelope(
            evaluation_id="artifact-eval-1",
            observed_at="2026-11-23T17:41:00+00:00",
            body_sha=body_sha,
            raw_sha=raw_sha,
            offset=off,
        )
        context = _context(client, site, [envelope])
    # Swapping the two hashes must not validate: envelope binds body, row binds raw.
    assert row["content_sha256"] == raw_sha != body_sha
    assert context["post"]["text_sha256"] == body_sha
    assert context["post"]["content_sha256"] == raw_sha
    carried = context["measures"][0]["value"]["evaluations"][0]["envelope"]
    assert carried["work_object"]["source_hash"] == body_sha
    assert carried["work_object"]["content_sha256"] == raw_sha


def test_rename_does_not_inherit_history(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod

    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, BODY_REV1)
    raw_sha, body_sha, off = _shas(raw)
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        _evaluate(client)
        (site / "content" / "post" / IDENTITY).rename(site / "content" / "post" / "beta.md")
        from mission_control.core.errors import NotFound
        from mission_control.websites import context as ctx

        with client.app.state.database.session() as session:
            with pytest.raises(NotFound):
                ctx.build_site_post_context(
                    session,
                    website_id=SITE_ID,
                    blog_dir=site / "content" / "post",
                    identity=IDENTITY,
                )
            beta = ctx.build_site_post_context(
                session,
                website_id=SITE_ID,
                blog_dir=site / "content" / "post",
                identity="beta.md",
                writer_envelopes=[
                    _envelope(
                        evaluation_id="artifact-eval-1",
                        observed_at="2026-11-23T17:41:00+00:00",
                        body_sha=body_sha,
                        raw_sha=raw_sha,
                        offset=off,
                    )
                ],
            )
    editorial = next(m for m in beta["measures"] if m["id"] == "mission.site.post.editorial")
    assert editorial["status"] == "NOT_RUN"
    assert "moves/renames create a new identity" in beta["post"]["lineage_note"]
    writer = next(m for m in beta["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "NOT_RUN"
    assert len(writer["value"]["rejected"]) == 1
    assert "does not match post" in writer["value"]["rejected"][0]["error"]


# ------------------------------------------------------- fail-safe inputs


def test_rejects_malformed_hostile_envelopes(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, BODY_REV1)
    raw_sha, body_sha, off = _shas(raw)
    good = _envelope(
        evaluation_id="artifact-good",
        observed_at="2026-11-23T17:42:00+00:00",
        body_sha=body_sha,
        raw_sha=raw_sha,
        offset=off,
    )

    def _bad(mutate):
        payload = _envelope(
            evaluation_id="artifact-bad",
            observed_at="2026-11-23T17:42:00+00:00",
            body_sha=body_sha,
            raw_sha=raw_sha,
            offset=off,
        )
        mutate(payload)
        return payload

    hostile = [
        "not-a-dict",
        ["a", "list"],
        None,
        42,
        _bad(lambda p: p.update(schema_version="writer.evaluation-envelope.v0")),
        _bad(lambda p: p.pop("evaluation_id")),
        _bad(lambda p: p.update(status="CURRENT")),
        _bad(lambda p: p.pop("work_object")),
        _bad(lambda p: p["work_object"].update(kind="chapter")),
        _bad(lambda p: p["work_object"].update(target_id="other.md")),
        _bad(lambda p: p["work_object"].update(source_hash="xyz")),
        _bad(lambda p: p["producer"].update(runtime_name="scoring")),
        _bad(lambda p: p.update(dimensions={})),
        _bad(lambda p: p.update(provenance=[])),
        _bad(lambda p: p["dimensions"].append({"dimension": "x"})),
        _bad(lambda p: p["findings"].append({"family": "artifact"})),
        _bad(
            lambda p: p["findings"].append(
                {"family": "artifact", "code": "X", "claim": ["not", "a", "string"]}
            )
        ),
        _bad(lambda p: p["work_object"].update(content_sha256="short")),
        _bad(lambda p: p["work_object"].update(body_offset_bytes=-1)),
        _bad(lambda p: p.pop("observed_at")),
        dict(good),  # duplicate evaluation_id of the good envelope
    ]
    with open_client(_runtime(tmp_path)) as client:
        context = _context(client, site, [good, *hostile])
    writer = next(m for m in context["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "CURRENT"  # the one good envelope still lands
    assert [item["evaluation_id"] for item in writer["value"]["evaluations"]] == ["artifact-good"]
    assert len(writer["value"]["rejected"]) == len(hostile)
    assert all(item["error"] for item in writer["value"]["rejected"])


def test_unavailable_post_raises_not_found(tmp_path: Path) -> None:
    from mission_control.core.errors import NotFound, ValidationProblem
    from mission_control.websites import context as ctx

    site = _hugo_site(tmp_path / "websites")
    _write_post(site, BODY_REV1)
    with open_client(_runtime(tmp_path)) as client:
        with client.app.state.database.session() as session:
            with pytest.raises(NotFound):
                ctx.build_site_post_context(
                    session,
                    website_id=SITE_ID,
                    blog_dir=site / "content" / "post",
                    identity="missing.md",
                )
            with pytest.raises(ValidationProblem):
                ctx.build_site_post_context(
                    session,
                    website_id=SITE_ID,
                    blog_dir=site / "content" / "post",
                    identity=IDENTITY,
                    writer_envelopes={"not": "a list"},
                )


def test_truncated_article_fails_safe(tmp_path: Path, monkeypatch) -> None:
    import mission_control.websites.evaluate as eval_mod
    import mission_control.websites.posts as posts_mod

    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, BODY_REV1)
    raw_sha = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(eval_mod, "run_pi_evaluation", lambda **kwargs: _outcome())
    monkeypatch.setenv("MISSION_CONTROL_BLOG_EVAL_MODEL", "fake-model")
    with open_client(_runtime(tmp_path)) as client:
        _evaluate(client)
        monkeypatch.setattr(posts_mod, "MAX_CONTENT_CHARS", 10)
        context = _context(
            client,
            site,
            [
                _envelope(
                    evaluation_id="artifact-eval-1",
                    observed_at="2026-11-23T17:41:00+00:00",
                    body_sha="0" * 64,
                    raw_sha=raw_sha,
                    offset=0,
                )
            ],
        )
    assert context["post"]["truncated"] is True
    assert context["post"]["text_sha256"] is None
    assert context["post"]["body_offset_bytes"] is None
    assert "refused rather than guessed" in context["extraction"]["note"]
    writer = next(m for m in context["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "UNAVAILABLE"
    assert writer["value"]["evaluations"][0]["derived"] == "UNVERIFIED"
    editorial = next(m for m in context["measures"] if m["id"] == "mission.site.post.editorial")
    # Raw bytes are exact even when the read is truncated: editorial still binds.
    assert editorial["status"] == "CURRENT"
    assert editorial["value"]["current"]["content_sha256"] == raw_sha


def test_envelope_status_unavailable_carried(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, BODY_REV1)
    raw_sha, body_sha, off = _shas(raw)
    envelope = _envelope(
        evaluation_id="qc-eval-1",
        observed_at="2026-11-23T17:41:00+00:00",
        body_sha=body_sha,
        raw_sha=raw_sha,
        offset=off,
        provider="qc",
        status="unavailable",
    )
    with open_client(_runtime(tmp_path)) as client:
        context = _context(client, site, [envelope])
    writer = next(m for m in context["measures"] if m["id"] == "mission.site.post.evaluations")
    assert writer["status"] == "UNAVAILABLE"
    assert writer["value"]["evaluations"][0]["derived"] == "UNAVAILABLE"


# ------------------------------------------------------- offsets


def test_body_span_to_raw_mapping() -> None:
    from mission_control.websites.context import body_span_to_raw, split_post_body

    raw = (FRONT + BODY_REV1).encode("utf-8")
    split = split_post_body(raw)
    assert split["note"] is None
    assert split["format"] == "toml"
    assert raw[split["offset"] :] == split["body"]
    needle = STABLE_QUOTE.encode("utf-8")
    body_pos = split["body"].find(needle)
    raw_pos = raw.find(needle)
    assert body_pos >= 0
    assert body_span_to_raw(body_pos, body_pos + len(needle), split["offset"]) == (
        raw_pos,
        raw_pos + len(needle),
    )
    assert body_span_to_raw(0, 5, None) is None
    assert body_span_to_raw(-1, 5, split["offset"]) is None
    assert body_span_to_raw(6, 5, split["offset"]) is None
    assert body_span_to_raw(True, 5, split["offset"]) is None


def test_split_unterminated_front_matter_unavailable() -> None:
    from mission_control.websites.context import split_post_body

    split = split_post_body(b'+++\ntitle = "No end"\n')
    assert split["body"] is None and split["offset"] is None
    assert "unterminated" in (split["note"] or "")
    assert split_post_body(b"no front matter here")["offset"] == 0


def test_deterministic_generated_at_override(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    _write_post(site, BODY_REV1)
    with open_client(_runtime(tmp_path)) as client:
        first = _context(client, site, generated_at="2026-11-23T00:00:00+00:00")
        second = _context(client, site, generated_at="2026-11-23T00:00:00+00:00")
    assert first["generated_at"] == "2026-11-23T00:00:00+00:00"
    assert first == second
