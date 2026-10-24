from __future__ import annotations

from pathlib import Path

import pytest

from mission_control.workflows.sandbox import DockerSandboxRunner, SandboxUnavailable


def test_docker_sandbox_runs_with_read_only_mount_and_limits(tmp_path: Path) -> None:
    runner = DockerSandboxRunner()
    try:
        runner.availability()
    except SandboxUnavailable as exc:
        pytest.skip(str(exc))
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )
    before = sorted(path.relative_to(repo) for path in repo.rglob("*"))
    result = runner.run(
        repo, ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"], timeout_seconds=60
    )
    assert result.exit_code == 0, result.stderr
    assert result.timed_out is False
    assert result.limits["network"] == "none"
    assert result.limits["repository_mount"] == "read-only"
    assert result.limits["root_filesystem"] == "read-only"
    after = sorted(path.relative_to(repo) for path in repo.rglob("*"))
    assert after == before
