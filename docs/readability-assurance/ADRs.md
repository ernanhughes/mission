# ADRs — READABILITY-ASSURANCE-01

**Status:** PROPOSED — Stage 0 decisions, not implementation claims
**Date:** 2026-11-16
**Rule:** an ADR is accepted only when the named owner accepts the boundary.
Until then it is a recommendation, not a licence to code.

---

## ADR-001 — Writer `editing` remains the sole mechanical readability authority

**Status:** ACCEPTED (owner decision, 2026-11-16)
**Decision:** No new sentence/paragraph scorer. `runtime.editing` owns the six
independent subdimensions and its `writer-editing-report-v1` evidence. All
other systems consume it by reference.

**Evidence:**
- `runtime.editing` registered; facade exposes `audit_book`, `audit_all`,
  `summary`, `list_reports`, `get_report`, `report_status`, `compare`.
- Subdimensions: `paragraph_load`, `sentence_load`, `fragmentation`, `rhythm`,
  `lexical_accessibility`, `section_structure`.
- Reports are read-only; no composite score.

**Consequences:**
- Reader Assurance may not compute its own readability score.
- `ai.scoring.manuscript` and `reader_legibility` must be labelled as different
  measures, not merged into Editing.
- UI must show the source measure and report id.

**Blocked by:** none. This is the least controversial decision.

---

## ADR-002 — No new `reader_assurance` domain; extend Writer `quality` with `reader_study`

**Status:** ACCEPTED (owner decision, 2026-11-16)
**Decision:** Do not register `reader_assurance`. The controlled human-reader
study capability is added to Writer `quality` as a `reader_study` service. In
v1:

1. Keep `editing` for mechanical signals.
2. Use Writer `quality` for portable findings, finding campaigns **and human
   reader studies**.
3. Use `artifact/self_repair` for contracts and gates A–E.
4. Use `evaluation_fabric` for runtime-participant probes.
5. No new manuscript parser, contract, campaign scheduler or model gateway.

**Why:**
- Writer already has a `quality` domain (WRITER-QUALITY-01…07) with portable
  findings, deterministic/direct/bounded_judge strategies, campaigns,
  improvement requests, and 87 passing tests in the targeted suite.
- `evaluation_fabric` owns runtime participants, evidence packets and council
  synthesis; `eval` owns benchmark runs; `reader` and `readthrough` own other
  reader-adjacent lifecycles.
- The genuinely unowned slice (human consent, assignment, frozen questions,
  outcomes, calibration) is a service, not a domain.

**Consequences:**
- `quality` needs a supported public surface for `reader_study`. Registering
  `runtime.quality` is the preferred way; a CLI-only surface is acceptable
  only if Workbench and Mission can consume it safely.
- Human-study records reference `exp-contract-v1`; they do not copy it.
- No call to `ai.scoring` for human outcomes.

**Blocked by:** `quality` facade/registration design and privacy review.

---

## ADR-003 — No `ai.assessment`; migrate Mission's advisory lane to Writer quality

**Status:** ACCEPTED (owner decision, 2026-11-16)
**Decision:** Do not add a generic AI assessment package. `ai.scoring` is the
existing generic scoring runtime; it is not extended for this programme.
Mission will migrate its `manuscript-prose-v1` evaluations to Writer `quality`
reports. Writer semantics stay in Writer.

**Evidence:**
- `src/ai/scoring/` includes dynamic dimensions, scorer registry, heuristic,
  LLM-judge and embedding-pair scorers, fusion, profiles, persistence and
  training-row derivation.
- `ai.scoring.manuscript` is `manuscript-prose-v1`: clarity, argument,
  precision, economy, voice, structure (1–5; mean overall).
- Mission `/api/quality` invokes `ai.scoring.manuscript_cli`; `/api/technical`
  invokes `ai.scoring.tech_cli`.
- `ai.books` already reads Writer `.writer` evidence, so `ai` is not
  book-agnostic today.

**Consequences:**
- Mission's quality service becomes a read model over Writer quality/editing
  evidence; it must not launch `ai.scoring.manuscript_cli` for new manuscript
  evaluations.
- Existing Mission `QualityEvaluation` history is retained read-only and
  labelled as legacy advisory until a migration mapping is accepted.
