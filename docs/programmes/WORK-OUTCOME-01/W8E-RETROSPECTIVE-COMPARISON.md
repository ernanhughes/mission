# W8E-RETROSPECTIVE-COMPARISON — One episode, measured honestly

Same work, two paths (08C push-evidence question):

| Dimension | Retrospective (W5A/W7) | Prospective (W8E pilot) |
| --------- | ---------------------- | ----------------------- |
| Requirement recovery | Mined from chat + docs after the fact (9 across 3 eps, weeks) | 3 authorized up front (minutes) |
| Association accuracy | Inferred (sessions→commits heuristic; 0 commits for 05) | Declared (evidence target in registration) |
| Ambiguous relationships | High (291 assocs, 126 unresolved) | Zero (all refs validated at registration) |
| Evidence availability | Missing SHAs/test records (217 unsupported) | Present by construction (checks defined first) |
| Model invocations | 6 semantic ($0) + benchmark 4 | 0 (deterministic only) |
| Context overhead | Full session packets (~KBs) on semantic path | 671-byte envelope, never in context |
| Manual intervention | Heavy (recovery, linking, closure each by hand) | Light (authorize + run + verify; linking automatic) |
| Reliability | Partial + conditional | Partial, but every link exact |

No broad claims from n=1: this compares one bounded evidence task,
not development at large. Documented direction (not proof):
pre-registration eliminates the two most expensive retrospective
costs (recovery + disambiguation) while leaving verification cost
unchanged — verification is where the work is, and should be.
