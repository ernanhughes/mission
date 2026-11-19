from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mission_control.living_book import service
from mission_control.living_book.client import LivingBookError
from test_living_book import FakeAlive, _add_evaluation, _book_tree, _project


class ImprovementAlive(FakeAlive):
    def __init__(self, root: Path, *, attachment_current: bool = True):
        super().__init__(root)
        self.attachment_current = attachment_current
        self.launched: list[dict] = []
        self.decisions: list[dict] = []
        self.decided = False
        self.earlier_version = False

    async def book(self, book_id: str):
        value = await super().book(book_id)
        value.update(
            {
                "workspace_id": "ws-1",
                "source": {
                    "binding_ref": "binding-1",
                    "approval_ref": "approval-1",
                    "capture_ref": "capture-1",
                    "status": "current",
                    "mode": "pinned",
                    "root": self.root,
                    "files": 4,
                    "bytes": 100,
                    "current": True,
                },
                "chapters": [
                    {
                        "chapter_id": "01-chapter.md",
                        "path": "content/books/distillation/01-chapter.md",
                        "title": "First chapter",
                        "status": "current",
                        "sha256": "a" * 64,
                        "word_count": 4,
                        "order": 1,
                    },
                    {
                        "chapter_id": "02-chapter.md",
                        "path": "content/books/distillation/02-chapter.md",
                        "title": "Second chapter",
                        "status": "current",
                        "sha256": "b" * 64,
                        "word_count": 3,
                        "order": 2,
                    },
                ],
            }
        )
        return value

    async def workspace(self, workspace_id: str):
        self.calls.append(("workspace", workspace_id))
        approval = "approval-1" if self.attachment_current else "approval-old"
        capture = "capture-1" if self.attachment_current else "capture-old"
        return {
            "id": workspace_id,
            "sources": [
                {
                    "binding_ref": "binding-1",
                    "approval_ref": approval,
                    "capture_ref": capture,
                    "status": "current",
                    "mode": "pinned",
                }
            ],
        }

    async def workflow_plan(self, workspace_id: str, chapter_path: str):
        self.calls.append(("plan", chapter_path))
        if not self.attachment_current:
            raise LivingBookError("conversation_source_not_in_workspace", 409)
        return {
            "mode": "sections",
            "workflow_version": 806,
            "workflow_definition_id": "definition-1",
            "workflow_definition_sha256": "c" * 64,
            "workflow_binding_sha256": "d" * 64,
            "model_calls": 8,
            "output_tokens": 12288,
            "wall_seconds": 900,
            "characters": 100,
            "sha256": "e" * 64,
            "sections": [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}],
            "governor": {"remaining_calls": 100, "remaining_tokens": 100000},
        }

    async def improvements(self, workspace_id: str):
        return {"improvements": [], "counts": {}, "notice": ""}

    async def experience(self, workspace_id: str, chapter_path: str, criteria: str):
        self.calls.append(("experience", chapter_path, criteria))
        return {
            "retrieval": {
                "enabled": True,
                "eligible_candidates": 0,
                "selected": [],
                "context_sha256": "f" * 64,
            },
            "items": [],
        }

    async def launch_workflow(self, workspace_id: str, body: dict):
        self.calls.append(("launch", body))
        self.launched.append(body)
        return {"id": "run-1", "status": "QUEUED", "terminal": False}

    async def workflow_run(self, workspace_id: str, run_id: str):
        return {
            "run": {
                "id": run_id,
                "status": "COMPLETED",
                "terminal": True,
                "workflow": {"name": "chapter-improvement", "version": 806},
                "budget": {"max_model_calls": 8, "max_output_tokens": 12288},
            },
            "stages": [{"stage_id": "review", "state": "COMPLETED"}],
            "usage": {"calls": 8, "tokens": 1000},
            "plan": {"version": "chapter-spans/v1"},
            "experience": {"enabled": False, "recorded": True},
            "reason": None,
        }

    async def improvement(self, workspace_id: str, run_id: str):
        decision = "accepted" if self.decided else "pending"
        return {
            "provenance": "complete",
            "chapter_path": "content/books/distillation/01-chapter.md",
            "original": {
                "path": "content/books/distillation/01-chapter.md",
                "sha256": "a" * 64,
            },
            "proposal": {
                "artifact_id": "artifact-1",
                "artifact_sha256": "b" * 64,
                "sha256": "b" * 64,
                "markdown": "# First chapter\n\nA tighter teacher signal.\n",
                "coverage": "complete",
                "limitations": "",
            },
            "change": {
                "differs": True,
                "lines_added": 1,
                "lines_removed": 1,
                "blocks": [],
                "unified": ["--- original", "+++ proposal"],
                "truncated": False,
            },
            "evaluation": {
                "status": "evaluated",
                "kind": "model_assessment",
                "verdict": "promising",
                "model": "model",
            },
            "source_version": {
                "status": "earlier_version" if self.earlier_version else "current"
            },
            "state": {"decision": decision, "decided_at": None},
            "history": [] if decision == "pending" else [{"decision": decision}],
        }

    async def decide(self, workspace_id: str, run_id: str, body: dict):
        self.decisions.append(body)
        self.decided = body["decision"] == "accepted"
        return await self.improvement(workspace_id, run_id)


def _setup(client: TestClient, tmp_path: Path, *, attachment_current: bool = True):
    root = _book_tree(tmp_path)
    _project(client, root)
    _add_evaluation(client)
    fake = ImprovementAlive(
        root / "content" / "books" / "distillation",
        attachment_current=attachment_current,
    )
    fake.registered = True
    return fake


