"""Live local-AI review demo: temp DB, fixture repo, Ollama loopback endpoint."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

os.environ["MISSION_CONTROL_MONITOR"] = "0"

from mission_control.activity_git.service import GitActivityService
from mission_control.config import RuntimeSettings
from mission_control.models import DiscoveryRoot, Setting
from mission_control.persistence.db import Database, now_iso
from mission_control.persistence.migrations import apply_migrations


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30, shell=False, check=False,
    )
    assert result.returncode == 0, result.stderr[:300]
    return (result.stdout or "").strip()


tmp = Path(tempfile.mkdtemp())
root = tmp / "projects"
root.mkdir(parents=True, exist_ok=True)
repo = root / "demo"
repo.mkdir(parents=True, exist_ok=True)
_git(repo, "init")
_git(repo, "config", "user.name", "T")
_git(repo, "config", "user.email", "t@e.com")
_git(repo, "config", "commit.gpgsign", "false")
(repo / "calc.py").write_text("def add(a, b):\n    return a + b\n")
(repo / "AGENTS.md").write_text("# Agents\n- Run pytest before finishing.\n- Keep diffs scoped.\n")
(repo / "DESCRIPTION.md").write_text("# Demo\nA tiny calculator library.\n")
_git(repo, "add", "-A")
_git(repo, "commit", "-m", "feat: add calculator", "--no-gpg-sign")
# A change with a genuine defect for the reviewer to find.
(repo / "calc.py").write_text("def add(a, b):\n    return a + b\n\ndef div(a, b):\n    return a / b\n")
_git(repo, "add", "-A")
_git(repo, "commit", "-m", "feat: add division without zero guard", "--no-gpg-sign")

rt = RuntimeSettings(
    repo_root=Path(".").resolve(),
    data_dir=tmp / "data",
    config_dir=Path("config").resolve(),
    frontend_dist=tmp / "dist",
    book_root=tmp / "books",
    start_monitor=False,
    seed_defaults=False,
)
db = Database(rt)
apply_migrations(db)
with db.session() as session:
    session.add(DiscoveryRoot(path=str(root), enabled=True, added_at=now_iso(),
                              display_name="F", category="software", git_enabled=True))
    session.add(Setting(key="ai", value={
        "enabled": True, "consent": True, "provider": "openai-compatible",
        "base_url": "http://127.0.0.1:11434/v1", "model": "mistral-small:latest",
        "api_key_env": "", "timeout_seconds": 180,
    }, updated_at=now_iso()))

svc = GitActivityService(db)


async def main() -> None:
    await svc.start()
    for _ in range(60):
        await asyncio.sleep(2)
        if not svc.status["running"]:
            break
    print("scan:", svc.status["status"], "errors:", svc.status.get("errors"))
    with db.session() as session:
        items, total, partial = svc.timeline(session, preset="30d", limit=10)
        print("indexed:", total, "partial:", partial)
        target = next(item for item in items if "division" in item["subject"])
        print("target:", target["short_sha"], target["subject"])
        package = svc.build_prompt(session, target["repo_id"], target["sha"], profile="code")
        print("prompt chars:", package["size_chars"], "truncated:", package["truncated"],
              "redactions:", package["redaction_count"])
        review = svc.request_review(session, repo_id=target["repo_id"], sha=target["sha"],
                                    model="mistral-small:latest", profile="code")
        review_id = review.id
        print("review queued:", review_id)
    await svc.execute_review(review_id)
    with db.session() as session:
        from mission_control.models import GitReview
        stored = session.get(GitReview, review_id)
        assert stored is not None
        print("status:", stored.status)
        print("verdict:", stored.verdict)
        print("error:", (stored.error or "")[:500])
        print("observed_model:", stored.observed_model, "route:", stored.model_route)
        print("--- summary (first 1500 chars) ---")
        print((stored.summary or "")[:1500])
        print("--- findings:", len(stored.findings or []), "---")
    # Prove durability across a full process-style restart: dispose the engine
    # and re-open the same data directory with brand-new objects.
    db.dispose()
    fresh_db = Database(rt)
    with fresh_db.session() as session:
        from mission_control.models import GitReview as FreshReview
        reopened = session.get(FreshReview, review_id)
        assert reopened is not None and reopened.status == "completed", "review did not survive restart"
        print("restart-persistence: OK (status=%s verdict=%s findings=%d)" % (
            reopened.status, reopened.verdict, len(reopened.findings or [])))

asyncio.run(main())
