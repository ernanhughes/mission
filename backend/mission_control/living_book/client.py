"""A narrow, loopback-only HTTP client for ALIVE's living-book API.

No URL or path from a browser becomes an outbound target here. The base URL comes from
Mission's application registry or runtime settings and must be loopback.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlsplit

import httpx


class LivingBookUnavailable(RuntimeError):
    """ALIVE is not reachable or did not answer with JSON."""


class LivingBookError(RuntimeError):
    def __init__(self, message: str, status: int | None = None,
                 correlation_id: str | None = None):
        super().__init__(message)
        self.status = status
        self.correlation_id = correlation_id


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
MAX_RESPONSE_BYTES = 4_000_000


def validate_base_url(value: str) -> str:
    raw = (value or "").strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOOPBACK_HOSTS:
        raise LivingBookUnavailable(
            "The ALIVE endpoint must be a loopback http(s) URL, for example http://127.0.0.1:8000."
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LivingBookUnavailable(
            "The ALIVE endpoint must not contain credentials or query data."
        )
    return raw


class AliveClient:
    def __init__(self, base_url: str):
        self.base_url = validate_base_url(base_url)

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        timeout: float = 15.0,
        allow_unavailable: bool = False,
        allow_null: bool = False,
    ) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.request(method, self._url(path), json=body)
        except httpx.TimeoutException:
            if allow_unavailable:
                return {"status": "unavailable", "detail": "ALIVE did not answer in time."}
            raise LivingBookUnavailable("ALIVE did not answer in time.") from None
        except httpx.HTTPError as error:
            if allow_unavailable:
                return {
                    "status": "unavailable",
                    "detail": f"ALIVE is not reachable at {self.base_url}.",
                }
            raise LivingBookUnavailable(
                f"ALIVE is not reachable at {self.base_url}. {type(error).__name__}."
            ) from None
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise LivingBookError("ALIVE returned more data than this surface accepts.", 502)
        content_type = response.headers.get("content-type", "")
        try:
            payload = response.json()
        except ValueError:
            if allow_unavailable:
                return {
                    "status": "unavailable",
                    "detail": "ALIVE returned an unreadable response.",
                }
            raise LivingBookUnavailable("ALIVE returned an unreadable response.") from None
        if not response.is_success:
            detail = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
            if not detail and isinstance(payload, dict):
                detail = payload.get("detail")
            message = (
                detail
                if isinstance(detail, str)
                else f"ALIVE returned HTTP {response.status_code}."
            )
            correlation = response.headers.get("x-correlation-id")
            raise LivingBookError(message[:1000], response.status_code, correlation)
        if payload is None and allow_null and content_type.startswith("application/json"):
            return None
        if not isinstance(payload, dict) or not content_type.startswith("application/json"):
            raise LivingBookUnavailable("ALIVE returned an unexpected response type.")
        return payload

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health", timeout=3.0, allow_unavailable=True)

    async def list_books(self, manuscript_root: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/living-books?manuscript_root=" + quote(manuscript_root, safe=""),
        )

    async def book(self, book_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/living-books/{quote(book_id, safe='')}")

    async def chapter(self, book_id: str, chapter_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/living-books/{quote(book_id, safe='')}/chapters/{quote(chapter_id, safe='')}",
        )

    async def reading(self, book_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "PUT", f"/living-books/{quote(book_id, safe='')}/reading", body=body
        )

    async def annotations(self, book_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/living-books/{quote(book_id, safe='')}/annotations")

    async def add_annotation(self, book_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", f"/living-books/{quote(book_id, safe='')}/annotations", body=body
        )

    async def remove_annotation(self, book_id: str, annotation_id: str) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            f"/living-books/{quote(book_id, safe='')}/annotations/{quote(annotation_id, safe='')}",
        )

    async def note(self, book_id: str, chapter_id: str) -> dict[str, Any] | None:
        return await self._request(
            "GET",
            f"/living-books/{quote(book_id, safe='')}/chapters/{quote(chapter_id, safe='')}/note",
            allow_null=True,
        )

    async def build_note(
        self, book_id: str, chapter_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/living-books/{quote(book_id, safe='')}/chapters/{quote(chapter_id, safe='')}/note",
            body=body,
            timeout=180.0,
        )

    async def ask(self, book_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", f"/living-books/{quote(book_id, safe='')}/ask", body=body, timeout=240.0
        )

    async def represent(self, book_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/living-books/{quote(book_id, safe='')}/representations",
            body=body,
            timeout=240.0,
        )

    async def representations(
        self, book_id: str, chapter_id: str | None = None
    ) -> dict[str, Any]:
        path = f"/living-books/{quote(book_id, safe='')}/representations"
        if chapter_id:
            path += "?chapter_id=" + quote(chapter_id, safe="")
        return await self._request("GET", path, timeout=30.0)

    async def representation(self, book_id: str, representation_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/living-books/{quote(book_id, safe='')}/representations/"
            f"{quote(representation_id, safe='')}",
            timeout=30.0,
        )

    async def reject_representation(self, book_id: str, representation_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/living-books/{quote(book_id, safe='')}/representations/"
            f"{quote(representation_id, safe='')}/reject",
            timeout=30.0,
        )

    async def conversation(self, book_id: str, conversation_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/living-books/{quote(book_id, safe='')}/conversations/"
            f"{quote(conversation_id, safe='')}",
        )

    async def revoke_session(self, book_id: str, consent_ref: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/living-books/{quote(book_id, safe='')}/sessions/{quote(consent_ref, safe='')}/revoke",
        )

    async def refresh(self, book_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/living-books/{quote(book_id, safe='')}/refresh", timeout=120.0
        )

    async def preview_source(self, path: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/sources/projects/preview", body={"path": path}, timeout=120.0
        )

    async def register_source(self, label: str, path: str, confirm_root: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/sources/projects",
            body={"label": label, "path": path, "confirm_root": confirm_root},
            timeout=180.0,
        )

    async def approve_source(
        self, capture_id: str, *, content_sha256: str, request_id: str, ttl_seconds: int
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/sources/{quote(capture_id, safe='')}/approve",
            body={
                "confirm_sha256": content_sha256,
                "scope": {"all": True},
                "profile": "live",
                "ttl_seconds": ttl_seconds,
                "request_id": request_id,
            },
            timeout=60.0,
        )

    async def register_book(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/living-books", body=body, timeout=60.0)

    async def workspace(self, workspace_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/workspaces/{quote(workspace_id, safe='')}", timeout=30.0
        )

    async def workflow_plan(self, workspace_id: str, chapter_path: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/workspaces/{quote(workspace_id, safe='')}/workflows/plan"
            f"?chapter_path={quote(chapter_path, safe='')}",
            timeout=120.0,
        )

    async def improvements(self, workspace_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/workspaces/{quote(workspace_id, safe='')}/improvements", timeout=30.0
        )

    async def experience(
        self, workspace_id: str, chapter_path: str, criteria: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/workspaces/{quote(workspace_id, safe='')}/experience"
            f"?chapter_path={quote(chapter_path, safe='')}"
            f"&criteria={quote(criteria, safe='')}",
            timeout=30.0,
        )

    async def launch_workflow(
        self, workspace_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/workspaces/{quote(workspace_id, safe='')}/workflows",
            body=body,
            timeout=120.0,
        )

    async def workflow_run(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/workspaces/{quote(workspace_id, safe='')}/workflows/{quote(run_id, safe='')}",
            timeout=30.0,
        )

    async def improvement(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/workspaces/{quote(workspace_id, safe='')}/workflows/{quote(run_id, safe='')}"
            "/improvement",
            timeout=30.0,
        )

    async def decide(
        self, workspace_id: str, run_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/workspaces/{quote(workspace_id, safe='')}/workflows/{quote(run_id, safe='')}"
            "/improvement/decisions",
            body=body,
            timeout=30.0,
        )

    async def workflow_runs(self, workspace_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/workspaces/{quote(workspace_id, safe='')}/workflows", timeout=30.0
        )

    async def chapter_evaluations(
        self, workspace_id: str, source_run_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/workspaces/{quote(workspace_id, safe='')}/chapter-evaluations"
            f"?source_run_id={quote(source_run_id, safe='')}",
            timeout=30.0,
        )

    async def chapter_evaluation(
        self, workspace_id: str, evaluation_run_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/workspaces/{quote(workspace_id, safe='')}/chapter-evaluations/"
            f"{quote(evaluation_run_id, safe='')}",
            timeout=30.0,
        )
