# MC-PROJECTS-QUALITY-02 — Evidence-Based Software Quality Evaluation: Report

## What was built

Persistent, evidence-backed software quality evaluation for the 40 software
project workspaces. The Quality tab placeholder is now a working system:
charter → evidence → evaluation → independent review → findings → improvement
prompts → cultivation reporting → history.

## Architecture (all reuse, no new gateways)

- Execution: `research/inference.py::resolve_model` (Pi-first, explicit IDs) +
  `complete_chat` (consent-gated); async queued/running/completed/failed/blocked
  pattern mirrored from `execute_review`; structured JSON validated by contract
  (`software-eval-v1`), brace-extract + required-keys + range + evidence-ref checks.
- Second opinions are separate `software_eval_reviews` rows with a different model;
  disagreements are preserved, never merged.
- History is append-only (`previous_evaluation_id` chains); freshness derived at
  read time (HEAD/charter/rubric drift); overall NULL unless the aggregation policy
  holds (≥8/10 dims incl. purpose+correctness; NA excluded from denominator via
  `max_attainable`).
- Findings deduplicated by `project_id + fingerprint`; lifecycle
  proposed → accepted/rejected/deferred/investigate → in_progress →
  needs_verification → resolved → reopened; high/critical findings need an
  independent agree to count as verified.
- Cultivation integration appends evidence only. A bare score is recorded as an
  unverified observation; only resolved findings with evidence (plus independent
  corroboration for high/critical) may be reported as verified progress. Stages,
  qualification, releases and measurements are never touched by the evaluator.

## Database contract (migration 038)

`software_charters` (draft/confirmed/archived revisions), `software_evaluations`
(`sqeval:`, overall NULL unless policy holds), `software_eval_reviews` (`sqrev:`),
`software_findings` (`sqfind:`, unique project+fingerprint), `software_finding_reviews`,
`software_prompts`. Migration test bumped to 38 with all tables (also absorbing
the parallel MC-PUBLISH-03 `037_publication_followups`).

## Rubric

`software-quality-v1`: purpose 150, correctness 170, testing 130, architecture 130,
maintainability 100, security 100, operations 70, documentation 50, usage 50,
delivery 50 = 1000. Per-dimension: score | abstain | NA + confidence + rationale +
evidence_refs (must cite manifest ids) + findings + assumptions + unknowns.

## Files

- Backend: `quality_software/{__init__,rubric,evidence,service}.py`,
  `api/software_quality.py`, models, schemas, `main.py` wiring.
- Frontend: `features/software/SoftwareQualityTab.tsx` (charter, evaluate flow with
  prompt preview/copy, eval detail, history + compare, independent reviews,
  findings queue, saved prompts, cultivation reporting), reworked Improvements tab,
  `types/api.ts` contracts.
- Tests: `backend/tests/test_software_quality.py` (21) covering charter lifecycle,
  evidence bounds/redaction/fingerprint, per-dimension validation, Windows
  argv-budget package test, dedupe, review independence, lifecycle gates and
  cultivation gating; frontend SoftwareWorkspace suite (charter propose/save,
  evaluate preview/execute).

## Verification

Backend `test_software_quality.py`: 21 passed. Migration seed: 3 passed
(migrations 1..38 incl. `037_publication_followups`). Full backend suite:
714 passed, 1 skipped (live Writer CLI, not configured). Five tests
initially failed on the AI-by-default change and were fixed honestly: one
`test_pi_first.py` assertion pinned the old wrapper path (updated to pin
the direct-launcher behavior, re-verified 5/5), and four consent-gating
tests (`scripts` e1/e2/e3, `software_quality` x2) relied on the ambient
off-default — they now pin the denied state explicitly
(`enabled`+`consent` false) and pass. Ruff clean on all touched files.
Frontend `npm run build` clean, `vitest` 106/106.

## Real bugs found and fixed during pilots

1. Rapid save→confirm sequences returned 404 ("Charter not found") because
   yield-dependency cleanup (and its DB commit) runs after the response is
   sent; a following request can open a session before the previous commit
   lands. Fixed by explicit `session.commit()` before returning in all new
   mutating endpoints (mirroring the `execute_review` precedent), plus the
   same fix in the cutover apply/auto-register/rollback routes. Reproduced
   1/3 → verified 3/3 after the fix.
2. Evidence ids contained Windows backslashes (`repo:C:\...`); after JSON
   escaping no model output could cite them back exactly, so every call
   failed validation. Fixed with `_index_id` (backslashes → forward
   slashes) in both `_evidence_index` and `_index_compact`; validation now
   only accepts ids the model actually received.
