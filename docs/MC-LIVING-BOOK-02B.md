# MC-LIVING-BOOK-02B — Narrow author-mode improvement journey

**Status:** Implemented and exercised on Distillation chapter 14; evaluation and experience integrity
qualified by [MC-LIVING-BOOK-02B-R1](MC-LIVING-BOOK-02B-R1.md).

**Design:** [MC-LIVING-BOOK-02A](MC-LIVING-BOOK-02A.md)

**Acceptance:** [mc-living-book-02b](acceptance/mc-living-book-02b/README.md) ·
[mc-living-book-02b-r1](acceptance/mc-living-book-02b-r1/README.md)

## What shipped

- A Mission gateway for one chapter improvement:
  - `GET /api/living-book/projects/{project_id}/improvement/preview`
  - `POST /api/living-book/projects/{project_id}/improvement`
  - `GET /api/living-book/projects/{project_id}/improvement/{run_id}`
  - `POST /api/living-book/projects/{project_id}/improvement/{run_id}/decision`
- A deterministic `living-book-improvement-intent.v1` envelope and a bounded editorial brief
  (at most 600 characters) built from the chapter’s current economy evidence.
- Exact source, approval, capture, chapter SHA-256, plan identity and budget in the preview.
- Author-mode UI in the reading room: evidence used, excluded `NOT_RUN` measures, plan/budget,
  read/model/action/write authority, earlier-decision preview, recent runs, proposal diff, evaluation
  label, source-at-review and accept/reject.
- Explicit source refresh when the workspace attachment is stale; fail-closed when the chapter or
  source changed.
- Reuse of ALIVE’s source custody, workspace, workflow, Pi/model, proposal, evaluation and decision
  machinery. No Mission model call, no new Mission table and no manuscript write path.

## ALIVE activation

The existing ALIVE AI-01A backend repair was applied from commit `0131dcfc` rather than reimplemented.
That repair made the informed family discoverable and executable (v6/801–806).

The first real run then exposed a token-budget defect: the six-section workflow had `model_calls=8`
but a fixed 100,000-token ceiling, so the full-proposal `evaluate` call was refused after the proposal
was saved. The fix derives the per-run token ceiling from the confirmed call plan:

```text
max_tokens = max(100000, model_calls * 30000)
```

Because the changed files are fingerprinted, the repair is a new immutable family:

| Family | State |
| --- | --- |
| v6 / 801–806 | Historical; retained for old runs |
| v7 / 901–906 | Current; chapter-14 plan v906, six sections, 8 calls, plan `642e4792…` |

## Authority and no-write boundary

| Authority | Implementation |
| --- | --- |
| Read | Existing approved source and exact capture; Mission never approves or widens a source |
| Model data use | Separate ALIVE workflow admission and budget confirmation |
| Action | Workspace Chapter Improvement; proposal only |
| Write | None. Decisions are append-only with `applied: false`; `accepted_with_edits` is hidden |

The preview is untrusted evidence in the UI. The workflow receives only the deterministic brief as
`criteria`; the full quality context stays in Mission. A model assessment is labelled
`model_assessment`, never “independent” or “verified quality improvement.”

## Real result

- Attempt 1 (`8d9f88ab-…`) stopped at section 5’s completeness guard with no proposal (6 calls,
  33,462 tokens). It is retained as a negative result.
- Run `c335aacf-cd5a-43a3-8914-d6dacd2dfc8a` retained proposal
  `ce2488e446fe4d1dbc43bb3c879bf64c7c06f63a35eef5e9fbc62ebeead1fe4f`.
- The proposal has a real diff (55 lines added, 286 removed) and complete section assembly.
- The evaluation failed with `authority_refused` at the old token ceiling. This is a negative result,
  not a quality verdict.
- The author accepted the proposal; decision event `203b21a5-ea2e-57d9-a877-a24a8ebda394`,
  `applied: false`.
- A later experience preview retrieves that decision as one eligible item (score 1.75, source text
  included while its pinned approval remains authorized).
- The chapter file SHA-256 is unchanged: `ad89a4e9…`.
- The source is pinned to capture `a632c716…` for reproducibility; switching back to live is an owner
  action.

## Verification

| Check | Result |
| --- | --- |
| Mission improvement + living-book tests | 11 passed |
| Mission full backend | 507 passed, 1 skipped; 4 unrelated environment failures |
| Frontend targeted LivingBookPage tests | 4 passed |
| Frontend full suite | 82 passed, 2 unrelated flakes; both flaky files pass together in isolation |
| Frontend production build | passed |
| ALIVE capability registry + living-book tests | 16 passed |
| Live plan after v7 activation | 200, v906, six sections, 8 calls, plan `642e…` |
| Live browser | Improve tab, evidence, v906, recent accepted run, proposal diff, evaluation and decision rendered; no console errors |

## Known gaps

- The token-ceiling repair was exercised by the v906 run (8 calls, 54,150 tokens, all 12 stages).
  The v8 quality gate is exercised by the live experience preview, not by a new model run with
  `use_experience=true`.
- No second `use_experience=true` run was launched in 02B; retrieval and delivery are previewed and
  receipted, but `experience_applied`, `quality_improved` and `transfer_demonstrated` remain
  **not established**.
- `accepted_with_edits` and every manuscript-write path remain out of scope.
- The source remains pinned; an owner can return it to live mode in ALIVE.
