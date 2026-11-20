# MC-LIVING-BOOK-02D-R1 — Provider Reliability and Experimental Readiness

Status: **R1 qualification complete. PILOT-2 protocol prepared, not authorised and not
executed.** PILOT-1 remains frozen and `inconclusive`; it was not rerun, amended or reinterpreted.

This is an engineering qualification, not evidence of learning.

## 1. What was investigated

PILOT-1's Arm B stopped twice at the first experience-bearing section request. Both failures were
`ambiguous_provider_request` with a provider timeout. R1 traced the retained receipts, compared
the exact admitted contexts with Arm A, and made bounded real provider calls using the exact
retained section-1 contexts.

The Pi/egress path was inspected and regression-tested separately. No full chapter workflow was
run. No manuscript, proposal, decision or PILOT-1 record was changed.

## 2. PILOT-1 receipts

| Attempt | Run | Section-1 context | Section-1 prompt tokens | Section-1 latency | Result |
| --- | --- | --- | --- | --- | --- |
| A | `1bae6afa…` | 14,440 bytes | 3,533 | 9,684 ms | completed, 4,704 tokens |
| B1 | `e493ef43…` | 17,543 bytes | 4,242 | 33,575 ms | timeout at 33,086 ms, no response |
| B2 | `5033629a…` | 17,036 bytes | 4,144 | 33,667 ms | timeout at 33,159 ms, no response |

The section workflow uses the same model (`muse-spark-1.3-contributor`), role
(`informed_improver`), instructions/schema, output ceiling (1,536) and workflow v1006 in all
three attempts. The source, plan, section text, outline, neighbours and criteria are identical.

The B contexts add the experience item: 2,672 bytes versus 28 bytes disabled in A. The remaining
difference is the separately generated review: B1 review 2,085 bytes, B2 1,653 bytes, A 1,603
bytes. The review stage is not experience-conditioned; it is a non-deterministic model call.

Both ambiguous requests were durably `dispatched` before the upstream call. Each Pi run admitted
exactly one provider request (`max_provider_requests: 1`, `provider_requests: 1`,
`inbound_requests: 1`). No retry was attempted. The provider returned no response, no HTTP status,
no usage and no response identity. ALIVE recorded the slot as `ambiguous` and charged the model
invocation conservatively (`22,650` and `22,148` tokens, reason `conservative reservation
retained`). That is an internal budget charge, not a provider-side bill.

The configured Pi run deadline was 120 s. The effective provider HTTP timeout was
`ALIVE_META_TIMEOUT=30` s; the failures landed at ~33 s. Arm A's own section latencies reached
29.686 s (section 5), so the 30 s ceiling is tight even without experience.

Reconciliation identifiers available for the historical requests:

| Attempt | Model invocation / sent `X-Request-ID` | Pi run | Provider body hash | Approved request hash | Response |
| --- | --- | --- | --- | --- | --- |
| A section-1 | `20508322-7e7d-45a0-b07a-5438781937a9` | `22c36ac1-8bab-49af-b0b7-154458f141c2` | `14a9c857…` | `879d1c20…` | `83c294bd…` |
| B1 section-1 | `22a784e6-c9aa-4a6c-9b4d-837bc17296f3` | `ca6d4fa6-1396-4b53-8d9f-0da1998ca64b` | `48e91477…` | `f3c329cd…` | none |
| B2 section-1 | `4a0df1a4-f0e0-4c1a-8c11-b97956ab2753` | `17332de5-1079-46ac-93f3-4ad0f573e9c2` | `f07cd454…` | `00c83b51…` | none |

The provider may be able to correlate the two ambiguous requests by the sent `X-Request-ID`. ALIVE
cannot itself determine provider-side completion or billing from the retained receipts.

**Conclusion supported by the evidence:** the best-supported cause is transient provider latency
crossing the 30-second client timeout, not a deterministic experience-payload failure. The exact
B contexts later completed at the 30-second setting. The evidence does not prove the remote cause,
and it does not establish whether the provider processed or billed the timed-out requests. No
provider request identifier was recorded in the historical rows (`upstream_ref` was null).

## 3. Bounded provider qualification

Method: `scripts/qualify_provider_02d_r1.py` in ALIVE reads the exact retained instructions and
admitted contexts from the named model invocations and calls the same Meta model/provider with the
same schema and output ceiling. One call per case, stated timeout, no retry. It starts no workflow,
creates no admission or Grant, writes no proposal and does not touch the manuscript. It is a
provider diagnostic; the Pi/egress path is covered separately.

The corrected run (`provider-qualification.json`):

| Case | Timeout | Latency | Tokens | Validation |
| --- | --- | --- | --- | --- |
| Minimal probe | 30 s | 6,881 ms | 161 | passed |
| A section-1, no experience | 30 s | 22,993 ms | 4,822 | passed |
| B1 section-1, experience | 30 s | 6,355 ms | 5,329 | passed |
| B1 section-1, experience | 90 s | 10,580 ms | 5,293 | passed |
| B2 section-1, experience | 90 s | 9,693 ms | 5,259 | passed |

