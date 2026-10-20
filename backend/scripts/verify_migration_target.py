"""Assert a disposable Alembic target before upgrade/downgrade smoke runs.

Usage:
  DATABASE_URL_TEST=postgresql+psycopg2://…/fashionrise_mig_v3b \\
    python scripts/verify_migration_target.py

Exits non-zero without connecting when the URL is missing, production-like,
or equal to DATABASE_URL / settings.database_url.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.test_db_guard import UnsafeTestDatabaseError, assert_safe_test_database_url  # noqa: E402


def main() -> None:
    test_url = os.environ.get("DATABASE_URL_TEST") or os.environ.get("ALEMBIC_SMOKE_DATABASE_URL")
    app_url = os.environ.get("DATABASE_URL")
    try:
        cleaned = assert_safe_test_database_url(
            test_url,
            app_database_url=app_url,
            require_env_name="DATABASE_URL_TEST",
        )
    except UnsafeTestDatabaseError as exc:
        print(f"UNSAFE migration target: {exc}", file=sys.stderr)
        sys.exit(2)
    # Do not print the full URL (may contain credentials); only the safety verdict.
    print("migration_target=safe")
    print(f"database_name_ok=yes")
    # Expose cleaned URL to callers via exit 0 only; they already have DATABASE_URL_TEST.
    _ = cleaned


if __name__ == "__main__":
    main()
