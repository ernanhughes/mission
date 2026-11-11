# EXPO-02 Calibration Report (provisional)

Passages: 46; semantically evaluated: 46; missing: 0.

## Approach comparison (UNCERTAIN excluded, provisional labels)

| Approach | n | TP | FP | FN | TN | Precision | Recall |
|---|---|---|---|---|---|---|---|
| deterministic-only | 37 | 3 | 4 | 5 | 25 | 0.429 | 0.375 |
| semantic-only | 37 | 1 | 2 | 7 | 27 | 0.333 | 0.125 |
| hybrid | 37 | 0 | 0 | 8 | 29 | None | 0.0 |

Deterministic false positives (flagged but provisionally clean): P04, P05, P06, P09
Deterministic false negatives (missed but provisionally positive): P16, P23, P30, P36, P46
Semantic false positives: P31, P37
Semantic false negatives: P01, P02, P03, P16, P23, P30, P36
UNCERTAIN (excluded): P07, P08, P21, P24, P26, P29, P35, P44, P45
Invalid evidence / provider errors: none

## Detector agreement (adjudicated subset with semantic result)

rule-vs-semantic agreement: 27/37
rule-positive rate: 7/37; semantic-positive rate: 3/37
hybrid blind spot (semantic-positive but rule-negative; reachable only via sampling, not screening): P31, P37, P46

## Semantic verdicts by provisional label

- EXPO_COMPRESSION: {'UNCERTAIN': 1, 'NO_ISSUE': 2}
- EXPO_INTERRUPTION: {'EXPO_INTERRUPTION': 1}
- NO_ISSUE: {'MIXED': 1, 'EXPO_COMPRESSION': 6, 'NO_ISSUE': 27, 'UNCERTAIN': 8}

Total input tokens: 167354; latency mean/max: {'n': 62, 'mean': 29.7, 'max': 169.6}

All labels provisional (implementer single-reviewer). UNCERTAIN excluded from P/R. No validated accuracy claimed; no thresholds retuned.