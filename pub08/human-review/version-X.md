+++
title = "Stop Generating"
date = '2026-10-05T09:00:00+01:00'
description = "When software needs one bounded value, what does it cost to get it by generating prose? A measured baseline before any decision model appears."
weight = 1
draft = false
series = ["The Book of Jev"]
categories = ["AI", "Decision Models", "Programming Languages"]
tags = ["decision models", "structured output", "constrained generation", "baselines"]
lastmod = '2026-11-10'
+++

Most systems that answer a question with a language model do the same thing: they ask the model to write some prose and then read one value out of it.

(Not all do. Some read a constrained token or a score directly, which is the subject of Chapter 7, and this chapter's measurement is the cost of the common path.)

Sometimes the prose is a sentence, sometimes it is JSON, sometimes it is a single word followed by four paragraphs of explanation.

The value is what the application wanted. The prose is packaging.

This chapter measures the packaging. Not philosophically — with a stopwatch and a token counter.

The question is narrow on purpose: when a program needs one bounded value, what does it cost to obtain that value by generating prose?

The answer is a number, and the number is the whole basis for everything the rest of this book tries to build.

There is a reason to start here rather than with the interesting question.

The claim that made decision models visible is that they are faster and cheaper than generation for exactly this kind of work.

Before accepting that, we owe the reader a floor: what does the *existing* way cost, and how good is it already?

If generation is already cheap enough and accurate enough, then a decision model has to beat something real, not a straw man.

If generation is expensive, we need to know by how much, because that number sets the bar.

The generate-then-parse loop is assumed here, not taught: it is the loop described in Agent Architectures, where a model emits text and the surrounding program reads values back out of it.

And "a bounded value" is a rung on the Representation Ladder from Language — a rung chosen by the programmer in advance, rather than one the model climbs to while writing.

Both are imported by name; neither is re-explained.

## The application

Pick one decision and commit to it: **should this support ticket get an automatic refund?**

The value the application consumes is a single boolean, read by a function that knows nothing about how the answer was produced:

```python
def handle_ticket(ticket: Ticket, refund_approved) -> str:
    """Apply the policy's outcome.

    `refund_approved` may be a plain bool (the predicate) or an object with
    `.value` and `.ok` (a decision). It may not be None-with-no-explanation: if the
    provider cannot decide, it must say so, and this function refuses a silent
    default rather than inventing one.
    """
    value = getattr(refund_approved, "value", refund_approved)
    if value is None:
        return f"escalated {ticket.id} to a human"
    return issue_refund(ticket) if value else f"declined {ticket.id}"
```

That is the whole contract. One bounded value, read once, by code that never inspects anything else the provider might have said.

The `reason` string that real systems routinely ask for goes to a log file.

Keeping it in our schema is deliberate: we want to charge the application for output it does not read.

> Approve automatically if the customer asks for no more than 50.00, the purchase is at most 30 days old, and this is their first refund in the last year. Anything else goes to a human.

## Path 1: the predicate

Write that policy as ordinary code first.

This is not a formality.

If the reader never sees what `if` already provides for free, every later number is being compared against an idea rather than against code.

```python
def predicate_decides(ticket: Ticket) -> bool:
    """True when the policy can answer this ticket without judgement."""
    return (
        ticket.amount <= 50.00
        and ticket.days_since_purchase <= 30
        and ticket.prior_refunds == 0
    )


def predicate_decide(ticket: Ticket) -> bool | None:
    """The predicate's answer, or None when the policy sends it to a human."""
    if not predicate_decides(ticket):
        return None
    return True
```

This is the whole of `examples/ch01-generate-vs-decide/tickets.py` as far as the decision is concerned.

Two functions, no model, no prose, no parsing, and — the part that matters most — an honest third answer.

`None` means *the policy does not cover this case*.

That value is not a failure of the predicate.

It is the predicate correctly declining to guess, and any baseline that cannot express it is being quietly flattered by the evaluation.

**Correction from Book Quality Lab (CAPSTONE-02B).** The earlier implementation also tested the channel after accepting a ticket as in-policy.

That extra condition was absent from the runbook: it could decline an eligible phone request.

The predicate above now approves every eligible ticket and escalates everything else.

The original measurements remain in `results/ch01.jsonl`; the correction, boundary checks and source hashes are recorded separately in `results/ch36-capstone02b-policy.jsonl`.

The displayed walkthrough still matches the existing case set; it did not contain the counterexample that exposed this implementation error.

**OBSERVED.** On the `test` split (20 cases), the predicate answered 10 and returned `None` on the other 10.

On the 10 it answered it was correct 8 times.

It generated zero tokens and every call took under 4 microseconds (`results/ch01.jsonl`, seed 0).

Both errors are worth naming, because they are not noise: `t11` ("Saw it cheaper yesterday") and `t60` ("Not asking for anything, but if you did, I would take it").

Both are inside the written policy and both are labelled "decline" in this case set, which was written by hand (see Limitations: the labels are not ground truth from a real queue).

The policy as written does not cover a price-drop request or an ambiguous ask.

The predicate is faithfully executing a rulebook that has a hole in it.

A model would get these "right" by having absorbed conventions the runbook never states, which is either better or worse depending on whether you can tell which one you are getting.

That distinction — *the rule was followed* versus *the outcome was sensible* — is the first thing this book has to keep separate, and it is why the harness records `agrees_with_predicate` separately from `correct`.

### Run it

Everything so far has been excerpts.

Here is the whole path from state to caller, runnable as it stands.

The state is a `Ticket`, and `render` is the exact text every model-backed provider will later be shown:

```python
@dataclass(frozen=True)
class Ticket:
    id: str
    subject: str
    body: str
    amount: float          # refund amount requested, in the store currency
    days_since_purchase: int
    prior_refunds: int    # refunds already taken on this account in the last year
    channel: str          # "chat" | "email" | "phone"
    label: bool           # the answer the ticket's own outcome turned out to have
    house_style: str = "plain"
    notes: str = field(default="", repr=False)


def render(ticket: Ticket) -> str:
    """The exact text every model-backed provider sees. Identical across providers."""
    return (
        f"Subject: {ticket.subject}\n"
        f"Message: {ticket.body}\n"
        f"Refund requested: {ticket.amount:.2f}\n"
        f"Days since purchase: {ticket.days_since_purchase}\n"
        f"Refunds on this account in the last year: {ticket.prior_refunds}\n"
        f"Channel: {ticket.channel}"
    )
```

Then `examples/ch01-generate-vs-decide/walkthrough_ch01.py` runs the real case set through the predicate and the caller.

It needs no model and no network, and it recomputes the figures quoted above from the code:

```python
from application import handle_ticket
from tickets import BY_ID, predicate_decide, render, split


def main() -> None:
    # 1. The state the application already has, exactly as a model would be shown it.
    ticket = BY_ID["t01"]
    print("1. one ticket, as every model-backed provider would see it")
    for line in render(ticket).splitlines():
        print(f"   {line}")

    # 2. The predicate answers, or honestly declines, and the caller never asks how.
    print("2. the predicate and the caller, on six tickets")
    print("   id   amount  days  prior  predicate  label  caller does")
    for tid in ("t01", "t06", "t21", "t11", "t60", "t30"):
        t = BY_ID[tid]
        answer = predicate_decide(t)
        shown = "None" if answer is None else str(answer)
        print(f"   {tid}  {t.amount:>6.2f}  {t.days_since_purchase:>4}  {t.prior_refunds:>5}  {shown:<9}  {str(t.label):<5}  {handle_ticket(t, answer)}")

    # 3. The two tickets the chapter names: inside the written policy, labelled 'decline'.
    print("3. two tickets where the rule was followed and the outcome was not sensible")
    for tid in ("t11", "t60"):
        t = BY_ID[tid]
        print(f"   {tid}: {t.subject!r} -> predicate {predicate_decide(t)}, label {t.label}")

    # 4. The figures the chapter quotes, recomputed from the test split.
    test = split("test")
    answered = [t for t in test if predicate_decide(t) is not None]
    right = [t for t in answered if predicate_decide(t) == t.label]
    print(f"4. the test split ({len(test)} tickets), recomputed")
    print(f"   predicate answered {len(answered)} and declined {len(test) - len(answered)}")
    print(f"   of the {len(answered)} it answered, {len(right)} match the label")
    errors = sorted(t.id for t in answered if predicate_decide(t) != t.label)
    print(f"   the errors: {errors}")
```

```text
1. one ticket, as every model-backed provider would see it
   Subject: Refund for order 8841
   Message: Item arrived two days ago and does not fit.
   Refund requested: 12.00
   Days since purchase: 2
   Refunds on this account in the last year: 0
   Channel: chat
2. the predicate and the caller, on six tickets
   id   amount  days  prior  predicate  label  caller does
   t01   12.00     2      0  True       True   refunded 12.00 for t01
   t06   47.20     4      0  True       True   refunded 47.20 for t06
   t21  480.00     6      0  None       True   escalated t21 to a human
   t11   49.00    14      0  True       False  refunded 49.00 for t11
   t60   45.00    24      0  True       False  refunded 45.00 for t60
   t30  3000.00   540      3  None       False  escalated t30 to a human
3. two tickets where the rule was followed and the outcome was not sensible
   t11: 'Price drop' -> predicate True, label False
   t60: 'Refund, mixed signals' -> predicate True, label False
4. the test split (20 tickets), recomputed
   predicate answered 10 and declined 10
   of the 10 it answered, 8 match the label
   the errors: ['t11', 't60']
```

Three things to read off the output.

- **Row `t21`:** a 480.00 refund is outside the written policy, so the predicate returns `None` and the caller escalates to a human. The predicate did not fail; it declined, and the caller has an explicit place for that.

- **Rows `t11` and `t60`:** inside the policy, answered `True`, and labelled "decline" in the case set. These are the two errors discussed above, and the figures (10 answered, 10 declined, 8 correct) are the ones quoted at the start of this section.

- **Row `t30`:** the policy again declines, and the label says declining was right. Both columns agree, which is the case where a deterministic rule earns its keep.

The model-backed paths are deliberately absent. They need local weights, and the next sections describe what they will measure.

## Paths 2 and 3: generate, then parse

Now the familiar path.

Same ticket, same policy, same information — but the answer arrives as text and has to be recovered.

The prompt is identical for both model-backed paths, which matters: any difference between them is attributable to the decoding constraint, not to a differently worded request.

```python
PROMPT_TEMPLATE = """\
You are handling a customer support ticket.

{ticket}

Decide whether the refund should be approved automatically.
Policy: approve if the amount is at most 50.00, the purchase is at most 30 days old,
and this is the first refund on the account in the last year.
Reply with JSON only, in exactly this shape:
{{"refund_approved": true or false, "reason": "one short sentence"}}
"""
```

**Path 2, free-form.** Decode normally, then run the recovery step every codebase has: a regex to find the first `{...}`, then `json.loads`, then validate.

**Path 3, schema-constrained.** Same prompt, same model, but the vocabulary is masked during decoding so that every token which would take the output outside the schema's language is disallowed.

This is the mechanism Willard et al. describe in *Efficient Guided Generation for Large Language Models* ([arXiv:2307.09702](https://arxiv.org/abs/2307.09702)): guided generation reformulated as transitions between the states of a finite-state machine, with an index built over the model's vocabulary so the set of admissible tokens can be fetched cheaply. **DOCUMENTED.**

Two details from their §1 and §5 earn their place here.

The obvious implementation — score the whole vocabulary each step and zero out the inadmissible tokens — costs O(N) per token with N the vocabulary size, which they note is often 10^4 or larger; the indexed version is O(1) on average.

And the index is not free: even naively built for an augmented Python grammar, they report it at "around 50 MB".

Constraint is a memory cost before it is a compute win.

The guarantee is worth stating precisely, because it is routinely overclaimed.

Their abstract says constrained decoding enables "reliable interfaces by guaranteeing the structure of the generated text".

**Structure**, not correctness.

Constrained decoding guarantees the *string* is well-formed.

It guarantees nothing about whether the string is the right string — and the rest of this section is about how much it can cost you.

Tam et al., *Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models* ([arXiv:2408.02442](https://arxiv.org/abs/2408.02442)), is the paper that attacks this chapter's comfort, and reading it changed the chapter twice. **DOCUMENTED.**

Their §5.3 kills the prediction this chapter made.

They began from the same hypothesis we preregistered — that the gap between prose and structured output is caused by parsing errors — tested it, and found it is not the main factor: Gemini 1.5 Flash and GPT-3.5 Turbo showed *near-zero parsing failures in all three formats*, and on LLaMA 3 8B the JSON parse-error rate on one task was 0.148% against a 38.15-point performance gap.

If our run finds no parse failures, the honest report is that our own hypothesis was wrong, and this paper is why we expected it to be.

Their §4.1 found something sharper: in 100% of GPT-3.5-turbo JSON-mode responses the "answer" key came *before* the "reason" key, which collapsed chain-of-thought into direct answering and cost accuracy.

Our preregistered schema asks for `refund_approved` first and `reason` second — the exact ordering they identify as harmful.

We found that by reading, before running anything.

The schema was not quietly edited: a second, reason-first variant was added and both are run, so the ordering becomes a measured factor instead of an assumption.

That costs an extra arm, and the change is recorded as a dated amendment to the preregistration.

Their §5.4 is the finding that should worry a decision-model enthusiast most.

With a CFG-constrained output guaranteeing 100% adherence, plain natural language still beat the constrained format on 2 of 3 reasoning datasets.

A guarantee about the string is not a guarantee about the answer.

And their §4.1 cuts the other way too, which is why this is a real trade-off and not a refutation of structured output: on *classification* tasks, constraint can help, because it removes answer-selection errors that free-form text invites.

Refund approval is a classification task.

We may find constraint helps.

We will not know until we run it.

Note also what this chapter is *not* doing.

Constrained generation, schema enforcement, and query languages for models all predate the current argument — and the arithmetic is already published.

LMQL, *Prompting Is Programming: A Query Language for Large Language Models* ([arXiv:2212.06094](https://arxiv.org/abs/2212.06094)), is a query language whose stated purpose is to stop generation at the moment a value is complete; its evaluation reports cutting inference cost and latency by 26-80% while retaining or slightly improving accuracy. **DOCUMENTED**, from its framing and that headline figure; its runtime and evaluation sections are not relied on here.

Willard et al.'s implementation is the Outlines library.

So: the idea that a model call should return a typed value rather than a paragraph is not new, the cost reduction is already on the record, and this book gets to claim none of it.

What Chapter 1 is doing is narrower and still worth doing: measuring the overhead on one concrete application, against a predicate that costs nothing, with the failures counted rather than smoothed.

## Path 4: ask for the value and nothing else

The fourth path generates nothing.

It reads the model's answer to the question directly, which is what the rest of this book is going to build.

```python
class DecideStubProvider:
    """Path 4, deliberately a stub.

    Chapter 7 replaces this with a real option-scored reader that produces the
    label without decoding it. Until then it returns nothing, which is the honest
    state of the art in this repository. It is not a baseline and it wins nothing.
    """

    name = "decide-stub"

    def answer(self, ticket: Ticket, seed: int) -> Outcome:
        return Outcome(
            provider=self.name,
            ticket_id=ticket.id,
            value=None,
            ok=False,
            tokens_in=0,
            tokens_out=0,
            latency_s=0.0,
            error="not implemented until Chapter 7",
        )
```

It is a stub and it returns nothing.

That is the correct state of the art here, and writing it down is cheaper than implying a path exists when it does not.

It is not claimed to be better than anything.

Chapter 7 makes it real and measures it against the same rows.

<figure class="jev-figure">
  <a href="/images/books/jev/fig-01-1-one-arm.svg" target="_blank" rel="noopener">
    <img src="/images/books/jev/fig-01-1-one-arm.svg" alt="A table of the five measurement arms. The predicate has measured tokens, latency and failure rates. The three generation arms and the decide stub are marked not observed. A callout records that the caller reads 25 characters." width="1200" height="700" loading="lazy">
  </a>
  <figcaption><strong>Figure 1.1.</strong> The chapter's honesty is the figure: four of five arms never ran. The one constant that needs no model is the 25-character payload the caller reads.</figcaption>
</figure>

## Four words we keep apart

The measurement is only interpretable if the following four are not allowed to blur into each other, and the rest of the book depends on keeping them apart.

**Computation.** The predicate. It maps state to a value by executing rules someone wrote.

It is exact with respect to those rules, it is fast, it is free, and it is completely unable to answer anything the rules do not mention.

In our run it answered half the test split and abstained on the rest.

**Prediction.** A statistical map from state to a value or a distribution over values.

A trained classifier is a prediction.

It generalises past the rules it was fitted on and it is wrong in ways that are not enumerable in advance.

This book treats decisions as a kind of prediction and is careful never to imply otherwise.

**Generation.** Producing a sequence of tokens that a human could read.

The interesting property of generation is not that it is correct; it is that it is *general*.

It can express anything a sequence of tokens can express, which is why it became the default interface.

Its cost is that the caller almost never wants the whole sequence.

**Decision.** A bounded answer to a bounded question, together with what the program is obliged to do about the uncertainty in it.

The bound is what makes it checkable: the answer set is finite and declared in advance, the output cannot drift outside it, and the uncertainty is part of the value rather than something a downstream reader has to reconstruct from the absence of a confidence score.

Generation is how you currently obtain a decision.

It is not the same act, and the measurements in this chapter are the evidence that conflating them is expensive.

That is the whole claim so far.

Whether a decision deserves to be a programming construct is [Chapter 16](/books/jev/16-chapter/); whether a decision model is a distinct category of model is [Chapter 2](/books/jev/02-chapter/).

## What we measured, and what we did not

The experiment was pre-registered *before* any run.

Its question: what fraction of tokens, latency and failures in generate-then-parse is overhead relative to the one value the application consumes?

Its prediction: overhead is a large majority of tokens and a nonzero parse-failure rate, but accuracy does not differ.

The machine this chapter ran on had no local model weights and a CPU-only build of torch, so the model-backed arms did not run.

Here is exactly what that leaves open:

| Arm | Status | Tokens out | p50 / p95 latency | Parse-failure rate | Schema-violation rate |
|---|---|---|---|---|---|
| `predicate` | **OBSERVED** | 0 | < 4e-06 s / < 4e-06 s | 0.0 | 0.0 |
| `generate-freeform` | **NOT_OBSERVED** | NOT_OBSERVED | NOT_OBSERVED | NOT_OBSERVED | NOT_OBSERVED |
| `generate-schema/answer-first` | **NOT_OBSERVED** | NOT_OBSERVED | NOT_OBSERVED | NOT_OBSERVED | NOT_OBSERVED |
| `generate-schema/reason-first` | **NOT_OBSERVED** | NOT_OBSERVED | NOT_OBSERVED | NOT_OBSERVED | NOT_OBSERVED |
| `decide-stub` | **NOT_OBSERVED** | 0 | 0 | n/a | n/a |

Five arms, not four: the schema ordering split adds one.

It is there because of Tam et al. §4.1, and it is the arm most likely to show that constraint is not free.

One quantity *is* observed and needs no model, because it is a property of the interface rather than of any model: the payload the application actually reads.

**OBSERVED.** The value the caller consumes, written out, is 25 characters: `{"refund_approved": true}`.

The schema the model is asked to emit is longer than that before the model has contributed a single character of justification.

The overhead ratio between "one bounded value" and "a JSON object containing one bounded value and an explanation" is therefore **greater than 1 by construction**, independent of what any model does, and it grows with whatever the model is willing to add.

Verified in `selftest.py`, "overhead accounting".

The prediction stands untested on the arms that matter.

> **Not yet run.** The model-backed arms fill `results/ch01.jsonl`, one row per case per arm, tagged with `schema_variant`. The command is:

```
unset HF_HUB_OFFLINE
huggingface-cli download Qwen/Qwen3-1.7B      # record the commit sha
python examples/ch01-generate-vs-decide/run_ch01.py \
    --providers generate-freeform generate-schema \
    --split test --seed 0 \
    --model Qwen/Qwen3-1.7B --revision <sha>
```

`generate-schema` expands to both key orderings, so one invocation produces three model-backed arms.

Repeat for seeds 1 and 2 and for `--split shift`.

Until those rows exist in `results/ch01.jsonl`, no claim about how large generation overhead is should be repeated, by this book or by anyone quoting it.

## Four ways the prediction could fail

Writing down how to be wrong is the only part of a prediction that survives contact with results.

This one has four distinct failure modes, and they are recorded before the run:

1. **Overhead is small.** If a model emits a tight `true` and stops, tokens and latency
   could be far below intuition. The 25-character floor is a lower bound on the schema,
   not an upper bound on the output.
2. **Free-form parsing is reliable.** At temperature 0 across three seeds, the
   free-form parse-failure rate could be exactly zero, in which case constrained decoding
   buys nothing and Tam et al.'s warning about format restrictions is the *only* cost
   that matters.
3. **Constraint changes the answer.** If `generate-schema` and `generate-freeform`
   disagree on a non-trivial share of cases, then constraint is not free and the two arms
   are not interchangeable.
4. **The predicate is the right tool and the model is not needed.** Half the test split is
   outside the written policy, but a human operator's implicit knowledge covers much of
   it. If a model cannot beat the predicate on the cases the predicate abstains on —
   without being *worse* on the cases it answers — then the honest architecture is
   predicate first, model second, and that is a result, not a disappointment.

Bucher et al., *Fine-Tuned 'Small' LLMs (Still) Significantly Outperform Zero-Shot Generative AI Models in Text Classification* ([arXiv:2406.08660](https://arxiv.org/abs/2406.08660)), points straight at failure mode 4. **DOCUMENTED.**

Smaller fine-tuned BERT-style models beat zero-shot prompted frontier models on every classification case study they ran — sentiment, approval, emotion, party position — across news, tweets and speeches.

Fine-tuning on application-specific data won in all cases.

Two details from the full text matter here.

First, their conclusion reports that performance begins to saturate after **around 200 labels**, which is the most useful number in this chapter's source set: it says how much annotation a decision actually costs.

Second, and less comfortable: their zero-shot baselines were ChatGPT with GPT-3.5 and GPT-4, and Claude Opus.

Those are hosted frontier models.

Ours is a local 1.7B model.

Their result does not transfer to our setup automatically, and this chapter does not get to say "the literature shows small models win" — it shows something narrower, against zero-shot prompting of large models, not against constrained generation.

So the premise of this chapter — that generation is the natural default route to a decision — is not a safe default.

That is a challenge to the framing, not a result this chapter has replicated.

## Where this leaves the argument

The floor is established for one arm and left open for three.

What we can say today is narrow but real: a program that wants one boolean can have it from a predicate in under four microseconds and zero tokens, and the interface it has to accept to get it from a model is already larger than the value it wanted.

What we cannot say today is how much larger in practice, which is the number the whole book is leaning on.

There is a second thing this chapter found by accident, which may matter more than the measurements.

Half of the test split is outside the written policy.

The predicate's abstentions were not gaps in the code; they were gaps in the rulebook, exposed by tickets the runbook never anticipated — a price-drop request, an ambiguous ask, an enterprise licence eighteen months old.

A deterministic predicate cannot answer those.

That is not an argument for a model.

It is an argument that **the specification was incomplete**, and the distinction is going to matter for the rest of the book: a decision provider can only be as good as the question it is asked, and the question is written by a human who did not know they were writing an underspecified interface.

So the closing question, which is Chapter 2's, is not "can a model handle the cases the predicate cannot?"

It is "what is the thing that handles them?"

The vendor answer is a model that returns typed values instead of prose — Jev's published contract, per its own site, is a choice from a declared label set, a score on an ordered rubric, or a yes/no probability, with output billed at zero because there is no generated text to bill for.

That is a **third-party claim, not DOCUMENTED**: the page describing it is an independent guide, not TypeSafe's own documentation, and this book will treat the contract as a claim to be tested rather than a specification to be trusted.

Chapter 2 reads the primary sources and fixes the vocabulary.

Until then, the honest summary of Chapter 1 is one line long.

Generate less. Measure the rest. — which LMQL said first, years ago, and which this chapter exists to hold you to.

## Limitations

- **The experiment did not run.** Model-backed arms are `NOT_OBSERVED` because no local
  weights were available and the installed torch is a CPU build. No number in this chapter is estimated, guessed or
  extrapolated; the gap is left open.
- **LMQL is used narrowly.** Only its framing and headline evaluation claim are relied
  on, not its runtime semantics or evaluation sections.
- **The dataset is hand-written.** 75 cases, written for this book, not collected from a
  production system. The labels are a judgement of what a support agent would
  do, not ground truth from a real queue. The predicate's 8-of-10 accuracy is therefore
  a property of this case set and must not be generalised.
- **Single decision, single provider family, one prompt.** One application, one schema,
  one prompt wording, one model size. A different prompt could plausibly change the token
  count substantially; the prompt hash is recorded in every row so that this can be
  checked.
- **`torch` is the CPU build**, so even a completed run would report CPU latency. Any GPU
  number would need the wheel pinned and re-measured, and the two must not be mixed in one
  comparison.
- **The Jev contract quoted above is third-party.** `jevmodel.org` states it is an
  independent guide and not affiliated with TypeSafe. Primary-source verification is
  Chapter 2's job.

## What Chapter 1 leaves behind

- `examples/ch01-generate-vs-decide/tickets.py` — 75 hand-written tickets, the policy, the
  predicate, and a fixed 20/10/10/20 split plus a 15-case `shift` split.
- `examples/ch01-generate-vs-decide/paths.py` — the four providers (five arms, counting
  both schema variants), the instrumentation, and the scoring code.
- `examples/ch01-generate-vs-decide/application.py` — the caller, which never learns how
  the answer was produced.
- `examples/ch01-generate-vs-decide/run_ch01.py` — the runner that writes
  `results/ch01.jsonl`, tagging each row with its `schema_variant`.
- `examples/ch01-generate-vs-decide/summarise_ch01.py` — appends the aggregate rows the
  prose quotes.
- `examples/ch01-generate-vs-decide/selftest.py` — 53 checks that run without a model.
  **OBSERVED**: all 53 pass.
- `examples/ch01-generate-vs-decide/requirements.txt` — the pinned versions the numbers
  were produced under.
- `evidence/ledger.md` — every claim in this chapter with its type and source.
- `results/ch01.jsonl` — 20 per-case rows for `provider = "predicate"`, plus 7 aggregates.
