# LIVING-WORK-BLOG-01 — D2 Integration Report (revalidation + verification)

**Status:** D2 scoped integration verified in place. No D3/D4. No commits, pushes,
deployments, production calls, or publication by this review. No manuscript edits.

**Reading guide:** the integration record itself lives in
`C:\Projects\alive\docs\LIVING-WORK-BLOG-01-D2-INTEGRATION-REPORT.md`
(commits `1484ea9` + `811230d4`, file SHAs, focused-suite evidence, push-state
disclosure). This report does **not** duplicate it. It records what this
revalidation pass independently re-checked, the broader regression run the
qualification left open, and the resulting verdict.

## 1. Revalidation (Step 1 — before touching anything)

- Mission HEAD `1484ea9` ("BLOG-01 D2: site post context builder and history
  (qualified GO)"), on top of `df08852` (== `origin/main`; local main is
  ahead by exactly that commit, unpushed). ALIVE HEAD `811230d4` (same
  message, ALIVE side), on top of `3eaee897` (== qualified base).
- `ab7dc15`: `git cat-file -t` → fatal; absent from `ls-remote --heads origin`.
  **Discrepancy preserved, not resolved.** `4a97a6a` carries the same commit
  message (`feat: add isolated Writer Work workflow`); its content
  (`schemas.py`, `workflows/service.py`, `workflows/templates.py`,
  `test_workflow_service.py`; +189/−23) has no websites/posts/quality changes.
  Recorded as message-level match only — no substitution of `4a97a6a` as the
  intended base. D2 was built and integrated against `df08852`, never `ab7dc15`.
- Qualified sources still available and intact: `blog01-d2/mission-d2`
  (2 untracked files, zero tracked modifications) and `blog01-d2/alive-d2`
  (2 modified files), plus `verify_d2.py`, `probe_alive_qual.py`,
  stage logs, and the `LIVING-WORK-BLOG-01-D2-INTEGRATION-REVIEW.md` gate.
- No conflicting modifications: Mission `git diff` shows only the
  book-production pipeline workstream (unrelated files, untouched by D2);
  ALIVE `git diff HEAD` is empty (only the pre-existing untracked integration
  report, read — never edited — by this pass).
- Unrelated work protected: no pipeline, inspect, worker, praxis, or
  cultivation file was staged, edited, or committed here. `uv.lock` and
  `.writer/writer.db` runtime noise left alone. No `git commit` or `git push`
  executed in either repo.

## 2. Integrated files — verified identical to the qualified state (Step 2)

No new integration was needed: both commits were already in place, so this
pass verified byte-identity instead of re-applying changes.

| File | Commit | SHA-256 (committed bytes) | Qualified source | Match |
|---|---|---|---|---|
| Mission `websites/context.py` | `1484ea9` | `6A23…ACCE72` | `mission-d2` worktree | byte-identical |
| Mission `tests/test_mc_website_posts_context.py` | `1484ea9` | `520E46…BD85D9` | `mission-d2` worktree | byte-identical |
| ALIVE `living_book/quality_history.py` | `811230d4` | `E79F32…9C51A9` | `alive-d2` worktree | identical after CRLF→LF normalization |
| ALIVE `living_book/service.py` | `811230d4` | `52BBE3…A9421` | `alive-d2` worktree | identical after CRLF→LF normalization |

- The ALIVE SHAs differ textually from the qualification report §2 because the
  report hashed worktree files (CRLF line endings); the git blobs store LF.
  `sha256(worktree_bytes.replace(CRLF, LF))` equals the committed blob SHA for
  both files — equivalence modulo line endings, verified programmatically.
- `git show --stat` on both commits lists exactly the 2 files each
  (Mission: +1280/−0; ALIVE: +123/−31). No `quality.py` change, no new
  scorer, no new table, no book-guidance or timeline behaviour change, no
  migration, no API route change.

## 3. Verification (Step 3 — focused + broader regression)

