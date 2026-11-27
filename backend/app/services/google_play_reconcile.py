"""Google Play financial reconciliation (orders.get + entitlement).

RTDN and voidedpurchases.list are useful but incomplete: Google documents that
refund-only flows (no revoke) may emit neither. This module uses:

  - ``orders.get`` for financial state (REFUNDED / PARTIAL / PENDING_REFUND / …)
  - ``purchases.products.get`` for entitlement (purchaseState)

Stars recovery requires **authoritative full-refund evidence** (state REFUNDED
**and** a full refundEvent with refundDetails.total) **and** canceled/404
entitlement, plus identity match (order id, purchase token, product id).

Dry-run is the default. Apply mode reuses ``google_rtdn._clawback_purchase`` +
purchase-token advisory locks. Failed/ignored reconcile rows do **not**
permanently suppress future recovery attempts.

Hourly scheduling (cluster lock, last-run, backoff, fair cursor) lives in
``google_play_reconcile_worker`` — Admin overview reads **persisted** runs /
findings only (no live Play calls on page load).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, ServiceUnavailableError
from app.models.google_play_reconcile import (
    GooglePlayReconcileCursor,
    GooglePlayReconcileFinding,
    GooglePlayReconcileRun,
)
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
    "skip_identity",
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
    stars_recovered: int = 0
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


def has_authoritative_full_refund(order: google_iap.GooglePlayOrder) -> bool:
    """Require explicit full-refund evidence — not merely a refundEvent or ambiguous state."""
    if (order.state or "").upper() != "REFUNDED":
        return False
    if not order.has_full_refund_event:
        return False
    # refundDetails.total must be present (units and/or nanos).
    if order.refund_total_units is None and order.refund_total_nanos is None:
        return False
    return True


def validate_order_identity(
    purchase: IapPurchase, order: google_iap.GooglePlayOrder
) -> tuple[bool, str]:
    """Match returned order identity to the stored purchase. Fail closed on gaps."""
    stored_order = (purchase.transaction_id or "").strip()
    returned_order = (order.order_id or "").strip()
    if not stored_order or not returned_order or stored_order != returned_order:
        return False, "order_id_mismatch"

    stored_token = (purchase.purchase_token or "").strip()
    returned_token = (order.purchase_token or "").strip() if order.purchase_token else ""
    if not returned_token:
        return False, "order_missing_purchase_token"
    if not stored_token or stored_token != returned_token:
        return False, "purchase_token_mismatch"

    stored_product = (purchase.product_id or "").strip()
    if not order.product_ids:
        return False, "order_missing_product_ids"
    if stored_product not in order.product_ids:
        return False, "product_id_mismatch"
    return True, "ok"


def classify_recovery(
    *,
    order: google_iap.GooglePlayOrder | None,
    entitlement: Entitlement,
    stars_outstanding: int,
    identity_ok: bool = True,
    identity_reason: str | None = None,
) -> tuple[Decision, str]:
    """Map Play financial + entitlement state to an explicit recovery decision."""
    if stars_outstanding <= 0:
        return "already_recovered", "no_outstanding_stars"

    if order is None:
        return "skip_no_order", "missing_order_id"

    if not identity_ok:
        return "skip_identity", identity_reason or "identity_mismatch"

    state = (order.state or "").upper()
    if state == "PENDING_REFUND":
        return "wait", "order_pending_refund"
    if state == "PARTIALLY_REFUNDED" or order.has_partial_refund_events:
        return "review", "partial_refund_requires_review"
    if state == "PENDING":
        return "wait", "order_pending"

    # Ambiguous: refundEvent without REFUNDED, or REFUNDED without full evidence.
    # Checked before PROCESSED/ok so a contradictory refundEvent never looks healthy.
    if order.has_full_refund_event and state != "REFUNDED":
        return "review", "refund_event_without_refunded_state"
    if state == "REFUNDED" and not has_authoritative_full_refund(order):
        return "review", "refunded_missing_authoritative_refund_total"

    if state in ("PROCESSED",):
        return "ok", "order_processed_active"
    if state == "CANCELED" and order.has_cancellation_event and not order.has_full_refund_event:
        return "review", "order_canceled_before_process"

    if has_authoritative_full_refund(order):
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


def inspect_purchase(
    db: Session, purchase: IapPurchase, *, provider_requests: list[int] | None = None
) -> ReconcileDecision:
    """Read-only classification for one Android purchase row."""
    credited = int(purchase.stars_credited or 0)
    clawed = int(purchase.stars_clawed_back or 0)
    outstanding = max(0, credited - clawed)
    order_id = (purchase.transaction_id or "").strip() or None
    token = (purchase.purchase_token or "").strip()

    def _bump() -> None:
        if provider_requests is not None:
            provider_requests[0] += 1

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
            _bump()
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

    identity_ok, identity_reason = validate_order_identity(purchase, order)
    if not identity_ok:
        return ReconcileDecision(
            **base,
            order_state=order.state,
            entitlement="unknown",
            decision="skip_identity",
            reason=identity_reason,
            refund_reason=order.refund_reason,
            refund_total_currency=order.refund_total_currency,
            refund_total_units=_money_units(order.refund_total_units, order.refund_total_nanos),
            would_recover_stars=0,
        )

    _bump()
    entitlement, _meta = _read_entitlement(purchase.product_id, token)
    decision, reason = classify_recovery(
        order=order,
        entitlement=entitlement,
        stars_outstanding=outstanding,
        identity_ok=True,
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


def _clear_non_applied_reconcile_row(db: Session, message_id: str) -> None:
    """Failed/ignored/received rows must not permanently suppress future recovery."""
    existing = db.scalar(
        select(IapGoogleNotification).where(IapGoogleNotification.message_id == message_id)
    )
    if existing is None:
        return
    if existing.processing_state == "applied":
        return
    db.delete(existing)
    db.flush()


def _evidence_still_valid(purchase: IapPurchase) -> tuple[bool, str, google_iap.GooglePlayOrder | None]:
    """Re-validate orders.get + entitlement at apply time under the caller's session."""
    order_id = (purchase.transaction_id or "").strip()
    token = (purchase.purchase_token or "").strip()
    if not order_id or not token:
        return False, "missing_identity", None
    try:
        order = google_iap.get_order(order_id)
    except Exception as exc:  # noqa: BLE001
        return False, f"orders_get_recheck:{type(exc).__name__}", None
    ok, reason = validate_order_identity(purchase, order)
    if not ok:
        return False, reason, order
    if not has_authoritative_full_refund(order):
        return False, "full_refund_evidence_invalid_at_apply", order
    entitlement, _ = _read_entitlement(purchase.product_id, token)
    if entitlement not in ("canceled", "not_found"):
        return False, f"entitlement_not_canceled_at_apply:{entitlement}", order
    return True, "ok", order