Five of five completed; zero timeouts; five of five section outputs passed the same restore and
validation path used by the section adapter. Every call returned a provider request ID distinct
from the local `X-Request-ID`.

A first run (`provider-qualification-run1.json`) also completed five of five provider calls with
zero timeouts, but its section validation step compared the pre-restoration template and reported
false failures. That receipt is retained for the provider-completion data; its validation column
is not used.

The exact B contexts completed at 30 s in both runs. The A context was the slowest call in the
corrected run (22.993 s), while the larger B context took 6.355 s. Payload size alone does not
explain the failures. The 30 s ceiling remains a systemic risk because A's real section calls
already reached 29.686 s.

## 4. Execution equivalence

Verified identical across A and B:

- model `muse-spark-1.3-contributor`, provider `meta`, role `informed_improver`;
- instructions, output schema, output ceiling 1,536, workflow v1006;
- pinned source, chapter path/hash, section plan, section text, outline, neighbours and criteria;
- call budget, token budget, source and workspace authority.

Verified different:

- the experience object: A disabled (28 bytes), B enabled with one item (2,672 bytes);
- the review output (not experience-conditioned, generated separately);
- therefore the exact admitted context hash. B's retrieval receipt is
  `e5993c625ac957e55de39b5b5be060bddb808c4ab60b18cc37c7b5edd610653a`.

A future PILOT-2 must preserve both context receipts and should either share one retained review
across conditions or accept review variance as a documented noise source.

## 5. Timeout, retry and ambiguity containment

- One reservation permits one provider request; the settings ceiling cannot be raised above one
  without refusal. A second inbound request is rejected (`request_limit`).
- An upstream timeout after dispatch is recorded `ambiguous`, never retried, and settles the run
  `UNKNOWN`; the workflow stops with no proposal.
- The model invocation is charged once, conservatively, when usage is unknown. Unknown usage is
  never recorded as zero.
- The provider request slot is persisted `dispatched` before the upstream call; a late or duplicate
  provider response cannot cause a second dispatch under the same reservation.
- `tests/test_pi_egress.py` and `tests/test_pi_lifecycle.py` pass (40 tests), including the
  one-request ceiling, ambiguity, cancellation, recovery and no-replay cases. The wider provider
  regression set passes (55 tests).

Provider request identity is now captured for future receipts:

- `Generation.request_id` records the provider response header when present;
- `PiProviderRequest.upstream_ref` is set at admission to the `X-Request-ID` ALIVE sent, then
  replaced by the provider response id on success;
- an ambiguous request keeps the sent `X-Request-ID` because no response id exists.

Historical PILOT-1 rows remain null; they were not rewritten.

## 6. Recommendation

Qualify PILOT-2 with `ALIVE_META_TIMEOUT=90` s while keeping one provider request per reservation
and no automatic retry. The 90 s qualification calls did not need 90 s; the change removes the
tight 30 s ceiling that Arm A's own sections already approached. Do not change the global default
without owner authorisation, and do not treat the timeout change as evidence of learning.

## 7. PILOT-2

The draft protocol is
`docs/acceptance/mc-living-book-02d-r1/PILOT-2-PROTOCOL.md`. It is prepared, not authorised:

- held-out chapter 16, `a4e0ee67…`, plan `45970e69…`, six sections, 8 calls;
- A no experience; B relevant chapter-14 context; C irrelevant context;
- C is blocked until an eligible, permission-safe irrelevant item exists;
- independent evaluation, one pre-registered block, no reruns, neutral outcome labels;
- H3 remains out of scope until a qualified lesson exists.

## 8. Reproducibility

| Item | Location |
| --- | --- |
| Qualification script | ALIVE `scripts/qualify_provider_02d_r1.py` |
| Corrected receipt | `docs/acceptance/mc-living-book-02d-r1/provider-qualification.json` (generated in ALIVE, copied here) |
| First-run receipt | `docs/acceptance/mc-living-book-02d-r1/provider-qualification-run1.json` (generated in ALIVE, copied here) |
| R1 code | ALIVE commit `6c577812` |
| R1 docs | this file and `docs/acceptance/mc-living-book-02d-r1/` |
| PILOT-2 criteria | `docs/acceptance/mc-living-book-02d-r1/pilot2-criteria.txt`, SHA-256 `9d33af57…` |

## Non-claims

Provider reliability is not evidence of learning. Retrieving experience is not evidence that it
helped. A favourable model evaluation is not independent proof of general quality improvement. A
successful single transfer task is not evidence of general transferable learning. The historical
ambiguous requests cannot be proven completed or billed from the retained evidence.
