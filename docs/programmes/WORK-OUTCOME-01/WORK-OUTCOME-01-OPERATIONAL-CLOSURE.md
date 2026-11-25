# WORK-OUTCOME-01-OPERATIONAL-CLOSURE — Bounded closure commission results

Date: 2026-11-25. Owner authorization: execute items (1)(2)(3), produce this
record, re-run self-evaluation, report three obligations separately.
Constraints honoured throughout: no W10, no commits/pushes, no operator
backend restart, no paid inference ($0), no unattended semantic, no automatic
corrective execution, publication work preserved.

## 1. Independent cross-family review — BLOCKED (attempted, honestly recorded)

- Commissioned: `opencode/deepseek-v4.1-flash-free` via `pi` (tools/skills/
  context/session disabled), bounded packet `W9G-PACKET.md` (8,857 chars,
  sha256 `D3CC77B6…B629B7D606`) covering W1–W9 assurance, verified-lane
  amendment proposal, 08C pilot, Wave 1 readiness.
- Result: NO MODEL OUTPUT. Attempt 1 + one same-model retry both failed
  `429 FreeUsageLimitError` (verbatim in `W9G-DEEPSEEK-REVIEW-RAW.md`,
  2026-11-25T13:12Z). No paid fallback tried (explicitly forbidden). Cost $0.
- Disposition: 0 findings (0 critical/major/minor); nothing to fix or accept.
  W9A Mistral disposition stands unchanged (neither confirmed nor reopened).
- Files (uncommitted): `W9G-PACKET.md`, `W9G-DEEPSEEK-REVIEW-RAW.md`,
  `W9G-DEEPSEEK-REVIEW.md` (verdict table all NOT REVIEWED, residual
  obligations listed).
- Obligation status: **PARTIAL** (different-family Mistral CONDITIONAL done;
  DeepSeek-family + human commission OPEN; gates unattended semantic only,
  which stays disabled).

## 2. 08C pilot — VERIFIED-COMPLETE on isolated scratch (w4-v2, narrow amendment)

- Reproductions (read-only git, `C:\Projects\ai`):
  - W8E original + W9C separate-agent re-run (byte-identical, recorded).
  - Third independent re-run 2026-11-25: `merge-base --is-ancestor 88b7c04
    origin/main` exit 0; `branch -r --contains 88b7c04` → `origin/main`,
    `origin/HEAD`; `remote.origin.url` exact
    `https://github.com/ernanhughes/ai.git`; full
    `88b7c04f38e52374dba41494d88540a9f7d23f1e AI-CORE-08C…`; `de28820`
    ancestor exit 0. Canonical digest
    `sha256:6cc6e4d7c38d51c739bcd6d77e031b563f24916f88c163662fbc765176ff`.
