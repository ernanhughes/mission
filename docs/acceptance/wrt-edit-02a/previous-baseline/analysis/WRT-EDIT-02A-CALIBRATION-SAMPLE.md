# WRT-EDIT-02A — Calibration sample

Date: 2026-10-25

Purpose: prepare a **blind, independent human assessment** of real passages
before changing any Writer threshold. No scores were tuned and no manuscript was
edited.

## Sample design

- 44 real passages from the 7 accessible registered books.
- 222 chapters were available; selection deliberately over-samples the extremes
  and includes ordinary prose.
- 22 high-diagnostic, 13 medium-diagnostic, 9 low-diagnostic chapters.
- Categories:

| Category | Passages |
| --- | ---: |
| `ordinary_prose` | 12 |
| `long_dense` | 10 |
| `structured_teaching` | 8 |
| `fragmented_sequence` | 6 |
| `lexical_difficulty` | 3 |
| `code_adjacent` | 2 |
| `uniform_cadence` | 2 |
| `short_technical_explanation` | 1 |

Diagnostic strata are based on the **chapter-level minimum dimension score**, not
on a ground-truth assessment of the passage. A high-stratum chapter can still
contain ordinary prose; that is intentional.

## Files

| File | Use |
| --- | --- |
| `C:\Projects\mission\docs\acceptance\wrt-edit-02a\calibration-passages.json` | Full passage text, source metadata, category, chapter diagnostics, paragraph metrics |
| `...\calibration-blind-passages.csv` | Text-only packet for the reviewer; no book names or scores |
| `...\calibration-review-template.csv` | 44 blank assessment rows keyed by passage ID |
| This document | Protocol and sample map |

Give the reviewer only `calibration-blind-passages.csv` and
`calibration-review-template.csv`. Do not give them this document or
`calibration-passages.json` until the assessment is submitted; both contain the
diagnostic key. The blind CSV deliberately omits book, chapter, category and
Writer scores.

## Blind review protocol

The reviewer reads each passage without the Writer report and assigns:

| Field | Scale |
| --- | --- |
| `overall_readability_1_5` | 1 = very hard to read, 5 = very easy to read |
| `density` | `too_dense`, `appropriate`, `too_sparse` |
| `fragmentation` | `too_fragmented`, `appropriate`, `too_continuous` |
| `rhythm` | `too_uniform`, `appropriate`, `too_irregular` |
| `lexical_difficulty` | `low`, `moderate`, `high` |
| `structural_clarity` | `clear`, `mixed`, `unclear` |
| `genuine_issue` | `yes`, `no`, `unsure` |
| `notes` | Free text: what the passage is doing, whether the issue is real, and what context matters |

Recommended comparative question after each passage:

> Is this passage hard because of the prose, or because the excerpt is a
> fragment of a code-first, list-first or exercise-first explanation?

A second reviewer is useful, but not required for the first calibration pass.
Disagreement should be preserved, not averaged away.

## Sample map

