# WORK-OUTCOME-01 — Work Outcome Evaluation Programme

Status: W0 investigation complete, pending owner review (read-only, no app-code changes).
Date: 2026-11-24
Recommendation: CONDITIONAL GO (see §W1 entry in W0-IMPLEMENTATION-PLAN.md).
Owner: Mission Control (`C:\Projects\mission`)

## Objective

Determine, for any coherent piece of work:

- What was requested?
- What was actually done?
- What changed in source?
- Was it completed, correct, independently verified, usable?
- What remains unfinished?

AI claims ("implementation complete, all tests passed") are inputs, not evidence.

## Stages

| Stage | Objective | Status | Evidence |
| ----- | --------- | ------ | -------- |
| W0 | Architecture and discovery | Conditionally accepted 2026-11-24 | 12 docs |
| W1 | Source observation | Conditionally accepted 2026-11-24 | W1-FINAL-REPORT |
| W2 | Work Episode reconstruction | CONDITIONAL ACCEPTANCE 2026-11-24; corrections re-reviewed CLOSED | W2-FINAL-REPORT |
| W3 | Semantic triage and requirement extraction | CONDITIONAL ACCEPTANCE 2026-11-24 | W3-FINAL-REPORT |
| W4 | Work Outcome Evaluation | CONDITIONAL ACCEPTANCE 2026-11-24; 8 review fixes landed, re-verification running | W4-FINAL-REPORT |
| W5 | Activity interface | CONDITIONAL ACCEPTANCE 2026-11-24 | W5-FINAL-REPORT |
| W5A | Operational activation (ai pilot) | CONDITIONAL ACCEPTANCE 2026-11-24 | W5A-FINAL-REPORT |
| W6 | Incremental evaluation + gap reconciliation | CONDITIONAL ACCEPTANCE 2026-11-24 (W6A–W6E gated; unattended operation NOT accepted) | W6-FINAL-REPORT |
| W7 | Follow-up work integration | CONDITIONAL ACCEPTANCE 2026-11-24 (unattended semantic eval + scheduler stay disabled) | W7-FINAL-REPORT |
| W7A | Corrective interface activation | Authorized; live on operational :8790 (proposal + confirmation demonstrated, zero console errors) | W8A-W7-OPERATIONAL-ACTIVATION |
| W8 | Prospective work instrumentation | CONDITIONAL ACCEPTANCE 2026-11-25 (W8A–F gated; scheduler + paid inference stay disabled) | W8-FINAL-REPORT |
| W9 | Qualification + controlled rollout | CONDITIONAL ACCEPTANCE 2026-11-25; closure recommended (2 assurance criteria open) | W9-FINAL-REPORT |

Pilot: `ai` project (`C:\Projects\ai`) only until W9.

## Acceptance gates

W0 is complete only when all items in the W0 brief §15 hold:
actual schemas inspected, reuse identified, ownership justified,
correlation limits explicit, completion semantics defined,
reported-vs-verified distinguished, bounded pilot examined,
incremental architecture designed, Activity integration specified,
security/cost documented, staged plan independently reviewable.

W1 entry requires: GO or CONDITIONAL GO recommendation, explicit
pre-W1 actions closed, no schema writes performed during W0.

## Documents (this directory)

1. `WORK-OUTCOME-01-PROGRAMME.md` (this file)
2. `W0-ECOSYSTEM-INVENTORY.md`
3. `W0-OPENCODE-DATABASE-REPORT.md`
4. `W0-EXISTING-ACTIVITY-ARCHITECTURE.md`
5. `W0-WORK-EPISODE-CONTRACT.md`
6. `W0-CORRELATION-DESIGN.md`
7. `W0-EVALUATION-RUBRIC.md`
8. `W0-OBLIGATION-LIFECYCLE.md`
9. `W0-PERSISTENCE-AND-SECURITY.md`
10. `W0-UI-DESIGN.md`
11. `W0-AI-PROJECT-PILOT.md`
12. `W0-IMPLEMENTATION-PLAN.md`

## Blockers / risks (live)

- OpenCode DB location + schema: pending verification (track 2).
- Ecosystem reuse inventory: pending verification (track 3).
- No `episode` storage exists today; new tables required in W1/W2 (see persistence report).
- No task/programme/commit join today; correlation must be inferred until harness emits explicit IDs (see correlation design).
- `.workbench` excluded from Git index by default; episode runner outputs may be invisible unless allow-listed.
- Test/workbench evidence unlinked from commits; join design required, no duplication of engines.

