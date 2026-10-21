import uuid

from fastapi import APIRouter, Body, Depends, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.ai import AIJobCreate, AIJobRead, SketchPipelineBody
from app.services import ai_service

router = APIRouter()


def _sketch_enqueue(
    db: Session, user, job_type: str, body: SketchPipelineBody | None
) -> AIJobRead:
    b = body if body is not None else SketchPipelineBody()
    job = ai_service.enqueue_job(
        db,
        user,
        AIJobCreate(design_id=b.design_id, job_type=job_type, input_data=b.input_data),
    )
    return AIJobRead.from_job(job)


@router.post("/sketch/clean", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("40/minute")
def sketch_clean(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    body: SketchPipelineBody | None = Body(None),
) -> AIJobRead:
    _ = request.url
    return _sketch_enqueue(db, user, "sketch_clean", body)


@router.post("/sketch/polish", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("40/minute")
def sketch_polish(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    body: SketchPipelineBody | None = Body(None),
) -> AIJobRead:
    _ = request.url
    return _sketch_enqueue(db, user, "sketch_polish", body)


@router.post("/style/suggest", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("40/minute")
def style_suggest(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    body: SketchPipelineBody | None = Body(None),
) -> AIJobRead:
    _ = request.url
    return _sketch_enqueue(db, user, "style_suggest", body)


@router.post("/jobs", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("40/minute")
def create_job(
    request: Request, data: AIJobCreate, user: CurrentUser, db: Session = Depends(get_db)
) -> AIJobRead:
    _ = request.url
    job = ai_service.enqueue_job(db, user, data)
    return AIJobRead.from_job(job)


@router.get("/jobs/{job_id}", response_model=AIJobRead)
@limiter.limit("400/minute")
def get_job(
    request: Request, job_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)
) -> AIJobRead:
    _ = request.url
    job = ai_service.get_job(db, user, job_id)
    return AIJobRead.from_job(job)


@router.get("/jobs/{job_id}/image")
@limiter.limit("120/minute")
def get_job_image(
    request: Request, job_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)
) -> FileResponse:
    """Serve a completed look image only to the owning authenticated user.

    Prefer this over public `/static/uploads` so production Nginx can keep
    static uploads denied while Magic still retrieves private results.
    """
    _ = request.url
    path = ai_service.resolve_job_image_file(db, user, job_id)
    suffix = path.suffix.lower()
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    return FileResponse(
        path,
        media_type=media,
        filename=f"fashionrise-look-{job_id.hex[:12]}{suffix or '.png'}",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )
