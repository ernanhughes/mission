"""Blog-post editorial evaluation via the existing Pi model route (MC-WEBSITES-POSTS-01).

No new AI integration is introduced. Model calls go through the same Pi CLI
facility Mission Control already uses (``pi --model <id> -p ...`` with
``@file`` prompt injection), argument-based, no shell. The blog rubric
(``blog-editorial-v1``) is applied here; the book-chapter prose scorer is
never used for articles.

Outcomes mirror the quality conventions: CURRENT carries validated scores,
BLOCKED/ERROR/PARTIAL carry no fabricated scores (``overall`` stays NULL at
record time). Editorial evaluation never claims independent factual
verification of the article's external assertions.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from mission_control.research import pi_backend as _pi
from mission_control.websites import rubric as _rubric

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "opencode-go/deepseek-v4.1-flash"

#: Hard prompt budget (chars). Larger articles are refused explicitly, never
#: silently truncated.
MAX_EVAL_CHARS = 120_000

EVAL_TIMEOUT_SECONDS = 600.0


def resolve_eval_model(explicit: str | None = None) -> str | None:
    """Model selection: explicit request wins, then the blog-eval setting.

    Returns None when nothing is configured — callers must report the precise
    blocker instead of running anything.
    """
    if explicit and explicit.strip():
        return explicit.strip()
    configured = (os.environ.get("MISSION_CONTROL_BLOG_EVAL_MODEL") or "").strip()
    return configured or None


def blocked_message() -> str:
    return (
        "No blog evaluation model is configured: set MISSION_CONTROL_BLOG_EVAL_MODEL "
        f"to a Pi model id (for example '{DEFAULT_MODEL}') or pass an explicit model."
    )


def build_eval_prompt(*, title: str, relpath: str, article_text: str) -> str:
    """Full evaluator prompt: role, versioned rubric, strict JSON contract."""
    lines = [
        "You are an exacting editorial reviewer for a technical programming blog.",
        "Evaluate the article below with the blog-editorial-v1 rubric.",
        "",
        "EDITORIAL SCOPE (read carefully):",
        "- Judge the writing: thesis, substance, reasoning, evidence handling,",
        "  structure, clarity, reader value and economy.",
        "- Do NOT claim any external reference, figure, financial number, technical",
        "  assertion or quotation has been independently verified: reading the",
        "  article does not establish the truth of its external claims.",
        "- Unsupported claims may be flagged for human or external review, but",
        "  never declare them true or false.",
        "- The noisy automated reference checker is NOT part of this evaluation.",
        "",
        "RUBRIC (maximum points per dimension, total 1000):",
    ]
    for dim in _rubric.DIMENSIONS:
        lines.append(f"- {dim.id} ({dim.label}): 0..{dim.max_points}. {dim.guidance}")
    lines += [
        "",
        "OVERALL SCORE: the exact sum of the eight dimension scores (0..1000).",
        "Compute it by addition; never invent or round it.",
        "",
        "RETURN EXACTLY ONE JSON OBJECT AND NOTHING ELSE, with this shape:",
        "{",
        '  "overall": <int, must equal the sum of dimension scores>,',
        '  "dimensions": { "<id>": {"score": <int>, "explanation": "<2-4 sentences>"}, ... all eight ... },',
        '  "assessment": "<executive assessment, 4-8 sentences>",',
        '  "strengths": ["<strongest aspect 1>", "<2>", "<3>"],',
        '  "weaknesses": ["<most important weakness 1>", "<2>", "<3>"],',
        '  "improvements": [',
        '    {"rank": 1, "title": "<...>", "problem": "<observed problem>",',
        '     "why_it_matters": "<...>", "suggestion": "<concrete improvement>",',
        '     "source_heading": "<nearest heading or null>",',
        '     "source_quote": "<verbatim passage or null>"},',
        "    ... exactly 3, ranked 1..3 ...",
        "  ],",
        '  "findings": [',
        '    {"finding_id": "<stable id>", "kind": "observation|risk|gap",',
        '     "title": "<...>", "detail": "<...>",',
        '     "source_heading": "<nearest heading or null>",',
        '     "source_quote": "<verbatim passage or null>"},',
        "    ... additional findings with source evidence ...",
        "  ],",
        '  "uncertainty": "<what remains uncertain>",',
        '  "limitations": ["<limitation of this review>", ...]',
        "}",
        "",
        "QUOTE RULE: every source_quote must occur verbatim in the article text",
        "(whitespace differences allowed). If no passage fits, use null.",
        "Never invent a quotation or a position.",
        "",
        "ARTICLE:",
        f"Title: {title}",
        f"Source: {relpath}",
        "---",
        article_text,
    ]
    return "\n".join(lines)


def _extract_json(output: str) -> tuple[dict[str, Any] | None, str | None]:
    """Extract the JSON object from model output. Returns (payload, error)."""
    text = output.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None, "Evaluator output contained no JSON object."
    try:
        payload = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        return None, f"Unparsable evaluator output: {exc}"
    if not isinstance(payload, dict):
        return None, "Evaluator output was not a JSON object."
    return payload, None


def _validate_payload(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Validate the evaluator payload against the rubric contract."""
    dims = payload.get("dimensions")
    if not isinstance(dims, dict):
        return None, "Evaluator payload is missing the dimensions mapping."
    scores: dict[str, Any] = {}
    explanations: dict[str, str] = {}
    for key, entry in dims.items():
        if not isinstance(entry, dict):
            return None, f"Dimension {key!r} is not an object."
        scores[key] = entry.get("score")
        explanations[key] = str(entry.get("explanation", ""))
    total, cleaned, errors = _rubric.validate_scores(scores)
    if errors:
        return None, "Invalid dimension scores: " + "; ".join(errors[:5])
    overall = payload.get("overall")
    if isinstance(overall, bool) or not isinstance(overall, (int, float)) or int(overall) != total:
        return None, (
            f"Overall score {overall!r} does not equal the dimension sum {total}."
        )
    for field in ("strengths", "weaknesses"):
        items = payload.get(field)
        if not isinstance(items, list) or len(items) != 3 or not all(
            isinstance(item, str) and item.strip() for item in items
        ):
            return None, f"Evaluator must return exactly 3 non-empty {field}."
    improvements = payload.get("improvements")
    if not isinstance(improvements, list) or len(improvements) < 3:
        return None, "Evaluator must return at least 3 ranked improvements."
    ranked = sorted(
        (item for item in improvements if isinstance(item, dict)),
        key=lambda item: item.get("rank", 99),
    )[:3]
    if [item.get("rank") for item in ranked] != [1, 2, 3]:
        # Accept any three well-formed improvements; normalise ranks here.
        for index, item in enumerate(ranked, start=1):
            item["rank"] = index
    for item in ranked:
        for key in ("title", "problem", "why_it_matters", "suggestion"):
            if not isinstance(item.get(key), str) or not str(item.get(key)).strip():
                return None, f"Improvement {item.get('rank')} is missing {key!r}."
    findings = payload.get("findings")
    if findings is None:
        findings = []
    if not isinstance(findings, list):
        return None, "Evaluator findings must be a list."
    for index, item in enumerate(findings):
        if not isinstance(item, dict):
            return None, f"Finding {index} is not an object."
        if not str(item.get("title", "")).strip() or not str(item.get("detail", "")).strip():
            return None, f"Finding {index} needs a title and detail."
        if not str(item.get("finding_id", "")).strip():
            item["finding_id"] = f"finding-{index + 1}"
    assessment = payload.get("assessment")
    if not isinstance(assessment, str) or not assessment.strip():
        return None, "Evaluator must return an executive assessment."
    return {
        "overall": total,
        "scores": cleaned,
        "explanations": explanations,
        "assessment": assessment,
        "strengths": list(payload["strengths"]),
        "weaknesses": list(payload["weaknesses"]),
        "improvements": ranked,
        "findings": findings,
        "uncertainty": str(payload.get("uncertainty", "")),
        "limitations": list(payload.get("limitations", []))
        if isinstance(payload.get("limitations"), list) else [],
    }, None


