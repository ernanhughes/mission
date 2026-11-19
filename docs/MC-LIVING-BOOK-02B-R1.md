# MC-LIVING-BOOK-02B-R1 — Evaluation Qualification and Experience Integrity

**Status:** Implemented and verified on the pinned Distillation source.

**Scope:** qualify the v906 evaluation path, distinguish quality evidence from author acceptance, and
prevent failed or unverified experience from becoming a proven lesson. No manuscript write, no 02C,
no 02D.

**Acceptance:** [mc-living-book-02b-r1](acceptance/mc-living-book-02b-r1/README.md)

---

## 1. Evaluation-only path: not available

The retained proposal `ce2488e4…` cannot be re-evaluated through an existing callable route:

- `alive/workflows/runner.py` explicitly never resumes or dispatches a stopped run; a failed stage is
  terminal and a new run starts from the beginning.
- The chapter `evaluate` operation is a DAG stage. It is not exposed as a standalone route, capability
  selection, or Bespoke action. `chapter.evaluate` is only constructed from a predecessor
  `save_proposal` artifact inside the workflow.
- The only independent-evaluation endpoint is the documentation workflow’s
  `POST /{run_id}/independent-evaluation`; its contract is limited to
  `documentation-improvement` and a different scored rubric. It is not a chapter evaluator.

This is recorded as the precise blocker. The authorised fallback was one bounded v906 end-to-end run.

## 2. Old 100,000-token refusal, reproduced

The failed run `c335aacf…` recorded:

| Item | Value |
| --- | --- |
| Completed stage tokens | 39,809 |
| Evaluate reservation | 63,914 |
| Total reserved | 103,723 |
| Old workflow token ceiling | 100,000 |
| Result | `standing_budget_exhausted` → `workflow_authority_revoked`; no model dispatch |

The old launch path hard-coded `max_tokens: 100000`. The v906 repair derives the ceiling from the
confirmed call plan: `max(100000, 8 × 30000) = 240,000`. The v906 run below exercised that path.

## 3. v906 evaluation run

| Item | Observed |
| --- | --- |
| Run | `9bf54fd8-d55c-4bcf-a0a6-7aa90a131dc9` |
| Workflow | v906, definition `6840efe4…`, six sections |
| Status | `COMPLETED`, 12/12 stages |
| Calls / tokens | 8 / 54,150 |
| Proposal | `c8daa07f30499d2042c3947cfefd43bb9803d2b61e84be23a75d3dc88d0f2464` |
| Diff | 51 lines added, 225 removed |
| Evaluation | `evaluated`, verdict `promising` |
| Evaluation limits | Text comparison only; hashes, code, citations and ledger numbers were not re-derived |
| Author decision | **pending** |
| Chapter SHA-256 | unchanged `ad89a4e9…` |

The evaluation is a model assessment, not an independent comparative result. It does not establish
quality improvement or transfer.

## 4. Experience integrity gate

The chapter experience path now attaches explicit quality evidence to every owner-decision item:

| Quality status | Meaning |
| --- | --- |
| `evaluation_failed` | evaluation did not complete; quality unverified |
| `not_evaluated` | no evaluation; quality unverified |
| `evaluated_promising` | one model assessment says promising; not comparative proof |
| `evaluated_mixed` / `evaluated_not_improved` / `evaluated_undetermined` | the assessment is negative or inconclusive |
| `owner_rejected` | owner rejection; retained as a negative observation |
| `contradicted` | later `improvement.evaluated` evidence records unresolved or critical issues |

Every item also carries:

```json
"promotion": {
  "eligible": false,
  "status": "context_only",
  "reason": "Chapter experience is owner-decision context. Improvement or transfer requires a separate comparative evaluation; owner acceptance alone is not such evidence.",
  "quality_status": "evaluation_failed"
}
```

The retrieval receipt reports `quality.evaluated`, `evaluation_failed`, `unverified`, `contradicted`
and `promotion_available: false`. The model note says owner acceptance is not quality evidence and no
item is a proven lesson. Later independent evaluation records are read through the existing
append-only `improvement.evaluated` contract and attached as `quality.history`; a decision is never
rewritten.

The old accepted decision now previews as:

```text
quality.status: evaluation_failed
quality.quality_unverified: true
promotion.eligible: false
note: The evaluation did not complete. Owner acceptance does not establish quality.
```

### Family identity

The gate changes a fingerprinted implementation, so it is a new immutable family: **v8/1001–1006**.
v7/901–906 and v6/801–806 remain readable historical families. The chapter-14 plan remains six
sections and eight calls.

## 5. Decisions and non-claims

- The author’s accepted decision on `ce2488e4…` is retained, but it is **not** a quality acceptance.
- The v906 proposal is retained and **pending**; no author decision was invented.
- The evaluation verdict `promising` is one model assessment, not an independent evaluation.
- No quality-improvement or transfer claim is made.
- The chapter file was not written.
- The source remains pinned to one exact capture for reproducibility.
- Recording a new independent evaluation against an already-retained chapter proposal is not
  available in this slice. The quality gate reads the existing append-only
  `improvement.evaluated` contract and attaches such evidence if it exists, but there is no
  chapter independent-evaluation route yet. This is the same structural blocker as evaluation-only
  execution, and it is why 02D needs a comparative measurement protocol rather than a promotion
  shortcut.

## 6. Next

`MC-LIVING-BOOK-02D` should compare control and treatment on held-out chapter tasks, with independent
quality measurement, pair-level receipts and no promotion of an unverified lesson. The quality gate
is the boundary that makes that experiment meaningful.
