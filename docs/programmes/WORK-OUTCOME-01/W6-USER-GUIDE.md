# W6-USER-GUIDE — Continuous Work Assurance in plain language

**Application**: your running Mission Control (`http://127.0.0.1:8790`
operational; W6E validation used an isolated copy — same code, scratch
data — so these screens match what an operator deploy shows).

**Finding it**: Activity → **Work Evaluation** → Overview | Work Episodes
| Outstanding Work | Quality | Coverage | **Controls** (new in W6).

## What changed in W6

- **Outstanding Work opens on Groups**: identical assertions are folded
  (e.g. one merge/push line repeated in 25 episodes = one group of 25).
  Every group shows severity, affected episodes, an example wording, and
  what would close it. Drill down to members; switch to Individual
  findings any time. Nothing is hidden: the group count line always names
  the underlying finding total.
- **Honest severity**: historical evidence limitations (missing SHA, no
  execution record, unproven push) are minor. Major is reserved for
  contradicted claims and missing mandatory requirements. Suspected
  stays suspected — the system does not auto-confirm.
- **Freshness**: episodes show Stale + reason + queue state when their
  inputs changed (new commits, new evidence, changed requirements).
  Unevaluated stays unevaluated.
- **Controls**: manual triggers that do exactly what they say —
  Observe now, Reconstruct changed work, Evaluate episode
  (deterministic, $0), queue + freshness inspectors, and Pause
  scheduled evaluation. Opening the panel runs only GETs; actions fire
  solely on click. Scheduled evaluation is off by default and the
  automatic paid budget is $0 (not raisable from here).

## Evaluating additional work deliberately

Same manual path as W5A (Observe → Reconstruct → Triage/Extract →
Evaluate), now one click per step in Controls instead of an API
sequence. Semantic evaluation stays opt-in per episode and doubly
gated (enabled flag + free route + budget); the deterministic path
never needs a model.

## What happens automatically

Nothing, by default: no timers run. When an operator enables the
schedule, deterministic observation runs every 15 min and the semantic
queue hourly, with overlapping-run prevention and failure-as-blocked.
Freshness is then shown, not hidden.

## What does not happen yet

Continuous monitoring is implemented but not switched on (operator
decision, W6E). No automatic corrective execution exists or is planned
before W7. Verified-complete at scale awaits independent test-execution
records (see exemplar report); the UI shows `partial`/reported exactly
where evidence ends.
