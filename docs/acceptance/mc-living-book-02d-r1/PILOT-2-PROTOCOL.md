# MC-LIVING-BOOK-02D-PILOT-2 — draft protocol

Status: **prepared, not authorised, not executed.** This document does not start a run and does
not change PILOT-1. Execution requires a separate owner authorisation.

PILOT-1 remains frozen and `inconclusive`. Its manifest, runs, decisions and conclusion are not
amended.

## 1. Questions

| ID | Question | Evidence needed |
| --- | --- | --- |
| H1 | Does the workspace's relevant historical context improve a new task compared with no experience? | A valid A/B proposal comparison with independent evaluation |
| H2 | Does relevant context help more than irrelevant context of similar size and format? | A valid B/C comparison under the same conditions |
| H3 | Does a qualified lesson transfer to a different held-out task? | A separately qualified lesson and transfer comparison — **not attempted here** |

This protocol tests H1 first. H2 is conditional on an eligible irrelevant item. H3 is out of
scope until an independently qualified lesson exists.

## 2. Frozen task set (to be checked again at authorisation)

| Field | Proposed value |
| --- | --- |
| Chapter | `content/books/distillation/16-chapter.md` — *Dataset Distillation* |
| Chapter SHA-256 | `a4e0ee678f56c95b95a17498acc6473ed7b327a2ea44bc1f3c5b7e665257352f` |
| Characters | 26,197 |
| Source | pinned capture `a632c716…`, approval `3996f4b2…` |
| Workflow | `chapter-improvement` v1006, six sections |
| Plan SHA-256 | `45970e69ebbe01e9e73b99d3b229bcd5fe5e35de6304f193446c39ca685c02ed` |
| Model calls / tokens | 8 / 100,000 per run |
| Criteria | `pilot2-criteria.txt`, 416 chars, SHA-256 `9d33af5771b5a49cfb291b9ee4396b84818d73f10911d23f8418355803e9a122` |
| Prior improvements | none on this chapter at preparation time; verify before authorisation |

## 3. Conditions

All conditions use the same source, plan, criteria, workflow, model, call/token budget and
authority. The only intended difference is the experience context.

### A — no experience

`use_experience=false`; empty experience context.

### B — relevant historical context

`use_experience=true`; the existing chapter-14 owner-decision experience:

| Field | Value |
| --- | --- |
| Improvement | `390ba0bd-0662-4788-b24c-284721cf4dd6` |
| Decision event | `203b21a5-ea2e-57d9-a877-a24a8ebda394` |
| Quality | `evaluation_failed`, `quality_unverified: true` |
| Promotion | `eligible: false`, `context_only` |
| Retrieval score for this task | `0.647` |
| Context SHA-256 | `e5993c625ac957e55de39b5b5be060bddb808c4ab60b18cc37c7b5edd610653a` |
| Context characters | 2,070 |

The item is context, not a proven lesson. The run must record both the retrieval receipt and the
actual context admitted to the model.

### C — irrelevant historical context

**Blocked.** The workspace has only one eligible owner decision. A valid C item must be a
permission-safe retained historical item with a comparable format and size, from a different task
or chapter, clearly labelled as context and not as a lesson. It must not be the chapter-14 economy
item and must not be fabricated from it.

Before C can run, the owner must create or authorise an eligible item through the normal decision
path and freeze its identity, quality status and context hash. If that does not happen, H2 is not
tested and the protocol must not substitute a pseudo-control. H1 can proceed only under a separate
reduced-protocol authorisation.

## 4. Models, transport and budgets

| Field | Proposed value |
| --- | --- |
| Workflow model | `muse-spark-1.3-contributor` |
| Evaluator | `muse-spark-1.3`, rubric `chapter-evaluation-v1`, blind to condition |
| Provider timeout | `ALIVE_META_TIMEOUT=90` s, qualified by R1; requires owner authorisation |
| Pi run deadline | at least 120 s |
| Provider requests | exactly one per reservation; no automatic retry |
| Improvement | 3 runs × 8 calls = 24 calls; 300,000 tokens ceiling |
| Independent evaluation | 3 runs × 1 call = 3 calls; 300,000 tokens ceiling |
| Total | 27 calls; 600,000 tokens ceiling |
| Monetary | unknown; ALIVE has no price table for this transport. Never report zero |

