# H0 — Writer, Praxis, and ECK reuse

## Writer and ECK

Writer already owns substantial context and prompt construction, semantic inspection, task-specific verification, strategy/lesson stores, experiment and candidate selection, trace records, and Writer-specific policy learning. The ECK code under `packages/writer-ai/writer_ai/eck/` should remain Writer-owned where it depends on Writer data, schemas, or semantics. The Praxis ECK ownership reconciliation identifies a narrower importable `StrategyLibrary` and says `LearningPolicyEngine` depends on Writer tables; it explicitly blocks copying ECK into Praxis.

**Disposition:** consume stable read-only or versioned interfaces; do not reimplement Writer context compilation inside Worker. Do not claim generic cross-domain learning from Writer-specific ECK modules. Keep manuscript evaluation and editing authority in Writer/Workbench.

## Praxis

Praxis already has `praxis.harness.state.v1`, a bounded loop (`HarnessState`, `HarnessPolicy`, `ActionExecutor`), a Mission ActionSpec executor, frozen manifests, task/evidence fixtures, independent criteria evaluation, and `praxis.effectiveness-record.v1` with `retain`, `reject`, and `insufficient_evidence`. Its ownership record places cross-domain effectiveness comparisons and advisory decisions in Praxis, while Mission retains execution/governance and Writer ECK retains Writer-specific learning.

### Experimental evidence (preserve negative findings)

- **HARNESS-01:** demonstrated a bounded Mission ActionSpec loop; explicitly made no improvement claim and concluded it did not prove Praxis improves outcomes.
- **HARNESS-02:** one-task exploratory candidate advantage, but comparison abstained for insufficient sample size.
- **HARNESS-03:** no quality/acceptance advantage; both primary comparisons rejected; no promotion.
- **HARNESS-04:** no measurable quality or recovery advantage; authentic group underpowered; context ablation failed and cost more.
- **HARNESS-05:** equal fault-task scores; candidate fabricated recovery in both no-fault controls, failed independent recovery checks, and was slower. Report recommends retiring the generic recovery controller from the active path.

**Disposition:** reuse manifest, state/action/evidence contracts, comparison policy and abstention patterns. Do not reintroduce H05 recovery logic as an accepted feature. Existing reports are valuable prior experiment evidence, not a general proof that the harness helps.

## Source references

`C:\Projects\praxis\praxis\harness.py`; `harness_model.py`; `docs/reviews/PRAXIS-HARNESS-01..05-REPORT.md`; matching manifests; `docs/reviews/PRAXIS-ECK-OWNERSHIP.md`; `C:\Projects\writer\packages\writer-ai\writer_ai\eck\`; `C:\Projects\writer\docs/runtime/`.
