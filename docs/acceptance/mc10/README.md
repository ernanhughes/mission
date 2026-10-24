# MC10 browser and runtime evidence

Evidence generated against the live Mission Control service, Worker and CoCoder
on 2026-10-24. This is not fixture data.

## Accepted workflow

- Workflow: `wf-72d32f9abfaa4144`
- Next candidate: TraceLite (`32e30df92070ef58c36324e400b2f6d54aacc375c9f14fd0b0de542630ce6c06`)
- Scope: `tracelite/reduce.py`
- Baseline: `ca5dfb35c035357d50e31ca7780ffaf3eb1af9dc`
- Result: `7403d1be2f7cefbea8d8d8861469bf366d3a3a21`
- Worker: `wrq_6b926abd0c72c625a5d43b9e99706c4d`, local `qwen2.5-coder:latest`
- CoCoder: 1 changed file, 0 findings
- Measurement: 21 → 3 events, 85.7% reduction, 5 tests passed
- Decision: accept, recorded in the browser

## Machine-readable

| File | Contents |
| --- | --- |
| `browser-e2e.json` | 5-step Chrome run: proposal inspection, UI approval, execution/review, UI decision, replay idempotency |
| `runtime-state.json` | Workflow records, accepted workflow, Next export, sandbox state, CoCoder artifact, source repositories, paid-inference record |
| `source-repositories.txt` | Read-only source repository states and MC10 source changes |

The browser run had zero unexpected console errors and zero page errors.

## Screenshots

| File | Scenario |
| --- | --- |
| `00-next-tracelite-candidate.png` | Real TraceLite candidate with the proposal entry point |
| `01-workflow-proposal.png` | Exact scope, budget, baseline and evidence before approval |
| `02-workflow-approved.png` | Approved workflow with execution available |
| `03-workflow-reviewed.png` | Worker result, 21 → 3 measurement, CoCoder clear review and decision actions |
| `04-workflow-decided.png` | Complete 13-event timeline and accepted human decision |
| `05-workflows-list.png` | Experiment list, including preserved failed attempts |

## Reproduce

- Start Mission Control (`scripts/start.ps1`).
- Start Worker with `WORKER_CONFIG` pointing to
  `data/integrations/worker/worker-config.json` (local Ollama direct executor).
- Generate the Next export with `next export --output ...`.
- Use `/workflows` in the dashboard or the Next TraceLite candidate's proposal
  button.

The browser run used a temporary `puppeteer-core` installation and Google Chrome;
it is not a runtime dependency.