3. Pi received the whole prompt via `pi.cmd` → `cmd.exe` (8191-char limit) →
   `powershell -File` double-quoting. JSON quotes/backslashes were mangled:
   short filler prompts passed but real 3.5k evidence prompts failed with
   WinError 206 (`FileNotFoundError`) or "system cannot find the file
   specified", and Pi's default coding-assistant system prompt made
   DeepSeek emit `DSML` tool calls (`ls -la`, `find ...`) instead of the
   contract JSON. Fixed in `pi_backend.py`: resolve directly to
   `node pi-launcher.js` (no cmd/PowerShell re-quoting, ~32k budget),
   split `system`/`user` roles and pass the evaluator contract via
   `--system-prompt` (replacing the agentic default) with `--no-tools` et
   al. Verified: the previously failing 3.5k purpose prompt now returns
   valid `assessed` JSON (`score 50`, cited refs) via both direct and
   backend paths.

## Pilots (scratch backend :8791 + Pi route, real repos, no writes to evaluated repos)

All three pilots ran the full charter → evaluate → findings chain with the
fixed Pi path (`node pi-launcher.js` + `--system-prompt`, model
`opencode-go/deepseek-v4.1-flash`, route `pi-default`), 10 bounded
per-dimension calls each. Results are honest partials: overall stays NULL
where the aggregation bar is not met, abstentions are explicit, and every
finding cites manifest evidence ids.

- verity: `sqeval:3f3f3cc1574d`, partial, coverage 70% (7/10 assessed;
  abstained: correctness, security, usage), 33 findings. Purpose 25/150,
  testing 30/130, architecture 70/130, maintainability 38/100, operations
  25/70, documentation 5/50, delivery 6/50.
- writer: `sqeval:4dada15be356`, partial, coverage 60% (6/10 assessed;
  abstained: correctness, security, operations, usage), 26 findings.
  Purpose 65/150, testing 40/130, architecture 54/130, maintainability
  47/100, documentation 33/50, delivery 12/50.
- mission: `sqeval:91e07f7bd19b`, partial, coverage 70% (7/10 assessed;
  abstained: correctness, maintainability, security), 27 findings. Purpose
  90/150, testing 60/130, architecture 58/130, operations 30/70,
  documentation 20/50, usage 6/50, delivery 16/50.
- Independent review (writer, different model `opencode-go/gpt-5.6-luna`):
  `sqrev:6658ea7a5416`, completed, verdict partial. The reviewer agreed
  the charter gap and missing test-execution evidence are real but pushed
  back where the evidence slice was thin ("claim that no CI pipeline is
  configured overstates an incomplete evidence slice; it establishes that
  CI was not evidenced, not that none exists"). Disagreement preserved,
  original scores untouched.
- Findings → prompts → cultivation (writer, live): 3 high findings
  ACCEPTed → 1 moved in_progress → improvement prompt saved
  (`sqprompt:c39668bdc382`, 2801 chars) → cultivation evidence recorded as
  unverified observation (`verified: false`, reference
  `software-evaluation:sqeval:4dada15be356`). The gate behaved correctly:
  prompt building refused proposed findings, and the cultivation report
  refused in-progress findings as verified progress.
- UI verified in-browser on scratch: `/projects/writer` Quality tab shows
  the confirmed charter, latest assessment with per-dimension scores,
  coverage, STALE freshness reason, and the evaluation detail table.

## Limitations / next steps

- Pi on Windows must be invoked via `node pi-launcher.js` (not `pi.cmd`)
  with the evaluator contract as `--system-prompt`; the `.cmd` path
  re-quotes JSON through `cmd.exe`/`powershell -File` and silently breaks
  prompts over ~3k chars. Per-dimension calls stay ≤6000 chars.
- AI is now enabled by default (owner-directed): seed defaults ship
  `enabled` + `consent` true so fresh databases start AI-on (existing rows
  are never overwritten — get-or-create), and production :8790 was flipped
  via Settings with consent recorded. `/api/health ai_enabled` now means
  Pi-ready (`enabled` + `consent`) instead of requiring a loopback
  endpoint+model, so Pi-only setups no longer report blocked-with-guidance.
  The consent gate itself is unchanged and still tested — the two tests
  that relied on the ambient off-default now pin the denied state
  explicitly (`enabled`+`consent` false).
- Suggested next: finding auto-triage from daily reviews, charter coverage in the
  Overview tab, calibration of the aggregation bar against pilot history.
