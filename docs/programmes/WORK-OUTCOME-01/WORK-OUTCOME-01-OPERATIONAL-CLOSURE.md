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
