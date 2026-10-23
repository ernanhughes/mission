"""Emits a fake secret so log redaction can be verified."""

from __future__ import annotations

import time


def main() -> int:
    print("starting diagnostic", flush=True)
    print("api_key=sk-testSECRET1234567890", flush=True)
    print("Authorization: Bearer super-secret-token", flush=True)
    time.sleep(10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