def apply_recovery(db: Session, purchase: IapPurchase, decision: ReconcileDecision) -> ReconcileDecision:
    """Apply ``recover_full`` via existing clawback engine. Reports **actual** Stars recovered."""
    if decision.decision != "recover_full" or decision.would_recover_stars <= 0:
        return decision

    token = (purchase.purchase_token or "").strip()
    message_id = f"orders-reconcile:{token}"
    existing = db.scalar(
        select(IapGoogleNotification).where(IapGoogleNotification.message_id == message_id)
    )
    if existing is not None and existing.processing_state == "applied":
        return _with_decision(
            decision,
            decision="already_recovered",
            reason="orders_reconcile_already_applied",
            would_recover_stars=0,
            stars_recovered=0,
            applied=False,
            notification_state=existing.processing_state,
        )
    # Allow retry after failed / ignored / received — do not permanently suppress.
    _clear_non_applied_reconcile_row(db, message_id)

    db.refresh(purchase)
    credited = int(purchase.stars_credited or 0)
    clawed_before = int(purchase.stars_clawed_back or 0)
    if credited - clawed_before <= 0:
        return _with_decision(
            decision,
            decision="already_recovered",
            reason="already_clawed",
            stars_clawed_back=clawed_before,
            stars_outstanding=0,
            would_recover_stars=0,
            stars_recovered=0,
        )

    valid, why, _order = _evidence_still_valid(purchase)
    if not valid:
        return _with_decision(
            decision,
            decision="skip_error" if why.startswith("orders_get") else "review",
            reason=f"apply_recheck:{why}",
            would_recover_stars=0,
            stars_recovered=0,
            applied=False,
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
            stars_recovered=0,
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
    db.refresh(purchase)
    clawed_after = int(purchase.stars_clawed_back or 0)
    actual = max(0, clawed_after - clawed_before)
    return _with_decision(
        decision,
        applied=row.processing_state == "applied" and actual > 0,
        notification_state=row.processing_state,
        stars_clawed_back=clawed_after,
        stars_outstanding=max(0, credited - clawed_after),
        stars_recovered=actual if row.processing_state == "applied" else 0,
        would_recover_stars=actual if row.processing_state == "applied" else decision.would_recover_stars,
        reason=(
            decision.reason
            if row.processing_state == "applied"
            else f"clawback_{row.processing_state}"
        ),
    )


def _upsert_finding(db: Session, purchase: IapPurchase, decision: ReconcileDecision) -> None:
    existing = db.scalar(
        select(GooglePlayReconcileFinding).where(
            GooglePlayReconcileFinding.iap_purchase_id == purchase.id
        )
    )
    now = datetime.now(timezone.utc)
    payload = {
        "order_id": decision.order_id,
        "environment": decision.environment,
        "decision": decision.decision,
        "reason": decision.reason,
        "order_state": decision.order_state,
        "entitlement": decision.entitlement,
        "stars_outstanding": decision.stars_outstanding,
        "stars_recovered": int(decision.stars_recovered or 0),
        "refund_total_currency": decision.refund_total_currency,
        "refund_total_units": decision.refund_total_units,
        "detail": {
            "would_recover_stars": decision.would_recover_stars,
            "applied": decision.applied,
            "notification_state": decision.notification_state,
            "purchase_status": decision.purchase_status,
        },
        "inspected_at": now,
        "updated_at": now,
    }
    if existing is None:
        db.add(
            GooglePlayReconcileFinding(
                id=uuid.uuid4(),
                iap_purchase_id=purchase.id,
                **payload,
            )
        )
    else:
        for key, value in payload.items():
            setattr(existing, key, value)


def _load_cursor(db: Session) -> GooglePlayReconcileCursor:
    row = db.get(GooglePlayReconcileCursor, 1)
    if row is None:
        row = GooglePlayReconcileCursor(id=1)
        db.add(row)
        db.flush()
    return row


def _select_fair_batch(
    db: Session, *, cap: int, purchase_id: uuid.UUID | None, order_id: str | None
) -> list[IapPurchase]:
    """Bounded batch with durable cursor so older outstanding rows are eventually scanned."""
    if purchase_id is not None:
        row = db.get(IapPurchase, purchase_id)
        return [row] if row and row.platform == "android" else []
    if order_id:
        rows = list(
            db.scalars(
                select(IapPurchase).where(
                    IapPurchase.platform == "android",
                    IapPurchase.transaction_id == order_id.strip(),
                )
            ).all()
        )
        return rows[:cap]

    cursor = _load_cursor(db)
    base = (
        select(IapPurchase)
        .where(
            IapPurchase.platform == "android",
            IapPurchase.stars_credited > IapPurchase.stars_clawed_back,
        )
        .order_by(IapPurchase.created_at.asc(), IapPurchase.id.asc())
    )

    after = base
    if cursor.last_purchase_created_at is not None and cursor.last_purchase_id is not None:
        after = after.where(
            or_(
                IapPurchase.created_at > cursor.last_purchase_created_at,
                and_(
                    IapPurchase.created_at == cursor.last_purchase_created_at,
                    IapPurchase.id > cursor.last_purchase_id,
                ),
            )
        )

    rows = list(db.scalars(after.limit(cap)).all())
    if len(rows) < cap:
        # Wrap: continue from the oldest outstanding purchases.
        wrap = list(db.scalars(base.limit(cap - len(rows))).all())
        seen = {r.id for r in rows}
        for r in wrap:
            if r.id not in seen:
                rows.append(r)

    if rows:
        last = rows[-1]
        cursor.last_purchase_created_at = last.created_at
        cursor.last_purchase_id = last.id
        cursor.updated_at = datetime.now(timezone.utc)
    return rows


def reconcile_android_purchases(
    db: Session,
    *,
    dry_run: bool = True,
    limit: int = 100,
    purchase_id: uuid.UUID | None = None,
    order_id: str | None = None,
    persist: bool = True,
    advance_cursor: bool = True,
) -> dict[str, Any]:
    """Bounded scan of credited Android purchases. Default is read-only dry-run."""
    if not google_iap.google_iap_configured():
        raise ServiceUnavailableError("Google Play service account not configured")

    cap = max(1, min(int(limit or 100), 200))
    if purchase_id is not None or order_id or not advance_cursor:
        if purchase_id is not None:
            rows = _select_fair_batch(db, cap=cap, purchase_id=purchase_id, order_id=None)
        elif order_id:
            rows = _select_fair_batch(db, cap=cap, purchase_id=None, order_id=order_id)
        else:
            rows = list(
                db.scalars(
                    select(IapPurchase)
                    .where(
                        IapPurchase.platform == "android",
                        IapPurchase.stars_credited > 0,
                    )
                    .order_by(IapPurchase.created_at.desc())
                    .limit(cap)
                ).all()
            )
    else:
        rows = _select_fair_batch(db, cap=cap, purchase_id=None, order_id=None)

    decisions: list[ReconcileDecision] = []
    counts: dict[str, int] = {}
    recovered = 0
    would_recover = 0
    unresolved: list[dict[str, Any]] = []
    provider_requests = [0]
    sandbox_scanned = 0
    production_scanned = 0

    settings = get_settings()
    apply_enabled = bool(getattr(settings, "iap_google_financial_reconcile_apply", False))
    scoped_order = (
        getattr(settings, "iap_google_financial_reconcile_apply_order_id", "") or ""
    ).strip()
    requested_order = (order_id or "").strip()
    # Process-local scoped apply: exact order_id env + matching order_id= arg.
    # Does NOT enable the persistent reconcile apply gate.
    scoped_apply = bool(
        scoped_order
        and requested_order
        and scoped_order == requested_order
        and purchase_id is None
    )
    if not dry_run and not apply_enabled and not scoped_apply:
        dry_run = True  # fail closed — never mutate unless apply or scoped order
    if not dry_run and scoped_apply and not apply_enabled:
        # Hard scope: only the authorized order row may be present.
        if len(rows) != 1 or (rows[0].transaction_id or "").strip() != requested_order:
            dry_run = True
            _log.error(
                "scoped_apply_refused order=%s rows=%s",
                requested_order,
                [getattr(r, "transaction_id", None) for r in rows],
            )

    for purchase in rows:
        env = (purchase.environment or "").strip().lower()
        if env == "sandbox":
            sandbox_scanned += 1
        else:
            production_scanned += 1
        decision = inspect_purchase(db, purchase, provider_requests=provider_requests)
        if not dry_run and decision.decision == "recover_full":
            decision = apply_recovery(db, purchase, decision)
            if decision.applied:
                recovered += int(decision.stars_recovered or 0)
        would_recover += int(decision.would_recover_stars or 0)
        decisions.append(decision)
        counts[decision.decision] = counts.get(decision.decision, 0) + 1
        if decision.decision in ("review", "skip_error", "wait", "skip_identity"):
            unresolved.append(decision.as_dict())
        if persist:
            _upsert_finding(db, purchase, decision)

    if persist:
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            _log.exception("reconcile_findings_commit_failed")
            db.rollback()

    return {
        "ok": True,
        "dry_run": dry_run,
        "apply_enabled": apply_enabled,
        "scoped_apply_order_id": requested_order if (scoped_apply and not dry_run) else None,
        "scanned": len(decisions),
        "provider_requests": provider_requests[0],
        "counts": counts,
        "stars_recovered": recovered if not dry_run else 0,
        "stars_would_recover": would_recover,
        "sandbox_scanned": sandbox_scanned,
        "production_scanned": production_scanned,
        "unresolved": unresolved,
        "decisions": [d.as_dict() for d in decisions],
    }


def record_reconcile_run(
    db: Session,
    *,
    status: str,
    dry_run: bool,
    report: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    meta: dict[str, Any] | None = None,
    started_at: datetime | None = None,
) -> GooglePlayReconcileRun:
    """Persist a reconcile run for Admin overview (no live Play calls needed later)."""
    now = datetime.now(timezone.utc)
    started = started_at or now
    report = report or {}
    run = GooglePlayReconcileRun(
        id=uuid.uuid4(),
        status=status,
        started_at=started,
        finished_at=now,
        dry_run=dry_run,
        scanned=int(report.get("scanned") or 0),
        provider_requests=int(report.get("provider_requests") or 0),
        stars_would_recover=int(report.get("stars_would_recover") or 0),
        stars_recovered=int(report.get("stars_recovered") or 0),
        sandbox_scanned=int(report.get("sandbox_scanned") or 0),
        production_scanned=int(report.get("production_scanned") or 0),
        error_code=error_code,
        error_detail=(error_detail or "")[:2000] or None,
        counts=dict(report.get("counts") or {}),
        meta=meta or {},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def admin_reconciliation_snapshot(db: Session, *, sample_limit: int = 25) -> dict[str, Any]:
    """Admin financial intelligence from **persisted** runs/findings only (no live Play APIs)."""
    apply_enabled = bool(
        getattr(get_settings(), "iap_google_financial_reconcile_apply", False)
    )
    enabled = bool(
        getattr(get_settings(), "iap_google_financial_reconcile_enabled", True)
    )
    last_success = db.scalar(
        select(GooglePlayReconcileRun)
        .where(GooglePlayReconcileRun.status.in_(("success", "partial")))
        .order_by(GooglePlayReconcileRun.started_at.desc())
        .limit(1)
    )
    last_any = db.scalar(
        select(GooglePlayReconcileRun)
        .order_by(GooglePlayReconcileRun.started_at.desc())
        .limit(1)
    )

    def _env_bucket(env_label: str) -> dict[str, Any]:
        env_filter = GooglePlayReconcileFinding.environment.ilike(env_label)
        if env_label.lower() == "production":
            env_filter = or_(
                GooglePlayReconcileFinding.environment.ilike("production"),
                GooglePlayReconcileFinding.environment.is_(None),
                and_(
                    GooglePlayReconcileFinding.environment.is_not(None),
                    ~GooglePlayReconcileFinding.environment.ilike("sandbox"),
                ),
            )
        scanned = int(
            db.scalar(
                select(func.count())
                .select_from(GooglePlayReconcileFinding)
                .where(env_filter)
            )
            or 0
        )
        confirmed = int(
            db.scalar(
                select(func.count())
                .select_from(GooglePlayReconcileFinding)
                .where(
                    env_filter,
                    GooglePlayReconcileFinding.decision.in_(
                        ("recover_full", "already_recovered")
                    ),
                    GooglePlayReconcileFinding.order_state.ilike("REFUNDED"),
                )
            )
            or 0
        )
        recovered = int(
            db.scalar(
                select(func.coalesce(func.sum(GooglePlayReconcileFinding.stars_recovered), 0)).where(
                    env_filter
                )
            )
            or 0
        )
        unresolved = int(
            db.scalar(
                select(func.count())
                .select_from(GooglePlayReconcileFinding)
                .where(
                    env_filter,
                    GooglePlayReconcileFinding.decision.in_(
                        ("review", "wait", "skip_error", "skip_identity")
                    ),
                )
            )
            or 0
        )
        errors = int(
            db.scalar(
                select(func.count())
                .select_from(GooglePlayReconcileFinding)
                .where(
                    env_filter,
                    GooglePlayReconcileFinding.decision == "skip_error",
                )
            )
            or 0
        )
        return {
            "scanned_purchases": scanned,
            "confirmed_refunds": confirmed,
            "recovered_stars": recovered,
            "unresolved_discrepancies": unresolved,
            "errors": errors,
        }

    unresolved_sample = [
        {
            "purchase_id": str(f.iap_purchase_id),
            "order_id": f.order_id,
            "environment": f.environment,
            "decision": f.decision,
            "reason": f.reason,
            "order_state": f.order_state,
            "entitlement": f.entitlement,
            "stars_outstanding": f.stars_outstanding,
            "inspected_at": f.inspected_at.isoformat() if f.inspected_at else None,
        }
        for f in db.scalars(
            select(GooglePlayReconcileFinding)
            .where(
                GooglePlayReconcileFinding.decision.in_(
                    ("review", "wait", "skip_error", "skip_identity", "recover_full")
                )
            )
            .order_by(GooglePlayReconcileFinding.updated_at.desc())
            .limit(max(1, min(int(sample_limit or 25), 50)))
        ).all()
    ]

    last_failed = db.scalar(
        select(GooglePlayReconcileRun)
        .where(GooglePlayReconcileRun.status == "failed")
        .order_by(GooglePlayReconcileRun.started_at.desc())
        .limit(1)
    )
    fail_streak = 0
    if last_failed is not None:
        meta = last_failed.meta if isinstance(last_failed.meta, dict) else {}
        fail_streak = max(0, int(meta.get("fail_streak") or 0))
        # If a later success exists, streak is cleared for operators.
        if last_success is not None and last_success.started_at >= last_failed.started_at:
            fail_streak = 0

    skipped_lock = int(
        db.scalar(
            select(func.count())
            .select_from(GooglePlayReconcileRun)
            .where(GooglePlayReconcileRun.status == "skipped_lock")
        )
        or 0
    )
    skipped_backoff = int(
        db.scalar(
            select(func.count())
            .select_from(GooglePlayReconcileRun)
            .where(GooglePlayReconcileRun.status == "skipped_backoff")
        )
        or 0
    )

    outstanding_purchases = int(
        db.scalar(
            select(func.count())
            .select_from(IapPurchase)
            .where(
                IapPurchase.platform == "android",
                IapPurchase.stars_credited > IapPurchase.stars_clawed_back,
            )
        )
        or 0
    )
    outstanding_stars = int(
        db.scalar(
            select(
                func.coalesce(
                    func.sum(IapPurchase.stars_credited - IapPurchase.stars_clawed_back),
                    0,
                )
            ).where(
                IapPurchase.platform == "android",
                IapPurchase.stars_credited > IapPurchase.stars_clawed_back,
            )
        )
        or 0
    )
    review_pending = int(
        db.scalar(
            select(func.count())
            .select_from(GooglePlayReconcileFinding)
            .where(GooglePlayReconcileFinding.decision == "review")
        )
        or 0
    )
    recover_full_pending = int(
        db.scalar(
            select(func.count())
            .select_from(GooglePlayReconcileFinding)
            .where(GooglePlayReconcileFinding.decision == "recover_full")
        )
        or 0
    )
    from app.models.user import User

    debt_users = int(
        db.scalar(select(func.count()).select_from(User).where(User.ai_stars_iap_debt > 0))
        or 0
    )
    debt_stars = int(
        db.scalar(select(func.coalesce(func.sum(User.ai_stars_iap_debt), 0))) or 0
    )

    settings = get_settings()
    interval = float(
        getattr(settings, "iap_google_financial_reconcile_interval_seconds", 3600) or 3600
    )
    limit = int(getattr(settings, "iap_google_financial_reconcile_limit", 50) or 50)

    return {
        "kind": "persisted",
        "source": "postgresql",
        "reconcile_enabled": enabled,
        "dry_run": True if last_success is None else bool(last_success.dry_run),
        "apply_enabled": apply_enabled,
        "scheduler": {
            "interval_seconds": interval,
            "batch_limit": limit,
            "cluster_lock_key": "0x46524953_47505243",
        },
        "last_successful_sync_at": (
            last_success.started_at.isoformat() if last_success else None
        ),
        "last_successful_sync": (
            {
                "id": str(last_success.id),
                "status": last_success.status,
                "started_at": last_success.started_at.isoformat(),
                "finished_at": (
                    last_success.finished_at.isoformat() if last_success.finished_at else None
                ),
                "dry_run": last_success.dry_run,
                "scanned": last_success.scanned,
                "provider_requests": last_success.provider_requests,
                "stars_would_recover": last_success.stars_would_recover,
                "stars_recovered": last_success.stars_recovered,
                "sandbox_scanned": last_success.sandbox_scanned,
                "production_scanned": last_success.production_scanned,
                "counts": last_success.counts,
            }
            if last_success
            else None
        ),
        "last_failed_sync": (
            {
                "id": str(last_failed.id),
                "status": last_failed.status,
                "started_at": last_failed.started_at.isoformat(),
                "error_code": last_failed.error_code,
                # Never include purchase tokens or credentials in operator snapshots.
                "error_detail": (last_failed.error_detail or "")[:200] or None,
                "fail_streak": int(
                    (last_failed.meta or {}).get("fail_streak") or 0
                )
                if isinstance(last_failed.meta, dict)
                else 0,
            }
            if last_failed
            else None
        ),
        "consecutive_failures": fail_streak,
        "last_run": (
            {
                "id": str(last_any.id),
                "status": last_any.status,
                "started_at": last_any.started_at.isoformat(),
                "error_code": last_any.error_code,
                "dry_run": last_any.dry_run,
            }
            if last_any
            else None
        ),
        "backlog": {
            "android_purchases_with_outstanding_stars": outstanding_purchases,
            "outstanding_stars": outstanding_stars,
            "findings_recover_full": recover_full_pending,
            "findings_review": review_pending,
            "wallet_debt_users": debt_users,
            "wallet_debt_stars": debt_stars,
            "skipped_lock_runs": skipped_lock,
            "skipped_backoff_runs": skipped_backoff,
        },
        "sandbox": _env_bucket("Sandbox"),
        "production": _env_bucket("Production"),
        "unresolved_sample": unresolved_sample,
        "note": (
            "Admin overview reads persisted reconcile runs/findings only — "
            "no orders.get / products.get on page load. "
            "Sandbox and Production are separated. "
            "Mutations require IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY=true. "
            "Alerts must never include purchase tokens or service-account material."
        ),
        "authority": ["orders.get", "purchases.products.get"],
    }
