import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.db.base import Base, import_models

import_models()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Set only by scripts/run_migration_smoke.py after fail-closed validation.
_SMOKE_BOUND_ENV = "ALEMBIC_SMOKE_BOUND_URL"


def get_url() -> str:
    """Resolve the Alembic database URL.

    Production / normal operator migrations use settings (DATABASE_URL / .env).
    Disposable smoke runs bind ``ALEMBIC_SMOKE_BOUND_URL`` so a prior preflight
    cannot diverge from the database Alembic actually migrates.
    """
    bound = (os.environ.get(_SMOKE_BOUND_ENV) or "").strip()
    if bound:
        from app.core.test_db_guard import (
            UnsafeTestDatabaseError,
            assert_safe_test_database_url,
            urls_point_to_same_database,
        )

        # Re-validate inside the Alembic process (still no production fallback).
        try:
            cleaned = assert_safe_test_database_url(
                bound,
                app_database_url=os.environ.get("DATABASE_URL_APP_SNAPSHOT"),
                require_env_name=_SMOKE_BOUND_ENV,
            )
        except UnsafeTestDatabaseError as exc:
            raise SystemExit(f"Refusing Alembic smoke URL: {exc}") from exc
        # DATABASE_URL must have been forced to the same identity by the runner.
        ambient = (os.environ.get("DATABASE_URL") or "").strip()
        if not ambient or not urls_point_to_same_database(cleaned, ambient):
            raise SystemExit(
                "Refusing Alembic smoke: ALEMBIC_SMOKE_BOUND_URL does not match DATABASE_URL"
            )
        return cleaned
    return get_settings().database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