- No new package and no silent dual scoring.
- The migration requires a Writer quality HTTP/bus surface; until that exists,
  the migration is blocked rather than faked.

**Blocked by:** Writer quality public facade/API; Mission migration mapping.

---

## ADR-004 — `exp-contract-v1` is the only explanation contract

**Status:** ACCEPTED (owner decision, 2026-11-16)
**Decision:** `exp-contract-v1` remains the canonical frozen requirements
document. `quality`'s `portable-v1` findings are a different artifact (review
findings), not a second contract. Reader Assurance references the contract; it
does not copy its fields into a new schema.

**Evidence:**
- `exp-contract-v1` has source revision, region/hash, objectives, hard/semantic
  obligations, question set, approval and content hash.
- Gates A–E consume it and re-verify its hash.
- 10 stored contracts in Inference; 1 APPROVED.

**Consequences:**
- New study fields (protocol id, participant consent, human outcomes) live in
  the study record, not in the contract.
- A study may reference only a contract approved for the current source hash.
- Extra questions may be stored as a study-specific validated set only if the
  contract's canonical set remains intact.

**Blocked by:** none.

---

## ADR-005 — Candidate application stays with Workbench; large regions are staged

**Status:** PROPOSED
**Decision:** Workbench's journaled Apply/Undo remains the only mutation path.
A candidate that requires multi-paragraph reordering is a staged, separately
authorized change set, not a bypass of the single-unit Apply. No Writer
campaign bulk-applies.

**Evidence:**
- Workbench routes: `/proposals/{pid}/accept`, `/undo`; `chapter_apply.py`
  implements atomic one-file apply with Git commit and recovery.
- Self-repair decisions (`/self-repair/decide`) do not mutate source.
- `book_campaign` and `quality.campaign` are candidate/evaluation orchestrators,
  not appliers.

**Consequences:**
- Region-size limits are a candidate-planning problem, not a reason to weaken
  Apply.
- A staged plan needs its own source hash, candidate ids and merge-preservation
  check.
- Undo is explicit, never automatic on a post-apply regression.

**Blocked by:** design of the staged change-set unit (not yet specified).

---

## ADR-006 — Human-reader evidence is a separate, consent-bound study

**Status:** ACCEPTED in principle (owner: Writer `quality`); privacy/retention
review pending
**Decision:** Human-reader studies are opt-in, data-minimized, and reported
separately from model probes. `NOT_RUN` remains visible. No AI-generated
testimony is labelled human evidence.

**Minimum record:**
- study id, protocol id/version, consent basis, retention rule
- assigned condition and exact source revision
- frozen question set/hash
- reader background (coarse, optional), objective correctness per question,
  error type, optional time/difficulty
- rater agreement and unresolved grading
- sample size, cohort split and descriptive limitations

**Consequences:**
- No claim of "readers understand better" without human data.
- Model Gate D remains a proxy and must say so.
- Do not collect identifiers or telemetry without a stated need.

**Blocked by:** D1 owner; privacy/retention review.

---

## ADR-007 — Mission extends the existing Writer review surface

**Status:** PROPOSED
**Decision:** Do not add a top-level Review page by assumption. Extend:
- the existing `/writer` cross-book review queue (Editing evidence, decisions,
  campaigns), and
- the existing ProjectPage quality tabs (Mission quality / Writer quality as
  separate labelled lanes).

Reuse the existing Workbench deep-link grammar. Mission never parses
manuscripts, rescores prose or applies changes.

**Evidence:**
- `frontend/src/app/App.tsx` has no `/review` route.
- `WriterPage.tsx` has a "Cross-book review queue" and campaign controls.
- `ProjectPage.tsx` has the `/api/quality/*` panels.
- Deep links are built in `writer/queue.py` as
  `/#chapter=<name>&menu=edt&drawer=editing&finding=<finding_id>`.

**Consequences:**
- If the author wants a distinct Review page later, that is a UI decision with
  its own ticket, not an implementation detail.
- Mission may launch only registered, approved integration actions; no arbitrary
  shell commands.
- Stale or unresolvable links must explain, not silently open another chapter.

**Blocked by:** D2 disposition; actual UI placement review.
