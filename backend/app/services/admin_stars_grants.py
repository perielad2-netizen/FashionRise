"""Administrative ADD-ONLY Stars grants.

Positive integers only. Reuses ``ai_stars.credit_stars`` under FOR UPDATE.
Never accepts a target balance. Never deducts. Never creates IAP rows.
Does not count toward purchase revenue.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.models.admin_stars_grant import (
    ABSOLUTE_GRANT_CEILING,
    ADMIN_GRANT_REASONS,
    ADMIN_GRANT_SOURCE,
    ADMIN_GRANT_STATUS_COMPLETED,
    STARS_INT_MAX,
    AdminStarsGrant,
)
from app.models.user import User
from app.services import ai_stars

_log = logging.getLogger(__name__)

NOTE_MAX_LEN = 2000
IDEMPOTENCY_KEY_MIN = 8
IDEMPOTENCY_KEY_MAX = 128
DEFAULT_MAX_GRANT = 10_000


def absolute_grant_ceiling() -> int:
    """Immutable code-enforced maximum — cannot be raised via environment."""
    return ABSOLUTE_GRANT_CEILING


def effective_max_grant_amount() -> int:
    """Configured max clamped to the absolute ceiling; invalid config → 10_000."""
    settings = get_settings()
    configured = int(settings.admin_stars_grant_max_amount)
    if configured < 1 or configured > ABSOLUTE_GRANT_CEILING:
        configured = DEFAULT_MAX_GRANT
    return min(configured, ABSOLUTE_GRANT_CEILING)


def large_confirm_threshold() -> int:
    raw = int(get_settings().admin_stars_grant_large_confirm_threshold)
    if raw < 1:
        return 500
    return min(raw, ABSOLUTE_GRANT_CEILING)


def grant_limits_payload() -> dict[str, Any]:
    return {
        "max_per_transaction": effective_max_grant_amount(),
        "absolute_ceiling": absolute_grant_ceiling(),
        "large_confirm_threshold": large_confirm_threshold(),
        "reasons": list(ADMIN_GRANT_REASONS),
    }


def _serialize(grant: AdminStarsGrant) -> dict[str, Any]:
    return {
        "grant_id": str(grant.id),
        "recipient_id": str(grant.recipient_id) if grant.recipient_id else None,
        "actor_id": str(grant.actor_id) if grant.actor_id else None,
        "amount": int(grant.amount),
        "balance_before": int(grant.balance_before),
        "balance_after": int(grant.balance_after),
        "reason": grant.reason,
        "note": grant.note,
        "source": grant.source,
        "status": grant.status,
        "idempotency_key": grant.idempotency_key,
        "created_at": grant.created_at.isoformat() if grant.created_at else None,
    }


def _validate_amount(raw: Any) -> int:
    """Strict positive integer — reject bool, float, str, zero, negative, overflow."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValidationAppError(
            "amount must be a strictly positive integer (no decimals, strings, or booleans)"
        )
    if raw <= 0:
        raise ValidationAppError("amount must be a strictly positive integer")
    if raw > STARS_INT_MAX:
        raise ValidationAppError("amount exceeds integer safety limit")
    max_allowed = effective_max_grant_amount()
    if raw > max_allowed:
        raise ValidationAppError(
            f"amount exceeds maximum allowed grant of {max_allowed} Stars per transaction"
        )
    if raw > ABSOLUTE_GRANT_CEILING:
        raise ValidationAppError(
            f"amount exceeds absolute ceiling of {ABSOLUTE_GRANT_CEILING} Stars"
        )
    return raw


def _validate_reason_and_note(reason: str, note: str | None) -> tuple[str, str | None]:
    r = (reason or "").strip().upper()
    if r not in ADMIN_GRANT_REASONS:
        raise ValidationAppError(
            f"reason must be one of: {', '.join(ADMIN_GRANT_REASONS)}"
        )
    cleaned_note = (note or "").strip() or None
    if cleaned_note is not None and len(cleaned_note) > NOTE_MAX_LEN:
        raise ValidationAppError(f"note must be at most {NOTE_MAX_LEN} characters")
    if r == "OTHER" and not cleaned_note:
        raise ValidationAppError("note is required when reason is OTHER")
    return r, cleaned_note


def _validate_idempotency_key(key: str) -> str:
    k = (key or "").strip()
    if len(k) < IDEMPOTENCY_KEY_MIN or len(k) > IDEMPOTENCY_KEY_MAX:
        raise ValidationAppError(
            f"idempotency_key must be {IDEMPOTENCY_KEY_MIN}–{IDEMPOTENCY_KEY_MAX} characters"
        )
    return k


def _idempotent_match(
    existing: AdminStarsGrant,
    *,
    actor_id: uuid.UUID,
    recipient_id: uuid.UUID,
    amount: int,
    reason: str,
    note: str | None,
) -> bool:
    """Same key may replay only for the same administrator + exact payload."""
    return (
        existing.actor_id == actor_id
        and existing.recipient_id == recipient_id
        and int(existing.amount) == amount
        and existing.reason == reason
        and (existing.note or None) == note
    )


