"""Periodic provider financial sync tick (OpenAI costs + FASHN credits).

Intended for the AI worker loop or cron ``--once``. Does not call providers
on every admin page refresh. Gates remain disabled by default.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.fashn_credit_sync import sync_fashn_credits
from app.services.openai_cost_sync import sync_openai_costs

log = logging.getLogger(__name__)

_last_tick_monotonic: float | None = None


def run_cost_sync_tick(db: Session, *, force: bool = False) -> dict[str, Any]:
    """Run enabled syncs subject to interval throttle. Returns status summary."""
    global _last_tick_monotonic
    settings = get_settings()
    interval = float(getattr(settings, "ai_cost_sync_interval_seconds", 3600) or 3600)
    interval = max(60.0, interval)
    now = time.monotonic()
    if not force and _last_tick_monotonic is not None:
        if now - _last_tick_monotonic < interval:
            return {"skipped": True, "reason": "interval"}

    results: dict[str, Any] = {"skipped": False, "openai": None, "fashn": None}
    try:
        openai_run = sync_openai_costs(db, force=force)
        results["openai"] = {
            "status": openai_run.status,
            "rows_upserted": openai_run.rows_upserted,
            "error_code": openai_run.error_code,
        }
    except Exception:  # noqa: BLE001
        log.exception("OpenAI cost sync tick crashed")
        results["openai"] = {"status": "failed", "error_code": "TICK_CRASH"}

    try:
        fashn_run = sync_fashn_credits(db, force=force)
        results["fashn"] = {
            "status": fashn_run.status,
            "rows_upserted": fashn_run.rows_upserted,
            "error_code": fashn_run.error_code,
        }
    except Exception:  # noqa: BLE001
        log.exception("FASHN credit sync tick crashed")
        results["fashn"] = {"status": "failed", "error_code": "TICK_CRASH"}

    try:
        db.commit()
    except Exception:  # noqa: BLE001
        log.exception("Cost sync commit failed")
        db.rollback()
        results["commit"] = "failed"
    else:
        results["commit"] = "ok"
        _last_tick_monotonic = now
    return results