All runs use disposable DBs/sites and fake or no evaluators. No live models,
no prod writes, no real-site contact.

**Mission** (`backend/`, repo venv):
- `test_mc_website_posts_context.py` — **14 passed** (D2 focused).
- `test_mc_website_posts.py` — **15 passed** (D2 focused).
- `test_living_book.py` + `test_living_book_improvement.py` +
  `test_living_book_represent.py` — **25 passed** (book-side, D2-adjacent).
- Broader websites sweep added `test_mc_websites_cultivation.py`:
  **2 failed, 71 passed overall.** Both failures are weekly-window blog
  cultivation tests (`this_week` award counting, draft-flip weekly progress),
  date-sensitive and outside D2 scope: the cultivation code imports nothing
  from `websites/context.py` (verified by grep), and both tests fail
  identically on the pristine `df08852` qualification worktree (no D2
  integration, no pipeline changes). **Pre-existing, D2-unrelated — recorded,
  not fixed here.**
- `ruff check` + `ruff format --check` on both new files: clean.

**ALIVE** (repo venv, `PYTHONDONTWRITEBYTECODE=1`):
- `verify_d2.py` (64 checks) rerun **against live main** (path-adjusted copy
  in temp; repo untouched): **64/64 pass**, including dual-hash separation,
  identity/rename isolation, replay dedup, force-link, unknown-ID
  non-authority, mixed states, `absent_now` never a fix, hostile/truncated
  safety.
- `probe_alive_qual.py` (32 authority probes) against live main:
  **32/32 pass**.
- `test_living_book_quality_history.py` (8) + `test_living_book.py` (7) +
  `test_living_book_semantics.py` (broader): **29 passed** with slow tests
  included (`-o addopts=""`; bare default deselects them by repo policy).
- `ruff format --check`: clean on both files. `ruff check`: one F841
  (`service.py:1276`, unused `registration` in `_representations`) —
  confirmed outside all D2 hunks (hunks span ~785–901) and present at base;
  left as-is per the no-unrelated-changes rule.

**Not run:** full Mission backend suite, full ALIVE suite, live-model
evaluation, real-site contact (same boundary as qualification, by brief).

## 4. Authority, freshness, and unknown handling (reconfirmed live)

- Unknown post IDs (`….evil`, `mission.other` even with `current=True`
  evals) render an empty block: no EVAL/FINDING lines, never CURRENT, no
  code citations (raw-JSON echo only, by design).
- Front-matter-only changes → editorial STALE with Writer CURRENT +
  `LOCATION_DRIFT_NOTE`; body changes → Writer STALE; renames → new identity
  NOT_RUN, old identity NotFound, cross-post links rejected.
- `absent_now` is never repaired or improved by the integration; missing /
  mismatched / unavailable inputs stay non-current; hostile and truncated
  inputs fail safe.
- Mission owns editorial/identity/storage; Writer deterministic observations
  only (`artifact`/`qc`, `scoring` rejected); ALIVE owns presentation.
  Human `human_review.pending` default kept.

## 5. Outstanding limitations

1. Full regression suites (both repos) remain unrun — narrowed but not
   closed by this pass (related subsets now green except 2 pre-existing
   date-sensitive cultivation failures, proven unrelated).
2. `ab7dc15` remains unresolvable; `4a97a6a` equivalence is message-only.
3. The ALIVE push recorded in the prior report already moved `origin/main`
   there; Mission `1484ea9` stays local. Nothing was pushed by this pass.
4. D3 (Writer post path) / D4 (collection view) / D5: not started, as briefed.

## Verdict: READY_FOR_D3_D4_REVIEW

The integrated state matches the qualified state (byte-identical modulo
ALIVE line endings), preserves all existing behavior per focused plus
broader related suites, fails safe, and leaves unrelated workstreams
untouched. The two broader-suite failures are proven pre-existing and
out of scope. D3/D4 remain held pending acceptance of this report.
