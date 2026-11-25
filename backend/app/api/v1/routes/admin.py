"""FashionRise Admin 2.0 console API (username allowlist + is_admin)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.admin import AdminUser
from app.db.session import get_db
from app.models.account_classification_event import ACCOUNT_CLASSIFICATIONS
from app.models.user import User
from app.services import admin_analytics

router = APIRouter()


class ClassificationBody(BaseModel):
    classification: str = Field(..., min_length=3, max_length=32)
    reason: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=2000)


@router.get("/overview")
def admin_overview(
    _admin: AdminUser,
    db: Session = Depends(get_db),
    range: str = Query(default="last_30d", alias="range"),
    audience: str = Query(default="all"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
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
    q: str | None = Query(default=None, max_length=120),
    classification: str | None = Query(default=None),
    audience: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="created_at_desc"),
) -> dict[str, Any]:
    return admin_analytics.list_customers(
        db,
        q=q,
        classification=classification,
        audience=audience,
        limit=limit,
        offset=offset,
        sort=sort,
    )


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
        )
        db.commit()
        return result
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
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    rows = admin_analytics.list_reports(db, limit=limit, status=status)
    return {"items": rows, "count": len(rows)}
