"""Periodic provider financial sync tick (OpenAI costs + FASHN credits).

Intended for the AI worker loop or cron ``--once``. Does not call providers
on every admin page refresh. Gates remain disabled by default.

Centralized across AI workers: a Postgres advisory lock plus a DB-backed
interval gate ensure at most one sync cycle per
``AI_COST_SYNC_INTERVAL_SECONDS`` cluster-wide (not once per worker process).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_cost_accounting import ProviderSyncRun
from app.services.fashn_credit_sync import sync_fashn_credits
from app.services.openai_cost_sync import sync_openai_costs

log = logging.getLogger(__name__)

# Stable cluster-wide lock key for AI provider cost sync (FashionRise AICS).
AI_COST_SYNC_LOCK_KEY = 0x46524953_41494353

_last_tick_monotonic: float | None = None


def _interval_seconds(settings: Any) -> float:
    interval = float(getattr(settings, "ai_cost_sync_interval_seconds", 3600) or 3600)
    return max(60.0, interval)


def _recent_successful_sync(db: Session, *, interval: float) -> bool:
    """True when any worker already completed a provider sync within the interval."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=interval)
    count = db.scalar(
        select(func.count())
        .select_from(ProviderSyncRun)
        .where(
            ProviderSyncRun.status.in_(("success", "partial")),
            ProviderSyncRun.sync_kind.in_(("organization_costs", "credits_balance")),
            ProviderSyncRun.started_at >= cutoff,
        )
    )
    return int(count or 0) > 0


def _try_acquire_lock(db: Session) -> bool:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        # Non-Postgres (rare in prod): fall through; process throttle still applies.
        return True
    got = db.execute(
        text("SELECT pg_try_advisory_xact_lock(:k)"),
        {"k": AI_COST_SYNC_LOCK_KEY},
    ).scalar()
    return bool(got)


def run_cost_sync_tick(db: Session, *, force: bool = False) -> dict[str, Any]:
    """Run enabled syncs subject to cluster-wide interval + lock. Returns status summary."""
    global _last_tick_monotonic
    settings = get_settings()
    interval = _interval_seconds(settings)
    now = time.monotonic()
    if not force and _last_tick_monotonic is not None:
        if now - _last_tick_monotonic < interval:
            return {"skipped": True, "reason": "interval"}

    if not force and _recent_successful_sync(db, interval=interval):
        _last_tick_monotonic = now
        return {"skipped": True, "reason": "interval_db"}

    if not _try_acquire_lock(db):
        return {"skipped": True, "reason": "lock_held"}

    # Re-check after lock: another worker may have finished while we waited.
    if not force and _recent_successful_sync(db, interval=interval):
        _last_tick_monotonic = now
        return {"skipped": True, "reason": "interval_db"}

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
