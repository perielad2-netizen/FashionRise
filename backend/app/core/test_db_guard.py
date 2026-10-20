"""Fail-closed guards that keep destructive tests off production databases.

These helpers parse URLs only — they never open a database connection.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

# Exact names that must never receive create_all/drop_all from the test harness.
FORBIDDEN_DATABASE_NAMES = frozenset(
    {
        "fashionrise_beta",
        "fashionrise",
        "postgres",
        "template0",
        "template1",
    }
)

_SAFE_NAME_RE = re.compile(r"(test|qa|mig)", re.IGNORECASE)


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when a test/migration target is missing, ambiguous, or production-like."""


def _strip_sqlalchemy_driver(url: str) -> str:
    # postgresql+psycopg2://… → postgresql://…
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "+" in scheme:
        scheme = scheme.split("+", 1)[0]
    return f"{scheme}://{rest}"


def database_name_from_url(url: str) -> str:
    parsed = urlparse(_strip_sqlalchemy_driver(url.strip()))
    path = unquote(parsed.path or "").lstrip("/")
    if not path:
        return ""
    return path.split("/", 1)[0]


def normalize_database_identity(url: str) -> tuple[str, str, str]:
    """Return (scheme, host:port, database_name) for equality checks."""
    parsed = urlparse(_strip_sqlalchemy_driver(url.strip()))
    host = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = f"{host}:{port}" if port else host
    return ((parsed.scheme or "").lower(), netloc, database_name_from_url(url).lower())


def urls_point_to_same_database(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return normalize_database_identity(left) == normalize_database_identity(right)


def assert_safe_test_database_url(
    test_url: str | None,
    *,
    app_database_url: str | None = None,
    require_env_name: str = "DATABASE_URL_TEST",
) -> str:
    """Validate a disposable test/migration database URL without connecting.

    Rules:
    - Explicit URL required (no silent fallback to the app database).
    - Database name must look disposable (contains test / qa / mig).
    - Reject known production names including fashionrise_beta.
    - Reject equality with the configured application DATABASE_URL.
    """
    if test_url is None or not str(test_url).strip():
        raise UnsafeTestDatabaseError(
            f"{require_env_name} must be set to an explicit disposable test database. "
            "Refusing to fall back to DATABASE_URL / settings."
        )

    cleaned = str(test_url).strip()
    name = database_name_from_url(cleaned)
    if not name:
        raise UnsafeTestDatabaseError(
            f"{require_env_name} must include a database name in the URL path."
        )

    lowered = name.lower()
    if lowered in FORBIDDEN_DATABASE_NAMES:
        raise UnsafeTestDatabaseError(
            f"Refusing destructive tests against forbidden database name {name!r}."
        )

    if not _SAFE_NAME_RE.search(name):
        raise UnsafeTestDatabaseError(
            f"Test database name {name!r} must include 'test', 'qa', or 'mig' "
            "so it cannot be mistaken for production."
        )

    if app_database_url and str(app_database_url).strip():
        if urls_point_to_same_database(cleaned, str(app_database_url).strip()):
            raise UnsafeTestDatabaseError(
                f"{require_env_name} must not point at the same database as the application DATABASE_URL."
            )

    return cleaned
