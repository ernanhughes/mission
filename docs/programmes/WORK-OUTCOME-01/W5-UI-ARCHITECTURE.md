# W5-UI-ARCHITECTURE — Five views, one read contract

```
ActivityPage (tab = evaluation)
└── WorkEvaluationTab (sub-view tabs + project filter)
    ├── OverviewView      GET /api/work-evaluation/overview (+ findings)
    │   └── Needs-attention list (mandatory-first sort, top 10)
    ├── EpisodesView       GET /api/work-evaluation/overview (filter client-side)
    │   └── EpisodeDetailModal (summary/requirements/changes/evidence/evaluation/history)
    │       ├── GET /api/work-episodes/{id}            (sessions/commits/repos)
    │       ├── GET /api/work-evaluation/episodes/{id} (verdicts, req assessments,
    │       │                                          claim verifications, findings)
    │       ├── GET /api/work-intent/requirements|claims (texts, authority)
    │       └── GET /api/work-evaluation/findings?episode_id= (actions)
    ├── OutstandingView   GET /api/work-evaluation/findings (kind/status filters)
    ├── QualityView       overview rows (execution/outcome split, no composite)
    └── CoverageView      overview + GET /api/work-intent/triage + coverage
```

Rules: reads only (one POST exists server-side for runs; the UI never calls
it); no model execution on page load or navigation (verified by test:
zero POST across navigation flows); no full-history payloads (bounded
limits, lazy detail); no invented data (every empty state says why, never
shows zero-as-success); conditional acceptance visible on every verdict
(status badge + "Conditional"/"Unevaluated" tags, never bare green).
