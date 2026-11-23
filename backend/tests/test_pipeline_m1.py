"""M1 pipeline projection tests (MC-BOOK-PIPELINE-01).

Hermetic: tmp registry, tmp manuscripts, tmp Writer artifacts. Read-only:
no Writer execution, no manuscript edits outside tmp fixtures (and those only
during fixture setup, never by the code under test).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from mission_control.publication import pipeline as pipe
from mission_control.publication.fingerprint import writer_source_digest


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def alpha_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Book alpha: 4 chapters + _index, mixed MRI/editing/validation states."""
    repo = tmp_path / "alpha"
    chapters = repo / "content" / "books" / "alpha"
    texts = {
        "01-chapter.md": "# One\n\nAlpha one.\n",
        "02-chapter.md": "# Two\n\nAlpha two.\n",
        "03-chapter.md": "# Three\n\nAlpha three.\n",
        "04-chapter.md": "# Four\n\nAlpha four.\n",
        "_index.md": "# Index\n",
    }
    for name, text in texts.items():
        _write(chapters / name, text)

    metadata = repo / "metadata"
    _write(metadata / "01-chapter.yaml", "title: One\nbeats:\n  - a\n")
    _write(metadata / "02-chapter.yaml", "{unclosed: [oops\n")
    _write(metadata / "04-chapter.yaml", "title: Four\n")

    mri_dir = repo / ".writer" / "mri" / "alpha"
    mri_dir.mkdir(parents=True, exist_ok=True)

    def mri_report(snapshot: str, status: str = "pass") -> dict:
        return {
            "target_id": "chapter",
            "snapshot_hash": snapshot,
            "observation": {},
            "alignment": {
                "declared_not_observed": [{"id": "d1"}],
                "observed_not_declared": [],
                "uncertainty_flags": [],
            },
            "provenance": {
                "observer_mode": "auto",
                "quality_model": "none",
                "snapshot_hash": snapshot,
                "metadata_sha256": "stored-not-recomputed-in-m1",
                "alignment_version": "v1",
                "observer_prompt_version": "p1",
                "stage_status": {
                    "observer": status,
                    "quality": status,
                    "sections": "ok",
                    "alignment": status,
                },
                "generated_at": "2026-01-01T00:00:00Z",
            },
        }

    live_01 = (chapters / "01-chapter.md").read_text(encoding="utf-8")
    (mri_dir / "01-chapter.mri.json").write_text(
        json.dumps(mri_report(_sha_text(live_01))), encoding="utf-8"
    )
    (mri_dir / "02-chapter.mri.json").write_text(
        json.dumps(mri_report(_sha_text("different text"))), encoding="utf-8"
    )
    (mri_dir / "04-chapter.mri.json").write_text("{oops not json", encoding="utf-8")
    # 03 has no report: missing.

    validation_dir = repo / ".writer" / "validation" / "chapters"
    validation_dir.mkdir(parents=True, exist_ok=True)
    live_v01 = (chapters / "01-chapter.md").read_text(encoding="utf-8")
    (validation_dir / "01-chapter.json").write_text(
        json.dumps(
            {
                "machine_status": "PASS",
                "source_digest": writer_source_digest(live_v01),
                "chapter_path": "01-chapter.md",
            }
        ),
        encoding="utf-8",
    )
    (validation_dir / "02-chapter.json").write_text(
        json.dumps(
            {
                "machine_status": "FAIL",
                "source_digest": writer_source_digest("something else"),
                "chapter_path": "02-chapter.md",
            }
        ),
        encoding="utf-8",
    )
    (validation_dir / "04-chapter.json").write_text(
        json.dumps({"machine_status": "PASS"}), encoding="utf-8"
    )
    # 03 has no report: missing.

    summary = {
        "schema_version": "writer-editing-summary-v1",
        "generated_at": "2026-01-02T00:00:00Z",
        "books": [
            {
                "project_id": "alpha",
                "report_id": "rep-1",
                "last_checked": "2026-01-02T00:00:00Z",
                "profile": "technical-nonfiction-v1",
                "chapters": [
                    {
                        "chapter_id": "chapter:alpha:01-chapter",
                        "source_path": str(chapters / "01-chapter.md"),
                        "source_fingerprint": _sha_bytes((chapters / "01-chapter.md").read_bytes()),
                        "status": "ok",
                        "status_band": "good",
                        "readable": True,
                    },
                    {
                        "chapter_id": "chapter:alpha:02-chapter",
                        "source_path": str(chapters / "02-chapter.md"),
                        "source_fingerprint": "0" * 64,
                        "status": "review_required",
                        "status_band": "watch",
                        "readable": True,
                    },
                    {
                        "chapter_id": "chapter:alpha:04-chapter",
                        "source_path": str(chapters / "04-chapter.md"),
                        "status": "ok",
                        "status_band": "good",
                        "readable": True,
                    },
                ],
            }
        ],
    }
    summary_path = tmp_path / "editing-summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setenv(pipe.EDITING_SUMMARY_ENV, str(summary_path))

    registry = {
        "projects": {
            "alpha": {
                "project_root": repo.as_posix(),
                "active": True,
                "tags": ["book"],
                "profile": "technical",
                "chapters": {"path": "content/books/alpha", "pattern": "*.md"},
                "metadata": {"path": "metadata", "pattern": "*.yaml"},
                "exclude_prefixes": ["00"],
                "book": {"manuscript": "alpha.md", "publication_status": "research"},
                "validation": {
                    "enabled": True,
                    "checks": [{"id": "manuscript_integrity", "required": True}],
                    "finalization": {"human_approval_required": True},
                },
            },
            "beta": {
                "project_root": (tmp_path / "beta").as_posix(),
                "active": True,
                "tags": ["book"],
                "profile": "technical",
                "chapters": {"path": "content", "pattern": "*.md"},
                "book": {"manuscript": "beta.md", "publication_status": "research"},
            },
        }
    }
    beta_chapters = tmp_path / "beta" / "content"
    _write(beta_chapters / "01-chapter.md", "# Beta one.\n")
    registry_path = tmp_path / "projects.yaml"
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    monkeypatch.setenv("MISSION_CONTROL_WRITER_REGISTRY", str(registry_path))
    return {"repo": repo, "chapters": chapters, "registry": registry_path}


