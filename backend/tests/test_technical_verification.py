"""MC-PRAXIS-15 tests: bounded arithmetic verification and governance."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from fastapi.testclient import TestClient


def _revision(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _await(client: TestClient, execution: dict) -> dict:
    for _ in range(100):
        row = client.get(
            f"/api/integrations/executions/{execution['id']}").json()
        if row["status"] not in ("queued", "running"):
            return row
        time.sleep(0.05)
    raise AssertionError("execution did not finish")


def _claim(client: TestClient, tmp_path: Path, text: str = "The total is 90.") -> dict:
    source = tmp_path / "chapter.md"
    source.write_text(f"# Numbers\n\n{text}\n", encoding="utf-8")
    revision = _revision(source)
    response = client.post("/api/technical/claims", json={
        "project_id": None,
        "book_id": "book-test",
        "chapter_id": "01-chapter.md",
        "source_path": str(source),
        "source_revision": revision,
        "source_excerpt": text,
        "claim_text": "Three workloads, five trials and six configurations total 90 runs.",
        "claim_type": "MATHEMATICAL",
        "epistemic_role": "DERIVED",
        "quote_validated": True,
    })
    assert response.status_code == 201, response.text
    claim = response.json()
    claim["_source"] = str(source)
    claim["_revision"] = revision
    return claim


def _proposition(claim: dict, **overrides) -> dict:
    proposition = {
        "claim_id": claim["id"],
        "source_revision": claim["_revision"],
        "source_span": "line 3",
        "kind": "product",
        "factors": ["3", "5", "6"],
        "expected": "90",
        "tolerance": "0",
        "units": "runs",
        "fidelity": "candidate",
        "evidence_refs": ["chapter.md:3"],
    }
    proposition.update(overrides)
    return proposition


def _execute(client: TestClient, claim: dict, **overrides) -> dict:
    parameters = {
        "claim_id": claim["id"],
        "source_revision": claim["_revision"],
        "method": "deterministic",
        "proposition": _proposition(claim, **overrides),
        "max_seconds": 10,
    }
    return client.post(
        "/api/integrations/technical/actions/verify_claim/execute",
        json={"parameters": parameters, "confirm": True})


def test_technical_action_is_exposed(client: TestClient) -> None:
    response = client.get("/api/integrations/technical")
    assert response.status_code == 200, response.text
    actions = {action["id"]: action for action in response.json()["actions"]}
    assert "verify_claim" in actions
    spec = actions["verify_claim"]
    assert spec["approval_required"] is True
    assert spec["side_effect"] == "local_generated_artifacts"
    assert spec["parameters_schema"]["required"] == [
        "claim_id", "source_revision", "method", "proposition"]


def test_bounded_verification_executes_without_changing_claim(
        client: TestClient, tmp_path: Path) -> None:
    claim = _claim(client, tmp_path)
    response = _execute(client, claim)
    assert response.status_code == 200, response.text
    row = _await(client, response.json())
    assert row["status"] == "succeeded"
    assert row["result"]["proposition_holds"] is True
    assert row["result"]["claim_level_truth"] is None
    assert row["result"]["claim_status_changed"] is False
    assert row["artifact_ref"]
    verifications = client.get(
        f"/api/technical/claims/{claim['id']}/verifications")
    assert verifications.status_code == 200
    assert verifications.json() == []


def test_unsupported_proposition_is_typed_failure(
        client: TestClient, tmp_path: Path) -> None:
    claim = _claim(client, tmp_path)
    response = _execute(client, claim, kind="equality",
                        left={"op": "eval", "args": []},
                        right={"const": "1"})
    assert response.status_code == 422
    assert "unsupported operator" in response.text


def test_division_by_zero_is_rejected(client: TestClient, tmp_path: Path) -> None:
    claim = _claim(client, tmp_path)
    response = _execute(client, claim, kind="ratio", numerator="1",
                        denominator="0", expected="1", tolerance="0")
    assert response.status_code == 422
    assert "denominator is zero" in response.text


def test_stale_source_is_rejected(client: TestClient, tmp_path: Path) -> None:
    claim = _claim(client, tmp_path)
    source = Path(claim["_source"])
    source.write_text("# Numbers\n\nThe total is 91.\n", encoding="utf-8")
    response = _execute(client, claim)
    assert response.status_code == 422
    assert "stale source revision" in response.text


def test_client_verdict_or_unknown_claim_is_rejected(
        client: TestClient, tmp_path: Path) -> None:
    claim = _claim(client, tmp_path)
    parameters = {
        "claim_id": claim["id"],
        "source_revision": claim["_revision"],
        "method": "deterministic",
        "proposition": _proposition(claim),
        "verdict": "SUPPORTED",
    }
    response = client.post(
        "/api/integrations/technical/actions/verify_claim/execute",
        json={"parameters": parameters, "confirm": True})
    assert response.status_code == 422

    response = client.post(
        "/api/integrations/technical/actions/verify_claim/execute",
        json={"parameters": {
            "claim_id": "tclaim:0000000000000000",
            "source_revision": claim["_revision"],
            "method": "deterministic",
            "proposition": _proposition(claim,
                                        claim_id="tclaim:0000000000000000"),
        }, "confirm": True})
    assert response.status_code == 422
    assert "unknown technical claim" in response.text


def test_confirmation_is_required(client: TestClient, tmp_path: Path) -> None:
    claim = _claim(client, tmp_path)
    response = client.post(
        "/api/integrations/technical/actions/verify_claim/execute",
        json={"parameters": {
            "claim_id": claim["id"],
            "source_revision": claim["_revision"],
            "method": "deterministic",
            "proposition": _proposition(claim),
        }, "confirm": False})
    assert response.status_code == 409
