# W9F-OPERATIONAL-ACCEPTANCE — Live product on :8790, verified

## Deployed state verified (not a dev screenshot)

`http://127.0.0.1:8790` (operator-owned process) serves the W9 working
tree: `/api/work-evaluation/policies` responded with all 6 levels and
the 81-project policy list; Work Evaluation tab renders Overview with
**31 episodes / 0 verified complete / 26 needing attention /
1 unevaluated**, `AI-CORE-05` showing PARTIAL with 24 open findings.
Zero console errors. Screenshot: `w9-operational-final.png`.

Deployment mechanism: the operator restarted the backend on the
working tree (same pattern as W5A/048). No deployment step was
performed by this commission; no unrelated workstream was staged.

## Views demonstrated live

| View | State |
| ---- | ----- |
| Overview | live, 31/0/26/1, needs-attention list ✓ |
| Work Episodes | live, per-episode detail incl. Envelope tab (scratch demo) ✓ |
| Outstanding Work | 24 groups / 287 open, drill-down ✓ |
| Proposals | 1 real proposal (approved → handed off) ✓ |
| Quality | per-episode perspectives, no composite ✓ |
| Coverage | assessment/claim/finding totals ✓ |
| Controls | manual triggers, queue, freshness, auto flag off ✓ |
| Requirement confirmation | 1 confirmed (c578e9ec, w8-human) ✓ |
| Execution evidence | 2 links (pilot + independent re-run) on scratch ✓ |
| Test evidence | ai receipt `exe_9054fcca10044918` bound at project level ✓ |
| Review evidence | graded records only (W6/W7/W8/W9A) ✓ |
| Assessment history | append-only, latest shown ✓ |
| Finding closure | 6 evidence-bound closures ✓ |

## Page-load safety

Suite-asserted for tab open, proposals, controls and envelope tabs
(zero POST, zero model calls). Live check: opening Overview issued
only GETs (server log confirms `/api/work-evaluation/overview`,
`/api/applications/workbench`), no execution endpoints.

## What the product tells you today

Intended: objective + requirement text with provenance and version.
Achieved: execution/outcome/completion verdicts per episode, 1 partial,
0 complete, 29 unknown. Quality: three independent perspectives, no
composite score. Remaining: 287 open findings in 24 groups, each with
a recommended action and closure criteria; 1 corrective proposal in
flight.

That is the sentence the programme was built to make possible — and
it is honest about the parts that are still unknown.
