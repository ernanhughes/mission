+++
title = "The Jev Provocation"
date = '2026-10-05T09:00:00+01:00'
description = "What Jev's public contract actually says, reconstructed from the vendor's own documentation — and which of its seven properties, if any, is genuinely new."
weight = 2
draft = false
series = ["The Book of Jev"]
categories = ["AI", "Decision Models", "Programming Languages"]
tags = ["jev", "decision contract", "prior art", "confidence", "option scoring"]
lastmod = '2026-11-10'
+++
Chapter 1 ended with a question: the predicate cannot answer half the test split, so
what is the thing that handles the rest? The vendor's answer is a product. Before this
book builds anything, it owes you a careful reading of that product's contract — what
it promises, what it pointedly does not promise, and which parts, if any, nobody had
built before.

That last clause is the whole chapter. Everything Jev does arrives wrapped in the
claim that it is a new kind of model. The claim might be true. It is more likely to be
packaging. Packaging is not nothing — a good interface changes what gets built — but
packaging and discovery are different achievements, and confusing them is how a book
like this one lies to you. So: the contract first, from the vendor's own pages only;
then nine older mechanisms held up against it, one property at a time; then the
verdict, including the one place where the verdict went against the prediction.

## The contract, from the vendor's pages only

Everything in this section comes from TypeSafe's own documentation and launch post.
The independent guide at `jevmodel.org` says much the same
thing, but it states on its own footer that it is unaffiliated with TypeSafe, so it is
not a source for anything here. Vendor claims about speed, price and calibration are
recorded as claims, not repeated as facts. No live behavior was observed: this book had
no Jev API key, and every statement about what the service *does*,
as opposed to what its documentation *says*, is `NOT_OBSERVED`.

You send a **state** — the application data you already have — and a set of **typed
questions** about it. What comes back is typed values, never prose. That sentence is
the product.

A question has an **ID** you choose (it is not sent to the model; the answer comes
back under it), a **type**, **instructions** in plain language, and **criteria**. There
are three types, and the trio is worth stating exactly, because every later chapter
assumes it:

- **Choice** — which of these options? Returns the winner, a probability for each
  option, and a confidence number. Up to 255 options; beyond comfortable sizes the
  vendor describes a two-stage score-then-choose system.
- **Score** — which level? Criteria are an ordered array of 2 to 10 level descriptions,
  numbered from 0. Returns a score that *can land between levels* (their worked example
  returns 1.43 on a three-level rubric), a legend, a probability per level, and a
  confidence number.
- **Noul** — is this true? Returns a single probability from 0 to 1. No separate
  confidence: in the vendor's own words, "the number is the answer and the certainty
  in one."

Several questions share one request. Every question sees the same state and is
evaluated **independently and in parallel** — the docs say adding questions "barely
changes" response time and does not create "context-rot". And the docs prescribe a
discipline, not just an API: ask one snap judgment per question, decompose anything
multi-factor into separate questions, and **combine the answers with logic in your
code**. Weights live in your code, not in a prompt, so when priorities shift you change
a coefficient rather than rewriting prose. That paragraph is the closest the vendor
comes to stating this book's thesis for it, and it is doing real work in the chapters
on composition.

![Decision flow for Chapter 2](/images/books/jev/diagram-02-01.png)

Seven properties, then. One state. Typed questions. Bounded answers. Many questions per
request, parallel and independent. Probabilities on every answer. A separate
confidence statistic. Atomic questions composed in code. Call them P1 through P7; the
experiment below is organized around them, and the code in `src/arbiter/contract.py`
implements exactly this shape — with one deliberate difference recorded below. If you
read Language, you already have the shape of this: a typed question is a rung on the
Representation Ladder chosen in advance by the programmer, rather than one the model
climbs to while writing. Chapter 1 imported that idea; this chapter spends it.

## What the vendor pointedly does not promise

> **Wrong:** Jev returns typed output, so the answer must be right. The schema is a
> guarantee of correctness.
>
> **Correct:** The schema is a guarantee about the *string*. The vendor's own launch
> post separates checkable claims (speed, pricing, zero type errors) from bolder ones,
> calls its headline 193.6x/444.6x figures "on the higher end", admits the reference
> answers bias toward OpenAI and Anthropic models, and notes that the 0% type-error
> figure in its plots is "not empirical" — schema matching is guaranteed, so there is
> nothing to measure.

That honesty is worth naming because it is unusual in launch material, and because the
book's standard for the vendor is the vendor's own standard. Type safety means the
output cannot be malformed. It says nothing about whether the output is true. Every
time this book grades a decision against a label, it is testing the part the vendor
never promised.

