"""Manual / offline Create My Croquis retention sweeper.

Stage A: do NOT install as a production timer. Default is dry-run (zero writes).

Usage (from backend/):

  DATABASE_URL_TEST=postgresql+psycopg2://…/fashionrise_test \\
    python scripts/run_croquis_retention_sweep.py --dry-run

  DATABASE_URL_TEST=… \\
    python scripts/run_croquis_retention_sweep.py --apply --batch-size 25

Never point at production without separate PM authorization.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.test_db_guard import (
    UnsafeTestDatabaseError,
    assert_safe_test_database_url,
)
from app.db.base import import_models
from app.services.personal_croquis_retention import run_retention_sweep


def main() -> int:
    parser = argparse.ArgumentParser(description="Create My Croquis retention sweep (offline)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Examine eligibility only; roll back all writes (default)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform bounded cleanup writes (overrides --dry-run)",
    )
    parser.add_argument("--batch-size", type=int, default=None)
    args = parser.parse_args()
    dry_run = not args.apply

    test_url = os.environ.get("DATABASE_URL_TEST")
    try:
        url = assert_safe_test_database_url(
            test_url,
            app_database_url=os.environ.get("DATABASE_URL"),
            require_env_name="DATABASE_URL_TEST",
        )
    except UnsafeTestDatabaseError as exc:
        print(f"Refusing to run: {exc}", file=sys.stderr)
        return 2

    import_models()
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        result = run_retention_sweep(db, dry_run=dry_run, batch_size=args.batch_size)
        print(
            json.dumps(
                {
                    "dry_run": result.dry_run,
                    "examined": result.examined,
                    "eligible_abandoned": result.eligible_abandoned,
                    "eligible_source_expiry": result.eligible_source_expiry,
                    "eligible_accepted_source": result.eligible_accepted_source,
                    "queue_processed": result.queue_processed,
                    "bytes_unlinked": result.bytes_unlinked,
                    "failures": result.failures,
                    "asset_ids_touched_count": len(result.asset_ids_touched),
                },
                indent=2,
            )
        )
    finally:
        db.close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
