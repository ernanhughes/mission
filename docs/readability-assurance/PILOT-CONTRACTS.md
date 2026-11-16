# Pilot contract review packet — chapters 10, 34, 44

**Status:** all three contracts have `SUPPORTED` independent reviews; **none is
approved**. **Chapter 10 is STALE on the current book branch** and cannot be
approved or used until it is re-audited and re-contracted (or evaluated against
a pinned `main` worktree). Chapters 34 and 44 remain source-current.
Approval is the author's action and freezes the content hash.
**Date:** 2026-11-16
**Source:** `C:\books\inference` on `editorial/reader-first-reconstruction`
(`1403b62`); Chapter 10 contract was built against the then-current checkout
`f958967` (current `main` is `132820e`).

| Chapter | Contract | Version | Region | Contract source SHA-256 | Current source SHA-256 | Freshness |
|---|---|---|---|---|---|---|
| 10 | `exp-7f9262f8c66377cd` | 2 | L106–108 | `fd34d339…f1b2` | `9f055001…92d8` | **STALE** |
| 34 | `exp-3d0a9322fcc0771e` | 2 | L121–123 | `92e1385f…b919` | `92e1385f…b919` | CURRENT |
| 44 | `exp-c732f3709d55f68a` | 1 | L131–133 | `26c5ba68…9c8e` | `26c5ba68…9c8e` | CURRENT |

All three remain `REVIEW_REQUIRED`. Chapters 34 and 44 are source-current and
eligible for author review; Chapter 10 is stale on the editorial branch and is
not eligible. No candidate was generated for any chapter.

## Chapter 10 — KV-cache logits parity

> **STALE:** this contract pins `fd34d339…f1b2` from `main`. The current
> editorial branch has `9f055001…92d8`. Do not approve or run it against the
> current chapter; re-audit and create a new contract, or evaluate against a
> pinned `main` worktree and label it as historical.

**Reader objective:** understand that the logits comparison is more sensitive
than selected-token parity, what maximum absolute errors were reported, why
floating-point and near-tie caveats limit what the 48-step argmax match proves,
and that the checked-in tests do not run the real-model measurements or verify
the effect of hot-swapping weights.

**Questions:**

1. For each of 48 positions, what did the parity command compare?
2. What were the GPU median and worst maximum absolute errors for a position,
   and what was the CPU worst?
3. What did the separate library comparison at the original prompt show on the
   GPU and CPU?
4. Why does matching argmaxes across 48 steps not rule out a different token
   elsewhere, and what should accompany an absolute-error threshold for other
   models?
5. What do the checked-in tests exercise?
6. What do the checked-in tests not execute or verify?
7. What is the status of the recorded GPT-2 measurements in
   `research/ch10/results.json`?
8. What can change the last few bits in the comparison?

**Review:** `SUPPORTED`, zero non-pass findings. Optional suggestions remain:
add the decision-margin clause to the stated order, clarify that hard items may
be paraphrased, and tighten two definitions. These are not blockers.

## Chapter 34 — Tool-loop latency

**Reader objective:** understand the measured fresh-prefill and reuse timings,
the modelled contributions, the illustrative ten-call scenario, and why the
earlier sample is evidence of an environmental confounder rather than a reason
to choose whichever measurement looks best.

**Questions:**

1. What did the 30-appended-token microbenchmark show for fresh-prefill time as
   context increased from 100 to 4,000 tokens, and what range did the reuse
   primitive show?
2. What were the fresh-prefill and reuse ranges for 500 appended tokens?
3. What does the passage say the relatively flat reuse timings partly reflect,
   and what do they not reflect?
4. In the short recorded loop, what were the prompt token averages and
   generation rounds, and what modelled mean prefill contributions were
   produced?
5. What does the illustrative ten 2,000-token resumptions scenario cost under
   the repeated 623-ms fresh-prefill approximation versus 30-token
   continuations, and what caveats are attached?
6. What does the earlier `reentry_earlier_busier_gpu.json` sample show versus
   the later checks, and how was the earlier observation used?
7. What does the passage recommend before claiming a production latency
   advantage, and which hardware and run factors belong in the manifest?

**Review:** `SUPPORTED`, zero non-pass findings, no recommended changes.

## Chapter 44 — A/A control and SLO ratios

**Reader objective:** understand what the A/A control shows, why an interval
containing the null is not proof of equivalence, why zero-denominator ratios are
not meaningful speedups, and how the parametric and exact small-sample analyses
can point in different directions.

**Questions:**

1. What does the A/A control show about treating an A/A cell as evidence of
   equivalence when its headline interval contains the null?
2. What heavy-traffic median SLO pass shares and five-trial ranges are reported
   for `cap-batched-8` and `cap-batched-8-copy`?
3. Why is a geometric ratio not returned for some serial configurations on
   heavy combined SLO?
4. What alternative reporting does the passage recommend instead of dividing
   pass shares by zero?
5. How can the *t*-analysis and exact sign-flip test point in different
   directions for the same A/A TPOT comparison?
6. How should zero and one SLO shares be treated?

**Review:** `SUPPORTED`, zero non-pass findings, no recommended changes.

## Approval checklist

- [ ] Current source SHA matches the contract's `source_revision` (Ch 10 is
      stale and cannot be approved).
- [ ] Each question is answerable from the cited source region.
- [ ] Hard preservation items capture the exact values, units and identifiers.
- [ ] Semantic items capture the conditions, scope and limitations the author
      intends to keep.
- [ ] The reader objective is the outcome the author wants, not a prose style.
- [ ] Approve with a named actor and rationale; approval freezes the content
      hash and does not apply any manuscript change.

After approval, the next step is one bounded candidate through gates A–E. No
candidate generation or Apply is authorized by this packet.
