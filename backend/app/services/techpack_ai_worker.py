"""Durable Techpack Professional AI consumer (claimed from techpack_ai_runs).

Runs beside Magic AIJob processing in ``fashionrise-ai-worker``. Paid work never
executes inside FastAPI background tasks tied to an HTTP request lifetime.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.techpack_ai_run import TechpackAIRun
from app.services import techpack_ai

logger = logging.getLogger(__name__)


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
        return str(result.get("status") or "unknown")
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


def run_techpack_worker_tick(db: Session, *, limit: int = 2) -> int:
    """Claim and process up to *limit* queued Professional techpack runs."""
    processed = 0
    for _ in range(max(1, limit)):
        claimed = claim_next_techpack_run(db)
        if claimed is None:
            break
        process_claimed_techpack_run(db, claimed.id)
        processed += 1
    return processed
