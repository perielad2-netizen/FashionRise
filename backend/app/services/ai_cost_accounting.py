"""AI cost accounting — record + aggregate OpenAI/FASHN financial telemetry.

Never mixes actual cash costs with estimated consumption without explicit kinds.
Does not invent zeros for missing provider data — marks unavailable.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_cost_accounting import (
    COST_KIND_ACTUAL,
    COST_KIND_ESTIMATED,
    COST_KIND_UNAVAILABLE,
    CREDITS_KIND_ACTUAL,
    CREDITS_KIND_ESTIMATED_FALLBACK,
    CREDITS_KIND_UNAVAILABLE,
    PROVIDER_FASHN,
    PROVIDER_OPENAI,
    AiProviderOperation,
    FashnCreditSnapshot,
    FashnPredictionCost,
    OpenAiCostDaily,
    OperatorExpenseRecord,
    ProviderPricingVersion,
    ProviderSyncRun,
)
from app.models.user import User

log = logging.getLogger(__name__)

_ZERO = Decimal("0")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def active_fashn_credit_rate(
    db: Session, *, at: datetime | None = None
) -> tuple[Decimal | None, uuid.UUID | None, bool]:
    """Return (usd_per_credit, pricing_version_id, operator_confirmed)."""
    when = at or _utcnow()
    row = db.scalars(
        select(ProviderPricingVersion)
        .where(
            ProviderPricingVersion.provider == PROVIDER_FASHN,
            ProviderPricingVersion.pricing_key == "credit_on_demand",
            ProviderPricingVersion.effective_from <= when,
            or_(
                ProviderPricingVersion.effective_to.is_(None),
                ProviderPricingVersion.effective_to > when,
            ),
        )
        .order_by(
            ProviderPricingVersion.operator_confirmed.desc(),
            ProviderPricingVersion.effective_from.desc(),
        )
        .limit(1)
    ).first()
    if row is None:
        # Config soft fallback — still estimated, not cash.
        settings = get_settings()
        cents = int(getattr(settings, "fashn_try_on_estimate_cents", 8) or 8)
        return Decimal(cents) / Decimal(100), None, False
    return Decimal(row.unit_amount), row.id, bool(row.operator_confirmed)


def record_fashn_prediction(
    db: Session,
    *,
    prediction_id: str,
    feature: str,
    final_status: str,
    user_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    model: str | None = None,
    generation_mode: str | None = None,
    resolution: str | None = None,
    output_count: int | None = None,
    credits_consumed: int | None = None,
    credits_header_present: bool = False,
    platform: str | None = None,
    occurred_at: datetime | None = None,
) -> FashnPredictionCost | None:
    """Idempotent insert of one FASHN prediction cost row.

    Missing credit header → credits_kind=unavailable (not zero).
    Never raises into the generation path — callers should still wrap.
    """
    pid = (prediction_id or "").strip()
    if not pid:
        return None

    if credits_header_present and credits_consumed is not None:
        kind = CREDITS_KIND_ACTUAL
        credits = max(0, int(credits_consumed))
    elif credits_consumed is not None and not credits_header_present:
        kind = CREDITS_KIND_ESTIMATED_FALLBACK
        credits = max(0, int(credits_consumed))
    else:
        kind = CREDITS_KIND_UNAVAILABLE
        credits = None

    rate, pricing_id, _confirmed = active_fashn_credit_rate(db, at=occurred_at)
    est = None
    if credits is not None and rate is not None:
        est = (Decimal(credits) * rate).quantize(Decimal("0.00000001"))

    existing = db.scalars(
        select(FashnPredictionCost).where(FashnPredictionCost.prediction_id == pid)
    ).first()
    if existing is not None:
        return existing

    row = FashnPredictionCost(
        id=uuid.uuid4(),
        prediction_id=pid[:128],
        user_id=user_id,
        job_id=job_id,
        feature=(feature or "unknown")[:64],
        model=(model or None)[:128] if model else None,
        generation_mode=(generation_mode or None)[:64] if generation_mode else None,
        resolution=(resolution or None)[:64] if resolution else None,
        output_count=output_count,
        final_status=(final_status or "unknown")[:32],
        credits_consumed=credits,
        credits_kind=kind,
        estimated_cost_usd=est,
        pricing_version_id=pricing_id,
        platform=(platform or None)[:32] if platform else None,
        occurred_at=occurred_at or _utcnow(),
    )
    db.add(row)

    # Mirror into reusable operations ledger (same idempotency).
    op_key = f"fashn:prediction:{pid}"
    op_existing = db.scalars(
        select(AiProviderOperation).where(AiProviderOperation.idempotency_key == op_key)
    ).first()
    if op_existing is None:
        cost_kind = (
            COST_KIND_ESTIMATED
            if kind in (CREDITS_KIND_ACTUAL, CREDITS_KIND_ESTIMATED_FALLBACK)
            else COST_KIND_UNAVAILABLE
        )
        db.add(
            AiProviderOperation(
                id=uuid.uuid4(),
                provider=PROVIDER_FASHN,
                feature=(feature or "unknown")[:64],
                user_id=user_id,
                job_id=job_id,
                provider_request_id=pid[:128],
                model=(model or None)[:128] if model else None,
                credits_consumed=credits,
                estimated_cost_usd=est,
                actual_cost_usd=None,  # cash requires invoice — never invent
                cost_kind=cost_kind,
                pricing_version_id=pricing_id,
                final_status=(final_status or "unknown")[:32],
                platform=(platform or None)[:32] if platform else None,
                idempotency_key=op_key[:160],
                occurred_at=occurred_at or _utcnow(),
            )
        )
    try:
        db.flush()
    except Exception:  # noqa: BLE001 — concurrent duplicate
        db.expire_all()
        return db.scalars(
            select(FashnPredictionCost).where(FashnPredictionCost.prediction_id == pid)
        ).first()
    return row


def record_fashn_predictions_best_effort(
    db: Session,
    *,
    prediction_ids: list[str] | None,
    credits_used_total: int | None,
    credits_header_present: bool,
    feature: str,
    user_id: uuid.UUID | None,
    job_id: uuid.UUID | None = None,
    model: str | None = None,
    generation_mode: str | None = None,
    resolution: str | None = None,
    platform: str | None = None,
    final_status: str = "completed",
) -> int:
    """Best-effort multi-prediction record. Never raises; returns rows written."""
    ids = [str(x).strip() for x in (prediction_ids or []) if str(x).strip()]
    if not ids:
        return 0
    written = 0
    # Distribute known total across predictions when header was aggregate-only.
    per: list[int | None]
    if credits_header_present and credits_used_total is not None and len(ids) == 1:
        per = [int(credits_used_total)]
    elif credits_header_present and credits_used_total is not None and len(ids) > 1:
        # Prefer equal split only when total matches count; else mark per-id actual unknown
        # but store total on first row as actual and others unavailable.
        if int(credits_used_total) == len(ids):
            per = [1] * len(ids)
        else:
            per = [int(credits_used_total)] + [None] * (len(ids) - 1)
    elif credits_used_total is not None and not credits_header_present:
        per = [None] * len(ids)  # do not invent per-prediction from fallback total
    else:
        per = [None] * len(ids)

    for i, pid in enumerate(ids):
        try:
            nested = db.begin_nested()
            credits = per[i]
            header = credits_header_present and credits is not None
            row = record_fashn_prediction(
                db,
                prediction_id=pid,
                feature=feature,
                final_status=final_status,
                user_id=user_id,
                job_id=job_id,
                model=model,
                generation_mode=generation_mode,
                resolution=resolution,
                output_count=1,
                credits_consumed=credits,
                credits_header_present=header,
                platform=platform,
            )
            nested.commit()
            if row is not None:
                written += 1
        except Exception:  # noqa: BLE001
            log.exception("FASHN cost record failed for prediction %s", pid[:16])
            try:
                nested.rollback()
            except Exception:  # noqa: BLE001
                pass
    return written


def record_openai_operation(
    db: Session,
    *,
    idempotency_key: str,
    feature: str,
    final_status: str,
    user_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    provider_request_id: str | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    cached_input_tokens: int | None = None,
    output_tokens: int | None = None,
    image_units: int | None = None,
    estimated_cost_usd: Decimal | float | str | None = None,
    platform: str | None = None,
    occurred_at: datetime | None = None,
) -> AiProviderOperation | None:
    """Idempotent OpenAI per-operation estimate (not org cash costs)."""
    key = (idempotency_key or "").strip()[:160]
    if not key:
        return None
    existing = db.scalars(
        select(AiProviderOperation).where(AiProviderOperation.idempotency_key == key)
    ).first()
    if existing is not None:
        return existing
    est = _dec(estimated_cost_usd)
    row = AiProviderOperation(
        id=uuid.uuid4(),
        provider=PROVIDER_OPENAI,
        feature=(feature or "unknown")[:64],
        user_id=user_id,
        job_id=job_id,
        provider_request_id=(provider_request_id or None)[:128] if provider_request_id else None,
        model=(model or None)[:128] if model else None,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        image_units=image_units,
        estimated_cost_usd=est,
        actual_cost_usd=None,
        cost_kind=COST_KIND_ESTIMATED if est is not None else COST_KIND_UNAVAILABLE,
        final_status=(final_status or "unknown")[:32],
        platform=(platform or None)[:32] if platform else None,
        idempotency_key=key,
        occurred_at=occurred_at or _utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def latest_fashn_credit_snapshot(db: Session) -> dict[str, Any] | None:
    row = db.scalars(
        select(FashnCreditSnapshot).order_by(FashnCreditSnapshot.captured_at.desc()).limit(1)
    ).first()
    if row is None:
        return None
    return {
        "credits_total": int(row.credits_total),
        "credits_subscription": int(row.credits_subscription),
        "credits_on_demand": int(row.credits_on_demand),
        "estimated_value_usd": float(row.estimated_value_usd)
        if row.estimated_value_usd is not None
        else None,
        "estimated_value_kind": "estimated",
        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
    }


def latest_sync_status(db: Session, provider: str, sync_kind: str) -> dict[str, Any]:
    row = db.scalars(
        select(ProviderSyncRun)
        .where(
            ProviderSyncRun.provider == provider,
            ProviderSyncRun.sync_kind == sync_kind,
        )
        .order_by(ProviderSyncRun.started_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return {
            "kind": "unavailable",
            "status": "never_synced",
            "detail": "No sync run recorded. Provider sync disabled by default.",
        }
    return {
        "kind": "exact" if row.status == "success" else "unavailable",
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "rows_upserted": int(row.rows_upserted or 0),
        "error_code": row.error_code,
        # Never echo secrets — error_detail is already sanitized by sync clients.
        "error_detail": (row.error_detail or None),
    }


def _audience_user_ids_subq(audience_filter):
    if audience_filter is None:
        return None
    return select(User.id).where(audience_filter)


def build_ai_financial_section(
    db: Session,
    *,
    start: datetime | None,
    end: datetime,
    audience_filter,
) -> dict[str, Any]:
    """Admin overview AI costs / income-vs-expenses block."""
    settings = get_settings()
    openai_sync_enabled = bool(getattr(settings, "openai_cost_sync_enabled", False))
    fashn_sync_enabled = bool(getattr(settings, "fashn_credit_sync_enabled", False))

    # --- OpenAI actual costs (org/project sync) — GLOBAL unless project-scoped ---
    openai_q = select(
        func.coalesce(func.sum(OpenAiCostDaily.amount), 0),
        func.count(OpenAiCostDaily.id),
    ).where(OpenAiCostDaily.bucket_start < end)
    if start is not None:
        openai_q = openai_q.where(OpenAiCostDaily.bucket_start >= start)
    # Prefer FashionRise project rows when configured; still report org totals separately.
    project_id = (getattr(settings, "openai_billing_project_id", None) or "").strip() or None
    openai_project_amount = _ZERO
    openai_org_amount = _ZERO
    openai_row_count = 0
    if project_id:
        proj_filters = [OpenAiCostDaily.bucket_start < end, OpenAiCostDaily.project_id == project_id]
        if start is not None:
            proj_filters.append(OpenAiCostDaily.bucket_start >= start)
        openai_project_amount = Decimal(
            str(
                db.scalar(
                    select(func.coalesce(func.sum(OpenAiCostDaily.amount), 0)).where(*proj_filters)
                )
                or 0
            )
        )
        org_filters = [
            OpenAiCostDaily.bucket_start < end,
            or_(OpenAiCostDaily.project_id.is_(None), OpenAiCostDaily.project_id != project_id),
        ]
        if start is not None:
            org_filters.append(OpenAiCostDaily.bucket_start >= start)
        openai_org_amount = Decimal(
            str(
                db.scalar(
                    select(func.coalesce(func.sum(OpenAiCostDaily.amount), 0)).where(*org_filters)
                )
                or 0
            )
        )
        openai_row_count = int(
            db.scalar(select(func.count()).select_from(OpenAiCostDaily).where(*proj_filters)) or 0
        )
    else:
        openai_org_amount = Decimal(str(db.execute(openai_q).one()[0] or 0))
        count_filters = [OpenAiCostDaily.bucket_start < end]
        if start is not None:
            count_filters.append(OpenAiCostDaily.bucket_start >= start)
        openai_row_count = int(
            db.scalar(select(func.count()).select_from(OpenAiCostDaily).where(*count_filters)) or 0
        )

    openai_has_data = openai_row_count > 0 or openai_project_amount > 0 or openai_org_amount > 0

    # Daily trend from OpenAI actuals (global / project)
    trend_q = (
        select(
            func.date_trunc("day", OpenAiCostDaily.bucket_start).label("day"),
            func.coalesce(func.sum(OpenAiCostDaily.amount), 0),
        )
        .where(OpenAiCostDaily.bucket_start < end)
        .group_by("day")
        .order_by("day")
    )
    if start is not None:
        trend_q = trend_q.where(OpenAiCostDaily.bucket_start >= start)
    if project_id:
        trend_q = trend_q.where(OpenAiCostDaily.project_id == project_id)
    trend_points = [
        {"date": r[0].date().isoformat() if hasattr(r[0], "date") else str(r[0])[:10],
         "openai_actual_usd": float(r[1] or 0)}
        for r in db.execute(trend_q).all()
    ]

    # --- FASHN attributed consumption (audience-scoped) ---
    fashn_filters = [FashnPredictionCost.occurred_at < end]
    if start is not None:
        fashn_filters.append(FashnPredictionCost.occurred_at >= start)
    if audience_filter is not None:
        fashn_filters.append(
            FashnPredictionCost.user_id.in_(select(User.id).where(audience_filter))
        )

    fashn_credits_actual = int(
        db.scalar(
            select(func.coalesce(func.sum(FashnPredictionCost.credits_consumed), 0)).where(
                *fashn_filters,
                FashnPredictionCost.credits_kind == CREDITS_KIND_ACTUAL,
            )
        )
        or 0
    )
    fashn_est_usd = Decimal(
        str(
            db.scalar(
                select(func.coalesce(func.sum(FashnPredictionCost.estimated_cost_usd), 0)).where(
                    *fashn_filters,
                    FashnPredictionCost.credits_kind.in_(
                        (CREDITS_KIND_ACTUAL, CREDITS_KIND_ESTIMATED_FALLBACK)
                    ),
                )
            )
            or 0
        )
    )
    fashn_unavailable = int(
        db.scalar(
            select(func.count()).select_from(FashnPredictionCost).where(
                *fashn_filters,
                FashnPredictionCost.credits_kind == CREDITS_KIND_UNAVAILABLE,
            )
        )
        or 0
    )
    fashn_ops = int(
        db.scalar(
            select(func.count()).select_from(FashnPredictionCost).where(*fashn_filters)
        )
        or 0
    )

    # By feature (FASHN estimated + OpenAI estimated ops)
    feature_rows = db.execute(
        select(
            AiProviderOperation.provider,
            AiProviderOperation.feature,
            func.count(AiProviderOperation.id),
            func.coalesce(func.sum(AiProviderOperation.estimated_cost_usd), 0),
            func.coalesce(func.sum(AiProviderOperation.credits_consumed), 0),
        )
        .where(
            AiProviderOperation.occurred_at < end,
            AiProviderOperation.final_status == "completed",
            *(
                [AiProviderOperation.occurred_at >= start]
                if start is not None
                else []
            ),
            *(
                [AiProviderOperation.user_id.in_(select(User.id).where(audience_filter))]
                if audience_filter is not None
                else []
            ),
        )
        .group_by(AiProviderOperation.provider, AiProviderOperation.feature)
        .order_by(AiProviderOperation.provider, AiProviderOperation.feature)
    ).all()
    by_feature = [
        {
            "provider": r[0],
            "feature": r[1],
            "successful_operations": int(r[2] or 0),
            "estimated_cost_usd": float(r[3] or 0),
            "credits_consumed": int(r[4] or 0) if r[0] == PROVIDER_FASHN else None,
            "cost_kind": "estimated",
        }
        for r in feature_rows
    ]

    # By classification (estimated ops only)
    class_rows = db.execute(
        select(
            User.account_classification,
            func.count(AiProviderOperation.id),
            func.coalesce(func.sum(AiProviderOperation.estimated_cost_usd), 0),
        )
        .join(User, User.id == AiProviderOperation.user_id, isouter=True)
        .where(
            AiProviderOperation.occurred_at < end,
            *(
                [AiProviderOperation.occurred_at >= start]
                if start is not None
                else []
            ),
            *(
                [AiProviderOperation.user_id.in_(select(User.id).where(audience_filter))]
                if audience_filter is not None
                else []
            ),
        )
        .group_by(User.account_classification)
    ).all()
    by_classification = [
        {
            "classification": r[0] or "UNATTRIBUTED",
            "operations": int(r[1] or 0),
            "estimated_cost_usd": float(r[2] or 0),
            "cost_kind": "estimated",
        }
        for r in class_rows
    ]

    # Operator expenses (actual cash when documented)
    exp_q = select(
        func.coalesce(func.sum(OperatorExpenseRecord.amount), 0)
    ).where(
        OperatorExpenseRecord.occurred_on < end.date(),
        OperatorExpenseRecord.kind == COST_KIND_ACTUAL,
        OperatorExpenseRecord.currency == "usd",
    )
    if start is not None:
        exp_q = exp_q.where(OperatorExpenseRecord.occurred_on >= start.date())
    operator_actual_usd = Decimal(str(db.scalar(exp_q) or 0))

    balance = latest_fashn_credit_snapshot(db)
    openai_sync = latest_sync_status(db, PROVIDER_OPENAI, "organization_costs")
    fashn_sync = latest_sync_status(db, PROVIDER_FASHN, "credits_balance")

    openai_project_block: dict[str, Any]
    if openai_has_data and project_id:
        openai_project_block = {
            "kind": "actual",
            "amount_usd": float(openai_project_amount),
            "scope_label": "FashionRise project (OpenAI Costs API)",
            "project_id_configured": True,
        }
    elif openai_has_data and not project_id:
        openai_project_block = {
            "kind": "unavailable",
            "detail": "OPENAI_BILLING_PROJECT_ID not configured — project isolation unavailable.",
            "organization_amount_usd": float(openai_org_amount),
        }
    else:
        openai_project_block = {
            "kind": "unavailable",
            "detail": (
                "No synced OpenAI costs yet. "
                + (
                    "OPENAI_COST_SYNC_ENABLED is false (default)."
                    if not openai_sync_enabled
                    else "Sync enabled but no rows persisted."
                )
            ),
        }

    alerts: list[dict[str, Any]] = []
    low_threshold = int(getattr(settings, "fashn_low_credits_threshold", 50) or 50)
    if balance is not None and int(balance["credits_total"]) <= low_threshold:
        alerts.append(
            {
                "id": "fashn.low_credits",
                "severity": "warning",
                "title": "Low FASHN credits",
                "detail": (
                    f"Remaining total credits {balance['credits_total']} "
                    f"≤ threshold {low_threshold}."
                ),
                "section": "ai",
                "scope": "global",
            }
        )
    if not openai_sync_enabled:
        alerts.append(
            {
                "id": "openai.sync_disabled",
                "severity": "info",
                "title": "OpenAI cost sync disabled",
                "detail": "OPENAI_COST_SYNC_ENABLED=false — dashboard serves persisted snapshots only.",
                "section": "ai",
                "scope": "global",
            }
        )
    elif openai_sync.get("status") in ("failed", "never_synced", "skipped_missing_credentials"):
        alerts.append(
            {
                "id": "openai.sync_stale",
                "severity": "warning",
                "title": "OpenAI cost sync not healthy",
                "detail": openai_sync.get("error_detail") or openai_sync.get("status") or "stale",
                "section": "ai",
                "scope": "global",
            }
        )
    if not fashn_sync_enabled:
        alerts.append(
            {
                "id": "fashn.sync_disabled",
                "severity": "info",
                "title": "FASHN credit sync disabled",
                "detail": "FASHN_CREDIT_SYNC_ENABLED=false — balance snapshots require activation.",
                "section": "ai",
                "scope": "global",
            }
        )
    rate, _, confirmed = active_fashn_credit_rate(db)
    if rate is None or not confirmed:
        alerts.append(
            {
                "id": "fashn.pricing_unconfirmed",
                "severity": "info",
                "title": "FASHN monetary rate is estimated",
                "detail": (
                    "Documented on-demand rate in use; operator-confirmed invoice rate not set. "
                    "Credit counts remain actual when header-captured."
                ),
                "section": "ai",
                "scope": "global",
            }
        )
    if fashn_unavailable > 0:
        alerts.append(
            {
                "id": "fashn.missing_credit_header",
                "severity": "info",
                "title": "Some FASHN predictions lack credit metadata",
                "detail": f"{fashn_unavailable} prediction(s) marked credits unavailable.",
                "section": "ai",
                "scope": "audience",
            }
        )

    return {
        "currency": "usd",
        "note": (
            "Actual = provider-reported cash (OpenAI Costs API) or operator invoice rows. "
            "Estimated = FASHN credits × versioned documented rate, or per-op soft estimates. "
            "Do not sum actual OpenAI totals with per-op OpenAI estimates. "
            "FASHN balance decreases are not treated as expenditure (top-ups/resets). "
            "Provider sync is disabled until credentials are verified."
        ),
        "sync": {
            "openai_cost_sync_enabled": openai_sync_enabled,
            "fashn_credit_sync_enabled": fashn_sync_enabled,
            "openai": openai_sync,
            "fashn": fashn_sync,
        },
        "openai": {
            "project_costs": openai_project_block,
            "organization_unattributed": {
                "kind": "actual" if openai_org_amount > 0 else "unavailable",
                "amount_usd": float(openai_org_amount) if openai_org_amount > 0 else None,
                "scope_label": "Organization-wide / unattributed (not FashionRise customers)",
                "detail": None
                if openai_org_amount > 0
                else "No organization-wide cost rows in range.",
            },
        },
        "fashn": {
            "balance": {
                "kind": "exact" if balance else "unavailable",
                "detail": None if balance else "No credit snapshot yet (sync disabled or never run).",
                **(balance or {}),
            },
            "credits_consumed_actual": {
                "kind": "exact" if fashn_ops else "unavailable",
                "value": fashn_credits_actual,
                "predictions": fashn_ops,
                "unavailable_predictions": fashn_unavailable,
                "audience_scoped": True,
                "period": "range",
            },
            "estimated_consumption_usd": {
                "kind": "estimated" if fashn_ops else "unavailable",
                "amount_usd": float(fashn_est_usd),
                "detail": "Credits × versioned documented/operator rate — not cash invoices.",
            },
            "actual_cash_expenditure": {
                "kind": "unavailable",
                "detail": (
                    "FASHN has no public historical invoice API. "
                    "Use operator_expense_records category=fashn_invoice when invoices are verified."
                ),
            },
        },
        "by_provider": [
            {
                "provider": "openai",
                "actual_usd": float(openai_project_amount)
                if project_id and openai_has_data
                else (float(openai_org_amount) if openai_has_data else None),
                "actual_kind": "actual" if openai_has_data else "unavailable",
                "estimated_usd": None,
                "scope_label": "global_provider" if not project_id else "project",
            },
            {
                "provider": "fashn",
                "actual_usd": None,
                "actual_kind": "unavailable",
                "estimated_usd": float(fashn_est_usd),
                "estimated_kind": "estimated",
                "credits_actual": fashn_credits_actual,
                "scope_label": "audience_attributed",
            },
        ],
        "by_feature": by_feature,
        "by_customer_classification": by_classification,
        "operator_expenses_actual_usd": {
            "kind": "actual" if operator_actual_usd > 0 else "unavailable",
            "amount_usd": float(operator_actual_usd) if operator_actual_usd > 0 else None,
            "detail": "Operator-entered hosting/invoice rows only.",
        },
        "daily_cost_trend": {
            "kind": "actual" if trend_points else "unavailable",
            "detail": None
            if trend_points
            else "Daily OpenAI actual series unavailable until Costs API sync populates rows.",
            "points": trend_points,
            "scope_label": "OpenAI project costs (global provider) — not audience-scoped",
        },
        "alerts": alerts,
    }


def build_income_vs_expenses(
    *,
    revenue_gross: float,
    revenue_refunds: float,
    revenue_net: float,
    ai_financial: dict[str, Any],
) -> dict[str, Any]:
    """Two reporting modes: operating consumption vs documented cash."""
    openai_project = ai_financial.get("openai", {}).get("project_costs", {})
    openai_actual = (
        float(openai_project.get("amount_usd") or 0)
        if openai_project.get("kind") == "actual"
        else None
    )
    fashn_est = ai_financial.get("fashn", {}).get("estimated_consumption_usd", {})
    fashn_est_usd = (
        float(fashn_est.get("amount_usd") or 0)
        if fashn_est.get("kind") == "estimated"
        else None
    )
    operator = ai_financial.get("operator_expenses_actual_usd", {})
    operator_usd = (
        float(operator.get("amount_usd") or 0) if operator.get("kind") == "actual" else None
    )

    operating_expenses = None
    if openai_actual is not None or fashn_est_usd is not None:
        operating_expenses = float(
            (openai_actual or 0.0) + (fashn_est_usd or 0.0)
        )

    contribution = None
    contribution_kind = "unavailable"
    if operating_expenses is not None:
        contribution = float(revenue_net) - operating_expenses
        contribution_kind = "estimated"
        # Incomplete if either leg missing.
        if openai_actual is None or fashn_est_usd is None:
            contribution_kind = "estimated_incomplete"

    cash_out = None
    if openai_actual is not None or operator_usd is not None:
        cash_out = float((openai_actual or 0.0) + (operator_usd or 0.0))

    return {
        "modes": {
            "operating_consumption": {
                "label": "Operating consumption & estimated contribution margin",
                "income": {
                    "gross_list_price_usd": {
                        "kind": "estimated",
                        "amount_usd": revenue_gross,
                    },
                    "refunds_list_price_usd": {
                        "kind": "estimated",
                        "amount_usd": revenue_refunds,
                    },
                    "net_list_price_usd": {
                        "kind": "estimated",
                        "amount_usd": revenue_net,
                    },
                    "actual_store_proceeds": {
                        "kind": "unavailable",
                        "detail": "Apple/Google net proceeds not imported.",
                    },
                },
                "expenses": {
                    "openai_recorded_costs_usd": {
                        "kind": "actual" if openai_actual is not None else "unavailable",
                        "amount_usd": openai_actual,
                    },
                    "fashn_estimated_consumption_usd": {
                        "kind": "estimated" if fashn_est_usd is not None else "unavailable",
                        "amount_usd": fashn_est_usd,
                    },
                    "fashn_actual_cash": {
                        "kind": "unavailable",
                        "detail": "No FASHN invoice API — use operator invoice rows.",
                    },
                    "total_operating_usd": {
                        "kind": "estimated" if operating_expenses is not None else "unavailable",
                        "amount_usd": operating_expenses,
                        "detail": (
                            "OpenAI actual (when synced) + FASHN estimated consumption. "
                            "Not accounting profit."
                        ),
                    },
                },
                "estimated_contribution_margin_usd": {
                    "kind": contribution_kind,
                    "amount_usd": contribution,
                    "detail": (
                        "Net estimated catalog revenue minus operating AI costs. "
                        "Not accounting profit. Incomplete when any expense leg is missing."
                    ),
                },
            },
            "documented_cash": {
                "label": "Actual cash inflows and outflows where documented",
                "income": {
                    "actual_store_proceeds": {
                        "kind": "unavailable",
                        "detail": "Apple/Google net proceeds not imported.",
                    },
                },
                "expenses": {
                    "openai_recorded_costs_usd": {
                        "kind": "actual" if openai_actual is not None else "unavailable",
                        "amount_usd": openai_actual,
                    },
                    "operator_expenses_usd": {
                        "kind": "actual" if operator_usd is not None else "unavailable",
                        "amount_usd": operator_usd,
                    },
                    "total_documented_cash_out_usd": {
                        "kind": "actual" if cash_out is not None else "unavailable",
                        "amount_usd": cash_out,
                    },
                },
                "note": (
                    "Do not mix consumption-based FASHN estimates into cash mode. "
                    "Store commissions must not be subtracted twice when using net proceeds."
                ),
            },
        },
    }


def upsert_openai_cost_rows(db: Session, rows: list[dict[str, Any]]) -> int:
    """Idempotent upsert by raw_fingerprint."""
    if not rows:
        return 0
    count = 0
    for r in rows:
        fingerprint = str(r["raw_fingerprint"])[:64]
        stmt = (
            pg_insert(OpenAiCostDaily)
            .values(
                id=uuid.uuid4(),
                bucket_start=r["bucket_start"],
                bucket_end=r["bucket_end"],
                project_id=r.get("project_id"),
                line_item=r.get("line_item"),
                currency=r.get("currency") or "usd",
                amount=r["amount"],
                quantity=r.get("quantity"),
                quantity_unit=r.get("quantity_unit"),
                scope=r.get("scope") or "organization",
                attribution=r.get("attribution") or "global",
                raw_fingerprint=fingerprint,
                synced_at=_utcnow(),
            )
            .on_conflict_do_update(
                index_elements=["raw_fingerprint"],
                set_={
                    "amount": r["amount"],
                    "quantity": r.get("quantity"),
                    "quantity_unit": r.get("quantity_unit"),
                    "synced_at": _utcnow(),
                },
            )
        )
        db.execute(stmt)
        count += 1
    db.flush()
    return count
