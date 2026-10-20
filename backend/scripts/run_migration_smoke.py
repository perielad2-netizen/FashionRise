"""Guarded Alembic smoke runner for disposable test databases only.

Binds validation and execution to the **same** explicit URL so a passing
preflight cannot be followed by `alembic` against `backend/.env` production.

Usage (from backend/):

  DATABASE_URL_TEST=postgresql+psycopg2://…/fashionrise_mig_v3b \\
    python scripts/run_migration_smoke.py upgrade head

  DATABASE_URL_TEST=…/fashionrise_mig_v3b \\
    python scripts/run_migration_smoke.py downgrade 003

  DATABASE_URL_TEST=…/fashionrise_mig_v3b \\
    python scripts/run_migration_smoke.py upgrade 004

Never use this script for production migrations. Production continues to use
the normal approved `alembic upgrade/downgrade` path with DATABASE_URL /
backend/.env after independent PM authorization.

This module validates URLs without opening a database connection. The child
Alembic process is the first connection attempt.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.test_db_guard import (  # noqa: E402
    UnsafeTestDatabaseError,
    assert_safe_test_database_url,
    database_name_from_url,
    urls_point_to_same_database,
)

# Child alembic/env.py reads this and refuses any other target while set.
SMOKE_BOUND_ENV = "ALEMBIC_SMOKE_BOUND_URL"


def resolve_smoke_database_url(
    *,
    env: dict[str, str] | None = None,
) -> str:
    """Resolve and validate the disposable smoke URL. No DB connection."""
    environ = env if env is not None else os.environ
    test_url = environ.get("DATABASE_URL_TEST") or environ.get("ALEMBIC_SMOKE_DATABASE_URL")
    app_url = environ.get("DATABASE_URL")
    # If DATABASE_URL is unset, still compare against settings when available so a
    # backend/.env production URL cannot equal the smoke target unnoticed.
    if not app_url:
        try:
            from app.core.config import get_settings

            get_settings.cache_clear()
            app_url = get_settings().database_url
        except Exception:  # noqa: BLE001
            app_url = None

    return assert_safe_test_database_url(
        test_url,
        app_database_url=app_url,
        require_env_name="DATABASE_URL_TEST",
    )


def build_smoke_child_env(validated_url: str, *, base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Build a child process env that forces Alembic onto the validated URL only."""
    child = dict(base_env if base_env is not None else os.environ)
    # Snapshot any ambient app URL for mismatch detection inside env.py.
    ambient_app = child.get("DATABASE_URL")
    if ambient_app and urls_point_to_same_database(ambient_app, validated_url):
        raise UnsafeTestDatabaseError(
            "Refusing smoke migration: ambient DATABASE_URL matches the smoke target."
        )
    if ambient_app:
        child["DATABASE_URL_APP_SNAPSHOT"] = ambient_app
    # Force both the settings source and the smoke-bound override to the same URL.
    child["DATABASE_URL"] = validated_url
    child[SMOKE_BOUND_ENV] = validated_url
    # Do not let a stale ALEMBIC_SMOKE_DATABASE_URL diverge from the bound target.
    child["DATABASE_URL_TEST"] = validated_url
    child["ALEMBIC_SMOKE_DATABASE_URL"] = validated_url
    return child


def run_alembic_smoke(alembic_args: list[str], *, env: dict[str, str] | None = None) -> int:
    """Validate, then exec alembic with the bound URL. Returns process exit code."""
    if not alembic_args:
        raise SystemExit("Provide an alembic command, e.g. upgrade head")

    validated = resolve_smoke_database_url(env=env)
    child_env = build_smoke_child_env(validated, base_env=env)
    # Re-assert identity equality before spawn (no connection).
    if not urls_point_to_same_database(child_env[SMOKE_BOUND_ENV], child_env["DATABASE_URL"]):
        raise UnsafeTestDatabaseError("Internal error: smoke-bound URL drifted from DATABASE_URL")

    name = database_name_from_url(validated)
    print(f"migration_smoke_target_db={name}", flush=True)
    print("migration_smoke_bound=yes", flush=True)
    print(f"migration_smoke_alembic_args={' '.join(alembic_args)}", flush=True)

    backend_root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "alembic", *alembic_args]
    completed = subprocess.run(cmd, cwd=str(backend_root), env=child_env, check=False)
    return int(completed.returncode)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Alembic against an explicit disposable DATABASE_URL_TEST only. "
            "Not for production migrations."
        )
    )
    parser.add_argument(
        "alembic_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to `python -m alembic` (e.g. upgrade head)",
    )
    args = parser.parse_args(argv)
    alembic_args = list(args.alembic_args)
    if alembic_args and alembic_args[0] == "--":
        alembic_args = alembic_args[1:]
    try:
        code = run_alembic_smoke(alembic_args)
    except UnsafeTestDatabaseError as exc:
        print(f"UNSAFE migration smoke target: {exc}", file=sys.stderr)
        sys.exit(2)
    sys.exit(code)


if __name__ == "__main__":
    main()
