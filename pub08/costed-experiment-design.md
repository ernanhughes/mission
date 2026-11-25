# PUB-08 — Costed Experimental Design (design only, nothing dispatched)

**Run identity.** Produced by **`opencode-go/deepseek-v4.1-flash`** (DeepSeek V4.1 Flash 1017) as an agent session, not a metered Worker dispatch. **Programme spend: $0.00. Zero pipeline/Worker/model dispatches. No repo writes, no commits, no PUB-09 work.** Two throwaway analysis scripts were written only under `%TEMP%\opencode\` (hash/size and control-string checks); nothing under `C:\Projects\mission`, `C:\books\jev`, `C:\Projects\writer` or `C:\Projects\worker` was modified.

---

## 1. Frozen-input manifest (verified this session)

### 1.1 Manuscript and candidates

| Ref | Path | Verified | Bytes | Lines | Raw SHA-256 | Pipeline fingerprint |
|---|---|---|---|---|---|---|
| **O** (source) | `C:\books\jev\content\books\jev\01-chapter.md` | exists, HEAD `c7aaad70a0bb…` (clean; 1 untracked pre-existing `scripts/`) | 31,903 | 562 | `144ab665…748417` | `435974701050832…` (PUB-06 record) |
| **H** (PUB-06 candidate) | `C:\Projects\mission\pub06\ch01\01-chapter-candidate.md` | exists | 34,620 | 606 | `981cac04…cd5c9c` | `f6c1cbf4266b…` (record chain) |
| Ch2 (out-of-scope fixture only) | `C:\books\jev\content\books\jev\02-chapter.md` | exists | 20,511 | 346 | `34e7961a…a38c7` | — |
| run-1 archive (control 7b only) | `C:\Projects\mission\pub07\ch02-superseded-run1\candidate.md` | exists, untouched | 20,716 | 338 | `804706fd…174d29` | line 138 verified verbatim |
| PUB-07 accepted candidate | `C:\Projects\mission\pub07\ch02-rerun\candidate.md` | exists | 20,239 | 355 | `9f36c9ba…a02b82` | `9f36c9ba…` |

Note: raw-file SHA-256 and the Writer **canonical** fingerprint are different hash functions; both are recorded so no later stage mixes them.

### 1.2 Evidence snapshot (read-only)

| Artifact | Path | SHA-256 | Load-bearing content |
|---|---|---|---|
| PUB-06 verification | `pub06\ch01\verification-report.json` | `3a99af30…d954fb0b` | **21/21 pass** (`byte_true_present` ×11, `no_change_identical` ×9, `new_sentence_honesty` ×1); cruft 1→1; complexity 38→39; 7 packages |
| PUB-06 record | `pub06\ch01\transformation-record.json` | `4c9f324f…9239404` | `writer.transform.record.v1`, 0 model dispatches, chain `f6c1cbf4…`, H identity **CONFLICTED** |
| PUB-06 package plan | `packages-ch1.json` / `plan-ch1.json` | `ba7f869c…` / `cb34c18e…` | 7 packages, 17 isolated ops, 12 respected, boundary executable |
| PUB-06 adjudications | `adjudications-ch1.json` | `188d843f…ad04e2` | 17 bound adjudications (declines preserved) |
| PUB-07 ledger actual | `pub07\ch02-rerun\program.json` | `3d715cc2…6c959c` | editorial **2,136 in / 6,110 out = 8,246 tok, $0.0039864**; review 5,678 tok, $0.00 |
| Jev claim ledger | `C:\books\jev\evidence\ledger.md` | `efe41584…0b3f9d` | Ch1 claims **1.1–1.25** with types DOCUMENTED / OBSERVED / PROPOSED / HYPOTHESIS / 3P-not-DOCUMENTED, plus **"Not claimed in Chapter 1"** |
| Programme docs | STATE / ROADMAP / DECISIONS / ACCEPTANCE / CAPABILITIES / ARCHITECTURE / README | `7119d336…`, `b7421c52…`, `a801766b…`, `55c36e19…`, `15d61820…`, `2c11378c…`, `36f15fd6…` | D-PUB-74/84, ACCEPTANCE §2/§3 |
| Reuse matrix | `pub08\reuse-matrix-survey.md` | `b36dca85…83c3e5` | mandatory starting point |

### 1.3 Detector / planner / contract versions (byte-fingerprinted, not just version strings)

| Component | Version | Module SHA-256 |
|---|---|---|
| Automation (generation+review+loop) | `publication-automation-v0.1` / `automation-v0.1` (UNCALIBRATED) | `publication_automation.py` `b311ccac…8bab2` |
| Transformation boundary/packages/verify | `publication-transformation-v0.1` / `transform-v0.1` | `publication_transformation.py` `81432a0c…374e1` |
| Pedagogy planner | `publication-pedagogy-v0.1` / `pedagogy-v0.1` | `publication_pedagogy.py` `499e5cde…1457c` |
| Cruft | `publication-cruft-v0.1` / `cruft-v0.1` | `publication_cruft.py` `00e07ecf…c09e73` |
| Complexity | `publication-complexity-v0.1` / `complexity-v0.1` | `publication_complexity.py` `46aee580…c8e13` |
| Evidence reconciliation | `evidence-reconciler-v0.1` / `reconcile-v0.1` | `evidence_reconciliation.py` `23c5eb5b…d5352` |
| CLI surface | — | `transform.py` `7dd74c2a…819c3dd` |
| Model/pricing catalogue | `opencode-go-catalogue-2026-11-08` | `worker.models.yaml` `805a6b61…464fd` |

Contracts: `EditorialCandidateResponse` / `EditorialReviewResponse` (v0.1), `writer.automation.ledger.v1`, `writer.transform.record.v1`, `writer.automation.program.v1`, `writer.automation.correction.v1`.

### 1.4 Repo state at freeze time

`mission` `e9888449…` (dirty, pre-existing + programme docs); `writer` `65a26839…` (36 dirty entries); `worker` `a2e881c8…` (19 dirty); `workbench` `55b794b2…`; `jev` `c7aaad7` clean except untracked `scripts/`.

**Consequence:** because `writer` is dirty, the manifest freezes **module bytes** (above), not only HEAD. A dispatch is refused if any frozen module hash changes.

**Not verified this session (carried uncertainties):** `tests/runtime/{mri,argument}` presence; Mission-side evidence-reconciliation coverage; `run_typed_task` runtime behaviour beyond its call site in `transform.py`.

---

## 2. Arms, prompt sketch and workflow plan

### 2.1 Arm definitions

| Arm | What it is | Generation cost | Role |
|---|---|---|---|
| **O** | The source chapter (`c7aaad7`) | $0 | non-generated reference |
| **H** | PUB-06 candidate (Muse-authored inside compiled packages, 0 paid dispatches) | $0 | non-generated engineered reference; its own identity is CONFLICTED |
| **A** | Direct AI editing: **one** dispatch, whole chapter, one prompt, one shot, no plan/packages/loop | 1 paid | treatment 1 |
| **B** | PUBLICATION workflow: reconcile → plan → packages → per-package dispatch + independent review + bounded correction + deterministic assembly | 2–5 paid | treatment 2 |
| **C** | A's bytes + PUBLICATION verification/attribution + bounded repair of verification-found defects only (paired on A) | 0–2 paid | optional, cheap, isolates verification |

C is deliberately **paired on A's output**, not a fresh generation: that makes "value of verification alone" a within-text comparison and costs no extra generation.

### 2.2 Arm A prompt sketch (careful, not weakened)

Delivered as **one** dispatch through the same D-PUB-08 seam (`run_typed_task` → `models.run` → Worker `POST /v1/work`) and the **same model/route** as B (`default_deepseek_go`), one shot, no retry, no repair. (Full prompt text in the design agent's report as issued; frozen with SHA before dispatch — including honesty-preservation constraints, one-synthesis-per-section cap, no prose-characterisation rule, and JSON-only whole-chapter output.)

**Fairness record (written into the freeze record):** A is denied only the *products of the engineered stack* (plan/op ids, package boundaries, detector findings, parsed preservation obligations, review rounds, correction loop); A gets the whole chapter in one context (≈7.8k tokens), strictly *more* context than any single B package; A's prompt is at least as explicit about quality and preservation as B's package prompt; A uses a whole-file experiment DTO (reusing `replacement_lines` would structurally handicap it); A's declarations are recorded, never enforced (enforcement is Arm C); malformed/truncated A output is a recorded failure mode, not a retry.

### 2.3 Arm B workflow plan (compose the matrix; invent nothing)

1. **Reconcile** → states + inventory revision (deterministic, $0); reuse PUB-06 states if revision unchanged.
2. **Plan** — reuse frozen `plan-ch1.json`; revalidate with `transform check` (deterministic, $0); re-plan only if stale.
3. **Package** → 7 packages (5 mutating; 17 ops isolated, 12 respected).
4. **Dry run** per package: freeze prompt SHA, passage SHA, obligation list; **zero dispatches**. Gate: prompt-SHA drift halts B.
5. **Dispatch** — one `transform automate` per executable package against O (never a mutated file); 1 editorial (paid) + 1 review ($0) + bounded correction (≤2) each.
6. **Assemble** — deterministic bottom-up merge onto O with per-line lineage; `verify_candidate` re-run on merged bytes. (Each package candidate differs from O only inside its own region.)
7. **Publish** — candidate + program + verification + record per package, plus one merged record. Nothing applied; tree untouched.

**Two real blockers found in the production path (not cost):**

- **B-i Single-contiguous-span rule.** `transform automate` refuses multi-region packages (only 2 of Ch1's 5 mutating packages qualify).
- **B-ii No multi-package composition.** No merge/chain step; chaining unsafe under freshness binding.

Ways forward (both $0 inference, both code): **B-max (no code)** — 2 contiguous packages only, valid sample but not chapter-level; **B-hull (small increment, recommended)** — compile each package to its span hull with intervening lines protected, plus a deterministic merge step (passage input 1,456 → 2,224 tokens; preserves package coherence instead of fragmenting into 13 slices). **Rejected:** 13 region slices. **Mandatory $0 gate before any B-hull dispatch:** no-op merge reproduces O byte-for-byte; synthetic two-region merge passes verify; dry-run shows one span per package.

### 2.4 Arm C plan

1. A's bytes as input (no new generation). 2. Composed verification stack (claim diff, entailment/grounding, certainty comparison, semantic-loss/quantity units, reconcile allow-list, D-PUB-84 attribution). 3. Repair **only** `TRANSFORMATION_INTRODUCED` / `TRANSFORMATION_STRENGTHENED` / `TRANSFORMATION_REDUNDANT_SYNTHESIS` in ≤2 bounded dispatches (≤$0.010 each), each re-verified. `INHERITED_UNRESOLVED` / `AUTHORIZED_IMPROVEMENT` never repaired. 4. If A unusable, C skipped and recorded as skipped.

### 2.5 Shared evaluation pipeline (composed, no parallel architecture)

Manuscript IR (`compile_chapter`, `verify_candidate_downstream`) → evidence claim extract/verify + argument entailment/drift → artifact `check_semantic_loss` + quantity units → QC CALLABLE gate → PUB-03 reconcile allow-list → deterministic screens (cruft/complexity/legibility/editing/quality) → mediated read + evaluation fabric (proxy only) → `revise` blind_ab trial shape for blinding → **D-PUB-84 contract (the one genuinely missing piece)**: thin record builder over the above (deterministic quote-existence + claim matching + model judgement for semantic classes only). **Rebuild rule:** every derived metric regenerated after the last detector change, regeneration recorded.

---

## 3. Blinded evaluation rubric (frozen before generation)

**No composite score anywhere.** Four dimension profiles, hard gates, dominance rule (preferred only if ≥ on every hard gate and better on ≥2 dimensions; else a reported trade-off; n=2 is a structured case comparison).

### 3.1 Blinding protocol

5 texts (O, H, A, B, C) → `T1…T5` by seeded shuffle; seed/mapping/pack SHA frozen. Judges get label + text only. Two independent judges: **reviewer** (haiku, editorial) and **reader** (haiku, comprehension); generator is deepseek so neither judge is the reviser. Recorded limitations: O recognisable; A/C near-identical outside repairs; H register recognisable.

### 3.2 Dimension 1 — Semantic integrity (hard gates)

Preservation obligations survive (**0 byte-true failures**); numbers unchanged (**0 altered**); no new unsupported claims (**0**); certainty preserved (**0** strengthened, 0 ledger-type upgrades); authorized changes only (**0** unlinked); attribution correctness (**7/7**, 0 misattributions — **stop rule**: any control failure invalidates the stack, no further paid dispatch without coordinator approval); quote validity (0 out-of-scope, 0 absent).

### 3.3 Dimension 2 — Editorial quality (profile, never a target)

Deterministic delta vs O (cruft/complexity with max severity preserved — no count-reduction incentive); workload proxies (legibility, editing, quality-evaluate on an isolated DB path); 8-criterion editorial checklist with verbatim quotes (no quote → abstain). **Anti-cheat gate:** honest-record sentence count must not drop.

### 3.4 Dimension 3 — Reader recovery (`MODEL_READER_PROBE`, not human comprehension)

12 fact probes + 3 epistemic probes (E1–E3: model-backed arms ran? contract as documented fact? overhead measured here? — all must answer No), key frozen pre-generation; 6 public / 6 held-out, held-out run once. Model-reader evidence is proxy only, never human comprehension.

### 3.5 Seven D-PUB-84 controls — frozen fixtures (strings verified absent/present in O, H, Ch2, run-1 archive this session)

NC1 byte-identical inherited claim (O:513 billing sentence; `INHERITED_UNRESOLVED`); NC2 newly introduced claim (A100-style sentence; `TRANSFORMATION_INTRODUCED`); NC3 strengthened hedge (contract "documented and can be trusted"; `TRANSFORMATION_STRENGTHENED`); NC4 out-of-scope citation (Ch2:26 vendor-pages line; `OUT_OF_SCOPE_CITATION`); NC5 absent quotation (predicate 12-of-20; `INVALID_REVIEW_EVIDENCE`); NC6 authorized correction (O 557–558 → OBSERVED + reconcile row; `AUTHORIZED_IMPROVEMENT`); NC7 redundant synthesis (7a injected "floor is real, not rhetorical" + 7b run-1 line-138 reference; `TRANSFORMATION_REDUNDANT_SYNTHESIS`). NC1/NC4/NC5/NC6 deterministic ($0); NC2/NC3/NC7a need model judgement (3 × 5 texts = 15 small $0-route dispatches).

### 3.6 Operational dimension

Dispatch counts, tokens, cost, latency, failure modes verbatim, provenance completeness, scope discipline, wall-clock/human interventions, budget compliance (aggregate projection, actuals ≤ $1.00).

---

## 4. Cost model (estimates unless marked "observed")

Unit economics (observed): deepseek $0.15/$0.60 per MTok in/out; haiku ledger actual $0.00. PUB-07 editorial anchor: 2,136 in + 6,110 out = 8,246 tok → $0.0039864 (blended $0.4835/MTok). Chapter ≈ 7,817 tokens (±15%). Cost driven by dispatch count × reasoning, not prose length.

| Arm | Paid dispatches | Central $ | Band |
|---|---|---|---|
| O / H | 0 | $0 | $0 |
| A | 1 | $0.010 | $0.008–0.015 |
| B-hull | 5 (+≤2 corrections) | $0.026 | $0.019–0.050 |
| B-max (no code) | 2 (+≤1) | $0.010 | $0.007–0.015 |
| C (paired) | ≤2 | $0.015 | $0.010–0.020 |
| Evaluation ($0 route) | 0 paid | $0.00 actual ($0.13 if haiku meters) | $0.10–0.16 |

**Recommended n=2 replicates:** paid generation 2 × ($0.010+$0.026+$0.015) = **$0.102**; evaluation $0.00 actual; **central ≈ $0.10 (≈$0.23 if verification meters); worst case ≈ $0.42; headroom ≈ $0.58 (2.4×)**. n=1 ≈ $0.05/$0.18; n=3 ≈ $0.15/$0.28 (fits, eats reserve; conditional).

**Fits in $1.00:** O/H/A/B/C, all dimensions, all 7 controls, 12+3 probes × 5 texts, 2 replicates, 2.4× reserve. **BLOCKED — not by budget:** (1) human reader study (deemed nonexistent; no human-comprehension claim permitted); (2) full-chapter B needs B-hull + merge code; (3) no multi-package merge exists; (4) no independent human editorial read (author-side); (5) n=2 is case comparison, not effect size; (6) second book out of scope; (7) `check_spend_guard` is per-invocation — a programme-level $1.00 aggregate wrapper is required before multi-invocation dispatch, or the cap is not actually enforced.

## 5. Go / no-go per paid arm (under $1.00)

O/H **GO** ($0). A **GO** (whole-file DTO + fake-dispatch test first; prompt frozen + SHA). B **CONDITIONAL GO** (packaging decision B-hull vs B-max; deterministic merge + no-op gate + synthetic verify; dry-run SHAs frozen; aggregate spend wrapper). C **GO paired** (only if A usable and attribution passes 7/7 first). E **GO** (probes/key frozen; blind pack SHA).

**Order (fail-closed):** freeze → controls on O and H only ($0) → 7/7 gate → A₁ → C₁ → B₁ (after merge gate) → evaluation → replicate 2 only if no stop rule fired. **Hard stops:** aggregate + projection > $1.00; any control misclassified; any paid dispatch failing twice; any arm >2× band; any frozen module hash change.

## 6. Uncertainties (preserved)

Token estimates ±40%; haiku $0 is observed allowance not guarantee (halt-and-report on route failure, never silently escalate); B-hull may trip preservation/boundary checks (unknown until $0 dry run); merge step is new (no-op gate non-negotiable); A is one-shot (truncation = recorded result, not retry); blinding partial; probes uncalibrated; detector counts uncalibrated; H is Muse-authored with CONFLICTED identity (historical reference, not peer arm); single-chapter scope limits generalisation.

## Provenance

Costed design by background subagent (`opencode-go/deepseek-v4.1-flash`), $0, zero pipeline dispatches, read-only. Recorded with light coordinator trimming (prompt text abridged to its frozen-before-dispatch requirement; tables otherwise verbatim). Not executed; module-hash freeze values and fixture line numbers must be re-confirmed at execution time (dirty trees). H-identity CONFLICTED flag carried as a known caveat for the read-out.
