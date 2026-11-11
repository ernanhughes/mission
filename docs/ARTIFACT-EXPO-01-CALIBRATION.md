# ARTIFACT-EXPO-01 — Detection Definition + Calibration (Stages 01/02/04)

## Detection definition (versioned)

- Family: `EXPOSITORY_OVERLOAD` (`expo-v1`).
- Subtype `EXPO_COMPRESSION`: a passage contains more conceptual material,
  distinctions, or explanatory steps than its structure makes comfortably
  comprehensible (multiple independent claims in one paragraph, several new
  concepts before an example, definition-in-comparison-in-exception, repeated
  purpose shifts, dense abstraction with no concrete anchor).
- Subtype `EXPO_INTERRUPTION`: the main explanation is repeatedly interrupted by
  qualification, defensive framing, methodological caveats, or rebuttal before
  the claim is established (result followed by what it does not prove,
  exceptions before the concept, repeated cautions, verification methodology
  inside an introduction, explanation-to-rebuttal shift).
- `MIXED`: both pressures exceed thresholds in the same unit.
- Explicitly NOT automatic proof: long sentences, negation, terminology,
  repeated words/openers, complex equations, legitimate limitations, deliberate
  pedagogical repetition. Existing detectors cover several of these; their
  outputs are supporting evidence only.

## Deterministic features (observations, not defects)

Sentence: word count, clause commas, relative clauses (who/which/that),
parentheticals, long-sentence runs (≥32 words).
Paragraph: word count, sentence count, distinct lexical concepts, propositional
density proxy, specialized-term concentration, concrete anchor (numbers, units,
code spans, figure/table/listing/example references — e.g. `2.7s`, `max_new_tokens`).
Qualification: negation counts, qualification phrases, contrast markers,
conditions/exceptions, consecutive defensive constructions
(`does not prove`, `must not be mistaken`, ...), rhetorical transitions.
Structural: consecutive abstract paragraphs, repeated comparison structures,
repetition across adjacent paragraphs, long stretches without concrete examples.

A deterministic report lists measured values (e.g. words 121, sentences 6,
qualification markers 4, contrast markers 3, possible repeated frame yes).
The semantic reviewer decides whether the difficulty is necessary or avoidable.

## Calibration experiment (honest MVP status)

Scope attempted: ~6 synthetic fixtures + Inference Ch01/39/43 pilot passages.
Labels: provisional (author-constructed), NOT human-validated. No claim of
validated detection accuracy is made.

### Deterministic-only (measured)

| Fixture | Expected (provisional) | Rule result (thresholds 5.0/2.5) |
|---|---|---|
| Ordinary prose | no overload | no flag (pass) |
| Dense multi-purpose para | flag compression | flagged `EXPO_COMPRESSION` (pass) |
| Premature caveat | flag interruption | flagged `EXPO_INTERRUPTION`/`MIXED` (pass) |
| Necessary qualification | allow either, candidate-only if flagged | flagged-or-clean both accepted (pass) |
| Pedagogical repetition | not automatic proof | candidate-only if flagged (pass) |
| Protected material (front matter/code/table/figure/shortcode) | never flag | no flag (pass) |
| Malformed/partial model output | invalid evidence | n/a (rule path) |
| Stale fingerprint | stale, never apply | n/a (pipeline rule) |

Pilot (rule only, `technical` profile):
- `01-chapter.md`: 3175 eligible words, 52 units, 4 mechanical candidates
  (3 HIGH compression L12-20/20-32/32-39 + 1 LOW L41), mechanical pressure 1.26,
  confirmed 0, coverage 100% mech / 0% sem.
- `39-chapter.md`: 5345 words, 47 units, 5 candidates, pressure 2.06.
- `43-chapter.md`: 3845 words, 39 units, 6 candidates, pressure 3.90.

False-positive controls present (ordinary + protected + necessary-qualification).
False-negative controls present by design: low-pressure spot-check escalation
(`expo_spot_check`) is implemented but no semantic campaign has run, so the
false-negative rate is currently unmeasured.

### AI-only and hybrid (pending)

Not run. The hybrid path (`_should_escalate_to_llm`, `prompt_template` with
`NO_ISSUE` allowed, quote verification, `INVALID_EVIDENCE` on mismatch) is
implemented and unit-testable with a fake runner, but no bounded Pi-model
campaign has executed. Therefore no precision/recall, agreement, token, or cost
numbers are reported. The detector is marked experimental/review-only for
semantic confirmation until a 40–60 passage reviewed benchmark with explicit
rationales exists.

### Decision

Both subtypes ship as deterministic screening + review-only semantic:
- `EXPO_COMPRESSION`: useful mechanical signal on pilot + fixtures.
- `EXPO_INTERRUPTION`: useful mechanical signal on fixtures; pilot chapters show
  low interruption pressure (0.3–2.1) vs high compression (5.4–14.2), consistent
  with the motivating passage being compression-dominant.
- Neither subtype is declared reliable for confirmed defects. Do not tune
  thresholds on a held-out set until one exists.
