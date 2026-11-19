from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mission_control.living_book import service
from mission_control.models import QualityEvaluation, now_iso


def _book_tree(tmp_path: Path) -> Path:
    root = tmp_path / "distillation"
    chapters = root / "content" / "books" / "distillation"
    chapters.mkdir(parents=True)
    (chapters / "01-chapter.md").write_text(
        "# First chapter\n\nA teacher signal.\n", encoding="utf-8"
    )
    (chapters / "02-chapter.md").write_text("# Second chapter\n\nA student.\n", encoding="utf-8")
    (root / "planning").mkdir()
    (root / "planning" / "01-evidence.md").write_text(
        "# Evidence\n\nNot a verdict.\n", encoding="utf-8"
    )
    (root / "public" / "images").mkdir(parents=True)
    (root / "public" / "images" / "cover.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8"
    )
    return root


def _project(client: TestClient, root: Path) -> str:
    response = client.post(
        "/api/projects",
        json={
            "id": "living-test",
            "name": "Living Test",
            "kind": "book",
            "repository_path": str(root),
            "book_title": "Living Test Book",
        },
    )
    assert response.status_code == 201, response.text
    updated = client.patch(
        "/api/books/book-living-test",
        json={
            "manuscript_paths": [str(root / "content" / "books" / "distillation")],
        },
    )
    assert updated.status_code == 200, updated.text
    return "living-test"


def _add_evaluation(client: TestClient) -> None:
    database = client.app.state.database
    with database.session() as session:
        session.add(
            QualityEvaluation(
                id="mqeval:living-test",
                project_id="living-test",
                book_id="",
                chapter_id="01-chapter.md",
                source_path="01-chapter.md",
                chapter_revision="a" * 64,
                rubric_id="manuscript-prose-v1",
                rubric_version=1,
                prompt_version="1",
                requested_model="model",
                actual_model="model",
                status="CURRENT",
                overall=3.0,
                aggregation_method="mean_equal_weights_v1",
                dimensions={
                    "clarity": {
                        "dimension": "clarity",
                        "score": 3,
                        "evidence": "A teacher signal.",
                        "evidence_validated": False,
                    },
                    "argument": {
                        "dimension": "argument",
                        "score": 3,
                        "evidence": "A student.",
                        "evidence_validated": False,
                    },
                    "precision": {
                        "dimension": "precision",
                        "score": 3,
                        "evidence": "",
                        "evidence_validated": False,
                    },
                    "economy": {
                        "dimension": "economy",
                        "score": 3,
                        "evidence": "",
                        "evidence_validated": False,
                    },
                    "voice": {
                        "dimension": "voice",
                        "score": 3,
                        "evidence": "",
                        "evidence_validated": False,
                    },
                    "structure": {
                        "dimension": "structure",
                        "score": 3,
                        "evidence": "",
                        "evidence_validated": False,
                    },
                },
                findings=[],
                uncertainty="Single-run model judgment.",
                limitations=["Single-run model judgment."],
                execution={},
                char_span=[],
                strategy="direct",
                created_at=now_iso(),
            )
        )
        session.commit()


class FakeAlive:
    base_url = "http://127.0.0.1:8000"

    def __init__(self, root: Path):
        self.root = str(root)
        self.calls: list[tuple[str, object]] = []
        self.registered = False

    async def health(self):
        return {"status": "ok"}

    async def list_books(self, manuscript_root: str):
        if not self.registered:
            return {"books": []}
        return {
            "books": [
                {
                    "id": "book-1",
                    "title": "Living Test Book",
                    "manuscript_root": self.root,
                }
            ]
        }

    async def book(self, book_id: str):
        return {
            "id": book_id,
            "title": "Living Test Book",
            "ready": True,
            "error": None,
            "source": {"binding_ref": "binding-1", "status": "current", "current": True},
            "chapters": [
                {"chapter_id": "01-chapter.md", "title": "First chapter", "status": "current"},
                {"chapter_id": "02-chapter.md", "title": "Second chapter", "status": "current"},
            ],
            "reading": None,
            "annotations": [],
            "notes": [],
            "conversations": [],
            "model": {"name": "model", "transport": "pi", "ready": True},
        }

    async def preview_source(self, path: str):
        self.calls.append(("preview", path))
        return {"root": path, "inventory": {"summary": {"files": 4, "bytes": 100}}}

    async def register_source(self, label: str, path: str, confirm_root: str):
        self.calls.append(("register", path))
        return {"capture": {"id": "capture-1", "content_sha256": "a" * 64}}

    async def approve_source(self, capture_id: str, **kwargs):
        self.calls.append(("approve", capture_id))
        return {"id": "approval-1", "capture_id": capture_id}

    async def register_book(self, body):
        self.calls.append(("book", body))
        self.registered = True
        return {"id": "book-1", "title": body["title"]}

    async def chapter(self, book_id: str, chapter_id: str):
        return {
            "chapter_id": chapter_id,
            "title": "First chapter",
            "markdown": "# First chapter\n\nA teacher signal.\n",
            "sha256": "a" * 64,
        }

    async def reading(self, book_id: str, body):
        return body

    async def annotations(self, book_id: str):
        return {"annotations": []}

    async def add_annotation(self, book_id: str, body):
        return {"id": "annotation-1", **body}

    async def remove_annotation(self, book_id: str, annotation_id: str):
        return {"id": annotation_id, "removed": True}

    async def ask(self, book_id: str, body):
        self.calls.append(("ask", body))
        return {"id": "conversation-1", "answer": "Grounded answer.", "status": "completed"}

    async def build_note(self, book_id: str, chapter_id: str, body):
        self.calls.append(("note", body))
        return {"id": "note-1", "chapter_id": chapter_id, "markdown": "## Note"}

    async def note(self, book_id: str, chapter_id: str):
        return {"id": "note-1", "chapter_id": chapter_id, "markdown": "## Note"}

    async def conversation(self, book_id: str, conversation_id: str):
        return {"id": conversation_id, "messages": []}

    async def refresh(self, book_id: str):
        return {"refresh": {"changed": False}}

    async def revoke_session(self, book_id: str, consent_ref: str):
        return {"state": "revoked"}


