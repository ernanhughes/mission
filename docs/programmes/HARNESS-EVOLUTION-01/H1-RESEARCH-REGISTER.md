# H1 Research Register

Research review completed 2026-11-24. Findings below are evidence for design choices, not proof that any external system is production-ready or superior.

| Source | Version/status inspected | Finding for this programme |
|---|---|---|
| [Exo](https://arxiv.org/abs/2611.00463), [repository](https://github.com/exoharness/exo) | Preprint 2026-10-30; repo `e1e56696a5755ddd9f043418936a3780efb200c6`, MIT, explicitly under construction | Useful protected mechanism / replaceable harness boundary and durable run concepts. Paper and current repo are distinct snapshots; do not import runtime wholesale. |
| [Meta-Harness](https://arxiv.org/abs/2603.28052), [repository](https://github.com/stanford-iris-lab/meta-harness) | Repo `f805ad3aa4ada290458c1e0deadbe132fbbdea4e`, MIT; README limits validation claim | Candidate isolation, bounded evaluation, budget and aggregation patterns. Its controller stages candidates and launches child jobs; cleaned repository says validation is limited. |
| [Harness Delta Attribution](https://arxiv.org/abs/2610.22466), [repository](https://github.com/Wenwen-D/HarnessDeltaAttribution) | Repo `cc4119a678b070e324e6d6d94adea1acfcc86acb`; no declared license observed | Separate overfit, test-time scaling and residual attribution; paired uncertainty and human checkpoints. Residual is an upper bound, not proof of transfer. Reuse method only; do not copy code. |
| [SEAGym](https://arxiv.org/abs/2606.17546), [repository](https://github.com/antropy-research/SEAGym) | Repo `9e61e14db1f1355de944cd7c5b10c244fc74e82d`, Apache-2.0 | Train/frozen-validation/held-out/replay/cost views. It is an evaluation environment, not an update or rollback algorithm. |
| [Hyperagents](https://arxiv.org/abs/2603.19461) | Paper, v2 updated 2026-11-01 | Self-modification of meta-procedures is a later research frontier; not a first implementation target. |
| [Harness Evolution Hits a Ceiling](https://arxiv.org/abs/2610.11655) | Preprint | Distinguishes process and content failure; use as a failure taxonomy, not a universal law. |
| [Winner's Curse](https://arxiv.org/abs/2610.09239) | Preprint | Candidate selection bias motivates a protected holdout and uncertainty reporting; no fixed sample count is magic. |
| [Who Verifies the Verifier?](https://arxiv.org/abs/2610.11464) | Workshop paper (2026) | Verifiers can collapse to always-pass behavior; ground acceptance independently. |
| [Reflections on Trusting Trust, Revisited](https://arxiv.org/abs/2609.17817) | Preprint | Evaluator and benchmark integrity are part of the trust boundary. |
| [Spotify harness study](https://arxiv.org/abs/2609.30297) | Industry study/preprint | Reports relative pass@1 improvement in its setting; online comparison does not isolate the harness loop. Treat as a case study, not a transferable guarantee. |
| [No Second Run](https://arxiv.org/abs/2611.10719) | Submitted 2026-11-07 | Frontier pretraining/nested-loop work; tangential to this execution architecture. |
| [RSI roadmap](https://arxiv.org/abs/2609.11873) | v3 2026-09-22 | Actual title: “The Last AI Built by Humans: Toward Genuine Recursive Self-Improvement”; a roadmap, not the survey title used in the supplied review. |

Research was read-only. No external repository was cloned or executed. Paper dates/status and repository snapshots must be rechecked before implementation if they affect a decision.
