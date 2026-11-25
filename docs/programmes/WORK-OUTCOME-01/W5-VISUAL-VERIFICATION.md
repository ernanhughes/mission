# W5-VISUAL-VERIFICATION — Rendered against real pilot data, zero console errors

Environment: unmodified backend on `MC_DSN=w4_pilot3` (31 episodes, 2
findings, 5 assessments), production frontend build, in-app Chromium,
viewport screenshots on file:

- `w5-overview.png` — tab present, 5 sub-views, 31/0/2/27 stats, needs-attention
  list with UNKNOWN (not red) badges.
- `w5-episodes.png` — filterable list incl. the unresolved bucket shown as
  Unresolved + Conditionally accepted; kind/state/only-findings filters.
- `w5-outstanding.png` — 2 verification gaps with rationale + next actions,
  mandatory-first, UNKNOWN badges (not failures).
- Coverage view (screenshot on file as rendered): 31/4/27, 5 requirements,
  51 claims, triage mix with consistent denominators.
- Episode detail modal: all 6 tabs render; requirements show authority +
  verdict; claims show verification state; evaluation shows three
  perspectives; history states the W6 reservation.

Console: zero errors on all verified views. One intentional console error
observed: `GET /api/work-evaluation/episodes/<unresolved-id>` → 404 when no
assessment exists — the UI handles it as "Unevaluated" (correct), and the
404 itself is the honest signal (no assessment row), not a bug. A backend
outage mid-session was also exercised: the views render the explicit
unavailable state with retry (screenshot on file).

Existing Commits/Notes tabs: untouched and passing (full frontend suite
162→171 tests green, incl. DailyReview regression).
