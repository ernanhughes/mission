# W8A-W7-OPERATIONAL-ACTIVATION — Corrective interface is live

## Verification (all live :8790, 2026-11-25)

- Schema v49; 048/049 tables present and EMPTY (proposals 0);
  projects 81 / commits 12779 unchanged; 293 findings (287 open).
- Backend serves W7 routes (work-corrective 200s) and rebuilt dist
  coherently (operator restart on the W7 tree; no version skew).
- Bounded activation demo, all manual triggers, all 200:
  24 groups → proposal wp:151452c03ef74063 (RECOVER_EXISTING_EVIDENCE,
  08C finding) → 17-section commission preview → submit →
  approve (w8-human + confirm) → manual handoff recorded (queued).
  Requirement c578e9ec confirmed (w8-human + R1 rationale).
  No execution, no auto-close, no ecosystem writes.
- Page-load behavior unchanged (GETs only; tested in suite).

## Position

- W7 frontend deployment: DONE (operator restart serves W7 dist+API).
- Operational proposal creation / confirmation interface / manual
  handoff: AUTHORIZED and DEMONSTRATED (bounded ai pilot).
- Scratch pilot rows (7 proposals, 2 confirmations, exemplar) stay on
  w6e — not copied to production (§3 honored; operational rows are
  the newly created legitimate ones above).
- Worker execution, semantic drafting, scheduler, paid inference:
  remain disabled/deferred as decided.

## W8A gate: PASS (available with constraints noted)

The interface is operationally available. Remaining constraint: 048
pilot rows live on scratch; operational use starts from the
demonstrated legitimate records above.
