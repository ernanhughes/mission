# W0-AI-PROJECT-PILOT — Bounded historical sample (no bulk evaluation)

Pilot repo: `C:\Projects\ai` (exists; README present, no AGENTS.md; `src/ai/*`,
`tests/`, `docs/`, `alembic 0001/0002`, `pytest_r*_*.log` from prior runs).
No bulk historical AI analysis in W0. Sample below is reconstruction feasibility only.

## 1. Why `ai`

Shared `ai.*` library (retrieval/memory/inference/scoring) is the proposed semantic
substrate for WORK-OUTCOME; piloting there tests both consumer and provider fit.
Postgres+pgvector via `AI_DSN`, deterministic-default tests, `integration` gate —
mirrors Mission's own evidence discipline.

## 2. Sample frame to collect in W1 (seven cases)

Seek one of each; if a case cannot be found, record the coverage gap — never fabricate:

1. Clearly completed task (code + test + merge/registration proof).
2. Incomplete task (mandatory requirement without `observed`).
3. Multi-commit task (≥2 SHAs, incl. possible squash/rebase — tests patch-id/trailer path).
4. Multi-session task (≥2 `session_v2` ids, `parent_id`/`job.child_session_id` links).
5. Success claimed without sufficient evidence (`reported` without `tested/verified`).
6. Legitimate non-code task (research/doc; completion without `integrated`).
7. Ambiguous/uncorrelatable (weak-only signals; must abstain → `unknown` + open obligation).

## 3. Reconstruction walkthrough (feasibility, not verdict)

For each candidate: quote objective (message locator) → list requirements (cheap-AI draft, human-checked in W1) →
attach sessions (`session_v2` ids + `directory/worktree`) → attach commits
(SHA-exists check + file-overlap + repo identity) → attach tests/reviews
(artifact digest + `git_reviews` reuse) → score requirement states (rubric §1) →
emit obligations for gaps → record `stale` where source moved.

The brief's Worker (`WORKER-USAGE-02-I1`: evidence contract/ledger/relay/tests/merge claim
vs real-relay-unproven/recoverable-errors-unreviewed/paths-uncovered) and Harness Repo-Scout
(manifest≠correctness, inventory≠passing, correction≠elimination, open gate blocks complete)
are the worked patterns to replicate — with `ai`-project evidence, not imported verdicts.

## 4. W1 pilot entry criteria

OpenCode HWM poller + git index join working read-only; `ai` repo in `DiscoveryRoot(git_enabled)`;
redaction + budgets + `mode=ro` + `locked`-retry proven; seven-case census recorded
(found/missing with locators). Then — and only then — run the deterministic reconstruction;
AI steps stay cached by digest from the start.
