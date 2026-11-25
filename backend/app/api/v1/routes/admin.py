"""FashionRise Admin 2.0 console API (username allowlist + is_admin).

Note: do not add ``from __future__ import annotations`` here — SlowAPI's
``@limiter.limit`` wrapper + postponed annotations make FastAPI treat Body /
Depends params as query strings (and break UUID Path resolution).
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from sqlalchemy.orm import Session

from app.auth.admin import AdminUser, FinancialAdminUser
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.account_classification_event import ACCOUNT_CLASSIFICATIONS
from app.models.admin_stars_grant import ADMIN_GRANT_REASONS
from app.models.user import User
from app.services import admin_analytics, admin_stars_grants
from app.services.admin_analytics import ConflictClassificationError

router = APIRouter()


class ClassificationBody(BaseModel):
    classification: str = Field(..., min_length=3, max_length=32)
    reason: str = Field(..., min_length=3, max_length=500)
    note: Optional[str] = Field(default=None, max_length=2000)
    expected_classification: Optional[str] = Field(default=None, max_length=32)
    expected_updated_at: Optional[str] = Field(default=None, max_length=64)


class StarsGrantBody(BaseModel):
    """ADD-ONLY Stars grant. Rejects unexpected financial fields.

    Only a strictly positive ``amount`` to add is accepted — never target /
    replacement balances, signed deltas, or client-supplied actor identity.
    """

    model_config = ConfigDict(extra="forbid")

    amount: StrictInt = Field(..., description="Strictly positive Stars to ADD")
    reason: str = Field(..., min_length=3, max_length=64)
    note: Optional[str] = Field(default=None, max_length=2000)
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    confirm_large: bool = Field(
        default=False,
        description="Required when amount >= large-confirm threshold",
    )

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("amount must be a strictly positive integer")
        return value

    @field_validator("reason")
    @classmethod
    def reason_known(cls, value: str) -> str:
        normalized = (value or "").strip().upper()
        if normalized not in ADMIN_GRANT_REASONS:
            raise ValueError(f"reason must be one of: {', '.join(ADMIN_GRANT_REASONS)}")
        return normalized


@router.get("/overview")
def admin_overview(
    _admin: AdminUser,
    db: Session = Depends(get_db),
    range: str = Query(default="last_30d", alias="range"),
    audience: str = Query(default="customers"),
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
) -> dict[str, Any]:
    try:
        return admin_analytics.overview(
            db, range_key=range, audience=audience, start=start, end=end
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/metrics/dictionary")
def admin_metric_dictionary(_admin: AdminUser) -> dict[str, Any]:
    return {"items": admin_analytics.metric_dictionary()}


@router.get("/customers")
def admin_customers(
    _admin: AdminUser,
    db: Session = Depends(get_db),
    q: Optional[str] = Query(default=None, max_length=120),
    classification: Optional[str] = Query(default=None),
    audience: str = Query(default="all"),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="created_at_desc"),
) -> dict[str, Any]:
    try:
        return admin_analytics.list_customers(
            db,
            q=q,
            classification=classification,
            audience=audience,
            limit=limit,
            offset=offset,
            sort=sort,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/customers/{user_id}")
def admin_customer_detail(
    user_id: uuid.UUID,
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    detail = admin_analytics.customer_detail(db, user_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return detail


@router.patch("/customers/{user_id}/classification")
def admin_set_classification(
    user_id: uuid.UUID,
    body: ClassificationBody,
    admin: AdminUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        result = admin_analytics.set_classification(
            db,
            target=target,
            actor=admin,
            to_classification=body.classification,
            reason=body.reason,
            note=body.note,
            expected_classification=body.expected_classification,
            expected_updated_at=body.expected_updated_at,
        )
        db.commit()
        return result
    except ConflictClassificationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/classification/dry-run")
def admin_classification_dry_run(
    _admin: AdminUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    return admin_analytics.classification_dry_run(db, limit=limit)


@router.get("/classification/options")
def admin_classification_options(_admin: AdminUser) -> dict[str, Any]:
    return {"items": list(ACCOUNT_CLASSIFICATIONS)}


@router.get("/reports")
def admin_reports(
    _admin: AdminUser,
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    rows = admin_analytics.list_reports(db, limit=limit, status=status_filter)
    return {"items": rows, "count": len(rows)}


@router.get("/stars/grants/config")
def admin_stars_grants_config(_admin: AdminUser) -> dict[str, Any]:
    """Expose effective grant limits so FE stays consistent with the server."""
    return admin_stars_grants.grant_limits_payload()


@router.get("/stars/grants")
def admin_stars_grants_overview(
    _admin: AdminUser,
    db: Session = Depends(get_db),
    range: str = Query(default="last_30d", alias="range"),
    audience: str = Query(default="customers"),
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
) -> dict[str, Any]:
    """Stars Grants history aggregates — never folded into purchase revenue."""
    try:
        range_start, range_end, range_label = admin_analytics.resolve_range(
            range, start=start, end=end
        )
        stats = admin_stars_grants.grants_overview(
            db, start=range_start, end=range_end, audience=audience
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "range": {
            "key": range_label,
            "start": range_start.isoformat() if range_start else None,
            "end": range_end.isoformat(),
        },
        **stats,
    }


@router.get("/users/{user_id}/stars/grants")
def admin_user_stars_grants(
    user_id: uuid.UUID,
    _admin: AdminUser,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    items = admin_stars_grants.list_grants_for_user(db, user_id, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/users/{user_id}/stars/grants", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute;100/hour")
def admin_grant_stars(
    request: Request,
    user_id: uuid.UUID,
    body: StarsGrantBody,
    admin: FinancialAdminUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """ADD-ONLY Stars grant. Actor identity is derived from the session — never the body."""
    _ = request  # SlowAPI keys on Request
    try:
        result = admin_stars_grants.grant_stars(
            db,
            actor=admin,
            recipient_id=user_id,
            amount=body.amount,
            reason=body.reason,
            note=body.note,
            idempotency_key=body.idempotency_key,
            confirm_large=body.confirm_large,
        )
        db.commit()
        return result
    except AppError:
        # grant_stars uses SAVEPOINT for credit+ledger atomicity. Do not
        # session.rollback() here — that would unwind the ambient transaction.
        db.expire_all()
        raise
    except Exception:
        db.rollback()
        raise
