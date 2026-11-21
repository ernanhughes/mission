# R2 qualification report — executable path, transport, containment

Covers the frozen PILOT-2 block (`PILOT-2-MANIFEST.json` rev 2). No paid call
beyond the authorised probe, block, and evaluation was made.

## 1. Transport configuration (scoped, no global change)

| Setting | Shipped default | Experimental process | Evidence |
| --- | --- | --- | --- |
| `ALIVE_META_TIMEOUT` | 30 (`alive/config.py`, range 1–120) | **90**, process env only | code unchanged; probe + block ran under it |
| `alive_pi_run_deadline` | 120 (range 1–900) | 120, unchanged | `alive/pi/gateway.py` passes it as the whole-process deadline |
| `alive_pi_max_provider_requests` | 1, code-enforced `ge=1 le=1` | 1, unchanged | gateway refuses any other value |
| Retry | none | none | ambiguous/failed runs terminal; B was not retried |

Provider timeout (90s) sits strictly inside the Pi deadline (120s), so an
upstream timeout settles the Pi run as ambiguous/UNKNOWN instead of racing the
deadline fence. R1's direct-provider qualification (exact B1/B2 contexts
complete at both 30s and 90s, slowest ~23s) supported the diagnosis; it did
not substitute for Pi-level evidence — the R2 probe below does.

## 2. Pi-level probe (authorised, 1 call + session)

Living-book `ask` on Distillation chapter 16 through the full Pi path
(session admission → Pi spawn → egress → Meta provider → settlement):

- Status completed, 11.1s end-to-end (inside both ceilings).
- 2 calls, 10,471 tokens, **real usage returned** (1,728 + 8,743 tokens,
  not conservative charges), 2 citations.
- Receipt: `pi-probe-receipt.json` (+ conversation `5d66c53f`).

Pi-level settlement, usage recording, and deadline containment are therefore
qualified with a real provider, not only by the offline suites
(`test_pi_egress.py` + `test_pi_lifecycle.py`: 40 passed 2026-11-20) or the
fake-Pi harness.

## 3. Block evidence (transport worked; generation did not)

- Arm A: 8/8 calls, 52,487 tokens, all stages COMPLETED, proposal retained.
- Arm B section_1: one upstream call admitted (prompt 4,436 tokens),
  completion hit exactly the 1,536-token section ceiling → output truncated →
  Revision validation failed closed → run FAILED in 17.9s. No timeout, no
  ambiguity, no retry, no re-dispatch (ceiling 1 / inbound 1 / admitted 1 /
  failed 1 / ambiguous 0). Receipts: `arm-b-result.json`, `arm-b-pi-receipt.json`
  (Pi 6571ff93, model invocation `17cf35eb`, request/response identities
  retained, cost unknown-not-zero).
- The B experience context was correctly admitted (context `e5993c62…`,
  2,070 chars, item `390ba0bd` score 0.647 — the frozen values); the failure
  was downstream at generation, not at admission.
- Review outputs differ per arm (A 2,609 bytes / B 2,299 bytes, distinct
  hashes) — the registered complete-pipeline comparison, not a pure
  isolated-experience effect. Recorded per frozen rule.

## 4. Execution equivalence (verified identical / different)

Identical: source snapshot (capture `a632c716…`, approval `3996f4b2…`),
chapter 16 (`a4e0ee67…`), criteria (`9d33af57…`, 416 chars), workflow v1006
(def `5cd3400f…`, binding live-verified 64-char hex), model
`muse-spark-1.3-contributor`, evaluator `muse-spark-1.3` /
`chapter-evaluation-v1` (def `13cc2b25…`), call/token budgets, authority,
environment. Different (by design): experience context (A 28-byte disabled
object vs B 2,070-char admitted item) and separately generated reviews.
Order A-then-B, no reruns, no manuscript writes (chapter hashes re-verified
after the block), no decision/promotion changes (A pending, B unavailable).

## 5. Environment finding (bounded decision, fully recorded)

The `.env`-pinned Pi 1.5.0 bundle (`ALIVE_PI_CLI` →
`.../releases/1.5.0/...`) no longer exists on disk — the Pi auto-updater
replaced it (1.5.2 on 11-12, 1.6.0 on 11-20). The first probe therefore
failed fast with `pi_unavailable`, settled once conservatively (8,929
tokens), no provider call. This failure is infrastructure, not experiment,
and is retained in the conversation record — not hidden.

Decision: installed the repo-pinned Pi 1.4.0 (`pi-runtime/`, committed
`package-lock.json`, `npm ci --ignore-scripts`), ran ALIVE with
process-scoped `ALIVE_PI_PINNED_VERSION=1.4.0` + explicit `ALIVE_PI_CLI`.
The committed bundle-sha pin (`e7966…`) matches **no file** in the faithful
npm 1.4.0 tree (verified by hashing the whole tree; receipts record the
executed file's computed digest), so the pin is unsatisfiable via the
documented install path and the check was skipped process-scoped
(`ALIVE_PI_BUNDLE_SHA256=""`). Version enforcement stayed on; every Pi
receipt records version + computed bundle digest. Re-enabling a satisfiable
pin is future ALIVE work, not this commission's scope. All 13 block-time
model calls (probe 2 + A 8 + B 2 + eval 1) ran through this
runtime with clean settlement.

## 6. What this does and does not establish

Establishes: the Pi/provider path settles real calls within the scoped
ceilings; single-dispatch containment held under load (13 upstream calls,
zero ambiguous, zero retries, zero re-dispatches); the frozen identities
were the executed identities; B's failure was a generation output-capacity
event with the experience context correctly admitted.

Does not establish: any learning, transfer, or experience effect (outcome
`inconclusive`); provider billing (unknown, never zero); anything about
output length causality (one truncated event cannot attribute length to
experience).
