"""Logging with rotation and secret redaction."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from mission_control.config import RuntimeSettings

_SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)\b(sk-[a-z0-9_-]{8,})"),
    re.compile(r"(?i)\b(api[_-]?key|password|secret|token)\s*[=:]\s*([^\s,;]+)"),
]


def redact_text(value: str) -> str:
    redacted = value
    redacted = _SECRET_PATTERNS[0].sub(r"\1[REDACTED]", redacted)
    redacted = _SECRET_PATTERNS[1].sub("[REDACTED_API_KEY]", redacted)
    redacted = _SECRET_PATTERNS[2].sub(r"\1=[REDACTED]", redacted)
    return redacted


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        cleaned = redact_text(rendered)
        if cleaned != rendered:
            record.msg = cleaned
            record.args = ()
        return True


def configure_logging(settings: RuntimeSettings) -> None:
    settings.ensure_directories()
    root = logging.getLogger()
    if getattr(root, "_mission_control_configured", False):
        return
    root.setLevel(settings.log_level.upper())
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(RedactionFilter())
    root.addHandler(console)

    log_path: Path = settings.log_dir / "mission-control.log"
    file_handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(RedactionFilter())
    root.addHandler(file_handler)
    root._mission_control_configured = True  # type: ignore[attr-defined]
