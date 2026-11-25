# W2-ENTRY-GATE — W1 closure, W2 authorization, initial state

## 1. W1 status at W2 entry

W1 CONDITIONALLY ACCEPTED 2026-11-24 (W1-FINAL-REPORT). Reconciled: the
implementation matches the report — `work_observation/` (5 modules),
`api/work_observation.py`, migration 041 dual-file, 41 focused tests green,
service wired in `main.py`, checkpoints/signals/checks as described.

## 2. W1 obligations: closed or explicitly carried

| Obligation | Outcome at W2 entry |
| ---------- | ------------------- |
| Independent review unavailable | CARRIED as open acceptance obligation. Governed routes still absent (no Muse/Codex route in-repo; Worker `127.0.0.1:7317` refused). Implementer 10-point challenge completed (W1-INDEPENDENT-REVIEW). W2 prepares an external review commission (W2-INDEPENDENT-REVIEW) instead of relabelling self-review. Deterministic W2 proceeds; no ungoverned AI judgments anywhere. |
| Migration 041 on pre-existing PG | CLOSED (validated). Simulated v40 scratch PG: `DROP wo_* + DELETE version>=41` → `apply_migrations` → `[41]`, version 41, pre-existing row intact, `wo_*` readable, reapplication `[]`. Operational `mc` untouched (auto-applies on next start). |
| Two unmatched SHAs | CLOSED (classified, read-only evidence): `0ada120a…` = valid commit in `C:\Projects\stephanie` (cross-repo reference, legitimately cited in ai docs as Stephanie source); `49d89821` = 64-hex embedding-profile id misread as abbreviated SHA (invalid as commit; 0 objects share the prefix). Neither forced into an association. Extractor guard added: existence checks are mandatory before promotion (W2 R3). |
| Full backend regression | CARRIED. Focused + neighbour suites green (76 tests); full suite deferred per test policy until shared paths change. Required before eventual integration. |
| Historical coverage fixtures | CLOSED. Coverage matrix in W1-HISTORICAL-COVERAGE-REPORT; key-tolerant parsers + `parse_error` + parts-supplement rule pinned by tests. |

## 3. Initial repository state (W2 start)

- Branch `main`; W1 files present as listed in W1-FINAL-REPORT; pre-existing
  `docs/programmes/publication/*` modifications preserved, unstaged.
- Operational `mc` PostgreSQL untouched by W1/W2 work (scratch DBs only).
- OpenCode DB live, read-only.

## 4. W2 gates (from authorization)

Deterministic reconstruction only (W3–W9 excluded); stable identities;
many-to-many; hierarchy without forced programmes; abstention over false
links; no completion judgements; zero model cost; operational PG writes
require separate authorization (scratch for pilots); no commits/pushes/deploy;
preserve unrelated publication changes.
