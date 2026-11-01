#!/usr/bin/env python3
"""Operator-only Create My Croquis ONE-IMAGE executor (disposable DB).

Default mode is dry-run / refuse-paid. Does NOT execute a paid images.edit unless
ALL of the following are present on argv AND env (after owner approval):

  --i-approve-paid-one-call
  CONFIRM_PAID_CROQUIS_ONE_CALL=YES
  MY_CROQUIS_AI_LIVE_HTTP=true
  Exact approved Settings envelope (see personal_croquis_one_call)
  OPENAI_API_KEY set
  DATABASE_URL_TEST → disposable DB already at Alembic 014 (never fashionrise_beta)

Uses the full Stage C enqueue → claim → fence → adapter → settle/reconcile path.
Never bypasses spend reservation / consent / tripwire safeguards.
"""

from __future__ import annotations

import argparse
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
from app.services.personal_croquis_one_call import (
    APPROVED_ALEMBIC_REVISION,
    APPROVED_ESTIMATE_CENTS,
    APPROVED_MAX_EXPOSURE_CENTS,
    APPROVED_MAX_USD_PER_RUN,
    APPROVED_MAX_USD_PER_USER_DAY,
    APPROVED_QUALITY,
    APPROVED_SIZE,
    APPROVED_SPEND_CEILING_USD,
    OneCallGuardError,
    approved_envelope,
    assert_alembic_revision_014,
    assert_edit_kwargs_match_envelope,
    assert_effective_one_call_settings,
    assert_official_effective_base_url,
    edit_kwargs_public_preview,
    load_approved_fixture_bytes,
)


def _print_plan(*, paid_approved: bool) -> None:
    print("=== Create My Croquis ONE-IMAGE EXECUTOR ===")
    print(
        json.dumps(
            {
                **approved_envelope(),
                "paid_approved_flags": paid_approved,
                "live_http_env": os.environ.get("MY_CROQUIS_AI_LIVE_HTTP", ""),
                "confirm_env": os.environ.get("CONFIRM_PAID_CROQUIS_ONE_CALL", ""),
            },
            indent=2,
        )
    )


def _refuse_prod_db(url: str | None) -> str:
    safe = assert_safe_test_database_url(
        url,
        app_database_url=os.environ.get("DATABASE_URL"),
        require_env_name="DATABASE_URL_TEST",
    )
    name = database_name_from_url(safe)
    if name.lower() == "fashionrise_beta":
        raise UnsafeTestDatabaseError("Refusing production database fashionrise_beta")
    return safe


def dry_run() -> int:
    _print_plan(paid_approved=False)
    print()
    print("DRY-RUN / STOP — no DB writes, no OpenAI sockets, no paid images.edit.")
    print("To prepare a paid run AFTER owner approval, re-invoke with:")
    print("  CONFIRM_PAID_CROQUIS_ONE_CALL=YES \\")
    print("  MY_CROQUIS_AI_LIVE_HTTP=true \\")
    print("  MY_CROQUIS_AI_ENABLED=true \\")
    print(f"  MY_CROQUIS_AI_SPEND_CEILING_USD={APPROVED_SPEND_CEILING_USD:.2f} \\")
    print(f"  MY_CROQUIS_AI_MAX_USD_PER_RUN={APPROVED_MAX_USD_PER_RUN:.2f} \\")
    print(f"  MY_CROQUIS_AI_MAX_USD_PER_USER_DAY={APPROVED_MAX_USD_PER_USER_DAY:.2f} \\")
    print(f"  MY_CROQUIS_AI_MAX_EXPOSURE_CENTS={APPROVED_MAX_EXPOSURE_CENTS} \\")
    print(f"  MY_CROQUIS_AI_ESTIMATE_CENTS={APPROVED_ESTIMATE_CENTS} \\")
    print(f"  MY_CROQUIS_AI_IMAGE_SIZE={APPROVED_SIZE} \\")
    print(f"  MY_CROQUIS_AI_IMAGE_QUALITY={APPROVED_QUALITY} \\")
    print("  OPENAI_IMAGE_MODEL=gpt-image-2.5-sunburst \\")
    print("  OPENAI_API_KEY=... \\")
    print("  DATABASE_URL_TEST=postgresql+psycopg2://…/fashionrise_test \\")
    print(f"  # disposable DB must already be alembic {APPROVED_ALEMBIC_REVISION}")
    print("  python scripts/croquis_one_image_executor.py --i-approve-paid-one-call")
    print()
    print("This build still refuses paid execution until that exact flag set is present;")
    print("even then it will STOP one more time unless --execute-now is also passed.")
    return 0


def _operator_request_preview() -> dict:
    """Assemble + validate final edit kwargs against approved envelope (0 HTTP)."""
    from app.core.config import get_settings
    from app.services.personal_croquis_provider import OpenAICroquisImagesEditAdapter

    get_settings.cache_clear()
    settings = get_settings()
    assert_effective_one_call_settings(settings)
    assert_official_effective_base_url(settings)
    source = load_approved_fixture_bytes()
    adapter = OpenAICroquisImagesEditAdapter()
    kwargs = adapter.build_edit_kwargs(source)
    assert_edit_kwargs_match_envelope(kwargs)
    import hashlib

    return edit_kwargs_public_preview(
        kwargs, source_sha256=hashlib.sha256(source).hexdigest()
    )


