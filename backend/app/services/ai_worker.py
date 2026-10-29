"""In-process consumer for queued AI jobs + Techpack Professional runs."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_job import AIJob
from app.services import sketch_openai
from app.services.techpack_ai_worker import run_techpack_worker_tick

logger = logging.getLogger(__name__)


def _stub_result(job: AIJob) -> dict[str, Any]:
    return {
        "message": f"stub worker completed ({job.job_type})",
        "pipeline": job.job_type,
        "input_echo": job.input_data,
    }


def _safe_failure_result(meta: Any) -> dict[str, Any] | None:
    """Persist allowlisted failure diagnostics only. Never prompts, images, or raw bodies."""
    return sketch_openai.failure_result_for_storage(meta)


def run_magic_worker_tick(db: Session, *, limit: int = 12) -> int:
    """Claim up to *limit* queued Magic AIJob rows (SKIP LOCKED)."""
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
            # Bound user-visible error text; never echo raw provider bodies.
            raw_msg = str(e) or "worker error"
            if len(raw_msg) > 240 or any(
                token in raw_msg.lower()
                for token in ("traceback", "sk-", "bearer ", "data:image", "base64")
            ):
                job.error_message = "Magic could not finish this look."
            else:
                job.error_message = raw_msg[:240]
            job.result_data = _safe_failure_result(getattr(e, "safe_meta", None))
        db.commit()
        processed += 1
    return processed


def run_worker_tick(db: Session, *, limit: int = 12) -> int:
    """Process Magic AIJobs then up to 2 Techpack Professional runs per tick."""
    magic_n = run_magic_worker_tick(db, limit=limit)
    tech_n = run_techpack_worker_tick(db, limit=2)
    return magic_n + tech_n
