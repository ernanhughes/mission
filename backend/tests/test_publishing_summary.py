"""Publishing workbench tests (MC-PUBLISH-01).

Read-only: no validator, build, approval or publication is ever triggered.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import select

from mission_control.config import RuntimeSettings
from mission_control.models import Book
from mission_control.persistence.db import Database
from mission_control.persistence.migrations import apply_migrations
from mission_control.persistence.seed import seed_defaults
from mission_control.publication.publishing import get_publishing_summary


def _chapters(book_dir: Path, count: int = 3) -> Path:
    book_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        (book_dir / f"{index:02d}-chapter.md").write_text("# c\n", encoding="utf-8")
    return book_dir


def _registry(tmp_path: Path, roots: dict[str, Path], extra: str = "") -> Path:
    lines = ["projects:"]
    for pid, root in roots.items():
        lines.append(f"  {pid}:")
        lines.append(f"    project_root: {root.as_posix()}")
        lines.append("    active: true")
        lines.append("    tags: [book]")
        lines.append("    profile: technical")
        lines.append("    chapters:")
        lines.append("      path: content/books/" + pid)
        lines.append("      pattern: '*.md'")
        lines.append("    book:")
        lines.append(f"      manuscript: {pid}.md")
        lines.append("      publication_status: research")
        lines.append("    validation:")
        lines.append("      enabled: true")
        lines.append("      finalization:")
        lines.append("        human_approval_required: true")
        lines.append("      checks:")
        lines.append("        - {id: manuscript_integrity, required: true, blocking: true}")
        lines.append("        - {id: qc, required: true, blocking: true}")
        lines.append("        - {id: readthrough, required: true, blocking: true}")
    path = tmp_path / "projects.yaml"
    path.write_text("\n".join(lines) + "\n" + extra, encoding="utf-8")
    return path


def _seed_db(runtime: RuntimeSettings) -> Database:
    database = Database(runtime)
    apply_migrations(database)
    with database.session() as session:
        seed_defaults(session, runtime)
    return database


def _by_type(summary: dict, evidence_type: str) -> dict:
    for item in summary["evidence"]:
        if item["evidence_type"] == evidence_type:
            return item
    raise AssertionError(f"missing evidence {evidence_type}")


def test_math_like_book_reports_honest_unknowns(
    runtime: RuntimeSettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "math"
    _chapters(repo / "content" / "books" / "math", 4)
    report = repo / "artifacts" / "math01" / "report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {
                "generated_at": "2026-11-01T00:00:00Z",
                "assessments": [
                    {
                        "claim_id": "a-1",
                        "overall_status": "formally_verified",
                        "unresolved_obligations": [],
                    },
                    {
                        "claim_id": "b-1",
                        "overall_status": "refuted_by_valid_counterexample",
                        "unresolved_obligations": ["Compose the bridge proof."],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    dist = tmp_path / "bbroot" / "dist"
    dist.mkdir(parents=True)
    (dist / "math.epub").write_bytes(b"0" * 64)
    monkeypatch.setenv("MISSION_CONTROL_WRITER_REGISTRY", str(_registry(tmp_path, {"math": repo})))
    monkeypatch.setenv("MISSION_CONTROL_BOOKBUILDER_ROOT", str(tmp_path / "bbroot"))
    database = _seed_db(runtime)
    # Point the seeded math book at the tmp repo (simulates Writer sync).
    with database.session() as session:
        book = session.scalar(select(Book).where(Book.project_id == "math"))
        assert book is not None
        book.manuscript_paths = [str(repo / "content" / "books" / "math")]
        session.flush()
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "math")
    assert summary["chapter_count"] == 4
    manuscript = _by_type(summary, "manuscript_discovery")
    assert manuscript["result"] == "passed"
    requirements = _by_type(summary, "writer_validation_requirements")
    assert requirements["result"] == "unknown"
    assert "manuscript_integrity" in requirements["diagnostics"]
    run = _by_type(summary, "writer_validation_run")
    assert run["result"] == "unknown"  # no .writer output; never run here
    proof = _by_type(summary, "proof_claims")
    assert proof["result"] == "unknown"  # native statuses preserved, no invented verdict
    assert "a-1" in proof["diagnostics"] or "a-1" in json.dumps(proof["detail"])
    assert "b-1" in json.dumps(proof["detail"])
    builder = _by_type(summary, "builder_artifacts")
    assert builder["result"] == "unknown"  # existence is not validity
    approval = _by_type(summary, "human_approval")
    assert approval["result"] == "pending"  # required, not recorded
    assert summary["publication_gate"] == "Unknown"
    database.dispose()


def test_writer_run_states_map_without_invention(
    runtime: RuntimeSettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "memory"
    _chapters(repo / "content" / "books" / "memory", 2)
    out = repo / ".writer" / "validation" / "chapters"
    out.mkdir(parents=True, exist_ok=True)
    (out / "01.json").write_text(
        json.dumps({"machine_status": "PASS"}), encoding="utf-8"
    )
    monkeypatch.setenv("MISSION_CONTROL_WRITER_REGISTRY", str(_registry(tmp_path, {"memory": repo})))
    monkeypatch.setenv("MISSION_CONTROL_BOOKBUILDER_ROOT", str(tmp_path / "empty-dist"))
    database = _seed_db(runtime)
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "memory")
    run = _by_type(summary, "writer_validation_run")
    assert run["result"] == "passed"
    database.dispose()


def test_failed_writer_run_surfaces_as_failed(
    runtime: RuntimeSettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "memory"
    _chapters(repo / "content" / "books" / "memory", 2)
    out = repo / ".writer" / "validation" / "chapters"
    out.mkdir(parents=True, exist_ok=True)
    (out / "01.json").write_text(
        json.dumps({"machine_status": "FAIL"}), encoding="utf-8"
    )
    monkeypatch.setenv("MISSION_CONTROL_WRITER_REGISTRY", str(_registry(tmp_path, {"memory": repo})))
    monkeypatch.setenv("MISSION_CONTROL_BOOKBUILDER_ROOT", str(tmp_path / "empty-dist"))
    database = _seed_db(runtime)
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "memory")
    run = _by_type(summary, "writer_validation_run")
    assert run["result"] == "failed"
    assert "writer_validation_run" in summary["blockers"]["failed"]
    database.dispose()


def test_fiction_drift_reports_unavailable_with_working_source(
    runtime: RuntimeSettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_root = tmp_path / "gone-latent"
    working = tmp_path / "working" / "latent" / "chapters"
    _chapters(working, 2)
    monkeypatch.setenv(
        "MISSION_CONTROL_WRITER_REGISTRY", str(_registry(tmp_path, {"latent": missing_root}))
    )
    monkeypatch.setenv("MISSION_CONTROL_BOOKBUILDER_ROOT", str(tmp_path / "empty-dist"))
    database = _seed_db(runtime)
    with database.session() as session:
        book = session.scalar(select(Book).where(Book.project_id == "latent"))
        if book is None:
            # Seed may not include latent; create the drifted working row.
            from mission_control.models import Project

            session.add(
                Project(
                    id="latent", name="Latent", kind="book", status="active",
                    priority=1000, pinned=False, archived=False, display_order=1000,
                )
            )
            session.flush()
            session.add(
                Book(
                    id="book-latent", project_id="latent", title="Latent",
                    manuscript_paths=[str(working)],
                )
            )
            session.flush()
        else:
            book.manuscript_paths = [str(working)]
            session.flush()
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "latent")
    manuscript = _by_type(summary, "manuscript_discovery")
    assert manuscript["result"] == "unavailable"
    assert "working source" in manuscript["diagnostics"]
    database.dispose()


def test_unregistered_book_stays_unknown(
    runtime: RuntimeSettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "MISSION_CONTROL_WRITER_REGISTRY", str(_registry(tmp_path, {}))
    )
    monkeypatch.setenv("MISSION_CONTROL_BOOKBUILDER_ROOT", str(tmp_path / "empty-dist"))
    database = _seed_db(runtime)
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "math")
    manuscript = _by_type(summary, "manuscript_discovery")
    assert manuscript["result"] == "unknown"
    database.dispose()


def test_live_math_proof_report_parses(
    runtime: RuntimeSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read-only parse of the real MATH01 report (no execution)."""
    report = Path(r"C:\books\math\artifacts\math01\report.json")
    if not report.is_file():
        pytest.skip("math proof report not present")
    database = _seed_db(runtime)
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "math")
    proof = _by_type(summary, "proof_claims")
    assert os.path.normcase(proof["source_reference"]) == os.path.normcase(str(report))
    assert proof["result"] == "unknown"
    assert "lorentz" in json.dumps(proof["detail"])
    database.dispose()


