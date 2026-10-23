"""Editor stand-in used to verify configured repository opening.

Appends the received path to a file named by EDITOR_PROBE_LOG. Environment
variables are explicitly allowed by the application's editor configuration in
the test.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    target = sys.argv[-1] if len(sys.argv) > 1 else ""
    log = os.environ.get("EDITOR_PROBE_LOG")
    if log:
        Path(log).write_text(target, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