Order: A, B, C; evaluations A, B, C. The order is pre-registered; no run is repeated to obtain a
more favourable result.

## 5. Valid comparison and outcome rules

A block is valid only when:

- every condition the comparison needs completed with a retained proposal;
- source, plan, criteria, workflow, model and (for B) experience-context hashes match the freeze;
- every proposal has a completed independent evaluation with valid quotes;
- no manuscript write, decision or promotion change occurred.

The 02D pair rules apply. For H1, compare B with A. For H2, compare B with C.

- `benefit_observed`: the treatment verdict is `benefit`; the comparator is not; the treatment's
  total and economy rubric deltas exceed the comparator's; preservation attention does not
  increase; technical, argument and provenance guardrails do not fall; every attention item is
  explained.
- `no_benefit_observed`: the comparison is valid and the benefit rule is not met.
- `harm_observed`: the treatment verdict is `harm`, a guardrail falls, attention increases, or the
  treatment's total delta is below the comparator's.
- `inconclusive`: a condition, proposal, evaluation, identity or receipt is missing, or the
  signals conflict.

For H2, `benefit_observed` means **relevance specificity was observed in this block**, not that
relevant experience is generally better. A single block cannot establish general transfer.

## 6. Failure, timeout and retry rules

- A timed-out or ambiguous provider request is terminal for that run: its slot is not retried,
  the run has no proposal, and the condition is incomplete.
- A timeout is not a quality result. Unknown usage is never recorded as zero; the reservation is
  charged conservatively once.
- No second provider request is permitted under the same reservation. A second inbound request is
  refused (`request_limit`).
- An incomplete condition makes the block `inconclusive`. **No rerun of that condition** to chase
  a result. A new block requires a new pre-registered protocol and separate owner authorisation.
- Definite pre-dispatch refusals (authentication, quota, invalid request) may be investigated and
  corrected as an infrastructure repair, but any new run still requires authorisation and must be
  recorded as a new attempt, not silently substituted.
- A provider timeout change must be qualified on isolated calls before a full workflow; R1
  performed that qualification at 30 s and 90 s.

## 7. Measurements

For every condition record: run id, status, stages, proposal artifact and text hashes, original
hash, plan hash, criteria hash, retrieval receipt, actual admitted context hash and size,
mechanical preservation checks, independent verdict and six dimension deltas, calls, tokens,
latency, provider request identifiers, Pi receipt ids, and cost status (unknown, not zero).

Also record the review output identity and size, because the review is a separate non-deterministic
model call and is not experience-conditioned.

## 8. Known limitations

- One block is a pilot, not a statistical test; no significance or general-transfer claim follows.
- The evaluator shares a model family with the generator; it is blind to condition, not
  third-party or human review.
- The review stage is a separate non-deterministic call. Different reviews across conditions are
  a noise source even though the review is not experience-conditioned.
- C is a context control, not a matched-quality control. A B/C difference may reflect the content
  of the irrelevant item as well as its irrelevance.
- Cost is unknown because ALIVE has no price table for the transport; cost must not be reported as
  zero.

## 9. Preconditions

1. Separate owner authorisation for PILOT-2.
2. Provider timeout decision made and verified; no global change without authorisation.
3. Source, chapter, plan and criteria re-verified against this document at freeze time.
4. No prior improvement run on chapter 16.
5. C item eligible and frozen, or H2 explicitly omitted under a reduced authorisation.
6. Independent evaluation workflow available and unchanged.
7. No manuscript write, decision change or promotion.

## 10. Non-claims

Provider reliability is not evidence of learning. Retrieving experience is not evidence that it
helped. A favourable independent model assessment is not proof of general quality improvement. A
successful H1 or H2 block is not evidence of general transferable learning. H3 remains untested
until a qualified lesson exists.
