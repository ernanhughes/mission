import asyncio
import os
import tempfile
from pathlib import Path

os.environ["MISSION_CONTROL_MONITOR"] = "0"

from mission_control.activity_git.service import GitActivityService
from mission_control.config import RuntimeSettings
from mission_control.models import DiscoveryRoot
from mission_control.persistence.db import Database, now_iso
from mission_control.persistence.migrations import apply_migrations

tmp = Path(tempfile.mkdtemp())
rt = RuntimeSettings(
    repo_root=Path(".").resolve(),
    data_dir=tmp / "data",
    config_dir=Path("config").resolve(),
    frontend_dist=tmp / "dist",
    book_root=Path(r"C:\books"),
)
db = Database(rt)
apply_migrations(db)
with db.session() as session:
    for path, category in [(r"C:\Projects", "software"), (r"C:\books", "books")]:
        if Path(path).exists() and session.get(DiscoveryRoot, path) is None:
            session.add(
                DiscoveryRoot(
                    path=path,
                    enabled=True,
                    added_at=now_iso(),
                    display_name=Path(path).name,
                    category=category,
                    git_enabled=True,
                )
            )

svc = GitActivityService(db)


async def main() -> None:
    await svc.start()
    for _ in range(100):
        await asyncio.sleep(6)
        st = svc.status
        print(
            "running=%s discovered=%s indexed=%s new=%s backfill=%s total_commits=%s"
            % (
                st["running"],
                st.get("repos_discovered"),
                st.get("repos_indexed"),
                st.get("commits_new"),
                st.get("backfill_pending"),
                st.get("total_commits"),
            ),
            flush=True,
        )
        if not st["running"]:
            break
    keys = ("status", "repos_discovered", "repos_indexed", "commits_new",
            "backfill_pending", "total_repos", "total_commits", "elapsed_seconds")
    print("FINAL:", {key: svc.status.get(key) for key in keys})
    print("ERRORS:", (svc.status.get("errors") or [])[:5])

    with db.session() as session:
        items, total, partial = svc.timeline(session, preset="today", limit=15)
        print("TODAY total=%s partial=%s" % (total, partial))
        for item in items[:15]:
            print(
                "%s %-18s %s %s (%s files +%s/-%s) reviews=%s"
                % (
                    item["short_sha"],
                    item["repo_name"][:18],
                    item["subject"][:80],
                    item["branches"][0] if item["branches"] else "-",
                    item["files_changed"],
                    item["insertions"],
                    item["deletions"],
                    item["review_count"],
                )
            )
        print("SUMMARY:", svc.summary(session))


asyncio.run(main())
