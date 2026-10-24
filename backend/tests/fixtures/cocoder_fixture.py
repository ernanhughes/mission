"""Deterministic CoCoder CLI fixture for action-contract tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    try:
        output = Path(argv[argv.index("--output") + 1])
    except (ValueError, IndexError):
        print("--output is required", file=sys.stderr)
        return 2
    review = {
        "schema_version": "0.2",
        "base": "BASE",
        "head": "HEAD",
        "working_tree": False,
        "changed_files": ["src/example.py"],
        "change_shape": {"files_changed": 1, "behaviour_bearing_python_lines": 12},
        "evidence": [
            {
                "fact_id": "EXC-fixture",
                "kind": "exception_boundary_widened",
                "description": "The handler now catches Exception.",
                "path": "src/example.py",
                "symbol": "run",
                "after_line": 9,
            }
        ],
        "findings": [
            {
                "finding_id": "F-fixture",
                "rule_code": "EXCEPTION_HANDLER_WIDENED",
                "category": "exception_boundary",
                "title": "Exception handling widened",
                "statement": "The handler catches Exception and does not re-raise.",
                "claim_type": "derived_structural_effect",
                "severity": "high",
                "confidence": "confirmed",
                "evidence_ids": ["EXC-fixture"],
                "assumptions": [],
                "unknowns": ["Which exception types are intended."],
                "question": "Should the handler be narrower?",
                "remediation": None,
            }
        ],
        "unknowns": ["Runtime correctness is not inferred."],
        "analysis_limitations": ["Fixture review."],
        "symbols": [],
        "detector_failures": 0,
        "request": None,
        "structural_analysis": None,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(review, indent=2), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
