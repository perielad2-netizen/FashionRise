"""Unit tests for test-database fail-closed guards. No database connections."""

from __future__ import annotations

import pytest

from app.core.test_db_guard import (
    UnsafeTestDatabaseError,
    assert_safe_test_database_url,
    database_name_from_url,
    urls_point_to_same_database,
)


def test_database_name_parsing():
    assert (
        database_name_from_url(
            "postgresql+psycopg2://user:pass@localhost:5432/fashionrise_test"
        )
        == "fashionrise_test"
    )


def test_rejects_missing_url():
    with pytest.raises(UnsafeTestDatabaseError, match="DATABASE_URL_TEST"):
        assert_safe_test_database_url(None)
    with pytest.raises(UnsafeTestDatabaseError, match="DATABASE_URL_TEST"):
        assert_safe_test_database_url("   ")


def test_rejects_production_names():
    for name in ("fashionrise_beta", "fashionrise", "postgres"):
        with pytest.raises(UnsafeTestDatabaseError, match="forbidden"):
            assert_safe_test_database_url(
                f"postgresql+psycopg2://u:p@localhost:5432/{name}"
            )


def test_rejects_names_without_disposable_marker():
    with pytest.raises(UnsafeTestDatabaseError, match="test', 'qa', or 'mig'"):
        assert_safe_test_database_url(
            "postgresql+psycopg2://u:p@localhost:5432/fashionrise_prod_copy"
        )


def test_rejects_same_database_as_application_url():
    test = "postgresql+psycopg2://u:p@db.example:5432/fashionrise_test"
    app = "postgresql+psycopg2://other:x@db.example:5432/fashionrise_test"
    assert urls_point_to_same_database(test, app)
    with pytest.raises(UnsafeTestDatabaseError, match="same database"):
        assert_safe_test_database_url(test, app_database_url=app)


def test_accepts_explicit_disposable_test_db_different_from_app():
    test = "postgresql+psycopg2://u:p@localhost:5432/fashionrise_test"
    app = "postgresql+psycopg2://u:p@localhost:5432/fashionrise_beta"
    assert (
        assert_safe_test_database_url(test, app_database_url=app) == test
    )


def test_accepts_qa_and_mig_names():
    assert_safe_test_database_url(
        "postgresql+psycopg2://u:p@localhost:5432/fashionrise_v3a_qa",
        app_database_url="postgresql+psycopg2://u:p@localhost:5432/fashionrise_beta",
    )
    assert_safe_test_database_url(
        "postgresql+psycopg2://u:p@localhost:5432/fashionrise_mig_v3b",
        app_database_url="postgresql+psycopg2://u:p@localhost:5432/fashionrise_beta",
    )
