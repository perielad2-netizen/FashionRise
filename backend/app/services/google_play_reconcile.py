"""Google Play financial reconciliation (orders.get + entitlement).

RTDN and voidedpurchases.list are useful but incomplete: Google documents that
refund-only flows (no revoke) may emit neither. This module uses:

  - ``orders.get`` for financial state (REFUNDED / PARTIAL / PENDING_REFUND / …)
  - ``purchases.products.get`` for entitlement (purchaseState)

Stars recovery rules (explicit):

  - Full refund (order REFUNDED + refundEvent) **and** entitlement canceled/404
    → recover unrecovered Stars via existing clawback engine.
  - Full refund but entitlement still Purchased → ``review`` (refund without revoke).
  - PARTIALLY_REFUNDED / PENDING_REFUND / ambiguous → ``review`` (never blind deduct).
  - Transport / auth / timeout / missing data → ``skip_error`` (never deduct).

Dry-run is the default for operator inspection. Apply mode reuses
``google_rtdn._clawback_purchase`` + purchase-token advisory locks + durable
``message_id`` idempotency so a later RTDN cannot double-claw.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, ServiceUnavailableError
from app.models.iap_google_notification import IapGoogleNotification
from app.models.iap_purchase import IapPurchase
from app.services import google_iap, google_rtdn

_log = logging.getLogger(__name__)

Decision = Literal[
    "ok",
    "recover_full",
    "already_recovered",
    "review",
    "wait",
    "skip_error",
    "skip_no_token",
    "skip_no_order",
]

Entitlement = Literal["purchased", "canceled", "pending", "not_found", "unknown", "error"]


@dataclass(frozen=True)
class ReconcileDecision:
    purchase_id: str
    order_id: str | None
    product_id: str
    environment: str | None
    stars_credited: int
    stars_clawed_back: int
    stars_outstanding: int
    purchase_status: str
    order_state: str | None
    entitlement: Entitlement
    decision: Decision
    reason: str
    refund_reason: str | None = None
    refund_total_currency: str | None = None
    refund_total_units: str | None = None
    would_recover_stars: int = 0
    applied: bool = False
    notification_state: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _money_units(units: str | None, nanos: int | None) -> str | None:
    if units is None and nanos is None:
        return None
    u = units or "0"
    if nanos:
        return f"{u}.{abs(int(nanos)):09d}".rstrip("0").rstrip(".")
    return u


def classify_recovery(
    *,
    order: google_iap.GooglePlayOrder | None,
    entitlement: Entitlement,
    stars_outstanding: int,
) -> tuple[Decision, str]:
    """Map Play financial + entitlement state to an explicit recovery decision."""
    if stars_outstanding <= 0:
        return "already_recovered", "no_outstanding_stars"

    if order is None:
        return "skip_no_order", "missing_order_id"

    state = (order.state or "").upper()
    if state == "PENDING_REFUND":
        return "wait", "order_pending_refund"
    if state == "PARTIALLY_REFUNDED" or order.has_partial_refund_events:
        return "review", "partial_refund_requires_review"
    if state == "PENDING":
        return "wait", "order_pending"
    if state in ("PROCESSED",):
        return "ok", "order_processed_active"
    if state == "CANCELED" and order.has_cancellation_event and not order.has_full_refund_event:
        # Canceled before settlement — should not have been credited; if credited, review.
        return "review", "order_canceled_before_process"
    if state == "REFUNDED" or order.has_full_refund_event:
        if entitlement in ("canceled", "not_found"):
            return "recover_full", "full_refund_and_entitlement_canceled"
        if entitlement == "purchased":
            return "review", "full_refund_without_entitlement_revoke"
        if entitlement == "pending":
            return "wait", "refunded_but_entitlement_pending"
        if entitlement == "error":
            return "skip_error", "entitlement_lookup_failed"
        return "review", f"refunded_entitlement_{entitlement}"
    if state in ("STATE_UNSPECIFIED", ""):
        return "skip_error", "order_state_unspecified"
    return "review", f"unhandled_order_state_{state}"


def _read_entitlement(product_id: str, purchase_token: str) -> tuple[Entitlement, dict[str, Any]]:
    try:
        verified = google_iap.verify_product_purchase(
            product_id=product_id, purchase_token=purchase_token
        )
    except ForbiddenError as exc:
        if "not found" in str(exc).lower():
            return "not_found", {"error": "not_found"}
        return "error", {"error": str(exc)}
    except ServiceUnavailableError as exc:
        return "error", {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        _log.exception("entitlement_lookup_unexpected")
        return "error", {"error": type(exc).__name__}

    if google_iap.is_canceled(verified):
        return "canceled", {"purchase_state": verified.purchase_state}
    if google_iap.is_pending(verified):
        return "pending", {"purchase_state": verified.purchase_state}
    if google_iap.is_purchased(verified):
        return "purchased", {"purchase_state": verified.purchase_state}
    return "unknown", {"purchase_state": verified.purchase_state}


def inspect_purchase(db: Session, purchase: IapPurchase) -> ReconcileDecision:
    """Read-only classification for one Android purchase row."""
    credited = int(purchase.stars_credited or 0)
    clawed = int(purchase.stars_clawed_back or 0)
    outstanding = max(0, credited - clawed)
    order_id = (purchase.transaction_id or "").strip() or None
    token = (purchase.purchase_token or "").strip()

    base = dict(
        purchase_id=str(purchase.id),
        order_id=order_id,
        product_id=purchase.product_id,
        environment=purchase.environment,
        stars_credited=credited,
        stars_clawed_back=clawed,
        stars_outstanding=outstanding,
        purchase_status=str(purchase.status),
    )

    if outstanding <= 0:
        return ReconcileDecision(
            **base,
            order_state=None,
            entitlement="unknown",
            decision="already_recovered",
            reason="no_outstanding_stars",
            would_recover_stars=0,
        )

    if not token:
        return ReconcileDecision(
            **base,
            order_state=None,
            entitlement="unknown",
            decision="skip_no_token",
            reason="missing_purchase_token",
            would_recover_stars=0,
        )

    order: google_iap.GooglePlayOrder | None = None
    if order_id:
        try:
            order = google_iap.get_order(order_id)
        except ForbiddenError as exc:
            return ReconcileDecision(
                **base,
                order_state=None,
                entitlement="unknown",
                decision="skip_error",
                reason=f"orders_get_forbidden:{exc}",
                would_recover_stars=0,
            )
        except ServiceUnavailableError as exc:
            return ReconcileDecision(
                **base,
                order_state=None,
                entitlement="unknown",
                decision="skip_error",
                reason=f"orders_get_unavailable:{exc}",
                would_recover_stars=0,
            )
        except Exception as exc:  # noqa: BLE001
            _log.exception("orders_get_unexpected")
            return ReconcileDecision(
                **base,
                order_state=None,
                entitlement="unknown",
                decision="skip_error",
                reason=f"orders_get_error:{type(exc).__name__}",
                would_recover_stars=0,
            )
    else:
        decision, reason = classify_recovery(
            order=None, entitlement="unknown", stars_outstanding=outstanding
        )
        return ReconcileDecision(
            **base,
            order_state=None,
            entitlement="unknown",
            decision=decision,
            reason=reason,
            would_recover_stars=0,
        )

    entitlement, _meta = _read_entitlement(purchase.product_id, token)
    decision, reason = classify_recovery(
        order=order, entitlement=entitlement, stars_outstanding=outstanding
    )
    would = outstanding if decision == "recover_full" else 0
    return ReconcileDecision(
        **base,
        order_state=order.state,
        entitlement=entitlement,
        decision=decision,
        reason=reason,
        refund_reason=order.refund_reason,
        refund_total_currency=order.refund_total_currency,
        refund_total_units=_money_units(order.refund_total_units, order.refund_total_nanos),
        would_recover_stars=would,
    )


def _with_decision(base: ReconcileDecision, **kwargs: Any) -> ReconcileDecision:
    data = base.as_dict()
    data.update(kwargs)
    return ReconcileDecision(**data)


def apply_recovery(db: Session, purchase: IapPurchase, decision: ReconcileDecision) -> ReconcileDecision:
    """Apply ``recover_full`` via existing clawback engine. Idempotent."""
    if decision.decision != "recover_full" or decision.would_recover_stars <= 0:
        return decision

    token = (purchase.purchase_token or "").strip()
    message_id = f"orders-reconcile:{token}"
    existing = db.scalar(
        select(IapGoogleNotification).where(IapGoogleNotification.message_id == message_id)
    )
    if existing is not None:
        return _with_decision(
            decision,
            decision="already_recovered",
            reason="orders_reconcile_row_exists",
            would_recover_stars=0,
            applied=False,
            notification_state=existing.processing_state,
        )

    # Also honor prior products-canceled / RTDN clawbacks via outstanding recalculation.
    db.refresh(purchase)
    credited = int(purchase.stars_credited or 0)
    clawed = int(purchase.stars_clawed_back or 0)
    if credited - clawed <= 0:
        return _with_decision(
            decision,
            decision="already_recovered",
            reason="already_clawed",
            stars_clawed_back=clawed,
            stars_outstanding=0,
            would_recover_stars=0,
        )

    row = IapGoogleNotification(
        id=uuid.uuid4(),
        message_id=message_id,
        notification_type="orders_reconcile",
        package_name=google_iap.google_package_name(),
        purchase_token=token,
        order_id=purchase.transaction_id,
        product_id=purchase.product_id,
        processing_state="received",
        audit_meta={
            "source": "orders.get_financial_reconcile",
            "decision": decision.as_dict(),
        },
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return _with_decision(
            decision,
            decision="already_recovered",
            reason="idempotent_conflict",
            would_recover_stars=0,
        )

    google_rtdn._clawback_purchase(
        db,
        row,
        purchase,
        kind="CANCELED",
        product_id_hint=purchase.product_id,
        authoritative="products.get",
    )
    db.commit()
    return _with_decision(
        decision,
        applied=row.processing_state == "applied",
        notification_state=row.processing_state,
        reason=(
            decision.reason
            if row.processing_state == "applied"
            else f"clawback_{row.processing_state}"
        ),
    )


def reconcile_android_purchases(
    db: Session,
    *,
    dry_run: bool = True,
    limit: int = 100,
    purchase_id: uuid.UUID | None = None,
    order_id: str | None = None,
) -> dict[str, Any]:
    """Bounded scan of credited Android purchases. Default is read-only dry-run."""
    if not google_iap.google_iap_configured():
        raise ServiceUnavailableError("Google Play service account not configured")

    cap = max(1, min(int(limit or 100), 200))
    stmt = select(IapPurchase).where(IapPurchase.platform == "android")
    if purchase_id is not None:
        stmt = stmt.where(IapPurchase.id == purchase_id)
    elif order_id:
        stmt = stmt.where(IapPurchase.transaction_id == order_id.strip())
    else:
        # Prefer rows that still look financially open, plus recent refunded for audit.
        stmt = stmt.where(IapPurchase.stars_credited > 0).order_by(IapPurchase.created_at.desc())
    rows = list(db.scalars(stmt.limit(cap)).all())

    decisions: list[ReconcileDecision] = []
    counts: dict[str, int] = {}
    recovered = 0
    unresolved: list[dict[str, Any]] = []

    apply_enabled = bool(
        getattr(get_settings(), "iap_google_financial_reconcile_apply", False)
    )
    if not dry_run and not apply_enabled:
        dry_run = True  # fail closed — never mutate unless apply flag is on

    for purchase in rows:
        decision = inspect_purchase(db, purchase)
        if not dry_run and decision.decision == "recover_full":
            decision = apply_recovery(db, purchase, decision)
            if decision.applied:
                recovered += int(decision.would_recover_stars or 0)
        decisions.append(decision)
        counts[decision.decision] = counts.get(decision.decision, 0) + 1
        if decision.decision in ("review", "skip_error", "wait"):
            unresolved.append(decision.as_dict())

    return {
        "ok": True,
        "dry_run": dry_run,
        "apply_enabled": apply_enabled,
        "scanned": len(decisions),
        "counts": counts,
        "stars_recovered": recovered if not dry_run else 0,
        "stars_would_recover": sum(d.would_recover_stars for d in decisions),
        "unresolved": unresolved,
        "decisions": [d.as_dict() for d in decisions],
    }


def admin_reconciliation_snapshot(db: Session, *, sample_limit: int = 25) -> dict[str, Any]:
    """Admin financial intelligence — reconciliation posture (read-only)."""
    try:
        report = reconcile_android_purchases(db, dry_run=True, limit=sample_limit)
    except ServiceUnavailableError as exc:
        return {
            "kind": "unavailable",
            "detail": str(exc),
            "apply_enabled": bool(
                getattr(get_settings(), "iap_google_financial_reconcile_apply", False)
            ),
        }

    outstanding = [
        d
        for d in report["decisions"]
        if d["decision"] in ("recover_full", "review", "wait", "skip_error")
    ]
    return {
        "kind": "estimated",
        "dry_run": True,
        "apply_enabled": report["apply_enabled"],
        "scanned": report["scanned"],
        "counts": report["counts"],
        "stars_would_recover": report["stars_would_recover"],
        "unresolved_count": len(report["unresolved"]),
        "unresolved_sample": report["unresolved"][:10],
        "recoverable_sample": [d for d in outstanding if d["decision"] == "recover_full"][:10],
        "note": (
            "orders.get financial state + products.get entitlement. "
            "Sandbox rows stay excluded from Production revenue. "
            "Mutations require IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY=true."
        ),
        "authority": ["orders.get", "purchases.products.get"],
    }
