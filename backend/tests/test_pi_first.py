"""Pi-first regression: precedence, env inheritance, no silent switching."""
from __future__ import annotations

from mission_control.research import inference
from mission_control.research import pi_backend as pi


def test_resolver_explicit_task_model_wins(monkeypatch):
    # stub read_config to avoid DB
    monkeypatch.setattr(inference, "read_config", lambda session: inference.LocalModelConfig(
        enabled=True, consent=True, base_url="http://127.0.0.1:11434", model="local-model",
        timeout_seconds=45, api_key_env="", api_key=None, provider="openai-compatible"))
    model, route = inference.resolve_model(object(), "opencode-go/deepseek-v4.1-flash")
    assert model == "opencode-go/deepseek-v4.1-flash" and route == pi.PI_ROUTE


def test_resolver_explicit_local_config_wins(monkeypatch):
    monkeypatch.setattr(inference, "read_config", lambda session: inference.LocalModelConfig(
        enabled=True, consent=True, base_url="http://127.0.0.1:11434", model="local-model",
        timeout_seconds=45, api_key_env="", api_key=None, provider="openai-compatible"))
    model, route = inference.resolve_model(object(), "")
    assert model == "local-model" and route == inference.LOCAL_ROUTE


def test_resolver_pi_default_without_rewrite(monkeypatch):
    monkeypatch.setattr(inference, "read_config", lambda session: inference.LocalModelConfig(
        enabled=True, consent=True, base_url="", model="",
        timeout_seconds=45, api_key_env="", api_key=None, provider="openai-compatible"))
    model, route = inference.resolve_model(object(), "")
    assert model == pi.PI_DEFAULT_MODEL == "opencode-go/deepseek-v4.1-flash"
    assert route == pi.PI_ROUTE


def test_pi_error_kinds_no_silent_switch():
    assert pi.classify_pi_error("HTTP 402 Insufficient balance") == "billing"
    assert pi.classify_pi_error("429 GoUsageLimitError") == "rate_limited"
    assert pi.classify_pi_error("401 unauthorized") == "auth"
    assert pi.classify_pi_error("model not found: x/y") == "model_not_found"
    assert pi.classify_pi_error("boom") is None


def test_pi_command_uses_path_lookup_not_ps1_direct(monkeypatch):
    import os
    import shutil
    monkeypatch.delenv("MISSION_PI", raising=False)
    monkeypatch.delenv("WORKBENCH_PI", raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: r"C:\Program Files\nodejs\node.EXE" if name == "node" else r"C:\Users\ernan\.pi\agent\bin\pi.cmd")
    # Direct node launcher avoids the cmd.exe/PowerShell re-quoting that
    # mangles JSON prompts (WinError 206 / "system cannot find the file").
    monkeypatch.setattr(os.path, "isfile", lambda path: True)
    assert pi.resolve_pi_command() == [
        r"C:\Program Files\nodejs\node.EXE",
        r"C:\Users\ernan\.pi\agent\bin\pi-launcher.js",
    ]
    # Falls back to the wrapper when no launcher sits next to it.
    monkeypatch.setattr(os.path, "isfile", lambda path: False)
    assert pi.resolve_pi_command() == [r"C:\Users\ernan\.pi\agent\bin\pi.cmd"]
