"""FashionRise Admin 2.0 aggregate metrics and customer operations.

Metric calculations are centralized so Overview / Customers / Revenue /
AI Costs stay consistent. Values are labeled exact | estimated | unavailable.

Critical rules (PM review on 27fa5361):
- Audience scope applies to every customer-attributable metric via SQL joins.
- Event metrics honor the selected Asia/Jerusalem reporting range.
- Production revenue requires an explicitly recognized Production environment.
- Free-vs-paid Stars attribution is unavailable (no historical charge amounts).
- Classification never grants admin privileges.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, func, or_, select
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
    STATUS_BLOCKED,
    STATUS_REFUND_REVERSED,
    STATUS_REFUNDED,
    STATUS_REVOKED,
    IapPurchase,
)
from app.models.personal_croquis import PersonalCroquis
from app.models.techpack_ai_run import TechpackAIRun
from app.models.user import User
from app.models.user_follow import UserFollow
from app.services import admin_stars_grants, ai_stars
from app.services.ai_cost_accounting import (
    build_ai_financial_section,
    build_income_vs_expenses,
)
from app.services.iap_service import STARS_PRODUCTS

# Launch ASC / Play list prices (USD) — catalog estimates, not storefront FX / proceeds.
_PRODUCT_USD: dict[str, Decimal] = {
    "stars_50": Decimal("5.99"),
    "stars_150": Decimal("16.99"),
    "stars_500": Decimal("49.99"),
}

_JOB_SUCCESS = "completed"

# Successful customer-facing job types (workers persist status=completed).
_JOB_MAGIC = ("sketch_polish", "sketch_clean")
_JOB_FITTING = ("fitting_room_try_on",)
_JOB_TRY_ON = ("personal_try_on",)  # realism step counted separately
_JOB_TRY_ON_REALISM = ("personal_garment_realism",)
_JOB_CROQUIS = ("personal_croquis_generate",)

_SANDBOX_ENVS = frozenset({"sandbox", "xcode", "localtesting", "test"})
# Only these env strings count toward production revenue (case-insensitive exact).
_PRODUCTION_ENVS = frozenset({"production"})

_INTERNAL_CLASS = frozenset(
    {"OWNER", "ADMIN", "INTERNAL_TESTER", "QA_AUTOMATION", "DEMO_ACCOUNT"}
)

_AUDIENCE_MODES = frozenset({"all", "customers", "internal", "unclassified"})
_VALID_AUDIENCES = _AUDIENCE_MODES | frozenset(ACCOUNT_CLASSIFICATIONS)

# Custom range max span (days) — protects the DB from unbounded scans.
_MAX_CUSTOM_RANGE_DAYS = 366

Audience = str
RangeKey = str

_JERUSALEM = ZoneInfo("Asia/Jerusalem")


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
    ``all_time`` returns start=None. Invalid keys raise ValueError (no silent fallback).
    """
    now = now or _utc_now()
    local = now.astimezone(_JERUSALEM)
    today_local = local.replace(hour=0, minute=0, second=0, microsecond=0)

    def to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_JERUSALEM)
        return dt.astimezone(UTC)

    k = (key or "").strip().lower()
    if not k:
        raise ValueError("range is required")

    if k == "custom":
        if start is None or end is None:
            raise ValueError("custom range requires start and end")
        s = to_utc(start)
        e = to_utc(end)
        if e <= s:
            raise ValueError("end must be after start")
        if (e - s).days > _MAX_CUSTOM_RANGE_DAYS:
            raise ValueError(f"custom range must be at most {_MAX_CUSTOM_RANGE_DAYS} days")
        return s, e, "custom"

    if k == "all_time":
        return None, now, "all_time"
    if k == "today":
        return to_utc(today_local), to_utc(today_local + timedelta(days=1)), "today"
    if k == "yesterday":
        return (
            to_utc(today_local - timedelta(days=1)),
            to_utc(today_local),
            "yesterday",
        )
    if k == "last_7d":
        e = to_utc(today_local + timedelta(days=1))
        return to_utc(today_local - timedelta(days=6)), e, "last_7d"
    if k == "last_30d":
        e = to_utc(today_local + timedelta(days=1))
        return to_utc(today_local - timedelta(days=29)), e, "last_30d"
    if k == "last_90d":
        e = to_utc(today_local + timedelta(days=1))
        return to_utc(today_local - timedelta(days=89)), e, "last_90d"
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

    raise ValueError(f"Invalid range: {key}")


def parse_audience(audience: str | None) -> str:
    """Validate audience. Default business view = confirmed customers."""
    a = (audience if audience is not None else "customers").strip()
    if a == "":
        a = "customers"
    if a not in _VALID_AUDIENCES:
        raise ValueError(
            f"Invalid audience: {audience}. "
            f"Allowed: {', '.join(sorted(_VALID_AUDIENCES))}"
        )
    return a


def _audience_user_filter(audience: str):
    """Filter expression on User for the selected audience. None = all accounts."""
    a = parse_audience(audience)
    if a == "all":
        return None
    if a == "customers":
        return User.account_classification == "CUSTOMER"
    if a == "internal":
        return User.account_classification.in_(tuple(_INTERNAL_CLASS))
    if a == "unclassified":
        return User.account_classification == "UNCLASSIFIED"
    return User.account_classification == a


def _audience_user_ids_subq(audience: str) -> Select | None:
    """Subquery of user ids in audience, or None when audience=all (no join needed)."""
    filt = _audience_user_filter(audience)
    if filt is None:
        return None
    return select(User.id).where(filt).scalar_subquery()


def _apply_audience_fk(stmt, fk_column, audience: str):
    subq = _audience_user_ids_subq(audience)
    if subq is None:
        return stmt
    return stmt.where(fk_column.in_(subq))


def _in_range(column, start: datetime | None, end: datetime):
    conds = [column < end]
    if start is not None:
        conds.insert(0, column >= start)
    return and_(*conds)


def _classification_of(user: User) -> str:
    raw = (getattr(user, "account_classification", None) or "UNCLASSIFIED").strip().upper()
    if raw not in ACCOUNT_CLASSIFICATIONS:
        return "UNCLASSIFIED"
    return raw


