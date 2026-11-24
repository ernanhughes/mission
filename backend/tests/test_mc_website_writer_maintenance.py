"""LIVING-WORK-BLOG-01 D5: automatic deterministic Writer observation maintenance.

Bounded pilot: isolated Hugo fixture, disposable database, real deterministic
Writer Artifact detector. Proves the lifecycle — missing, eligible, executed,
stored, current, no duplicate for unchanged content, stale after edit,
reprocessing after invalidation, history preservation, rename isolation —
with no source writes and no model calls.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from helpers import open_client
from mission_control.adapters.base import ActionContext
from mission_control.config import RuntimeSettings

SITE_ID = "website-programmer-ie"
IDENTITY = "alpha.md"
FRONT = '+++\ntitle = "Alpha"\ndate = "2024-03-10T10:00:00+00:00"\n+++\n\n'
BODY_V1 = (
    "The city wakes slowly. The city stretches its avenues. The city hums with bicycles.\n"
    "\n"
    "The thesis of this note is simple: small habits compound into durable skill.\n"
)
BODY_V2 = BODY_V1 + "\nA later paragraph arrives with fresh examples and longer sentences.\n"


def _runtime(tmp_path: Path) -> RuntimeSettings:
    base = RuntimeSettings(
        repo_root=Path(__file__).resolve().parents[2],
        data_dir=tmp_path / "data",
        config_dir=Path(__file__).resolve().parents[2] / "config",
        frontend_dist=tmp_path / "dist",
        book_root=tmp_path / "b",
        fiction_book_root=tmp_path / "fb",
        host="127.0.0.1",
        port=8793,
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


def _write_post(site: Path, name: str, body: str) -> bytes:
    raw = (FRONT + body).encode("utf-8")
    (site / "content" / "post" / name).write_bytes(raw)
    return raw


def _action_context(tmp_path: Path) -> ActionContext:
    repo = tmp_path / "writer-checkout"
    repo.mkdir(exist_ok=True)
    return ActionContext(
        application_id="writer",
        data_dir=tmp_path / "data",
        application_repository_path=str(repo),
        config={},
    )


# --- fingerprint contract ----------------------------------------------------


def test_auto_fingerprint_is_deterministic_and_input_sensitive() -> None:
    from mission_control.websites import maintenance as _maintenance

    base = _maintenance.auto_fingerprint(source_digest="a", metadata_digest="b", profile="post")
    assert base == _maintenance.auto_fingerprint(
        source_digest="a", metadata_digest="b", profile="post"
    )
    assert base != _maintenance.auto_fingerprint(
        source_digest="a2", metadata_digest="b", profile="post"
    )
    assert base != _maintenance.auto_fingerprint(
        source_digest="a", metadata_digest="b2", profile="post"
    )
    assert base != _maintenance.auto_fingerprint(
        source_digest="a",
        metadata_digest="b",
        profile="post",
        policy_version="blog-auto-v2",
    )


# --- pure decision matrix ----------------------------------------------------


def _state(freshness: str, *, has_evidence: bool = True) -> dict[str, Any]:
    return {"has_evidence": has_evidence, "freshness": freshness, "result": "unknown"}


def test_decide_post_pure_matrix() -> None:
    from mission_control.websites import maintenance as _maintenance

    kw: dict[str, Any] = {
        "site_paused": False,
        "state": _state("missing", has_evidence=False),
        "live_source_digest": "s",
        "live_content_digest": "c",
        "active_execution_id": None,
        "last_receipt": None,
        "consecutive_failures": 0,
        "last_failure_at": None,
    }
    assert _maintenance.decide_post(enabled=False, **kw).action == "wait"
    assert (
        _maintenance.decide_post(
            enabled=True, site_paused=True, **{k: v for k, v in kw.items() if k != "site_paused"}
        ).action
        == "blocked"
    )
    busy = dict(kw, enabled=True, active_execution_id="exec-1")
    assert _maintenance.decide_post(**busy).action == "wait"
    assert _maintenance.decide_post(enabled=True, **kw).action == "run"
    assert (
        _maintenance.decide_post(enabled=True, **{**kw, "live_source_digest": None}).action
        == "blocked"
    )
    current = dict(kw, enabled=True, state=_state("current"))
    assert _maintenance.decide_post(**current).action == "skip"
    matching = dict(
        current, last_receipt={"fingerprint": _maintenance.decide_post(**current).fingerprint}
    )
    assert _maintenance.decide_post(**matching).action == "skip"
    failed = dict(
        kw,
        enabled=True,
        consecutive_failures=3,
        last_receipt={"fingerprint": _maintenance.decide_post(enabled=True, **kw).fingerprint},
    )
    assert _maintenance.decide_post(**failed).action == "blocked"


# --- adapter validation + real execution -------------------------------------


def test_adapter_validates_policy_and_identity(tmp_path: Path) -> None:
    from mission_control.adapters.writer import WriterAdapter
    from mission_control.websites import maintenance as _maintenance

    site = _hugo_site(tmp_path / "websites")
    _write_post(site, IDENTITY, BODY_V1)
    blog_dir = str(site / "content" / "post")
    adapter = WriterAdapter()
    context = _action_context(tmp_path)
    good = {
        "website_id": SITE_ID,
        "article_identity": IDENTITY,
        "blog_dir": blog_dir,
        "policy_version": _maintenance.BLOG_AUTO_POLICY_VERSION,
    }
    adapter.validate_action("writer_observe_post_auto", dict(good), context)
    with __import__("pytest").raises(ValueError):
        adapter.validate_action(
            "writer_observe_post_auto", {**good, "policy_version": "pipeline-auto-v1"}, context
        )
    with __import__("pytest").raises(ValueError):
        adapter.validate_action(
            "writer_observe_post_auto", {**good, "article_identity": "../escape.md"}, context
        )


def test_adapter_executes_real_detector_with_receipt_only(tmp_path: Path) -> None:
    from mission_control.adapters.writer import WriterAdapter
    from mission_control.websites import maintenance as _maintenance

    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, IDENTITY, BODY_V1)
    blog_dir = str(site / "content" / "post")
    adapter = WriterAdapter()
    context = _action_context(tmp_path)
    result = asyncio.run(
        adapter.execute_action(
            "writer_observe_post_auto",
            {
                "website_id": SITE_ID,
                "article_identity": IDENTITY,
                "blog_dir": blog_dir,
                "policy_version": _maintenance.BLOG_AUTO_POLICY_VERSION,
            },
            context,
        )
    )
    assert result.status == "succeeded", result.error
    assert result.result["schema_version"] == "mc.writer_observe_post.v1"
    assert (
        result.result["source_digest"]
        == hashlib.sha256(
            __import__(
                "mission_control.websites.context", fromlist=["split_post_body"]
            ).split_post_body(raw)["body"]
        ).hexdigest()
    )
    assert result.result["content_digest"] == hashlib.sha256(raw).hexdigest()
    assert result.result["auto_fingerprint"] == result.result["auto_inputs"]["fingerprint"]
    assert (site / "content" / "post" / IDENTITY).read_bytes() == raw  # no source writes


# --- full pilot lifecycle ----------------------------------------------------


def test_pilot_lifecycle_missing_to_current_to_stale_to_reprocessed(tmp_path: Path) -> None:
    from mission_control.adapters.writer import WriterAdapter
    from mission_control.websites import maintenance as _maintenance
    from mission_control.websites import post_artifact as _post_artifact

    site = _hugo_site(tmp_path / "websites")
    raw_v1 = _write_post(site, IDENTITY, BODY_V1)
    blog_dir = site / "content" / "post"
    adapter = WriterAdapter()
    context = _action_context(tmp_path)

    with open_client(_runtime(tmp_path)) as client:
        database = client.app.state.database
        with database.session() as session:
            assert _maintenance.is_auto_enabled(session) is False  # off by default
            _maintenance.set_auto_enabled(session, True)
            session.commit()
        # 1. Initial state: missing.
        with database.session() as session:
            state = _maintenance.project_post_state(
                session,
                website_id=SITE_ID,
                identity=IDENTITY,
                relpath=IDENTITY,
                blog_dir=blog_dir,
            )
        assert state["has_evidence"] is False and state["freshness"] == "missing"

        # 2. Eligible: pure decision says run.
        decision = _maintenance.decide_post(
            enabled=True,
            site_paused=False,
            state={**state, "applicable": True},
            live_source_digest=state["live_digest"],
            live_content_digest=hashlib.sha256(raw_v1).hexdigest(),
            active_execution_id=None,
            last_receipt=None,
            consecutive_failures=0,
            last_failure_at=None,
        )
        assert decision.action == "run"

        # 3. One real execution → receipt (no storage yet).
        result = asyncio.run(
            adapter.execute_action(
                "writer_observe_post_auto",
                {
                    "website_id": SITE_ID,
                    "article_identity": IDENTITY,
                    "blog_dir": str(blog_dir),
                    "policy_version": _maintenance.BLOG_AUTO_POLICY_VERSION,
                },
                context,
            )
        )
        assert result.status == "succeeded", result.error

        # 4. Stored evidence → current.
        with database.session() as session:
            envelope = _post_artifact.artifact_envelope_for_live_post(
                blog_dir, identity=IDENTITY, observed_at=result.result["observed_at"]
            )
            assert envelope is not None
            row = _maintenance.store_observation(
                session,
                website_id=SITE_ID,
                identity=IDENTITY,
                envelope=envelope,
                execution_id="exec-pilot-1",
                fingerprint_inputs=result.result["auto_inputs"],
            )
            session.commit()
            assert row.body_sha256 == result.result["source_digest"]
            state = _maintenance.project_post_state(
                session,
                website_id=SITE_ID,
                identity=IDENTITY,
                relpath=IDENTITY,
                blog_dir=blog_dir,
            )
        assert state["freshness"] == "current" and state["history_count"] == 1

        # 5. No duplicate for unchanged content: decision is skip.
        decision = _maintenance.decide_post(
            enabled=True,
            site_paused=False,
            state={**state, "applicable": True},
            live_source_digest=state["live_digest"],
            live_content_digest=hashlib.sha256(raw_v1).hexdigest(),
            active_execution_id=None,
            last_receipt={"fingerprint": row.fingerprint},
            consecutive_failures=0,
            last_failure_at=None,
        )
        assert decision.action == "skip"

        # 6. Fixture edit → stale, history preserved.
        raw_v2 = _write_post(site, IDENTITY, BODY_V2)
        assert raw_v2 != raw_v1
        with database.session() as session:
            state = _maintenance.project_post_state(
                session,
                website_id=SITE_ID,
                identity=IDENTITY,
                relpath=IDENTITY,
                blog_dir=blog_dir,
            )
        assert state["freshness"] == "stale" and state["history_count"] == 1

        # 7. Reprocessing after invalidation → current again, two rows kept.
        with database.session() as session:
            envelope2 = _post_artifact.artifact_envelope_for_live_post(
                blog_dir, identity=IDENTITY, observed_at="2026-11-23T00:00:01+00:00"
            )
            assert envelope2 is not None
            _maintenance.store_observation(
                session,
                website_id=SITE_ID,
                identity=IDENTITY,
                envelope=envelope2,
                execution_id="exec-pilot-2",
                fingerprint_inputs=_maintenance.build_auto_inputs(
                    source_digest=envelope2["work_object"]["source_hash"],
                    content_digest=envelope2["work_object"]["content_sha256"],
                ),
            )
            session.commit()
            state = _maintenance.project_post_state(
                session,
                website_id=SITE_ID,
                identity=IDENTITY,
                relpath=IDENTITY,
                blog_dir=blog_dir,
            )
        assert state["freshness"] == "current" and state["history_count"] == 2

        # 8. Rename isolation: new identity starts missing; old history retained.
        (blog_dir / IDENTITY).rename(blog_dir / "renamed.md")
        with database.session() as session:
            from sqlalchemy import func, select
            from mission_control.models import WebsitePostWriterObservation

            new_state = _maintenance.project_post_state(
                session,
                website_id=SITE_ID,
                identity="renamed.md",
                relpath="renamed.md",
                blog_dir=blog_dir,
            )
            old_rows = session.scalar(
                select(func.count())
                .select_from(WebsitePostWriterObservation)
                .where(WebsitePostWriterObservation.article_identity == IDENTITY)
            )
        assert new_state["freshness"] == "missing" and new_state["history_count"] == 0
        assert old_rows == 2


# --- collection integration --------------------------------------------------


def test_collection_writer_evidence_tracks_lifecycle_without_touching_editorial(
    tmp_path: Path,
) -> None:
    from mission_control.websites import collection as _collection
    from mission_control.websites import maintenance as _maintenance
    from mission_control.websites import post_artifact as _post_artifact

    site = _hugo_site(tmp_path / "websites")
    raw = _write_post(site, IDENTITY, BODY_V1)
    blog_dir = site / "content" / "post"
    with open_client(_runtime(tmp_path)) as client:
        database = client.app.state.database
        with database.session() as session:
            before = _collection.build_collection_quality_map(
                session, website_id=SITE_ID, blog_dir=blog_dir
            )
        assert before["coverage"]["unevaluated"] == 1  # editorial untouched
        writer = before["writer_evidence"]
        assert writer["missing"] == 1 and writer["current"] == 0
        assert writer["posts"][0]["freshness"] == "missing"

        with database.session() as session:
            envelope = _post_artifact.artifact_envelope_for_live_post(
                blog_dir, identity=IDENTITY, observed_at="2026-11-23T00:00:00+00:00"
            )
            assert envelope is not None
            _maintenance.store_observation(
                session,
                website_id=SITE_ID,
                identity=IDENTITY,
                envelope=envelope,
                execution_id="exec-coll-1",
                fingerprint_inputs=_maintenance.build_auto_inputs(
                    source_digest=envelope["work_object"]["source_hash"],
                    content_digest=envelope["work_object"]["content_sha256"],
                ),
            )
            session.commit()
            after = _collection.build_collection_quality_map(
                session, website_id=SITE_ID, blog_dir=blog_dir
            )
        # Editorial keys byte-identical in shape; only the new block changed.
        assert after["coverage"] == before["coverage"]
        assert after["scores"]["n_scored"] == before["scores"]["n_scored"]
        assert after["writer_evidence"]["current"] == 1
        assert after["writer_evidence"]["posts"][0]["freshness"] == "current"
        assert after["writer_evidence"]["posts"][0]["stored"]["finding_count"] >= 0

        _write_post(site, IDENTITY, BODY_V2)
        with database.session() as session:
            stale_map = _collection.build_collection_quality_map(
                session, website_id=SITE_ID, blog_dir=blog_dir
            )
        assert stale_map["writer_evidence"]["stale"] == 1
        assert stale_map["coverage"]["unevaluated"] == 1  # editorial still untouched
        assert (blog_dir / IDENTITY).read_bytes() != raw  # only our fixture edit changed bytes


# --- endpoints -----------------------------------------------------------------


def test_writer_maintenance_endpoints_status_history_reconcile_dry_run(tmp_path: Path) -> None:
    site = _hugo_site(tmp_path / "websites")
    _write_post(site, IDENTITY, BODY_V1)
    with open_client(_runtime(tmp_path)) as client:
        response = client.get(f"/api/websites/{SITE_ID}/writer-maintenance/status")
        assert response.status_code == 200, response.text
        assert response.json()["enabled"] is False
        assert response.json()["policy_version"] == "blog-auto-v1"

        history = client.get(f"/api/websites/{SITE_ID}/writer-observations/{IDENTITY}")
        assert history.status_code == 200, history.text
        assert history.json()["history_count"] == 0

        assert client.get(f"/api/websites/{SITE_ID}/writer-observations/nope.md").status_code == 404

        reconcile = client.post(
            f"/api/websites/{SITE_ID}/writer-maintenance/reconcile", json={"dry_run": True}
        )
        assert reconcile.status_code == 200, reconcile.text
        assert reconcile.json()["dry_run"] is True
        assert reconcile.json()["enabled"] is False

        toggle = client.post(
            f"/api/websites/{SITE_ID}/writer-maintenance/enabled", json={"enabled": True}
        )
        assert toggle.status_code == 200 and toggle.json()["enabled"] is True
        pause = client.post(
            f"/api/websites/{SITE_ID}/writer-maintenance/pause",
            json={"website_id": SITE_ID, "paused": True},
        )
        assert pause.status_code == 200 and SITE_ID in pause.json()["paused_websites"]
        unpause = client.post(
            f"/api/websites/{SITE_ID}/writer-maintenance/pause",
            json={"website_id": SITE_ID, "paused": False},
        )
        assert unpause.json()["paused_websites"] == []
        back_off = client.post(
            f"/api/websites/{SITE_ID}/writer-maintenance/enabled", json={"enabled": False}
        )
        assert back_off.json()["enabled"] is False


def test_ingest_is_idempotent_and_binding_checked(tmp_path: Path) -> None:
    from mission_control.models import WebsitePostWriterObservation
    from mission_control.websites import maintenance as _maintenance
    from mission_control.websites import post_artifact as _post_artifact

    site = _hugo_site(tmp_path / "websites")
    _write_post(site, IDENTITY, BODY_V1)
    blog_dir = site / "content" / "post"
    with open_client(_runtime(tmp_path)) as client:
        database = client.app.state.database
        with database.session() as session:
            envelope = _post_artifact.artifact_envelope_for_live_post(
                blog_dir, identity=IDENTITY, observed_at="2026-11-23T00:00:00+00:00"
            )
            assert envelope is not None
            execution = type(
                "Execution",
                (),
                {
                    "id": "exec-ingest-1",
                    "action_id": "writer_observe_post_auto",
                    "status": "succeeded",
                    "parameters": {"website_id": SITE_ID, "article_identity": IDENTITY},
                    "result": {
                        "source_digest": envelope["work_object"]["source_hash"],
                        "observed_at": envelope["observed_at"],
                        "auto_inputs": _maintenance.build_auto_inputs(
                            source_digest=envelope["work_object"]["source_hash"],
                            content_digest=envelope["work_object"]["content_sha256"],
                        ),
                    },
                },
            )()
            first = _maintenance.ingest_completed_execution(
                session, execution=execution, blog_dir=blog_dir
            )
            session.commit()
            assert first is not None
            second = _maintenance.ingest_completed_execution(
                session, execution=execution, blog_dir=blog_dir
            )
            session.commit()
            from sqlalchemy import func, select

            count = session.scalar(select(func.count()).select_from(WebsitePostWriterObservation))
            assert second.id == first.id and count == 1
