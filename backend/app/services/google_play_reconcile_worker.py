"""Hourly Google Play financial reconcile tick (cluster-wide).

Mirrors ``ai_cost_sync_worker``: Postgres advisory lock + DB-backed interval so
AI workers do not call orders.get on every job tick. Does not block or delay
Magic / croquis / techpack processing beyond a non-fatal try/except wrapper.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.models.google_play_reconcile import GooglePlayReconcileRun
from app.services import google_play_reconcile

log = logging.getLogger(__name__)

# Stable cluster-wide lock key for Google Play financial reconcile (FashionRise GPRC).
GOOGLE_PLAY_RECONCILE_LOCK_KEY = 0x46524953_47505243

_GOOGLE_API_ERROR_CODES = frozenset(
    {
        "GOOGLE_API_UNAVAILABLE",
        "GOOGLE_API_FORBIDDEN",
        "GOOGLE_NOT_CONFIGURED",
        "TICK_CRASH",
    }
)

_last_tick_monotonic: float | None = None


def _interval_seconds(settings: Any) -> float:
    interval = float(
        getattr(settings, "iap_google_financial_reconcile_interval_seconds", 3600) or 3600
    )
    return max(60.0, interval)


def _recent_sync(db: Session, *, interval: float) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=interval)
    count = db.scalar(
        select(func.count())
        .select_from(GooglePlayReconcileRun)
        .where(
            GooglePlayReconcileRun.status.in_(("success", "partial", "skipped_disabled")),
            GooglePlayReconcileRun.started_at >= cutoff,
        )
    )
    return int(count or 0) > 0


def _backoff_active(db: Session) -> tuple[bool, str | None]:
    """Skip when the last run failed on Google API errors within exponential backoff."""
    last = db.scalar(
        select(GooglePlayReconcileRun)
        .order_by(GooglePlayReconcileRun.started_at.desc())
        .limit(1)
    )
    if last is None or last.status != "failed":
        return False, None
    if (last.error_code or "") not in _GOOGLE_API_ERROR_CODES:
        return False, None
    meta = last.meta if isinstance(last.meta, dict) else {}
    streak = max(0, int(meta.get("fail_streak") or 1))
    # 15m, 30m, 1h, 2h, 4h, cap 6h
    backoff = min(6 * 3600, 900 * (2 ** min(streak - 1, 5)))
    ready_at = last.started_at + timedelta(seconds=backoff)
    if datetime.now(timezone.utc) < ready_at:
        return True, f"backoff_until_{ready_at.isoformat()}"
    return False, None


def _fail_streak(db: Session) -> int:
    last = db.scalar(
        select(GooglePlayReconcileRun)
        .order_by(GooglePlayReconcileRun.started_at.desc())
        .limit(1)
    )
    if last is None or last.status != "failed":
        return 0
    meta = last.meta if isinstance(last.meta, dict) else {}
    return max(0, int(meta.get("fail_streak") or 0))


def _try_acquire_lock(db: Session) -> bool:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return True
    got = db.execute(
        text("SELECT pg_try_advisory_xact_lock(:k)"),
        {"k": GOOGLE_PLAY_RECONCILE_LOCK_KEY},
    ).scalar()
    return bool(got)


def run_google_play_reconcile_tick(db: Session, *, force: bool = False) -> dict[str, Any]:
    """Run bounded financial reconcile subject to cluster interval + lock + backoff."""
    global _last_tick_monotonic
    settings = get_settings()
    interval = _interval_seconds(settings)
    now_m = time.monotonic()
    if not force and _last_tick_monotonic is not None:
        if now_m - _last_tick_monotonic < interval:
            return {"skipped": True, "reason": "interval"}

    enabled = bool(getattr(settings, "iap_google_financial_reconcile_enabled", True))
    if not enabled:
        if not force and _recent_sync(db, interval=interval):
            _last_tick_monotonic = now_m
            return {"skipped": True, "reason": "interval_db"}
        google_play_reconcile.record_reconcile_run(
            db,
            status="skipped_disabled",
            dry_run=True,
            meta={"reason": "reconcile_disabled"},
        )
        _last_tick_monotonic = now_m
        return {"skipped": True, "reason": "disabled"}

    if not force and _recent_sync(db, interval=interval):
        _last_tick_monotonic = now_m
        return {"skipped": True, "reason": "interval_db"}

    in_backoff, backoff_reason = _backoff_active(db)
    if not force and in_backoff:
        google_play_reconcile.record_reconcile_run(
            db,
            status="skipped_backoff",
            dry_run=True,
            meta={"reason": backoff_reason},
        )
        _last_tick_monotonic = now_m
        return {"skipped": True, "reason": "backoff"}

    if not _try_acquire_lock(db):
        return {"skipped": True, "reason": "lock_held"}

    if not force and _recent_sync(db, interval=interval):
        _last_tick_monotonic = now_m
        return {"skipped": True, "reason": "interval_db"}

    apply_enabled = bool(
        getattr(settings, "iap_google_financial_reconcile_apply", False)
    )
    # Public apply stays OFF unless explicitly authorized.
    dry_run = not apply_enabled
    limit = int(getattr(settings, "iap_google_financial_reconcile_limit", 50) or 50)
    started = datetime.now(timezone.utc)

    try:
        report = google_play_reconcile.reconcile_android_purchases(
            db,
            dry_run=dry_run,
            limit=limit,
            persist=True,
            advance_cursor=True,
        )
    except ServiceUnavailableError as exc:
        streak = _fail_streak(db) + 1
        google_play_reconcile.record_reconcile_run(
            db,
            status="failed",
            dry_run=dry_run,
            error_code="GOOGLE_API_UNAVAILABLE",
            error_detail=str(exc),
            meta={"fail_streak": streak},
            started_at=started,
        )
        _last_tick_monotonic = now_m
        return {"skipped": False, "status": "failed", "error_code": "GOOGLE_API_UNAVAILABLE"}
    except Exception as exc:  # noqa: BLE001
        log.exception("Google Play financial reconcile tick crashed")
        streak = _fail_streak(db) + 1
        try:
            google_play_reconcile.record_reconcile_run(
                db,
                status="failed",
                dry_run=dry_run,
                error_code="TICK_CRASH",
                error_detail=f"{type(exc).__name__}:{exc}",
                meta={"fail_streak": streak},
                started_at=started,
            )
        except Exception:  # noqa: BLE001
            log.exception("Failed to record reconcile crash run")
        _last_tick_monotonic = now_m
        return {"skipped": False, "status": "failed", "error_code": "TICK_CRASH"}

    counts = report.get("counts") or {}
    has_errors = int(counts.get("skip_error") or 0) > 0
    status = "partial" if has_errors else "success"
    google_play_reconcile.record_reconcile_run(
        db,
        status=status,
        dry_run=bool(report.get("dry_run", dry_run)),
        report=report,
        meta={"fail_streak": 0, "apply_enabled": apply_enabled},
        started_at=started,
    )
    _last_tick_monotonic = now_m
    return {
        "skipped": False,
        "status": status,
        "scanned": report.get("scanned"),
        "stars_would_recover": report.get("stars_would_recover"),
        "stars_recovered": report.get("stars_recovered"),
        "dry_run": report.get("dry_run"),
    }
