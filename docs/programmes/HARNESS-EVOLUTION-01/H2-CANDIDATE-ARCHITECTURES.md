# H2 Candidate Architectures

## Options

| Option | Shape | Benefit | Main cost/risk |
|---|---|---|---|
| A. Worker monolith | Put policy, memory, evaluation, adaptation, and execution in Worker | One runtime surface | Duplicates Mission governance, Writer/ECK and Praxis; makes Worker a large authority-bearing system. |
| B. Federated composition (preferred) | Mission governs; Worker executes; Pi/OpenCode are engines; Writer/Praxis retain domain/effectiveness ownership; explicit adapters link records | Reuses deployed boundaries and keeps independent acceptance | Requires stable identity, versioning, and clear cross-repo contracts. |
| C. Mission-only harness | Mission owns execution loop and all capabilities | Direct control-plane integration | Rebuilds Worker substrate and couples Mission to engines. |
| D. Praxis/ECK-centered harness | Move runtime policy and evaluation into learning systems | Strong experiment vocabulary | Effectiveness/policy components are not general execution runtimes; risks promoting research prototypes into authority. |

## Recommendation

Advance B to H2 review. Worker is the execution substrate, not a monolithic capability owner. Mission is the control plane for intent, authority, lifecycle, observation, and final governance. Pi/OpenCode remain replaceable engines. Writer owns writing context and domain evaluation; ECK remains Writer-specific procedural learning. Praxis owns cross-domain experiment/effectiveness records and can recommend, but cannot grant runtime authority or acceptance. Workbench supplies human decisions. Stephanie may later propose candidates through a governed adapter; it has no established service contract or demonstrated effectiveness. Remembering/Relate and `ai.*` are composed only where a measured need exists.

The Harness book’s current blueprint is Pi-centered with a future TypeScript host. That is an architectural tension, not an instruction to replace Worker. H2 must decide whether the book describes a conceptual reference implementation separate from Mission’s production composition, or revises its host premise. No book changes are authorized here.
