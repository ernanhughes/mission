# MC-LIVING-BOOK-02D acceptance record

Status: **Phase A qualified; Phase B frozen; Phase C outcome `inconclusive`; Phase D live
comparison verified.** This is a research pilot. It does not establish learning or transfer.

## What was built

### Read-only independent evaluation (ALIVE)

| Item | Identity |
| --- | --- |
| Workflow | `chapter-evaluation` v1 |
| Definition SHA-256 | `13cc2b251d34564f819f4412eac44c3c14961bf8461e381ccfe707eaee812ce7` |
| Capability | `chapter.independent_evaluate` v1.0.0 |
| Rubric | `chapter-evaluation-v1` (six dimensions, 0–4) |
| Mechanical preservation | seven deterministic presence checks |
| ALIVE commit | `435fc649` (evaluation path), `6eedbf75` (usage receipts) |
| Mission commits | `2653647` (comparison view), `4671876` (Pi receipt in the view), `35ad2f9` (cost unknown) |

The route accepts one retained proposal and its original, binds both identities in the Grant,
rechecks them at dispatch, and records an append-only evaluation run. It never regenerates,
writes the manuscript, records a decision or changes promotion.

### Phase A live qualification

The first attempt failed closed at the Pi fence with no typed dispatch binding
(`4332d806-1839-432e-918d-56099c4ac8d8`, `authority_refused`). The run is retained. After the
binding was added, the v906 proposal evaluation completed:

| Field | Value |
| --- | --- |
| Evaluation run | `a7114cdb-0c72-4b6a-aa0a-11dd5b41a629` |
| Proposal SHA-256 | `c8daa07f…` |
| Original SHA-256 | `ad89a4e9…` |
| Verdict | `benefit` |
| Mechanical | `attention` — equation delimiters changed, explained |
| Proposal/decision/chapter after | unchanged / still pending / unchanged |

This one assessment is not proof. It qualified the read-only path.

## Phase B freeze

`experiment-manifest.json` revision 3, SHA-256
`4fdc321b9ee4fdfc795b7c73055818c8366db6a56fe88434f87a0807d7e93474`.
`freeze-receipt.json` records the source, plan, criteria, experience-context and code hashes.

| Field | Value |
| --- | --- |
| Experiment | `MC-LIVING-BOOK-02D-PILOT-1` |
| Held-out chapter | `content/books/distillation/15-chapter.md` |
| Chapter SHA-256 | `5bf5c4c7e06c2bea92156a8ff78fbe00a8da3151f6cb92a537f8b3826f2e464f` |
| Pinned source | capture `a632c716…`, approval `3996f4b2…` |
| Plan | v1006, six sections, 8 calls, SHA-256 `637feb22…` |
| Criteria | `criteria.txt`, 565 chars, SHA-256 `6d0ac383…` |
| A | `use_experience=false` |
| B | `use_experience=true`, context SHA-256 `e5993c62…` |
| Experience item | `390ba0bd…`, chapter 14, decision `203b21a5…`, quality `evaluation_failed` |
| Models | workflow `muse-spark-1.3-contributor`; evaluator `muse-spark-1.3` |

The one allowed infrastructure retry was recorded before it ran, after B's first attempt timed
out with no proposal. The retry used the identical authorization input hash
`1f00ff3d…`.

## Phase C result

| Attempt | Run | Status | Calls | Tokens | Proposal |
| --- | --- | --- | --- | --- | --- |
| A | `1bae6afa-3b24-4cf6-8683-bad990faf8e7` | COMPLETED | 8 | 51,312 | `93914a3d…` |
| B attempt 1 | `e493ef43-4316-42e2-8c37-cb917a5b1494` | UNKNOWN | 2 | 31,454 | none |
| B retry | `5033629a-7e85-4cb7-9a5e-4f419376e37a` | UNKNOWN | 2 | 30,834 | none |
| A evaluation | `7f5f348d-0e52-4057-a77b-c5a559add843` | COMPLETED | 1 | 13,945 | verdict `benefit` |

Arm A's independent rubric: technical 4→4, argument 3→4, clarity 3→3, economy 2→3,
completeness 3→3, provenance 3→4 (total +3); mechanical checks pass. This is one blind model
assessment, not proof.

Arm B never produced a proposal. Both attempts completed the review stage and then timed out at
the first experience-bearing section request (`ambiguous_provider_request`, ~33 s, no provider
response). The Pi receipts are `ca6d4fa6…` and `17332de5…`.

**Outcome: `inconclusive`.** The pre-registered comparison is invalid without a B proposal and a
B evaluation. No benefit, no-benefit or harm conclusion follows. H2 was not testable because no
independently evaluated lesson exists.

## Phase D live verification

At `http://127.0.0.1:8790/projects/distillation/read`, chapter 15, Improve:

- the preview lists all three runs, including both B failures;
- selecting A and the B retry opens `Two runs, one pair`;
- the conclusion is `inconclusive` with `comparison incomplete`;
- A shows its proposal, rubric and `benefit` evaluation;
- B shows `No proposal retained`, the `section_1` failure and Pi receipt
  `17332de5-1079-46ac-93f3-4ad0f573e9c2`;
- B shows the experience item's `evaluation_failed`, quality-unverified, context-only status and
  context hash `e5993c62…`;
- the side-by-side rubric shows A's deltas and `-` for B;
- no console errors; the comparison request returned 200.

The comparison endpoint is read-only and makes no model call:

`GET /api/living-book/projects/distillation/improvement/comparison?run_ids=…&run_ids=…`

## Final state

- Chapter 15 SHA-256 unchanged: `5bf5c4c7…`.
- Chapter 14 SHA-256 unchanged: `ad89a4e9…`.
- Arm A decision: `pending`; no decision event.
- Arm B: no proposal; decision unavailable.
- Experience item: still `evaluation_failed`, `quality_unverified: true`, `promotable: false`.
- No manuscript write, promotion or deployment.

## Non-claims

- The outcome is inconclusive; it is not evidence that experience helps or harms.
- The experience item is not an independently evaluated lesson.
- Owner acceptance is context, not quality evidence.
- A model verdict is not publication readiness.
- One pair is not statistical evidence.
- The evaluator shares a model family with the generator.
