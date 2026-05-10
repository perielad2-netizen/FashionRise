import uuid

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
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
    return AIJobRead.model_validate(job)


@router.post("/sketch/clean", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
def sketch_clean(
    user: CurrentUser,
    db: Session = Depends(get_db),
    body: SketchPipelineBody | None = Body(None),
) -> AIJobRead:
    return _sketch_enqueue(db, user, "sketch_clean", body)


@router.post("/sketch/polish", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
def sketch_polish(
    user: CurrentUser,
    db: Session = Depends(get_db),
    body: SketchPipelineBody | None = Body(None),
) -> AIJobRead:
    return _sketch_enqueue(db, user, "sketch_polish", body)


@router.post("/style/suggest", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
def style_suggest(
    user: CurrentUser,
    db: Session = Depends(get_db),
    body: SketchPipelineBody | None = Body(None),
) -> AIJobRead:
    return _sketch_enqueue(db, user, "style_suggest", body)


@router.post("/jobs", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    data: AIJobCreate, user: CurrentUser, db: Session = Depends(get_db)
) -> AIJobRead:
    job = ai_service.enqueue_job(db, user, data)
    return AIJobRead.model_validate(job)


@router.get("/jobs/{job_id}", response_model=AIJobRead)
def get_job(job_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> AIJobRead:
    job = ai_service.get_job(db, user, job_id)
    return AIJobRead.model_validate(job)
