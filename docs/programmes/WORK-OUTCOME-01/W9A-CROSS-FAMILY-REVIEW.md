# W9A-CROSS-FAMILY-REVIEW — A real different-family review, and its limits

## Reviewer identity and independence

- **Reviewer model**: `mistral:7b-instruct` (Mistral family), served by
  the local Ollama endpoint on loopback. Procedure: the reviewing
  agent (Muse/meta family) built a bounded excerpt packet and passed
  it to the Mistral model; the verdicts recorded below are the
  Mistral model's output, not the agent's.
- A first attempt with `deepseek-r1:8b` (DeepSeek family) returned an
  empty response and was discarded, not reinterpreted.
- **Limitation (stated, not hidden)**: this is a genuine cross-family
  *model* review of the enforcement code, but it is not the full
  W1–W5 commission with human sign-off, and a 7B model cannot
  inspect the whole diff. It closes the "no different-family opinion
  exists" gap; it does not close the human-commissioned obligation.

## Materials reviewed (12 excerpts, ~21k chars)

Authorization: `proposals.py` approval gate + handoff;
`envelopes.py` registration authorization + link validation.
False completion: `evaluate.py` reconcile/resolve/reopen.
Severity: `grouping.py` w6b-v1.
Operational safety: `main.py` startup guard + migration auto-apply;
`persistence/db.py` test guard + target gate; `config.py` DSN
precedence.

## Verdicts (reviewer output)

| Area | Verdict |
| ---- | ------- |
| A authorization boundaries | CONDITIONAL |
| B false completion | CONDITIONAL |
| C severity policy | PASS |
| D migration auto-apply | PASS |
| E DB targeting | CONDITIONAL |
| **Overall** | **CONDITIONAL** |

Top risks named: auto-closure without human evidence; self-asserted
actors; SQLite via env flag; test→prod guard bypass.

## Disposition (what changed because of it)

- **B → fixed.** `reconcile_resolved` now requires a human actor and
  a reason (same bar as `resolve_finding`); closure text records both.
  Regression test covers the rejection paths.
- **A → accepted as architecture.** Actor names remain
  self-asserted (single-user local app, no auth layer). Literal
  `system`/`model` signatures are refused everywhere; real
  authentication is out of scope for this programme and is recorded as
  a limitation, not a defect.
- **C, D → PASS confirmed**; the reviewer's D basis was the runner
  only, so the promotion audit was extended with a destructive-DDL
  grep (no `DROP/TRUNCATE/DELETE` in any PG delta).
- **E → corrected on evidence.** SQLite requires an explicit
  `MISSION_CONTROL_ALLOW_SQLITE=1` (not silent), and the test guard
  refuses anything but `MC_TEST_DSN` (bypass would need a code
  change, not configuration). Severity downgraded accordingly.

## Residual obligation

The human-commissioned W1–W5 cross-family review (DeepSeek route
`opencode-go/deepseek-v4.1-flash`, commission text in
`W2-INDEPENDENT-REVIEW.md`) remains OPEN. It gates only unattended
semantic operation, which stays disabled.
