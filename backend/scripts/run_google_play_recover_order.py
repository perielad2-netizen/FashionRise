#!/usr/bin/env python3
"""Targeted Google Play Stars recovery for ONE order (operator / PM-authorized).

Safety:
  - Persistent IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY stays untouched (must remain false).
  - Apply is process-local via IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY_ORDER_ID for this
    process only, and only when --order-id matches that env and --authorize-recovery-stars
    matches the dry-run would_recover amount.
  - Never scans or mutates other purchases.
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


def _run(db, *, order_id: str, dry_run: bool) -> dict:
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
    parser.add_argument("--order-id", required=True, help="Exact Play order id (GPA.…)")
    parser.add_argument(
        "--authorize-recovery-stars",
        type=int,
        default=None,
        help="Required with --apply; must equal dry-run would_recover_stars",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply after dry-run (process-local scoped auth only)",
    )
    args = parser.parse_args()
    order_id = args.order_id.strip()
    if not order_id.startswith("GPA."):
        print(json.dumps({"error": "order_id_must_start_with_GPA"}))
        return 2

    settings = get_settings()
    print(
        json.dumps(
            {
                "phase": "preflight",
                "order_id": order_id,
                "persistent_apply_gate": bool(settings.iap_google_financial_reconcile_apply),
                "purchasing": bool(getattr(settings, "iap_google_purchasing_enabled", False)),
                "credit": bool(getattr(settings, "iap_google_credit_enabled", False)),
            }
        )
    )
    if bool(settings.iap_google_financial_reconcile_apply):
        print(
            json.dumps(
                {
                    "error": "persistent_apply_gate_is_on",
                    "detail": "Refuse — unset IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY and use scoped order auth",
                }
            )
        )
        return 3

    db = SessionLocal()
    try:
        dry = _run(db, order_id=order_id, dry_run=True)
        print(json.dumps({"phase": "dry_run", **dry}, default=str))
        if not args.apply:
            return 0

        if args.authorize_recovery_stars is None:
            print(json.dumps({"error": "authorize_recovery_stars_required_for_apply"}))
            return 2
        if dry.get("scanned") != 1:
            print(json.dumps({"error": "expected_exactly_one_purchase", "scanned": dry.get("scanned")}))
            return 4
        decision = (dry.get("decisions") or [{}])[0]
        if decision.get("decision") != "recover_full":
            print(json.dumps({"error": "not_recover_full", "decision": decision}))
            return 5
        would = int(decision.get("would_recover_stars") or dry.get("stars_would_recover") or 0)
        if would != int(args.authorize_recovery_stars):
            print(
                json.dumps(
                    {
                        "error": "authorize_stars_mismatch",
                        "would_recover_stars": would,
                        "authorized": int(args.authorize_recovery_stars),
                    }
                )
            )
            return 6

        # Process-local scoped authorization — never write host .env.
        os.environ["IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY_ORDER_ID"] = order_id
        # Ensure persistent gate remains unset for this process.
        os.environ["IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY"] = "false"
        get_settings.cache_clear()

        applied = _run(db, order_id=order_id, dry_run=False)
        print(json.dumps({"phase": "apply", **applied}, default=str))

        # Exactly-once proof
        get_settings.cache_clear()
        os.environ.pop("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY_ORDER_ID", None)
        get_settings.cache_clear()
        post = _run(db, order_id=order_id, dry_run=True)
        print(json.dumps({"phase": "post_dry_run", **post}, default=str))

        # Re-read persistent gate from fresh settings (must still be false).
        get_settings.cache_clear()
        gate = bool(get_settings().iap_google_financial_reconcile_apply)
        ok = (
            int(applied.get("stars_recovered") or 0) == int(args.authorize_recovery_stars)
            and int(post.get("stars_would_recover") or 0) == 0
            and not gate
            and applied.get("scoped_apply_order_id") == order_id
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
