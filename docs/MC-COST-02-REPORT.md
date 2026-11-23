# MC-COST-02 — AI Consumption & Model Efficiency (report)

Extends the MC-COST-01 Cost dashboard in place. No new system, no model
switching, no paid calls, no Worker changes. Everything below is uncommitted
pending owner review.

## What changed

**Backend** (`backend/mission_control/`):
- `opencode_cost/__init__.py`
  - `throughput_of` / per-request throughput on totals, per-model, per-session,
    per-call: `input + output + cache_read + cache_write` (provider accounting:
    output includes reasoning, so reasoning is shown separately, never added).
  - `classify_billing(provider, model_id)` → `go-candidate` / `direct-candidate` /
    `free-candidate` / `mixed` / `unknown`, always with a reason string stating
    that authoritative `opencode.billing_source` is not retained locally.
    A zero-dollar cost never implies a route on its own.
  - Per-session dominant billing + `billing_mixed` flag, `max_input`
    (largest single-call uncached input), `models` list. Children are separate
    sessions; parent totals never include child messages.
  - `build_efficiency(scan)`: deterministic advisory recommendations, each with
    evidence session IDs and `action: "none (advisory only)"`.
  - `caller_identity_audit()`: retained vs missing caller fields + per-system
    instrumentation list.
- `api/cost.py`
  - `GET /api/cost/sessions?sort=cost|requests|throughput|input|cache_read|output|updated`
    (validated, defaults to `cost`).
  - `GET /api/cost/efficiency` — advisory recs for the selected window.
  - `GET /api/cost/attribution` — retained/missing fields, Unknown counts.
  - `GET /api/cost/catalogue` — Pi `pi --list-models` (no session) + keyless Go
    model list (4 s timeout, 10 min cache); any failure degrades to unknown.
  - Spikes gains `large-context` (≥200k uncached single call) and
    `repeated-operations` (≥100 calls/session) findings.
- `schemas.py`: additive `Cost*` fields (all defaulted) + `CostEfficiency*`,
  `CostCatalogue*`, `CostAttribution*`.

**Frontend** (`frontend/src/`):
- `pages/CostPage.tsx`: throughput-first header, sortable Top-consumer tables
  (projects + models: throughput/requests/input/cache_read/cache_write/output/cost),
  session sort selector (server-side), billing badges with legend, Model
  Efficiency section, Attribution section, catalogue note, clickable
  parent/children navigation in the session modal, throughput breakdowns that
  separate cached reads from newly processed input. All data paths are GET.
- `types/api.ts`: mirrors for the new/changed contracts.
- `test/CostPage.test.tsx`: +2 tests (sorting without refetch, efficiency
  evidence + GET-only).

## Caller identity: what is retained, what is missing

Retained locally: session id, project/worktree, parent/child links, working
directory, agent name, per-request provider/model/variant.
Missing: OS process/command, application name, `x-opencode-session` header value,
per-request billing_source/allowance/list_cost.
Instrumentation still needed: Mission Control tags Pi calls with a stable
session id instead of `--no-session` where continuity is intended; Worker
propagates workflow/run ids; Pi forwards `x-opencode-session`; ALIVE/Translator
add a caller header on direct inference calls (or route through a tagged session).
Sessions whose project has no local row, plus direct application calls that
bypass OpenCode sessions entirely, are labelled `Unknown` — never guessed.

## Verification

- `ruff check` clean on all touched backend files.
- Backend: `test_opencode_cost` (7) + `test_opencode_cost2` (7) + `test_git_activity`
  + `test_security` — **30 passed**. New tests cover throughput math, billing
  categories incl. mixed sessions, parent/child no-double-count, sort keys +
  invalid-sort 422, advisory-only efficiency, catalogue graceful degradation,
  attribution Unknown counts.
- Frontend: **131 passed (27 files)**, incl. 4 CostPage tests (GET-only on load,
  unavailable source, sorting, efficiency evidence).
- `npm run build` succeeds.
- Real-DB smoke (`mode=ro`, Dublin 2026-11-22): 7,096 requests, throughput
  identity holds exactly; top model by throughput is `meta/muse-spark-1.3-contributor`
  (1.60B, direct-candidate — correctly kept separate from the Go allowance);
  8 efficiency recs, all advisory with evidence links.
- Independent SQL cross-check from MC-COST-01 still matches dashboard totals.

## Acceptance walkthrough

Cost → Yesterday (or Custom 2026-11-22) → Top consumers sorted by **throughput**
→ largest project → its sessions sorted by throughput → open the top session →
actual model calls with per-call input/cache/output, agent, parent/children,
failures → Model Efficiency states whether a cheaper/free route is worth
verifying for that workload. Every figure traces to a recorded row; allowance
itself remains provider-side only.

## Deliberate non-goals (unchanged)

No automatic model switching, no paid experiments, no Worker/ECK enforcement,
no provider credential exposure, no fabricated percentages. Mission Control
observes and explains; Worker would eventually decide and enforce.
