# MC-LIVING-BOOK-02D-R1 acceptance record

Status: **R1 complete. Provider qualification passed; PILOT-2 prepared, not executed.**
PILOT-1 remains frozen and `inconclusive`.

## Deliverables

| Item | Location |
| --- | --- |
| Diagnosis and recommendation | `docs/MC-LIVING-BOOK-02D-R1.md` |
| PILOT-2 draft protocol | `docs/acceptance/mc-living-book-02d-r1/PILOT-2-PROTOCOL.md` |
| PILOT-2 criteria | `docs/acceptance/mc-living-book-02d-r1/pilot2-criteria.txt` |
| Qualification script | ALIVE `scripts/qualify_provider_02d_r1.py` |
| Corrected provider receipt | ALIVE `docs/acceptance/mc-living-book-02d-r1/provider-qualification.json` |
| First provider receipt | ALIVE `docs/acceptance/mc-living-book-02d-r1/provider-qualification-run1.json` |
| R1 code commit | ALIVE `6c577812` |

## What was established

### Diagnosis

PILOT-1's two Arm B attempts were provider timeouts at ~33 s. The Pi run admitted exactly one
provider request each time, no retry occurred, and the requests were durably `dispatched` before
the upstream call. No response, HTTP status, usage or provider ID was received. ALIVE charged each
failed model invocation conservatively once (22,650 and 22,148 tokens) and recorded unknown usage
as unknown, never zero.

The exact section-1 context sizes:

| Attempt | Context bytes | Prompt tokens | Latency |
| --- | --- | --- | --- |
| A, no experience | 14,440 | 3,533 | 9,684 ms |
| B1, experience | 17,543 | 4,242 | 33,575 ms (timed out) |
| B2, experience | 17,036 | 4,144 | 33,667 ms (timed out) |

The B contexts add 2,672 bytes of experience (A's disabled object is 28 bytes). The review output
also differs and is not experience-conditioned. The effective provider timeout is 30 s; the Pi
run deadline is 120 s. Arm A's own section 5 took 29.686 s.

### Qualification

Five bounded real provider calls using the exact retained instructions and admitted contexts:

| Case | Timeout | Latency | Tokens | Output validation |
| --- | --- | --- | --- | --- |
| Minimal probe | 30 s | 6,881 ms | 161 | passed |
| A section-1 | 30 s | 22,993 ms | 4,822 | passed |
| B1 section-1 | 30 s | 6,355 ms | 5,329 | passed |
| B1 section-1 | 90 s | 10,580 ms | 5,293 | passed |
| B2 section-1 | 90 s | 9,693 ms | 5,259 | passed |

Five of five completed, zero timeouts, five of five section outputs passed the real restore and
validation path. A first run also completed five of five provider calls with zero timeouts; its
section validation reported false failures because the harness compared the pre-restoration
template. That receipt is retained; its validation column is not used.

The exact B contexts completed at 30 s in both runs, while the smaller A context was the slowest
call in the corrected run. The evidence supports transient provider latency crossing the 30 s
ceiling, not deterministic payload failure. It does not prove the remote cause or provider billing.

### Containment

- One reservation permits one provider request; a second is refused.
- A timeout after dispatch is `ambiguous`, never retried, and the run stops without a proposal.
- Unknown usage is null, never zero; the reservation is charged once conservatively.
- `tests/test_pi_egress.py` and `tests/test_pi_lifecycle.py`: 40 passed.
- Wider provider/transport regression set: 55 passed.
- Provider response IDs are now captured in `Generation.request_id` and
  `PiProviderRequest.upstream_ref`; ambiguous requests retain the sent `X-Request-ID`. Historical
  PILOT-1 rows were not rewritten.

## PILOT-2

Prepared only. It uses chapter 16, six sections, A/B/C conditions, a 90 s provider timeout, one
pre-registered block and no reruns. C is blocked until an eligible, permission-safe irrelevant item
exists. No PILOT-2 model call has been made.

## Non-claims

Provider reliability is not learning. Retrieving experience is not evidence that it helped. A
favourable model assessment is not independent proof of general quality. A single block is not
general transfer. Historical provider completion or billing cannot be proven from the existing
ambiguous receipts.
