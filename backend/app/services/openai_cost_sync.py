"""OpenAI Organization Costs API sync (read-only admin reporting).

Uses OPENAI_ADMIN_API_KEY — never the generation key for admin reporting when
configured separately. Sync is fail-closed (OPENAI_COST_SYNC_ENABLED=false).

Never creates AI generation requests with the admin key.
Never logs or returns the API key.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_cost_accounting import PROVIDER_OPENAI, ProviderSyncRun
from app.services.ai_cost_accounting import upsert_openai_cost_rows

log = logging.getLogger(__name__)

OPENAI_COSTS_URL = "https://api.openai.com/v1/organization/costs"

# Injectable transport for tests (no live HTTP).
_http_override: Callable[..., httpx.Response] | None = None


def set_openai_cost_http_override(fn: Callable[..., httpx.Response] | None) -> None:
    global _http_override
    _http_override = fn


def _redact(detail: str) -> str:
    settings = get_settings()
    text = (detail or "")[:400]
    for secret in (
        getattr(settings, "openai_admin_api_key", None),
        getattr(settings, "openai_api_key", None),
    ):
        if secret and secret in text:
            text = text.replace(secret, "[REDACTED]")
    return text


def parse_costs_page(
    payload: dict[str, Any],
    *,
    fashionrise_project_id: str | None,
) -> list[dict[str, Any]]:
    """Parse one Costs API page into upsertable rows."""
    rows: list[dict[str, Any]] = []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return rows
    for bucket in data:
        if not isinstance(bucket, dict):
            continue
        start_ts = bucket.get("start_time")
        end_ts = bucket.get("end_time")
        if start_ts is None or end_ts is None:
            continue
        try:
            bucket_start = datetime.fromtimestamp(int(start_ts), tz=timezone.utc)
            bucket_end = datetime.fromtimestamp(int(end_ts), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            continue
        results = bucket.get("results")
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            if result.get("object") and result.get("object") != "organization.costs.result":
                # Skip non-cost usage result shapes if API mixes them.
                if "amount" not in result:
                    continue
            amount_obj = result.get("amount") if isinstance(result.get("amount"), dict) else {}
            currency = str(amount_obj.get("currency") or "usd").lower()[:8]
            try:
                amount = Decimal(str(amount_obj.get("value") or 0))
            except Exception:  # noqa: BLE001
                continue
            if amount < 0:
                amount = Decimal("0")
            project_id = result.get("project_id")
            project_id_s = str(project_id) if project_id else None
            line_item = result.get("line_item")
            line_item_s = str(line_item)[:256] if line_item else None
            quantity = result.get("quantity")
            quantity_unit = result.get("quantity_unit")
            if fashionrise_project_id and project_id_s == fashionrise_project_id:
                scope = "project"
                attribution = "project"
            elif project_id_s:
                scope = "project"
                attribution = "organization_unattributed"
            else:
                scope = "organization"
                attribution = "organization_unattributed"
            fp_src = "|".join(
                [
                    str(int(start_ts)),
                    str(int(end_ts)),
                    project_id_s or "",
                    line_item_s or "",
                    currency,
                    str(result.get("api_key_id") or ""),
                    str(result.get("user_id") or ""),
                ]
            )
            fingerprint = hashlib.sha256(fp_src.encode("utf-8")).hexdigest()[:64]
            rows.append(
                {
                    "bucket_start": bucket_start,
                    "bucket_end": bucket_end,
                    "project_id": project_id_s,
                    "line_item": line_item_s,
                    "currency": currency,
                    "amount": amount,
                    "quantity": Decimal(str(quantity)) if quantity is not None else None,
                    "quantity_unit": str(quantity_unit)[:64] if quantity_unit else None,
                    "scope": scope,
                    "attribution": attribution,
                    "raw_fingerprint": fingerprint,
                }
            )
    return rows


def _request_page(
    *,
    api_key: str,
    params: dict[str, Any],
    timeout: float,
) -> httpx.Response:
    if _http_override is not None:
        return _http_override("GET", OPENAI_COSTS_URL, params=params, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
    with httpx.Client(timeout=timeout) as client:
        return client.get(
            OPENAI_COSTS_URL,
            params=params,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )


def sync_openai_costs(
    db: Session,
    *,
    lookback_days: int | None = None,
    force: bool = False,
) -> ProviderSyncRun:
    """Fetch and persist OpenAI daily costs. Respects enable + credential gates."""
    settings = get_settings()
    started = datetime.now(timezone.utc)
    run = ProviderSyncRun(
        id=uuid.uuid4(),
        provider=PROVIDER_OPENAI,
        sync_kind="organization_costs",
        status="skipped_disabled",
        started_at=started,
        rows_upserted=0,
        meta={},
    )
    db.add(run)
    db.flush()

    enabled = bool(getattr(settings, "openai_cost_sync_enabled", False))
    if not enabled and not force:
        run.status = "skipped_disabled"
        run.finished_at = datetime.now(timezone.utc)
        run.error_detail = "OPENAI_COST_SYNC_ENABLED is false"
        db.flush()
        return run

    api_key = (getattr(settings, "openai_admin_api_key", None) or "").strip()
    if not api_key:
        run.status = "skipped_missing_credentials"
        run.finished_at = datetime.now(timezone.utc)
        run.error_code = "MISSING_ADMIN_KEY"
        run.error_detail = "OPENAI_ADMIN_API_KEY not configured"
        db.flush()
        return run

    days = lookback_days
    if days is None:
        days = int(getattr(settings, "openai_cost_sync_lookback_days", 14) or 14)
    days = max(1, min(int(days), 180))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    project_id = (getattr(settings, "openai_billing_project_id", None) or "").strip() or None
    timeout = float(getattr(settings, "openai_cost_sync_timeout_seconds", 30) or 30)

    params: dict[str, Any] = {
        "start_time": int(start.timestamp()),
        "end_time": int(end.timestamp()),
        "bucket_width": "1d",
        "limit": 180,
        "group_by": ["project_id", "line_item"],
    }
    if project_id:
        # Still request org-wide with grouping; project filter optionally applied.
        # Keep unfiltered so unattributed org charges remain visible separately.
        pass

    upserted = 0
    pages = 0
    next_page: str | None = None
    try:
        while pages < 40:
            page_params = dict(params)
            if next_page:
                page_params["page"] = next_page
            resp = _request_page(api_key=api_key, params=page_params, timeout=timeout)
            if resp.status_code in (401, 403):
                run.status = "failed"
                run.error_code = "AUTH"
                run.error_detail = _redact(f"OpenAI Costs API HTTP {resp.status_code}")
                break
            if resp.status_code >= 400:
                run.status = "failed"
                run.error_code = f"HTTP_{resp.status_code}"
                run.error_detail = _redact(f"OpenAI Costs API HTTP {resp.status_code}")
                break
            try:
                payload = resp.json()
            except Exception:  # noqa: BLE001
                run.status = "failed"
                run.error_code = "INVALID_JSON"
                run.error_detail = "OpenAI Costs API returned non-JSON"
                break
            if not isinstance(payload, dict):
                run.status = "failed"
                run.error_code = "INVALID_PAYLOAD"
                run.error_detail = "OpenAI Costs API malformed page"
                break
            rows = parse_costs_page(payload, fashionrise_project_id=project_id)
            upserted += upsert_openai_cost_rows(db, rows)
            pages += 1
            if not payload.get("has_more"):
                run.status = "success"
                break
            next_page = payload.get("next_page")
            if not next_page:
                run.status = "success"
                break
        else:
            run.status = "partial"
            run.error_code = "PAGE_CAP"
            run.error_detail = "Stopped after page cap; partial sync persisted"
    except httpx.TimeoutException:
        run.status = "failed"
        run.error_code = "TIMEOUT"
        run.error_detail = "OpenAI Costs API timeout"
    except httpx.HTTPError as exc:
        run.status = "failed"
        run.error_code = "TRANSPORT"
        run.error_detail = _redact(f"OpenAI Costs transport: {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        log.exception("OpenAI cost sync failed")
        run.status = "failed"
        run.error_code = "INTERNAL"
        run.error_detail = _redact(f"{type(exc).__name__}")

    run.rows_upserted = upserted
    run.finished_at = datetime.now(timezone.utc)
    run.meta = {
        "pages": pages,
        "lookback_days": days,
        "project_id_configured": bool(project_id),
        # Never include key material.
    }
    db.flush()
    return run