def _parse_classification_filters(classification: str | None) -> list[str]:
    """Accept a single value or comma-separated multi-select filter."""
    if not classification:
        return []
    raw_parts = [p.strip().upper() for p in classification.split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        if not part or part in seen:
            continue
        if part not in ACCOUNT_CLASSIFICATIONS:
            raise ValueError(f"Invalid classification filter: {part}")
        seen.add(part)
        out.append(part)
    return out


def _classification_filter(classes: list[str]):
    """Match any selected classification. UNCLASSIFIED includes NULL legacy rows."""
    if not classes:
        return None
    conds = []
    for c in classes:
        if c == "UNCLASSIFIED":
            conds.append(
                or_(
                    User.account_classification.is_(None),
                    User.account_classification == "UNCLASSIFIED",
                )
            )
        else:
            conds.append(User.account_classification == c)
    return or_(*conds) if len(conds) > 1 else conds[0]


def _is_production_env(environment: str | None) -> bool:
    env = (environment or "").strip().lower()
    return env in _PRODUCTION_ENVS


def _is_sandbox_env(environment: str | None) -> bool:
    env = (environment or "").strip().lower()
    return env in _SANDBOX_ENVS or env.startswith("sandbox")


def suggest_classification(user: User) -> dict[str, Any]:
    """Non-authoritative heuristic. Unlimited Stars ≠ OWNER proof."""
    name = (user.username or "").strip().lower()
    evidence: list[str] = []
    if name in ADMIN_USERNAMES or user_is_admin(user):
        return {
            "suggested": "ADMIN" if user_is_admin(user) or name in ADMIN_USERNAMES else "UNCLASSIFIED",
            "confidence": "medium",
            "evidence": ["admin_username_allowlist_or_is_admin"],
            "authoritative": False,
            "note": "Suggestion only — confirm manually. is_admin is independent of classification.",
        }
    if bool(getattr(user, "ai_stars_unlimited", False)) or ai_stars.user_has_unlimited_stars(
        user
    ):
        evidence.append("unlimited_stars_wallet")
        return {
            "suggested": "UNCLASSIFIED",
            "confidence": "low",
            "evidence": evidence,
            "authoritative": False,
            "note": "Unlimited wallet is evidence for manual review, not proof of OWNER.",
        }
    email = (user.email or "").lower()
    if email.endswith("@example.com") or email.endswith(".test"):
        return {
            "suggested": "QA_AUTOMATION",
            "confidence": "medium",
            "evidence": ["example_or_test_email_domain"],
            "authoritative": False,
            "note": "Suggestion only.",
        }
    return {
        "suggested": "UNCLASSIFIED",
        "confidence": "none",
        "evidence": [],
        "authoritative": False,
        "note": "No strong heuristic signal.",
    }


def metric_dictionary() -> list[dict[str, Any]]:
    return [
        {
            "id": "users.registered",
            "name": "Registered accounts",
            "definition": "Count of users rows in the selected audience (lifetime snapshot).",
            "source": "users",
            "kind": "exact",
            "period": "snapshot",
            "audience_scoped": True,
        },
        {
            "id": "users.enabled",
            "name": "Enabled accounts",
            "definition": "Users with is_active=true. Account status only — not engagement DAU/WAU.",
            "source": "users.is_active",
            "kind": "exact",
            "period": "snapshot",
            "audience_scoped": True,
            "limitations": "Not meaningful activity. DAU/WAU unavailable without event store.",
        },
        {
            "id": "users.new_in_range",
            "name": "Registrations in range",
            "definition": "Users created_at within the selected Asia/Jerusalem reporting period.",
            "source": "users.created_at",
            "kind": "exact",
            "period": "range",
            "audience_scoped": True,
        },
        {
            "id": "ai.magic_completed_in_range",
            "name": "Magic completed (range)",
            "definition": (
                "AIJob job_type in sketch_polish/sketch_clean, status=completed, "
                "timestamp = updated_at (completion proxy; no dedicated completed_at column)."
            ),
            "source": "ai_jobs",
            "kind": "exact",
            "period": "range",
            "audience_scoped": True,
            "limitations": "Dual Magic creates two sketch_polish jobs. updated_at used as completion proxy.",
        },
        {
            "id": "ai.fitting_room_completed_in_range",
            "name": "Fitting Room completed (range)",
            "definition": "AIJob fitting_room_try_on status=completed, filtered by updated_at + audience.",
            "source": "ai_jobs",
            "kind": "exact",
            "period": "range",
            "audience_scoped": True,
        },
        {
            "id": "revenue.gross_list_price_usd",
            "name": "Gross estimated list-price revenue (Production)",
            "definition": (
                "Sum of catalog USD list prices for credited Production IAP rows "
                "(active / refunded / revoked / refund_reversed with stars_credited > 0). "
                "Refunded sales stay in gross so refunds are subtracted once. "
                "Blocked-before-credit excluded. Filtered by original purchase date "
                "(current lifecycle state), not refund cash-flow timing."
            ),
            "source": "iap_purchases",
            "kind": "estimated",
            "period": "range",
            "audience_scoped": True,
            "limitations": (
                "Not Apple/Google proceeds. Sandbox/unknown envs excluded separately. "
                "Authoritative refund timestamps unavailable — reporting uses current status."
            ),
        },
        {
            "id": "ai.openai_project_costs_usd",
            "name": "OpenAI recorded project costs (USD)",
            "definition": (
                "Actual monetary amounts from OpenAI Organization Costs API "
                "(GET /v1/organization/costs), filtered to OPENAI_BILLING_PROJECT_ID when set. "
                "Served from persisted daily snapshots — not live on each Admin refresh."
            ),
            "source": "openai_cost_daily",
            "kind": "actual",
            "period": "range",
            "audience_scoped": False,
            "limitations": (
                "Global/provider scope. OpenAI org user IDs are not FashionRise customers. "
                "Sync disabled until OPENAI_COST_SYNC_ENABLED + OPENAI_ADMIN_API_KEY verified."
            ),
        },
        {
            "id": "ai.fashn_credits_consumed",
            "name": "FASHN credits consumed (header-reported)",
            "definition": (
                "Sum of x-fashn-credits-used for completed predictions attributed to the "
                "selected audience. Missing headers are unavailable — never recorded as zero."
            ),
            "source": "fashn_prediction_costs",
            "kind": "exact",
            "period": "range",
            "audience_scoped": True,
        },
        {
            "id": "ai.fashn_estimated_consumption_usd",
            "name": "FASHN estimated consumption (USD)",
            "definition": (
                "Actual credits × versioned documented/operator credit rate. "
                "Not cash invoices. Balance decreases are not expenditure."
            ),
            "source": "fashn_prediction_costs + provider_pricing_versions",
            "kind": "estimated",
            "period": "range",
            "audience_scoped": True,
        },
        {
            "id": "revenue.refunds_list_price_usd",
            "name": "Refunds estimated list-price (Production)",
            "definition": (
                "Catalog USD list prices for Production IAP rows currently status "
                "refunded or revoked (originally credited). Subtracted once from gross."
            ),
            "source": "iap_purchases",
            "kind": "estimated",
            "period": "range",
            "audience_scoped": True,
        },
        {
            "id": "revenue.net_list_price_usd",
            "name": "Net estimated list-price revenue (Production)",
            "definition": "gross_list_price_usd − refunds_list_price_usd (floored at 0).",
            "source": "iap_purchases",
            "kind": "estimated",
            "period": "range",
            "audience_scoped": True,
        },
        {
            "id": "charts.registrations_trend",
            "name": "Registration trend (Asia/Jerusalem calendar days)",
            "definition": (
                "Daily new-user counts grouped with PostgreSQL "
                "timezone('Asia/Jerusalem', created_at) — true local calendar days. "
                "All Time chart capped to last 90 Jerusalem days."
            ),
            "source": "users.created_at",
            "kind": "exact",
            "period": "range",
            "audience_scoped": True,
        },
        {
            "id": "stars.free_vs_paid_attribution",
            "name": "Free vs paid Stars consumption",
            "definition": "Unavailable — historical charged Stars amounts are not stored per debit.",
            "source": None,
            "kind": "unavailable",
            "limitations": "Do not infer from starting_balance_config × users − spend.",
        },
        {
            "id": "engagement.dau",
            "name": "Daily active users",
            "definition": "Unavailable — no authoritative meaningful-activity event store.",
            "source": None,
            "kind": "unavailable",
        },
        {
            "id": "ops.jobs_pending",
            "name": "Pending AI jobs (global)",
            "definition": "Queue depth across all accounts. Not audience-filtered.",
            "source": "ai_jobs",
            "kind": "exact",
            "period": "snapshot",
            "audience_scoped": False,
            "scope_label": "Global / All Accounts",
        },
    ]


def _job_success_count(
    db: Session,
    *,
    job_types: tuple[str, ...],
    start: datetime | None,
    end: datetime,
    audience: str,
) -> int:
    """Count completed jobs for audience using updated_at as completion proxy."""
    stmt = (
        select(func.count())
        .select_from(AIJob)
        .where(
            AIJob.job_type.in_(job_types),
            AIJob.status == _JOB_SUCCESS,
            _in_range(AIJob.updated_at, start, end),
        )
    )
    stmt = _apply_audience_fk(stmt, AIJob.user_id, audience)
    return _count(db, stmt)


def _registration_trend(
    db: Session,
    *,
    audience: str,
    start: datetime | None,
    end: datetime,
) -> dict[str, Any]:
    """Daily registration counts grouped by Asia/Jerusalem calendar dates.

    Uses PostgreSQL ``timezone('Asia/Jerusalem', created_at)`` so buckets are
    true local calendar days (not UTC days relabeled). When the selected range
    is All Time, the chart is capped to the last 90 Jerusalem days and labeled.
    """
    capped = False
    if start is None:
        # Cap all_time chart to last 90 Jerusalem days for query safety.
        local = _utc_now().astimezone(_JERUSALEM).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start = local.replace(tzinfo=_JERUSALEM).astimezone(UTC) - timedelta(days=89)
        capped = True
    # Convert timestamptz → Asia/Jerusalem wall time, then truncate to local day.
    jerusalem_day = func.date_trunc(
        "day", func.timezone("Asia/Jerusalem", User.created_at)
    )
    stmt = (
        select(jerusalem_day, func.count())
        .select_from(User)
        .where(_in_range(User.created_at, start, end))
        .group_by(jerusalem_day)
        .order_by(jerusalem_day.asc())
    )
    filt = _audience_user_filter(audience)
    if filt is not None:
        stmt = stmt.where(filt)
    rows = db.execute(stmt).all()
    points: list[dict[str, Any]] = []
    for bucket, cnt in rows:
        if bucket is None:
            continue
        # date_trunc on timezone()-converted timestamp returns naive local midnight.
        if hasattr(bucket, "date"):
            local_label = bucket.date().isoformat()
        else:
            local_label = str(bucket)[:10]
        points.append({"date": local_label, "count": int(cnt or 0)})
    return {
        "timezone": "Asia/Jerusalem",
        "grouping": "asia_jerusalem_calendar_day",
        "all_time_chart_capped_to_90_days": capped,
        "cap_note": (
            "All Time registration chart shows the last 90 Asia/Jerusalem calendar days only."
            if capped
            else None
        ),
        "points": points,
    }


def overview(
    db: Session,
    *,
    range_key: str = "last_30d",
    audience: str = "customers",
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    range_start, range_end, range_label = resolve_range(
        range_key, start=start, end=end, now=now
    )
    audience = parse_audience(audience)
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)
    aud_filt = _audience_user_filter(audience)

    def user_count(*, extra=None) -> int:
        stmt = select(func.count()).select_from(User)
        if aud_filt is not None:
            stmt = stmt.where(aud_filt)
        if extra is not None:
            stmt = stmt.where(extra)
        return _count(db, stmt)

    users_total = user_count()
    users_enabled = user_count(extra=User.is_active.is_(True))
    users_new_7d = user_count(extra=User.created_at >= week_ago)
    users_new_30d = user_count(extra=User.created_at >= now - timedelta(days=30))
    users_new_in_range = user_count(
        extra=_in_range(User.created_at, range_start, range_end)
    )

    # Classification histogram is always global (operator needs full inventory).
    class_counts = {
        c: _count(
            db,
            select(func.count())
            .select_from(User)
            .where(User.account_classification == c),
        )
        for c in ACCOUNT_CLASSIFICATIONS
    }

    # Content — audience-scoped via ownership FKs.
    designs_stmt = select(func.count()).select_from(GarmentDesign)
    designs_stmt = _apply_audience_fk(designs_stmt, GarmentDesign.user_id, audience)
    designs_total = _count(db, designs_stmt)

    designs_in_range_stmt = select(func.count()).select_from(GarmentDesign).where(
        _in_range(GarmentDesign.created_at, range_start, range_end)
    )
    designs_in_range_stmt = _apply_audience_fk(
        designs_in_range_stmt, GarmentDesign.user_id, audience
    )
    designs_in_range = _count(db, designs_in_range_stmt)

    gallery_pub_stmt = (
        select(func.count())
        .select_from(GalleryItem)
        .where(GalleryItem.visibility == "public")
    )
    gallery_pub_stmt = _apply_audience_fk(gallery_pub_stmt, GalleryItem.user_id, audience)
    gallery_public = _count(db, gallery_pub_stmt)

    designs_published_stmt = (
        select(func.count())
        .select_from(GalleryItem)
        .where(GalleryItem.design_id.is_not(None))
    )
    designs_published_stmt = _apply_audience_fk(
        designs_published_stmt, GalleryItem.user_id, audience
    )
    designs_published = _count(db, designs_published_stmt)

    looks_published_stmt = (
        select(func.count())
        .select_from(GalleryItem)
        .where(GalleryItem.look_id.is_not(None))
    )
    looks_published_stmt = _apply_audience_fk(
        looks_published_stmt, GalleryItem.user_id, audience
    )
    looks_published = _count(db, looks_published_stmt)

    models_stmt = select(func.count()).select_from(PersonalCroquis)
    models_stmt = _apply_audience_fk(models_stmt, PersonalCroquis.owner_id, audience)
    models_created = _count(db, models_stmt)

    models_ready_stmt = (
        select(func.count())
        .select_from(PersonalCroquis)
        .where(PersonalCroquis.status == "uploaded")
    )
    models_ready_stmt = _apply_audience_fk(
        models_ready_stmt, PersonalCroquis.owner_id, audience
    )
    models_ready = _count(db, models_ready_stmt)

    ai_fabrics_stmt = (
        select(func.count())
        .select_from(FabricAsset)
        .where(FabricAsset.source == "ai", FabricAsset.deleted_at.is_(None))
    )
    ai_fabrics_stmt = _apply_audience_fk(ai_fabrics_stmt, FabricAsset.owner_id, audience)
    ai_fabrics = _count(db, ai_fabrics_stmt)

    uploaded_fabrics_stmt = (
        select(func.count())
        .select_from(FabricAsset)
        .where(FabricAsset.source != "ai", FabricAsset.deleted_at.is_(None))
    )
    uploaded_fabrics_stmt = _apply_audience_fk(
        uploaded_fabrics_stmt, FabricAsset.owner_id, audience
    )
    uploaded_fabrics = _count(db, uploaded_fabrics_stmt)

    # Social: actions BY audience vs engagement RECEIVED on audience content.
    likes_by_stmt = select(func.count()).select_from(GalleryLike)
    likes_by_stmt = _apply_audience_fk(likes_by_stmt, GalleryLike.user_id, audience)
    likes_by_audience = _count(db, likes_by_stmt)

    likes_on_content_stmt = (
        select(func.count())
        .select_from(GalleryLike)
        .join(GalleryItem, GalleryItem.id == GalleryLike.gallery_item_id)
    )
    likes_on_content_stmt = _apply_audience_fk(
        likes_on_content_stmt, GalleryItem.user_id, audience
    )
    likes_on_audience_content = _count(db, likes_on_content_stmt)

    comments_by_stmt = select(func.count()).select_from(GalleryComment)
    comments_by_stmt = _apply_audience_fk(comments_by_stmt, GalleryComment.user_id, audience)
    comments_by_audience = _count(db, comments_by_stmt)

    comments_on_content_stmt = (
        select(func.count())
        .select_from(GalleryComment)
        .join(GalleryItem, GalleryItem.id == GalleryComment.gallery_item_id)
    )
    comments_on_content_stmt = _apply_audience_fk(
        comments_on_content_stmt, GalleryItem.user_id, audience
    )
    comments_on_audience_content = _count(db, comments_on_content_stmt)

    follows_by_stmt = select(func.count()).select_from(UserFollow)
    follows_by_stmt = _apply_audience_fk(follows_by_stmt, UserFollow.follower_id, audience)
    follows_by_audience = _count(db, follows_by_stmt)

    followed_stmt = select(func.count()).select_from(UserFollow)
    followed_stmt = _apply_audience_fk(followed_stmt, UserFollow.following_id, audience)
    followed_audience = _count(db, followed_stmt)

    # AI usage — audience + range via updated_at completion proxy.
    magic_lifetime = _job_success_count(
        db, job_types=_JOB_MAGIC, start=None, end=now + timedelta(seconds=1), audience=audience
    )
    magic_in_range = _job_success_count(
        db, job_types=_JOB_MAGIC, start=range_start, end=range_end, audience=audience
    )
    fitting_lifetime = _job_success_count(
        db, job_types=_JOB_FITTING, start=None, end=now + timedelta(seconds=1), audience=audience
    )
    fitting_in_range = _job_success_count(
        db, job_types=_JOB_FITTING, start=range_start, end=range_end, audience=audience
    )
    fitting_7d = _job_success_count(
        db, job_types=_JOB_FITTING, start=week_ago, end=now + timedelta(seconds=1), audience=audience
    )
    try_on_in_range = _job_success_count(
        db, job_types=_JOB_TRY_ON, start=range_start, end=range_end, audience=audience
    )
    try_on_realism_in_range = _job_success_count(
        db,
        job_types=_JOB_TRY_ON_REALISM,
        start=range_start,
        end=range_end,
        audience=audience,
    )
    croquis_in_range = _job_success_count(
        db, job_types=_JOB_CROQUIS, start=range_start, end=range_end, audience=audience
    )

    # Technical PDF / Create Real Design — separate TechpackAIRun table (not AIJob).
    techpack_stmt = (
        select(func.count())
        .select_from(TechpackAIRun)
        .where(
            TechpackAIRun.status == "completed",
            _in_range(TechpackAIRun.updated_at, range_start, range_end),
        )
    )
    techpack_stmt = _apply_audience_fk(techpack_stmt, TechpackAIRun.user_id, audience)
    techpack_completed_in_range = _count(db, techpack_stmt)

    # AI fabrics are FabricAsset rows (source=ai), not AIJob — counted under content.
    # No separate fabric AIJob type exists; avoid double-counting with content.ai_fabrics_created.

    # Global operational metrics — explicitly labeled.
    jobs_last_24h = _count(
        db, select(func.count()).select_from(AIJob).where(AIJob.created_at >= day_ago)
    )
    jobs_pending = _count(
        db,
        select(func.count())
        .select_from(AIJob)
        .where(AIJob.status.in_(("queued", "running", "pending"))),
    )
    jobs_failed_lifetime = _count(
        db, select(func.count()).select_from(AIJob).where(AIJob.status == "failed")
    )
    reports_open = _count(
        db,
        select(func.count())
        .select_from(ContentReport)
        .where(ContentReport.status == "open"),
    )
    reports_total = _count(db, select(func.count()).select_from(ContentReport))

    # Revenue — Production env only; audience-scoped buyers; range by original
    # purchase created_at (current lifecycle state, not refund cash-flow timing).
    #
    # Gross = catalog price of every credited Production sale (active, later
    # refunded/revoked, or refund_reversed). Refunded rows remain in gross so
    # refunds are not double-subtracted. Blocked-before-credit is excluded.
    purchase_stmt = select(
        IapPurchase.product_id,
        IapPurchase.stars_credited,
        IapPurchase.stars_clawed_back,
        IapPurchase.stars_restored,
        IapPurchase.status,
        IapPurchase.environment,
        IapPurchase.created_at,
    ).where(_in_range(IapPurchase.created_at, range_start, range_end))
    purchase_stmt = _apply_audience_fk(purchase_stmt, IapPurchase.user_id, audience)
    purchase_rows = db.execute(purchase_stmt).all()

    gross_list = Decimal("0.00")
    refund_list = Decimal("0.00")
    purchases_counted = 0
    refunds_counted = 0
    blocked_before_credit = 0
    stars_bought_net = 0
    stars_clawed = 0
    stars_restored_total = 0
    sandbox_excluded = 0
    unknown_env_excluded = 0
    for (
        product_id,
        credited,
        clawed,
        restored,
        status,
        environment,
        _created,
    ) in purchase_rows:
        if _is_sandbox_env(environment):
            sandbox_excluded += 1
            continue
        if not _is_production_env(environment):
            unknown_env_excluded += 1
            continue
        unit = _PRODUCT_USD.get(str(product_id or ""), Decimal(0))
        credited_i = int(credited or 0)
        clawed_i = int(clawed or 0)
        restored_i = int(restored or 0)
        st = str(status or "")

        # ASN refund/revoke before credit — never a sale; exclude from gross/refunds.
        if st == STATUS_BLOCKED or credited_i <= 0:
            if st == STATUS_BLOCKED:
                blocked_before_credit += 1
            continue

        # Original credited sale → gross (including rows later refunded/revoked).
        if st in (
            STATUS_ACTIVE,
            STATUS_REFUNDED,
            STATUS_REVOKED,
            STATUS_REFUND_REVERSED,
        ):
            purchases_counted += 1
            if unit > 0:
                gross_list += unit

        if st in (STATUS_REFUNDED, STATUS_REVOKED):
            refunds_counted += 1
            stars_clawed += clawed_i
            if unit > 0:
                refund_list += unit
        elif st in (STATUS_ACTIVE, STATUS_REFUND_REVERSED):
            # Net Stars still attributable after clawback / restore.
            stars_bought_net += max(0, credited_i - clawed_i + restored_i)
            stars_restored_total += restored_i

    net_list = gross_list - refund_list
    if net_list < 0:
        net_list = Decimal("0.00")

    # Wallet snapshot (audience-scoped finite wallets).
    wallet_stmt = select(func.coalesce(func.sum(User.ai_stars), 0)).where(
        User.ai_stars_unlimited.is_(False)
    )
    if aud_filt is not None:
        wallet_stmt = wallet_stmt.where(aud_filt)
    wallet_sum = int(db.scalar(wallet_stmt) or 0)

    unlimited_stmt = select(func.count()).select_from(User).where(
        User.ai_stars_unlimited.is_(True)
    )
    if aud_filt is not None:
        unlimited_stmt = unlimited_stmt.where(aud_filt)
    unlimited_wallets = _count(db, unlimited_stmt)

    # Paying customers in audience (lifetime Production purchase, any time).
    paying_stmt = (
        select(func.count(func.distinct(IapPurchase.user_id)))
        .select_from(IapPurchase)
        .where(
            IapPurchase.status.in_((STATUS_ACTIVE, STATUS_REFUND_REVERSED)),
            IapPurchase.stars_credited > 0,
            func.lower(func.coalesce(IapPurchase.environment, "")) == "production",
        )
    )
    paying_stmt = _apply_audience_fk(paying_stmt, IapPurchase.user_id, audience)
    paying_customers = _count(db, paying_stmt)

    # Recent signups — audience scoped; omit email from overview (PII minimization).
    recent_stmt = select(User).order_by(User.created_at.desc()).limit(12)
    if aud_filt is not None:
        recent_stmt = recent_stmt.where(aud_filt)
    recent_signups = [
        {
            "id": str(u.id),
            "username": u.username,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "classification": _classification_of(u),
            "suggestion": suggest_classification(u),
        }
        for u in db.scalars(recent_stmt).all()
    ]

    registrations_trend = _registration_trend(
        db, audience=audience, start=range_start, end=range_end
    )

    needs_attention: list[dict[str, Any]] = []
    if class_counts.get("UNCLASSIFIED", 0) > 0:
        needs_attention.append(
            {
                "id": "unclassified_accounts",
                "severity": "medium",
                "title": f"{class_counts['UNCLASSIFIED']} unclassified accounts",
                "detail": "Review classification before treating analytics as confirmed customers.",
                "section": "customers",
                "scope": "Global / All Accounts",
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
                "scope": "Global / All Accounts",
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
                "scope": "Global / All Accounts",
            }
        )

    starting_cfg = ai_stars.starting_balance()

    payload: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "timezone_reporting": "Asia/Jerusalem",
        "range": {
            "key": range_label,
            "start": range_start.isoformat() if range_start else None,
            "end": range_end.isoformat(),
            "label_note": "Event metrics use this period unless marked snapshot/lifetime/global.",
        },
        "audience": audience,
        "audience_default": "customers",
        "classification_counts": class_counts,
        "users": {
            "registered": users_total,
            "enabled": users_enabled,
            "new_7d": users_new_7d,
            "new_30d": users_new_30d,
            "new_in_range": users_new_in_range,
            "confirmed_customers": class_counts.get("CUSTOMER", 0),
            "unclassified": class_counts.get("UNCLASSIFIED", 0),
            "internal": sum(class_counts.get(c, 0) for c in _INTERNAL_CLASS),
            "paying_customers": paying_customers,
            # Deprecated aliases kept for transitional FE — same values, new names preferred.
            "total": users_total,
            "active": users_enabled,
            "period": {
                "registered": "snapshot",
                "enabled": "snapshot",
                "new_in_range": "range",
                "paying_customers": "lifetime",
            },
        },
        "content": {
            "designs_saved": designs_total,
            "designs_saved_in_range": designs_in_range,
            "designs_published": designs_published,
            "looks_published": looks_published,
            "gallery_public": gallery_public,
            "models_created": models_created,
            "models_ready": models_ready,
            "ai_fabrics_created": ai_fabrics,
            "uploaded_fabrics": uploaded_fabrics,
            # Legacy FE keys = actions performed by the selected audience.
            "likes": likes_by_audience,
            "comments": comments_by_audience,
            "follows": follows_by_audience,
            "period": {
                "designs_saved": "lifetime",
                "designs_saved_in_range": "range",
                "models_ready": "snapshot",
            },
            "audience_scoped": True,
        },
        "engagement": {
            "likes_by_audience": likes_by_audience,
            "likes_on_audience_content": likes_on_audience_content,
            "comments_by_audience": comments_by_audience,
            "comments_on_audience_content": comments_on_audience_content,
            "follows_by_audience": follows_by_audience,
            "followed_audience": followed_audience,
            "dau": {"kind": "unavailable", "detail": "No meaningful-activity event store."},
            "wau": {"kind": "unavailable", "detail": "No meaningful-activity event store."},
            "audience_scoped": True,
        },
        "ai_usage": {
            "fitting_room_completed": fitting_lifetime,
            "fitting_room_7d": fitting_7d,
            "fitting_room_in_range": fitting_in_range,
            "magic_completed": magic_lifetime,
            "magic_in_range": magic_in_range,
            "try_on_completed_in_range": try_on_in_range,
            "try_on_realism_step_in_range": try_on_realism_in_range,
            "croquis_completed_in_range": croquis_in_range,
            "techpack_completed_in_range": techpack_completed_in_range,
            "fabrics_note": (
                "AI fabric creations are content.ai_fabrics_created (FabricAsset.source=ai), "
                "not AIJob rows — not double-counted here."
            ),
            "try_on_completed": try_on_in_range,  # transitional alias = in-range
            # Global ops mirrored here with explicit labels for existing FE cards.
            "jobs_last_24h": jobs_last_24h,
            "jobs_pending": jobs_pending,
            "jobs_failed": jobs_failed_lifetime,
            "jobs_scope_label": "Global / All Accounts",
            "status_semantics": "completed",
            "completion_timestamp": "updated_at",
            "completion_timestamp_note": (
                "AIJob has no completed_at column. Successful jobs use updated_at as "
                "completion proxy when status=completed. created_at is not used for success windows."
            ),
            "note": (
                "Success = AIJob.status 'completed'. Dual Magic = two sketch_polish rows. "
                "personal_garment_realism is an intermediate step (counted separately). "
                "Unlimited wallets remain included in usage counts. "
                "jobs_pending / jobs_last_24h / jobs_failed are Global / All Accounts."
            ),
            "audience_scoped": True,
            "period_default": "range_for_in_range_fields_lifetime_for_completed",
        },
        "operations_global": {
            "scope_label": "Global / All Accounts",
            "jobs_last_24h": jobs_last_24h,
            "jobs_pending": jobs_pending,
            "jobs_failed_lifetime": jobs_failed_lifetime,
            "reports_open": reports_open,
            "reports_total": reports_total,
            "audience_scoped": False,
        },
        "stars": {
            "starting_balance_config": starting_cfg,
            "starting_grant_per_user": starting_cfg,  # transitional alias — config, not issued
            "starting_balance_config_note": (
                "Current configured AI_STARS_STARTING_BALANCE — not historical grants issued."
            ),
            "free_grants_issued": {
                "kind": "unavailable",
                "detail": "Historical starting-grant issuance not stored separately from wallet balance.",
            },
            "free_vs_paid_attribution": {
                "kind": "unavailable",
                "detail": (
                    "Historical Stars debit amounts are not stored. "
                    "Cannot attribute free vs purchased consumption without inventing values."
                ),
            },
            # Transitional FE fields — marked unavailable; never invent paid/free split.
            "free_stars_consumed_est": None,
            "paid_stars_consumed_est": None,
            "stars_spent_total_est": None,
            "spent_by_feature_est": {},
            "stars_spent_total": {
                "kind": "unavailable",
                "detail": (
                    "Do not apply today's feature prices to historical jobs as actual consumption. "
                    "Use AI usage counts (exact) instead."
                ),
            },
            "stars_purchased_net": stars_bought_net,
            "stars_purchased_net_in_range": stars_bought_net,
            "stars_clawed_back": stars_clawed,
            "stars_clawed_back_in_range": stars_clawed,
            "wallet_balance_sum": wallet_sum,
            "wallet_balance_sum_period": "snapshot",
            "unlimited_wallets": unlimited_wallets,
            "costs": ai_stars.cost_catalog(),
            "costs_config": ai_stars.cost_catalog(),
            "admin_grants": {
                **admin_stars_grants.grants_overview(
                    db, start=range_start, end=range_end, audience=audience
                ),
                "period": "range",
                "excluded_from_revenue": True,
                "excluded_from_purchased_stars": True,
            },
            "audience_scoped": True,
        },
        "revenue": {
            "currency": "USD",
            "gross_list_price_usd": float(gross_list),
            "refunds_list_price_usd": float(refund_list),
            "net_list_price_usd": float(net_list),
            "purchases_counted": purchases_counted,
            "refunds_counted": refunds_counted,
            "blocked_before_credit_excluded": blocked_before_credit,
            "stars_restored_in_range": stars_restored_total,
            "sandbox_purchases_excluded": sandbox_excluded,
            "unknown_environment_excluded": unknown_env_excluded,
            "kind": "estimated",
            "period": "range",
            "audience_scoped": True,
            "reporting_basis": (
                "current_lifecycle_state_grouped_by_original_purchase_date"
            ),
            "verified_actual_transaction_amounts": {
                "kind": "unavailable",
                "detail": "Store transaction price FX not persisted on iap_purchases.",
            },
            "actual_store_proceeds": {
                "kind": "unavailable",
                "detail": "Apple/Google net proceeds not imported.",
            },
            "note": (
                "Estimated catalog list prices for environment=Production only. "
                "Gross includes every credited Production sale (active, refunded, revoked, "
                "refund_reversed) so refunds are subtracted once — not double-counted. "
                "Blocked-before-credit is excluded. Rows are filtered by original purchase "
                "created_at (current lifecycle state), not refund cash-flow timing. "
                "Sandbox/Test/unknown environments excluded separately. "
                "Not Apple/Google net proceeds. Administrative grants never count as revenue."
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
            "scope_label": "Global / All Accounts",
            "reports_open": reports_open,
            "reports_total": reports_total,
            "audience_scoped": False,
        },
        "charts": {
            "registrations_trend": {
                "kind": "exact",
                "period": "range",
                "audience_scoped": True,
                "timezone": registrations_trend["timezone"],
                "grouping": registrations_trend["grouping"],
                "all_time_chart_capped_to_90_days": registrations_trend[
                    "all_time_chart_capped_to_90_days"
                ],
                "cap_note": registrations_trend["cap_note"],
                "points": registrations_trend["points"],
                "empty": len(registrations_trend["points"]) == 0,
            },
            "revenue_trend": {
                "kind": "unavailable",
                "detail": "Daily revenue series deferred — use range totals until Phase C.",
            },
            "ai_cost_trend": {
                "kind": "unavailable",
                "detail": "Provider cash billing unavailable until sync populates rows.",
            },
        },
        "needs_attention": needs_attention,
        "unavailable": [
            "acquisition.platform",
            "acquisition.country",
            "retention.d7",
            "engagement.dau",
            "engagement.wau",
            "external.app_store_downloads_live",
            "stars.free_vs_paid_attribution",
            "stars.historical_spend_actual",
        ],
        "recent_signups": recent_signups,
        # FE transitional: expose jobs_* on ai_usage for existing cards.
        "ai_usage_extended": True,
    }

    # AI financial intelligence (Phase D) — persisted snapshots; sync disabled by default.
    ai_financial = build_ai_financial_section(
        db,
        start=range_start,
        end=range_end,
        audience_filter=aud_filt,
    )
    payload["ai_financial"] = ai_financial
    try:
        from app.services import google_play_reconcile

        payload["ai_financial"]["google_play_reconciliation"] = (
            google_play_reconcile.admin_reconciliation_snapshot(db, sample_limit=25)
        )
    except Exception:  # noqa: BLE001 — overview must not fail closed on reconcile probe
        payload["ai_financial"]["google_play_reconciliation"] = {
            "kind": "unavailable",
            "detail": "google_play_reconciliation_probe_failed",
        }
    successful_gens = int(
        magic_in_range
        + fitting_in_range
        + try_on_in_range
        + croquis_in_range
        + techpack_completed_in_range
    )
    payload["income_vs_expenses"] = build_income_vs_expenses(
        revenue_gross=float(gross_list),
        revenue_refunds=float(refund_list),
        revenue_net=float(net_list),
        ai_financial=ai_financial,
        stars_purchased_net=int(stars_bought_net),
        successful_generations=successful_gens,
        paying_customers=int(paying_customers),
    )
    trend = ai_financial.get("daily_cost_trend") or {}
    payload["charts"]["ai_cost_trend"] = {
        "kind": trend.get("kind") or "unavailable",
        "detail": trend.get("detail"),
        "points": trend.get("points") or [],
        "scope_label": trend.get("scope_label"),
        "period": "range",
        "audience_scoped": False,
    }
    for alert in ai_financial.get("alerts") or []:
        if isinstance(alert, dict):
            payload["needs_attention"].append(alert)
    # Keep unavailable honest: org billing remains unavailable until sync has actual rows.
    openai_proj = (ai_financial.get("openai") or {}).get("project_costs") or {}
    if openai_proj.get("kind") != "actual":
        payload["unavailable"].append("ai.provider_actual_billing")
    else:
        payload["unavailable"].append("ai.fashn_actual_cash_invoices")

    return payload


def list_customers(
    db: Session,
    *,
    q: str | None = None,
    classification: str | None = None,
    audience: str = "customers",
    limit: int = 50,
    offset: int = 0,
    sort: str = "created_at_desc",
) -> dict[str, Any]:
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    audience = parse_audience(audience)

    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    class_filters = _parse_classification_filters(classification)
    if class_filters:
        filt = _classification_filter(class_filters)
    else:
        filt = _audience_user_filter(audience)

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

    # Stable ordering: primary sort + id tie-break.
    if sort == "stars_desc":
        stmt = stmt.order_by(User.ai_stars.desc(), User.id.asc())
    elif sort == "username_asc":
        stmt = stmt.order_by(func.lower(User.username).asc(), User.id.asc())
    else:
        stmt = stmt.order_by(User.created_at.desc(), User.id.asc())

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
                "ai_stars": int(u.ai_stars or 0),
                "ai_stars_unlimited": bool(getattr(u, "ai_stars_unlimited", False)),
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "suggestion": suggest_classification(u),
            }
        )
    return {
        "items": items,
        "total": total,
        "limit": lim,
        "offset": off,
        "has_more": off + len(items) < total,
        "audience": audience,
        "classification": ",".join(class_filters) if class_filters else None,
        "classifications": class_filters,
        "sort": sort,
    }