def test_status_is_truthful_when_alive_is_unavailable(client: TestClient, tmp_path, monkeypatch):
    root = _book_tree(tmp_path)
    _project(client, root)
    _add_evaluation(client)

    class Down(FakeAlive):
        async def health(self):
            return {"status": "unavailable", "detail": "ALIVE is not running."}

    monkeypatch.setattr(service, "_client", lambda session, settings: Down(root))
    response = client.get("/api/living-book/projects/living-test")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is False
    assert body["state"] == "unavailable"
    assert body["quality"]["coverage"]["prose"]["current"] == 1
    assert body["quality"]["summary"]["overall_min"] == 3.0


def test_connect_requires_explicit_approval_and_uses_candidate_roots(
    client: TestClient, tmp_path, monkeypatch
):
    root = _book_tree(tmp_path)
    _project(client, root)
    fake = FakeAlive(root / "content" / "books" / "distillation")
    monkeypatch.setattr(service, "_client", lambda session, settings: fake)

    state = client.get("/api/living-book/projects/living-test").json()
    assert state["state"] == "not_connected"
    assert {item["kind"] for item in state["candidates"]} == {"manuscript", "repository"}

    denied = client.post(
        "/api/living-book/projects/living-test/connect",
        json={"root": str(root), "approve": False},
    )
    assert denied.status_code == 403
    assert fake.calls == []

    preview = client.post(
        "/api/living-book/projects/living-test/connect/preview",
        json={"root": str(root)},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["preview"]["root"] == str(root)

    connected = client.post(
        "/api/living-book/projects/living-test/connect",
        json={"root": str(root), "approve": True},
    )
    assert connected.status_code == 200, connected.text
    assert connected.json()["book"]["id"] == "book-1"
    assert ("approve", "capture-1") in fake.calls


def test_chapter_and_ask_preserve_quality_context(client: TestClient, tmp_path, monkeypatch):
    root = _book_tree(tmp_path)
    _project(client, root)
    _add_evaluation(client)
    fake = FakeAlive(root / "content" / "books" / "distillation")
    fake.registered = True
    monkeypatch.setattr(service, "_client", lambda session, settings: fake)

    status = client.get("/api/living-book/projects/living-test").json()
    assert status["state"] == "ready"
    assert status["quality"]["coverage"]["prose"]["current"] == 1

    chapter = client.get("/api/living-book/projects/living-test/chapters/01-chapter.md")
    assert chapter.status_code == 200, chapter.text
    assert "A teacher signal" in chapter.json()["markdown"]

    asked = client.post(
        "/api/living-book/projects/living-test/ask",
        json={
            "message": "Why did this score 3.0?",
            "chapter_id": "01-chapter.md",
            "scope": "chapter",
            "idempotency_key": "mission-ask-1",
        },
    )
    assert asked.status_code == 200, asked.text
    body = fake.calls[-1][1]
    assert body["quality_context"]["schema"] == "book-quality-context.v1"
    assert body["quality_context"]["measures"][0]["value"]["overall"] == 3.0
    assert body["quality_context"]["coverage"]["publication"]["status"] == "NOT_RUN"
    assert asked.json()["answer"] == "Grounded answer."


def test_quality_context_never_invents_a_composite(client: TestClient, tmp_path):
    root = _book_tree(tmp_path)
    _project(client, root)
    _add_evaluation(client)
    response = client.get(
        "/api/living-book/projects/living-test/quality",
        params={"chapter_id": "01-chapter.md"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "composite" not in response.text.lower()
    assert body["summary"]["overall_min"] == 3.0
    assert body["coverage"]["technical"]["status"] == "NOT_RUN"
    assert body["coverage"]["publication"]["status"] == "NOT_RUN"
    assert body["measures"][0]["limitations"]
    assert body["limitations"][0].startswith("Prose scores are single-run")


def test_missing_living_note_is_null_not_unavailable(client: TestClient, tmp_path, monkeypatch):
    root = _book_tree(tmp_path)
    _project(client, root)
    fake = FakeAlive(root / "content" / "books" / "distillation")
    fake.registered = True

    async def no_note(book_id: str, chapter_id: str):
        return None

    fake.note = no_note
    monkeypatch.setattr(service, "_client", lambda session, settings: fake)
    response = client.get("/api/living-book/projects/living-test/notes/01-chapter.md")
    assert response.status_code == 200, response.text
    assert response.json() is None


def test_assets_are_bounded_to_book_images(client: TestClient, tmp_path):
    root = _book_tree(tmp_path)
    _project(client, root)

    served = client.get(
        "/api/living-book/projects/living-test/assets",
        params={"path": "images/cover.svg"},
    )
    assert served.status_code == 200, served.text
    assert served.headers["content-type"].startswith("image/svg")

    traversal = client.get(
        "/api/living-book/projects/living-test/assets",
        params={"path": "../secret.svg"},
    )
    assert traversal.status_code == 422

    non_image = client.get(
        "/api/living-book/projects/living-test/assets",
        params={"path": "content/books/distillation/01-chapter.md"},
    )
    assert non_image.status_code == 422
