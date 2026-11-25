# Mediated reader probe (model-reader ≠ human proof; PUB-08 owns calibration)

Bounded BLIND original-vs-revised comparison via a mediated-read /
evaluation-fabric style protocol. The probing reader must NOT be the
revising model (CONFLICTED_MODEL_JUDGEMENT if it is); use a separate
model or, preferably, a human reader in PUB-08.

## Source-grounded reference contract (from the authoritative chapter)

The blind reader's answers are scored against this contract, built only
from source-bound facts:

1. Central problem: the cost (tokens, latency, failures) of obtaining
   one bounded value by generating prose, measured against a free
   predicate baseline.
2. Argument: generation is the current default route to a decision but
   not the same act; conflating them is expensive; the floor is one arm,
   the rest is unmeasured.
3. Distinctions: computation vs prediction vs generation vs decision
   (four kept-apart meanings).
4. Established: predicate 10 answered / 10 abstained / 8 correct, 0
   tokens, <4µs; 25-character payload; Willard O(N)→O(1) + ~50 MB;
   Tam ordering confound + 2-of-3 reasoning result; Bucher ~200 labels.
5. Unresolved: all model-backed arms (NOT_OBSERVED); schema-ordering
   effect; free-form reliability; predicate-vs-model architecture.
6. Example function: the walkthrough recomputes quoted figures from code
   (runnable, no model); t11/t60 show the rulebook's hole.
7. Why it matters: sets the bar (the number) the whole book leans on.

## Protocol

1. Present original and candidate in random order, unlabelled, without
   provenance.
2. Ask: (a) one-sentence problem; (b) the four distinctions in own
   words; (c) what is established vs unresolved; (d) what the walkthrough
   is for; (e) why the chapter matters for the book.
3. Score each against the contract (present / partial / absent / contradicted).
4. Comprehension win = candidate ≥ original on (a)–(e) with no
   contradiction anywhere; any contradiction fails the probe regardless
   of fluency preference.
5. Record: reader identity, blindness, order, scores, quotes. A
   model-reader result is directional only; PUB-08 repeats with humans.

## Status

Specified here; not executed in PUB-06 fix batch (no human pool;
model-reader run would be directional at best and is deferred to avoid
manufacturing a comprehension claim before PUB-08). The fix batch adds
a first deterministic new-sentence honesty layer
(`_check_new_sentence_honesty`, D-PUB-59) but explicitly does not claim
comprehension; PUB-08 owns human calibration.
