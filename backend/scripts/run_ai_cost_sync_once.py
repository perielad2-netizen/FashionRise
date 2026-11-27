#!/usr/bin/env python3
"""One-shot OpenAI + FASHN financial sync (force). Never prints secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.ai_cost_sync_worker import run_cost_sync_tick  # noqa: E402


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    summary = {
        "openai_cost_sync_enabled": bool(settings.openai_cost_sync_enabled),
        "fashn_credit_sync_enabled": bool(settings.fashn_credit_sync_enabled),
        "openai_admin_key_configured": bool((settings.openai_admin_api_key or "").strip()),
        "openai_billing_project_configured": bool(
            (settings.openai_billing_project_id or "").strip()
        ),
        "fashn_api_key_configured": bool((settings.fashn_api_key or "").strip()),
        "lookback_days": int(settings.openai_cost_sync_lookback_days or 0),
        "interval_seconds": float(settings.ai_cost_sync_interval_seconds or 0),
        "fashn_operator_credit_usd": float(settings.fashn_operator_credit_usd or 0),
    }
    db = SessionLocal()
    try:
        result = run_cost_sync_tick(db, force=True)
        summary["tick"] = result
    finally:
        db.close()
    print(json.dumps(summary, sort_keys=True, default=str))
    tick = summary.get("tick") or {}
    if tick.get("commit") == "failed":
        return 2
    openai = (tick.get("openai") or {}).get("status")
    fashn = (tick.get("fashn") or {}).get("status")
    if openai == "failed" or fashn == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
