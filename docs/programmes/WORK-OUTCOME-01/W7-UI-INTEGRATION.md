# W7-UI-INTEGRATION — Corrective work inside Work Evaluation

No new top-level application. Within Activity → Work Evaluation:

- **Outstanding Work → group drill-down**: recommended action +
  plain-language advice per gap class, closure criteria, and
  "Generate corrective commission" (one proposal per affected
  episode; duplicates return the existing proposal id).
- **Proposals tab (new)**: list with status filter → inspect detail
  (objective/scope/exclusions/acceptance/verification/findings) →
  commission preview + copy → authorization (actor + reason +
  confirm checkbox semantics: approve requires typed human actor and
  an explicit confirm click) → manual handoff record → executions +
  full event history.
- **Episodes → Requirements**: per-requirement decision buttons +
  reviewer field + amend flow (creates v+1, supersedes old).
- **Freshness/queue/Controls**: unchanged from W6; evaluation and
  closure actions show stale/queue state so operators never approve
  against obsolete assessments unknowingly.

Guards: opening anything (proposal, commission, episode) performs
only GETs (tested: no POST on tab open, incl. new Proposals tab);
approval/handoff/closure are explicit button clicks with confirm
semantics; AI-generated text never appears (all content is stored
facts); proposals and execution are visually distinct (draft ≠
authorized ≠ running).
