"""Web-only FashionRise admin console API (username allowlist)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.admin import AdminUser
from app.db.session import get_db
from app.services import admin_analytics

router = APIRouter()


@router.get("/overview")
def admin_overview(
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return admin_analytics.overview(db)


@router.get("/reports")
def admin_reports(
    _admin: AdminUser,
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    rows = admin_analytics.list_reports(db, limit=limit, status=status)
    return {"items": rows, "count": len(rows)}
