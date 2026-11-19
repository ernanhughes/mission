# MC-LIVING-BOOK-02B — Narrow improvement journey acceptance

**Date:** 2026-11-19

**Scope:** Distillation chapter 14, economy focus, one retained proposal and one author decision.
No manuscript write, no automatic learning, no quality-improvement claim.

**Design:** [MC-LIVING-BOOK-02A](../../MC-LIVING-BOOK-02A.md)

---

## 1. Live sequence

| Step | Result |
| --- | --- |
| Source binding | `bdaefced-4d88-4b62-ad20-ffe044c73d89` |
| Source mode | `pinned` for the run |
| Pinned capture | `a632c716-f82b-42a0-85eb-e275caea0e96` |
| Pinned approval | `3996f4b2-7a40-411f-8ad3-8bab777313b0` |
| Pinned source | 1,262 files, 14,504,783 bytes |
| Chapter | `content/books/distillation/14-chapter.md` |
| Chapter SHA-256 | `ad89a4e96412b58818579c79b6c06dd6eac6082b3f6e549c4a337fb7d5acaa05` |
| File SHA-256 after runs | same |
| Workflow at first real run | v806, six sections, 8 calls, 12,288 output tokens, 900 s |
| Workflow after token repair | v7/901–906; chapter-14 plan v906, same plan SHA `642e479274374abd157c1eaf8b5a974f9a39caef584f0d65b2fa01c0f979f42b` |

The source was pinned because the live folder changed twice during the audit (1,260 → 1,261 → 1,262
files). The chapter itself did not change. Pinning preserved one exact edition for the run.

## 2. Attempt 1 — completeness guard

| Item | Observed |
| --- | --- |
| Run | `8d9f88ab-1ab0-4822-a18c-03d71509c1c0` |
| Status | `UNKNOWN`, terminal |
| Reason | `Improve section 5: Section length suggests omission or duplicated content; no complete proposal was assembled.` |
| Calls / tokens | 6 / 33,462 |
| Completed | review, sections 1–4 |
| Failed | section 5 |
| Proposal | none (`provenance: no_proposal`) |

This is a **negative result**, not a quality verdict. The section guard rejected a shortened output before
any proposal was saved. The failure is retained in ALIVE.

## 3. Attempt 2 — retained proposal

| Item | Observed |
| --- | --- |
| Run | `c335aacf-cd5a-43a3-8914-d6dacd2dfc8a` |
| Workflow | `chapter-improvement` v806, definition `d0478712-c0f4-4824-9f5b-574bec5c6692` |
| Status | `FAILED`, terminal |
| Reason | `Evaluate original and saved proposal: authority_refused` |
| Calls / tokens | 8 / 103,723 |
| Proposal artifact | `390ba0bd-0662-4788-b24c-284721cf4dd6` |
| Proposal SHA-256 | `ce2488e446fe4d1dbc43bb3c879bf64c7c06f63a35eef5e9fbc62ebeead1fe4f` |
| Diff | 55 lines added, 286 removed |
| Evaluation | `evaluation_failed`, `authority_refused` |
| Source at review | `current`, chapter `ad89a4e9…` |

The workflow retained a complete proposal after all six sections passed assembly. The `evaluate` call
was then refused at the workflow’s old 100,000-token ceiling. Inspecting the Pi receipt showed
`workflow_authority_revoked` and `pi_unexpected_requests`; this was a token-budget refusal, not a model
verdict or a manuscript write.

### Follow-up repair

The existing ALIVE AI-01A backend repair was applied from commit `0131dcfc` (not reimplemented). The
section plan’s `model_calls=8` was correct, but `max_tokens` was fixed at 100,000 while the
six-section review plus full-proposal evaluation needed more. The launch now derives a per-run token
ceiling from the confirmed call plan (`max(100000, calls × 30000)`) in both the informed and section
launch paths. Because those files are fingerprinted, the repair is a new immutable family:
**v7/901–906**. The old v6/801–806 family is historical and remains readable. The repair was activated
after the accepted run; it has **not** been exercised by a third real-model run.

