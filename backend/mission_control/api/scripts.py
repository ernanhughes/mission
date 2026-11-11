"""Script registry API (MC-SCRIPTS-02 Phase B, MC-SCRIPTS-05 Phase E2).

Read-only toward the source tree. The sync endpoint reconciles the
configured root only; it never accepts an arbitrary path from the browser.
Content reads are confined to the owning library root with traversal and
symlink protection. Batch reviews run bounded sequential steps; synthesis
reads review evidence and bounded excerpts.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from mission_control.api.deps import get_session
from mission_control.core.errors import InferenceProblem, ValidationProblem
from mission_control.persistence.db import now_iso
from mission_control.schemas import (
    OkResponse,
    ScriptArchiveUpdate,
    ScriptBatchCreate,
    ScriptBatchStep,
    ScriptBulkUpdate,
    ScriptCandidateCreate,
    ScriptCandidateRead,
    ScriptCandidateRevise,
    ScriptCandidateStatus,
    ScriptContentRead,
    ScriptEffectivenessUpdate,
    ScriptLibraryMigrate,
    ScriptMigrationApply,
    ScriptMigrationApprove,
    ScriptRead,
    ScriptRelationshipConfirm,
    ScriptReviewCreate,
    ScriptReviewRead,
    ScriptStatusRead,
    ScriptStatusUpdate,
    ScriptSynthesisCreate,
    ScriptTagSet,
)
from mission_control.scripts import batches as batch_ops
from mission_control.scripts import candidates as cand_ops
from mission_control.scripts import intelligence as intellect
from mission_control.scripts import organise as organise
from mission_control.scripts import service as scripts
from mission_control.scripts import synthesis as synth

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


@router.get("/status", response_model=ScriptStatusRead)
def get_status(session: Session = Depends(get_session)) -> ScriptStatusRead:
    return ScriptStatusRead(**scripts.status_read(session))


@router.post("/sync")
def sync(session: Session = Depends(get_session)) -> dict:
    return scripts.sync_scripts(session)


@router.post("/migrate-legacy")
def migrate_legacy(session: Session = Depends(get_session)) -> dict:
    result = scripts.migrate_legacy_items(session)
    session.flush()
    return result


@router.post("/bulk/status")
def bulk_status(payload: ScriptBulkUpdate, session: Session = Depends(get_session)) -> dict:
    result = scripts.bulk_set_status(
        session, payload.script_ids, payload.status, note=payload.note,
        completed_at=payload.completed_at, as_historical=payload.as_historical)
    session.flush()
    return result


@router.post("/libraries/migrate")
def migrate_library(payload: ScriptLibraryMigrate,
                    session: Session = Depends(get_session)) -> dict:
    result = scripts.migrate_library(
        session, source_key=payload.source_key, dest_key=payload.dest_key,
        dry_run=payload.dry_run)
    session.flush()
    return result


@router.post("/relationships/discover")
def discover_relationships(session: Session = Depends(get_session)) -> dict:
    result = organise.discover_relationships(session)
    session.flush()
    return result


@router.get("/relationships")
def list_relationships(session: Session = Depends(get_session)) -> dict:
    return {"relationships": organise.list_relationships(session)}


@router.post("/relationships/confirm")
def confirm_relationship(payload: ScriptRelationshipConfirm,
                         session: Session = Depends(get_session)) -> dict:
    result = organise.confirm_relationship(
        session, payload.source_id, payload.target_id, payload.kind,
        confirmed=payload.confirmed, note=payload.note)
    session.flush()
    return result


@router.get("/works")
def get_works(session: Session = Depends(get_session)) -> dict:
    return organise.work_groups(session)


@router.post("/migrations/preview")
def preview_migration(session: Session = Depends(get_session)) -> dict:
    result = organise.plan_migration(session)
    session.flush()
    return result


@router.get("/migrations")
def list_migrations(session: Session = Depends(get_session)) -> dict:
    return {"migrations": organise.list_migrations(session)}


@router.get("/migrations/{migration_id}")
def get_migration(migration_id: str, session: Session = Depends(get_session)) -> dict:
    return organise.migration_read(organise.get_migration(session, migration_id))


@router.post("/migrations/{migration_id}/approve")
def approve_migration(migration_id: str, payload: ScriptMigrationApprove,
                      session: Session = Depends(get_session)) -> dict:
    result = organise.approve_migration(session, migration_id, expected_hash=payload.expected_hash)
    session.flush()
    return result


@router.post("/migrations/{migration_id}/apply")
def apply_migration(migration_id: str, payload: ScriptMigrationApply,
                    session: Session = Depends(get_session)) -> dict:
    result = organise.apply_migration(session, migration_id, expected_hash=payload.expected_hash)
    session.flush()
    return result


@router.post("/migrations/{migration_id}/rollback")
def rollback_migration(migration_id: str, session: Session = Depends(get_session)) -> dict:
    result = organise.rollback_migration(session, migration_id)
    session.flush()
    return result


@router.post("/batches", status_code=201)
def create_batch(payload: ScriptBatchCreate, session: Session = Depends(get_session)) -> dict:
    batch = batch_ops.create_batch(
        session, scope=payload.scope, script_ids=list(payload.script_ids or []),
        status_filter=payload.status, model=payload.model, force=payload.force)
    session.flush()
    return batch_ops.batch_read(session, batch)


@router.get("/batches")
def list_batches(session: Session = Depends(get_session)) -> dict:
    return {"batches": batch_ops.list_batches(session)}


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, session: Session = Depends(get_session)) -> dict:
    return batch_ops.batch_read(session, batch_ops.get_batch(session, batch_id))


@router.post("/batches/{batch_id}/step")
async def step_batch(batch_id: str, payload: ScriptBatchStep,
                     session: Session = Depends(get_session)) -> dict:
    result = await batch_ops.step_batch(session, batch_id, limit=payload.limit)
    session.flush()
    return result


@router.post("/batches/{batch_id}/pause")
def pause_batch(batch_id: str, session: Session = Depends(get_session)) -> dict:
    result = batch_ops.pause_batch(session, batch_id)
    session.flush()
    return result


@router.post("/batches/{batch_id}/cancel")
def cancel_batch(batch_id: str, session: Session = Depends(get_session)) -> dict:
    result = batch_ops.cancel_batch(session, batch_id)
    session.flush()
    return result


@router.post("/batches/{batch_id}/retry")
def retry_batch(batch_id: str, session: Session = Depends(get_session)) -> dict:
    result = batch_ops.retry_batch(session, batch_id)
    session.flush()
    return result


@router.get("/intelligence/coverage")
def intelligence_coverage(session: Session = Depends(get_session)) -> dict:
    return {"coverage": synth.coverage(session),
            "purposes": synth.purpose_distribution(session)}


@router.get("/syntheses")
def list_syntheses(kind: str | None = None,
                   session: Session = Depends(get_session)) -> dict:
    return {"syntheses": synth.list_syntheses(session, kind=kind)}


@router.post("/syntheses", status_code=201)
async def create_synthesis(payload: ScriptSynthesisCreate,
                           session: Session = Depends(get_session)) -> dict:
    result = await synth.generate_synthesis(session, kind=payload.kind or "full",
                                            model=payload.model or "")
    session.flush()
    return result


@router.get("/syntheses/{synthesis_id}")
def get_synthesis(synthesis_id: str, session: Session = Depends(get_session)) -> dict:
    return synth.synthesis_read(session, synth.get_synthesis(session, synthesis_id))


@router.get("", response_model=list[ScriptRead])
def list_scripts(session: Session = Depends(get_session),
                 status: str | None = None,
                 search: str | None = None,
                 include_archived: bool = True,
                 include_missing: bool = True,
                 completed: bool | None = None,
                 duplicate: bool | None = None,
                 limit: int = Query(default=200, ge=1, le=500),
                 offset: int = Query(default=0, ge=0)) -> list[ScriptRead]:
    rows, _ = scripts.list_records(
        session, status=status or None, search=search or None,
        include_archived=include_archived, include_missing=include_missing,
        completed=completed, duplicate=duplicate,
        limit=limit, offset=offset)
    return [ScriptRead(**scripts.record_read(session, row)) for row in rows]


@router.get("/{script_id}", response_model=ScriptRead)
def get_script(script_id: str, session: Session = Depends(get_session)) -> ScriptRead:
    return ScriptRead(**scripts.record_read(session, scripts.get_record(session, script_id)))


@router.get("/{script_id}/content", response_model=ScriptContentRead)
def get_content(script_id: str, session: Session = Depends(get_session)) -> ScriptContentRead:
    return ScriptContentRead(**scripts.read_content(session, script_id))


@router.patch("/{script_id}/status", response_model=ScriptRead)
def patch_status(script_id: str, payload: ScriptStatusUpdate,
                 session: Session = Depends(get_session)) -> ScriptRead:
    row = scripts.set_status(session, script_id, payload.status,
                             note=payload.note, completed_at=payload.completed_at)
    session.flush()
    return ScriptRead(**scripts.record_read(session, row))


@router.patch("/{script_id}/archive", response_model=ScriptRead)
def patch_archive(script_id: str, payload: ScriptArchiveUpdate,
                  session: Session = Depends(get_session)) -> ScriptRead:
    row = scripts.set_archived(session, script_id, archived=payload.archived, note=payload.note)
    session.flush()
    return ScriptRead(**scripts.record_read(session, row))


@router.post("/{script_id}/reviews", response_model=ScriptReviewRead, status_code=201)
async def request_review(script_id: str, payload: ScriptReviewCreate,
                         session: Session = Depends(get_session)) -> ScriptReviewRead:
    row = await intellect.run_review(session, script_id, model=payload.model or "")
    session.flush()
    return ScriptReviewRead(**row)


@router.get("/{script_id}/reviews")
def list_reviews(script_id: str, session: Session = Depends(get_session)) -> dict:
    return {"reviews": intellect.list_reviews(session, script_id)}


@router.post("/{script_id}/tags")
def set_tags(script_id: str, payload: ScriptTagSet,
             session: Session = Depends(get_session)) -> dict:
    tags = synth.set_tags(session, script_id, list(payload.tags or []),
                          origin=payload.origin or "user")
    session.flush()
    return {"script_id": script_id, "tags": tags}


@router.patch("/{script_id}/effectiveness", response_model=ScriptRead)
def patch_effectiveness(script_id: str, payload: ScriptEffectivenessUpdate,
                        session: Session = Depends(get_session)) -> ScriptRead:
    row = intellect.set_effectiveness(
        session, script_id, usage_count=payload.usage_count,
        personal_rating=payload.personal_rating,
        personal_target=payload.personal_target,
        personal_effect=payload.personal_effect,
        last_used_at=payload.last_used_at)
    session.flush()
    return ScriptRead(**scripts.record_read(session, row))


@router.delete("/{script_id}/effectiveness", response_model=ScriptRead)
def clear_effectiveness(script_id: str, session: Session = Depends(get_session)) -> ScriptRead:
    row = intellect.clear_effectiveness(session, script_id)
    session.flush()
    return ScriptRead(**scripts.record_read(session, row))


@router.post("/candidates", response_model=ScriptCandidateRead, status_code=201)
def create_candidate(payload: ScriptCandidateCreate,
                     session: Session = Depends(get_session)) -> ScriptCandidateRead:
    row = cand_ops.create_candidate(
        session, title=payload.title, content=payload.content, kind=payload.kind,
        version=payload.version, source_manifest=dict(payload.source_manifest or {}),
        provenance=dict(payload.provenance or {}))
    session.flush()
    return ScriptCandidateRead(**cand_ops.candidate_read(row))


@router.get("/candidates")
def list_candidates(session: Session = Depends(get_session)) -> dict:
    return {"candidates": [cand_ops.candidate_read(row) for row in cand_ops.list_candidates(session)]}


@router.get("/candidates/{candidate_id}", response_model=ScriptCandidateRead)
def get_candidate(candidate_id: str, session: Session = Depends(get_session)) -> ScriptCandidateRead:
    return ScriptCandidateRead(**cand_ops.candidate_read(cand_ops.get_candidate(session, candidate_id)))


@router.get("/candidates/{candidate_id}/diff")
def candidate_diff(candidate_id: str, session: Session = Depends(get_session)) -> dict:
    row = cand_ops.get_candidate(session, candidate_id)
    if not row.parent_candidate_id:
        return {"diff": "", "parent": None}
    parent = cand_ops.get_candidate(session, row.parent_candidate_id)
    return {"diff": cand_ops.candidate_diff(parent.content or "", row.content or ""),
            "parent": parent.id}


@router.post("/candidates/{candidate_id}/revise", response_model=ScriptCandidateRead, status_code=201)
def revise_candidate(candidate_id: str, payload: ScriptCandidateRevise,
                     session: Session = Depends(get_session)) -> ScriptCandidateRead:
    row = cand_ops.revise_candidate(session, candidate_id, content=payload.content,
                                    note=payload.note, version=payload.version)
    session.flush()
    return ScriptCandidateRead(**cand_ops.candidate_read(row))


@router.post("/candidates/{candidate_id}/critique")
async def critique_candidate(candidate_id: str, model: str = "",
                             session: Session = Depends(get_session)) -> dict:
    row = cand_ops.get_candidate(session, candidate_id)
    deterministic = cand_ops.deterministic_critique(
        row.content or "", dict(row.validation or cand_ops.validate_candidate(row.content or "")))
    result: dict[str, Any] = {"deterministic": deterministic, "pi": None}
    try:
        result["pi"] = await cand_ops.pi_critique(session, row.content or "", model=model or "")
    except (ValidationProblem, InferenceProblem) as exc:
        result["pi"] = {"origin": "pi", "error": str(exc)[:500], "skipped": True}
    except (ValidationProblem, InferenceProblem) as exc:
        result["pi"] = {"origin": "pi", "error": str(exc)[:500], "skipped": True}
    row.critique = result
    if row.status == "draft":
        row.status = "critiqued"
    row.updated_at = now_iso()
    session.flush()
    return result


@router.patch("/candidates/{candidate_id}/status", response_model=ScriptCandidateRead)
def patch_candidate(candidate_id: str, payload: ScriptCandidateStatus,
                    session: Session = Depends(get_session)) -> ScriptCandidateRead:
    row = cand_ops.set_candidate_status(session, candidate_id, payload.status, note=payload.note)
    session.flush()
    return ScriptCandidateRead(**cand_ops.candidate_read(row))


@router.post("/candidates/{candidate_id}/promote", response_model=ScriptCandidateRead)
def promote_candidate(candidate_id: str, session: Session = Depends(get_session)) -> ScriptCandidateRead:
    row = cand_ops.promote_candidate(session, candidate_id)
    session.flush()
    return ScriptCandidateRead(**cand_ops.candidate_read(row))


@router.get("/health/ping", response_model=OkResponse)
def ping() -> OkResponse:
    return OkResponse()
