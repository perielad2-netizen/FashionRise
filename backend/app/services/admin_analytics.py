"""FashionRise Admin 2.0 aggregate metrics and customer operations.

Metric calculations are centralized here so Overview / Customers / Revenue /
AI Costs stay consistent. Values are labeled exact | estimated | unavailable.

Critical fix (Admin 1.0): AI jobs persist success as status ``completed``,
not ``succeeded``. Counting ``succeeded`` under-reported Magic / Fitting Room.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.auth.admin import ADMIN_USERNAMES, user_is_admin
from app.models.account_classification_event import (
    ACCOUNT_CLASSIFICATIONS,
    AccountClassificationEvent,
)
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

# Launch ASC / Play list prices (USD) — catalog estimates, not storefront FX.
_PRODUCT_USD: dict[str, Decimal] = {
    "stars_50": Decimal("5.99"),
    "stars_150": Decimal("16.99"),
    "stars_500": Decimal("49.99"),
}

# Workers mark success as "completed" (never "succeeded").
_JOB_SUCCESS = "completed"

_JOB_FEATURE: dict[str, str] = {
    "sketch_polish": "magic",
    "sketch_clean": "magic",
    "personal_try_on": "try_on",
    "personal_garment_realism": "try_on",
    "fitting_room_try_on": "fitting_room",
    "personal_croquis_generate": "croquis",
}

_SANDBOX_ENVS = frozenset({"sandbox", "xcode", "localtesting", "test"})

_INTERNAL_CLASS = frozenset(
    {"OWNER", "ADMIN", "INTERNAL_TESTER", "QA_AUTOMATION", "DEMO_ACCOUNT"}
)

Audience = Literal[
    "all",
    "customers",
    "internal",
    "unclassified",
    "CUSTOMER",
    "OWNER",
    "ADMIN",
    "INTERNAL_TESTER",
    "QA_AUTOMATION",
    "DEMO_ACCOUNT",
    "UNCLASSIFIED",
]

RangeKey = Literal[
    "today",
    "yesterday",
    "last_7d",
    "last_30d",
    "last_90d",
    "this_month",
    "last_month",
    "all_time",
    "custom",
]

_JERUSALEM = ZoneInfo("Asia/Jerusalem")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def resolve_range(
    key: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime, str]:
    """Return (range_start_utc inclusive, range_end_utc exclusive, label).

    Day/month boundaries use Asia/Jerusalem calendar days, then convert to UTC.
    ``all_time`` returns start=None.
    """
    now = now or _utc_now()
    local = now.astimezone(_JERUSALEM)
    today_local = local.replace(hour=0, minute=0, second=0, microsecond=0)

    def to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_JERUSALEM)
        return dt.astimezone(timezone.utc)

    k = (key or "last_30d").strip().lower()
    if k == "custom":
        if start is None or end is None:
            raise ValueError("custom range requires start and end")
        s = to_utc(start)
        e = to_utc(end)
        if e <= s:
            raise ValueError("end must be after start")
        return s, e, "custom"

    if k == "all_time":
        return None, now, "all_time"
    if k == "today":
        s = to_utc(today_local)
        e = to_utc(today_local + timedelta(days=1))
        return s, e, "today"
    if k == "yesterday":
        s = to_utc(today_local - timedelta(days=1))
        e = to_utc(today_local)
        return s, e, "yesterday"
    if k == "last_7d":
        e = to_utc(today_local + timedelta(days=1))
        s = to_utc(today_local - timedelta(days=6))
        return s, e, "last_7d"
    if k == "last_30d":
        e = to_utc(today_local + timedelta(days=1))
        s = to_utc(today_local - timedelta(days=29))
        return s, e, "last_30d"
    if k == "last_90d":
        e = to_utc(today_local + timedelta(days=1))
        s = to_utc(today_local - timedelta(days=89))
        return s, e, "last_90d"
    if k == "this_month":
        month_start = today_local.replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        return to_utc(month_start), to_utc(next_month), "this_month"
    if k == "last_month":
        month_start = today_local.replace(day=1)
        if month_start.month == 1:
            prev = month_start.replace(year=month_start.year - 1, month=12)
        else:
            prev = month_start.replace(month=month_start.month - 1)
        return to_utc(prev), to_utc(month_start), "last_month"
    # default last_30d
    e = to_utc(today_local + timedelta(days=1))
    s = to_utc(today_local - timedelta(days=29))
    return s, e, "last_30d"


def _classification_of(user: User) -> str:
    raw = (getattr(user, "account_classification", None) or "UNCLASSIFIED").strip().upper()
    if raw not in ACCOUNT_CLASSIFICATIONS:
        return "UNCLASSIFIED"
    return raw


def _audience_filter(audience: str):
    """SQLAlchemy filter on User.account_classification for audience mode."""
    a = (audience or "all").strip()
    if a in ("", "all"):
        return None
    if a == "customers":
        return User.account_classification == "CUSTOMER"
    if a == "internal":
        return User.account_classification.in_(tuple(_INTERNAL_CLASS))
    if a == "unclassified":
        return User.account_classification == "UNCLASSIFIED"
    if a in ACCOUNT_CLASSIFICATIONS:
        return User.account_classification == a
    return None


def suggest_classification(user: User) -> dict[str, Any]:
    """Non-authoritative heuristic suggestion (never silent write)."""
    name = (user.username or "").strip().lower()
    if name in ADMIN_USERNAMES or user_is_admin(user):
        return {
            "suggested": "OWNER" if name in {"perishilat", "shilatperi", "yanivprbk"} else "ADMIN",
            "confidence": "high",
            "evidence": ["admin_username_allowlist_or_is_admin"],
        }
    if bool(getattr(user, "ai_stars_unlimited", False)) or ai_stars.user_has_unlimited_stars(
        user
    ):
        return {
            "suggested": "OWNER",
            "confidence": "medium",
            "evidence": ["unlimited_stars_wallet"],
        }
    email = (user.email or "").lower()
    if email.endswith("@example.com") or email.endswith(".test"):
        return {
            "suggested": "QA_AUTOMATION",
            "confidence": "medium",
            "evidence": ["example_or_test_email_domain"],
        }
    return {
        "suggested": "UNCLASSIFIED",
        "confidence": "none",
        "evidence": [],
    }


def metric_dictionary() -> list[dict[str, Any]]:
    return [
        {
            "id": "users.total",
            "name": "Total accounts",
            "definition": "Count of rows in users.",
            "source": "users",
            "kind": "exact",
            "audience_default": "all",
            "limitations": "Includes internal/test/unclassified unless filtered.",
        },
        {
            "id": "ai.magic_completed",
            "name": "Magic completed",
            "definition": "AIJob rows with job_type in (sketch_polish, sketch_clean) and status=completed.",
            "source": "ai_jobs",
            "kind": "exact",
            "coverage_note": "Admin 1.0 incorrectly filtered status=succeeded (always 0).",
            "limitations": "Dual Magic creates two sketch_polish jobs.",
        },
        {
            "id": "ai.fitting_room_completed",
            "name": "Fitting Room completed",
            "definition": "AIJob job_type=fitting_room_try_on and status=completed.",
            "source": "ai_jobs",
            "kind": "exact",
            "coverage_note": "Admin 1.0 incorrectly filtered status=succeeded (always 0).",
        },
        {
            "id": "ai.try_on_completed",
            "name": "Try-On completed",
            "definition": "AIJob job_type in (personal_try_on, personal_garment_realism) status=completed.",
            "source": "ai_jobs",
            "kind": "exact",
            "limitations": "personal_garment_realism is an intermediate realism step.",
        },
        {
            "id": "revenue.gross_list_price_usd",
            "name": "Gross production purchase revenue (list)",
            "definition": "Sum of ASC/Play catalog USD list prices for production IAP rows with net Stars > 0.",
            "source": "iap_purchases",
            "kind": "estimated",
            "limitations": "Not Apple/Google net proceeds; not storefront FX; sandbox excluded.",
        },
        {
            "id": "stars.spent_total_est",
            "name": "Stars spent (estimated)",
            "definition": "Succeeded AI jobs with stars_debited × feature cost + AI fabric count × fabric cost.",
            "source": "ai_jobs + fabric_assets",
            "kind": "estimated",
            "limitations": "Techpack PDF spend on TechpackAIRun not yet included; unlimited accounts may not debit.",
        },
        {
            "id": "content.models_ready",
            "name": "Models ready (uploaded parent)",
            "definition": "PersonalCroquis.status == uploaded (photo uploaded), not version accepted.",
            "source": "personal_croquis",
            "kind": "exact",
            "limitations": "Does not equal accepted AI model versions.",
        },
        {
            "id": "acquisition.platform",
            "name": "Registration platform",
            "definition": "Unavailable — no authoritative first-platform field on users.",
            "source": None,
            "kind": "unavailable",
            "limitations": "Requires new instrumentation; do not infer from UA alone.",
        },
        {
            "id": "acquisition.country",
            "name": "Customer country",
            "definition": "Unavailable — no authoritative residence field.",
            "source": None,
            "kind": "unavailable",
            "limitations": "Do not infer from email/name/IP as confirmed residence.",
        },
        {
            "id": "retention.d7",
            "name": "D7 retention",
            "definition": "Unavailable — no versioned analytics event store for meaningful activity days.",
            "source": None,
            "kind": "unavailable",
            "limitations": "Phase C / instrumentation required.",
        },
    ]


def _job_success_count(
    db: Session,
    *,
    job_types: tuple[str, ...],
    start: datetime | None,
    end: datetime,
) -> int:
    stmt = (
        select(func.count())
        .select_from(AIJob)
        .where(AIJob.job_type.in_(job_types), AIJob.status == _JOB_SUCCESS)
    )
    if start is not None:
        stmt = stmt.where(AIJob.created_at >= start)
    stmt = stmt.where(AIJob.created_at < end)
    return _count(db, stmt)


def _user_ids_for_audience(db: Session, audience: str) -> list[uuid.UUID] | None:
    filt = _audience_filter(audience)
    if filt is None:
        return None
    return list(db.scalars(select(User.id).where(filt)).all())


def overview(
    db: Session,
    *,
    range_key: str = "last_30d",
    audience: str = "all",
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    range_start, range_end, range_label = resolve_range(
        range_key, start=start, end=end, now=now
    )
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)

    audience_filt = _audience_filter(audience)
    user_base = select(func.count()).select_from(User)
    if audience_filt is not None:
        user_base = user_base.where(audience_filt)

    users_total = _count(db, user_base)
    active_stmt = select(func.count()).select_from(User).where(User.is_active.is_(True))
    if audience_filt is not None:
        active_stmt = active_stmt.where(audience_filt)
    users_active = _count(db, active_stmt)

    def _new_users_since(since: datetime) -> int:
        stmt = select(func.count()).select_from(User).where(User.created_at >= since)
        if audience_filt is not None:
            stmt = stmt.where(audience_filt)
        return _count(db, stmt)

    users_new_7d = _new_users_since(week_ago)
    users_new_30d = _new_users_since(now - timedelta(days=30))
    users_new_in_range = _count(
        db,
        select(func.count())
        .select_from(User)
        .where(
            *((User.created_at >= range_start,) if range_start is not None else ()),
            User.created_at < range_end,
            *((audience_filt,) if audience_filt is not None else ()),
        ),
    )

    class_counts = {
        c: _count(
            db,
            select(func.count())
            .select_from(User)
            .where(User.account_classification == c),
        )
        for c in ACCOUNT_CLASSIFICATIONS
    }

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

    # Corrected AI success status.
    magic_done = _job_success_count(
        db, job_types=("sketch_polish", "sketch_clean"), start=None, end=now + timedelta(seconds=1)
    )
    fitting_room_done = _job_success_count(
        db, job_types=("fitting_room_try_on",), start=None, end=now + timedelta(seconds=1)
    )
    fitting_room_7d = _job_success_count(
        db, job_types=("fitting_room_try_on",), start=week_ago, end=now + timedelta(seconds=1)
    )
    try_on_done = _job_success_count(
        db,
        job_types=("personal_try_on", "personal_garment_realism"),
        start=None,
        end=now + timedelta(seconds=1),
    )
    magic_in_range = _job_success_count(
        db,
        job_types=("sketch_polish", "sketch_clean"),
        start=range_start,
        end=range_end,
    )
    fitting_in_range = _job_success_count(
        db, job_types=("fitting_room_try_on",), start=range_start, end=range_end
    )

    jobs_last_24h = _count(
        db,
        select(func.count()).select_from(AIJob).where(AIJob.created_at >= day_ago),
    )
    jobs_pending = _count(
        db,
        select(func.count())
        .select_from(AIJob)
        .where(AIJob.status.in_(("queued", "running", "pending"))),
    )
    jobs_failed = _count(
        db,
        select(func.count()).select_from(AIJob).where(AIJob.status == "failed"),
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
            if net > 0 and unit > 0:
                revenue_usd += unit
        else:
            stars_clawed += clawed_i

    spent_by_feature: dict[str, int] = {
        "magic": 0,
        "croquis": 0,
        "fitting_room": 0,
        "try_on": 0,
        "fabric": 0,
        "pdf": 0,
        "other": 0,
    }
    debited_jobs = db.execute(
        select(AIJob.job_type, func.count())
        .where(
            AIJob.status == _JOB_SUCCESS,
            AIJob.result_data.contains({"stars_debited": True}),
        )
        .group_by(AIJob.job_type)
    ).all()
    stars_spent = 0
    for job_type, cnt in debited_jobs:
        feature = _JOB_FEATURE.get(str(job_type or ""), "other")
        cost_key = "magic" if feature == "try_on" else feature
        # try_on billed as fitting_room cost when separate; personal try-on uses magic-like costs
        if feature == "try_on":
            cost = ai_stars.feature_cost("fitting_room")
        elif feature == "other":
            cost = 0
        else:
            cost = ai_stars.feature_cost(cost_key)  # type: ignore[arg-type]
        total = int(cnt or 0) * max(0, cost)
        spent_by_feature[feature] = spent_by_feature.get(feature, 0) + total
        stars_spent += total

    fabric_spend = ai_fabrics * ai_stars.feature_cost("fabric")
    spent_by_feature["fabric"] = spent_by_feature.get("fabric", 0) + fabric_spend
    stars_spent += fabric_spend

    starting = ai_stars.starting_balance()
    free_granted = users_total * starting
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
    unlimited_wallets = _count(
        db,
        select(func.count()).select_from(User).where(User.ai_stars_unlimited.is_(True)),
    )

    recent_signups = [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "ai_stars": int(u.ai_stars or 0),
            "classification": _classification_of(u),
            "suggestion": suggest_classification(u),
        }
        for u in db.scalars(select(User).order_by(User.created_at.desc()).limit(12)).all()
    ]

    needs_attention: list[dict[str, Any]] = []
    if class_counts.get("UNCLASSIFIED", 0) > 0:
        needs_attention.append(
            {
                "id": "unclassified_accounts",
                "severity": "medium",
                "title": f"{class_counts['UNCLASSIFIED']} unclassified accounts",
                "detail": "Review classification before treating analytics as confirmed customers.",
                "section": "customers",
            }
        )
    if reports_open > 0:
        needs_attention.append(
            {
                "id": "open_reports",
                "severity": "high",
                "title": f"{reports_open} open moderation reports",
                "detail": "Review Community & Moderation queue.",
                "section": "community",
            }
        )
    if jobs_pending > 20:
        needs_attention.append(
            {
                "id": "pending_jobs",
                "severity": "medium",
                "title": f"{jobs_pending} pending AI jobs",
                "detail": "Queue depth elevated relative to quiet baseline.",
                "section": "system",
            }
        )
    if jobs_failed > 0 and jobs_last_24h > 0:
        needs_attention.append(
            {
                "id": "failed_jobs",
                "severity": "medium",
                "title": f"{jobs_failed} failed AI jobs (lifetime counter)",
                "detail": "Inspect AI & Costs for failure patterns.",
                "section": "ai",
            }
        )

    return {
        "generated_at": now.isoformat(),
        "timezone_reporting": "Asia/Jerusalem",
        "range": {
            "key": range_label,
            "start": range_start.isoformat() if range_start else None,
            "end": range_end.isoformat(),
        },
        "audience": audience,
        "classification_counts": class_counts,
        "users": {
            "total": users_total,
            "active": users_active,
            "new_7d": users_new_7d,
            "new_30d": users_new_30d,
            "new_in_range": users_new_in_range,
            "confirmed_customers": class_counts.get("CUSTOMER", 0),
            "unclassified": class_counts.get("UNCLASSIFIED", 0),
            "internal": sum(class_counts.get(c, 0) for c in _INTERNAL_CLASS),
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
            "fitting_room_in_range": fitting_in_range,
            "magic_completed": magic_done,
            "magic_in_range": magic_in_range,
            "try_on_completed": try_on_done,
            "jobs_last_24h": jobs_last_24h,
            "jobs_pending": jobs_pending,
            "jobs_failed": jobs_failed,
            "status_semantics": "completed",
            "note": (
                "Success = AIJob.status 'completed' (workers). "
                "Admin 1.0 used 'succeeded' and under-counted Magic/Fitting Room."
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
            "unlimited_wallets": unlimited_wallets,
            "costs": ai_stars.cost_catalog(),
            "admin_grants": {
                "kind": "unavailable",
                "detail": "No durable admin-grant ledger yet; balance-only gifts are not separately tagged.",
            },
        },
        "revenue": {
            "currency": "USD",
            "gross_list_price_usd": float(revenue_usd),
            "purchases_counted": purchases_count,
            "sandbox_purchases_excluded": sandbox_excluded,
            "kind": "estimated",
            "note": (
                "Production purchases only (Sandbox / TestFlight excluded). "
                "Estimated from App Store / Play list prices "
                f"({', '.join(f'{k}=${v}' for k, v in _PRODUCT_USD.items())}). "
                "Not Apple/Google net proceeds."
            ),
            "product_catalog": [
                {
                    "product_id": pid,
                    "stars": stars,
                    "list_price_usd": float(_PRODUCT_USD.get(pid, 0)),
                }
                for pid, stars in STARS_PRODUCTS.items()
            ],
        },
        "moderation": {
            "reports_open": reports_open,
            "reports_total": reports_total,
        },
        "needs_attention": needs_attention,
        "unavailable": [
            "acquisition.platform",
            "acquisition.country",
            "retention.d7",
            "external.app_store_downloads_live",
            "ai.provider_actual_billing",
        ],
        "recent_signups": recent_signups,
    }


def list_customers(
    db: Session,
    *,
    q: str | None = None,
    classification: str | None = None,
    audience: str = "all",
    limit: int = 50,
    offset: int = 0,
    sort: str = "created_at_desc",
) -> dict[str, Any]:
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    filt = _audience_filter(audience if not classification else classification)
    if classification and classification in ACCOUNT_CLASSIFICATIONS:
        filt = User.account_classification == classification
    if filt is not None:
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)

    if q:
        like = f"%{q.strip().lower()}%"
        cond = or_(
            func.lower(User.username).like(like),
            func.lower(User.email).like(like),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    if sort == "stars_desc":
        stmt = stmt.order_by(User.ai_stars.desc(), User.created_at.desc())
    elif sort == "username_asc":
        stmt = stmt.order_by(func.lower(User.username).asc())
    else:
        stmt = stmt.order_by(User.created_at.desc())

    total = _count(db, count_stmt)
    rows = db.scalars(stmt.offset(off).limit(lim)).all()
    items = []
    for u in rows:
        items.append(
            {
                "id": str(u.id),
                "username": u.username,
                "email": u.email,
                "is_active": bool(u.is_active),
                "is_admin": bool(u.is_admin),
                "classification": _classification_of(u),
                "classification_note": getattr(u, "account_classification_note", None),
                "ai_stars": int(u.ai_stars or 0),
                "ai_stars_unlimited": bool(getattr(u, "ai_stars_unlimited", False)),
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "suggestion": suggest_classification(u),
            }
        )
    return {"items": items, "total": total, "limit": lim, "offset": off}


def customer_detail(db: Session, user_id: uuid.UUID) -> dict[str, Any] | None:
    user = db.get(User, user_id)
    if user is None:
        return None

    designs = _count(
        db, select(func.count()).select_from(GarmentDesign).where(GarmentDesign.user_id == user.id)
    )
    models = _count(
        db,
        select(func.count())
        .select_from(PersonalCroquis)
        .where(PersonalCroquis.owner_id == user.id),
    )
    magic = _count(
        db,
        select(func.count())
        .select_from(AIJob)
        .where(
            AIJob.user_id == user.id,
            AIJob.job_type.in_(("sketch_polish", "sketch_clean")),
            AIJob.status == _JOB_SUCCESS,
        ),
    )
    fitting = _count(
        db,
        select(func.count())
        .select_from(AIJob)
        .where(
            AIJob.user_id == user.id,
            AIJob.job_type == "fitting_room_try_on",
            AIJob.status == _JOB_SUCCESS,
        ),
    )
    purchases = db.execute(
        select(
            IapPurchase.product_id,
            IapPurchase.stars_credited,
            IapPurchase.environment,
            IapPurchase.status,
            IapPurchase.created_at,
            IapPurchase.platform,
        )
        .where(IapPurchase.user_id == user.id)
        .order_by(IapPurchase.created_at.desc())
        .limit(50)
    ).all()
    purchase_items = []
    lifetime_list_usd = Decimal("0.00")
    for pid, credited, env, status, created, platform in purchases:
        env_l = (env or "").strip().lower()
        sandbox = env_l in _SANDBOX_ENVS or env_l.startswith("sandbox")
        unit = _PRODUCT_USD.get(str(pid or ""), Decimal("0"))
        if (
            not sandbox
            and status in (STATUS_ACTIVE, STATUS_REFUND_REVERSED)
            and int(credited or 0) > 0
        ):
            lifetime_list_usd += unit
        purchase_items.append(
            {
                "product_id": pid,
                "stars_credited": int(credited or 0),
                "environment": env,
                "sandbox": sandbox,
                "status": status,
                "platform": platform,
                "created_at": created.isoformat() if created else None,
                "list_price_usd": float(unit),
            }
        )

    history = db.scalars(
        select(AccountClassificationEvent)
        .where(AccountClassificationEvent.user_id == user.id)
        .order_by(AccountClassificationEvent.created_at.desc())
        .limit(20)
    ).all()

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "is_active": bool(user.is_active),
        "is_admin": bool(user.is_admin),
        "email_verified": bool(getattr(user, "email_verified", False)),
        "classification": _classification_of(user),
        "classification_note": getattr(user, "account_classification_note", None),
        "classification_updated_at": (
            user.account_classification_updated_at.isoformat()
            if getattr(user, "account_classification_updated_at", None)
            else None
        ),
        "suggestion": suggest_classification(user),
        "wallet": {
            "ai_stars": int(user.ai_stars or 0),
            "ai_stars_iap_debt": int(getattr(user, "ai_stars_iap_debt", 0) or 0),
            "ai_stars_unlimited": bool(getattr(user, "ai_stars_unlimited", False)),
        },
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "activity": {
            "designs_saved": designs,
            "models_created": models,
            "magic_completed": magic,
            "fitting_room_completed": fitting,
        },
        "purchases": {
            "items": purchase_items,
            "lifetime_list_price_usd": float(lifetime_list_usd),
            "kind": "estimated",
        },
        "classification_history": [
            {
                "id": str(h.id),
                "from": h.from_classification,
                "to": h.to_classification,
                "reason": h.reason,
                "note": h.note,
                "actor_id": str(h.actor_id) if h.actor_id else None,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in history
        ],
        "unavailable": [
            "first_platform",
            "country",
            "notification_registrations_detail",
            "full_activity_timeline",
        ],
    }


def set_classification(
    db: Session,
    *,
    target: User,
    actor: User,
    to_classification: str,
    reason: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    to_c = (to_classification or "").strip().upper()
    if to_c not in ACCOUNT_CLASSIFICATIONS:
        raise ValueError(f"Invalid classification: {to_classification}")
    from_c = _classification_of(target)
    if from_c == to_c and (note is None or note == getattr(target, "account_classification_note", None)):
        return customer_detail(db, target.id) or {}

    # Classification must never flip is_admin.
    target.account_classification = to_c
    if note is not None:
        target.account_classification_note = note
    target.account_classification_updated_at = _utc_now()
    target.account_classification_updated_by_id = actor.id
    evt = AccountClassificationEvent(
        id=uuid.uuid4(),
        user_id=target.id,
        actor_id=actor.id,
        from_classification=from_c,
        to_classification=to_c,
        reason=reason,
        note=note,
    )
    db.add(evt)
    db.flush()
    return customer_detail(db, target.id) or {}


def classification_dry_run(db: Session, *, limit: int = 200) -> dict[str, Any]:
    """Operator preview of heuristic suggestions — no writes."""
    lim = max(1, min(int(limit), 500))
    rows = db.scalars(select(User).order_by(User.created_at.desc()).limit(lim)).all()
    items = []
    for u in rows:
        current = _classification_of(u)
        sug = suggest_classification(u)
        if sug["suggested"] != current and sug["confidence"] != "none":
            items.append(
                {
                    "id": str(u.id),
                    "username": u.username,
                    "current": current,
                    "suggested": sug["suggested"],
                    "confidence": sug["confidence"],
                    "evidence": sug["evidence"],
                }
            )
    return {
        "scanned": len(rows),
        "actionable_suggestions": len(items),
        "items": items,
        "note": "Dry-run only. No classifications were written. Operator approval required for any backfill.",
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
