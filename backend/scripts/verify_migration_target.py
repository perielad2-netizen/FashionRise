"""Validate a disposable Alembic smoke target without connecting.

Prefer the bound runner for actual migrations:

  DATABASE_URL_TEST=postgresql+psycopg2://…/fashionrise_mig_v3b \\
    python scripts/run_migration_smoke.py upgrade head

This script only checks the URL. It does **not** prove a subsequent bare
`alembic` command will use the same database — use ``run_migration_smoke.py``
for that.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.test_db_guard import UnsafeTestDatabaseError  # noqa: E402


def _load_runner():
    path = _BACKEND_ROOT / "scripts" / "run_migration_smoke.py"
    spec = importlib.util.spec_from_file_location("run_migration_smoke", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    runner = _load_runner()
    try:
        cleaned = runner.resolve_smoke_database_url()
    except UnsafeTestDatabaseError as exc:
        print(f"UNSAFE migration target: {exc}", file=sys.stderr)
        sys.exit(2)
    print("migration_target=safe")
    print("database_name_ok=yes")
    print(
        "note=Use scripts/run_migration_smoke.py to execute Alembic against this URL; "
        "a standalone preflight does not bind bare `alembic`."
    )
    _ = cleaned


if __name__ == "__main__":
    main()
