# W9D-MODEL-CAPABILITY — What is established for which job

Established (loopback Ollama, $0, validated with fixtures):

| Capability | Model | Standing |
| ---------- | ----- | -------- |
| Triage (deterministic rules) | n/a (code) | established |
| Requirement extraction (assisted, validated) | mistral-small:latest | established WITH validator (W6A: authority tightening); latency ~60–180s/call bounds use to a handful of episodes |
| Requirement validation gates | code | established (vacuity/paraphrase/authority/source tests) |
| Authority recognition | mistral-small | partial: sources correctly, over-claims objectives without session sources (fixed by rejection) |
| Evidence reasoning | deterministic only | established; semantic evidence reasoning NOT established |
| Outcome evaluation (semantic) | mistral-small | pilot-only; 0.5b models BARRED from judgements |
| Independent review | none established | open: same-family agents = reproducibility only; cross-family obtained once (Mistral, W9A) for assurance scope, not per-episode verdicts |
| Commission drafting | none | explicitly deferred; deterministic assembly only |

Unattended semantic evaluation stays DISABLED: capability is
assisted-only, calibration covers the deterministic contract, budgets
are unwirable ($0), and cross-family qualification of per-episode
semantic verdicts does not exist.
