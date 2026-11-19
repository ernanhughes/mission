# MC-LIVING-BOOK-02B-R1 — Acceptance evidence

**Date:** 2026-11-19

**Scope:** qualify the v906 evaluation path, preserve quality/decision separation, and gate chapter
experience. No manuscript write.

**Report:** [MC-LIVING-BOOK-02B-R1](../../MC-LIVING-BOOK-02B-R1.md)

---

## 1. Evaluation-only path

The retained proposal `ce2488e4…` cannot be re-evaluated without regenerating it:

- the workflow runner never resumes or dispatches a stopped run;
- the chapter `evaluate` stage is only constructed inside the chapter DAG from a predecessor
  `save_proposal` artifact;
- there is no standalone chapter-evaluate route, capability action or Bespoke handoff;
- the documentation independent-evaluation endpoint requires `documentation-improvement` and a
  different scored rubric.

Exact refusal path for the old evaluation:

| Item | Value |
| --- | --- |
| Old run | `c335aacf-cd5a-43a3-8914-d6dacd2dfc8a` |
| Completed calls | 7 |
| Completed-token sum | 39,809 |
| Evaluate reservation | 63,914 |
| Total reserved | 103,723 |
| Old ceiling | 100,000 |
| Observed error | `authority_refused`; Pi `workflow_authority_revoked`, `pi_unexpected_requests` |
| Old code | `informed_service.py` / `section_service.py`: `max_tokens: 100000` |
| New code | `max(100000, model_calls × 30000)` → 240,000 for 8 calls |

## 2. v906 end-to-end evaluation

The authorised bounded fallback was one v906 run on the pinned source.

| Item | Observed |
| --- | --- |
| Run | `9bf54fd8-d55c-4bcf-a0a6-7aa90a131dc9` |
| Workflow | v906, definition `6840efe4-4415-49d5-b99f-4da88d0c5d9c`, six sections |
| Source | pinned capture `a632c716…`, approval `3996f4b2…` |
| Chapter SHA-256 | `ad89a4e96412b58818579c79b6c06dd6eac6082b3f6e549c4a337fb7d5acaa05` |
| Status | `COMPLETED`, 12/12 stages |
| Calls / tokens | 8 / 54,150 |
| Budget | 8 calls, 12,288 output tokens, 900 s, effective token ceiling 240,000 |
| Proposal | `c8daa07f30499d2042c3947cfefd43bb9803d2b61e84be23a75d3dc88d0f2464` |
| Diff | 51 added, 225 removed |
| Evaluation | `evaluated`, `promising` |
| Evaluation limitations | Text comparison only; did not re-derive ledger numbers, hashes, code or citations |
| Author decision | pending |
| Chapter file after run | unchanged, same SHA-256 |

The evaluation is a model assessment. It is not an independent comparative evaluation and does not
establish quality improvement.

## 3. Experience quality gate

The old accepted decision previews with:

```text
decision: accepted
quality.status: evaluation_failed
quality.quality_unverified: true
quality.note: The evaluation did not complete. Owner acceptance does not establish quality.
promotion.eligible: false
promotion.status: context_only
```

The v906 pending proposal appears in `recent_improvements` with `decision: pending` and
`evaluation_status: evaluated`, verdict `promising`. It is not an author decision.

The chapter experience receipt now carries:

```json
{
  "quality": {
    "evaluated": 0,
    "evaluation_failed": 1,
    "unverified": 1,
    "contradicted": 0,
    "promotion_available": false,
    "note": "Quality evidence is attached, never promoted: a failed, missing, negative or contradicted evaluation remains visible and cannot become a proven improvement."
  },
  "promotion": {
    "eligible": false,
    "status": "context_only",
    "reason": "Chapter experience is owner-decision context. Improvement or transfer requires a separate comparative evaluation; owner acceptance alone is not such evidence."
  }
}
```

Independent `improvement.evaluated` records, when present, are attached as `quality.history`; they are
never written into or over a decision. A remaining or critical error changes the quality status to
`contradicted` and keeps promotion disabled.

## 4. Family and plan

| Family | State |
| --- | --- |
| v6 / 801–806 | historical |
| v7 / 901–906 | historical |
| v8 / 1001–1006 | current |

The live chapter-14 plan after v8 activation is v1006, six sections, eight calls, same source plan
SHA `642e4792…`. The v906 run remains readable as a historical run.

## 5. Verification

| Check | Result |
| --- | --- |
| `tests/test_chapter_experience_quality.py` + `tests/test_capability_registry.py` + `tests/test_living_book.py` (ALIVE) | 22 passed |
| Mission improvement + living-book tests | 11 passed |
| Mission full backend | 507 passed, 1 skipped; 4 unrelated environment failures |
| Frontend targeted LivingBookPage | 4 passed |
| Frontend full suite | 82 passed, 2 unrelated flakes that pass in isolation |
| Frontend production build | passed |
| Live v906 plan | 200 |
| Live v8 plan | 200, v1006, six sections, eight calls |
| Live experience preview | quality `evaluation_failed`, promotion `false` |
| Live UI | quality-unverified tag and recent pending/accepted runs visible |

The four backend failures are pre-existing environment-dependent areas (cultivation Git dates,
configured editor, quality evaluator availability, scripts weekly boundary). The two frontend flakes
are unrelated and pass together in isolation.

## 6. Non-claims and open items

- The v906 evaluation verdict is one model assessment, not independent quality proof.
- The v906 proposal remains pending; no author decision was invented.
- The old accepted decision remains historical and quality-unverified.
- v8’s quality gate is exercised by the live experience preview, not by a new model run with
  `use_experience=true`.
- No manuscript file was modified or applied.
- The source remains pinned for reproducibility.
- No chapter independent-evaluation route exists yet. The gate’s `quality.history` attachment point
  reads the existing append-only `improvement.evaluated` contract, but recording such evidence against
  an already-retained chapter proposal is a remaining structural gap.
