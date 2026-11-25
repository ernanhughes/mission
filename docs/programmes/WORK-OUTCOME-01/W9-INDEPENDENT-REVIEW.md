# W9-INDEPENDENT-REVIEW — Two reviews, ten findings, all reconciled

## 1. Cross-family review (Mistral family, non-Meta)

`mistral:7b-instruct` via loopback Ollama, on a bounded excerpt packet
of the enforcement paths. Verdict **CONDITIONAL**, no critical
findings. Its closure finding (`reconcile_resolved` system-attributed)
was fixed in code. Full record: `W9A-CROSS-FAMILY-REVIEW.md`.
Limitation stated there: 7B model, excerpts only, not the human
W1–W5 commission.

## 2. W9 implementation review (separate agent, same family)

Reviewer: DeepSeek V4.1 Flash subagent — **same family as the
implementer**, so this is code inspection and reproducibility, not
independence. It ran the focused suites itself and reproduced two
bugs. Verdict summary: DB-target gate directionally correct but
**not "fail-closed" as documented**.

### Findings and disposition

| # | Severity | Finding | Disposition |
| - | -------- | ------- | ----------- |
| F1 | **High** | `continuous._gated` returned True when the policy service or project scope was absent — including for semantic evaluation | **FIXED.** Semantic now refused without service+scope; deterministic-unscoped is allowed but recorded as `*:policy_unscoped`. Test `test_semantic_never_allowed_without_policy_service` reproduces the reviewer's attack and pins the fix. |
| F2 | Medium | Mechanical-evaluation policy skip was unrecorded; receipt still said `completed` | **FIXED.** `evaluate_mechanical:policy_disallows` recorded; asserted in `test_explicit_policy_changes_gate_outcome`. |
| F3 | Medium | Policy ladder not enforced on manual endpoints (`/work-observation/runs`, `/work-episodes/runs`, `/work-evaluation/runs`, `/work-intent/runs`) | **FIXED.** `require_scope_allowed` added to all four; 403 with a message naming the capability. Test: `test_manual_endpoint_respects_policy`. Unscoped manual actions remain allowed (operator-wide intent) and that is documented. |
| F4 | **High** | Target gate broke `scripts/migrate_sqlite_to_postgres.ensure_pg_schema_via_orm`; direct `psycopg` paths bypass the gate entirely | **PARTLY FIXED, partly corrected.** Script now passes `target="migration"`; 4 other scripts pass `script:<name>`. Coverage claim corrected in `W9A-DATABASE-TARGET-SAFETY.md`: the gate covers the ORM boundary, **not** every raw `psycopg` connection (enumerated there). |
| F5 | Medium | `test_pg_unavailable_points_at_postgres_not_sqlite` failed at construction (missed `target=`) | **FIXED.** |
| F6 | Low | SafeJSON silently coerced malformed data to empty | **FIXED (observability).** Coercion logs a one-time warning naming the failure mode; behaviour stays fail-soft so one corrupt row cannot break a listing. |
| F7 | Medium | Policy tests did not prove an *explicit* policy drives the gate (used default-disabled and default-allowed projects) | **FIXED.** New tests downgrade `ai` to `disabled` (observation blocked) and upgrade an unknown project to `observe` (allowed), plus mechanical-skip and canonicalization cases. Old tautological cases kept as regression. |
| F8 | Low | Non-numeric `lookback_days` → 500; no POST length caps; corrupted stored doc could raise | **FIXED.** try/except → 422; caps on key/level/actor; `get_policy` tolerates a bad stored integer. |
| F9 | Low | `target=` is an unvalidated string, not an authorization | **ACCEPTED + documented.** It is an intent marker (speed bump), not an authz token; the doc now says exactly that and drops the "wrong target shape → refuse" claim. Real authorization is the operator's. |
| F10 | Low | Policy key was the raw scope string, so `work/ai` resolved to a different key than `ai` | **FIXED.** `resolve_project_key`: exact → basename → suffix match; `Projects/ai` removed from defaults so there is one canonical key. Verified live: `work/ai` → `ai`. |
| F11 | Low | `manual_evaluation` could not permit on-demand semantic despite the doc | **FIXED.** `evaluate_semantic_manual` (needs `manual_evaluation`) vs `evaluate_semantic_scheduled` (needs `continuous_semantic`). |
| F-ADJ | Low | `_redact_url` did not redact `?password=…` query parameters | **FIXED.** Query keys matching password/passwd/pwd/secret/token/key are redacted. |

## 3. Result

- 218 focused backend tests green (was 214; +4 new negative controls).
- Reviewer's two reproduced bugs (F1, F2) are now covered by tests
  that would fail if the fix regressed.
- Remaining accepted limitation: actor identity is self-asserted
  (documented since W7); raw `psycopg` call sites are outside the ORM
  gate (documented).

## 4. Deployment note (important for the operator)

The live process on :8790 currently runs the W9 tree **as it was at the
last restart**, which predates the ten review fixes in §2. Everything
in §2 is in the working tree (uncommitted, as required) and takes
effect on the next operator restart. Until then the live process still
has the fail-open semantic gate (F1) and the unenforced manual
endpoints (F3) — latent, because no scheduler exists and nothing
invokes them unattended, but the operator should restart before
enabling any policy or scheduler work.

## 5. Prior obligations, actual status

| Obligation | Status |
| ---------- | ------ |
| W1–W5 cross-family commission | **OPEN** — human invocation of the DeepSeek route pending; gates unattended semantic operation only |
| W4 8-fix re-verification | **OPEN** — no result artifact; own screen green |
| W5 4-fix re-verification | **OPEN** — same; 15 UI tests cover the fixed behaviours |
| W6/W7/W8 separate-agent reviews | CLOSED for issues raised (all critical/major fixed + re-tested) |
| W9A cross-family | CLOSED as a different-family review, limitation stated |
| W9 implementation review | CLOSED — 10 findings, 9 fixed, 1 accepted-and-documented |

## 5. Not claimed

No end-to-end independent acceptance; no trustworthy-without-
qualification semantic verdicts; no verified-complete episode. The
product's own self-evaluation named the same three gaps, which is the
strongest statement available without an external human reviewer.
