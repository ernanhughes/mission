"""Tiny HTTP server for ensure-open tests.

Serves a Workbench-identifying page (``workbench`` mode) or a generic page
(``other`` mode) on 127.0.0.1. ``other`` mode simulates a port conflict: a
listener that is not Workbench.
"""

from __future__ import annotations

import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    mode = sys.argv[2] if len(sys.argv) > 2 else "workbench"
    if mode == "workbench":
        title = "Workbench"
    else:
        title = "Something Else"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = (
                f"<html><head><title>{title}</title></head>"
                f"<body>fixture mode={mode}</body></html>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"fixture-start port={server.server_port}", flush=True)
    deadline = time.time() + 60
    server.timeout = 0.2
    while time.time() < deadline:
        server.handle_request()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
