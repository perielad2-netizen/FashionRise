"""In-process consumer for queued AI jobs + Techpack Professional runs."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_job import AIJob
from app.models.personal_croquis import CROQUIS_GENERATE_JOB_TYPE
from app.services import sketch_openai
from app.services.personal_croquis_worker import run_croquis_worker_tick
from app.services.fashn_garment_realism import GARMENT_REALISM_JOB_TYPE
from app.services.fitting_room import FITTING_ROOM_JOB_TYPE
from app.services.personal_try_on_provider import TRY_ON_JOB_TYPE
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
    """Claim up to *limit* queued Magic AIJob rows (SKIP LOCKED).

    Claim commits ``running`` before provider I/O so owner cancel can land
    ``cancel_requested`` mid-generation (and skip Stars) without waiting on the
    provider row lock.
    """
    processed = 0
    for _ in range(limit):
        job = db.scalar(
            select(AIJob)
            .where(
                AIJob.status == "queued",
                AIJob.job_type != CROQUIS_GENERATE_JOB_TYPE,
            )
            .order_by(AIJob.created_at.asc())
            .limit(1)
            .with_for_update(of=AIJob, skip_locked=True)
        )
        if job is None:
            break

        from app.services.ai_service import _job_cancel_requested, debit_magic_stars_on_success

        # Owner cancel before provider work — fail closed, never charge.
        if _job_cancel_requested(job):
            job.status = "failed"
            job.error_message = job.error_message or "Cancelled by owner."
            db.commit()
            processed += 1
            continue

        job_id = job.id
        job.status = "running"
        db.commit()  # release row lock so POST /cancel can commit mid-provider

        job = db.get(AIJob, job_id)
        if job is None:
            processed += 1
            continue
        # Cancel may have landed between claim and reload.
        if _job_cancel_requested(job) or job.status == "failed":
            job.status = "failed"
            job.error_message = job.error_message or "Cancelled by owner."
            db.commit()
            processed += 1
            continue

        try:
            if job.job_type == TRY_ON_JOB_TYPE:
                from app.services.personal_try_on import complete_try_on_job

                # complete_try_on_job sets status/result itself (incl. failed paths).
                complete_try_on_job(db, job)
            elif job.job_type == FITTING_ROOM_JOB_TYPE:
                from app.services.fitting_room import complete_fitting_room_job

                complete_fitting_room_job(db, job)
            elif job.job_type == GARMENT_REALISM_JOB_TYPE:
                from app.services.personal_try_on import complete_garment_realism_job

                complete_garment_realism_job(db, job)
            elif job.job_type in sketch_openai.SKETCH_JOB_TYPES and sketch_openai.is_configured():
                job.result_data = sketch_openai.complete_sketch_job(job)
                job.error_message = None
                job.status = "completed"
            else:
                job.result_data = _stub_result(job)
                job.error_message = None
                job.status = "completed"
            # If the owner cancelled while the provider ran, do not keep a billable success.
            # Re-read cancel flag without db.refresh() (refresh would wipe in-memory result).
            if job.status == "completed":
                fresh_input = db.scalar(select(AIJob.input_data).where(AIJob.id == job.id))
                cancelled = isinstance(fresh_input, dict) and fresh_input.get("cancel_requested") is True
                if cancelled:
                    data = dict(job.input_data) if isinstance(job.input_data, dict) else {}
                    data["cancel_requested"] = True
                    job.input_data = data
                    job.status = "failed"
                    job.error_message = "Cancelled by owner."
            # Charge Stars only after the full Magic / Try On / FASHN look succeeds.
            # Garment realism is intermediate and is skipped inside the helper.
            # Cancelled jobs never debit (also gated inside debit_magic_stars_on_success).
            if job.status == "completed" and job.job_type in {
                "sketch_polish",
                TRY_ON_JOB_TYPE,
                FITTING_ROOM_JOB_TYPE,
            }:
                debit_magic_stars_on_success(db, job)
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
        # Automatic OpenAI cost estimate for every settled job (incl. failed billable).
        # FASHN predictions are recorded separately; skip when result provider is FASHN.
        try:
            from app.services.ai_cost_accounting import record_job_openai_estimate_best_effort

            result = job.result_data if isinstance(job.result_data, dict) else {}
            provider = str(result.get("provider") or "")
            if job.status in ("completed", "failed") and "Cancelled" not in (job.error_message or ""):
                record_job_openai_estimate_best_effort(
                    db,
                    job_id=job.id,
                    user_id=job.user_id,
                    job_type=job.job_type,
                    final_status=job.status,
                    model=str(result.get("model") or "")[:128] or None,
                    provider=provider,
                )
        except Exception:  # noqa: BLE001
            logger.exception("Job cost ledger hook failed (non-fatal)")
        db.commit()
        processed += 1
    return processed


def run_worker_tick(db: Session, *, limit: int = 12) -> int:
    """Process Magic AIJobs, croquis generate jobs, then Techpack Professional runs."""
    magic_n = run_magic_worker_tick(db, limit=limit)
    croquis_n = run_croquis_worker_tick(db, limit=min(4, limit))
    tech_n = run_techpack_worker_tick(db, limit=2)
    # Provider financial sync (OpenAI costs / FASHN credits) — gated off by default.
    try:
        from app.services.ai_cost_sync_worker import run_cost_sync_tick

        run_cost_sync_tick(db)
    except Exception:  # noqa: BLE001
        logger.exception("AI cost sync tick failed (non-fatal)")
    return magic_n + croquis_n + tech_n
