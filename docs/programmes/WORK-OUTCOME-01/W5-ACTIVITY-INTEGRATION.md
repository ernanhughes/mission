# W5-ACTIVITY-INTEGRATION — Tab added, nothing moved

Change: `frontend/src/pages/ActivityPage.tsx` gains a third tab,
"Work Evaluation" (`tab: "commits" | "events" | "evaluation"`), rendering
`<WorkEvaluationTab />` from the new `features/work-evaluation/` module.
Existing Commits/Events tabs, filters, modals, polling and review flows are
untouched (verified by the untouched DailyReview + full frontend suite).

Conventions reused (not reinvented): `useApi` + `apiPath`, `PageHeader/
Section/Stat/Tag/LoadingBlock/ErrorState/EmptyState/Modal`, `copyText`,
`.toolbar[role=tablist]`, `.stat-strip`, `.activity-feed` + `.activity-marker`
+ `.activity-entry/.activity-head/.activity-meta/.activity-actions`,
`link-button`, `toolbar-count`. New code lives in separated components
(`WorkEvaluationTab`, `EpisodesView` + `EpisodeDetailModal`, `OutstandingView`,
`QualityView`, `CoverageView`, `labels`), not in an enlarged ActivityPage.