def _lifetime_production_revenue_usd(db: Session, user_id: uuid.UUID) -> Decimal:
    """All eligible Production purchases — independent of the 50-row display page."""
    rows = db.execute(
        select(
            IapPurchase.product_id,
            IapPurchase.stars_credited,
            IapPurchase.stars_clawed_back,
            IapPurchase.status,
            IapPurchase.environment,
        ).where(IapPurchase.user_id == user_id)
    ).all()
    total = Decimal("0.00")
    for pid, credited, clawed, status, environment in rows:
        if not _is_production_env(environment):
            continue
        if status not in (STATUS_ACTIVE, STATUS_REFUND_REVERSED):
            continue
        net = max(0, int(credited or 0) - int(clawed or 0))
        if net <= 0:
            continue
        unit = _PRODUCT_USD.get(str(pid or ""), Decimal(0))
        if unit > 0:
            total += unit
    return total


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
            AIJob.job_type.in_(_JOB_MAGIC),
            AIJob.status == _JOB_SUCCESS,
        ),
    )
    fitting = _count(
        db,
        select(func.count())
        .select_from(AIJob)
        .where(
            AIJob.user_id == user.id,
            AIJob.job_type.in_(_JOB_FITTING),
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
    for pid, credited, env, status, created, platform in purchases:
        unit = _PRODUCT_USD.get(str(pid or ""), Decimal(0))
        purchase_items.append(
            {
                "product_id": pid,
                "stars_credited": int(credited or 0),
                "environment": env,
                "sandbox": _is_sandbox_env(env),
                "production": _is_production_env(env),
                "status": status,
                "platform": platform,
                "created_at": created.isoformat() if created else None,
                "list_price_usd": float(unit),
            }
        )

    lifetime_list_usd = _lifetime_production_revenue_usd(db, user.id)

    history = db.scalars(
        select(AccountClassificationEvent)
        .where(AccountClassificationEvent.user_id == user.id)
        .order_by(AccountClassificationEvent.created_at.desc())
        .limit(50)
    ).all()
    actor_ids = {h.actor_id for h in history if h.actor_id}
    actors = {
        a.id: a.username
        for a in db.scalars(select(User).where(User.id.in_(actor_ids))).all()
    } if actor_ids else {}

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
        "classification_updated_by_id": (
            str(user.account_classification_updated_by_id)
            if getattr(user, "account_classification_updated_by_id", None)
            else None
        ),
        "suggestion": suggest_classification(user),
        "wallet": {
            "ai_stars": int(user.ai_stars or 0),
            "ai_stars_iap_debt": int(getattr(user, "ai_stars_iap_debt", 0) or 0),
            "ai_stars_unlimited": bool(
                ai_stars.user_has_unlimited_stars(user)
            ),
            "period": "snapshot",
        },
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "activity": {
            "designs_saved": designs,
            "models_created": models,
            "magic_completed": magic,
            "fitting_room_completed": fitting,
            "period": "lifetime",
        },
        "purchases": {
            "items": purchase_items,
            "display_limit": 50,
            "lifetime_list_price_usd": float(lifetime_list_usd),
            "lifetime_list_price_note": (
                "Lifetime estimated Production list-price revenue across ALL purchases "
                "(not limited to the 50-row display page)."
            ),
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
                "actor_username": actors.get(h.actor_id) if h.actor_id else None,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in history
        ],
        "admin_stars_grants": {
            "items": admin_stars_grants.list_grants_for_user(db, user.id, limit=50),
            "excluded_from_revenue": True,
            "excluded_from_purchased_stars": True,
            "editable": False,
            "deletable": False,
        },
        "unavailable": [
            "first_platform",
            "country",
            "notification_registrations_detail",
            "full_activity_timeline",
            "stars.free_vs_paid_attribution",
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
    expected_updated_at: str | None = None,
    expected_classification: str | None = None,
) -> dict[str, Any]:
    to_c = (to_classification or "").strip().upper()
    if to_c not in ACCOUNT_CLASSIFICATIONS:
        raise ValueError(f"Invalid classification: {to_classification}")
    reason_clean = (reason or "").strip()
    if len(reason_clean) < 3:
        raise ValueError("A meaningful reason is required (min 3 characters)")

    # Lock row and refresh identity-map state so optimistic checks see DB truth.
    locked = db.scalar(
        select(User)
        .where(User.id == target.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None:
        raise ValueError("User not found")
    db.refresh(locked)

    from_c = _classification_of(locked)
    if expected_classification:
        exp = expected_classification.strip().upper()
        if exp != from_c:
            raise ConflictClassificationError(
                f"Classification changed concurrently (expected {exp}, found {from_c})"
            )
    if expected_updated_at:
        current_ts = (
            locked.account_classification_updated_at.isoformat()
            if locked.account_classification_updated_at
            else None
        )
        if current_ts != expected_updated_at:
            raise ConflictClassificationError(
                "Classification was updated by another admin; refresh and retry"
            )

    if from_c == to_c and (
        note is None or note == getattr(locked, "account_classification_note", None)
    ):
        return customer_detail(db, locked.id) or {}

    # Classification must never flip is_admin / permissions.
    prior_admin = bool(locked.is_admin)
    locked.account_classification = to_c
    if note is not None:
        locked.account_classification_note = note
    locked.account_classification_updated_at = _utc_now()
    locked.account_classification_updated_by_id = actor.id
    locked.is_admin = prior_admin
    evt = AccountClassificationEvent(
        id=uuid.uuid4(),
        user_id=locked.id,
        actor_id=actor.id,
        from_classification=from_c,
        to_classification=to_c,
        reason=reason_clean,
        note=note,
    )
    db.add(evt)
    db.flush()
    target.account_classification = locked.account_classification
    target.is_admin = prior_admin
    return customer_detail(db, locked.id) or {}


class ConflictClassificationError(ValueError):
    """Raised when optimistic concurrency check fails on classification."""


def classification_dry_run(db: Session, *, limit: int = 200) -> dict[str, Any]:
    lim = max(1, min(int(limit), 500))
    rows = db.scalars(select(User).order_by(User.created_at.desc()).limit(lim)).all()
    items = []
    for u in rows:
        current = _classification_of(u)
        sug = suggest_classification(u)
        if sug["suggested"] != current and sug["confidence"] not in ("none",):
            items.append(
                {
                    "id": str(u.id),
                    "username": u.username,
                    "current": current,
                    "suggested": sug["suggested"],
                    "confidence": sug["confidence"],
                    "evidence": sug["evidence"],
                    "note": sug.get("note"),
                }
            )
    return {
        "scanned": len(rows),
        "actionable_suggestions": len(items),
        "items": items,
        "note": (
            "Dry-run only. No classifications were written. "
            "Unlimited Stars never alone implies OWNER. Operator approval required."
        ),
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
