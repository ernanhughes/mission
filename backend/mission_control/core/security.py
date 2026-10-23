"""Local-origin and response-header protections.

The backend binds to loopback by default. Browser requests that could cause
local execution must carry an allowlisted Origin and a non-simple custom
header. This blocks cross-site form posts and simple requests from a malicious
page; non-browser local CLI clients (no Origin) remain usable.
"""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
REQUIRED_HEADER = "x-mission-control-request"
LOCAL_ORIGIN_REQUIRED = "1"


class OriginGuardMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: tuple[str, ...]) -> None:
        self.app = app
        self.allowed_origins = set(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["method"] in UNSAFE_METHODS:
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            if origin is not None:
                if origin not in self.allowed_origins:
                    await self._reject(scope, receive, send, "Origin is not allowed")
                    return
                if headers.get(REQUIRED_HEADER) != LOCAL_ORIGIN_REQUIRED:
                    await self._reject(scope, receive, send, "Missing local request header")
                    return
        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send, message: str) -> None:
        response = JSONResponse(
            status_code=403,
            content={"error": {"code": "origin_rejected", "message": message, "detail": None}},
        )
        await response(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                path = scope.get("path", "")
                if path.startswith("/docs"):
                    # FastAPI's Swagger UI is loaded from a CDN and includes an
                    # inline bootstrap script. Keep the stricter policy for the
                    # application and relax only the API documentation routes.
                    csp = (
                        b"default-src 'self' https://cdn.jsdelivr.net; "
                        b"img-src 'self' data: https://fastapi.tiangolo.com; "
                        b"style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                        b"script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                        b"frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
                    )
                else:
                    csp = (
                        b"default-src 'self'; img-src 'self' data:; "
                        b"style-src 'self' 'unsafe-inline'; script-src 'self'; "
                        b"connect-src 'self' http://127.0.0.1:5173 http://localhost:5173; "
                        b"frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
                    )
                additions = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"no-referrer",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                    b"content-security-policy": csp,
                }
                present = {key.lower() for key, _ in headers}
                for key, value in additions.items():
                    if key not in present:
                        headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, _send)


def add_middleware(app, allowed_origins: tuple[str, ...]) -> None:  # type: ignore[no-untyped-def]
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(OriginGuardMiddleware, allowed_origins=allowed_origins)
