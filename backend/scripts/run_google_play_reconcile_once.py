#!/usr/bin/env python3
"""One-shot Google Play financial reconcile (operator / deploy).

Default mode: hourly worker tick (advisory lock + fair cursor + persist).
Apply stays OFF unless IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY=true.

Order-scoped mode (--order-id):
  Calls the same ``google_play_reconcile.reconcile_android_purchases`` service
  the worker uses (normal ledger / clawback / audit path), under the same
  cluster advisory lock, restricted to ONE order.

  Mutations require BOTH:
    - process-local IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY_ORDER_ID == --order-id
      (set by this script only when --apply is passed; never written to host .env)
    - --authorize-apply-stars matching dry-run would_recover_stars

  Persistent IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY must remain false.
  Purchasing / credit gates are not touched.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import google_play_reconcile  # noqa: E402
from app.services.google_play_reconcile_worker import (  # noqa: E402
    _hold_cluster_lock,
    run_google_play_reconcile_tick,
)


def _preflight(order_id: str | None) -> dict:
    settings = get_settings()
    return {
        "reconcile_enabled": bool(settings.iap_google_financial_reconcile_enabled),
        "persistent_apply_gate": bool(settings.iap_google_financial_reconcile_apply),
        "purchasing": bool(getattr(settings, "iap_google_purchasing_enabled", False)),
        "credit": bool(getattr(settings, "iap_google_credit_enabled", False)),
        "limit": int(settings.iap_google_financial_reconcile_limit or 0),
        "interval_seconds": float(
            settings.iap_google_financial_reconcile_interval_seconds or 0
        ),
        "order_id": order_id,
    }


def _run_order_scoped(
    db,
    *,
    order_id: str,
    dry_run: bool,
) -> dict:
    return google_play_reconcile.reconcile_android_purchases(
        db,
        dry_run=dry_run,
        order_id=order_id,
        persist=True,
        advance_cursor=False,
        limit=1,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--order-id",
        default=None,
        help="Bound to exact Play order (GPA.…). Uses reconcile service, not fair-cursor tick.",
    )
    parser.add_argument(
        "--authorize-apply-stars",
        type=int,
        default=None,
        help="Required with --apply; must equal dry-run would_recover_stars",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply after dry-run via process-local APPLY_ORDER_ID (persistent gate stays false)",
    )
    args = parser.parse_args()
    order_id = (args.order_id or "").strip() or None

    get_settings.cache_clear()
    print(json.dumps({"phase": "preflight", **_preflight(order_id)}))

    if bool(get_settings().iap_google_financial_reconcile_apply):
        print(
            json.dumps(
                {
                    "error": "persistent_apply_gate_is_on",
                    "detail": "Refuse — unset IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY; use process-local order scope",
                }
            )
        )
        return 3

    if order_id is None:
        # Legacy / default: full worker tick (always dry-run while apply gate is false).
        if args.apply:
            print(json.dumps({"error": "apply_requires_order_id"}))
            return 2
        db = SessionLocal()
        try:
            result = run_google_play_reconcile_tick(db, force=True)
            print(json.dumps({"phase": "worker_tick", **result}, default=str))
            return 0 if not result.get("error_code") else 1
        finally:
            db.close()

    if not order_id.startswith("GPA."):
        print(json.dumps({"error": "order_id_must_start_with_GPA"}))
        return 2

    db = SessionLocal()
    try:
        with _hold_cluster_lock() as got_lock:
            if not got_lock:
                print(json.dumps({"error": "cluster_lock_held", "detail": "another reconcile owns the lock"}))
                return 7

            dry = _run_order_scoped(db, order_id=order_id, dry_run=True)
            print(json.dumps({"phase": "dry_run", **dry}, default=str))

            if not args.apply:
                return 0

            if args.authorize_apply_stars is None:
                print(json.dumps({"error": "authorize_apply_stars_required_for_apply"}))
                return 2
            if dry.get("scanned") != 1:
                print(json.dumps({"error": "expected_exactly_one_purchase", "scanned": dry.get("scanned")}))
                return 4
            decision = (dry.get("decisions") or [{}])[0]
            if decision.get("decision") != "recover_full":
                print(json.dumps({"error": "not_recover_full", "decision": decision}))
                return 5
            would = int(decision.get("would_recover_stars") or dry.get("stars_would_recover") or 0)
            if would <= 0 or would != int(args.authorize_apply_stars):
                print(
                    json.dumps(
                        {
                            "error": "authorize_stars_mismatch",
                            "would_recover_stars": would,
                            "authorized": int(args.authorize_apply_stars),
                        }
                    )
                )
                return 6

            # Process-local scoped authorization — never write host .env.
            os.environ["IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY_ORDER_ID"] = order_id
            os.environ["IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY"] = "false"
            get_settings.cache_clear()

            applied = _run_order_scoped(db, order_id=order_id, dry_run=False)
            print(json.dumps({"phase": "apply", **applied}, default=str))

            os.environ.pop("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY_ORDER_ID", None)
            get_settings.cache_clear()
            post = _run_order_scoped(db, order_id=order_id, dry_run=True)
            print(json.dumps({"phase": "post_dry_run", **post}, default=str))

            gate = bool(get_settings().iap_google_financial_reconcile_apply)
            ok = (
                int(applied.get("stars_recovered") or 0) == int(args.authorize_apply_stars)
                and int(post.get("stars_would_recover") or 0) == 0
                and not gate
                and applied.get("scoped_apply_order_id") == order_id
                and applied.get("dry_run") is False
            )
            print(
                json.dumps(
                    {
                        "phase": "summary",
                        "ok": ok,
                        "stars_recovered": applied.get("stars_recovered"),
                        "post_would_recover": post.get("stars_would_recover"),
                        "persistent_apply_gate": gate,
                        "scoped_apply_order_id": applied.get("scoped_apply_order_id"),
                    }
                )
            )
            return 0 if ok else 1
    finally:
        db.close()
        os.environ.pop("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY_ORDER_ID", None)


if __name__ == "__main__":
    raise SystemExit(main())
