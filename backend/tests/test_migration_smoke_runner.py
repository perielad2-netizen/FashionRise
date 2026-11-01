"""No-DB tests: migration smoke runner binds Alembic to the validated URL only."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from app.core.test_db_guard import UnsafeTestDatabaseError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = BACKEND_ROOT / "scripts" / "run_migration_smoke.py"


def _load_runner():
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    spec = importlib.util.spec_from_file_location("run_migration_smoke_under_test", RUNNER_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_resolve_rejects_missing_url_without_connecting():
    runner = _load_runner()
    with pytest.raises(UnsafeTestDatabaseError, match="DATABASE_URL_TEST"):
        runner.resolve_smoke_database_url(env={})


def test_resolve_rejects_production_name_without_connecting():
    runner = _load_runner()
    with pytest.raises(UnsafeTestDatabaseError, match="forbidden"):
        runner.resolve_smoke_database_url(
            env={
                "DATABASE_URL_TEST": "postgresql+psycopg2://u:p@localhost:5432/fashionrise_beta",
                "DATABASE_URL": "postgresql+psycopg2://u:p@localhost:5432/other_test",
            }
        )


def test_resolve_rejects_same_as_app_database_without_connecting():
    runner = _load_runner()
    url = "postgresql+psycopg2://u:p@localhost:5432/fashionrise_test"
    with pytest.raises(UnsafeTestDatabaseError, match="same database"):
        runner.resolve_smoke_database_url(
            env={"DATABASE_URL_TEST": url, "DATABASE_URL": url}
        )


def test_build_child_env_forces_bound_url_over_ambient_app():
    """A misleading ambient DATABASE_URL (prod) must not remain the Alembic target."""
    runner = _load_runner()
    validated = "postgresql+psycopg2://u:p@localhost:5432/fashionrise_mig_v3b"
    ambient_prod = "postgresql+psycopg2://u:p@localhost:5432/fashionrise_beta"
    child = runner.build_smoke_child_env(
        validated,
        base_env={
            "DATABASE_URL": ambient_prod,
            "PATH": "/usr/bin",
            "HOME": "/tmp",
        },
    )
    assert child["DATABASE_URL"] == validated
    assert child[runner.SMOKE_BOUND_ENV] == validated
    assert child["DATABASE_URL_APP_SNAPSHOT"] == ambient_prod
    assert child["DATABASE_URL"] != ambient_prod


def test_run_alembic_smoke_refuses_before_spawn_when_url_unsafe(monkeypatch):
    runner = _load_runner()
    spawned = []

    def fake_run(*args, **kwargs):  # noqa: ANN001
        spawned.append((args, kwargs))
        raise AssertionError("subprocess must not run for unsafe URLs")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    with pytest.raises(UnsafeTestDatabaseError):
        runner.run_alembic_smoke(
            ["upgrade", "head"],
            env={
                "DATABASE_URL_TEST": "postgresql+psycopg2://u:p@localhost:5432/fashionrise_beta",
                "DATABASE_URL": "postgresql+psycopg2://u:p@localhost:5432/fashionrise_test",
            },
        )
    assert spawned == []


def test_run_alembic_smoke_passes_bound_url_to_child(monkeypatch):
    runner = _load_runner()
    captured = {}

    class Result:
        returncode = 0

    def fake_run(cmd, cwd=None, env=None, check=False):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["env"] = env
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    validated = "postgresql+psycopg2://u:p@localhost:5432/fashionrise_mig_v3b"
    code = runner.run_alembic_smoke(
        ["upgrade", "head"],
        env={
            "DATABASE_URL_TEST": validated,
            "DATABASE_URL": "postgresql+psycopg2://u:p@localhost:5432/fashionrise_beta",
            "PATH": "/usr/bin",
        },
    )
    assert code == 0
    assert captured["env"]["DATABASE_URL"] == validated
    assert captured["env"][runner.SMOKE_BOUND_ENV] == validated
    assert captured["cmd"][:3] == [sys.executable, "-m", "alembic"]
    assert captured["cmd"][3:] == ["upgrade", "head"]
