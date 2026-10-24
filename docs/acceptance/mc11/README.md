# MC11 browser and runtime evidence

Generated against the live Mission Control, Worker, local Ollama and Docker
environment on 2026-10-24. This is not fixture-only evidence.

## Accepted workflows

| Workflow | Template | Result |
| --- | --- | --- |
| `wf-94ab93391db64780` | `trace_reduce_v1` | 21 → 3 events, 5 tests pass, 0 CoCoder findings, accepted |
| `wf-e88029132bc24f28` | `brightness_observation_v1` | means/max `[0,128,255]`, monotonic, 0 findings, accepted |
| `wf-aad909c4b5b34806` | `brightness_observation_v1` | cancelled before execution |
| `wf-72d32f9abfaa4144` | `trace_reduce_v1` | preserved MC10 accepted workflow |

Project `mc11-experiments` links 4 workflows (one cancelled) and 2 Language observations.

## Machine-readable

| File | Contents |
| --- | --- |
| `browser-e2e.json` | 5-step Chrome run: two templates, two human accepts, project timeline, cancellation |
| `runtime-state.json` | Workflows, observations, sandboxes, Docker, Worker, source repositories, project timeline |
| `worker-executor-evaluation.json` | Live `opencode-work` free-route evaluation (BLOCKED) |
| `source-repositories.txt` | Source repository states and preservation notes |

Browser console errors: 0. Page errors: 0.

## Screenshots

| File | Scenario |
| --- | --- |
| `01-workflow-templates.png` | Both registered templates and historic attempts |
| `02-brightness-review.png` | Brightness measurement, CoCoder review, Language observation, final decision |
| `03-brightness-decided.png` | Brightness final trace |
| `04-trace-review.png` | TraceLite measurement, CoCoder review and Language observation |
| `05-trace-decided.png` | TraceLite final trace |
| `06-project-evidence-timeline.png` | Project evidence with 4 workflows (one cancelled) and 2 observations |
| `07-cancelled-workflow.png` | Cancelled attempt with no execution or acceptance |

## Reproduce

```powershell
.\scripts\start.ps1
docker build -t mission-control/sandbox-python:3.13 `
  -f docker\sandbox\Dockerfile docker\sandbox
$env:WORKER_CONFIG='C:\Projects\mission\data\integrations\worker\worker-config.json'
# start Worker from C:\Projects\worker
```

The browser run used a temporary `puppeteer-core` installation and Google Chrome;
it is not a runtime dependency.
