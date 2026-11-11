"""Local model discovery and execution for research conversations.

Mission Control already owns an explicit OpenAI-compatible AI configuration
used by the optional briefing interpretation.  This module reuses that provider
boundary instead of adding a second Ollama client.  Research chat is stricter
than the briefing: the configured endpoint must be loopback, and a remote
endpoint is refused rather than used as a silent fallback.

Worker was inspected first.  Its running catalogue exposes Pi/OpenCode cloud
routes and its optional ``direct`` local executor is not registered, so it does
not currently provide a local conversational route.  The smallest compatible
route available today is the existing provider-neutral AI configuration.
"""

from __future__ import annotations

import ipaddress
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from mission_control.core.errors import (
    CapabilityUnavailable,
    InferenceProblem,
    ValidationProblem,
)
from mission_control.models import Setting

LOCAL_ROUTE = "configured-local-openai"
LOCAL_PROVIDER = "openai-compatible"


@dataclass(frozen=True, slots=True)
class LocalModelConfig:
    enabled: bool
    consent: bool
    base_url: str
    model: str
    timeout_seconds: float
    api_key_env: str
    api_key: str | None
    provider: str

    @property
    def endpoint(self) -> str:
        try:
            parsed = urlsplit(self.base_url)
            return parsed.hostname or "unknown endpoint"
        except ValueError:
            return "unknown endpoint"

    @property
    def local(self) -> bool:
        return is_loopback(self.base_url)

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.consent and self.base_url and self.model)


def is_loopback(base_url: str) -> bool:
    """Only an explicitly local address is eligible for research chat."""

    try:
        host = (urlsplit(base_url).hostname or "").strip().casefold()
    except ValueError:
        return False
    if host in {"localhost", "localhost."}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def read_config(session: Session) -> LocalModelConfig:
    setting = session.get(Setting, "ai")
    value = setting.value if setting and isinstance(setting.value, dict) else {}
    api_key_env = str(value.get("api_key_env") or "")
    try:
        timeout = float(value.get("timeout_seconds") or 45)
    except (TypeError, ValueError):
        timeout = 45.0
    return LocalModelConfig(
        enabled=bool(value.get("enabled")),
        consent=bool(value.get("consent")),
        base_url=str(value.get("base_url") or "").rstrip("/"),
        model=str(value.get("model") or "").strip(),
        timeout_seconds=max(5.0, min(timeout, 180.0)),
        api_key_env=api_key_env,
        api_key=os.environ.get(api_key_env) if api_key_env else None,
        provider=str(value.get("provider") or LOCAL_PROVIDER),
    )