def test_stale_assessment_surfaces_in_summary(
    runtime: RuntimeSettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mission_control.publication import service as _pub

    repo = tmp_path / "math"
    book_dir = _chapters(repo / "content" / "books" / "math", 2)
    monkeypatch.setenv("MISSION_CONTROL_WRITER_REGISTRY", str(_registry(tmp_path, {"math": repo})))
    monkeypatch.setenv("MISSION_CONTROL_BOOKBUILDER_ROOT", str(tmp_path / "empty-dist"))
    database = _seed_db(runtime)
    with database.session() as session:
        book = session.scalar(select(Book).where(Book.project_id == "math"))
        assert book is not None
        book.manuscript_paths = [str(book_dir)]
        session.flush()
        record = _pub.create_assessment(session, runtime, project_id="math", technical_scope="pilot")
        assessment_id = record.id
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "math")
    mission = _by_type(summary, "mission_assessment")
    assert mission["freshness"] == "current"
    assert "mission_assessment" not in summary["blockers"]["stale"]
    # Change the manuscript, then refresh: stored evidence goes stale.
    (book_dir / "03-chapter.md").write_text("# third\n", encoding="utf-8")
    with database.session() as session:
        _pub.refresh_freshness(session, runtime, assessment_id)
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "math")
    mission = _by_type(summary, "mission_assessment")
    assert mission["freshness"] == "stale"
    assert "mission_assessment" in summary["blockers"]["stale"]
    database.dispose()


