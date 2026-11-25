# W5-STATUS-AND-EVIDENCE-PRESENTATION — Assurance without decoration

Vocabulary (exact, enforced in `labels.ts`): Complete · verified (only for
deterministic `complete`), Partial, Incomplete, Blocked, Unknown,
Unevaluated, Conditionally accepted, Evidence outstanding, Evidence linked,
Qualified. CSS tones are restricted to `tag-accent` (verified-complete
only), `tag-danger` (major problems), default (everything else) — meaning
lives in words, never color alone.

Key presentations and their honesty properties:

- Unknown ≠ failed: unevaluated episodes show "Unknown"/"Unevaluated", never
  red; incomplete shows "Incomplete" only on evidence.
- Claims vs verification: claims list shows "Unverified assertion" unless a
  verification row exists; verified claims show method + rationale excerpt.
- Conditional acceptance: candidate-status episodes carry a "Conditionally
  accepted" tag wherever they appear (list, detail, overview).
- Empty states distinguish no-records from clean bills: "Empty here means
  unavailable data, not finished work."
- Findings: severity + kind + status + next action + closure evidence;
  mandatory work sorts first in the default overview.
- Backend failures render explicit error states with retry ("Mission
  Control is not reachable…"), never zero-count dashboards — verified
  live by killing the dev backend mid-session (screenshot on file).
- No composite scores anywhere; execution/outcome/completion stay in
  separate sections.