def run_pi_evaluation(
    *,
    model: str,
    title: str,
    relpath: str,
    article_text: str,
    timeout: float = EVAL_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run one editorial evaluation through Pi. Never fabricates scores.

    Returns an outcome dict: on success ``status=CURRENT`` with the validated
    payload; otherwise ``status`` BLOCKED/ERROR with ``error`` and no scores.
    """
    article_chars = len(article_text)
    prompt = build_eval_prompt(title=title, relpath=relpath, article_text=article_text)
    if len(prompt) > MAX_EVAL_CHARS:
        return {"status": "BLOCKED",
                "error": (f"Article prompt ({len(prompt)} chars) exceeds the evaluation "
                          f"budget of {MAX_EVAL_CHARS} chars; refused rather than truncated.")}
    pi_cmd: list[str]
    try:
        pi_cmd = _pi.resolve_pi_command()
    except (FileNotFoundError, OSError):
        return {"status": "BLOCKED",
                "error": "Pi command not found: set MISSION_PI or WORKBENCH_PI, "
                         "or ensure 'pi' is on PATH."}
    tmp_path: Path | None = None
    started = time.monotonic()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".eval-prompt.md", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(prompt)
            tmp_path = Path(handle.name)
        # Mirror pi_backend._run_pi: explicit offline default, no console window.
        import sys as _sys

        env = dict(os.environ)
        env.setdefault("PI_OFFLINE", "0")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if _sys.platform == "win32" else 0
        argv = [
            *pi_cmd, "--model", model, "--no-tools", "--no-extensions", "--no-skills",
            "--no-prompt-templates", "--no-context-files", "--no-session",
            "--no-mcp", "-p", f"@{tmp_path}",
        ]
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout, shell=False, check=False,
                env=env, creationflags=creationflags)
        except subprocess.TimeoutExpired:
            return {"status": "BLOCKED",
                    "error": f"Evaluator timed out after {timeout:g}s; no scores recorded.",
                    "execution": _execution(model, started, article_chars, len(prompt))}
        except OSError as exc:
            return {"status": "BLOCKED",
                    "error": f"Evaluator launch failed: {exc}",
                    "execution": _execution(model, started, article_chars, len(prompt))}
        if proc.returncode != 0:
            return {"status": "BLOCKED",
                    "error": f"Evaluator exited {proc.returncode}: {(proc.stderr or '')[:500]}",
                    "execution": _execution(model, started, article_chars, len(prompt))}
        payload, error = _extract_json(proc.stdout or "")
        if error is not None:
            return {"status": "ERROR", "error": error,
                    "execution": _execution(model, started, article_chars, len(prompt))}
        validated, error = _validate_payload(payload)
        if error is not None:
            return {"status": "ERROR", "error": error,
                    "execution": _execution(model, started, article_chars, len(prompt))}
        assert validated is not None
        return {"status": "CURRENT", **validated,
                "execution": _execution(model, started, article_chars, len(prompt))}
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _execution(model: str, started: float, article_chars: int, prompt_chars: int) -> dict[str, Any]:
    return {
        "transport": "pi",
        "requested_model": model,
        "actual_model": model,
        "duration_s": round(time.monotonic() - started, 1),
        "article_chars": article_chars,
        "prompt_chars": prompt_chars,
        "token_usage": "unknown",
        "cost_usd": None,
        "costs_unknown": True,
    }