There is a second non-promise hiding in the confidence formulas, and it is the most
interesting thing the vendor published. Confidence is *derived* — a statistic computed
from the answer's own probabilities, with the formula printed in the docs:

```python
def choice_confidence(probabilities: list[float]) -> float:
    n = len(probabilities)
    return (max(probabilities) - 1 / n) / (1 - 1 / n)
```

Even split is 0, certainty is 1. The score formula compares the probability-weighted
distance from the peak level against the same distance under an even spread, floored
at 0 — so probability on a neighboring level costs less than probability far away.
Nouls get no separate confidence; the suggested equivalent is |2p − 1|. Our
implementation reproduces the vendor's own worked numbers exactly (their 0.76 choice
example, their ~0.35 score example — verified in `selftest_ch02.py`). Publishing the
formula is what makes confidence checkable rather than mystical, and checkability is
the theme of Chapter 9. Whether the number *means* anything — whether 0.76 behaves
like 76% — is a calibration question, and calibration is Chapter 9's, not this
chapter's. Do not let the formula's exactness convince you the uncertainty is exact.
That confusion has a name, and Chapter 9 gives it a chapter.

## Nine older mechanisms, seven properties

The preregistration, written before any of this was built, predicted
that **no single element of the contract is new**, and that the combination — shared
state, typed question set, probabilities by default — is the packaging contribution.
The test is a table: nine prior mechanisms against the seven properties, 63 cells,
each cell carrying a citation or marked UNKNOWN. The table lives in
`examples/ch02-the-jev-provocation/table.py`, the acceptance check is executable
(`check_table` fails on an uncited cell), and the rows are in `results/ch02.jsonl`.

The nine: a fine-tuned classifier, zero-shot/NLI scoring, the Cobbe verifier, the
GenRM direct verifier, P(True) self-evaluation, constrained generation, LMQL, the
LLM-as-judge, and training-free option scoring from an off-the-shelf LLM (LLM2Jev).
The NLI row is UNKNOWN throughout — Chapters 5 and 6 own it, and this chapter does
not borrow their findings in advance.

