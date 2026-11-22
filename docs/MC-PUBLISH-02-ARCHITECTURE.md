# MC-PUBLISH-02 — Architecture Note: Canonical Identity & Evidence Freshness

## 1. Current identity relationships

| System | Identifier | Stability | Notes |
|---|---|---|---|
| Mission `projects.id` | e.g. `math`, `axiom-zero` | Stable, canonical | PK; routes, assessments, approvals, evaluations all key here |
| Mission `books.id` | `book-<project>` (or `book-<project>-<hex>` manual) | Stable per row | PK; 1:1 with project (`project_id` unique FK) |
| Writer registry key | e.g. `math`, `axiom_zero` | Stable in YAML | Authoritative for manuscript location + validation config |
| Filesystem path | e.g. `C:\books\math\...` | Moves | Repaired by Writer sync; drift preserved, never clobbered |
| Hugo route / Bookbuilder slug | `<identifier>` e.g. `math` | Stable per book | `math.toml: identifier`, `preview.route_prefix /books/<slug>/` |
| ALIVE book id | Ephemeral | Per registration | Re-resolved by manuscript path every call; never persisted |
| Publication rows | `(project_id, manuscript_fingerprint)` | Content-bound | Assessments/approvals bind exact snapshot, never transfer |

No alias/canonical/fingerprint subsystem existed. No `Book.alias`, `canonical_id`,
or fingerprint columns anywhere. This milestone adds a resolution layer without
touching any of the above.

## 2. Canonical identity decisions

- **Canonical id = Mission `project_id`.** No new PK is introduced; every existing
  row keeps its keys, so assessments, approvals, QC evaluations, reviews,
  ALIVE links, goals, milestones and activity are untouched by definition.
- **Aliases live in the `settings` table** (`book_identity_aliases`, JSON list),
  following the established `scripts_migration_log_*` precedent. No schema
  migration, no new tables, no FK risk. Removal = delete the entry; history rows
  are never rewritten.
- **Resolution order:** exact Mission id → explicit alias → (never auto-merge)
  normalized suggestion. String normalization (`_`/`-`/case folding) only ever
  produces `candidate` entries. Similar titles never resolve. Shared repos never
  imply shared identity. Duplicate `(system, external_id)` mappings fail closed.
- **Writer ids are validated** against the live registry snapshot at save time;
  fabricated Writer ids are rejected.
- **Delete/rollback:** removing an alias restores the prior state exactly;
  nothing else references aliases, so there is nothing to cascade.

## 3. Reused infrastructure (nothing parallel built)

- `build_snapshot` hash semantics reused verbatim for `manuscript-v1`
  fingerprints (CRLF→LF, `file:sha` manifest) → directly comparable to stored
  assessment fingerprints.
- `refresh_freshness` remains the authority for assessment CURRENT/STALE; the
  Publishing summary adds an independent fingerprint cross-check, never a
  replacement verdict.
- Writer `source_digest` algorithm replicated exactly (frontmatter strip, no CRLF
  norm, `sha256:` prefix) for stored-run comparison; mismatch or absence leaves
  freshness `unknown`, never stale-by-default.
- Settings-table JSON precedent (`scripts_migration_log_*`, `DEFAULT_SETTINGS`).

## 4. Migration decisions

- **No migration in this milestone.** Rationale: the shared tree already carries
  an untracked `035_website_post_evaluations.sql` from another workstream while
  `test_migrations_and_seed.py` asserts `1..34` (fails with or without our
  changes — reproduced on a stash). Adding `036_*` now would collide with that
  workstream's numbering and deepen the drift. The alias store needs no schema.
- If a future milestone needs relational alias queries, allocate the next free
  number **after coordinating** with the websites workstream, and update the
  count assertion together with the migration in one commit.

## 5. Unresolved risks

- Writer fiction roots (`C:\books\<slug>`) vs Mission fiction roots
  (`C:\fiction-books\<slug>`): drift is reported, not healed. Healing belongs to
  Writer (registry edit) with author approval, not to Mission sync.
- `agent-architectures` has no manuscript anywhere: honestly `unavailable`.
- Proof freshness stays `unknown`: MATH01 binds formal artifacts, not manuscript
  passages; no passage mapping exists to compare against.
- Bookbuilder/Hugo freshness is comparison-only where copies exist; no
  deployment evidence exists anywhere observed.
- The three underscore/hyphen pairs remain `candidate` until the author confirms
  the suggested mappings via `POST /api/books/aliases` (`confirm: true`).
