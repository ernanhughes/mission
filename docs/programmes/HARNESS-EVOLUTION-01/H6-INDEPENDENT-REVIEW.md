# H6 independent review

## Reviewer and independence

Read-only review by a separate isolated Codex reviewer (`gpt-6-luna`) as requested in H6-X. The reviewer inspected H6 requirements, Mission Harness API/UI and Work Envelope, Worker summary/catalogue contract, plus repository status. It did not edit files, run tests, invoke models, access operational databases/services, or change shared dirty work. Review was procedural and source-based; it is not an external provider review.

## Initial findings and closure

| Severity | Finding | Resolution / evidence |
|---|---|---|
| P1 | UI trusted Worker episode IDs although Worker marks them `caller_supplied_unverified`; this could attach unrelated Work Outcome records. | Mission now joins `operation_id` to `WoWorkEnvelope` and verifies Worker episode and task/objective against the envelope. Only verified correlations drive project filters and evaluation links; UI retains the Worker source flag. Backend test covers exact match and tampering. Isolated E2E correlation is verified. |
| P2 | Project-scoped Harness still offered global episode choices and launch did not enforce scope. | Episode list receives exact project key; launcher sends it; server checks resolved `episode.project_key` before authorization. Focused backend test rejects out-of-scope launch with no envelope. |
| P2 | Experiment comparison grouped by task/route alone and implied comparability despite different budgets/policy/runtime conditions. | Group now requires verified episode/objective plus matching populated backend, route, policy, time/output budgets, data policy, temperature, reasoning effort, and executor; comparison label requires distinct strategies. UI describes its limits; focused frontend tests/build pass. |
| P2 | Unknown temperature/reasoning settings could still pass the comparison completeness check. | Closed: both fields must be populated; frontend regression verifies unknown conditions do not qualify. |
| P2 | Decisions view showed an unverified Worker episode ID. | Closed: UI shows only verified Mission correlation or explicitly says “Worker episode unverified”; frontend regression covers it. |

## Review disposition

Initial material findings and two follow-up residuals were corrected. Final read-only follow-up confirmed the fixes and found no further material concern. The reviewer inspected source/tests but did not run tests or use live services. No general effectiveness or live provider inference claim is made.

The reviewer also noted that actor and authorization note values are operator-entered attestations; no authenticated-user identity binding was established. This is recorded as K-27 and must be considered before operational activation.