- Authorized amendment (owner: "independently reproduced Git relationships
  are legitimate verification evidence when bound to the correct repository,
  revision and requirement"): rubric `w4-v1` → `w4-v2`
  (`backend/mission_control/work_observation/verify.py`).
  - New `relational` lane: `satisfied_verified` ONLY when a resolved
    `git_commit` AND a resolved `remote_ref` bind the SAME sha
    (prefix-tolerant, case-insensitive, `_bound_git_remote`); citation
    without binding stays `satisfied_reported`; `functional`/`existence`
    rules unchanged (no weakening — `functional` + git + remote still
    reports; unbound sha still reports; ambiguous never upgrades).
  - `evaluate.py` `_validate_eval`: relational verified requires bound
    `git_commit` + `remote_ref`; non-relational keeps pre-v2 rule
    (`remote_ref` alone never verifies).
  - 4 new regression tests in `backend/tests/test_work_evaluate.py`
    (bound verifies / git-only reports / unbound reports / functional
    stays reported).
- Demonstration (isolated SQLite scratch, `MC_DSN` removed, no operational
  writes): episode `ep:task:W8-PILOT-VERIFY-08C-V2`, 3 × `relational` /
  `explicit_user` / mandatory requirements (merge-base / branch -r / remote
  URL), association `git-ai-08c:88b7c04f38e…`, bound `git_commit` +
  `remote_ref` links → `evaluate_episode(semantic=False)`:
  **STATUS completed, COMPLETION complete**,
  `rq1/rq2/rq3 = satisfied_verified` ("relational git fact independently
  reproduced and bound to repo+revision").
- Operational note: the pilot has NO rows on operational mc (by design,
  W8E). Promoting the verified record to live waits for the operator
  restart (new code) + explicit enablement — NOT done here (no backend
  restart, no operational writes). The mechanism is proven; the live
  promotion is a defined operator step.
- Obligation status: **MET on scratch** (first verified-complete episode;
  independent reproductions ×3 + bound refs + deterministic evaluation →
  complete). Live promotion pending restart — reported as such, not claimed.

## 3. Wave 1 activation — PREPARED, blocked pending operator restart

- Backend version verification:
  - No process listens on 127.0.0.1:8790 (probed 2026-11-25; `northbound`
    refused). Running version therefore CANNOT be verified — restart required.
  - Tree contains all W9 review fixes (verified in working tree):
    `continuous._gated` fail-closed semantic + `policy_unscoped` receipt;
    `require_scope_allowed` on all four manual endpoints; `w4-v2` above.
  - Frontend `dist/index.html` (2026-11-25 08:18) is newer than all
    `work-evaluation` sources (07:37); no frontend changes since — rebuild
    NOT required unless the operator edits frontend.
  - Operational store intact (read-only, `target='server:read-only-*'`):
    migrations v54…45 present (latest 54); `wo_episodes` 31,
    `wo_requirements` 9, `wo_findings` 293, `wo_policy:*` 0 rows (all
    defaults; `ai → manual_evaluation`); projects 81 incl. `mission`,
    `worker`, `workbench`, `ai`. No test rows, no pilot rows on live.
- Scoping (live repo activity, last 30 days, read-only git):
  `mission` 99 commits, `worker` 8 (latest 2026-11-24), `workbench` 8
  (latest 2026-11-25). Real Wave 1 workload exists.
- Worker/Workbench probes: `:7317` refused (down, as designed — starts on
  demand for dry-run); `:7420` reachable; `:7422` refused. W9B posture
  unchanged: worker dry-run proven, live execution needs opencode CLI +
  paid authorization (neither sought); workbench unconfigured + owner-gated.
  No services started or reconfigured here.
- Exact operator restart + enablement (operator action ONLY):
  1. Preflight (already done, re-confirm): `git status` shows only
     publication/pub08 changes; `frontend/dist` fresh; backup operational
     PG (`mc`, v54) per `W5A-BACKUP-AND-MIGRATION`.
  2. Restart (picks up W9 fixes + w4-v2; no rebuild needed):
     `C:\Projects\mission\mission.cmd` (or `mission --no-browser`), which
     runs `scripts/start.ps1 -Port 8790`. Do NOT use `--rebuild` unless
     frontend sources changed. Verify `http://127.0.0.1:8790/api/health`
     reports `database ok`, `schema_version 54`.
  3. Verify corrected gates live: `GET /api/work-evaluation/policies`
     (defaults; `ai → manual_evaluation`); `GET
     /api/work-evaluation/policies/gate/evaluate_manual?project_key=mission`
     → allowed false (disabled default — correct fail-closed);
     `POST /api/work-observation/runs {"project_contains":"unknown-xyz"}`
     → 403 naming capability.
  4. Enable Wave 1 in order, one project at a time (human actor!):
     `POST /api/work-evaluation/policies {"project_key":"mission",
     "level":"manual_evaluation","actor":"<your name>","lookback_days":30}`
     then bounded pass `POST /api/work-observation/runs
     {"project_contains":"mission"}`; review findings + coverage in
     Activity → Work Evaluation before touching `worker`/`workbench`.
     `worker`/`workbench` same payload only after `mission` qualifies and
     their routes are proven (`worker` dry-run → executor; `workbench`
     workflow env + owner session).
  5. Scheduler stays OFF (no timer in code); semantic stays assisted-only
     (`manual_evaluation` permits on-demand semantic; scheduled semantic
     requires `continuous_semantic` + global auto flag + budget — all off).
- Obligation status: **NOT MET** (Wave 1 prepared, not enabled; backend
  down so live qualification impossible here; all preconditions + payloads
  ready, no silent enablement performed).

## 4b. Operational activation results (2026-11-25, backend operator-started)

Operator started Mission Control (PID 37200, 13:09 UTC — BEFORE the w4-v2
commit 2a7d22c at 13:32 UTC). Health `ok`, `database ok`, `schema_version
54`, `model_enabled false`. All API probes below by the local AI; no
operator-process restart performed by this commission.

- Gate verification (W9 fixes confirmed RUNNING): `GET
  policies/gate/evaluate_manual?project_key=unknown-xyz-probe` →
  `disabled/allowed:false`; `GET ...?project_key=mission` (pre-enable) →
  `disabled/allowed:false`; `POST /api/work-observation/runs
  {"project_contains":"unknown-xyz-probe"}` → **403** (F3 fix live);
  cost endpoint `model_calls 0, model_cost_usd 0`; settings contain no
  `%auto_enabled%` keys (scheduler stays OFF); single historical
  `wo_observation_runs` row (no timer activity).
- w4-v2 status: **NOT running** (proven operationally, §2): the promoted
  08C episode evaluates `partial` / 3× `satisfied_reported` on live —
  byte-identical inputs verify under w4-v2 on scratch. Operator restart
  (`mission.cmd`, no `--rebuild`) + re-run `POST
  /api/work-evaluation/runs {"episode_id":"ep:task:W8-PILOT-VERIFY-08C",
  "semantic":false}` promotes the live verdict to `complete`.
- 08C promotion (genuine refs only, idempotent, historical rows untouched):
  new `ep:task:W8-PILOT-VERIFY-08C` (`Projects/ai`) + objective `w8obj1` +
  3× `relational`/`explicit_user`/mandatory requirements + association
  `git-78e0d72b6ea4b329629520f8:88b7c04f38e…` + 6 bound evidence links
  (3× `git_commit` + 3× `remote_ref`, digest `repro:6cc6e4d7…`).
  Live eval run `586d94a346de4b10` (513 ms, 0 model calls): `completed`,
  `partial`, 3 requirements assessed, 3 `verification_gap` findings raised
  (expected under w4-v1). `ep:task:AI-CORE-08C` and all prior assessments
  untouched. Rubric-review vs fact-reproduction separation kept: no reviewer
  assertion was used as evidence; only git plumbing outputs + bindings.
- Mission activation (actor `operator`, per Q&A): policy set
  `mission → manual_evaluation` (30-day lookback). Bounded pass, all
  deterministic, $0: observation `f4a9c9b76a0b49cd` (76 sessions, 2000
  msgs incl. truncation flag, 197 new signals, 1.0 s); reconstruction
  `fa115d947cea4cea` (34 episodes, 482 associations, 4 rejected, 4.3 s);
  triage `6423fcb59da5418a` (454 triaged, 0 queued for model, 9.8 s);
  deterministic extraction on 10 task episodes (W0–W8 + WORK-OUTCOME-01):
  0 requirements written (+1 inferred objective on WORK-OUTCOME-01);
  evaluation of those 10 with `semantic:false`: all `unknown` (no
  requirements to assess — honest, not a failure). No requirement
  confirmed (none recovered; confirmation stays human).
- Metrics for Activity → Work Evaluation: sessions observed 76; episodes
  reconstructed 34 (mission) incl. `ep:task:W{0..8}`, `WORK-OUTCOME-01`,
  4× `D-PUB-*`, 19 chains, 1 unresolved bucket; requirements recovered 0;
  awaiting confirmation 0; verified outcomes 0 on mission (08C partial on
  live per above); findings raised this pass 3 (all 08C
  verification_gaps); groups now 27; unevaluated work 24 mission episodes
  (D-PUBs + chains, bounded pass covered 10); processing ~15.5 s total;
  model expenditure $0.00 (cost endpoint confirms 0 calls).
- Worker/workbench: **HELD disabled** (conditional not met). Mission proves
  the pipeline runs end-to-end, but evaluations stay `unknown` until
  requirement recovery works — which needs semantic assistance (disabled,
  $0) or human-authored recovery. Enabling more projects now multiplies
  unevaluated episodes without assessments. Payloads ready for the
  operator: same `POST policies` shape with `"project_key":"worker"` (or
  `"workbench"`), then the three bounded `POST .../runs` above.
- DeepSeek retry (step 5): `pi --model
  opencode/deepseek-v4.1-flash-free` probe → **429 FreeUsageLimitError**
  again. Recorded; no paid route tried. Cross-family stays PARTIAL.
- Checklist: 8 items — backend started ✓ / code-running verified
  (w4-v2 ✗ → restart pending) / 08C promoted ✓ (live verdict pending
  restart) / mission enabled ✓ / mission evaluated ✓ (10 bounded) /
  worker-workbench held / DeepSeek retried-blocked / commit-push SKIPPED
  (not authorized — tree left dirty, see below).
- No code changed in this activation (no regression tests required;
  focused suites last green 92 on 2a7d22c). Operational writes only:
  1 policy row (`wo_policy:mission`), 1 observation run, 1 recon run,
  1 triage run, 1 episode + 1 objective + 3 requirements + 1 association
  + 6 links, 11 eval runs, 3 findings. Nothing else touched; publication
  work preserved (no publication files read or written here).

## 4. Programme self-evaluation re-run (focused, 3 obligations, scratch)

Method mirrors W9F on an isolated copy (no operational writes):
`ep:task:WORK-OUTCOME-01-CLOSURE` (kind programme), 3 mandatory
`explicit_user` requirements, linked current-tree evidence, deterministic
evaluation only. Result: **STATUS completed, COMPLETION incomplete** —
`cr1 (cross-family complete) = satisfied_reported` (Mistral conditional
linked; correctness unjudged — human commission still open);
`cr2 (verified episode record exists) = satisfied_verified` (w4-v2 code +
demo digest linked); `cr3 (multi-project demonstrated) = not_satisfied`
(no live Wave 1 evidence while siblings have it). Honest movement: 3 gaps
→ 1 verified + 1 reported + 1 missing. No unconditional acceptance claimed.

## Test evidence

- 92 focused backend tests green (single run, ~13s):
  `test_work_evaluate` (incl. 4 new w4-v2) + `test_work_calibration` +
  `test_work_continuous` + `test_db_targeting` + `test_work_policies`.
- 14-policy/target subset also green standalone. No `long`/corpus suites run
  (per AGENTS.md: capability-resolution corpus is ~2-min `long`, not a
  per-stage smoke; unrelated to this change).
- Frontend suite / `tsc` / build NOT re-run (no frontend changes; dist
  freshness verified by mtime + clean `git status -- frontend/`).
- Provider spend: **$0.00**. Local model calls: 0 successful (2 DeepSeek
  free attempts, both 429, $0). Deterministic paths made zero model calls.

## Working-tree changes (uncommitted, nothing pushed)

- `backend/mission_control/work_observation/verify.py` (w4-v2 lane + binding).
- `backend/mission_control/work_observation/evaluate.py` (relational gate).
- `backend/tests/test_work_evaluate.py` (+4 w4-v2 tests).
- `docs/programmes/WORK-OUTCOME-01/W9G-*` (DeepSeek attempt record).
- This file. Program ledger update follows (minimal).

## Residual obligations (explicit, no W10)

1. Human cross-family sign-off (DeepSeek route when free tier recovers, or
   commissioned human): gates unattended semantic only.
2. Live promotion of the verified 08C record + Wave 1 enablement: operator
   restart + bounded passes above.
3. Future independent ruling on w4-v2 (when a cross-family reviewer is
   available): amendment is narrow, tested, and owner-authorized; a REJECT
   ruling would revert 08C to partial without affecting any other verdict.

## Requirement-recovery qualification (2026-11-25, backend operator-started)

- Actual cause of zero mission recovery (evidence, not speculation):
  deterministic extraction abstains by design (`extract.py:166-169` —
  "Requirements need judgement and are explicitly abstained here");
  `_deterministic_packet` emits only objectives (task episodes) + claims
  (test/completion signals). Live packets for all 10 task episodes:
  `requirements:[]`, `session_id:null` — the 2,000-message truncation is
  NOT causal (messages are not requirement-mined on this path). Programme
  docs were never searched (no repo-doc step on the deterministic path).
  The authority gate (`record_requirement_manual`: explicit_user /
  accepted_proposal + digest + basis) is sound but had no feeder. Semantic
  extraction refused: `model_not_enabled`, 0 calls.
- Semantic capability: Ollama loopback UP (incl. `mistral:7b-instruct`,
  `mistral-small`, `ministral-3:8b`); backend governed route DISABLED
  (`model_enabled:false`). One refused probe spent (0/10 budget used
  successfully, $0). Ollama NOT called directly (would bypass budget,
  validation, caching). Fallback used: human-reviewed recovery path.
- Recovered (API-accepted 9/9, reviewer `operator`, state accepted,
  UNCONFIRMED — no `/confirmations` called): W2 x2 (deterministic-only
  gate sentence; PG-write authorization sentence; src W2-ENTRY-GATE.md
  `4FDC3903…`), W5 x2 (independent-review-pending UI rule; read-contract
  rule; src W5-ENTRY-GATE.md `FDE8C80E…`), W8 x2 (stop-conditions
  sentence; W8A→W8F gate order; src W8-ENTRY-GATE.md `79854DB3…`),
  programme x3 (§31 NOT MET/PARTIAL rows; src W9-FINAL-REPORT.md
  `3C8DFB07…`), all rev `a1410fa`, kind `acceptance`, mandatory. Texts
  are verbatim excerpts (minor punctuation normalization where quoted
  JSON required it — full provenance in `wo_requirement_sources`).
- Evidence: 9 `file:` citation links (basenames, human-reviewed,
  moderate) → deterministic assessments 9x `satisfied_reported`
  (correctness unjudged — honest). Evaluations: W2/W5/W8/WORK-OUTCOME-01
  all `partial`; 9 `verification_gap`/minor/suspected findings with
  `next_action: supply independent verification`. Coverage now:
  partial 6, requirements_assessed 41, findings 305, model_calls 0.
- Awaiting confirmation: 9. Confirmed: 0.
- Meaningfully evaluated: 4 mission episodes at requirement level
  (reported) + 08C (reported live / verified scratch w4-v2) + 10 mission
  task episodes `unknown` (no requirements — correctly abstained).
  Worker (2 eps, 455 assoc) + workbench (3 eps, 500 assoc) reconstructed
  with 0 sessions observed (git-side only; needle matched no session
  metadata) — policies enabled (`manual_evaluation`, actor operator),
  evaluation deferred until requirements exist (same honest pattern).
  No scheduler, no auto-confirm, no paid inference anywhere.
- Actionable conclusions: (1) Confirm-or-reject the 9 recovered
  requirements in Activity → Work Evaluation — the highest-leverage human
  action; each flips a `partial` toward `complete`/`incomplete` honestly.
  (2) Restart backend (below) flips live 08C to `complete` under w4-v2.
  (3) Mission's 24 remaining episodes repeat the same recovery pattern.
- Limitations: reported ≠ verified; reviewer `operator` is the
  transcription identity (owner confirmation pending — recorded as such);
  semantic route still operator-gated; DeepSeek free still 429 (no
  further retries); 08C live verdict awaits restart; worker/workbench
  episode content is git-derived until session linkage improves.
- Spend: $0.00 total (1 refused model probe + 1 refused DeepSeek probe,
  0 successful model calls across ~40 deterministic runs).

## Operator restart for w4-v2 (safe, picks up 2a7d22c)

Preflight already done (v54, backup per W5A, dist fresh). Run from the
tree at `a1410fa` (contains w4-v2; no `--rebuild` — frontend unchanged):

```
mission.cmd --stop
mission.cmd
```

Verify: `/api/health` → `schema_version 54`; then re-run
`POST /api/work-evaluation/runs {"episode_id":"ep:task:W8-PILOT-VERIFY-08C","semantic":false}`
→ expect `complete` / 3x `satisfied_verified`. If it still reports
`partial`, the restart did not pick up the tree — stop and report.

## MC-HARNESS-FIX-01 — project Harness tab correction (2026-11-25)

- Root cause (reproduced live, not assumed): Worker :7317 is UP
  (v0.2.0, `/v1/jobs` and `/v1/strategies` healthy) but its
  `/v1/executions` ledger route returns 404 `NOT_FOUND` because no local
  execution ledger is configured on that Worker process
  (`worker/src/server/server.ts:50-55` — read access gated on a local
  ledger). Mission's adapter mapped every Worker 404 to
  "Worker execution or retained artifact was not found", and the
  project panel rendered that verbatim with no empty/unavailable
  distinction. Same failure on all 6 probed projects (systemic, not
  jev-specific). Jev (`kind book`, active) has no envelopes, so even a
  readable ledger would correctly return zero rows for it.
- Backend fix (`backend/mission_control/api/harness.py`, uncommitted):
  ledger-read 404 → 200 empty collection + explicit
  `coverage.ledger {available:false}` and `worker.ledger: unavailable`
  (renders as unavailable-with-retry, never as zero); worker transport
  503/504 still propagate as 503 (unavailable distinct from empty);
  single-record 404s keep not-found semantics; `project_key` validated
  against the registry (unknown → 404 `Unknown project`, not empty);
  filtering uses canonical basename identity (`Projects/ai` ≡ `ai`,
  exact-basename only, no fuzzy matching). Execution≠acceptance and
  per-record artifact semantics untouched.
- Frontend fix (`frontend/.../harness/HarnessPage.tsx`, dist rebuilt and
  live): three states everywhere (unavailable+retry / empty with
  counts+how-to / rows), friendly error mapping by status, jargon
  description replaced with user copy + `<details>` diagnostics,
  Executions tab and ProjectHarnessPanel share the logic. Verified
  rendering: panel + global history (`/harness?tab=executions&
  project_key=jev`) both load scoped views with retry; console shows
  only the expected ledger-404 resource errors, no JS exceptions.
  Screenshots: `jev-harness2.png`, `jev-global2.png` (temp dir).
- Regression evidence: 15/15 backend (`test_harness_api.py`, incl. 5 new:
  ledger-disabled empty-200, zero-executions empty-200, unknown-404,
  worker-down-503-propagates, canonical-identity match); 9/9 frontend
  (`HarnessPage.test.tsx`, incl. 3 new panel states); `tsc` clean;
  production build clean (pre-existing chunk-size warning only). Full
  frontend suite: 185/187 — the 2 failures (LivingBook, Inspect) pass in
  isolation and are parallel-run flakes in unrelated pages.
- Operational status: frontend half LIVE now (dist served, friendly
  error + retry visible); backend half PENDING operator restart (running
  backend predates the fix — same restart as w4-v2; one restart picks up
  both). Post-restart expectation: all 6 projects → 200 empty +
  unavailable panel; unknown project → 404. No model calls, no
  executions launched, no auto-confirmation anywhere. Blocker: backend
  restart authorization.
