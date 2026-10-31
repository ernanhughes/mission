# WRT-EDIT-02A — Cross-book readability baseline

Date: 2026-10-25

Scope: the **7 editing-eligible registered books** actually reachable under the
current registry (222 chapters). This is not the full `C:\books` collection,
because the registry relocation has not happened. See
[WRT-EDIT-02A-REGISTRY-AUDIT.md](WRT-EDIT-02A-REGISTRY-AUDIT.md).

No thresholds were changed. No manuscripts were written or corrected.

## Audit run

| Project | Report | Chapters | Findings | High/medium |
| --- | --- | ---: | ---: | ---: |
| `models-from-first-principles` | `edit-20261025T011838291414Z-4e6d97366df1` | 12 | 49 | 36 |
| `freestyle-cognition` | `edit-20261025T011837040957Z-352dfd8d7ed3` | 32 | 84 | 56 |
| `cellular-automata-from-first-principles` | `edit-20261025T011835410154Z-64441f163d7a` | 59 | 163 | 126 |
| `agent-architectures` | `edit-20261025T011833303053Z-cbc9b7adffc9` | 16 | 29 | 19 |
| `advanced-agents-from-first-principles` | `edit-20261025T011832619658Z-54162b204174` | 46 | 184 | 138 |
| `programmer_ie` (Digital Life content) | `edit-20261025T011827648495Z-8f2d619cfed3` | 19 | 48 | 24 |
| `language` | `edit-20261025T011826244809Z-4c44a9e02cc3` | 38 | 56 | 43 |
| **Total** | | **222** | **613** | **442** |

Severity distribution: **143 high, 299 medium, 164 low, 7 info**. The info
entries are the mandatory `READABILITY.METRIC_LIMITATION` record per book.

## Coverage comparison

```text
previous MC-WRITER-01 baseline: 7 audited, 21 blocked, 1 no manuscript
WRT-EDIT-02A after relocation:  7 audited, 21 blocked, 1 no manuscript
```

The relocation did not increase audit coverage because the registry still points
to `C:\Projects`. This is an operational blocker, not a Writer measurement result.

## Findings by rule

| Rule | Count | Books where present |
| --- | ---: | --- |
| `READABILITY.FRAGMENTATION` | 168 | all 7 |
| `READABILITY.UNIFORM_CADENCE` | 136 | all 7 |
| `READABILITY.TRIVIAL_SECTION` | 132 | all 7 |
| `READABILITY.HEADING_DENSITY` | 120 | all 7 |
| `READABILITY.PARAGRAPH_DENSITY` | 30 | 1 of 7 (Language only) |
| `READABILITY.LONG_SENTENCE` | 11 | 4 of 7 |
| `READABILITY.LEXICAL_DIFFICULTY` | 9 | 2 of 7 |
| `READABILITY.METRIC_LIMITATION` | 7 | all 7 |

## Dimension distribution

222 chapters. Bands are `good / watch / review / high / not_applicable`.

| Dimension | Good | Watch | Review | High | N/A | Median score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Paragraph load | 209 | 12 | 0 | 0 | 1 | 100 |
| Sentence load | 221 | 0 | 0 | 0 | 1 | 100 |
| Fragmentation | 52 | 11 | 10 | 136 | 13 | 0.0 |
| Rhythm | 101 | 13 | 96 | 0 | 12 | 79.1 |
| Lexical accessibility | 204 | 12 | 4 | 1 | 1 | 100 |
| Section structure | 138 | 21 | 19 | 44 | 0 | 94.8 |

### What stands out

1. **Fragmentation dominates the corpus.** 136 of 209 scored chapters are high,
   and 168 fragmentation findings are recorded. Models, cellular automata and
   advanced agents have chapters with 99–100% short, one-sentence paragraphs.
2. **Rhythm is the second large signal.** 96 chapters are in review and 136
   uniform-cadence findings occur. This heavily overlaps fragmentation in the
   same books.
3. **Sentence load is almost entirely clean.** No chapter is in review/high by
   sentence score; only 11 long-sentence findings occur.
4. **Paragraph load is not a cross-book crisis.** 209/222 chapters are good;
   12 are watch (all Language) and none are high.
5. **Section structure is noisy and likely format-sensitive.** 44 chapters are
   high, driven by 120 heading-density and 132 trivial-section findings, mostly
   in books with many short teaching headings.
