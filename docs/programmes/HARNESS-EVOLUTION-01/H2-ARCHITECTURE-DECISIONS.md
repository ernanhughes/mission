# H2 Architecture Decisions

Accepted by the programme owner in the 2026-11-24 H2 decision attachment.

| ID | Decision | H3 application |
|---|---|---|
| AD-01 | Federated architecture; Mission governs, Worker composes execution, engines remain replaceable, domains retain ownership. | H3 only adds identity/observation composition to Worker; no capability migration. |
| AD-02 | Worker progresses beyond a passive gateway without becoming a monolith. | Expose the existing effective execution choices and correlation; no policy language or speculative plugin framework. |
| AD-03 | Pi is the educational reference engine; Worker is the proposed production realization. | Preserve book; resolve its reference-host relation in H9 after evidence. |
| AD-04 | Reuse Work Outcome; do not create a parallel episode lifecycle. | Optional Mission `episode_id` links to existing `WoEpisode`; no Worker-owned episode type. |
| AD-05 | Execution, domain correctness, objective achievement, independent verification, comparative effectiveness, and promotion are distinct. | Worker reports execution evidence only; evaluator and Mission own their verdicts. |
| AD-06 | Candidate, evaluator, and acceptance authority are separate. | No candidate can alter evaluator, fixtures, permissions, audit data, or promotion authority. |
| AD-07 | Unknowns and negative findings remain explicit. | Missing engine/model/cost/evidence values remain unknown; no inferred success. |

The exact full decision text is retained in the user-provided H2 decision attachment. This table records the implementation interpretation, not additional scope.