def grant_stars(
    db: Session,
    *,
    actor: User,
    recipient_id: uuid.UUID,
    amount: Any,
    reason: str,
    note: str | None,
    idempotency_key: str,
    confirm_large: bool = False,
) -> dict[str, Any]:
    """Atomically credit Stars and write an AdminStarsGrant audit row.

    Idempotent on ``idempotency_key`` bound to the administrator identity.
    Same key + same actor + same payload → original result.
    Same key + different actor or payload → conflict.
    Never creates IapPurchase rows. Never deducts.
    """
    amt = _validate_amount(amount)
    reason_n, note_n = _validate_reason_and_note(reason, note)
    idem = _validate_idempotency_key(idempotency_key)

    if amt >= large_confirm_threshold() and not confirm_large:
        raise ValidationAppError(
            f"grants of {large_confirm_threshold()} Stars or more require confirm_large=true"
        )

    existing = db.scalar(
        select(AdminStarsGrant).where(AdminStarsGrant.idempotency_key == idem)
    )
    if existing is not None:
        if not _idempotent_match(
            existing,
            actor_id=actor.id,
            recipient_id=recipient_id,
            amount=amt,
            reason=reason_n,
            note=note_n,
        ):
            raise ConflictError(
                "idempotency_key already used with different grant details "
                "or by a different administrator",
                payload={"grant_id": str(existing.id)},
            )
        return {**_serialize(existing), "idempotent_replay": True}

    # Fresh authoritative recipient under row lock — avoid stale identity-map values.
    db.expire_all()
    recipient = db.scalar(select(User).where(User.id == recipient_id).with_for_update())
    if recipient is None:
        raise NotFoundError("User not found")
    if not bool(recipient.is_active):
        raise ValidationAppError("Cannot grant Stars to an inactive account")

    if ai_stars.user_has_unlimited_stars(recipient):
        raise ForbiddenError(
            "Manual Stars grants are disabled for unlimited-wallet accounts"
        )

    debt = max(0, int(getattr(recipient, "ai_stars_iap_debt", 0) or 0))
    if debt > 0:
        raise ForbiddenError(
            "Cannot grant Stars while outstanding IAP Stars debt exists "
            f"({debt} Stars). Resolve debt through the existing refund accounting path first."
        )

    balance_before = int(recipient.ai_stars or 0)
    if balance_before < 0:
        raise ValidationAppError("Recipient wallet balance is corrupt (negative)")
    if balance_before > STARS_INT_MAX - amt:
        raise ValidationAppError(
            "Grant would overflow the Stars wallet integer limit; reduce amount"
        )
    expected_after = balance_before + amt

    grant = AdminStarsGrant(
        id=uuid.uuid4(),
        recipient_id=recipient.id,
        actor_id=actor.id,
        amount=amt,
        balance_before=balance_before,
        balance_after=expected_after,
        reason=reason_n,
        note=note_n,
        source=ADMIN_GRANT_SOURCE,
        status=ADMIN_GRANT_STATUS_COMPLETED,
        idempotency_key=idem,
    )

    try:
        # SAVEPOINT: wallet credit + ledger row succeed or roll back together.
        with db.begin_nested():
            balance_after = ai_stars.credit_stars(
                db, recipient, amt, reason=f"admin_grant:{reason_n}"
            )
            credited = int(balance_after)
            if credited != expected_after:
                raise ValidationAppError(
                    "Grant aborted: credited balance did not equal requested add "
                    f"(expected {expected_after}, got {credited})"
                )
            if credited != balance_before + amt:
                raise ValidationAppError(
                    "Grant aborted: credit did not equal the requested positive amount"
                )
            grant.balance_after = credited
            db.add(grant)
            db.flush()
    except IntegrityError as exc:
        raced = db.scalar(
            select(AdminStarsGrant).where(AdminStarsGrant.idempotency_key == idem)
        )
        if raced is not None:
            if _idempotent_match(
                raced,
                actor_id=actor.id,
                recipient_id=recipient_id,
                amount=amt,
                reason=reason_n,
                note=note_n,
            ):
                return {**_serialize(raced), "idempotent_replay": True}
            raise ConflictError(
                "idempotency_key already used with different grant details "
                "or by a different administrator",
                payload={"grant_id": str(raced.id)},
            ) from exc
        raise ValidationAppError("Grant could not be recorded; please retry") from exc

    _log.info(
        "admin_stars_grant grant_id=%s actor=%s recipient=%s amount=%s before=%s after=%s reason=%s",
        grant.id,
        actor.id,
        recipient.id,
        amt,
        balance_before,
        grant.balance_after,
        reason_n,
    )
    return {**_serialize(grant), "idempotent_replay": False}