def test_publishing_api_returns_math_summary(client, runtime: RuntimeSettings) -> None:
    response = client.get("/api/publication/publishing", params={"project_id": "math"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["project_id"] == "math"
    assert data["chapter_count"] == 39
    assert data["lifecycle"] == "research"
    assert data["publication_gate"] == "Unknown"
    by_type = {item["evidence_type"]: item for item in data["evidence"]}
    assert by_type["manuscript_discovery"]["result"] == "passed"
    assert by_type["proof_claims"]["result"] == "unknown"
    assert by_type["human_approval"]["result"] == "pending"
    assert set(data["blockers"]) == {"failed", "stale", "missing", "identity_conflicts"}
    assert data["blockers"]["identity_conflicts"] == []
    assert data["identity"]["identity_state"] == "resolved"
    assert data["identity"]["writer_project_id"] == "math"
    assert data["source_fingerprint"]["ok"] is True
    assert data["source_fingerprint"]["scope_version"] == "manuscript-v1"
    assert data["source_fingerprint"]["file_count"] == 39
    assert data["observed_at"]


def test_stale_writer_run_detected_by_digest(
    runtime: RuntimeSettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mission_control.publication.fingerprint import writer_source_digest

    repo = tmp_path / "memory"
    book_dir = _chapters(repo / "content" / "books" / "memory", 1)
    chapter = book_dir / "01-chapter.md"
    out = repo / ".writer" / "validation" / "chapters"
    out.mkdir(parents=True, exist_ok=True)
    (out / "01.json").write_text(
        json.dumps({
            "machine_status": "PASS",
            "chapter_path": "content/books/memory/01-chapter.md",
            "source_digest": writer_source_digest(chapter.read_text(encoding="utf-8")),
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("MISSION_CONTROL_WRITER_REGISTRY", str(_registry(tmp_path, {"memory": repo})))
    monkeypatch.setenv("MISSION_CONTROL_BOOKBUILDER_ROOT", str(tmp_path / "empty-dist"))
    database = _seed_db(runtime)
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "memory")
    run = _by_type(summary, "writer_validation_run")
    assert run["result"] == "passed"
    assert run["freshness"] == "current"
    # Source edit after the stored run: same verdict, now stale.
    chapter.write_text("# changed after validation\n", encoding="utf-8")
    with database.session() as session:
        summary = get_publishing_summary(session, runtime, "memory")
    run = _by_type(summary, "writer_validation_run")
    assert run["result"] == "passed"
    assert run["freshness"] == "stale"
    assert "writer_validation_run" in summary["blockers"]["stale"]
    database.dispose()


def test_refresh_rereads_without_executing(
    client, runtime: RuntimeSettings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = client.get("/api/publication/publishing", params={"project_id": "math"}).json()
    after = client.get("/api/publication/publishing", params={"project_id": "math"}).json()
    assert before["chapter_count"] == after["chapter_count"] == 39
    assert before["observed_at"] and after["observed_at"]
    # No validator, builder or publisher runs: no .writer output, no dist changes.
    assert not Path(r"C:\books\math\.writer").exists()
    assert before["publication_gate"] == after["publication_gate"] == "Unknown"


def test_alias_api_requires_confirmation_and_lists_conflicts(
    client, runtime: RuntimeSettings, tmp_path
) -> None:
    repo_dir = tmp_path / "axiom-zero"
    repo_dir.mkdir(parents=True, exist_ok=True)
    created_book = client.post("/api/projects", json={
        "id": "axiom-zero", "name": "Axiom Zero", "kind": "book",
        "repository_path": str(repo_dir),
        "book_title": "Axiom Zero",
    })
    assert created_book.status_code == 201, created_book.text
    denied = client.post("/api/books/aliases", json={
        "canonical_project_id": "axiom-zero",
        "system": "writer",
        "external_id": "axiom_zero",
    })
    assert denied.status_code == 422
    created = client.post("/api/books/aliases", json={
        "canonical_project_id": "axiom-zero",
        "system": "writer",
        "external_id": "axiom_zero",
        "source_reference": "test mapping",
        "confirm": True,
    })
    assert created.status_code == 201, created.text
    identity = client.get("/api/books/book-axiom-zero/identity").json()
    assert identity["identity_state"] == "resolved"
    assert identity["writer_project_id"] == "axiom_zero"
    conflicts = client.get("/api/books/identity-conflicts").json()
    assert not any(c["project_id"] == "axiom-zero" for c in conflicts["candidates"])
    removed = client.request("DELETE", "/api/books/aliases", json={
        "system": "writer", "external_id": "axiom_zero",
    })
    assert removed.status_code == 200 and removed.json()["removed"] is True
    identity = client.get("/api/books/book-axiom-zero/identity").json()
    assert identity["identity_state"] == "candidate"
