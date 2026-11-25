# H4 strategy contract

Worker accepts `execution.strategy_id` as one of `direct.v1`, `structured.v1`, or `corrective.v1`. A selected strategy routes through the existing `model` executor; the caller must name an explicit Worker model route and policy. Requests without `strategy_id` retain the existing path.

| Strategy | Calls | Internal validation | Correction |
|---|---:|---|---|
| `direct.v1` | 1 | None | Never |
| `structured.v1` | 1 | Bounded structural JSON Schema via AJV | Never |
| `corrective.v1` | 1–2 | Same as structured | One extra call only after structural failure |

The structural schema subset is limited to object/array/string/number/integer/boolean/null, properties, required fields, additional-properties boolean, and bounded length/item constraints. Value-specific or semantic keywords are rejected. Internal validation does not establish task correctness; the independent evaluator remains separate.

Each execution returns `strategy_execution` with a catalog digest, lifecycle states, parent Worker request ID, child runtime execution IDs, validation/correction records, resource use, and termination. Correction feedback includes only structural errors and the public task/schema. Prior output is included only for `local_only` or `training_allowed`, bounded to 16 KiB, and marked untrusted. It never receives evaluator answers.

The H4 model runtime requires an explicit free route in an explicit one-attempt policy. This fixes the route and prevents hidden paid fallback or retry. See [H4 resource enforcement](H4-RESOURCE-ENFORCEMENT.md) for provider-side limits and unknowns.
