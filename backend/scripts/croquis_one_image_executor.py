#!/usr/bin/env python3
"""Operator-only Create My Croquis ONE-IMAGE executor (disposable DB).

Default mode is dry-run / refuse-paid. Does NOT execute a paid images.edit unless
ALL of the following are present on argv AND env (after owner approval):

  --i-approve-paid-one-call
  CONFIRM_PAID_CROQUIS_ONE_CALL=YES
  MY_CROQUIS_AI_LIVE_HTTP=true
  OPENAI_API_KEY set
  DATABASE_URL_TEST → disposable DB (never fashionrise_beta)

Uses the full Stage C enqueue → claim → fence → adapter → settle/reconcile path.
Never bypasses spend reservation / consent / tripwire safeguards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.test_db_guard import (
    UnsafeTestDatabaseError,
    assert_safe_test_database_url,
    database_name_from_url,
)
from tests.fixtures.croquis.synthetic_adult_model import (
    SYNTHETIC_PNG_PATH,
    load_synthetic_clothed_adult_model_png,
)

OFFICIAL_OPENAI_BASE = "https://api.openai.com/v1"

# Revised PM envelope (2026-11-01): reserve the full $1.00; 40¢ soft estimate only.
ENVELOPE = {
    "model": "gpt-image-2.5-sunburst",
    "size": "1024x1536",
    "quality": "medium",
    "background": "transparent",
    "output_format": "png",
    "n": 1,
    "design_plane": "768x1024",
    "estimate_cents": 40,  # soft only — not a provider cap
    "max_exposure_cents": 100,
    "spend_ceiling_usd": 1.00,
    "max_usd_per_run": 1.00,
    "max_usd_per_user_day": 1.00,
    "fixture": str(SYNTHETIC_PNG_PATH.relative_to(ROOT)),
}


def _fixture_sha() -> str:
    return hashlib.sha256(load_synthetic_clothed_adult_model_png()).hexdigest()


def _print_plan(*, paid_approved: bool) -> None:
    print("=== Create My Croquis ONE-IMAGE EXECUTOR ===")
    print(
        json.dumps(
            {
                **ENVELOPE,
                "fixture_sha256": _fixture_sha(),
                "fixture_note": "procedural clothed cartoon — validates integration/normalization, NOT photo fidelity",
                "openai_base_url_required": OFFICIAL_OPENAI_BASE,
                "paid_approved_flags": paid_approved,
                "live_http_env": os.environ.get("MY_CROQUIS_AI_LIVE_HTTP", ""),
                "confirm_env": os.environ.get("CONFIRM_PAID_CROQUIS_ONE_CALL", ""),
            },
            indent=2,
        )
    )


def _refuse_prod_db(url: str) -> str:
    safe = assert_safe_test_database_url(
        url,
        app_database_url=os.environ.get("DATABASE_URL"),
        require_env_name="DATABASE_URL_TEST",
    )
    name = database_name_from_url(safe)
    if name.lower() == "fashionrise_beta":
        raise UnsafeTestDatabaseError("Refusing production database fashionrise_beta")
    return safe


def _assert_official_endpoint() -> None:
    base = (os.environ.get("OPENAI_BASE_URL") or "").strip()
    if base and base.rstrip("/") != OFFICIAL_OPENAI_BASE.rstrip("/"):
        raise SystemExit(
            f"Refusing non-official OPENAI_BASE_URL={base!r}; "
            f"one-call test requires {OFFICIAL_OPENAI_BASE} or unset (SDK default)."
        )


def dry_run() -> int:
    _print_plan(paid_approved=False)
    print()
    print("DRY-RUN / STOP — no DB writes, no OpenAI sockets, no paid images.edit.")
    print("To prepare a paid run AFTER owner approval, re-invoke with:")
    print("  CONFIRM_PAID_CROQUIS_ONE_CALL=YES \\")
    print("  MY_CROQUIS_AI_LIVE_HTTP=true \\")
    print("  MY_CROQUIS_AI_ENABLED=true \\")
    print("  MY_CROQUIS_AI_SPEND_CEILING_USD=1.00 \\")
    print("  MY_CROQUIS_AI_MAX_USD_PER_RUN=1.00 \\")
    print("  MY_CROQUIS_AI_MAX_USD_PER_USER_DAY=1.00 \\")
    print("  MY_CROQUIS_AI_MAX_EXPOSURE_CENTS=100 \\")
    print("  MY_CROQUIS_AI_ESTIMATE_CENTS=40 \\")
    print("  OPENAI_API_KEY=... \\")
    print("  DATABASE_URL_TEST=postgresql+psycopg2://…/fashionrise_test \\")
    print("  python scripts/croquis_one_image_executor.py --i-approve-paid-one-call")
    print()
    print("This build still refuses paid execution until that exact flag set is present;")
    print("even then it will STOP one more time unless --execute-now is also passed.")
    return 0


def paid_guarded(args: argparse.Namespace) -> int:
    """Validate envelope; refuse unless --execute-now (still owner-gated)."""
    if os.environ.get("CONFIRM_PAID_CROQUIS_ONE_CALL") != "YES":
        print("Missing CONFIRM_PAID_CROQUIS_ONE_CALL=YES")
        return 2
    if os.environ.get("MY_CROQUIS_AI_LIVE_HTTP", "").lower() not in {"1", "true", "yes"}:
        print("MY_CROQUIS_AI_LIVE_HTTP must be true for paid path")
        return 2
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        print("OPENAI_API_KEY missing")
        return 2
    _assert_official_endpoint()
    test_url = os.environ.get("DATABASE_URL_TEST")
    try:
        safe_url = _refuse_prod_db(test_url)
    except UnsafeTestDatabaseError as exc:
        print(f"Database guard: {exc}")
        return 2

    _print_plan(paid_approved=True)
    print(f"Disposable DB ok: name={database_name_from_url(safe_url)}")
    print()
    if not args.execute_now:
        print("=== STOP — paid flags present but --execute-now not passed ===")
        print("No images.edit executed. Re-run with --execute-now only after final PM OK.")
        return 0

    # Explicit execution path — still uses Stage C services (no bypass).
    # Imported lazily so dry-run never needs a live DB engine.
    os.environ.setdefault("TESTING", "false")  # allow live adapter selection
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import get_settings
    from app.core.security import hash_password
    from app.db.base import Base, import_models
    from app.models.user import User
    from app.services import personal_croquis_generate as pcg
    from app.services import personal_croquis_service as pcs
    from app.services.personal_croquis_worker import run_croquis_worker_tick
    from tests.croquis_test_fixtures import (
        SYNTHETIC_ADULTS_NOTICE,
        SYNTHETIC_AI_NOTICE,
        SYNTHETIC_STORAGE_NOTICE,
        adults_body,
        ai_body,
        storage_body,
    )

    get_settings.cache_clear()
    settings = get_settings()
    # Hard asserts on envelope (process env must match approved plan).
    if float(settings.my_croquis_ai_spend_ceiling_usd or 0) > 1.00 + 1e-9:
        print("Refusing ceiling above $1.00")
        return 2
    if int(settings.my_croquis_ai_max_exposure_cents or 0) != 100:
        print("Refusing max exposure != 100¢")
        return 2
    if float(settings.my_croquis_ai_max_usd_per_user_day or 0) != 1.00:
        print("Refusing max/user/day != $1.00")
        return 2
    if (settings.openai_image_model or "").strip() != "gpt-image-2.5-sunburst":
        print("Refusing non-sunburst model")
        return 2

    # Inject synthetic notices into env for this process only.
    os.environ["MY_CROQUIS_ADULTS_NOTICE_TEXT"] = SYNTHETIC_ADULTS_NOTICE
    os.environ["MY_CROQUIS_STORAGE_NOTICE_TEXT"] = SYNTHETIC_STORAGE_NOTICE
    os.environ["MY_CROQUIS_AI_NOTICE_TEXT"] = SYNTHETIC_AI_NOTICE
    os.environ["MY_CROQUIS_UPLOAD_ENABLED"] = "true"
    get_settings.cache_clear()
    settings = get_settings()

    import_models()
    engine = create_engine(safe_url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        email = f"croquis_one_call_{uuid.uuid4().hex[:10]}@example.invalid"
        user = User(
            email=email,
            username=f"c1_{uuid.uuid4().hex[:8]}",
            hashed_password=hash_password("not-used-in-script"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        adults_payload = adults_body()
        pcs.record_adults_attestation(db, user, **adults_payload)
        storage_payload = storage_body()
        storage = pcs.record_storage_consent(db, user, **storage_payload)
        croquis = pcs.upload_source_photo(
            db,
            user,
            raw=load_synthetic_clothed_adult_model_png(),
            declared_content_type="image/png",
            storage_consent_id=storage.id,
            display_name="synthetic-one-call",
        )
        ai_payload = ai_body(croquis_id=str(croquis.id))
        # Service expects UUID croquis_id kw, not string in body helper alone.
        ai = pcs.record_ai_consent(
            db,
            user,
            acknowledged=bool(ai_payload["acknowledged"]),
            adults_attested=bool(ai_payload["adults_attested"]),
            notice_version=str(ai_payload["notice_version"]),
            notice_text_hash=str(ai_payload["notice_text_hash"]),
            croquis_id=croquis.id,
        )
        ver = pcg.enqueue_personal_croquis_generate(
            db,
            user,
            croquis.id,
            ai_consent_id=ai.id,
            idempotency_key=f"one-call-{uuid.uuid4().hex}",
        )
        print(f"enqueued version_id={ver.id} status={ver.status}")
        n = run_croquis_worker_tick(db, limit=1)
        print(f"worker_tick processed={n}")
        db.refresh(ver)
        from app.models.personal_croquis_spend import PersonalCroquisSpendReservation

        res = (
            db.query(PersonalCroquisSpendReservation)
            .filter(PersonalCroquisSpendReservation.version_id == ver.id)
            .one_or_none()
        )
        evidence = {
            "version_status": ver.status,
            "generated_asset_id": str(ver.generated_asset_id) if ver.generated_asset_id else None,
            "reservation_status": getattr(res, "status", None),
            "provider_called": getattr(res, "provider_called", None),
            "actual_cost_cents": getattr(res, "actual_cost_cents", None),
            "estimate_cents": getattr(res, "estimate_cents", None),
            "error_detail": getattr(res, "error_detail", None),
            "note": "Invoice/token usage must be verified independently; reservation is not a provider hard cap.",
        }
        print("AUDIT_EVIDENCE")
        print(json.dumps(evidence, indent=2))
        return 0
    finally:
        db.close()
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--i-approve-paid-one-call",
        action="store_true",
        help="Acknowledge owner-approved paid one-call envelope (still needs env confirm).",
    )
    parser.add_argument(
        "--execute-now",
        action="store_true",
        help="Actually run enqueue/worker against disposable DB (requires paid flags).",
    )
    args = parser.parse_args(argv)
    if not args.i_approve_paid_one_call:
        return dry_run()
    return paid_guarded(args)


if __name__ == "__main__":
    raise SystemExit(main())
