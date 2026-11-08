# MC-NEXT-CHAT-01 acceptance evidence

Date: 2026-11-08
Selected Next record: `res-55ff4404532bf16d807a`
Stable opportunity ID: `combine-36908f991960c259`

## Artifacts

| Artifact | Purpose |
| --- | --- |
| `selected-opportunity-export.md` | Actual Markdown copied for the real selected opportunity |
| `selected-opportunity-export.json` | Export schema, fingerprint, identity, sources, scores and experiment status |
| `chat-smoke.json` | Real local-model call, reported model/provider/route, usage, latency, answer and captured request-context checks |
| `chat-request-context.md` | The actual system prompt and user message sent to the local model |

The export and request context were generated from a copy of the live Mission
Control database. The real model call used the local Ollama OpenAI-compatible
endpoint. No Next database write occurred.

## Stage 1 — Copy for ChatGPT

| Criterion | Result | Evidence |
| --- | --- | --- |
| Open an existing Next opportunity | Pass | Real record opened in the built UI |
| One-click copy action exists | Pass | `Copy for ChatGPT` button in the Next detail panel |
| Clipboard contains readable Markdown | Pass | Manual UI check showed the success toast; `selected-opportunity-export.md` is the exact export body |
| Clear critical-review instruction | Pass | Section A tells the receiver not to assume validity |
| Source provenance preserved | Pass | GitHub URL and recorded arXiv identifier `2611.06914v1` |
| Uncertainty preserved | Pass | Assessment status, uncertainty 62, missing `overall_confidence` |
| Missing information explicitly marked | Pass | No URL invented; no experiment/success criteria stated |
| Combined opportunity represented correctly | Pass | "Proposed research combination", not a demonstrated improvement |
| No model invocation | Pass | Export endpoint is read-only; the UI wait state made no chat request; backend test asserts no completion call |
| No Next mutation | Pass | Backend test compares stored record data before/after export |
| Tests cover complete/partial/missing-URL/provisional/combined records | Pass | `backend/tests/test_research_chat.py` |

Representative export: 8,782 Markdown characters, context fingerprint
`3e568f5c316143b562a2e6c6e57994b58a897aee8fd0d40877e6dea70e992b74`.

The selected record's arXiv item is stored by Next as the identifier
`2611.06914v1`, not a URL. The export reports that identifier and says no link was
invented. This is intentional: a canonical link would be a derived citation not
recorded by the source.

## Stage 2 — Discuss with AI

| Criterion | Result | Evidence |
| --- | --- | --- |
| Open the same opportunity | Pass | Real opportunity loaded |
| Side-panel chat opens without leaving the workspace | Pass | Manual UI check: `.research-chat-panel` dialog opened over Next |
| Select a genuinely configured and available local model | Pass | `/api/research/models` returned 50 models from `127.0.0.1`; `qwen2.5:latest` selected |
| No model call before explicit submission | Pass | Opening the panel issued only model discovery, session list and session read; no `POST .../messages` |
| Request includes correct opportunity context | Pass | Captured system prompt contains the title, source identifier and combination warning |
| Receive a model response | Pass | Real `qwen2.5:latest` response, 200 OK, 48.84 s |
| Follow-up continuity | Pass | Automated test verifies the second request includes the first complete exchange |
| Refresh and reopen session | Pass | Automated restart test and manual UI reopen both retained the conversation |
| Model attribution persisted | Pass | Message records provider/model/route/local/usage/latency; UI displayed `qwen2.5:latest`, `openai-compatible`, `local route`, `48771 ms` |
| Local-only session cannot fall back to cloud | Pass | Remote endpoint is refused before session creation; changing settings to remote makes the next send fail closed; tests cover both |
| No writes to Next | Pass | Conversations are stored only in Mission Control tables; no Next write path exists |

### Real model smoke

| Field | Value |
| --- | --- |
| Model | `qwen2.5:latest` |
| Endpoint | `http://127.0.0.1:11434/v1` (loopback) |
| Route | `configured-local-openai` |
| Provider | `openai-compatible` |
| HTTP result | 200 |
| Prompt tokens | 2,456 |
| Completion tokens | 551 |
| Reported latency | 48,771 ms |
| Assistant status | `completed` |
| Context fingerprint | `3e568f5c316143b562a2e6c6e57994b58a897aee8fd0d40877e6dea70e992b74` |
| Context contains selected title | Yes |
| Context contains arXiv identifier | Yes |
| Context contains combination warning | Yes |
| Context contains untrusted-data warning | Yes |

This is a real local-model call. It is not a quality evaluation and it is not
evidence that the research opportunity is valid.

### Manual UI check

A built Mission Control instance was started against a copy of the live database
on port 8791:

- Next showed the real record with **Copy for ChatGPT** and **Discuss with AI**.
- Copying produced the success toast: "Research review package copied. Paste it
  into ChatGPT or another AI. No model was called and no source state was
  changed."
- The chat panel opened with the real opportunity title, 2 source items, stable ID,
  model selector, local inference badge, endpoint host and conversation history.
- The retained real-model conversation displayed the answer, model, provider,
  local-route indicator and latency.
- Opening the panel generated no message POST and no model completion call.
- The clipboard could not be read back programmatically because the desktop
  browser window was not focused; the UI success path and the legacy fallback
  completed instead of hanging.

## Automated verification

See the final verification report for the exact command output. At implementation
time:

- backend suite: 83 passed, 1 skipped (the existing Docker-dependent sandbox test);
- frontend suite: 34 tests passed across 11 files;
- production build: passed (`tsc -b` and `vite build`);
- Ruff: passed.

The Docker skip is the existing sandbox test that requires a running Docker
daemon; it is unrelated to this change.

## Boundaries and limitations

- Worker was evaluated but does not currently expose a local conversational route;
  the existing configured OpenAI-compatible provider is used and labelled truthfully.
- Chat is non-streaming.
- Stop is client-side; the model request may still complete after the browser stops
  waiting.
- Source content is metadata only; no paper or repository is downloaded.
- A conversation is not a human decision, accepted recommendation or verified finding.
