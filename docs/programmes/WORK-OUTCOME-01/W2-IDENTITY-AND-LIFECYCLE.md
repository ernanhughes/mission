# W2-IDENTITY-AND-LIFECYCLE — Stable ids, honest evolution

- **Identity**: task episodes `ep:task:<SLUG>`, chains `ep:chain:<root>`,
  clusters `ep:cluster:<member-digest>`, buckets `ep:unresolved:<project>`.
  All URL-safe (no slashes — fixed a 404 found by test). Re-runs recompute
  identical ids; association ids are `sha1(episode|type|target|method)`.
  Slug inputs are bounded alphabets (programme/task ids, session ids);
  truncation at 120 chars can collide only for ids identical in their first
  120 chars (impossible for distinct session ids; would merge only truly
  duplicate task spellings). Cluster ids rotate membership-dependently by
  design (old row supersedes). Known bound, accepted.
- **Lifecycle**: discover → attach → revise → (merge | split | supersede).
  Re-runs upsert (title/times/`source_digest`, `version+1`); new valid links
  insert-or-ignore; same-scope episodes absent from a new result become
  `superseded` (never deleted). Splits materialize as new child episodes with
  parent links (chain+task overlap case tested); merges keep the task id and
  record the event in run stats.
- **Replay/idempotence**: identical input → identical ids, zero new rows
  (tested at engine and service levels, plus live replay).
- **Programmes/stages**: parent links only on co-mention evidence with cycle
  rejection (`check_cycle` tested, including self-parent). No forced
  programme membership; no completion inference upward or downward.
- **History vs now**: event times on episodes, observation times on rows,
  `recon_version` per association; later evidence changes current
  understanding via new versions/validity flags, never by rewriting history.
