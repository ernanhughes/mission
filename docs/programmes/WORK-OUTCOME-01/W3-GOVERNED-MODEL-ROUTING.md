# W3-GOVERNED-MODEL-ROUTING — Demonstrated loopback route (survey pending)

## Demonstrated (this commission, bounded, $0)

- **Route**: `POST http://127.0.0.1:11434/v1/chat/completions` (Ollama
  OpenAI-compatible API; httpx, already a Mission dependency — no new
  provider client, no registry). Loopback-only enforced in code
  (`ollama_backend.py`: non-loopback base_url raises).
- **Model**: `qwen2.5:0.5b` (50 local models available; smallest chosen for
  the synthetic probe; MC10-accepted `mistral-small:latest` and
  `qwen2.5-coder:latest` present for stronger runs).
- **Governance**: temperature 0, `max_tokens` cap, client timeout,
  `format: json` request, fence-tolerant parse, JSON-schema validation
  before persistence, usage (`prompt/completion_tokens`) captured per call,
  hard caps (20 calls / $1) enforced in-service with cache-first
  (`UNIQUE(input_digest, schema, prompt, extractor)`).
- **Synthetic probe first**: fabricated hello-endpoint conversation, no
  history/secrets; probe 1 exposed fence-wrapping + truncation (prompt
  hardened); probe 2 validated end-to-end through `ExtractionPacket`.
- **Why not Worker**: `127.0.0.1:7317` refused (operator-start policy per
  `config/defaults/applications.yaml`; not a failure). Depending on it
  would couple observation to an execution service. No `LITELLM_API_KEY`
  observed (Worker `direct` path blocked); Go routes are subscription-side.

## Separate survey status

A parallel survey (worker/workbench/ai/mission/next/work inspection + live
loopback probes) was commissioned to confirm the intended mechanism. If it
identifies a cheaper or more governed route, the backend's `model` parameter
and `extractor` identity make the switch a config change, not a rebuild;
the 20-call pilot results remain valid as pipeline evidence regardless.

## Cost model

Local Ollama: $0 + electricity; usage tokens logged as receipts. No paid
calls were made. Any future paid route requires explicit authorization,
per-call cost capture (already in the ledger), and the same validation gates.
