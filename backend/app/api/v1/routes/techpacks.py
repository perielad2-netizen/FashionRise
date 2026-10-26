"""Create Real Design — techpack draft + authenticated PDF + gated AI routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.techpack import (
    TechpackAiConfirmRequest,
    TechpackAiGenerateRequest,
    TechpackCreate,
    TechpackDraftRead,
    TechpackExportRead,
    TechpackListResponse,
    TechpackUpdate,
)
from app.services import techpack_ai, techpack_service

router = APIRouter()


@router.get("/ai/status")
def techpack_ai_status(user: CurrentUser) -> dict[str, Any]:
    """Public-to-auth AI capability / spend gate status. Never triggers paid work."""
    _ = user
    return techpack_ai.ai_status()


@router.get("/ai/runs/{run_id}")
def techpack_ai_run(
    run_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    return techpack_ai.get_run(db, user, run_id)


@router.post("", response_model=TechpackDraftRead, status_code=status.HTTP_201_CREATED)
def create_techpack(
    data: TechpackCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> TechpackDraftRead:
    return techpack_service.create_draft(db, user, data)


@router.get("", response_model=TechpackListResponse)
def list_techpacks(
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
    look_id: uuid.UUID | None = Query(None),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TechpackListResponse:
    return techpack_service.list_drafts(db, user, look_id=look_id, limit=limit, offset=offset)


@router.get("/exports/{export_id}/pdf")
def download_techpack_pdf(
    export_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> FileResponse:
    """Serve private tech-pack PDF bytes to the owning authenticated user only."""
    path, row = techpack_service.resolve_export_pdf_path(db, user, export_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=row.filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{draft_id}", response_model=TechpackDraftRead)
def get_techpack(
    draft_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> TechpackDraftRead:
    return techpack_service.get_draft(db, user, draft_id)


@router.patch("/{draft_id}", response_model=TechpackDraftRead)
def update_techpack(
    draft_id: uuid.UUID,
    data: TechpackUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> TechpackDraftRead:
    return techpack_service.update_draft(db, user, draft_id, data)


@router.post("/{draft_id}/export", response_model=TechpackExportRead, status_code=status.HTTP_201_CREATED)
def export_techpack_pdf(
    draft_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> TechpackExportRead:
    return techpack_service.export_pdf(db, user, draft_id)


@router.get("/{draft_id}/exports", response_model=list[TechpackExportRead])
def list_techpack_exports(
    draft_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> list[TechpackExportRead]:
    return techpack_service.list_exports(db, user, draft_id)


@router.post("/{draft_id}/ai/confirm")
def techpack_ai_confirm(
    draft_id: uuid.UUID,
    data: TechpackAiConfirmRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    """Issue a one-time confirm token. Does not call paid providers."""
    return techpack_ai.create_confirm_challenge(db, user, draft_id, stage=data.stage)


@router.post("/{draft_id}/ai/generate")
def techpack_ai_generate(
    draft_id: uuid.UUID,
    data: TechpackAiGenerateRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    """Heuristic ($0) or paid AI generation after explicit confirm_token."""
    return techpack_ai.run_generate(
        db,
        user,
        draft_id,
        confirm_token=data.confirm_token,
        idempotency_key=data.idempotency_key,
        mode=data.mode,
        sections=data.sections,
    )


@router.post("/{draft_id}/ai-draft", status_code=status.HTTP_403_FORBIDDEN)
def ai_draft_assist(
    draft_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),  # noqa: B008
) -> None:
    """Legacy V1 path — remains disabled. Use /ai/confirm + /ai/generate."""
    _ = (draft_id, user, db)
    techpack_service.ai_draft_assist_disabled()
