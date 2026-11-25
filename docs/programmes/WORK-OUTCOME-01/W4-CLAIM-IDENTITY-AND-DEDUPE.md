# W4-CLAIM-IDENTITY-AND-DEDUPE — Statement ≠ claim ≠ occurrence ≠ verification

| Level | Identity | Dedupe rule |
| ----- | -------- | ----------- |
| Statement | `sha1(normalized text)` | cosmetic variants ("All tests passed" vs "  ALL TESTS passed ") merge for counting |
| Claim | statement + subject scope + source revision | evaluation unit; identical text on different commits/repos = different claims |
| Occurrence | claim + session/message locator | provenance preserved; all 1,202 rows retained |
| Verification | claim identity + evidence digest + method + evaluator | cached; repeat occurrences never re-trigger evaluation |

Implemented: `verify.claim_identity`, `UNIQUE(claim_id, method, evaluator)`
on `wo_claim_verifications`, `UNIQUE(input_digest, schema, prompt, extractor)`
on the shared extraction ledger. Dedupe is by factual context (scope +
revision), never wording alone — the W3 24× repeats collapse only where
scope and revision match. Conflicting claims (same subject, incompatible
assertions) are preserved side-by-side for semantic adjudication, never
merged. Qualified claims keep their qualifiers into verification
(`qualified` flag; unqualified-looking deterministic rows are explicitly
marked as unevaluated-for-qualification, not as unqualified).
