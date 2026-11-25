# W8C-METADATA-PROPAGATION — Small metadata, existing channels

The envelope never enters model context as a blob. Propagation uses
channels that already exist:

- Worker: mission episode/requirement ids travel in the existing
  caller-supplied `task_id`/`episode_id` request fields
  (`caller_supplied_unverified` is the honest linkage state until the
  worker echoes them in its result/provenance — designed, not yet
  demonstrated live; §12 gate).
- Workbench: envelope id fits run/journal metadata (documented
  mapping; not yet written by any runner).
- AITest: linkage rows (receipt id ↔ work id) recorded in
  `wo_execution_links.test_receipt_ref` — manual today, no new writer.
- Mission-internal: envelope id is a first-class API resource
  (register/list/link/size); evaluation already joins requirement
  versions.

Context overhead: measured 671 bytes for the pilot envelope;
`envelope_size_bytes` endpoint proves metadata-only carriage
(`carries_conversation: false`). No prompt-caching impact (nothing is
injected), no window pressure. Where integration is unavailable, the
supported fallback is the explicit manual reference (recorded link),
exactly as W7 handoffs work.
