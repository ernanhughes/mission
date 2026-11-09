"""Restart-persistence proof: open an earlier demo DB with fresh objects."""

import tempfile
from pathlib import Path

from mission_control.config import RuntimeSettings
from mission_control.models import GitCommit, GitReview
from mission_control.persistence.db import Database

# tmpql43cx80 holds the completed live review rev-21a936c00f1f4383.
data_dir = Path(tempfile.gettempdir()) / "tmpql43cx80" / "data"
rt = RuntimeSettings(
    repo_root=Path(".").resolve(),
    data_dir=data_dir,
    config_dir=Path("config").resolve(),
    frontend_dist=Path("nonexistent"),
    book_root=Path("nonexistent"),
    start_monitor=False,
    seed_defaults=False,
)
db = Database(rt)
with db.session() as session:
    review = session.get(GitReview, "rev-21a936c00f1f4383")
    assert review is not None, "completed review missing after restart"
    assert review.status == "completed", review.status
    print("review:", review.id, review.status, review.verdict, review.observed_model, review.model_route)
    print("prompt_hash:", review.prompt_hash, "diff_hash:", review.diff_hash)
    print("context_fingerprint:", review.context_fingerprint)
    print("findings:", len(review.findings or []), "evidence_coverage:", review.evidence_coverage)
    commit = session.get(GitCommit, (review.repo_id, review.commit_sha or ""))
    assert commit is not None, "reviewed commit missing after restart"
    print("commit:", commit.short_sha, commit.subject)
print("restart-persistence: OK")