def _headers(config: LocalModelConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return headers


def _models_url(base_url: str) -> str:
    return base_url if base_url.endswith("/models") else base_url + "/models"


def _completions_url(base_url: str) -> str:
    if base_url.endswith("/chat/completions"):
        return base_url
    return base_url + "/chat/completions"


def resolve_model(session: Session, requested: str = "") -> tuple[str, str]:
    """Central Pi-first resolver: explicit task model > explicit local config > Pi default.

    Returns (model, route). Never rewrites provider/model IDs and never
    substitutes an unrelated provider. Pi default prefers the validated
    ``opencode-go/deepseek-v4.1-flash`` when no explicit choice exists.
    """
    from mission_control.research import pi_backend as _pi

    explicit = (requested or "").strip()
    if explicit:
        config = read_config(session)
        if config.configured and explicit == config.model:
            return explicit, LOCAL_ROUTE
        if "/" in explicit:
            return explicit, _pi.PI_ROUTE
        return explicit, LOCAL_ROUTE
    config = read_config(session)
    if config.configured and config.model:
        return config.model, LOCAL_ROUTE
    return _pi.PI_DEFAULT_MODEL, _pi.PI_ROUTE


async def complete_chat(
    session: Session,
    *,
    model: str,
    messages: list[dict[str, str]],
    route: str | None = None,
) -> dict[str, Any]:
    """Execute one chat completion through the unified Pi-first layer.

    Local loopback remains an explicit override. Otherwise Pi is used when
    AI is enabled and consent is recorded. Remote Pi inference is never
    local: callers must keep the consent distinction explicit in the UI.
    No silent provider switching on billing/auth failures.
    """
    from mission_control.research import pi_backend as _pi

    config = read_config(session)
    if not config.enabled or not config.consent:
        raise CapabilityUnavailable(
            "AI is disabled or consent has not been recorded. Enable AI in Settings and record consent."
        )
    selected = (model or "").strip() or config.model or _pi.PI_DEFAULT_MODEL
    use_route = (route or "").strip()
    if not use_route:
        use_route = LOCAL_ROUTE if (config.configured and selected == config.model) else _pi.PI_ROUTE
    if use_route == LOCAL_ROUTE:
        return await complete_local_chat(session, model=selected, messages=messages)
    return _pi.complete_pi_chat(model=selected, messages=messages, timeout=config.timeout_seconds)


async def discover_local_models(session: Session) -> dict[str, Any]:
    """Return the explicit local model catalogue and a truthful diagnostic.

    A model is not marked available merely because its name is configured.  If
    the endpoint cannot be reached or the configured model is absent from its
    catalogue, ``available`` remains false and the UI shows why.
    """

    config = read_config(session)
    result: dict[str, Any] = {
        "provider": config.provider,
        "route": LOCAL_ROUTE,
        "configured": config.configured,
        "local": config.local,
        "available": False,
        "endpoint": config.endpoint if config.base_url else None,
        "selected": config.model or None,
        "models": [],
        "detail": "No local model endpoint is configured.",
        "error": None,
    }
    if not config.enabled or not config.consent:
        result["detail"] = (
            "Local research chat is disabled. Enable AI in Settings, record consent, "
            "and configure a loopback OpenAI-compatible endpoint."
        )
        return result
    if not config.base_url or not config.model:
        result["detail"] = (
            "The AI configuration is incomplete. Set a loopback base URL and a model "
            "in Settings before starting a research conversation."
        )
        return result
    if not config.local:
        result["detail"] = (
            "The configured AI endpoint is not a loopback address. Research chat is "
            "local-only and will not route this conversation to a remote provider."
        )
        result["error"] = "remote_endpoint_refused"
        return result

    timeout = min(config.timeout_seconds, 10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.get(_models_url(config.base_url), headers=_headers(config))
        if response.status_code != 200:
            result["detail"] = (
                f"The local endpoint returned HTTP {response.status_code} while listing "
                "models. The configured model has not been proven available."
            )
            result["error"] = f"model_catalogue_http_{response.status_code}"
            return result
        payload = response.json()
        raw_models = payload.get("data") if isinstance(payload, dict) else None
        models = []
        if isinstance(raw_models, list):
            seen: set[str] = set()
            for item in raw_models:
                model_id = item.get("id") if isinstance(item, dict) else None
                if not isinstance(model_id, str) or not model_id.strip() or model_id in seen:
                    continue
                seen.add(model_id)
                models.append(
                    {
                        "id": model_id,
                        "label": model_id,
                        "local": True,
                        "configured": model_id == config.model,
                        "available": True,
                    }
                )
        result["models"] = models
        configured_present = any(item["id"] == config.model for item in models)
        if not models:
            result["detail"] = (
                "The local endpoint returned no models. Start the local model server or "
                "pull the configured model; the configuration alone is not availability."
            )
            result["error"] = "no_models"
            return result
        if not configured_present:
            result["detail"] = (
                f"The configured model '{config.model}' is not reported by the endpoint. "
                "Select a model the local endpoint actually serves."
            )
            result["error"] = "configured_model_missing"
            result["available"] = True
            return result
        result["available"] = True
        result["detail"] = (
            f"Local OpenAI-compatible endpoint at {config.endpoint} reports "
            f"{len(models)} model(s). The configured model is available."
        )
        return result
    except httpx.TimeoutException:
        result["detail"] = (
            f"The local model endpoint at {config.endpoint} timed out while listing models."
        )
        result["error"] = "model_catalogue_timeout"
        return result
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        result["detail"] = (
            f"The local model endpoint at {config.endpoint} could not be queried "
            f"({exc.__class__.__name__}). The selected model is not proven available."
        )
        result["error"] = "model_catalogue_failed"
        return result


async def complete_local_chat(
    session: Session,
    *,
    model: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Perform one local chat completion, failing closed on every ambiguity."""

    config = read_config(session)
    if not config.enabled or not config.consent:
        raise CapabilityUnavailable(
            "Local research chat is disabled or consent has not been recorded."
        )
    if not config.base_url or not config.model:
        raise CapabilityUnavailable(
            "The local model endpoint is not configured. Set a loopback base URL and model."
        )
    if not config.local:
        raise CapabilityUnavailable(
            "The configured endpoint is not loopback. Research chat will not fall back "
            "to a remote provider."
        )
    selected = model.strip()
    if not selected or len(selected) > 200 or any(character in selected for character in "\r\n"):
        raise ValidationProblem("The selected model identifier is invalid.")
    if not messages or any(
        not isinstance(item, dict)
        or item.get("role") not in {"system", "user", "assistant"}
        or not isinstance(item.get("content"), str)
        for item in messages
    ):
        raise ValidationProblem("The chat request did not contain valid messages.")

    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds, trust_env=False) as client:
            response = await client.post(
                _completions_url(config.base_url),
                headers=_headers(config),
                json={
                    "model": selected,
                    "messages": messages,
                    "temperature": 0.2,
                    "stream": False,
                    "max_tokens": 2048,
                },
            )
    except httpx.TimeoutException as exc:
        raise InferenceProblem(
            f"The local model did not respond within {config.timeout_seconds:g} seconds.",
            detail=f"endpoint={config.endpoint}; route={LOCAL_ROUTE}",
        ) from exc
    except httpx.HTTPError as exc:
        raise InferenceProblem(
            "The local model request failed before a response was received.",
            detail=f"{exc.__class__.__name__}; endpoint={config.endpoint}",
        ) from exc

    if response.status_code != 200:
        raise InferenceProblem(
            f"The local model endpoint returned HTTP {response.status_code}.",
            detail=f"route={LOCAL_ROUTE}; endpoint={config.endpoint}",
        )
    try:
        payload = response.json()
        choices = payload.get("choices") if isinstance(payload, dict) else None
        content = choices[0].get("message", {}).get("content") if choices else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("missing choices[0].message.content")
        actual_model = payload.get("model") if isinstance(payload.get("model"), str) else selected
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise InferenceProblem(
            "The local model returned an unreadable response; no answer was recorded.",
            detail=f"route={LOCAL_ROUTE}; endpoint={config.endpoint}",
        ) from exc

    return {
        "content": content.strip(),
        "provider": LOCAL_PROVIDER,
        "route": LOCAL_ROUTE,
        "local": True,
        "endpoint": config.endpoint,
        "requested_model": selected,
        "model": actual_model,
        "usage": payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
        "latency_ms": int((time.monotonic() - started) * 1000),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