## Decisions log

- 2026-11-24: W0 is design-only. No app-code edits, migrations, UI builds, commits, pushes, or bulk historical AI analysis.
- 2026-11-24: PostgreSQL `mc` is the proposed store for derived episode records. OpenCode DB stays read-only source. No duplication of full conversation history.
- 2026-11-24: W1 CONDITIONAL ACCEPTANCE. Observation foundation implemented,
  tested (41 focused + neighbours green), piloted live (ai-scoped, scratch PG),
  zero model calls. No W2+ work. Pre-existing publication modifications preserved.
  Operational `mc` untouched (041 auto-applies on next start).
- 2026-11-24: W2 CONDITIONAL ACCEPTANCE. Deterministic reconstruction over W1
  foundation: 30 episodes/280 links from 147 ai sessions, 7/7 fixtures PASS,
  74 focused tests green, zero model cost. No W3+ work. Independent review
  carried as open obligation with runnable external commission.
- 2026-11-24: W3 CONDITIONAL ACCEPTANCE. Deterministic triage (90/26/21/10)
  validated by full-bucket audit; semantic pilot 19/20 calls at $0 (pipeline
  proven, 0.5b quality insufficient — vacuity filter enforced, echo outputs
  quarantined). 106 focused tests green. No W4+ work. Operational DBs
  untouched. Cross-family review carried.
- 2026-11-24: W4 CONDITIONAL ACCEPTANCE. Evaluation engine (deterministic
  verification + gated mistral-small semantic layer, validated, budgeted):
  6-episode pilot, 1 complete packet (AI-CORE-05: incomplete/poor, actionable
  findings), 0 false completions, 24/30 calls at $0. Migration 044+045
  (digests via follow-up delta after discovering operational v44). 180 focused
  tests green. No W5+ work. Operational DB advanced to v44 by backend startup
  (not this commission); 045 applies next start.
- 2026-11-24: W5 CONDITIONAL ACCEPTANCE. Work Evaluation tab in Activity
  (5 views, real pilot data, zero-POST UI, 9 feature tests + full frontend
  suite green, production build ok, 5 views screenshotted with zero console
  errors). No W6+ work. Operational DBs untouched. Independent review
  findings fixed in code; cross-family review carried.
- 2026-11-24: W5A CONDITIONAL ACCEPTANCE (operational). Backup + verified
  restore, 041–045 applied via runner (045 new; co-applied 046 aitest
  recorded additive/untouched), operational backfill (151 sessions → 31
  episodes → 26 objectives, 1267 claims, 278 findings), interface
  demonstrated on live data with zero console errors, 2 findings
  investigated and actionable. No restarts/commits/pushes. Reviews
  carried with conditional labelling.
- 2026-11-24: W6 CONDITIONAL ACCEPTANCE (W6A–W6E gated; unattended
  operation NOT accepted). 9 requirements recovered with provenance;
  w6b-v1 severity (217 majors → minor); 24 groups / 288 members;
  5 §21 closures; auto-link bare-SHA + recon cross-scope defects found
  and fixed; staleness + manual controls; $0 spend. Timer NOT started.
- 2026-11-24: W7 authorized (corrective work integration only).
  Scheduler stays disabled; unattended semantic evaluation stays
  disabled; no auto-execution/confirm/close; no W8/W9.
- 2026-11-25: W8 CONDITIONAL ACCEPTANCE. Envelope v1 (671 bytes,
  digest-bound, metadata only), link resolution or rejection,
  prospective pilot 3/3 reported → partial, retro comparison (n=1).
  Two incidents disclosed and handled: diagnostic script wrote 3
  fixture rows to operational mc (removed, counts restored) and
  JSON-over-TEXT returned strings on PG (envelope path hardened).
  No new infra; $0.
- 2026-11-25: W9 CONDITIONAL ACCEPTANCE, closure recommended.
  Fail-closed DB targeting (target= required for PG), SafeJSON
  boundary for all Wo* columns, policy ladder over existing settings
  (only `ai` enabled), cross-family review obtained (Mistral,
  CONDITIONAL; closure finding fixed), AITest receipt bound, worker
  dry-run propagation proven, programme self-evaluation returned
  `incomplete` naming the same three gaps as the human reviewer.
  Open: independent verified-complete episode, human cross-family
  commission, Wave 1 activation. No timer, no paid inference, no
  commit/push.
