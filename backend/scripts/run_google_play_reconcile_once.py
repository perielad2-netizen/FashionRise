#!/usr/bin/env python3
"""One-shot Google Play financial reconcile tick (operator / deploy).

Uses the same hourly worker path (advisory lock + persist). Apply stays OFF
unless IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY=true.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.google_play_reconcile_worker import run_google_play_reconcile_tick  # noqa: E402


def main() -> int:
    settings = get_settings()
    print(
        json.dumps(
            {
                "reconcile_enabled": bool(settings.iap_google_financial_reconcile_enabled),
                "apply_enabled": bool(settings.iap_google_financial_reconcile_apply),
                "limit": int(settings.iap_google_financial_reconcile_limit or 0),
                "interval_seconds": float(
                    settings.iap_google_financial_reconcile_interval_seconds or 0
                ),
            }
        )
    )
    db = SessionLocal()
    try:
        result = run_google_play_reconcile_tick(db, force=True)
        print(json.dumps(result, default=str))
        return 0 if not result.get("error_code") else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