def list_grants_for_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AdminStarsGrant)
        .where(AdminStarsGrant.recipient_id == user_id)
        .order_by(AdminStarsGrant.created_at.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    return [_serialize(r) for r in rows]


def reconcile_grant_by_idempotency(
    db: Session,
    *,
    actor: User,
    idempotency_key: str,
) -> dict[str, Any]:
    """Read-only lookup of a completed grant by idempotency key.

    Outcomes:
    - ``recorded`` — grant exists and was created by this financial admin.
    - ``not_found`` — no row yet; a concurrent POST may still commit
      (not-found is **not** proof that the operation cannot complete).
    - ``unavailable`` — a grant exists for this key but is not owned by the
      requesting administrator (details withheld).

    Never mutates wallets or grant rows.
    """
    idem = _validate_idempotency_key(idempotency_key)
    existing = db.scalar(
        select(AdminStarsGrant).where(AdminStarsGrant.idempotency_key == idem)
    )
    if existing is None:
        return {
            "outcome": "not_found",
            "message": (
                "No completed grant recorded for this idempotency key. "
                "A concurrent request may still commit — not-found is not "
                "proof that the operation cannot complete."
            ),
            "grant": None,
            "wallet": None,
            "wallet_mutations": 0,
        }

    if existing.actor_id != actor.id:
        return {
            "outcome": "unavailable",
            "message": (
                "Grant reconciliation is unavailable for this administrator. "
                "Another administrator may own this idempotency key."
            ),
            "grant": None,
            "wallet": None,
            "wallet_mutations": 0,
        }

    wallet: dict[str, Any] | None = None
    if existing.recipient_id is not None:
        recipient = db.get(User, existing.recipient_id)
        if recipient is not None:
            wallet = {
                "recipient_id": str(recipient.id),
                "ai_stars": int(recipient.ai_stars or 0),
                "ai_stars_unlimited": bool(
                    ai_stars.user_has_unlimited_stars(recipient)
                ),
                "ai_stars_iap_debt": max(
                    0, int(getattr(recipient, "ai_stars_iap_debt", 0) or 0)
                ),
            }

    return {
        "outcome": "recorded",
        "message": "Completed grant recorded for this idempotency key.",
        "grant": {**_serialize(existing), "idempotent_replay": True},
        "wallet": wallet,
        "wallet_mutations": 0,
    }


def grants_overview(
    db: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    """Aggregate admin-grant stats (separate from purchase revenue).

    When ``audience`` is provided, filter by recipient classification via SQL subquery.
    """
    from app.services.admin_analytics import _apply_audience_fk, parse_audience

    aud = parse_audience(audience) if audience is not None else "all"

    def _apply_filters(stmt):
        if start is not None:
            stmt = stmt.where(AdminStarsGrant.created_at >= start)
        if end is not None:
            stmt = stmt.where(AdminStarsGrant.created_at < end)
        stmt = _apply_audience_fk(stmt, AdminStarsGrant.recipient_id, aud)
        return stmt

    stars_sum = int(
        db.scalar(
            _apply_filters(select(func.coalesce(func.sum(AdminStarsGrant.amount), 0)))
        )
        or 0
    )
    grant_count = int(
        db.scalar(_apply_filters(select(func.count()).select_from(AdminStarsGrant))) or 0
    )
    recipient_count = int(
        db.scalar(
            _apply_filters(select(func.count(func.distinct(AdminStarsGrant.recipient_id))))
        )
        or 0
    )

    by_reason_rows = db.execute(
        _apply_filters(
            select(
                AdminStarsGrant.reason,
                func.count(),
                func.coalesce(func.sum(AdminStarsGrant.amount), 0),
            ).group_by(AdminStarsGrant.reason)
        )
    ).all()
    by_reason = {
        str(reason): {"count": int(cnt), "stars": int(stars)}
        for reason, cnt, stars in by_reason_rows
    }

    by_actor_rows = db.execute(
        _apply_filters(
            select(
                AdminStarsGrant.actor_id,
                func.count(),
                func.coalesce(func.sum(AdminStarsGrant.amount), 0),
            ).group_by(AdminStarsGrant.actor_id)
        )
    ).all()
    by_actor: list[dict[str, Any]] = []
    for actor_id, cnt, stars in by_actor_rows:
        actor = db.get(User, actor_id) if actor_id else None
        by_actor.append(
            {
                "actor_id": str(actor_id) if actor_id else None,
                "username": actor.username if actor else None,
                "count": int(cnt),
                "stars": int(stars),
            }
        )

    recent_stmt = select(AdminStarsGrant).order_by(AdminStarsGrant.created_at.desc()).limit(20)
    recent_stmt = _apply_filters(recent_stmt)
    recent = db.scalars(recent_stmt).all()

    return {
        "kind": "exact",
        "source": ADMIN_GRANT_SOURCE,
        "counts_toward_revenue": False,
        "creates_iap_transactions": False,
        "excluded_from_purchased_stars": True,
        "total_stars_granted": stars_sum,
        "grant_count": grant_count,
        "recipient_count": recipient_count,
        "by_reason": by_reason,
        "by_administrator": by_actor,
        "recent": [_serialize(r) for r in recent],
        "audience": aud,
        "audience_scoped": aud != "all",
        **grant_limits_payload(),
        "note": (
            "Administrative ADD-ONLY credits. Not purchased Stars. "
            "Not Apple/Google revenue. Distinct from competition payouts and starting grants. "
            "Free-vs-paid consumption attribution remains unavailable."
        ),
    }