6. **Lexical difficulty is rare.** 9 findings, 4 review chapters, 1 high chapter.
   Language carries 8 of the 9 lexical findings.

## Book-level observations

### Language

- 56 findings, 43 high/medium.
- Dominant rules: paragraph density (30), heading density (11), lexical
  difficulty (8), long sentence (3).
- Paragraph load: 12 watch-level chapters, no high band; longest paragraph
  224 words.
- Fragmentation: only one high chapter (`Memory can be right and still make the
  present wrong`, 29.3). Rhythm: one review chapter. Section structure: 97.3
  worst score, still in the good band.
- This is a **density and lexical-load** book more than a fragmentation book.

### Models From First Principles

- 12 chapters, 49 findings, 36 high/medium.
- Fragmentation, uniform cadence, heading density and trivial sections occur in
  all 12 chapters.
- Median paragraph length per chapter is 5–7 words; several chapters have
  99–100% one-sentence paragraphs. 4 chapters have section-structure scores
  below 10 with 67–159 sections.
- This may describe a deliberate code-first teaching format, but the current
  parser/scorer treats it as severe fragmentation and structural overload.

### Advanced Agents From First Principles

- 46 chapters, 184 findings, 138 high/medium.
- Fragmentation, heading density and uniform cadence occur in 46/46 chapters.
- The text is highly modular and list/code-heavy; section-structure scores are
  often review/high.
- This is the largest single contributor to the raw finding count.

### Cellular Automata From First Principles

- 59 chapters, 163 findings, 126 high/medium.
- Fragmentation in 59/59; uniform cadence in 58/59.
- 7–40 code fences per chapter (median 17) and many short teaching steps.
- Section structure is less severe than models/advanced (55.7 worst), suggesting
  a different heading strategy.

### Freestyle Cognition

- 32 chapters, 84 findings, 56 high/medium.
- Fragmentation in 22 chapters; trivial sections in 25; heading density in 18.
- Some chapters are genuinely different in kind (prompts, logs, checklists,
  appendices); one has no prose paragraphs at all. Coverage is uneven.

### Agent Architectures

- 16 chapters, 29 findings, 19 high/medium.
- Fragmentation in 12; 1 lexical high (`The ladder`, FRE 0.29 on a very short
  38-word prose sample).
- The lexical outlier is likely a small-sample/technical-term artifact, not a
  general lexical verdict for the book.

### Programmer.ie (Digital Life content)

- 19 chapters, 48 findings, 24 high/medium.
- Fragmentation in 16; 5 long-sentence findings; only 1 uniform-cadence finding.
- This is the closest accessible proxy for the “Digital Life fragmentation”
  hypothesis, and the signal is present. It is not unique to Digital Life.

## Highest-risk chapters

Selection: the two chapters per book with the lowest minimum dimension score
among chapters carrying at least one high or medium finding; ties are broken by
chapter order.

| Book | Chapter | High/medium | Lowest score | Flags |
| --- | --- | ---: | ---: | --- |
| models | The Model Inside the Model | 3 | 0.0 | fragmentation high, rhythm review, section high |
| models | MR.Q — Building a Neural Quality Model From Two Embeddings | 3 | 0.0 | fragmentation high, rhythm review, section high |
| freestyle | 🎯 Goal of this Chapter | 3 | 0.0 | fragmentation high |
| freestyle | 📘 Summary | 3 | 0.0 | fragmentation high |
| cellular | The smallest useful model | 3 | 0.0 | fragmentation high |
| cellular | Rule numbers are lookup tables | 3 | 0.0 | fragmentation high |
| agent | The Goal | 3 | 23.8 | fragmentation high |
| agent | Structure Shapes Behavior | 2 | 26.7 | fragmentation high |
| advanced | Advanced Agents … 00 | 3 | 0.0 | fragmentation high, rhythm review, section review |
| advanced | The Search Problem: Why Does My AI Agent Fail… | 3 | 0.0 | fragmentation high, rhythm review, section high |
| programmer_ie | The Rule Was Searched. The Replicator Wasn't. | 3 | 0.0 | fragmentation high, long sentence |
| programmer_ie | Too Far Away to Matter | 2 | 0.0 | fragmentation high |
| language | Memory can be right and still make the present wrong | 1 | 29.3 | fragmentation high |
| language | Five stages, five separate permissions | 2 | 47.9 | lexical review, density |

