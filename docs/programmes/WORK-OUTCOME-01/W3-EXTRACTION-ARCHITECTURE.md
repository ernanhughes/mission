# W3-EXTRACTION-ARCHITECTURE — Proposals, not truth

```
episode + signals + redacted excerpts
        │ (evidence packet ≤6 msgs × 800 chars + signal list; no full bodies)
        ▼
deterministic pre-pass (triage.py; user-role scan; claim patterns; task ids)
        │  substantive/ambiguous only
        ▼
governed model invocation (single route, §3; JSON-schema-validated output)
        │
        ▼
deterministic post-validation ──► reject (store run metadata + error only)
        │  (schema, known source ids, no fabricated quotes, authority rules,
        │   output caps, no tool/exec instructions)
        ▼ accepted
WoObjective / WoRequirement / WoClaim / WoEvidenceLink rows
+ WoExtractionRun ledger (input_digest × schema × prompt × extractor cache)
```

## Invariants

- Model output is an extraction *proposal*; rows are written only after
  post-validation passes. Rejected outputs persist as run metadata, never as
  requirements.
- Cache key `(input_digest, schema_version, prompt_version, extractor_id,
  policy_version)` — no paid repeat for unchanged inputs.
- Budget ledger is the same table (`cost_usd/tokens/latency` per run);
  hard stop at 20 invocations / $1 (whichever first) without new authorization.
- Staleness: new source observations bump episode `source_digest`; cached
  extractions compare digests and report stale instead of silently reusing.
- Prompt-injection containment: historical content is quoted evidence inside
  a fixed instruction envelope; outputs matching `tool|exec|commit|push|
  deploy` directives are rejected; extractor has no repository write scope.
- Redaction before submission (reuse `redact_secrets`); no secrets, env
  dumps, credentials, or unrelated private content leave the machine.
