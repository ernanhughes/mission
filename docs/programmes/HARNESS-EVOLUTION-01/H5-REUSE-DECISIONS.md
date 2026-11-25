# H5 reuse decisions

- Reuse Worker strategy catalogue, runtime/provider routing, WorkResult, H3 execution summary and ledgers. Add only opt-in `adaptive.v1`; A/B/C strategy definitions and digests remain unchanged.
- Reuse Mission Work Outcome as the future episode/outcome/evaluation authority. H5 makes no Mission runtime or database writes and creates no episode lifecycle.
- Reuse only bounded harness/policy concepts from Praxis; do not import its generic recovery loop after the documented no-fault false recovery. Writer JSON parsing remains domain-owned and is not imported.
- Keep candidate proposal, Worker action authority, independent evaluation, and Mission governance distinct. H5's deterministic normalizer and one schema-directed correction are fixed policy actions, not autonomous policy learning.
- Preserve unknown causation as `suspected_cause: null`; syntax/schema observations do not establish why a model produced them.
