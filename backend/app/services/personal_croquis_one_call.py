"""Create My Croquis — authorized ONE-IMAGE paid-call guards (offline / fail-closed).

Used by ``scripts/croquis_one_image_executor.py`` and zero-network unit tests.
Does not open sockets. Does not bypass Stage C spend/consent fences.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

OFFICIAL_OPENAI_BASE = "https://api.openai.com/v1"

# Exact PM-authorized one-call envelope (2026-11-01 re-review).
APPROVED_MODEL = "gpt-image-2.5-sunburst"
APPROVED_SIZE = "1024x1536"
APPROVED_QUALITY = "medium"
APPROVED_BACKGROUND = "transparent"
APPROVED_OUTPUT_FORMAT = "png"
APPROVED_N = 1
APPROVED_DESIGN_PLANE = "768x1024"
APPROVED_ESTIMATE_CENTS = 40
APPROVED_MAX_EXPOSURE_CENTS = 100
APPROVED_SPEND_CEILING_USD = 1.00
APPROVED_MAX_USD_PER_RUN = 1.00
APPROVED_MAX_USD_PER_USER_DAY = 1.00
APPROVED_ALEMBIC_REVISION = "014"

# Committed synthetic clothed cartoon only — NOT a photograph / fidelity proof.
APPROVED_FIXTURE_RELATIVE = Path("tests/fixtures/croquis/synthetic_clothed_adult_model.png")
APPROVED_FIXTURE_SHA256 = (
    "489dcb82167d858a14ff0f2c91fe2e60d42c2aeceaccfe5d368f5d0ebc28e29d"
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class OneCallGuardError(RuntimeError):
    """Authorized one-call plan mismatch — refuse before any paid HTTP."""


def approved_envelope() -> dict[str, Any]:
    return {
        "model": APPROVED_MODEL,
        "size": APPROVED_SIZE,
        "quality": APPROVED_QUALITY,
        "background": APPROVED_BACKGROUND,
        "output_format": APPROVED_OUTPUT_FORMAT,
        "n": APPROVED_N,
        "design_plane": APPROVED_DESIGN_PLANE,
        "estimate_cents": APPROVED_ESTIMATE_CENTS,
        "max_exposure_cents": APPROVED_MAX_EXPOSURE_CENTS,
        "spend_ceiling_usd": APPROVED_SPEND_CEILING_USD,
        "max_usd_per_run": APPROVED_MAX_USD_PER_RUN,
        "max_usd_per_user_day": APPROVED_MAX_USD_PER_USER_DAY,
        "fixture": str(APPROVED_FIXTURE_RELATIVE).replace("\\", "/"),
        "fixture_sha256": APPROVED_FIXTURE_SHA256,
        "openai_base_url_required": OFFICIAL_OPENAI_BASE,
        "alembic_revision_required": APPROVED_ALEMBIC_REVISION,
        "fixture_note": (
            "procedural clothed cartoon — validates integration/normalization, "
            "NOT photo fidelity"
        ),
    }


def approved_fixture_path() -> Path:
    return (BACKEND_ROOT / APPROVED_FIXTURE_RELATIVE).resolve()


def load_approved_fixture_bytes() -> bytes:
    """Load the exact committed fixture; fail closed on path/hash mismatch.

    Never regenerates bytes — a missing or altered file refuses the one-call.
    """
    path = approved_fixture_path()
    expected = (BACKEND_ROOT / APPROVED_FIXTURE_RELATIVE).resolve()
    if path != expected:
        raise OneCallGuardError(f"Fixture path resolved away from approved location: {path}")
    if not path.is_file():
        raise OneCallGuardError(f"Approved fixture missing: {path}")
    # Refuse symlink escape outside backend tests fixtures tree.
    try:
        path.relative_to((BACKEND_ROOT / "tests" / "fixtures" / "croquis").resolve())
    except ValueError as exc:
        raise OneCallGuardError(f"Fixture path outside approved fixture dir: {path}") from exc
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != APPROVED_FIXTURE_SHA256:
        raise OneCallGuardError(
            f"Fixture SHA256 mismatch: got {digest}, expected {APPROVED_FIXTURE_SHA256}"
        )
    return data


def _approx_eq(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= 1e-9


def assert_effective_one_call_settings(settings: Any) -> None:
    """Require exact effective Settings for the authorized one-call (no silent defaults)."""
    if not bool(getattr(settings, "my_croquis_ai_enabled", False)):
        raise OneCallGuardError("MY_CROQUIS_AI_ENABLED must be true for paid one-call")
    if not bool(getattr(settings, "my_croquis_ai_live_http", False)):
        raise OneCallGuardError("MY_CROQUIS_AI_LIVE_HTTP must be true for paid one-call")
    if not _approx_eq(getattr(settings, "my_croquis_ai_spend_ceiling_usd", 0), APPROVED_SPEND_CEILING_USD):
        raise OneCallGuardError(
            f"spend ceiling must be exactly ${APPROVED_SPEND_CEILING_USD:.2f}, "
            f"got {getattr(settings, 'my_croquis_ai_spend_ceiling_usd', None)!r}"
        )
    if not _approx_eq(getattr(settings, "my_croquis_ai_max_usd_per_run", 0), APPROVED_MAX_USD_PER_RUN):
        raise OneCallGuardError(
            f"max/run must be exactly ${APPROVED_MAX_USD_PER_RUN:.2f}, "
            f"got {getattr(settings, 'my_croquis_ai_max_usd_per_run', None)!r}"
        )
    if not _approx_eq(
        getattr(settings, "my_croquis_ai_max_usd_per_user_day", 0), APPROVED_MAX_USD_PER_USER_DAY
    ):
        raise OneCallGuardError(
            f"max/user/day must be exactly ${APPROVED_MAX_USD_PER_USER_DAY:.2f}, "
            f"got {getattr(settings, 'my_croquis_ai_max_usd_per_user_day', None)!r}"
        )
    if int(getattr(settings, "my_croquis_ai_max_exposure_cents", 0) or 0) != APPROVED_MAX_EXPOSURE_CENTS:
        raise OneCallGuardError(
            f"max exposure must be exactly {APPROVED_MAX_EXPOSURE_CENTS}¢, "
            f"got {getattr(settings, 'my_croquis_ai_max_exposure_cents', None)!r}"
        )
    if int(getattr(settings, "my_croquis_ai_estimate_cents", 0) or 0) != APPROVED_ESTIMATE_CENTS:
        raise OneCallGuardError(
            f"estimate must be exactly {APPROVED_ESTIMATE_CENTS}¢ (soft only), "
            f"got {getattr(settings, 'my_croquis_ai_estimate_cents', None)!r}"
        )
    model = (getattr(settings, "openai_image_model", None) or "").strip()
    if model != APPROVED_MODEL:
        raise OneCallGuardError(f"model must be {APPROVED_MODEL!r}, got {model!r}")
    size = (getattr(settings, "my_croquis_ai_image_size", None) or "").strip()
    if size != APPROVED_SIZE:
        raise OneCallGuardError(f"image size must be {APPROVED_SIZE!r}, got {size!r}")
    quality = (getattr(settings, "my_croquis_ai_image_quality", None) or "").strip().lower()
    if quality != APPROVED_QUALITY:
        raise OneCallGuardError(f"image quality must be {APPROVED_QUALITY!r}, got {quality!r}")
    if not (getattr(settings, "openai_api_key", None) or "").strip():
        raise OneCallGuardError("OPENAI_API_KEY missing for paid one-call")


def assert_official_effective_base_url(settings: Any) -> None:
    """Check effective Settings base URL (includes .env), not process env alone."""
    base = (getattr(settings, "openai_base_url", None) or "").strip()
    if not base:
        # SDK default is official api.openai.com — allowed.
        return
    if base.rstrip("/") != OFFICIAL_OPENAI_BASE.rstrip("/"):
        raise OneCallGuardError(
            f"Refusing non-official effective openai_base_url={base!r}; "
            f"one-call requires {OFFICIAL_OPENAI_BASE} or unset."
        )


def edit_kwargs_public_preview(kwargs: dict[str, Any], *, source_sha256: str) -> dict[str, Any]:
    """Operator-safe request metadata — never includes image bytes or secrets."""
    image = kwargs.get("image")
    image_kind = type(image).__name__
    # OpenAI SDK single-file form is a (filename, fileobj, mime) tuple — count as 1.
    # Multi-image form is a list of such tuples.
    if image is None:
        image_count = 0
    elif isinstance(image, list):
        image_count = len(image)
    else:
        image_count = 1
    return {
        "model": kwargs.get("model"),
        "size": kwargs.get("size"),
        "quality": kwargs.get("quality"),
        "background": kwargs.get("background"),
        "output_format": kwargs.get("output_format"),
        "n": kwargs.get("n"),
        "input_fidelity_present": "input_fidelity" in kwargs,
        "image_count": image_count,
        "image_arg_type": image_kind,
        "prompt_chars": len(str(kwargs.get("prompt") or "")),
        "source_sha256": source_sha256,
    }


def assert_edit_kwargs_match_envelope(kwargs: dict[str, Any]) -> None:
    """Refuse any request shape that does not match the authorized one-call plan."""
    if kwargs.get("model") != APPROVED_MODEL:
        raise OneCallGuardError(f"edit kwargs model mismatch: {kwargs.get('model')!r}")
    if kwargs.get("size") != APPROVED_SIZE:
        raise OneCallGuardError(
            f"edit kwargs size mismatch (no silent fallback): {kwargs.get('size')!r} "
            f"!= {APPROVED_SIZE!r}"
        )
    if kwargs.get("quality") != APPROVED_QUALITY:
        raise OneCallGuardError(
            f"edit kwargs quality mismatch (no silent upgrade/fallback): "
            f"{kwargs.get('quality')!r} != {APPROVED_QUALITY!r}"
        )
    if kwargs.get("background") != APPROVED_BACKGROUND:
        raise OneCallGuardError(f"edit kwargs background mismatch: {kwargs.get('background')!r}")
    if kwargs.get("output_format") != APPROVED_OUTPUT_FORMAT:
        raise OneCallGuardError(
            f"edit kwargs output_format mismatch: {kwargs.get('output_format')!r}"
        )
    if int(kwargs.get("n") or 0) != APPROVED_N:
        raise OneCallGuardError(f"edit kwargs n mismatch: {kwargs.get('n')!r}")
    if "input_fidelity" in kwargs:
        raise OneCallGuardError("edit kwargs must not include input_fidelity for sunburst croquis")
    image = kwargs.get("image")
    if isinstance(image, list):
        raise OneCallGuardError("edit kwargs must use exactly one image input (not a list)")
    if image is None:
        raise OneCallGuardError("edit kwargs missing image input")


def assert_alembic_revision_014(engine: Engine) -> str:
    """Require disposable DB already migrated to Alembic 014 (triggers present).

    ``Base.metadata.create_all`` alone is insufficient — refuse it.
    """
    with engine.connect() as conn:
        try:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        except Exception as exc:
            raise OneCallGuardError(
                "alembic_version missing — run alembic upgrade to 014 on an isolated "
                "disposable DB before paid one-call (create_all is not enough)"
            ) from exc
    if row is None or not row[0]:
        raise OneCallGuardError("alembic_version empty — migrate disposable DB to 014 first")
    rev = str(row[0]).strip()
    if rev != APPROVED_ALEMBIC_REVISION:
        raise OneCallGuardError(
            f"Disposable DB alembic revision must be exactly {APPROVED_ALEMBIC_REVISION!r}, "
            f"got {rev!r}"
        )
    return rev


# Path segment required in LOCAL_STORAGE_ROOT for the one-call executor.
ONE_CALL_STORAGE_MARKER = "croquis-one-call"

_FORBIDDEN_STORAGE_FRAGMENTS = (
    "/var/www",
    "/srv/fashionrise",
    "fashionrise_beta",
    "/var/lib/fashionrise",
)


def default_backend_storage_root() -> Path:
    return (BACKEND_ROOT / "data" / "storage").resolve()


def assert_dedicated_one_call_storage(settings: Any) -> Path:
    """Fail closed before any private upload / DB write.

    Requires an absolute dedicated ``local_storage_root`` containing
    ``croquis-one-call`` — never the default backend ``data/storage`` or
    production-looking paths.
    """
    raw = (getattr(settings, "local_storage_root", None) or "").strip()
    if not raw:
        raise OneCallGuardError(
            "LOCAL_STORAGE_ROOT unset — set a dedicated …/croquis-one-call… path "
            "before paid one-call"
        )
    root = Path(raw).expanduser()
    if not root.is_absolute():
        # Settings normally absolutizes relative paths under backend/ — still refuse
        # anything that resolves to the default app storage tree.
        root = Path(raw)
        if not root.is_absolute():
            raise OneCallGuardError(
                f"LOCAL_STORAGE_ROOT must be absolute for one-call, got {raw!r}"
            )
    root = root.resolve()
    default = default_backend_storage_root()
    if root == default:
        raise OneCallGuardError(
            f"Refusing default app storage root {root}"
        )
    for a, b, label in (
        (root, default, "under default app storage"),
        (default, root, "contains default app storage"),
    ):
        try:
            a.relative_to(b)
        except ValueError:
            continue
        raise OneCallGuardError(
            f"Refusing storage root {root} ({label}; default is {default})"
        )
    lowered = str(root).lower()
    for frag in _FORBIDDEN_STORAGE_FRAGMENTS:
        if frag in lowered:
            raise OneCallGuardError(
                f"Refusing production-looking storage path containing {frag!r}: {root}"
            )
    if ONE_CALL_STORAGE_MARKER not in str(root):
        raise OneCallGuardError(
            f"LOCAL_STORAGE_ROOT must contain {ONE_CALL_STORAGE_MARKER!r} "
            f"(dedicated one-call private path); got {root}"
        )
    return root


def assert_disposable_db_fresh_for_one_call(engine: Engine) -> None:
    """Refuse a reused disposable DB that already has croquis jobs/rows.

    Prevents ``run_croquis_worker_tick`` / oldest-queue claim from selecting an
    unapproved earlier source. Must run before enqueue writes.
    """
    checks = (
        (
            "SELECT COUNT(*) FROM ai_jobs WHERE job_type = 'personal_croquis_generate'",
            "personal_croquis_generate AI jobs",
        ),
        ("SELECT COUNT(*) FROM personal_croquis", "personal_croquis rows"),
        (
            "SELECT COUNT(*) FROM personal_croquis_spend_reservations",
            "personal_croquis_spend_reservations",
        ),
        ("SELECT COUNT(*) FROM personal_croquis_versions", "personal_croquis_versions"),
    )
    with engine.connect() as conn:
        for sql, label in checks:
            try:
                n = conn.execute(text(sql)).scalar()
            except Exception as exc:
                raise OneCallGuardError(
                    f"Cannot verify disposable DB freshness ({label}): {exc}"
                ) from exc
            if int(n or 0) != 0:
                raise OneCallGuardError(
                    f"Refusing reused disposable DB: {label}={n} (must be empty "
                    "before one-call enqueue)"
                )


def assert_source_asset_sha(
    *,
    storage_key: str,
    expected_sha256: str = APPROVED_FIXTURE_SHA256,
) -> str:
    """Read private croquis bytes and require the approved fixture digest."""
    from app.storage.local import LocalStorageBackend

    path = LocalStorageBackend().resolve_private_croquis_file(key=storage_key)
    if path is None or not path.is_file():
        raise OneCallGuardError(
            f"Source asset bytes missing for storage_key={storage_key!r}"
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise OneCallGuardError(
            f"Stored source SHA256 mismatch: got {digest}, expected {expected_sha256}"
        )
    return digest


def assert_only_target_croquis_job_queued(db: Any, job_id: Any) -> None:
    """After enqueue, the only queued croquis job must be the authorized one."""
    from app.models.ai_job import AIJob
    from app.models.personal_croquis import CROQUIS_GENERATE_JOB_TYPE

    queued = (
        db.query(AIJob)
        .filter(
            AIJob.job_type == CROQUIS_GENERATE_JOB_TYPE,
            AIJob.status == "queued",
        )
        .all()
    )
    if len(queued) != 1:
        raise OneCallGuardError(
            f"Expected exactly 1 queued croquis job before one-call claim, got {len(queued)}"
        )
    if queued[0].id != job_id:
        raise OneCallGuardError(
            f"Queued croquis job id {queued[0].id} != authorized job {job_id}"
        )

