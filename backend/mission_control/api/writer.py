"""Writer Editing workspace API.

Read routes consume Writer's adapter resources. The audit action is launched
through Mission Control's durable integration-execution lifecycle; the browser
never supplies an executable or command.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request

from mission_control.adapters.service import AdapterService
from mission_control.schemas import (
    IntegrationExecutionRead,
    RawModel,
    WriterAuditRequest,
    WriterWorkspaceRead,
)
from mission_control.writer.service import WriterService

from pydantic import Field

router = APIRouter(prefix="/api/writer", tags=["writer"])


@router.get("/books", response_model=WriterWorkspaceRead)
def list_writer_books(request: Request) -> WriterWorkspaceRead:
    return WriterWorkspaceRead(
        **WriterService(
            request.app.state.database, request.app.state.settings
        ).workspace()
    )


@router.get("/self-repair")
def read_writer_self_repair(request: Request) -> dict[str, Any]:
    """Read-only self-repair process summary. No scores, no writes."""
    from mission_control.writer.self_repair import summarize_self_repair

    return summarize_self_repair(request.app.state.settings.book_root)


@router.get("/improvement")
def read_writer_improvement(request: Request) -> dict[str, Any]:
    """Read-only chapter-improvement process summary. No scores, no writes."""
    from mission_control.writer.improvement_summary import summarize_improvement

    return summarize_improvement(request.app.state.settings.book_root)


@router.get("/campaigns")
def read_writer_campaigns(request: Request) -> dict[str, Any]:
    """Read-only book-campaign summary. No scores, no writes."""
    from mission_control.writer.campaign_summary import summarize_campaigns

    return summarize_campaigns(request.app.state.settings.book_root)


@router.get("/campaigns/runs/{run_id}")
def read_writer_campaign_run(run_id: str, request: Request) -> dict[str, Any]:
    """Read one durable campaign run record by id (searches all known book roots)."""
    from mission_control.writer.campaign_summary import summarize_campaigns

    summary = summarize_campaigns(request.app.state.settings.book_root)
    for book in summary.get("books", []):
        for chapter in book.get("chapters", []):
            for key in ("run_id", "report_id", "latest_report"):
                if chapter.get(key) == run_id:
                    return {"ok": True, "run_id": run_id, "chapter": chapter,
                            "book_id": book["book_id"]}
    return {"ok": False, "error": f"campaign run not found: {run_id}"}


@router.get("/intel")
def read_writer_intel(request: Request) -> dict[str, Any]:
    """Read-only improvement-intelligence summary. No scores of manuscripts, no writes."""
    from mission_control.writer.intel_summary import summarize_intel

    return summarize_intel(request.app.state.settings.book_root)


@router.get("/evolution")
def read_strategy_evolution(request: Request) -> dict[str, Any]:
    """Read-only strategy-evolution summary. No scores, no writes."""
    from mission_control.writer.evolution_summary import summarize_strategy_evolution

    return summarize_strategy_evolution(request.app.state.settings.book_root)


class WriterCampaignCreateRequest(RawModel):
    book_root: str = Field(min_length=1)
    book_id: str = ""
    mode: str = "PLAN"
    chapters: list[str] = Field(default_factory=list)


class WriterCampaignActionRequest(RawModel):
    campaign_id: str | None = None
    run_id: str | None = None
    book_root: str = Field(min_length=1)
    max_wall_seconds: int = 240
    selective: str = "all"


@router.post("/campaigns", response_model=IntegrationExecutionRead)
async def create_writer_campaign(
    payload: WriterCampaignCreateRequest, request: Request
) -> IntegrationExecutionRead:
    return await request.app.state.integration_service.start_action(
        "writer",
        "book_campaign_create",
        {"book_root": payload.book_root, "book_id": payload.book_id,
         "mode": payload.mode, "chapters": payload.chapters},
        confirm=True,
    )


@router.post("/campaigns/{campaign_id}/manifest", response_model=IntegrationExecutionRead)
async def manifest_writer_campaign(
    campaign_id: str, payload: WriterCampaignActionRequest, request: Request
) -> IntegrationExecutionRead:
    return await request.app.state.integration_service.start_action(
        "writer", "book_campaign_manifest",
        {"campaign_id": campaign_id, "book_root": payload.book_root}, confirm=True)


@router.post("/campaigns/{campaign_id}/plan", response_model=IntegrationExecutionRead)
async def plan_writer_campaign(
    campaign_id: str, payload: WriterCampaignActionRequest, request: Request
) -> IntegrationExecutionRead:
    return await request.app.state.integration_service.start_action(
        "writer", "book_campaign_plan",
        {"campaign_id": campaign_id, "book_root": payload.book_root,
         "selective": payload.selective}, confirm=True)


@router.post("/campaigns/runs/chunk", response_model=IntegrationExecutionRead)
async def run_writer_campaign_chunk(
    payload: WriterCampaignActionRequest, request: Request
) -> IntegrationExecutionRead:
    if not payload.run_id:
        raise ValueError("run_id is required")
    return await request.app.state.integration_service.start_action(
        "writer", "book_campaign_run_chunk",
        {"run_id": payload.run_id, "book_root": payload.book_root,
         "max_wall_seconds": payload.max_wall_seconds}, confirm=True)


@router.post("/campaigns/runs/{run_id}/pause", response_model=IntegrationExecutionRead)
async def pause_writer_campaign(
    run_id: str, payload: WriterCampaignActionRequest, request: Request
) -> IntegrationExecutionRead:
    return await request.app.state.integration_service.start_action(
        "writer", "book_campaign_pause",
        {"run_id": run_id, "book_root": payload.book_root}, confirm=True)


class StrategyExperimentRunRequest(RawModel):
    experiment_id: str = Field(min_length=1)
    arm: Literal["baseline", "candidate"] = "baseline"
    book_root: str = Field(min_length=1)


@router.post("/evolution/experiments/run", response_model=IntegrationExecutionRead)
async def run_strategy_experiment_arm(
    payload: StrategyExperimentRunRequest, request: Request
) -> IntegrationExecutionRead:
    if payload.arm not in ("baseline", "candidate"):
        raise ValueError("arm must be baseline|candidate")
    return await request.app.state.integration_service.start_action(
        "writer", "book_strategy_experiment_run",
        {"experiment_id": payload.experiment_id, "arm": payload.arm,
         "book_root": payload.book_root}, confirm=True)


@router.post("/campaigns/runs/{run_id}/resume", response_model=IntegrationExecutionRead)
async def resume_writer_campaign(
    run_id: str, payload: WriterCampaignActionRequest, request: Request
) -> IntegrationExecutionRead:
    return await request.app.state.integration_service.start_action(
        "writer", "book_campaign_resume",
        {"run_id": run_id, "book_root": payload.book_root}, confirm=True)


@router.post("/campaigns/runs/{run_id}/cancel", response_model=IntegrationExecutionRead)
async def cancel_writer_campaign(
    run_id: str, payload: WriterCampaignActionRequest, request: Request
) -> IntegrationExecutionRead:
    return await request.app.state.integration_service.start_action(
        "writer", "book_campaign_cancel",
        {"run_id": run_id, "book_root": payload.book_root}, confirm=True)


@router.post("/refresh", response_model=WriterWorkspaceRead)
async def refresh_writer(request: Request) -> WriterWorkspaceRead:
    await AdapterService(
        request.app.state.database, request.app.state.settings
    ).refresh_application("writer")
    return WriterWorkspaceRead(
        **WriterService(
            request.app.state.database, request.app.state.settings
        ).workspace()
    )


@router.post("/audit", response_model=IntegrationExecutionRead)
async def audit_writer(
    payload: WriterAuditRequest, request: Request
) -> IntegrationExecutionRead:
    return await request.app.state.integration_service.start_action(
        "writer",
        "audit_registered_books",
        {"profile": payload.profile},
        confirm=True,
    )
