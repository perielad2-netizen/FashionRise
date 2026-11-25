"""FASHN credits balance sync (GET /v1/credits).

Fail-closed via FASHN_CREDIT_SYNC_ENABLED=false.
Never auto-purchases credits or enables auto-top-up.
Balance decreases are snapshots only — not expenditure records.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_cost_accounting import (
    PROVIDER_FASHN,
    FashnCreditSnapshot,
    ProviderSyncRun,
)
from app.services.ai_cost_accounting import active_fashn_credit_rate

log = logging.getLogger(__name__)

_http_override: Callable[..., httpx.Response] | None = None


def set_fashn_credit_http_override(fn: Callable[..., httpx.Response] | None) -> None:
    global _http_override
    _http_override = fn


def _redact(detail: str) -> str:
    settings = get_settings()
    text = (detail or "")[:400]
    key = getattr(settings, "fashn_api_key", None)
    if key and key in text:
        text = text.replace(key, "[REDACTED]")
    return text


def parse_credits_payload(payload: dict[str, Any]) -> dict[str, int]:
    credits = payload.get("credits") if isinstance(payload, dict) else None
    if not isinstance(credits, dict):
        raise ValueError("missing credits object")
    total = int(credits.get("total") or 0)
    subscription = int(credits.get("subscription") or 0)
    on_demand = int(credits.get("on_demand") or 0)
    if total < 0 or subscription < 0 or on_demand < 0:
        raise ValueError("negative credits")
    return {
        "credits_total": total,
        "credits_subscription": subscription,
        "credits_on_demand": on_demand,
    }


def sync_fashn_credits(
    db: Session,
    *,
    force: bool = False,
) -> ProviderSyncRun:
    settings = get_settings()
    started = datetime.now(timezone.utc)
    run = ProviderSyncRun(
        id=uuid.uuid4(),
        provider=PROVIDER_FASHN,
        sync_kind="credits_balance",
        status="skipped_disabled",
        started_at=started,
        rows_upserted=0,
        meta={},
    )
    db.add(run)
    db.flush()

    enabled = bool(getattr(settings, "fashn_credit_sync_enabled", False))
    if not enabled and not force:
        run.status = "skipped_disabled"
        run.finished_at = datetime.now(timezone.utc)
        run.error_detail = "FASHN_CREDIT_SYNC_ENABLED is false"
        db.flush()
        return run

    api_key = (getattr(settings, "fashn_api_key", None) or "").strip()
    if not api_key:
        run.status = "skipped_missing_credentials"
        run.finished_at = datetime.now(timezone.utc)
        run.error_code = "MISSING_API_KEY"
        run.error_detail = "FASHN_API_KEY not configured"
        db.flush()
        return run

    base = (getattr(settings, "fashn_api_base_url", None) or "https://api.fashn.ai").rstrip("/")
    url = f"{base}/v1/credits"
    timeout = float(getattr(settings, "fashn_credit_sync_timeout_seconds", 20) or 20)

    try:
        if _http_override is not None:
            resp = _http_override(
                "GET",
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        else:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
        if resp.status_code in (401, 403):
            run.status = "failed"
            run.error_code = "AUTH"
            run.error_detail = _redact(f"FASHN credits HTTP {resp.status_code}")
        elif resp.status_code >= 400:
            run.status = "failed"
            run.error_code = f"HTTP_{resp.status_code}"
            run.error_detail = _redact(f"FASHN credits HTTP {resp.status_code}")
        else:
            payload = resp.json()
            parsed = parse_credits_payload(payload)
            rate, pricing_id, _ = active_fashn_credit_rate(db)
            est = None
            if rate is not None:
                est = (Decimal(parsed["credits_total"]) * rate).quantize(Decimal("0.00000001"))
            snap = FashnCreditSnapshot(
                id=uuid.uuid4(),
                credits_total=parsed["credits_total"],
                credits_subscription=parsed["credits_subscription"],
                credits_on_demand=parsed["credits_on_demand"],
                estimated_value_usd=est,
                pricing_version_id=pricing_id,
                captured_at=datetime.now(timezone.utc),
            )
            db.add(snap)
            run.rows_upserted = 1
            run.status = "success"
            run.meta = {
                "credits_total": parsed["credits_total"],
                "estimated_value_kind": "estimated",
            }
    except httpx.TimeoutException:
        run.status = "failed"
        run.error_code = "TIMEOUT"
        run.error_detail = "FASHN credits timeout"
    except httpx.HTTPError as exc:
        run.status = "failed"
        run.error_code = "TRANSPORT"
        run.error_detail = _redact(f"FASHN credits transport: {type(exc).__name__}")
    except ValueError as exc:
        run.status = "failed"
        run.error_code = "INVALID_PAYLOAD"
        run.error_detail = _redact(str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("FASHN credit sync failed")
        run.status = "failed"
        run.error_code = "INTERNAL"
        run.error_detail = _redact(type(exc).__name__)

    run.finished_at = datetime.now(timezone.utc)
    db.flush()
    return run