Almost every property has a crowd of ancestors.
Typed questions and bounded answers (P2, P3) are covered four times over: P(True) gives distributions over labeled options and True/False reformulations (Kadavath et al., [arXiv:2207.05221](https://arxiv.org/abs/2207.05221)); constrained generation bounds any schema by construction (Willard et al., [arXiv:2307.09702](https://arxiv.org/abs/2307.09702)); LMQL declares answer kinds up front ([arXiv:2212.06094](https://arxiv.org/abs/2212.06094)); LLM2Jev takes choice/noul/score as its three canonical formats ([arXiv:2610.02076](https://arxiv.org/abs/2610.02076)).
Probabilities by default (P5) are older still — the Cobbe verifier outputs the probability a solution is correct ([arXiv:2110.14168](https://arxiv.org/abs/2110.14168)), and the GenRM direct verifier uses the likelihood of a single 'Yes' token as its score ([arXiv:2408.15240](https://arxiv.org/abs/2408.15240)).
That last one deserves a pause: option scoring over a two-option slate, trained with the ordinary next-token loss, published in 2024.
If you squint, Jev's choice primitive is GenRM's direct verifier with better marketing and a parallel sampler.
So the crowding is real, not rhetorical: P2 and P3 are covered four times over, P5's ancestors are older still, and the GenRM comparison is offered with a squint — a resemblance, not a demonstrated equivalence.

And then there is the paper that says the quiet part loudly. LLM2Jev's finding, read
in its §1, is that "modern LLMs are inherently effective decision models": an
off-the-shelf 4B model *matches community Jev-style models built on the same
backbone*, with no training, and fine-tuning gives diminishing or even negative
returns on capable models. If that holds up — this chapter relies on its findings and
method sections, not its full experiments — then "decision model" is an inference
recipe, not a model category. That is H1 wearing a paper's clothes, and Chapter 2
concedes it explicitly rather than burying it: nothing in the contract below required
training a new model.

## The result: six crowds, one empty column, one thin one

Six of the seven columns have prior art. The seventh does not.

**P6 — confidence as a separate, published, derived statistic — has no prior
mechanism among the nine.** Eight cells are ABSENT with citations, one (NLI) is
UNKNOWN. The sharpest ABSENT is the classifier's: Guo et al.'s temperature scaling
([arXiv:1706.04599](https://arxiv.org/abs/1706.04599), §4.2, eq. 9) defines the
"confidence prediction" as the max of the softened distribution itself. There is no
second statistic. Every other mechanism is the same story told differently: the score
*is* the probability (Cobbe, GenRM, P(True)), or no probabilities are returned at all
(constrained generation, LMQL), or the judge "do[es] not natively provide" calibrated
distributions (Rao & Callison-Burch, [arXiv:2609.29769](https://arxiv.org/abs/2609.29769),
abstract only).

Per the preregistered `what_would_refute`, a fully-absent-or-unknown column is a
discovery, not a gap — so the prediction was **partially refuted**, and the chapter
reports it as such. The honest reading: the genuinely distinctive thing in Jev's
contract may not be the typed values, the probabilities, or the parallel questions.
It may be the *published second number* — a vendor committing, in documentation, to
exactly how its certainty statistic is computed from its distribution, so that anyone
can check it. Whether that number is *calibrated* is untested here. A checkable
formula is not a true formula. But nothing else in the nine mechanisms even publishes
one, and that asymmetry is real.

The thin column is P4: one state, many questions, parallel and independent. Only
holistic LLM judging covers it — reading a whole rubric at once, which Rao's abstract
explicitly compares to Jev on this axis — and LMQL's multi-part prompting partially
does. Everything else answers one question per call. P4 is the closest thing to a
second distinction, and it is the outcome the prediction allowed for: the combination
may be the contribution even where the elements are not.

Two caveats travel with the verdict, because a table is only as honest as its gaps.
First, the NLI row is UNKNOWN throughout; if Chapters 5–6 find a published separate
confidence statistic in NLI scoring, claim P6 falls, and the ledger already records
the condition. Second, AnyJev — third-party, not one of the nine — ships level-gated
decisions with calibrated L2 heads and a `require="L1"` gate, which sits adjacent to
P6 and must be addressed before any novelty claim hardens. Chapter 7 builds option
scoring independently; Chapter 9 tests calibration directly.

<figure class="jev-figure">
  <a href="/images/books/jev/fig-02-1-seven-properties.svg" target="_blank" rel="noopener">
    <img src="/images/books/jev/fig-02-1-seven-properties.svg" alt="Seven cards, one per contract property. Five are marked prior art, one is thin, and P6, a separate published confidence, has no prior mechanism." width="1200" height="800" loading="lazy">
  </a>
  <figcaption><strong>Figure 2.1.</strong> Six of seven properties are crowded. P6 is the empty column and P4 is the thin one. Whether an empty column is a contribution or a decoration is the question the rest of the book tests.</figcaption>
</figure>

## The build: the contract as code

`src/arbiter/contract.py` is the specification side of the book's standing split —
specification, provider, runtime, evidence, action. Providers arrive in later chapters
and import it; they do not fork it. It implements the vendor shape exactly
(`DecisionRequest` with state, questions keyed by caller-chosen ids, and model;
`ChoiceAnswer`, `ScoreAnswer`, `NoulAnswer`; the confidence formulas verbatim) with
four recorded differences (`VENDOR_DIFFERENCES`): our names follow the book's
vocabulary rather than client/server; we validate what the vendor merely parses
(probabilities must sum to one, the winner must be the argmax, the score must be
in range); we do not model token usage (cost lives in `results/` rows, not in the
answer type); and our library and model line are called `arbiter` / Arbiter rather
than `Decider`, because AnyJev already ships a client class of that name.

Chapter 1's refund decision restated in the contract looks like this, and runs. This is
`examples/ch02-the-jev-provocation/demo_ch02.py`, complete. It imports Chapter 1's
tickets and this chapter's contract, builds one request that asks the same ticket two
questions (a yes/no probability and a two-way choice, the way the vendor's own triage
example asks several questions about one state), and prints what a provider would
receive. Nothing is sent anywhere.

```python
"""The Chapter 1 refund decision, restated in the Chapter 2 contract.

    python examples/ch02-the-jev-provocation/demo_ch02.py

Builds the same ticket state Chapter 1 measured and asks the same question two
ways — as a noul and as a two-option choice — the way the vendor's own triage
example asks several questions about one ticket. Nothing is sent anywhere; this
prints the request a provider would receive.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "examples/ch01-generate-vs-decide"))

from arbiter.contract import ChoiceQuestion, DecisionRequest, NoulQuestion  # noqa: E402
from tickets import BY_ID, render  # noqa: E402

ticket = BY_ID["t01"]

request = DecisionRequest(
    state=render(ticket),
    questions={
        "refund": NoulQuestion(
            id="refund",
            instructions="Should this ticket get an automatic refund?",
            criteria={
                "true": "Amount at most 50.00, purchase at most 30 days old, first refund",
                "false": "Anything else",
            },
        ),
        "route": ChoiceQuestion(
            id="route",
            instructions="Which team should handle this?",
            criteria={"billing": "Charges and payments", "returns": "Wrong or damaged items"},
        ),
    },
)

print(f"state chars : {len(request.state)}")
for qid, question in request.questions.items():
    print(f"question {qid}: {type(question).__name__}: {question.instructions}")
```

```text
state chars : 188
question refund: NoulQuestion: Should this ticket get an automatic refund?
question route: ChoiceQuestion: Which team should handle this?
```

The `noul` question carries optional `criteria` that say what `true` and `false` mean;
the `choice` question requires them. Both are part of the request and neither is
interpreted here, which is the point: the contract describes what is being asked, and a
provider decides how to answer it.

The demo imports Chapter 1's tickets rather than copying them. Later chapters import
this contract rather than copying it. That chain of imports is the book's actual
argument about composition, stated in code before it is stated in prose.

## What to carry forward

Three things. First, the contract: `DecisionRequest` in, `DecisionResult` out, every
number checkable against the answer's own distribution. Second, the table:
`planning/prior-art.md` now registers all nine mechanisms with what each contributes
and what each lacks, and every later chapter updates it instead of re-litigating it.
Third, the two live questions: **is P6 — the published second number — a real
distinction or a nicely documented decoration?** (Chapters 9 through 11 decide, by
testing whether confidence behaves like certainty), and **does anything in the
contract require a new model, or is it all an inference recipe on existing weights?**
(Chapters 7, 14, 15 and 28 decide, by building the recipe and measuring it).

## Limitations

- **No live behavior was observed.** Without a Jev API key, every statement about what
  the service does — as opposed to what its documentation says — is `NOT_OBSERVED`.
  The contract above is a reconstruction from public pages as of October 2026, and
  pages change.
- **Two sources are used narrowly.** LLM2Jev is cited for its findings and method, not
  its §4 experiments; Rao et al. only for its abstract.
- **The NLI row is UNKNOWN throughout.** Zero-shot classification and NLI scoring
  are deliberately left to Chapters 5 and 6. If they publish a separate
  confidence statistic, the P6 verdict falls.
- **AnyJev was not one of the nine.** Its level-gated decisions sit adjacent to P6
  and must be addressed before any novelty claim hardens.
- **The Red Hat benchmark is secondhand here.** Chapter 3 treats it directly.
- **Guo et al. is used narrowly.** Only §4.2 — enough for the classifier/P6 cell
  (eq. 9 defines confidence as max over softmax), not a general citation for
  calibration. Chapter 9 uses it in full.
- **Commenter claims are not findings.** Numbers from Hacker News comments
  (jev-sec-bench, Banking77) are never cited as results.

## What Chapter 2 leaves behind

- `src/arbiter/contract.py` — `DecisionRequest`, the three question types, the three
  answer types with strict validation, the vendor's confidence formulas verbatim,
  `parse_vendor_response`, and `VENDOR_DIFFERENCES`.
- `examples/ch02-the-jev-provocation/table.py` — the 63-cell table with its
  executable acceptance check.
- `examples/ch02-the-jev-provocation/run_ch02.py`, `selftest_ch02.py` (27 checks,
  **OBSERVED** passing), `demo_ch02.py`, `requirements.txt`, `README.md`.
- `planning/prior-art.md` — the mechanism register and the open threads.
- `results/ch02.jsonl` — 63 cell rows + 7 column rows.
- `evidence/ledger.md` — claims 2.1–2.21 with type and source.

What exactly did Jev discover? One sentence, defensible from the rows: **Jev packaged
typed, probabilistic, parallel questions with a published, checkable confidence
formula — six-sevenths of which existed, with the seventh, the published second
number, the one element none of the nine prior mechanisms provide.** What could not
be verified: every live behavior (no key); the NLI row (left to Chapters 5–6); the Rao
paper beyond its abstract; LLM2Jev's full experiments; and whether the confidence
formula is calibrated, which no published page establishes.

Chapter 3 asks the adversarial version of this chapter's question: granted the
contract is mostly packaging, did Jev's *implementation* beat the alternatives
anyway — and what does the Red Hat benchmark, which found it did not reliably do so,
actually show?