## Likely parser/threshold artifacts

1. **List/code-heavy chapters are scored on a thin connector-prose sample.**
   The parser excludes headings, lists, tables and code. A chapter with 400
   short paragraphs and 3,000 words can therefore produce a fragmentation score
   of zero even if the chapter is a legitimate tutorial. This is the leading
   explanation for the extreme models/cellular/advanced results.
2. **Section-structure penalties are format-sensitive.** 6 chapters with 50+
   sections score zero. Technical books deliberately use many small headings,
   prompts, exercise steps and tables. The metric currently cannot distinguish
   useful navigation from excessive fragmentation of sections.
3. **Uniform cadence overlaps list-driven teaching.** Short instructions and
   one-line steps create a narrow paragraph distribution. That can be genuine
   staccato writing, or simply the wrong unit of analysis.
4. **`The ladder` lexical score is a small-sample outlier.** One 38-word prose
   paragraph produced FRE 0.29 and FK 16.37. A minimum prose sample size is
   needed before lexical scoring is allowed to drive a review band.
5. **Language’s paragraph density is real but only watch-level.** 30 density
   findings with 12 watch chapters; do not conflate this with the severe
   fragmentation pattern in the teaching books.

## Genre comparison

Not possible with current coverage. All 7 audited books use the `technical`
profile. The fiction projects (Latent, Coin, Softwear, Axiom Zero, Becoming
Alice, Collapse, Goblins, Techno Prophet, Projection) are all blocked, and
`C:\books` is not registered. No claim about fiction readability can be made.

## Hypothesis result

- **Language density hotspots:** partially supported as watch-level density and
  lexical load; no high paragraph-load chapter.
- **Digital Life fragmentation:** supported for the 19-chapter Digital Life
  content, but fragmentation is **not unique** to it.
- **Other books acceptable with local hotspots:** not supported. Every
  accessible technical book has high fragmentation or structural findings.
- **Embeddings, Context, Debugging AI, Hallucination:** unavailable; hypothesis
  untested.
- The strongest finding is operational: the full-collection audit is still
  blocked by the stale registry, not by Writer.

## Recommended calibration experiments

1. **Registry-relocation validation** — reviewed explicit mapping from old
   `C:\Projects` paths to `C:\books`; do not infer. Re-run the audit only after
   every configured content path resolves to a real chapter tree.
2. **Blind human scoring of the 44 passages** in
   [WRT-EDIT-02A-CALIBRATION-SAMPLE.md](WRT-EDIT-02A-CALIBRATION-SAMPLE.md).
   Collect labels before changing thresholds.
3. **Structured-format guard** — measure prose sample size and list/code/table
   density. Mark readability dimensions `not_applicable` or lower-confidence
   when the prose sample is too small.
4. **Fragmentation threshold experiment** — compare current thresholds against
   labels for genuine staccato prose, tutorial steps and normal transitions.
5. **Section-structure experiment** — treat heading/list/table structure as a
   distinct navigation dimension, not a prose defect.
6. **Minimum lexical sample** — require a configurable minimum word count before
   Flesch scores can generate review/high bands.
7. **Production-process question** — if the same fragmentation signature survives
   calibration across multiple books, investigate the generation/formatting
   process once rather than opening dozens of per-chapter edits.

## Limitations

- Heuristic, chapter-level measurements only; no passage-level ground truth.
- Only 222 chapters from 7 accessible technical books.
- Registry still points at `C:\Projects`; `C:\books` is not audited. These results
  therefore describe the registered `C:\Projects` copies, not necessarily the
  relocated copies under `C:\books`; the two were not compared.
- Technical prose, code, lists, tables and generated teaching formats dominate
  the accessible sample.
- Flesch scores are approximate and distort proper names/technical vocabulary.
- All books are `NEEDS_REVIEW`; that is not a literary-quality verdict.
- No thresholds, parser rules or manuscript text were changed.

## Evidence

Raw evidence: `C:\Projects\mission\docs\acceptance\wrt-edit-02a\`

- `registry-audit.json`
- `cross-book-analysis.json`
- `summary-before.json`
- `audit-all.json`
- `summary-after.json`
- `manuscript-hashes-before.json`
- `manuscript-hashes-after.json`
- `mission-writer-workspace.json`
- `writer-live-after-audit.png`
