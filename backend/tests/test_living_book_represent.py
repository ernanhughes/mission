"""MC-LIVING-BOOK-02C: Mission representation proxy.

The proxy owns no cognition: it forwards the reader's passage + task to ALIVE
and returns the retained record. ALIVE does the resolving, obligating,
generating and validating.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from mission_control.living_book import service
from test_living_book import FakeAlive, _book_tree, _project


class RepresentAlive(FakeAlive):
    async def represent(self, book_id: str, body: dict):
        self.calls.append(("represent", body))
        assert body["chapter_id"] == "01-chapter.md"
        assert body["quote"]
        assert body["idempotency_key"]
        assert "fixture" not in body  # the UI never sends the test flag
        return {
            "id": "rep-1",
            "task": body["task"],
            "transformation_class": "reveal",
            "chapter_id": "01-chapter.md",
            "source": {"chapter_sha256": "a" * 64},
            "passage": {"text": body["quote"], "sha256": "b" * 64},
            "rendering": {"format": "markdown", "content": "### Explanation (fixture)"},
            "citations": [{"quote": body["quote"][:20]}],
            "added": [],
            "verification": {"standing": "attention", "reason": "fixture"},
            "model": {"name": "fixture-deterministic-v1", "fixture": True},
            "rejected": False,
        }

    async def representations(self, book_id: str, chapter_id: str | None = None):
        return {"representations": [{"id": "rep-1", "chapter_id": "01-chapter.md"}]}

    async def representation(self, book_id: str, representation_id: str):
        assert representation_id == "rep-1"
        return {"id": "rep-1", "chapter_id": "01-chapter.md", "rejected": False}

    async def reject_representation(self, book_id: str, representation_id: str):
        assert representation_id == "rep-1"
        return {"id": "rep-1", "chapter_id": "01-chapter.md", "rejected": True}


def _wired(client: TestClient, tmp_path, monkeypatch) -> str:
    root = _book_tree(tmp_path)
    project_id = _project(client, root)
    fake = RepresentAlive(root / "content" / "books" / "distillation")
    fake.registered = True
    monkeypatch.setattr(service, "_client", lambda session, settings: fake)
    return project_id


def test_represent_forwards_passage_and_task(client: TestClient, tmp_path, monkeypatch):
    _wired(client, tmp_path, monkeypatch)
    response = client.post(
        "/api/living-book/projects/living-test/representations",
        json={
            "chapter_id": "01-chapter.md",
            "task": "explain",
            "quote": "A teacher signal.",
            "idempotency_key": "rep-test-1",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == "rep-1"
    assert body["verification"]["standing"] == "attention"
    assert body["model"]["fixture"] is True


def test_list_get_and_reject_representation(client: TestClient, tmp_path, monkeypatch):
    _wired(client, tmp_path, monkeypatch)
    listed = client.get(
        "/api/living-book/projects/living-test/representations",
        params={"chapter_id": "01-chapter.md"},
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["representations"][0]["id"] == "rep-1"

    fetched = client.get("/api/living-book/projects/living-test/representations/rep-1")
    assert fetched.status_code == 200, fetched.text

    rejected = client.post(
        "/api/living-book/projects/living-test/representations/rep-1/reject", json={}
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["rejected"] is True


def test_represent_validates_task(client: TestClient, tmp_path, monkeypatch):
    _wired(client, tmp_path, monkeypatch)
    response = client.post(
        "/api/living-book/projects/living-test/representations",
        json={
            "chapter_id": "01-chapter.md",
            "task": "invent",
            "quote": "A teacher signal.",
            "idempotency_key": "rep-test-2",
        },
    )
    assert response.status_code == 422, response.text
