# W9-FINAL-REPORT — Qualification, rollout, programme closure

## Verdict: CONDITIONAL ACCEPTANCE, with programme closure recommended

The programme has delivered what it set out to deliver:
Mission Control can now tell you **what was intended, what was
actually achieved, how good the result was, and what remains to be
done** — with evidence, and without inventing certainty.

Two acceptance criteria remain genuinely unsupported (see §31
mapping). Neither is a capability gap; both are *assurance* gaps.
Unconditional acceptance is therefore not claimed, and a precisely
bounded closure commission is named at the end instead of another
programme stage.

## Sub-stage verdicts

- **W9A assurance + safety: CONDITIONAL ACCEPTANCE.** Cross-family
  review obtained (Mistral, CONDITIONAL, no critical findings) with
  its limitation stated; its closure finding fixed in code. DB
  targeting is fail-closed **at the ORM boundary** (`target=` required
  for PostgreSQL, credentials never echoed, negative controls tested) —
  the W8 accident is structurally impossible on the application path;
  raw `psycopg` call sites are enumerated as outside the gate. JSON/TEXT
  serialization normalized at one shared boundary for all Wo* columns,
  PG-verified, with coercion now logged. Migration governance procedure
  adopted and exercised three times during the stage (052–054 attributed
  to other workstreams, recorded, counts unchanged).
- **W9B live propagation: CONDITIONAL ACCEPTANCE.** Worker reachable
  and dry-run proven (request accepted, job ledger, project identity
  echoed); no real model execution (opencode CLI absent — precise
  blocker). Workbench blocked and documented. AITest live: receipt
  `exe_9054fcca10044918` bound at project level. Manual handoff remains
  the demonstrated path.
- **W9C verified-complete episode: NOT ESTABLISHED (honest).** Pilot
  re-run + independent re-execution agree on all three facts;
  verdict stays `partial`. The blocker is the rubric's verified lane
  being mechanical-existence only — widening it would weaken
  completion semantics, so it was not done. Correct withholding is
  demonstrated (calibration corpus, 05 partial, 29 unknown).
- **W9D coverage + calibration: ACCEPTED.** Denominator-honest census
  (151 sessions, 31 episodes, 3 with requirements, 0 complete).
  17-case hand-annotated corpus pins both directions. Model
  capability recorded per job; semantic stays assisted-only.
- **W9E rollout + policies: ACCEPTED.** Six levels over existing
  settings storage, fail-closed, human-only changes, enforced on the
  scheduled *and* manual paths; only `ai` enabled
  (`manual_evaluation`); Wave 1 prepared not activated. Scheduler
  qualified but **left off**.
- **W9F acceptance + closure: CONDITIONAL ACCEPTANCE.** Live product
  verified on :8790 with zero console errors. Self-evaluation graded
  the programme `incomplete` and named the same three gaps the human
  reviewer named.

## §31 acceptance criteria — final mapping

| Criterion | Status |
| --------- | ------ |
| Work observed safely | MET (read-only, tested) |
| Episodes reconstructed | MET (31) |
| Objectives/requirements traceable | MET (authority + digest + version) |
| Prospective registration | MET (envelope, digest-bound) |
| Execution evidence associated | MET (links + receipts; live worker dry-run) |
| Mechanical vs semantic boundaries | MET (two paths, budget gates) |
| Success recognized | MET (08C closure, 05 reported) |
| Unfinished work identified | MET (287 open, 24 groups) |
| Missing evidence ≠ poor implementation | MET (severity policy + calibration) |
| Findings proportionate/actionable | MET |
| Commissions retain scope | MET (version + scope hash) |
| Execution authorized | MET (human + confirm) |
| Closure evidence-bound | MET (human + citation) |
| **≥1 episode independently verified complete** | **NOT MET** |
| Operational DB safety | MET (fail-closed targeting) |
| **Cross-family assurance complete** | **PARTIAL** (different-family review done; human commission open) |
| **Controlled multi-project operation** | **NOT MET** (Wave 1 prepared, not enabled) |
| Live product useful | MET (subjectively, by demonstration) |

## Actuals

- Operational URL: `http://127.0.0.1:8790` (operator-owned; serves W9 tree).
- Operational schema: **v54** (050/051 work-outcome; 052–054 AITEST/
  Inspect, attributed under the governance procedure, additive, not
  approved by this programme).
- Enabled policies: `ai` → `manual_evaluation`; every other project
  `disabled` (0 explicit overrides stored — all defaults).
- Scheduler: **OFF** (mechanism qualified; no timer in code).
- Verified-complete episodes: **0** (partial: 1; unknown: 29).
- Provider spend: **$0.00**. Local model calls: 1 cross-family review.
- Tests: 218 focused backend, 184 frontend across 32 files, tsc +
  build clean.
- Repo: 75+ changed entries, nothing committed or pushed.
- Operational data unchanged by W9: 31 episodes, 9 requirements,
  293 findings, 1 proposal, 0 envelopes, 81 projects, 12,779 commits,
  zero stray test rows (verified).
- Independent review: 10 findings — 9 fixed with tests, 1 accepted and
  documented (`target=` is an intent marker, not authorization).

## Explicitly deferred (not gaps)

Scheduled observation activation; Wave 1–4 enablement; unattended
semantic evaluation; semantic commission drafting; worker/workbench
live execution; automatic corrective execution; paid inference;
ecosystem backfill.

## Precise bounded closure commission (instead of a W10)

Three items, each with an existing mechanism — none is new
development:

1. **Episode-level verified completion (≤1 day).** Pick the 08C pilot;
   commission a genuine independent review of its acceptance criteria
   under the existing review contract; if the reviewer accepts, either
   (a) record the review as `review` evidence and let the rubric
   produce its verdict, or (b) amend the rubric to admit reviewed
   relational facts into the verified lane — an explicit policy
   decision with its own approval, not a code tweak.
2. **Cross-family human sign-off (≤1 hour).** Invoke the existing
   DeepSeek commission (`W2-INDEPENDENT-REVIEW.md` text) against the
   W1–W8 tree; reconcile findings into the assurance ledger.
3. **Wave 1 activation (≤1 hour).** Set `mission` to `manual_evaluation`,
   run one bounded pass, review the findings, then decide on
   `worker`/`workbench`.

Completion of (1) and (2) satisfies the last two mandatory criteria.
Until then, unattended semantic operation stays prohibited — which is
the safe default, not a limitation of the product.

## Recommendation

**Close WORK-OUTCOME-01 as a delivery programme** and transition to
ordinary maintenance. The remaining work is assurance and enablement,
not architecture. The programme's own evaluation of itself —
`incomplete`, with 11 criteria reported and 3 gaps named — is the
most accurate summary available, and it is available from the product.
