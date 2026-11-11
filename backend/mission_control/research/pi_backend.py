"""Pi-first execution backend for Mission Control.

Pi is the default AI execution layer. An explicitly configured loopback
OpenAI-compatible endpoint remains available as an override, but no AI
feature requires it when Pi is available and consent is recorded.

This module shells to the installed Pi CLI (one-shot, non-interactive).
Each call starts a fresh Pi process, so it always inherits the current
environment and never reuses a stale persistent process. No API keys or
authorization headers are ever logged or stored here.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any

PI_ROUTE = "pi-default"
PI_PROVIDER_FALLBACK = "opencode-go"
PI_DEFAULT_MODEL = "opencode-go/deepseek-v4.1-flash"
PI_TIMEOUT_SECONDS = 120.0
PI_MAX_OUTPUT_CHARS = 50_000
PI_MAX_PROMPT_CHARS = 100_000

_BILLING = re.compile(r"(?i)(402|insufficient[\s_-]?balance|payment required|billing|out of credit)")
_RATE = re.compile(r"(?i)(429|GoUsageLimitError|rate[\s_-]?limit|too many requests|retry[\s_-]?after|quota|overloaded|529)")
_AUTH = re.compile(r"(?i)(401|403|unauthorized|forbidden|invalid api key|authentication|authorization)")
_MODEL_MISSING = re.compile(r"(?i)(model (not found|unknown|not listed|not available)|unknown model|not in the list|no such model)")


def classify_pi_error(text: str) -> str | None:
    m = text or ""
    if _AUTH.search(m):
        return "auth"
    if _BILLING.search(m):
        return "billing"
    if _RATE.search(m):
        return "rate_limited"
    if _MODEL_MISSING.search(m):
        return "model_not_found"
    return None


def resolve_pi_command() -> list[str]:
    explicit = os.environ.get("MISSION_PI") or os.environ.get("WORKBENCH_PI")
    if explicit:
        return [explicit]
    exe = shutil.which("pi")
    if not exe:
        raise FileNotFoundError("`pi` not found on PATH; set MISSION_PI to its path")
    return [exe]


def _run_pi(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    cmd = resolve_pi_command()
    env = dict(os.environ)
    env.setdefault("PI_OFFLINE", "0")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    return subprocess.run(
        [*cmd, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        stdin=subprocess.DEVNULL,
        creationflags=flags,
    )


def discover_pi_models(timeout: float = 15.0) -> dict[str, Any]:
    """List Pi models via `pi --list-models`. Read-only; starts no session."""
    try:
        proc = _run_pi(["--list-models"], timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "models": [], "detail": f"Pi could not be queried ({exc.__class__.__name__}).", "error": "pi_unavailable"}
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:500] or f"exit {proc.returncode}"
        return {"available": False, "models": [], "detail": f"Pi model catalogue failed: {detail[:200]}", "error": classify_pi_error(detail) or "pi_catalogue_failed"}
    models: list[dict[str, Any]] = []
    for line in (proc.stdout or "").splitlines():
        parts = line.strip().split()
        if len(parts) < 2 or line.strip().lower().startswith("provider"):
            continue
        provider, model_id = parts[0].strip(), parts[1].strip()
        if not provider or not model_id or "/" in model_id:
            continue
        full = f"{provider}/{model_id}"
        models.append({"id": full, "label": full, "local": False, "configured": full == PI_DEFAULT_MODEL, "available": True})
    if not models:
        return {"available": False, "models": [], "detail": "Pi reported no models.", "error": "no_models"}
    return {"available": True, "models": models, "detail": f"Pi reports {len(models)} model(s).", "error": None}


def complete_pi_chat(*, model: str, messages: list[dict[str, str]], timeout: float = PI_TIMEOUT_SECONDS) -> dict[str, Any]:
    """One Pi inference call. Fresh process per call; no silent provider switching."""
    selected = (model or "").strip()
    if not selected or len(selected) > 200 or any(c in selected for c in "\r\n"):
        raise ValueError("The selected model identifier is invalid.")
    if "/" not in selected:
        raise ValueError("The model must look like provider/model-id.")
    prompt_parts: list[str] = []
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in {"system", "user", "assistant"} or not isinstance(item.get("content"), str):
            raise ValueError("The chat request did not contain valid messages.")
        prompt_parts.append(f"{item['role'].upper()}:\n{item['content']}")
    prompt = "\n\n".join(prompt_parts)[:PI_MAX_PROMPT_CHARS]
    started = time.monotonic()
    try:
        proc = _run_pi(
            ["--model", selected, "--no-tools", "--no-extensions", "--no-skills",
             "--no-prompt-templates", "--no-context-files", "--no-session", "-p", prompt],
            timeout=max(5.0, min(timeout, 300.0)),
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Pi did not respond within {timeout:g} seconds.") from exc
    except OSError as exc:
        raise RuntimeError(f"Pi could not be started ({exc.__class__.__name__}).") from exc
    text = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        combined = f"{err}\n{text}".strip()[:2000]
        kind = classify_pi_error(combined)
        if kind == "billing":
            raise RuntimeError("Pi billing failure (402/insufficient balance). Do not switch providers automatically; top up and retry the same model.")
        if kind == "rate_limited":
            raise RuntimeError(f"Pi rate limit/overload (429). Bounded retry only; do not switch billing accounts. {combined[:300]}")
        if kind == "auth":
            raise RuntimeError(f"Pi authentication failure (401/403). Check Pi credentials; nothing was switched. {combined[:300]}")
        if kind == "model_not_found":
            raise ValueError(f"Pi model not found: {selected}. Refresh models and choose a listed model.")
        raise RuntimeError(f"Pi request failed (exit {proc.returncode}). {combined[:500]}")
    if not text:
        raise RuntimeError("Pi returned an empty response; no answer was recorded.")
    content = text[:PI_MAX_OUTPUT_CHARS]
    provider = selected.partition("/")[0]
    return {
        "content": content,
        "provider": provider,
        "route": PI_ROUTE,
        "local": False,
        "endpoint": "pi",
        "requested_model": selected,
        "model": selected,
        "usage": {},
        "latency_ms": int((time.monotonic() - started) * 1000),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
