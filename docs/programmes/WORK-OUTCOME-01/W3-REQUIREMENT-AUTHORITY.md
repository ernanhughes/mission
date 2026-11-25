# W3-REQUIREMENT-AUTHORITY — Who authorized this, and how we know

Ten classes (§8 of the commission), enforced at extraction and tested:

1. `explicit_user` — direct user request (user-role message, imperative).
2. `accepted_proposal` — AI proposal + subsequent user authorization
   (authorization must be evidenced: explicit approval, not mere continuation).
3. `standing` — programme/architectural policy (AGENTS.md rules, W-series
   stop conditions, security model).
4. `derived` — logically necessary for an explicit objective (marked as
   reasoning, never as quoted request).
5. `ai_decision` — implementing-agent choice (recorded, never mandatory).
6. `suggested` — optional improvement (never blocks completion).
7. `excluded` — explicitly out of scope.
8. `deferred` — explicitly postponed (with the deferral source).
9. `superseded` — replaced by a later authorized amendment (history kept).
10. `ambiguous` — intent not reliably establishable (abstain from authority).

## Enforcement rules (extraction post-validation)

- Quoted review material, historical prompts, documentation listings, and
  fixture identifiers are NEVER `explicit_user`, even when imperative.
- An AI proposal is NEVER `accepted_proposal` merely because the AI
  implemented it; implementation without authorization evidence stays
  `ai_decision` (this is the Mission-Control-UI failure mode from the brief:
  the agent's narrower plan must not silently redefine the objective).
- Conflicts are preserved with chronology; supersession requires an
  authorized amendment, not a later contradictory claim.
- `mandatory` defaults true only for classes 1–4; classes 5–6 default false;
  7–10 never block W4 completion (W4 decides that; W3 records the class).