## 4. Author decision

| Item | Observed |
| --- | --- |
| Decision event | `203b21a5-ea2e-57d9-a877-a24a8ebda394` |
| Decision | `accepted` |
| Comment | `economy: retained the proposal; evaluation stopped at the old token ceiling, not a quality verdict` |
| Decided at | `2026-11-19T21:43:20.891909Z` |
| Source version at decision | `current`, `ad89a4e9…` |
| Applied | `false` |
| Chapter file changed | no; SHA-256 still `ad89a4e9…` |

The decision is append-only and records the author’s judgement of this exact proposal. It does not
claim the proposal improved the chapter.

## 5. Experience retrieval

The accepted decision is retrievable for a later run:

```text
GET /api/v1/workspaces/9a992443-…/experience
  ?chapter_path=content/books/distillation/14-chapter.md
  &criteria=<the 534-character brief>

200
eligible_candidates: 1
selected:
  improvement:390ba0bd-0662-4788-b24c-284721cf4dd6
  decision: accepted
  score: 1.75
  reasons: criteria overlap 1.0, same chapter path, owner comment recorded
  source_text_included: true
  source_text_approvals: [3996f4b2-7a40-411f-8ad3-8bab777313b0]
context_sha256: f2bf011ea3cc8d1b99ecc587ef426942c9528641c177927858e747daaaabe8d7
```

This establishes **retrieval succeeded** and that the source text was authorized at preview time. It
does not establish `experience_applied`, `quality_improved` or `transfer_demonstrated`. No second run
was launched in 02B.

## 6. UI acceptance

Browser verification at `http://127.0.0.1:8790/projects/distillation/read`:

- the chapter opens at chapter 14 with the source and `ad89a4e9…`;
- the **Improve** tab shows “Improve this chapter”, the economy evidence (overall 3.00, economy 2.00,
  quote, `evidence_validated=false`), the 534-character brief, v906, six sections, eight calls,
  12,288 output tokens, 15 minutes, authority read/model/action/write, and `source pinned`;
- the prior accepted decision appears under “Earlier decisions” and “Recent runs”;
- opening that run shows the retained proposal, the actual diff, `evaluation_failed`, the current
  source, the accepted decision and the notice that no manuscript file changed;
- console errors: none.

No screenshot is attached because the browser screenshot tool required a visible desktop window.

## 7. Tests and build

| Check | Result |
| --- | --- |
| Mission `backend/tests/test_living_book_improvement.py` + `test_living_book.py` | 11 passed |
| Mission full backend | 507 passed, 1 skipped; 4 unrelated environment failures (cultivation git dates, configured editor, quality campaign evaluator, scripts weekly boundary) |
| ALIVE `tests/test_capability_registry.py` + `test_living_book.py` | 16 passed |
| Frontend targeted `LivingBookPage.test.tsx` | 4 passed |
| Frontend full suite | 82 passed, 2 unrelated flakes (CultivationPage, WorkbenchSidebarAction); both files pass together in isolation (19 passed) |
| Frontend production build | passed |
| Live plan after v7 activation | 200, v906, six sections, 8 calls, plan `642e…` |

The full-suite failures are not in the Living Book or improvement path. The four backend failures match the
pre-existing environment-dependent areas recorded in the 01 audit; they are reported, not hidden.

## 8. Non-claims

- The evaluation did not complete. No quality improvement is claimed.
- The proposal was accepted by the author; it was not independently verified as better.
- The first run’s section-5 guard failure is retained as a negative result.
- The token-ceiling repair was later exercised by the v906 evaluation run; see
  [the R1 acceptance](../mc-living-book-02b-r1/README.md). The v8 experience-quality gate is not yet
  exercised by a new model run with `use_experience=true`.
- The source is pinned to one exact capture for reproducibility; switching back to live is an owner
  action, not a hidden effect.
- No manuscript file was written, applied or overwritten.
