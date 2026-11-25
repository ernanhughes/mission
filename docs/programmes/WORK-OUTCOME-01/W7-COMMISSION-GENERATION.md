# W7-COMMISSION-GENERATION — Deterministic assembly, semantic deferred

`assemble_commission` builds the 13-section commission (§9) purely from
stored facts: original objective (episode title), authorized
requirements + versions + human confirmation decisions, current
implementation pointer (Changes/Evidence views), the exact gap per
finding + next actions, cited rationale excerpts, previous-work
pointers, requested action (category + objective), scope, exclusions,
acceptance criteria, required verification, cost constraints, stop
conditions. No model calls; no conversation history submitted; no
invented content (empty slots say so explicitly).

Semantic drafting is deliberately NOT implemented in W7: the brief
permits it only with justification, and the stop conditions forbid
unattended semantic evaluation. A user-triggered drafting aid would
still need budget/governance wiring; recorded as W8 input, not built.

Preview + copy are the handoff: the operator pastes the commission
where the work will be done (worker `POST /v1/work`, workbench,
OpenCode, or manual execution) and records the link back. The pilot
commission (17 rendered lines for the 08C recovery: 13 sections +
finding citations) is the reference output.
