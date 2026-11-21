# Architecture decisions — R2 + 02C

1. **Two-arm H1, no C.** Only one genuine eligible experience item exists;
   manufacturing a control would corrupt the experiment. H2 stays explicitly
   untested. (Manifest rev 1→2: binding-hash transcription fix only.)
2. **Complete-pipeline comparison, not pure experience effect.** The review
   stage provably receives no experience (constructor injection only into
   `*_improve`); pinning one review across runs was rejected as invasive.
   Claim matches design; both review identities recorded.
3. **Scoped 90s provider timeout, unchanged 120s Pi deadline, no retry.**
   No global change, no code change. Hard-stop on incomplete arms.
4. **No new model operation for mediation.** Reused the bound conversation
   path (avoids a second Phase-A dispatch-binding failure). All novelty is
   deterministic (resolve → obligate → validate → retain).
5. **Chapter-ch07 record schema reused verbatim** (concepts, claims,
   relations, qualifiers, sequence, evidence, spans) — no new ontology.
6. **Citation grounding split (passage vs chapter).** Genuine chapter quotes
   outside the passage window are surfaced as context with attention, not
   refused; fabrication (neither) still refuses; zero grounding is attention.
7. **Compactness bounds from the 1,536-token conversation ceiling.**
   Truncation fails closed (attention + raw retained). Two-call
   record-then-render deferred to a later commission.
8. **Pi runtime: repo-pinned 1.4.0 via lockfile.** Environment's 1.5.0
   vanished; unsatisfiable committed sha-pin skipped process-scoped with
   version enforcement + per-receipt digests. Re-pin is future ALIVE work.
9. **Inconclusive recorded, not repaired.** B's truncation is a capacity
   event with correctly admitted context; one event cannot attribute output
   length to experience. No rerun per frozen rules.
10. **Fixture path always labelled** (`fixture-deterministic-v1`,
    verification attention, UI badge); the UI never sends the flag.
