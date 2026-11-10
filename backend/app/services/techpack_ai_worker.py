"""Durable Techpack Professional AI consumer (claimed from techpack_ai_runs).

Runs beside Magic AIJob processing in ``fashionrise-ai-worker``. Paid work never
executes inside FastAPI background tasks tied to an HTTP request lifetime.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.techpack_ai_artifact import TechpackAIArtifact
from app.models.techpack_ai_run import TechpackAIRun
from app.services import techpack_ai

logger = logging.getLogger(__name__)

# Running rows with no progress update beyond this are treated as abandoned
# (worker SIGKILL / crash). Live Professional steps refresh updated_at often.
STALE_RUNNING_SECONDS = 20 * 60


def claim_next_techpack_run(db: Session) -> TechpackAIRun | None:
    """Claim one queued Professional run with SKIP LOCKED (transactional)."""
    run = db.scalar(
        select(TechpackAIRun)
        .where(
            TechpackAIRun.status == "queued",
            TechpackAIRun.stage == "professional",
        )
        .order_by(TechpackAIRun.created_at.asc())
        .limit(1)
        .with_for_update(of=TechpackAIRun, skip_locked=True)
    )
    if run is None:
        return None
    run.status = "running"
    req = dict(run.request) if isinstance(run.request, dict) else {}
    req["worker_claim"] = {"claimed_at": datetime.now(UTC).isoformat()}
    # Preserve preparing progress for FE.
    if not isinstance(req.get("progress"), dict):
        req["progress"] = {
            "phase": "preparing",
            "message": "Preparing your design",
            "pieces_done": 0,
            "pieces_total": 1,
        }
    run.request = req
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def process_claimed_techpack_run(db: Session, run_id: uuid.UUID) -> str:
    """Execute a previously claimed run. Returns terminal status string."""
    try:
        result = techpack_ai.execute_professional_run(db, run_id)
        status = str(result.get("status") or "unknown")
        if status == "completed":
            techpack_ai.debit_pdf_stars_on_success(db, run_id)
        return status
    except Exception:
        logger.exception("Techpack AI run %s failed in worker", run_id)
        row = db.get(TechpackAIRun, run_id)
        if row is None:
            return "missing"
        # Avoid stuck queued/running if execute crashed before a terminal status.
        if row.status in ("queued", "running"):
            techpack_ai._fail_run_preserve_cost(
                db, run_id, error="Worker execution failed", provider_called=True
            )
        db.refresh(row)
        return row.status


def reclaim_stale_running_techpack_runs(
    db: Session,
    *,
    older_than_seconds: int = STALE_RUNNING_SECONDS,
) -> int:
    """Fail or reconcile Professional runs abandoned mid-flight after a worker crash.

    Never auto-restarts paid OpenAI work. Rows with ``provider_in_flight`` and
    existing artifacts go to ``reconciliation_required`` (PDF recovery path).
    Otherwise the run is failed with cost preserved so the UI stops spinning.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=max(60, int(older_than_seconds)))
    stale = list(
        db.scalars(
            select(TechpackAIRun)
            .where(
                TechpackAIRun.status == "running",
                TechpackAIRun.stage == "professional",
                TechpackAIRun.updated_at < cutoff,
            )
            .order_by(TechpackAIRun.updated_at.asc())
            .limit(8)
            .with_for_update(of=TechpackAIRun, skip_locked=True)
        ).all()
    )
    reclaimed = 0
    for run in stale:
        req = dict(run.request) if isinstance(run.request, dict) else {}
        in_flight = req.get("provider_in_flight")
        art_count = db.scalar(
            select(TechpackAIArtifact.id)
            .where(TechpackAIArtifact.run_id == run.id)
            .limit(1)
        )
        has_arts = art_count is not None
        if isinstance(in_flight, dict) and in_flight and has_arts:
            # Known in-flight interrupt with saved illustrations — do not re-pay.
            out = techpack_ai.execute_professional_run(db, run.id)
            logger.warning(
                "Reclaimed stale techpack run %s → %s (in_flight + artifacts)",
                run.id,
                out.get("status"),
            )
        else:
            techpack_ai._fail_run_preserve_cost(
                db,
                run.id,
                error=(
                    "Generation was interrupted while illustrations were in progress. "
                    "No usable PDF was saved. Your design is safe — tap Generate AI PDF "
                    "again (new illustrations) to retry."
                ),
                provider_called=True,
            )
            logger.warning(
                "Failed stale techpack run %s (in_flight=%s artifacts=%s)",
                run.id,
                bool(in_flight),
                has_arts,
            )
        reclaimed += 1
    return reclaimed


def run_techpack_worker_tick(db: Session, *, limit: int = 2) -> int:
    """Reclaim abandoned runs, then claim and process queued Professional runs."""
    try:
        reclaim_stale_running_techpack_runs(db)
    except Exception:
        logger.exception("Techpack stale-run reclaim failed")
        db.rollback()
    processed = 0
    for _ in range(max(1, limit)):
        claimed = claim_next_techpack_run(db)
        if claimed is None:
            break
        process_claimed_techpack_run(db, claimed.id)
        processed += 1
    return processed
