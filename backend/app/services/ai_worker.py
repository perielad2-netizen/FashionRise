"""In-process consumer for queued AI jobs (OpenAI vision for sketch pipeline when configured; otherwise stub)."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_job import AIJob
from app.services import sketch_openai

logger = logging.getLogger(__name__)


def _stub_result(job: AIJob) -> dict[str, Any]:
    return {
        "message": f"stub worker completed ({job.job_type})",
        "pipeline": job.job_type,
        "input_echo": job.input_data,
    }


def run_worker_tick(db: Session, *, limit: int = 12) -> int:
    """Claim up to *limit* queued jobs (SKIP LOCKED), complete with stub *result_data* or mark failed."""
    processed = 0
    for _ in range(limit):
        job = db.scalar(
            select(AIJob)
            .where(AIJob.status == "queued")
            .order_by(AIJob.created_at.asc())
            .limit(1)
            .with_for_update(of=AIJob, skip_locked=True)
        )
        if job is None:
            break
        try:
            if job.job_type in sketch_openai.SKETCH_JOB_TYPES and sketch_openai.is_configured():
                job.result_data = sketch_openai.complete_sketch_job(job)
            else:
                job.result_data = _stub_result(job)
            job.error_message = None
            job.status = "completed"
        except Exception as e:  # pragma: no cover — defensive
            logger.exception("AI job %s failed in worker", job.id)
            job.status = "failed"
            job.error_message = (str(e) or "worker error")[:2000]
            job.result_data = None
        db.commit()
        processed += 1
    return processed
