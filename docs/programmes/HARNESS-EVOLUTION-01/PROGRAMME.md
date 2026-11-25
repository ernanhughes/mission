# HARNESS-EVOLUTION-01 — Worker as a Programmable Harness

**Status:** H0/H1 accepted by owner; H2 bounded gate passed; H3 accepted for deterministic offline execution only after H3Q independent review; H4 conditionally accepted with evidence-verification limitations. H5+ remain unauthorized.
**Owner:** Mission Control (`C:\Projects\mission`)
**Date:** 2026-11-25

## Objective

Establish a coherent programmable harness by composing current capabilities, with Worker as the production execution-composition substrate and other systems retaining their specialized capability ownership. The harness is an architectural composition, not one repository containing every capability.

## Authority and boundaries

- Authorized: H0–H4 within their stated bounds; H4 permits up to six intentional model invocations total, bounded local/free execution, and focused implementation/testing/evidence.
- Not authorized: H5+, production strategy promotion, Mission integration, migrations/deployment, manuscript changes, commits, or pushes.
- Preserve all existing work. Mission Work Outcome and Praxis changes remain uncommitted WIP; do not overwrite or modify them for this slice.
- Mission Control retains governance, workflow coordination, and operational observation unless evidence supports a better boundary. Worker remains the execution-substrate candidate; Praxis/ECK, Pi, and Stephanie are investigated as existing assets.
- Logical ownership does not require moving code into the owning repository. Prefer established contracts and composition; do not create a second DTO ecosystem.

## Current conclusion

The central hypothesis is strongly supported: harness capabilities already exist across Worker, Mission, Praxis, Writer/ECK, Workbench, Remembering/Relate, AITest, and Stephanie. The largest gap is coherent cross-system run identity, policy provenance, and outcome lineage. Worker is a suitable execution substrate if it stays modular and does not absorb Mission's governance, Writer's domain context/evaluation, or Praxis's cross-domain effectiveness work.

The most important qualification is empirical: Praxis's HARNESS-01–05 work built a real bounded harness and experiment apparatus, but did not establish a general quality or recovery advantage. HARNESS-05 found a false recovery claim in a no-fault condition and recommended retiring that generic recovery controller. The next stage should make execution reproducible and measurable before adding adaptive behavior.

## Stages

| Stage | Status | Authority |
|---|---|---|
| H0 — Ecosystem capability and ownership discovery | Accepted | Complete |
| H1 — Research and external implementation investigation | Accepted | Complete |
| H2 — Architecture and harness contracts | Gate passed for deterministic offline lane | Complete for H3 scope |
| H3 — Reproducible execution baseline | Accepted — deterministic offline only | Current pinned baseline and N1-N3 negative scenarios; local model output failed task evaluation |
| H4 — Minimal programmable harness | Conditionally accepted | Three versioned Worker strategies, focused tests and one bounded local A/B/C comparison; final verifier/source provenance limitations remain |
| H5 — Adaptive policies and failure attribution | Pending | Not authorized |
| H6 — Mission Control integration | Pending | Not authorized |
| H7 — Stephanie improvement experiments | Pending | Not authorized |
| H8 — Independent comparative research | Pending | Not authorized |
| H9 — Book and capstone reconciliation | Pending | Not authorized |

H0 and H1 are owner-accepted. H2 passed the bounded offline implementation gate. H3Q independently accepted H3 for deterministic offline execution only. H4 now establishes a fixed strategy surface; the live Qwen outputs had the correct value but invalid fenced JSON. Independent review identified evidence status and linkage-verifier gaps; the verifier was hardened to fail closed, while the final edits and historical B/C bundles remain conditionally qualified. See [STAGE-LEDGER.md](STAGE-LEDGER.md), [H3Q-FINAL-ACCEPTANCE.md](H3Q-FINAL-ACCEPTANCE.md), and [H4-FINAL-REPORT.md](H4-FINAL-REPORT.md).

## Deliverables

H0/H1 evidence and H2 proposals are in the linked files in this directory. [H0-H1-FINAL-REPORT.md](H0-H1-FINAL-REPORT.md) is the research entry point. H3Q acceptance, resource controls, negative execution, live execution, independent review and H4 inputs are recorded in the H3Q reports. The original programme brief is preserved in the conversation attachment.