| ID | Book | Chapter | Category | Stratum | Paragraph words | Lines |
| --- | --- | --- | --- | --- | ---: | --- |
| P01 | models-from-first-principles | The Model Inside the Model | code_adjacent | high | 2, 16 | 77–91 |
| P02 | models-from-first-principles | MR.Q — Building a Neural Quality Model From Two Embeddings | structured_teaching | high | 7, 6, 9 | 418–422 |
| P03 | models-from-first-principles | EBT — From One Score to Q, V, Policy and Advantage | fragmented_sequence | high | 9, 6, 10 | 14–32 |
| P04 | models-from-first-principles | HRM — Hierarchical Reasoning With Fast and Slow Recurrent State | long_dense | high | 26 | 259–259 |
| P05 | models-from-first-principles | Reasoning Is More Than Architecture — Where Extra Computation Lives | fragmented_sequence | high | 20, 6, 7 | 12–16 |
| P06 | models-from-first-principles | Inside Tiny: Residual Blocks, Attention and Sparse Autoencoders | ordinary_prose | high | 13, 15 | 12–28 |
| P07 | freestyle-cognition | 💡 What Just Happened? | fragmented_sequence | high | 15, 3, 4 | 19–27 |
| P08 | freestyle-cognition | 🧠 You Have the Tools | uniform_cadence | medium | 4, 6, 4, 10 | 64–80 |
| P09 | freestyle-cognition | Summary | fragmented_sequence | low | 18, 1, 14 | 14–52 |
| P10 | freestyle-cognition | 🧗 Coach Phase (Start of Session) | ordinary_prose | medium | 30, 28 | 12–71 |
| P11 | freestyle-cognition | A Reference Guide to Core Tools and Methods | structured_teaching | medium | 8, 42, 16 | 272–289 |
| P12 | freestyle-cognition | Step 1: Unified Agent Base Class | structured_teaching | high | 21, 1, 2 | 927–932 |
| P13 | cellular-automata-from-first-principles | The smallest useful model | structured_teaching | high | 5, 7, 12 | 42–50 |
| P14 | cellular-automata-from-first-principles | Start with a one-dimensional world | code_adjacent | high | 12, 7 | 11–20 |
| P15 | cellular-automata-from-first-principles | Binary entropy | long_dense | high | 61 | 131–131 |
| P16 | cellular-automata-from-first-principles | A seed becomes a full cell state | ordinary_prose | medium | 35, 27 | 28–61 |
| P17 | cellular-automata-from-first-principles | Damage the state, not just the image | ordinary_prose | medium | 32, 34 | 74–110 |
| P18 | cellular-automata-from-first-principles | Choose a system family | structured_teaching | high | 4, 19, 1 | 314–318 |
| P19 | advanced-agents-from-first-principles | Advanced Agents From First Principles 00: When Should You Use an Advanced Agent Architecture? | structured_teaching | high | 7, 7, 14 | 557–569 |
| P20 | advanced-agents-from-first-principles | The Problem: Architecture Accretion | long_dense | high | 38 | 1785–1785 |
| P21 | advanced-agents-from-first-principles | Which Advanced Agent Architecture Should You Use? | structured_teaching | high | 8, 6, 11 | 481–485 |
| P22 | advanced-agents-from-first-principles | What Happens When One Dependency Starts Failing? | fragmented_sequence | high | 11, 6, 8 | 13–17 |
| P23 | advanced-agents-from-first-principles | The Search Problem: “What Should I Build First in an AI Agent Platform?” | long_dense | high | 35 | 49–49 |
| P24 | advanced-agents-from-first-principles | You Probably Don't Need All of This | short_technical_explanation | high | 19, 1 | 12–14 |
| P25 | agent-architectures | What Is an LLM Agent? | ordinary_prose | medium | 26, 105 | 13–15 |
| P26 | agent-architectures | Structure Shapes Behavior | long_dense | high | 70 | 202–202 |
| P27 | agent-architectures | Handoff record | structured_teaching | low | 19 | 32–32 |
| P28 | agent-architectures | The ladder | lexical_difficulty | high | 38 | 32–32 |
| P29 | agent-architectures | Reproduce | ordinary_prose | low | 53, 32 | 11–22 |
| P30 | agent-architectures | What You Have Built | ordinary_prose | low | 35, 42 | 13–15 |
| P31 | programmer_ie | Your Brain Has Already Invented an Object | ordinary_prose | low | 66, 48 | 22–46 |
| P32 | programmer_ie | The Present Is Not the Past | long_dense | high | 108 | 268–268 |
| P33 | programmer_ie | One More Kind of Cell | fragmented_sequence | high | 17, 15, 15 | 20–26 |
| P34 | programmer_ie | Surely Loss Eventually Wins | ordinary_prose | low | 42, 33 | 14–16 |
| P35 | programmer_ie | Same Shape, Different Hidden State | long_dense | medium | 160 | 631–631 |
| P36 | programmer_ie | Failure Is Not One Thing | ordinary_prose | low | 42, 37 | 37–39 |
| P37 | language | Three joints | long_dense | medium | 151 | 55–55 |
| P38 | language | The pipe, and why it fails | long_dense | medium | 224 | 65–65 |
| P39 | language | The oldest interface is multimodal | uniform_cadence | medium | 58, 59, 59, 58 | 80–86 |
| P40 | language | The fixed page and its bargain | long_dense | medium | 175 | 56–56 |
| P41 | language | Context describes the present | ordinary_prose | low | 74, 82 | 12–14 |
| P42 | language | A goal does not authorise every intervention | ordinary_prose | low | 94, 67 | 12–14 |
| P43 | language | Six available inputs, not six necessities | lexical_difficulty | medium | 118 | 159–159 |
| P44 | language | A name for the residue | lexical_difficulty | medium | 127 | 13–13 |

## Important limitations

- A passage is not a chapter. The diagnostic stratum is chapter-level.
- Code, tables, headings and lists are excluded from metrics; several samples are
  deliberately code-adjacent or structure-heavy.
- Some chapters are short-form teaching formats where the prose stream is only a
  fraction of the chapter.
- No labels exist yet. Nothing here justifies a threshold change.
- The full `C:\books` collection is not represented because the registry is still
  stale.

## Next step

Collect independent labels, then run calibration experiments against those
labels. Do not tune thresholds against the diagnostic strata.
