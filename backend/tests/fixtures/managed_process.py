"""Safe child process used by real process-management tests."""

from __future__ import annotations

import os
import sys
import time


def main() -> int:
    print(f"fixture-start pid={os.getpid()}", flush=True)
    print(f"fixture-cwd={os.getcwd()}", flush=True)
    print(f"fixture-arg={sys.argv[1] if len(sys.argv) > 1 else ''}", flush=True)
    deadline = time.time() + 30
    while time.time() < deadline:
        print("fixture-tick", flush=True)
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
