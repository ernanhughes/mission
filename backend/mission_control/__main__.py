"""Windows-friendly entry point."""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mission-control", description="Run the local Mission Control server")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8790, help="Port (default: 8790)")
    parser.add_argument("--reload", action="store_true", help="Development reload")
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Mission Control only binds to loopback")
    os.environ["MISSION_CONTROL_HOST"] = args.host
    os.environ["MISSION_CONTROL_PORT"] = str(args.port)
    import uvicorn

    print(f"Mission Control: http://{args.host}:{args.port}")
    uvicorn.run(
        "mission_control.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
