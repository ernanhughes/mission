from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from mission_control.discovery.scanner import scan_roots
from mission_control.persistence.seed import DEFAULT_EXCLUSIONS


def build_discovery_fixture(root: Path) -> None:
    alpha = root / "alpha-app"
    alpha.mkdir()
    (alpha / "README.md").write_text("# Alpha\n\nA local application.", encoding="utf-8")
    (alpha / "pyproject.toml").write_text(
        "[project]\nname='alpha'\n[project.scripts]\nalpha = 'alpha:main'\n",
        encoding="utf-8",
    )
    book = root / "book-one"
    (book / "content" / "books" / "book-one").mkdir(parents=True)
    (book / "README.md").write_text(
        "# A Book\n\nThis manuscript has chapters.", encoding="utf-8"
    )
    (book / "content" / "books" / "book-one" / "01-chapter.md").write_text(
        "# One", encoding="utf-8"
    )
    library = root / "beta-lib"
    library.mkdir()
    (library / "README.md").write_text("# Beta\n\nA small library.", encoding="utf-8")
    (library / "package.json").write_text('{"name": "beta-lib"}', encoding="utf-8")
    generated = root / "generated-demo"
    generated.mkdir()
    (generated / "README.md").write_text("# Demo", encoding="utf-8")
    excluded = root / "node_modules"
    (excluded / "package").mkdir(parents=True)
    (excluded / "package" / "package.json").write_text('{"name": "noise"}', encoding="utf-8")
    review_pack = root / "project-review-pack"
    review_pack.mkdir()
    (review_pack / "README.md").write_text("# Review pack", encoding="utf-8")
    (root / "empty-dir").mkdir()


def test_scanner_classifies_and_excludes(tmp_path: Path) -> None:
    root = tmp_path / "roots"
    root.mkdir()
    build_discovery_fixture(root)
    result = scan_roots(
        [str(root), str(root)],
        exclusion_patterns=DEFAULT_EXCLUSIONS,
        max_depth=1,
        max_candidates=50,
        timeout_seconds=30,
    )
    by_name = {candidate.name: candidate for candidate in result.candidates}
    assert "alpha-app" in by_name
    assert by_name["alpha-app"].classification == "executable_application"
    assert any("Declared commands" in item for item in by_name["alpha-app"].evidence)
    assert by_name["book-one"].classification == "book"
    assert by_name["beta-lib"].classification == "library"
    assert by_name["generated-demo"].classification == "generated_artifact"
    assert "node_modules" not in by_name
    assert "project-review-pack" not in by_name
    assert "empty-dir" not in by_name
    assert result.cancelled is False
    assert len(by_name) == len(result.candidates)  # duplicate root did not duplicate records


def test_scanner_is_bounded_and_cancellable(tmp_path: Path) -> None:
    root = tmp_path / "roots"
    root.mkdir()
    build_discovery_fixture(root)
    bounded = scan_roots(
        [str(root)],
        exclusion_patterns=DEFAULT_EXCLUSIONS,
        max_depth=1,
        max_candidates=2,
        timeout_seconds=30,
    )
    assert bounded.truncated is True
    assert len(bounded.candidates) == 2

    cancel = threading.Event()
    cancel.set()
    cancelled = scan_roots(
        [str(root)],
        exclusion_patterns=DEFAULT_EXCLUSIONS,
        max_depth=1,
        max_candidates=50,
        timeout_seconds=30,
        cancel_event=cancel,
    )
    assert cancelled.cancelled is True


def test_api_discovery_persists_candidates_without_registering_applications(
    client: TestClient, tmp_path: Path
) -> None:
    root = tmp_path / "roots"
    root.mkdir()
    build_discovery_fixture(root)

    for existing in client.get("/api/discovery/roots").json():
        client.delete(f"/api/discovery/roots?path={existing['path']}")
    added = client.post("/api/discovery/roots", json={"path": str(root), "enabled": True})
    assert added.status_code == 201, added.text

    started = client.post("/api/discovery/scan")
    assert started.status_code == 202, started.text
    deadline = time.time() + 20
    status = started.json()
    while time.time() < deadline:
        status = client.get("/api/discovery/scan").json()
        if not status["running"]:
            break
        time.sleep(0.15)
    assert status["status"] == "complete", status
    assert status["candidate_count"] >= 3
    assert status["counts"]["executable_application"] >= 1

    candidates = client.get("/api/discovery/candidates?limit=100").json()
    names = {candidate["name"] for candidate in candidates}
    assert {"alpha-app", "book-one", "generated-demo"} <= names
    assert "node_modules" not in names
    alpha = next(candidate for candidate in candidates if candidate["name"] == "alpha-app")
    assert alpha["classification"] == "executable_application"
    assert alpha["confidence"] > 0
    assert alpha["evidence"]

    # Discovery is advisory: it must not auto-register an application or a launch.
    assert client.get("/api/applications/alpha-app").status_code == 404
    applications = client.get("/api/applications").json()
    assert "alpha-app" not in {app["id"] for app in applications}
