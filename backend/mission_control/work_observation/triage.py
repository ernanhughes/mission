"""WORK-OUTCOME-01 W3: deterministic semantic triage (no model calls).

Implements W3-SEMANTIC-TRIAGE deterministic rules over assembled session
summaries. Anything genuinely ambiguous returns NEEDS_SEMANTIC (bounded model
queue) or INSUFFICIENT_EVIDENCE/AMBIGUOUS — never an invented objective.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TRIVIAL_INTERACTION = "TRIVIAL_INTERACTION"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
AMBIGUOUS = "AMBIGUOUS"
NEEDS_SEMANTIC = "NEEDS_SEMANTIC"
RESEARCH_OR_INVESTIGATION = "RESEARCH_OR_INVESTIGATION"
REVIEW_OR_CORRECTION = "REVIEW_OR_CORRECTION"
SUBSTANTIVE_CANDIDATE = "SUBSTANTIVE_CANDIDATE"

_PROBE_RES = [
    re.compile(r"return the single word ready", re.I),
    re.compile(r"^request:\s*$", re.I | re.M),
    re.compile(r"reply as instructed", re.I),
    re.compile(r"opencode-prompt-[\w-]+\.md", re.I),
]

_RESEARCH_RES = [
    re.compile(r"docs/research/", re.I),
    re.compile(r"mIGRATION-plan|research.*\.md$", re.I),
]


@dataclass
class SessionSummary:
    session_id: str
    message_count: int
    has_task: bool = False
    has_sha: bool = False
    has_files: bool = False
    has_claims: bool = False
    has_tools: bool = False
    has_chain: bool = False
    user_first: str = ""
    code_files: list[str] = field(default_factory=list)
    research_files: list[str] = field(default_factory=list)
    review_tools: bool = False
    in_episode: bool = False


@dataclass
class TriageVerdict:
    session_id: str
    classification: str
    method: str  # deterministic | model
    reason: str
    queued_for_model: bool = False


def _looks_probe(text: str) -> bool:
    return any(rx.search(text or "") for rx in _PROBE_RES)


def triage(summary: SessionSummary) -> TriageVerdict:
    """Deterministic triage. Pure function, tested exhaustively."""
    sid = summary.session_id
    if summary.in_episode or summary.has_chain or summary.has_task:
        return TriageVerdict(sid, SUBSTANTIVE_CANDIDATE, "deterministic",
                             "w2-corroborated")
    if summary.review_tools:
        return TriageVerdict(sid, REVIEW_OR_CORRECTION, "deterministic",
                             "review-tool-invocation")
    if summary.has_claims and not (summary.has_sha or summary.has_files):
        return TriageVerdict(sid, AMBIGUOUS, "deterministic",
                             "claim-without-anchor", queued_for_model=True)
    if summary.research_files and not summary.code_files and not summary.has_tools:
        return TriageVerdict(sid, RESEARCH_OR_INVESTIGATION, "deterministic",
                             "research-paths-only")
    if (summary.message_count <= 6 and not summary.has_tools
            and not summary.has_claims and _looks_probe(summary.user_first)):
        return TriageVerdict(sid, TRIVIAL_INTERACTION, "deterministic",
                             "probe-pattern")
    if not (summary.has_sha or summary.has_files or summary.has_tools
            or summary.has_claims):
        return TriageVerdict(sid, INSUFFICIENT_EVIDENCE, "deterministic",
                             "no-corroborating-signal")
    return TriageVerdict(sid, NEEDS_SEMANTIC, "deterministic",
                         "signals-without-episode-home", queued_for_model=True)
