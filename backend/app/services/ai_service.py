import uuid

from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.models.ai_job import AIJob
from app.models.garment_design import GarmentDesign
from app.models.user import User
from app.schemas.ai import AIJobCreate


def enqueue_job(db: Session, user: User, data: AIJobCreate) -> AIJob:
    if data.design_id:
        design = db.get(GarmentDesign, data.design_id)
        if not design:
            raise NotFoundError("Design not found")
        if design.user_id != user.id:
            raise ForbiddenError("Not allowed for this design")
    job = AIJob(
        user_id=user.id,
        design_id=data.design_id,
        job_type=data.job_type,
        status="queued",
        input_data=data.input_data,
        result_data=None,
        error_message=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, user: User, job_id: uuid.UUID) -> AIJob:
    job = db.get(AIJob, job_id)
    if not job or job.user_id != user.id:
        raise NotFoundError("Job not found")
    return job
