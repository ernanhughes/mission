# H2 Experimental Design

Before any experiment, freeze a small task family, task/evaluator versions, engine and model route, prompts/context inputs, effective policy/configuration digests, tool permissions, retry rules, and total inference/tool/time/cost budgets. Record repetitions and randomization/matching strategy.

Use development data for diagnosis, frozen validation for iteration, and protected acceptance tasks for the final comparison. Keep evaluator material outside candidate access. Include a no-fault control and targeted fault cases where recovery is claimed. Independent deterministic checks should decide mechanical correctness; calibrated human/model review may assess semantic quality, with disagreements visible.

Report per-run outcomes and paired differences with uncertainty, failures, abstentions, missing evidence, costs, and protocol deviations. Do not infer a harness effect from a model change, extra inference budget, selected best run, or online comparison with a different workflow. Preserve negative results. Promotion requires a separately authorized gate, independent review, and rollback path. This design is a proposal; no experiment ran in H0/H1.