def test_preview_builds_bounded_evidence_and_plan(
    client: TestClient, tmp_path, monkeypatch
):
    fake = _setup(client, tmp_path)
    monkeypatch.setattr(service, "_client", lambda session, settings: fake)

    response = client.get(
        "/api/living-book/projects/living-test/improvement/preview",
        params={"chapter_id": "01-chapter.md"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["eligible"] is True, body
    assert body["plan"]["workflow_version"] == 806
    assert body["plan"]["model_calls"] == 8
    assert body["evidence"]["measure_id"] == "mission.prose.manuscript-prose-v1"
    assert body["evidence"]["value"]["economy"] == 3
    assert body["intent"]["evidence"][0]["chapter_revision"] == "a" * 64
    assert len(body["brief"]) <= 600
    assert body["criteria_sha256"]
    assert body["intent_sha256"]
    assert body["source"]["workspace_attachment_current"] is True
    assert any(item["status"] == "NOT_RUN" for item in body["excluded"])


def test_preview_blocks_a_stale_workspace_attachment(
    client: TestClient, tmp_path, monkeypatch
):
    fake = _setup(client, tmp_path, attachment_current=False)
    monkeypatch.setattr(service, "_client", lambda session, settings: fake)

    response = client.get(
        "/api/living-book/projects/living-test/improvement/preview",
        params={"chapter_id": "01-chapter.md"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["eligible"] is False
    assert any(
        item["code"] == "source_attachment_stale" for item in body["blockers"]
    )
    assert not any(call[0] == "plan" for call in fake.calls)


def test_launch_requires_confirmation_and_forwards_the_exact_plan(
    client: TestClient, tmp_path, monkeypatch
):
    fake = _setup(client, tmp_path)
    monkeypatch.setattr(service, "_client", lambda session, settings: fake)
    preview = client.get(
        "/api/living-book/projects/living-test/improvement/preview",
        params={"chapter_id": "01-chapter.md"},
    ).json()

    unconfirmed = client.post(
        "/api/living-book/projects/living-test/improvement",
        json={
            "chapter_id": "01-chapter.md",
            "focus": "economy",
            "intent_sha256": preview["intent_sha256"],
            "plan_sha256": preview["plan"]["plan_sha256"],
            "criteria": preview["brief"],
            "model": "model",
            "use_experience": False,
            "confirmed": False,
            "idempotency_key": "launch-unconfirmed",
        },
    )
    assert unconfirmed.status_code == 409
    assert not fake.launched

    response = client.post(
        "/api/living-book/projects/living-test/improvement",
        json={
            "chapter_id": "01-chapter.md",
            "focus": "economy",
            "intent_sha256": preview["intent_sha256"],
            "plan_sha256": preview["plan"]["plan_sha256"],
            "criteria": preview["brief"],
            "model": "model",
            "use_experience": False,
            "confirmed": True,
            "idempotency_key": "launch-1",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_id"] == "run-1"
    assert body["status_label"] == "Proposal retained; awaiting author decision"
    assert body["applied"] is False
    assert fake.launched[0]["workflow_version"] == 806
    assert fake.launched[0]["plan_sha256"] == "e" * 64
    assert fake.launched[0]["confirmed"] is True
    assert fake.launched[0]["chapter_path"].endswith("01-chapter.md")


def test_decision_is_append_only_and_never_writes_a_file(
    client: TestClient, tmp_path, monkeypatch
):
    fake = _setup(client, tmp_path)
    monkeypatch.setattr(service, "_client", lambda session, settings: fake)
    chapter = Path(fake.root) / "01-chapter.md"
    before = chapter.read_text(encoding="utf-8")

    response = client.post(
        "/api/living-book/projects/living-test/improvement/run-1/decision",
        json={
            "decision": "accepted",
            "proposal_sha256": "b" * 64,
            "comment": "economy: keep the claim, tighten the example",
            "idempotency_key": "decision-1",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"]["decision"] == "accepted"
    assert body["applied"] is False
    assert fake.decisions[0]["decision"] == "accepted"
    assert fake.decisions[0]["acknowledge_earlier_version"] is False
    assert chapter.read_text(encoding="utf-8") == before


def test_decision_refuses_a_changed_proposal_and_earlier_version(
    client: TestClient, tmp_path, monkeypatch
):
    fake = _setup(client, tmp_path)
    monkeypatch.setattr(service, "_client", lambda session, settings: fake)

    changed = client.post(
        "/api/living-book/projects/living-test/improvement/run-1/decision",
        json={
            "decision": "accepted",
            "proposal_sha256": "c" * 64,
            "idempotency_key": "decision-changed",
        },
    )
    assert changed.status_code == 409
    assert not fake.decisions

    fake.earlier_version = True
    earlier = client.post(
        "/api/living-book/projects/living-test/improvement/run-1/decision",
        json={
            "decision": "accepted",
            "proposal_sha256": "b" * 64,
            "idempotency_key": "decision-earlier",
        },
    )
    assert earlier.status_code == 409
    assert "earlier" in earlier.json()["error"]["message"]
    assert not fake.decisions

    edits = client.post(
        "/api/living-book/projects/living-test/improvement/run-1/decision",
        json={
            "decision": "accepted_with_edits",
            "proposal_sha256": "b" * 64,
            "idempotency_key": "decision-edits",
        },
    )
    assert edits.status_code == 422
    assert not fake.decisions
