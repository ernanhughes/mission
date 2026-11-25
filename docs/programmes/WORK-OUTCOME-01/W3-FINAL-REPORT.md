# W3-FINAL-REPORT — Intent extraction CONDITIONAL ACCEPTANCE

## Verdict: CONDITIONAL ACCEPTANCE

W3 built exactly what was authorized: deterministic triage + intent domain +
validation-gated extraction + bounded pilot. No W4 judgements, no W5 UI, no
ecosystem analysis, no budget breach (19/20 calls, $0.00), no operational
writes, no commits/pushes/deploys, nothing staged.

## Acceptance (§25)

- [x] W1/W2 review addressed (focused re-review CLOSED all 5 + 2 new minors
      fixed; cross-family review carried with commission).
- [x] Governed invocation demonstrated (loopback Ollama, synthetic probe,
      usage receipts, loopback refusal tested).
- [x] Migration obligations reconciled (041/042 validated; 043 simulated
      pre-existing v42 → `[43]`, rows intact, re-run `[]`).
- [x] Coverage denominators established (147/6,390; 94.6% message coverage;
      exclusions reported, none silent).
- [x] Substantive vs noise distinguished (90/26/21/10 + full-bucket audit).
- [x] Objectives extracted with provenance (26 inferred, task episodes only).
- [x] Atomic requirements carry authority (schema + validator; model
      requirements quarantined by vacuity filter — quality reported, not hidden).
- [x] Restrictions/gates recorded as requirement kinds (schema `constraint`/
      `gate`; deterministic abstention documented).
- [x] Claims distinct from verified results (1,202 rows, all CLAIMED-class).
- [x] Candidate evidence bound (W2 links carried; 24 SHA-bearing claims).
- [x] Uncertainty/abstention supported (AMBIGUOUS, UNKNOWN, NEEDS_SEMANTIC,
      INSUFFICIENT_EVIDENCE paths tested).
- [x] Bounded real-source pilot executed (17 model calls + deterministic
      full-scope run).
- [x] Spend within limits ($0.00 / $1.00; 19 / 20 calls; ledger complete).
- [x] Persistence + replay validated (043 additive; cache idempotence tested).
- [~] Review findings reported; cross-family review outstanding (carried).
- [x] No outcome judgements implemented (no completion/quality columns exist).

## What changed

New: `work_observation/{triage,extract,extract_schemas,ollama_backend}.py`,
`api/work_intent.py` (8 routes), migration `043_*`, `test_work_{triage,extract}.py`
(28 tests), 13 W3 docs. Modified: `models.py` (6 tables), `main.py`,
`reconstruct.py` (review fixes), `episodes.py` (retirement/audit fixes),
`service.py` (parts count), `opencode_adapter.py` (stage/programme patterns),
migrations test (043), W1/W2 amendment notes.

## W4 entry requirements

1. Cross-family independent review of W1–W3 (or recorded exception).
2. Assert 041–043 on pre-existing PG at next authorized backend start.
3. Stronger local model (or human-supervised drafting) for requirements —
   0.5b Echo class quarantined; do not feed quarantined rows to W4.
4. Qualifier detection for claims (partial/conditional language).
5. Full-backend regression before shared-path changes.
6. Decide unresolved-bucket surfacing (W5 input).