def paid_guarded(args: argparse.Namespace) -> int:
    """Validate exact envelope; refuse unless --execute-now (still owner-gated)."""
    if os.environ.get("CONFIRM_PAID_CROQUIS_ONE_CALL") != "YES":
        print("Missing CONFIRM_PAID_CROQUIS_ONE_CALL=YES")
        return 2
    if os.environ.get("MY_CROQUIS_AI_LIVE_HTTP", "").lower() not in {"1", "true", "yes"}:
        print("MY_CROQUIS_AI_LIVE_HTTP must be true for paid path")
        return 2

    test_url = os.environ.get("DATABASE_URL_TEST")
    try:
        safe_url = _refuse_prod_db(test_url)
    except UnsafeTestDatabaseError as exc:
        print(f"Database guard: {exc}")
        return 2

    _print_plan(paid_approved=True)

    # Effective Settings (includes backend/.env) — refuse inherited high quality etc.
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert_effective_one_call_settings(settings)
        assert_official_effective_base_url(settings)
        source = load_approved_fixture_bytes()
        preview = _operator_request_preview()
    except OneCallGuardError as exc:
        print(f"ONE-CALL GUARD REFUSED: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"ONE-CALL GUARD REFUSED (unexpected): {type(exc).__name__}: {exc}")
        return 2

    print("OPERATOR_REQUEST_PREVIEW (no secrets / no image bytes):")
    print(json.dumps(preview, indent=2))
    print(f"Disposable DB ok: name={database_name_from_url(safe_url)}")
    print()
    if not args.execute_now:
        print("=== STOP — paid flags present but --execute-now not passed ===")
        print("No images.edit executed. Re-run with --execute-now only after final owner OK.")
        return 0

    # Explicit execution path — still uses Stage C services (no bypass).
    os.environ.setdefault("TESTING", "false")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password
    from app.db.base import import_models
    from app.models.ai_job import AIJob
    from app.models.personal_croquis import CROQUIS_GENERATE_JOB_TYPE
    from app.models.personal_croquis_spend import PersonalCroquisSpendReservation
    from app.models.private_media_asset import PrivateMediaAsset
    from app.models.user import User
    from app.services import personal_croquis_generate as pcg
    from app.services import personal_croquis_service as pcs
    from app.services.personal_croquis_worker import run_croquis_worker_tick
    from app.storage.local import LocalStorageBackend
    from tests.croquis_test_fixtures import (
        SYNTHETIC_ADULTS_NOTICE,
        SYNTHETIC_AI_NOTICE,
        SYNTHETIC_STORAGE_NOTICE,
        adults_body,
        ai_body,
        storage_body,
    )

    # Notices only — spend/image envelope already asserted from process Settings.
    os.environ["MY_CROQUIS_ADULTS_NOTICE_TEXT"] = SYNTHETIC_ADULTS_NOTICE
    os.environ["MY_CROQUIS_STORAGE_NOTICE_TEXT"] = SYNTHETIC_STORAGE_NOTICE
    os.environ["MY_CROQUIS_AI_NOTICE_TEXT"] = SYNTHETIC_AI_NOTICE
    os.environ["MY_CROQUIS_UPLOAD_ENABLED"] = "true"
    get_settings.cache_clear()

    import_models()
    engine = create_engine(safe_url, pool_pre_ping=True)
    try:
        rev = assert_alembic_revision_014(engine)
    except OneCallGuardError as exc:
        print(f"Migration guard: {exc}")
        engine.dispose()
        return 2
    print(f"Alembic revision ok: {rev}")

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        # Re-assert fixture immediately before upload (tamper window).
        source = load_approved_fixture_bytes()
        # Re-assert final kwargs immediately before enqueue/worker (no silent drift).
        preview = _operator_request_preview()
        print("PRE_SUBMIT_REQUEST_PREVIEW:")
        print(json.dumps(preview, indent=2))

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
            raw=source,
            declared_content_type="image/png",
            storage_consent_id=storage.id,
            display_name="synthetic-one-call",
        )
        ai_payload = ai_body(croquis_id=str(croquis.id))
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

        res = (
            db.query(PersonalCroquisSpendReservation)
            .filter(PersonalCroquisSpendReservation.version_id == ver.id)
            .one_or_none()
        )
        job = (
            db.query(AIJob)
            .filter(
                AIJob.job_type == CROQUIS_GENERATE_JOB_TYPE,
                AIJob.user_id == user.id,
            )
            .order_by(AIJob.created_at.desc())
            .first()
        )
        result_data = dict(job.result_data or {}) if job is not None else {}
        private_preview_path = None
        private_storage_key = None
        if ver.generated_asset_id is not None:
            asset = db.get(PrivateMediaAsset, ver.generated_asset_id)
            if asset is not None:
                private_storage_key = asset.storage_key
                resolved = LocalStorageBackend().resolve_private_croquis_file(
                    key=asset.storage_key
                )
                private_preview_path = str(resolved) if resolved is not None else None

        evidence = {
            "version_status": ver.status,
            "generated_asset_id": str(ver.generated_asset_id) if ver.generated_asset_id else None,
            "provider_job_id": result_data.get("provider_job_id"),
            "cost_usage_source": result_data.get("cost_usage_source"),
            "cost_cents_settled": result_data.get("cost_cents_settled"),
            "reservation_status": getattr(res, "status", None),
            "provider_called": getattr(res, "provider_called", None),
            "actual_cost_cents": getattr(res, "actual_cost_cents", None),
            "estimate_cents": getattr(res, "estimate_cents", None),
            "error_detail": getattr(res, "error_detail", None),
            "private_storage_key": private_storage_key,
            "private_preview_path": private_preview_path,
            "request_preview": preview,
            "note": (
                "Reservation/estimate is NOT a provider hard cap. "
                "Reconcile provider_job_id + usage against OpenAI account billing independently. "
                "Preview path is private local storage — never a public URL."
            ),
        }
        print("AUDIT_EVIDENCE")
        print(json.dumps(evidence, indent=2, default=str))
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
