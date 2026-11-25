# W3-INDEPENDENT-REVIEW — Focused self-check; external commission open

Status: implementer self-check completed; cross-family independent review
still open (carried, not waived). The separate-agent re-review closed W1/W2
findings (W3-W1-W2-INDEPENDENT-REVIEW); this note covers new W3 surface.

## Self-check (10 points, code + tests)

1. Triage correctness: 90-trivial stratification independently re-read;
   no tool/task/sha/file sessions in the bucket (verified by query).
2. No false exclusions: probe patterns + zero-signal requirement jointly
   necessary; correction-with-execution can never match (tested).
3. Requirement authority: unsupported authorities rejected (tested);
   `accepted_proposal` requires evidence (validator enforces sources;
   acceptance-evidence check is a stated W4 gap, not claimed).
4. Source validation: unknown session refs rejected (tested); fabricated
   structure rejected (tested).
5. Claim/evidence binding: candidates only, method/confidence carried
   (no W4 judgement fields exist).
6. Cache correctness: identical inputs → `cached`, zero new calls (tested).
7. Budget enforcement: caps checked pre-call (tested); ledger records all
   attempts incl. provider failures and rejections.
8. Prompt-injection containment: untrusted content is quoted evidence;
   outputs matching tool/exec directives have no execution path (no shell,
   no repo writes in the extraction path — verified by grep).
9. Privacy: excerpts ≤800 chars redacted; no bodies in PG; fixtures
   synthetic; no secrets in prompts (synthetic probe contained none).
10. Test honesty: negative controls assert absence; pilot quality failures
    reported as failures (instruction echo quarantined by new filter).

## Disagreements / outstanding

- Requirement quality at 0.5b is insufficient (reported, not softened).
- Model triage discrimination is weak (unanimous classes; reported).
- Qualifier detection (`qualified` flag) unimplemented — deterministic gap.
- Cross-family review of W1–W3 still outstanding: external commission in
  W2-INDEPENDENT-REVIEW extended to cover `extract.py`, `triage.py`,
  `ollama_backend.py`, `api/work_intent.py`, migration 043, and this pilot.