def _snapshot_files(root: Path) -> dict[str, bytes]:
    return {str(p): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --- registry --------------------------------------------------------------


def test_registry_is_versioned_and_conservative():
    payload = pipe.list_stages()
    assert payload["registry_version"] == pipe.PIPELINE_REGISTRY_VERSION
    by_id = {s["stage_id"]: s for s in payload["stages"]}
    assert set(by_id) == {
        "metadata",
        "mri",
        "patterns",
        "strengthening",
        "editing",
        "validation",
        "graph",
    }
    assert {s for s in by_id if by_id[s]["availability"] == "implemented"} == {
        "metadata",
        "mri",
        "editing",
        "validation",
    }
    assert by_id["patterns"]["availability"] == "planned"
    assert by_id["strengthening"]["availability"] == "planned"
    assert by_id["graph"]["availability"] == "unavailable"
    orders = [s["presentation_order"] for s in payload["stages"]]
    assert orders == sorted(orders)


# --- discovery ---------------------------------------------------------------


def test_chapter_discovery_excludes_index_stems(alpha_repo: dict):
    payload = pipe.get_book_pipeline(None, None, "alpha")
    assert payload["known"] is True
    ids = [c["chapter_id"] for c in payload["chapters"]]
    assert ids == ["01-chapter", "02-chapter", "03-chapter", "04-chapter"]


def test_unknown_book_is_explicit(alpha_repo: dict):
    payload = pipe.get_book_pipeline(None, None, "gamma")
    assert payload["known"] is False
    assert "not registered" in payload["diagnostics"].lower()


# --- MRI ---------------------------------------------------------------------


def test_mri_current_stale_missing_invalid(alpha_repo: dict):
    detail = pipe.get_stage_detail(None, None, "alpha", "mri")
    assert detail is not None
    by_id = {c["chapter_id"]: c for c in detail["cells"]}
    c01 = by_id["01-chapter"]
    assert (c01["result"], c01["freshness"]) == ("passed", "current")
    assert c01["digest_match"] is True
    assert c01["has_evidence"] is True
    c02 = by_id["02-chapter"]
    assert c02["freshness"] == "stale"
    assert c02["result"] == "passed"  # result preserved, not failed by staleness
    assert c02["digest_match"] is False
    c03 = by_id["03-chapter"]
    assert c03["has_evidence"] is False
    assert (c03["result"], c03["freshness"]) == ("unknown", "unknown")
    c04 = by_id["04-chapter"]
    assert c04["has_evidence"] is True
    assert (c04["result"], c04["freshness"]) == ("unknown", "unknown")
    assert "json" in c04["diagnostics"].lower()


# --- editing -----------------------------------------------------------------


def test_editing_current_stale_missing_unbound(alpha_repo: dict):
    detail = pipe.get_stage_detail(None, None, "alpha", "editing")
    assert detail is not None
    by_id = {c["chapter_id"]: c for c in detail["cells"]}
    assert (by_id["01-chapter"]["result"], by_id["01-chapter"]["freshness"]) == (
        "passed",
        "current",
    )
    c02 = by_id["02-chapter"]
    assert c02["freshness"] == "stale"
    assert c02["result"] == "passed"  # completed analysis, issues reported
    c03 = by_id["03-chapter"]
    assert c03["has_evidence"] is False
    assert (c03["result"], c03["freshness"]) == ("unknown", "unknown")
    c04 = by_id["04-chapter"]
    assert c04["has_evidence"] is True
    assert (c04["result"], c04["freshness"]) == ("unknown", "unknown")
    assert "binding" in c04["diagnostics"].lower()


# --- validation --------------------------------------------------------------


def test_validation_current_stale_missing_unbound(alpha_repo: dict):
    detail = pipe.get_stage_detail(None, None, "alpha", "validation")
    assert detail is not None
    by_id = {c["chapter_id"]: c for c in detail["cells"]}
    assert (by_id["01-chapter"]["result"], by_id["01-chapter"]["freshness"]) == (
        "passed",
        "current",
    )
    c02 = by_id["02-chapter"]
    assert (c02["result"], c02["freshness"]) == ("failed", "stale")
    c03 = by_id["03-chapter"]
    assert c03["has_evidence"] is False
    c04 = by_id["04-chapter"]
    assert c04["has_evidence"] is True
    # Stored verdict is preserved; the missing binding affects freshness only.
    assert (c04["result"], c04["freshness"]) == ("passed", "unknown")


# --- metadata ----------------------------------------------------------------


def test_metadata_present_invalid_missing(alpha_repo: dict):
    detail = pipe.get_stage_detail(None, None, "alpha", "metadata")
    assert detail is not None
    by_id = {c["chapter_id"]: c for c in detail["cells"]}
    c01 = by_id["01-chapter"]
    assert c01["has_evidence"] is True
    assert (c01["result"], c01["freshness"]) == ("unknown", "unknown")
    c02 = by_id["02-chapter"]
    assert c02["result"] == "failed"  # invalid YAML is a verified defect
    c03 = by_id["03-chapter"]
    assert c03["has_evidence"] is False


# --- aggregation -------------------------------------------------------------


def test_aggregation_partitions_without_double_counting(alpha_repo: dict):
    payload = pipe.get_book_pipeline(None, None, "alpha")
    mri = payload["summaries"]["mri"]
    assert mri["applicable"] == 4
    assert mri["current"] + mri["stale"] + mri["missing"] + mri["unknown"] == 4
    assert (mri["current"], mri["stale"], mri["missing"], mri["unknown"]) == (1, 1, 1, 1)
    assert mri["coverage"] == "1/4 current"
    assert mri["coverage_fraction"] == pytest.approx(0.25)
    assert mri["fully_current"] is False


def test_new_chapter_is_missing_not_current(alpha_repo: dict):
    _write(alpha_repo["chapters"] / "05-chapter.md", "# Five\n")
    payload = pipe.get_book_pipeline(None, None, "alpha")
    assert payload["summaries"]["mri"]["missing"] == 2
    assert payload["summaries"]["mri"]["coverage"] == "1/5 current"


def test_planned_stages_report_unavailable(alpha_repo: dict):
    payload = pipe.get_book_pipeline(None, None, "alpha")
    assert payload["summaries"]["patterns"]["availability"] == "planned"
    assert payload["summaries"]["graph"]["availability"] == "unavailable"
    for cell in payload["matrix"]["graph"]:
        assert cell["result"] == "unavailable"


def test_beta_stages_not_applicable(alpha_repo: dict):
    validation = pipe.get_stage_detail(None, None, "beta", "validation")
    assert validation is not None
    for cell in validation["cells"]:
        assert cell["applicable"] is False
        assert cell["result"] == "unavailable"
    metadata = pipe.get_stage_detail(None, None, "beta", "metadata")
    assert metadata is not None
    for cell in metadata["cells"]:
        assert cell["result"] == "unavailable"


def test_source_dir_unavailable_is_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    registry = {
        "projects": {
            "gone": {
                "project_root": str(tmp_path / "does-not-exist"),
                "active": True,
                "tags": ["book"],
                "profile": "technical",
                "chapters": {"path": "content", "pattern": "*.md"},
                "book": {"manuscript": "gone.md"},
            }
        }
    }
    path = tmp_path / "projects.yaml"
    path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    monkeypatch.setenv("MISSION_CONTROL_WRITER_REGISTRY", str(path))
    payload = pipe.get_book_pipeline(None, None, "gone")
    assert payload["known"] is True
    assert payload["chapters"] == []
    assert "not available" in payload["discovery"].get("error", "").lower()
    assert payload["summaries"]["mri"]["coverage"] == "0/0"


def test_digest_algorithms_are_not_interchanged(alpha_repo: dict):
    mri = pipe.get_stage_detail(None, None, "alpha", "mri")
    editing = pipe.get_stage_detail(None, None, "alpha", "editing")
    validation = pipe.get_stage_detail(None, None, "alpha", "validation")
    assert mri is not None and editing is not None and validation is not None
    algos = {
        mri["cells"][0]["digest_algorithm"],
        editing["cells"][0]["digest_algorithm"],
        validation["cells"][0]["digest_algorithm"],
    }
    assert len(algos) == 3


# --- read-only + stability ---------------------------------------------------


def test_projection_writes_nothing(alpha_repo: dict):
    before = _snapshot_files(alpha_repo["repo"].parent)
    pipe.get_book_pipeline(None, None, "alpha")
    for stage in ("mri", "editing", "validation", "metadata"):
        pipe.get_stage_detail(None, None, "alpha", stage)
    after = _snapshot_files(alpha_repo["repo"].parent)
    assert before == after


def test_repeated_reads_are_stable(alpha_repo: dict):
    first = pipe.get_book_pipeline(None, None, "alpha")
    second = pipe.get_book_pipeline(None, None, "alpha")
    assert first == second


# --- API ---------------------------------------------------------------------


def test_api_stages_registry(client, alpha_repo: dict):
    response = client.get("/api/pipeline/stages")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["registry_version"] == pipe.PIPELINE_REGISTRY_VERSION
    assert len(body["stages"]) == 7


def test_api_book_summary_and_matrix(client, alpha_repo: dict):
    response = client.get("/api/pipeline/books/alpha")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == "alpha"
    assert len(body["chapters"]) == 4
    assert body["summaries"]["mri"]["coverage"] == "1/4 current"
    assert set(body["matrix"]) == {
        "metadata",
        "mri",
        "patterns",
        "strengthening",
        "editing",
        "validation",
        "graph",
    }
    assert len(body["matrix"]["mri"]) == 4


def test_api_stage_detail(client, alpha_repo: dict):
    response = client.get("/api/pipeline/books/alpha/stages/editing")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stage"]["stage_id"] == "editing"
    assert len(body["cells"]) == 4
    assert body["cells"][0]["digest_algorithm"] == "source_fingerprint:sha256-raw-bytes"


def test_api_unknown_book_and_stage_404(client, alpha_repo: dict):
    assert client.get("/api/pipeline/books/gamma").status_code == 404
    assert client.get("/api/pipeline/books/alpha/stages/nope").status_code == 404


# --- cross-book overview (M2) --------------------------------------------------


def test_overview_matches_per_book_summaries(alpha_repo: dict):
    overview = pipe.get_pipeline_overview(None, None)
    assert overview["registry_version"] == pipe.PIPELINE_REGISTRY_VERSION
    assert overview["book_count"] == 2
    assert len(overview["stages"]) == 7
    assert isinstance(overview["elapsed_ms"], int)
    by_id = {b["project_id"]: b for b in overview["books"]}
    assert set(by_id) == {"alpha", "beta"}
    single = pipe.get_book_pipeline(None, None, "alpha")
    assert by_id["alpha"]["summaries"] == single["summaries"]
    assert by_id["alpha"]["applicable_chapters"] == 4
    assert by_id["beta"]["summaries"]["validation"]["availability"] == "implemented"
    beta_row = next(b for b in overview["books"] if b["project_id"] == "beta")
    beta_validation = pipe.get_stage_detail(None, None, "beta", "validation")
    assert beta_row["summaries"]["validation"] == {
        **{k: v for k, v in pipe.summarize_stage(beta_validation["cells"]).items()},
        "availability": "implemented",
    }
    for row in overview["books"]:
        assert isinstance(row["elapsed_ms"], int)
        assert row["known"] is True


def test_overview_parses_shared_store_once(alpha_repo: dict, monkeypatch: pytest.MonkeyPatch):
    calls = {"count": 0}
    real_parse = pipe._parse_editing_doc

    def counting(path):
        calls["count"] += 1
        return real_parse(path)

    monkeypatch.setattr(pipe, "_parse_editing_doc", counting)
    pipe.get_pipeline_overview(None, None)
    # alpha + beta resolve to the same env-override store: one parse.
    assert calls["count"] == 1


def test_cache_invalidates_on_rewrite(alpha_repo: dict):
    pipe._DOC_CACHE.clear()
    first = pipe.get_stage_detail(None, None, "alpha", "mri")
    assert first is not None
    assert first["summary"]["stale"] == 1
    live = (alpha_repo["chapters"] / "02-chapter.md").read_text(encoding="utf-8")
    report_path = alpha_repo["repo"] / ".writer" / "mri" / "alpha" / "02-chapter.mri.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["snapshot_hash"] = _sha_text(live)
    report["provenance"]["snapshot_hash"] = _sha_text(live)
    report_path.write_text(json.dumps(report), encoding="utf-8")
    second = pipe.get_stage_detail(None, None, "alpha", "mri")
    assert second is not None
    # Rewritten artifact (new mtime) misses the cache: chapter 02 is current now.
    assert second["summary"]["stale"] == 0
    assert second["summary"]["current"] == 2


def test_cached_parse_shares_single_read(alpha_repo: dict, monkeypatch: pytest.MonkeyPatch):
    pipe._DOC_CACHE.clear()
    calls = {"count": 0}
    real_load = pipe._load_json_artifact

    def counting(path):
        calls["count"] += 1
        return real_load(path)

    monkeypatch.setattr(pipe, "_load_json_artifact", counting)
    report = alpha_repo["repo"] / ".writer" / "mri" / "alpha" / "01-chapter.mri.json"
    assert pipe._load_json_cached(report)[1] is None
    assert pipe._load_json_cached(report)[1] is None
    assert calls["count"] == 1


def test_api_overview(client, alpha_repo: dict):
    response = client.get("/api/pipeline/overview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["book_count"] == 2
    by_id = {b["project_id"]: b for b in body["books"]}
    assert by_id["alpha"]["summaries"]["mri"]["coverage"] == "1/4 current"
    assert "elapsed_ms" in body
