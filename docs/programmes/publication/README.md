# Programme PUBLICATION

**Stage:** PUB-00 — Foundation, Discovery and Documentation (research and documentation only).
**Status:** PUB-00 executed 2026-11-24. Under review — no implementation authorized yet.
**Rule:** Ultimate success is a genuinely readable, technically faithful published book
(Jev first), not the existence of detectors, APIs, workflows or UIs.

## 1. Objective

~67 books are in pre-publication or development with substantial research, working
implementations and quality validation, yet manuscripts remain difficult to read and
unsuitable for publication. Existing research, technical, semantic and editorial quality
assessments do not detect this. PUBLICATION builds the distinct **Publication Quality**
domain answering: *is this manuscript ready to be read, understood and used by its
intended audience?*

End state: the author opens a book in Mission Control, sees publication defects, corrects
them through governed AI-assisted workflows, independently validates the result, and
publishes.

## 2. Scope

- **In scope:** publication-defect detection (cruft, unnecessary complexity, pedagogical
  and representational defects), repo↔manuscript evidence reconciliation, governed
  manuscript transformation, independent validation/calibration, Mission Control
  Publication section, end-to-end demonstration on the Book of Jev, portfolio reuse.
- **Out of scope for this programme:** research quality, technical correctness
  validation as such (consumed as evidence, owned elsewhere), fiction-continuity
  systems, marketing/distribution, new model-routing infrastructure.
- **PUB-00 boundary (this stage):** read-only inspection, safe diagnostics, existing
  tests where cheap, architecture, documentation, tracker init, cleanup. No feature
  implementation, no manuscript edits, no experiment reruns, no migrations, no deploys,
  no commits, no deletion of unrelated files. All held.

## 3. Architectural direction (proposed, to be validated per stage)

Build bottom-up: AI → Writer → Workbench/Worker → editing and manuscript
transformation → Mission Control → Publication. Prefer extending proven existing
capabilities over parallel implementations. Mission Control consumes authoritative
findings and workflow state from owning systems; it does not reimplement editorial
intelligence. See ARCHITECTURE.md.

## 4. Normative references

- [ARCHITECTURE.md](ARCHITECTURE.md) — boundaries, direction, ownership, contracts.
- [CAPABILITIES.md](CAPABILITIES.md) — verified existing capabilities, reuse and gaps.
- [ROADMAP.md](ROADMAP.md) — stable stage IDs (PUB-00…PUB-11), dependencies, gates.
- [STATE.md](STATE.md) — current state, blockers, exact next action.
- [ACCEPTANCE.md](ACCEPTANCE.md) — programme-wide and per-milestone evidence rules.
- [DECISIONS.md](DECISIONS.md) — material decisions and rationale.
- Prior art this programme inherits (do not duplicate): `docs/readability-assurance/`
  (ownership map, 10 ADRs, Stage-0 reconciliation, baseline health, pilot contracts,
  V2 addendum), `docs/milestones/`, `docs/MC-PUBLISH-02-ARCHITECTURE.md`
  (canonical identity and evidence freshness).

## 5. Stage lifecycle (mandatory for every implementation stage)

Research → Understand → Design → Implement → Test → Review → Document → Clean up →
Handover. Full gate definitions in ROADMAP.md; evidence rules in ACCEPTANCE.md.
Anti-cruft rule applies to our own repos: retain production code, regression tests,
fixtures, canonical docs, essential eval evidence and audit/provenance; remove
scratch scripts, duplicate reports, superseded plans and temp outputs.

Repeatable stage contract (every milestone, every agent — inherited by all
future stages; the stage is not done until all hold):

1. Read the canonical programme docs (`docs/programmes/publication/`, all files).
2. Consult the current capability catalog — never design from memory or stale data.
3. Research existing implementations before proposing anything.
4. Identify reuse before new functionality (extend the closest owner; new code
   only for the genuinely unowned slice).
5. Define acceptance before implementation (gates + evidence rules).
6. Implement only approved scope (no unrelated refactoring, no scope smuggling).
7. Execute focused tests for touched domains plus regression tests for neighbours.
8. Demonstrate callable behaviour live (facade/CLI/API — import alone is not done).
9. Update owning-domain docs where the implementation lives.
10. Update capability declarations where justified (catalog, manifests, DTOs).
11. Update programme state (`STATE.md` + the affected canonical docs).
12. Remove temp artifacts (scratch scripts, duplicate reports, temp outputs).
13. Hand over concisely: decision, changes, verification, risks, exact next action.
14. Stop at the review gate: no next stage starts on one agent's report alone —
    independent review (architecture + regression) is the gate, never optional.
15. Inherit the model allocation and cost policy (§6) in every stage prompt.

### 5.1 Test cost policy (mandatory)

- Routine stage verification runs **focused, short** suites for the touched
  domains plus immediate neighbours; never the whole Writer suite by default.
- Writer tests taking more than ~2 seconds wall-clock are marked
  `@pytest.mark.long` and excluded by `pytest.ini` by default. Do not run
  `long` tests in ordinary stage loops or add them to reviewer prompts unless
  the stage directly changes that corpus or a release gate requires it; record
  the deferral instead.
- `tests/runtime/test_capability_resolution.py::test_capability_resolution_corpus`
  takes ~2 minutes. It is a capability-resolution/release corpus, not a
  per-stage smoke test. The historical 156-second "mediated_read +
  evaluation_fabric + capability_resolution" block is almost entirely this one
  test; running the short parts separately takes a few seconds.
- A reviewer's time budget is evidence: if a suite is slow, split the short
  regression set from the long corpus and report which was deliberately not run.

## 6. Model allocation and cost policy (permanent, all milestones)

Preferred models (resolve exact identifiers through model discovery/routing;
prefer the covered provider route when equivalents exist):

- **Muse** (existing configuration): primary research, architecture,
  implementation, documentation.
- **DeepSeek** `deepseek-v4.1-flash-free`: testing, regression analysis,
  adversarial testing, routine independent verification.
- **DeepSeek fallback** `deepseek-v4.1-flash`: only when the free model is
  unavailable or its allocation is exhausted (record the reason).
- **Codex** `gpt-6-luna`: architectural review, code review, integration
  verification, acceptance review.
- **Claude** `claude-haiku-5-5`: where editorial, pedagogical or independent
  prose assessment is required.

Execution policy:

1. Prefer deterministic computation over model inference.
2. Prefer the cheapest model capable of completing the task reliably.
3. Use the free DeepSeek model for routine testing and regression.
4. Escalate only when the cheaper model demonstrably fails, abstains or
   produces insufficient evidence.
5. Use Codex at important architectural and implementation acceptance gates.
6. Use Claude when editorial judgment adds material value.
7. Avoid unnecessary duplicate reviews.
8. Record the actual model, provider, fallback reason, usage and cost where
   available.
9. Never silently substitute a more expensive model.
10. Preserve independent verification requirements regardless of cost.
