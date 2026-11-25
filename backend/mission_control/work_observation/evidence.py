"""Evidence classification for WORK-OUTCOME-01 W1.

Four classes (reconciled with W0-WORK-EPISODE-CONTRACT §3):

- OBSERVED: a row exists in a source system (OpenCode message, git commit,
  review record). Proven by locator + digest.
- CLAIMED: participant text asserting a result ("382 passed", "merged").
  Stored with locator; never proof.
- INFERRED: a candidate signal with confidence below explicit (timestamp
  proximity, semantic similarity, unconfirmed SHA mention).
- VERIFIED: an independent check re-executed against a pinned source revision
  with its own digest and evaluator identity. W1 never produces VERIFIED;
  the label exists so later stages cannot conflate claims with proof.
"""

from __future__ import annotations

import hashlib

from mission_control.activity_git.service import redact_secrets

OBSERVED = "observed"
CLAIMED = "claimed"
INFERRED = "inferred"
VERIFIED = "verified"

EVIDENCE_CLASSES = (OBSERVED, CLAIMED, INFERRED, VERIFIED)

EXCERPT_MAX_CHARS = 800


def digest_text(value: str) -> str:
    """Stable sha256 hex digest for cache keys and provenance."""
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def excerpt_redacted(text: str, limit: int = EXCERPT_MAX_CHARS) -> tuple[str, int]:
    """Redact secrets then truncate. Returns (excerpt, redaction_count).

    Never returns more than ``limit`` chars; appends a truncation marker so
    readers cannot mistake a clipped excerpt for a complete record.
    """
    if not text:
        return "", 0
    redacted, redactions = redact_secrets(text)
    count = len(redactions) if isinstance(redactions, list) else int(redactions or 0)
    if len(redacted) > limit:
        return redacted[:limit] + "…[truncated]", count
    return redacted, count


def classify_record(kind: str) -> str:
    """Map a normalized record kind to its evidence class.

    Rows that exist are OBSERVED. Free-text assertions extracted from those
    rows are CLAIMED. Anything scored by the signal extractor below explicit
    confidence is INFERRED. VERIFIED requires an independent re-execution
    (W4+) and is never assigned here.
    """
    if kind in {"session", "message", "message_part", "tool_call", "git_commit",
                "git_review", "file_state", "workbench_record"}:
        return OBSERVED
    if kind in {"claim", "test_claim", "completion_claim", "merge_claim"}:
        return CLAIMED
    if kind in {"signal", "candidate_association"}:
        return INFERRED
    if kind in {"verification", "reproduction", "acceptance"}:
        return VERIFIED
    return INFERRED
