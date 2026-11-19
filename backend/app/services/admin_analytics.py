"""Aggregate FashionRise product metrics for the web admin console."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.ai_job import AIJob
from app.models.content_report import ContentReport
from app.models.fabric_asset import FabricAsset
from app.models.gallery_comment import GalleryComment
from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.garment_design import GarmentDesign
from app.models.iap_purchase import (
    STATUS_ACTIVE,
    STATUS_REFUND_REVERSED,
    STATUS_REFUNDED,
    STATUS_REVOKED,
    IapPurchase,
)
from app.models.personal_croquis import PersonalCroquis
from app.models.user import User
from app.models.user_follow import UserFollow
from app.services import ai_stars
from app.services.iap_service import STARS_PRODUCTS

# Launch ASC / Play list prices (USD) — keep in sync with iap_service comment.
_PRODUCT_USD: dict[str, Decimal] = {
    "stars_50": Decimal("5.99"),
    "stars_150": Decimal("16.99"),
    "stars_500": Decimal("49.99"),
}

_JOB_FEATURE: dict[str, str] = {
    "sketch_polish": "magic",
    "personal_try_on": "magic",
    "fitting_room_try_on": "fitting_room",
    "personal_croquis_generate": "croquis",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def overview(db: Session) -> dict[str, Any]:
    now = _utc_now()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    users_total = _count(db, select(func.count()).select_from(User))
    users_active = _count(
        db, select(func.count()).select_from(User).where(User.is_active.is_(True))
    )
    users_new_7d = _count(
        db, select(func.count()).select_from(User).where(User.created_at >= week_ago)
    )
    users_new_30d = _count(
        db, select(func.count()).select_from(User).where(User.created_at >= month_ago)
    )

    designs_total = _count(db, select(func.count()).select_from(GarmentDesign))
    designs_published = _count(
        db,
        select(func.count())
        .select_from(GalleryItem)
        .where(GalleryItem.design_id.is_not(None)),
    )
    looks_published = _count(
        db,
        select(func.count())
        .select_from(GalleryItem)
        .where(GalleryItem.look_id.is_not(None)),
    )
    gallery_public = _count(
        db,
        select(func.count())
        .select_from(GalleryItem)
        .where(GalleryItem.visibility == "public"),
    )

    models_created = _count(db, select(func.count()).select_from(PersonalCroquis))
    models_accepted = _count(
        db,
        select(func.count())
        .select_from(PersonalCroquis)
        .where(PersonalCroquis.status == "uploaded"),
    )

    ai_fabrics = _count(
        db,
        select(func.count())
        .select_from(FabricAsset)
        .where(FabricAsset.source == "ai", FabricAsset.deleted_at.is_(None)),
    )
    uploaded_fabrics = _count(
        db,
        select(func.count())
        .select_from(FabricAsset)
        .where(FabricAsset.source != "ai", FabricAsset.deleted_at.is_(None)),
    )

    fitting_room_done = _count(
        db,
        select(func.count())
        .select_from(AIJob)
        .where(
            AIJob.job_type == "fitting_room_try_on",
            AIJob.status == "succeeded",
        ),
    )
    fitting_room_7d = _count(
        db,
        select(func.count())
        .select_from(AIJob)
        .where(
            AIJob.job_type == "fitting_room_try_on",
            AIJob.status == "succeeded",
            AIJob.created_at >= week_ago,
        ),
    )
    magic_done = _count(
        db,
        select(func.count())
        .select_from(AIJob)
        .where(AIJob.job_type == "sketch_polish", AIJob.status == "succeeded"),
    )
    try_on_done = _count(
        db,
        select(func.count())
        .select_from(AIJob)
        .where(AIJob.job_type == "personal_try_on", AIJob.status == "succeeded"),
    )

    likes_total = _count(db, select(func.count()).select_from(GalleryLike))
    comments_total = _count(db, select(func.count()).select_from(GalleryComment))
    follows_total = _count(db, select(func.count()).select_from(UserFollow))

    reports_open = _count(
        db,
        select(func.count())
        .select_from(ContentReport)
        .where(ContentReport.status == "open"),
    )
    reports_total = _count(db, select(func.count()).select_from(ContentReport))

    # Stars purchased / money earned — Production App Store / Play only.
    # Exclude Sandbox / TestFlight / Xcode buys (not real customer money).
    _SANDBOX_ENVS = frozenset({"sandbox", "xcode", "localtesting", "test"})
    purchase_rows = db.execute(
        select(
            IapPurchase.product_id,
            IapPurchase.stars_credited,
            IapPurchase.stars_clawed_back,
            IapPurchase.status,
            IapPurchase.platform,
            IapPurchase.environment,
        ).where(
            IapPurchase.status.in_(
                (STATUS_ACTIVE, STATUS_REFUND_REVERSED, STATUS_REFUNDED, STATUS_REVOKED)
            )
        )
    ).all()

    stars_bought = 0
    stars_clawed = 0
    revenue_usd = Decimal("0.00")
    purchases_count = 0
    sandbox_excluded = 0
    for product_id, credited, clawed, status, _platform, environment in purchase_rows:
        env = (environment or "").strip().lower()
        if env in _SANDBOX_ENVS or env.startswith("sandbox"):
            sandbox_excluded += 1
            continue
        credited_i = int(credited or 0)
        clawed_i = int(clawed or 0)
        if status in (STATUS_ACTIVE, STATUS_REFUND_REVERSED):
            net = max(0, credited_i - clawed_i)
            stars_bought += net
            purchases_count += 1
            unit = _PRODUCT_USD.get(str(product_id or ""), Decimal("0"))
            # Approximate: one purchase row ≈ one unit at list price when net > 0.
            if net > 0 and unit > 0:
                revenue_usd += unit
        else:
            stars_clawed += clawed_i

    # Estimate Stars spent from successful AI jobs that settled a debit.
    spent_by_feature: dict[str, int] = {
        "magic": 0,
        "croquis": 0,
        "fitting_room": 0,
        "fabric": 0,
        "pdf": 0,
        "other": 0,
    }
    debited_jobs = db.execute(
        select(AIJob.job_type, func.count())
        .where(
            AIJob.status == "succeeded",
            AIJob.result_data.contains({"stars_debited": True}),
        )
        .group_by(AIJob.job_type)
    ).all()
    stars_spent = 0
    for job_type, cnt in debited_jobs:
        feature = _JOB_FEATURE.get(str(job_type or ""), "other")
        cost = ai_stars.feature_cost(feature) if feature != "other" else 0
        # AI fabric creates may not always use a dedicated job_type — count via fabrics below.
        total = int(cnt or 0) * max(0, cost)
        spent_by_feature[feature] = spent_by_feature.get(feature, 0) + total
        stars_spent += total

    # Fabric AI creates are billed at fabric cost when source=ai.
    fabric_spend = ai_fabrics * ai_stars.feature_cost("fabric")
    spent_by_feature["fabric"] = spent_by_feature.get("fabric", 0) + fabric_spend
    stars_spent += fabric_spend

    starting = ai_stars.starting_balance()
    free_granted = users_total * starting
    # Free consumption ≈ spent that could come from grants before purchases exhaust.
    # Cap at free grants issued; remainder of spend is treated as paid-pool usage.
    free_stars_consumed = min(stars_spent, free_granted)
    paid_stars_consumed = max(0, stars_spent - free_stars_consumed)

    wallet_sum = int(
        db.scalar(
            select(func.coalesce(func.sum(User.ai_stars), 0)).where(
                User.ai_stars_unlimited.is_(False)
            )
        )
        or 0
    )

    recent_signups = [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "ai_stars": int(u.ai_stars or 0),
        }
        for u in db.scalars(
            select(User).order_by(User.created_at.desc()).limit(12)
        ).all()
    ]

    return {
        "generated_at": now.isoformat(),
        "users": {
            "total": users_total,
            "active": users_active,
            "new_7d": users_new_7d,
            "new_30d": users_new_30d,
        },
        "content": {
            "designs_saved": designs_total,
            "designs_published": designs_published,
            "looks_published": looks_published,
            "gallery_public": gallery_public,
            "models_created": models_created,
            "models_ready": models_accepted,
            "ai_fabrics_created": ai_fabrics,
            "uploaded_fabrics": uploaded_fabrics,
            "likes": likes_total,
            "comments": comments_total,
            "follows": follows_total,
        },
        "ai_usage": {
            "fitting_room_completed": fitting_room_done,
            "fitting_room_7d": fitting_room_7d,
            "magic_completed": magic_done,
            "try_on_completed": try_on_done,
            "jobs_last_24h": _count(
                db,
                select(func.count())
                .select_from(AIJob)
                .where(AIJob.created_at >= day_ago),
            ),
        },
        "stars": {
            "starting_grant_per_user": starting,
            "free_grants_issued": free_granted,
            "free_stars_consumed_est": free_stars_consumed,
            "paid_stars_consumed_est": paid_stars_consumed,
            "stars_spent_total_est": stars_spent,
            "spent_by_feature_est": spent_by_feature,
            "stars_purchased_net": stars_bought,
            "stars_clawed_back": stars_clawed,
            "wallet_balance_sum": wallet_sum,
            "costs": ai_stars.cost_catalog(),
        },
        "revenue": {
            "currency": "USD",
            "gross_list_price_usd": float(revenue_usd),
            "purchases_counted": purchases_count,
            "sandbox_purchases_excluded": sandbox_excluded,
            "note": (
                "Production purchases only (Sandbox / TestFlight excluded). "
                "Estimated from App Store / Play list prices "
                f"({', '.join(f'{k}=${v}' for k, v in _PRODUCT_USD.items())}). "
                "Not Apple/Google net proceeds."
            ),
            "product_catalog": [
                {"product_id": pid, "stars": stars, "list_price_usd": float(_PRODUCT_USD.get(pid, 0))}
                for pid, stars in STARS_PRODUCTS.items()
            ],
        },
        "moderation": {
            "reports_open": reports_open,
            "reports_total": reports_total,
        },
        "recent_signups": recent_signups,
    }


def list_reports(db: Session, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 200))
    stmt = (
        select(ContentReport)
        .options(
            joinedload(ContentReport.reporter),
            joinedload(ContentReport.reported_user),
            joinedload(ContentReport.gallery_item),
        )
        .order_by(ContentReport.created_at.desc())
        .limit(lim)
    )
    if status:
        stmt = stmt.where(ContentReport.status == status)
    rows = db.scalars(stmt).unique().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        item = r.gallery_item
        out.append(
            {
                "id": str(r.id),
                "status": r.status,
                "reason": r.reason,
                "details": r.details,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "reporter": {
                    "id": str(r.reporter_id),
                    "username": getattr(r.reporter, "username", None),
                },
                "reported_user": {
                    "id": str(r.reported_user_id),
                    "username": getattr(r.reported_user, "username", None),
                },
                "gallery_item": {
                    "id": str(r.gallery_item_id),
                    "title": getattr(item, "title", None) if item else None,
                    "image_url": getattr(item, "image_url", None) if item else None,
                    "moderation_status": getattr(item, "moderation_status", None)
                    if item
                    else None,
                },
            }
        )
    return out
