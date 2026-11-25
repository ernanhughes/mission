# W7-CORRECTIVE-ACTION-TAXONOMY — Evidence first, code last

12 categories (§6), classifier `action_for_finding(kind, gap_class)`
in proposals.py + mirrored `actionForGap` in labels.ts (tested both
sides; 7 backend tests).

| Category | Trigger semantics |
| -------- | ----------------- |
| RECOVER_EXISTING_EVIDENCE | missing provenance (merge/push/claim gaps) |
| REPRODUCE_VERIFICATION | test report without execution record |
| RECOVER_OR_CONFIRM_REQUIREMENTS | no usable requirements; missing mandatory |
| INDEPENDENT_REVIEW | unresolved review findings |
| INVESTIGATE_SUSPECTED_DEFECT | contradicted/suspected defect (investigate, then decide) |
| CORRECT_CONFIRMED_DEFECT | only after investigation confirms |
| IMPLEMENT_MISSING_REQUIREMENT | only for verified-missing mandatory work |
| COMPLETE_INTEGRATION | missing integration |
| REEVALUATE_STALE_ASSESSMENT | stale freshness state |
| REQUEST_USER_DECISION | ambiguous / anything else (never guessed) |
| DEFER_WITH_AUTHORIZATION | authorized deferral path |
| NO_ACTION_REQUIRED | explicit non-action (recorded, not silent) |

Rules: a verification gap is never classified as a defect; code-change
categories require confirmed defects or verified-missing requirements;
the default for unknown input is REQUEST_USER_DECISION. The classifier
suggests; the human confirms (proposal creation accepts an override
category, validated against the closed set).
