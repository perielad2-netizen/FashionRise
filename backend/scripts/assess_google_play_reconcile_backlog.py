#!/usr/bin/env python3
"""Read-only Android IAP + reconcile backlog assessment (no Play fan-out, no mutations).

Usage (VPS):
  cd /opt/fashionrise/src/backend
  sudo -u fashionriseapp env PYTHONPATH=/opt/fashionrise/src/backend \\
    /opt/fashionrise/.venv/bin/python scripts/assess_google_play_reconcile_backlog.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.services import google_play_reconcile

    get_settings.cache_clear()
    settings = get_settings()
    db = SessionLocal()
    try:
        purchases = dict(
            db.execute(
                text(
                    """
                    select
                      count(*) as total,
                      count(*) filter (where status='active') as active,
                      count(*) filter (where status='refunded') as refunded,
                      count(*) filter (where status='revoked') as revoked,
                      count(*) filter (where coalesce(stars_credited,0) > coalesce(stars_clawed_back,0)) as outstanding_rows,
                      coalesce(sum(greatest(coalesce(stars_credited,0)-coalesce(stars_clawed_back,0),0)),0) as outstanding_stars,
                      count(*) filter (where lower(coalesce(environment,'')) like '%sandbox%') as sandbox,
                      count(*) filter (where lower(coalesce(environment,'')) not like '%sandbox%') as non_sandbox
                    from iap_purchases where platform='android'
                    """
                )
            ).mappings().one()
        )
        outstanding = [
            dict(r)
            for r in db.execute(
                text(
                    """
                    select transaction_id, status, product_id, environment,
                           stars_credited, stars_clawed_back,
                           greatest(stars_credited - stars_clawed_back, 0) as outstanding
                    from iap_purchases
                    where platform='android' and stars_credited > stars_clawed_back
                    order by created_at
                    limit 50
                    """
                )
            ).mappings()
        ]
        snap = google_play_reconcile.admin_reconciliation_snapshot(db, sample_limit=15)
        out = {
            "gates": {
                "reconcile_enabled": bool(settings.iap_google_financial_reconcile_enabled),
                "apply": bool(settings.iap_google_financial_reconcile_apply),
                "purchasing": bool(settings.iap_google_purchasing_enabled),
                "credit": bool(settings.iap_google_credit_enabled),
                "limit": int(settings.iap_google_financial_reconcile_limit or 0),
                "interval_seconds": float(
                    settings.iap_google_financial_reconcile_interval_seconds or 0
                ),
            },
            "purchases": purchases,
            "outstanding_sample": outstanding,
            "snapshot_backlog": snap.get("backlog"),
            "last_successful_sync_at": snap.get("last_successful_sync_at"),
            "consecutive_failures": snap.get("consecutive_failures"),
            "unresolved_sample": snap.get("unresolved_sample"),
            "note": "Read-only. No orders.get fan-out. Do not apply without PM approval.",
        }
        print(json.dumps(out, default=str, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
