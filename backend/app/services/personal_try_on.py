"""Personal Try On Person — enqueue + worker completion.

Freeze garment artwork + croquis/source binding at enqueue. Resolve the original
photograph on the server from the owner's accepted croquis version. Spend uses
``PersonalCroquisSpendReservation`` under the same operator ceilings as croquis
generate (idempotency keys prefixed ``try_on:``).
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.personal_croquis import VERSION_STATUS_ACCEPTED
from app.models.personal_croquis_spend import (
    RESERVATION_OPEN,
    RESERVATION_RECONCILIATION,
    RESERVATION_RELEASED,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.models.private_media_asset import KIND_CROQUIS_SOURCE
from app.models.user import User
from app.models.user_consent_event import PURPOSE_TRY_ON_PERSON, UserConsentEvent
from app.services import personal_croquis_service as pcs
from app.services.fashn_garment_fidelity import (
    assert_structural_fidelity,
    compute_silhouette_features,
    recommend_fashn_category,
)
from app.services.fashn_garment_prep import (
    PieceCategory,
    prep_from_approved_product_pieces,
    prepare_garment_reference,
)
from app.services.fashn_garment_realism import (
    GARMENT_REALISM_JOB_TYPE,
    GARMENT_REALISM_PROMPT_VERSION,
    GARMENT_REALISM_PROVIDER_ID,
    OpenAIGarmentRealismAdapter,
    decode_data_url_png,
    downscale_studio_context,
    estimate_garment_realism_cents,
)
from app.services.fashn_try_on_provider import (
    FASHN_CONSENT_VERSION,
    FASHN_NOTICE_TEXT,
    FASHN_PROMPT_VERSION,
    FASHN_PROVIDER_ID,
    estimate_fashn_cost_cents,
    fashn_configured,
    fashn_live_armed,
    fashn_notice_text_hash,
)
from app.services.garment_leg_geometry import (
    analyze_lower_garment_geometry,
    RESULT_KIND_OPENAI_TRY_ON_PHOTO,
    merge_openai_design_hints,
    openai_trouser_design_hints,
    soft_try_on_structure_review,
)
from app.services.personal_croquis_generate import (
    _count_generations_today,
    _lock_spend_tx,
    _sum_billable_cents,
    resolve_max_exposure_cents,
)
from app.services.personal_croquis_provider import (
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
)
from app.services.personal_try_on_provider import (
    TRY_ON_CONSENT_VERSION,
    TRY_ON_JOB_TYPE,
    TRY_ON_NOTICE_TEXT,
    TRY_ON_PROMPT_VERSION,
    TRY_ON_USER_MODERATION_MESSAGE,
    TRY_ON_USER_PROVIDER_REJECT_MESSAGE,
    estimate_try_on_cost_cents,
    get_try_on_provider,
    try_on_notice_text_hash,
)

TRY_ON_PROVIDER_OPENAI = "openai"
TRY_ON_PROVIDER_FASHN = "fashn"
from app.storage.local import LocalStorageBackend

_DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$", re.DOTALL | re.IGNORECASE)
_BILLABLE = (RESERVATION_OPEN, RESERVATION_SETTLED, RESERVATION_RECONCILIATION)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _require_ai_gate() -> None:
    settings = get_settings()
    if not settings.my_croquis_ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create My Croquis AI is not enabled (required for Try On Person).",
        )


def _decode_garment_png(data_url: str) -> bytes:
    raw = (data_url or "").strip()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork is required.")
    m = _DATA_URL_RE.match(raw)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garment artwork must be a PNG/JPEG/WebP data URL.",
        )
    try:
        blob = base64.b64decode(m.group(2), validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork base64 is invalid."
        ) from exc
    if len(blob) < 32:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork is empty.")
    max_bytes = int(get_settings().max_upload_size_mb or 8) * 1024 * 1024
    if len(blob) > max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork is too large.")
    # Fail closed if not a real PNG with alpha-capable content for try-on identity.
    from PIL import Image

    try:
        with Image.open(io.BytesIO(blob)) as img:
            img.load()
            if img.width < 8 or img.height < 8:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork is too small."
                )
            # Convert to PNG bytes for provider.
            out = io.BytesIO()
            img.convert("RGBA").save(out, format="PNG")
            return out.getvalue()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork could not be decoded."
        ) from exc


def _normalize_provider(raw: str | None, *, strict: bool = True) -> str:
    name = (raw or TRY_ON_PROVIDER_OPENAI).strip().lower()
    if name in {TRY_ON_PROVIDER_FASHN, "fashn_tryon_v1_6", "tryon-v1.6", FASHN_PROVIDER_ID}:
        return TRY_ON_PROVIDER_FASHN
    if name in {TRY_ON_PROVIDER_OPENAI, "openai_images_edit"}:
        return TRY_ON_PROVIDER_OPENAI
    if not strict:
        return TRY_ON_PROVIDER_OPENAI
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Try On Person provider must be openai or fashn.",
    )


def _record_try_on_consent(
    db: Session, user: User, *, provider: str
) -> UserConsentEvent:
    """Record one-action try-on consent for this enqueue (immutable event)."""
    attestation = pcs._latest_adults_attestation(db, user)
    if attestation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adults-only beta attestation is required before Try On Person.",
        )
    if provider == TRY_ON_PROVIDER_FASHN:
        version = FASHN_CONSENT_VERSION
        text_hash = fashn_notice_text_hash()
    else:
        version = TRY_ON_CONSENT_VERSION
        text_hash = try_on_notice_text_hash()
    row = UserConsentEvent(
        id=uuid.uuid4(),
        owner_id=user.id,
        purpose=PURPOSE_TRY_ON_PERSON,
        consent_version=version,
        adults_attested=True,
        text_hash=text_hash,
    )
    db.add(row)
    db.flush()
    return row


def _find_try_on_by_idempotency(db: Session, user_id: uuid.UUID, key: str) -> AIJob | None:
    return db.scalar(
        select(AIJob)
        .where(
            AIJob.user_id == user_id,
            AIJob.job_type == TRY_ON_JOB_TYPE,
            AIJob.input_data["idempotency_key"].astext == key,
        )
        .order_by(AIJob.created_at.desc())
        .limit(1)
    )


def _normalize_design_hints(raw: list[str] | None) -> list[str]:
    """Bound Studio-derived hints for prompt appendix (never invent details)."""
    out: list[str] = []
    for item in raw or []:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split())
        if not text:
            continue
        out.append(text[:120])
        if len(out) >= 8:
            break
    return out


def enqueue_personal_try_on(
    db: Session,
    user: User,
    *,
    croquis_id: uuid.UUID,
    croquis_version: int,
    garment_image_base64: str,
    idempotency_key: str,
    design_id: uuid.UUID | None,
    source_revision: int,
    content_fingerprint: str,
    consent_acknowledged: bool,
    consent_version: str,
    design_hints: list[str] | None = None,
    provider: str = TRY_ON_PROVIDER_OPENAI,
    approved_garment_pieces: list[dict[str, Any]] | None = None,
    garment_realism_job_id: uuid.UUID | None = None,
) -> AIJob:
    """Validate, reserve spend, freeze garment, enqueue ``personal_try_on`` job."""
    _require_ai_gate()
    settings = get_settings()
    hints = _normalize_design_hints(design_hints)
    provider_name = _normalize_provider(provider)

    key = (idempotency_key or "").strip()
    if not key or len(key) > 128:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="idempotency_key is required.")
    if not key.startswith("try_on:"):
        # Namespace spend unique constraint away from croquis generate keys.
        key = f"try_on:{key}"
    # Keep OpenAI and FASHN idempotency namespaces distinct to block cross-provider replays.
    if provider_name == TRY_ON_PROVIDER_FASHN and ":fashn:" not in key:
        key = key.replace("try_on:", "try_on:fashn:", 1)

    if not consent_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Try On Person requires explicit consent acknowledgment.",
        )
    if provider_name == TRY_ON_PROVIDER_FASHN:
        if not fashn_configured():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="FASHN Try On is not configured on this server.",
            )
        if consent_version != FASHN_CONSENT_VERSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FASHN Try On consent version is outdated.",
            )
        if fashn_notice_text_hash() != hashlib.sha256(FASHN_NOTICE_TEXT.encode("utf-8")).hexdigest():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="FASHN notice hash mismatch."
            )
        expected_prompt_version = FASHN_PROMPT_VERSION
        consent_ver = FASHN_CONSENT_VERSION
    else:
        if consent_version != TRY_ON_CONSENT_VERSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Try On Person consent version is outdated.",
            )
        if try_on_notice_text_hash() != hashlib.sha256(TRY_ON_NOTICE_TEXT.encode("utf-8")).hexdigest():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Notice hash mismatch."
            )
        expected_prompt_version = TRY_ON_PROMPT_VERSION
        consent_ver = TRY_ON_CONSENT_VERSION

    fp = (content_fingerprint or "").strip()
    if not fp or len(fp) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="content_fingerprint is required."
        )
    if not isinstance(source_revision, int) or source_revision < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="source_revision must be a positive integer."
        )

    # Idempotent replay before spend lock when possible.
    existing = _find_try_on_by_idempotency(db, user.id, key)
    if existing is not None:
        return existing

    croquis = pcs.get_owned_croquis(db, user, croquis_id)
    if croquis.source_asset_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This croquis has no retained original photo for Try On Person.",
        )
    version = pcs.get_exact_version(db, user, croquis_id, croquis_version)
    if version.status != VERSION_STATUS_ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Try On Person requires an accepted personal croquis version.",
        )

    source = pcs.get_owned_media_asset(db, user, croquis.source_asset_id, allow_erased_meta=False)
    if source.kind != KIND_CROQUIS_SOURCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Original photograph binding is invalid.",
        )
    if source.bytes_purged_at is not None or source.erase_requested_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Original photograph is no longer available for Try On Person.",
        )
    # Prove bytes still exist before billing.
    pcs.resolve_croquis_asset_file(db, user, source.id)

    garment_png = _decode_garment_png(garment_image_base64)
    garment_fp = hashlib.sha256(garment_png).hexdigest()

    fashn_prep_meta: dict[str, Any] | None = None
    approved_frozen: list[dict[str, str]] | None = None
    if provider_name == TRY_ON_PROVIDER_FASHN:
        # #161/#166 — never send sketch plates to FASHN. Require server-bound OpenAI realism pieces.
        if garment_realism_job_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "FASHN Try On requires a completed garment realism job id. "
                    "Generate the realistic garment first."
                ),
            )
        raw_pieces: list[Any] = []
        realism_binding: dict[str, Any] | None = None
        if garment_realism_job_id is not None:
            realism_job = db.get(AIJob, garment_realism_job_id)
            if (
                realism_job is None
                or realism_job.user_id != user.id
                or realism_job.job_type != GARMENT_REALISM_JOB_TYPE
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Garment realism job not found for this FASHN Try On.",
                )
            if realism_job.status != "completed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Garment realism must complete successfully before FASHN Try On.",
                )
            rdata = realism_job.result_data if isinstance(realism_job.result_data, dict) else {}
            r_provider = str(rdata.get("provider") or "")
            if r_provider != GARMENT_REALISM_PROVIDER_ID or bool(rdata.get("prefer_local_product")):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "FASHN Try On requires an OpenAI realistic garment product image. "
                        "Sketch plates / local plate passthrough cannot be used."
                    ),
                )
            if rdata.get("fidelity_ok") is False or rdata.get("block_fashn"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(rdata.get("summary") or "Garment realism failed fidelity checks."),
                )
            # #169 — FASHN requires explicit owner acceptance of the OpenAI product images.
            if rdata.get("owner_accepted") is not True:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Accept the realistic garment product images before running FASHN Try On."
                    ),
                )
            r_input = realism_job.input_data if isinstance(realism_job.input_data, dict) else {}
            bound_fp = str(r_input.get("garment_fingerprint") or "")
            if bound_fp and bound_fp != garment_fp:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The Studio garment changed after realistic garment generation. "
                        "Regenerate and accept the product images again before FASHN."
                    ),
                )
            r_pieces = rdata.get("pieces")
            if not isinstance(r_pieces, list) or not r_pieces:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Garment realism job has no product pieces for FASHN.",
                )
            # Authoritative binding: ignore client-supplied images when realism job is present.
            raw_pieces = r_pieces
            realism_binding = {
                "garment_realism_job_id": str(garment_realism_job_id),
                "provider": r_provider,
                "prompt_version": rdata.get("prompt_version"),
                "piece_shas": [
                    str(p.get("sha256") or "")
                    for p in r_pieces
                    if isinstance(p, dict)
                ],
                "source_plate_shas": [
                    str(p.get("source_plate_sha256") or "")
                    for p in r_pieces
                    if isinstance(p, dict)
                ],
            }
        if not raw_pieces:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "FASHN Try On requires an accepted realistic garment product image. "
                    "Generate and approve the garment first."
                ),
            )
        # Offline prep of the immutable sketch → plate(s) for fidelity + category.
        try:
            sketch_prep = prepare_garment_reference(garment_png)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if sketch_prep.quality_ok is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=sketch_prep.quality_notes or "Garment sketch plates failed quality checks.",
            )

        parsed: list[tuple[PieceCategory, bytes]] = []
        fidelity_reports: list[dict[str, Any]] = []
        for idx, item in enumerate(raw_pieces):
            if not isinstance(item, dict):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid approved garment piece.")
            cat = str(item.get("category") or "auto").strip().lower()
            if cat not in {"tops", "bottoms", "one-pieces", "auto"}:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid piece category: {cat}")
            try:
                png = decode_data_url_png(str(item.get("image_base64") or ""))
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            plate_png = (
                sketch_prep.pieces[idx].png_bytes
                if idx < len(sketch_prep.pieces)
                else sketch_prep.pieces[0].png_bytes
            )
            product_sha = hashlib.sha256(png).hexdigest()
            plate_sha = hashlib.sha256(plate_png).hexdigest()
            source_plate_sha = str(item.get("source_plate_sha256") or "")
            if product_sha == plate_sha or (source_plate_sha and product_sha == source_plate_sha):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "FASHN Try On refused a sketch-like garment plate. "
                        "A realistic OpenAI product image is required."
                    ),
                )
            verdict = assert_structural_fidelity(
                source_png=plate_png,
                product_png=png,
                layout=sketch_prep.layout,
            )
            fidelity_reports.append(verdict.public_dict())
            if not verdict.ok:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=verdict.message,
                )
            # Remap auto → one-pieces (etc.) from source silhouette; never send auto for swimsuits.
            mapped = recommend_fashn_category(
                layout=sketch_prep.layout,
                piece_category=cat if cat != "auto" else verdict.recommended_category,
                features=verdict.source,
            )
            if sketch_prep.layout == "two_piece":
                # Preserve tops/bottoms ordering from prep when possible.
                mapped = sketch_prep.pieces[idx].category if idx < len(sketch_prep.pieces) else mapped
            parsed.append((mapped, png))  # type: ignore[arg-type]
        try:
            prep = prep_from_approved_product_pieces(
                pieces=parsed,
                source_fingerprint=garment_fp,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        estimate = estimate_fashn_cost_cents(fashn_calls=prep.fashn_calls)
        approved_frozen = [
            {
                "category": cat,
                "image_base64": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
                "sha256": hashlib.sha256(png).hexdigest(),
            }
            for cat, png in parsed
        ]
        fashn_prep_meta = {
            "layout": prep.layout,
            "fashn_calls": prep.fashn_calls,
            "garment_fingerprint": prep.source_fingerprint,
            "from_approved_product": True,
            "garment_realism_job_id": str(garment_realism_job_id) if garment_realism_job_id else None,
            "realism_binding": realism_binding,
            "fidelity": fidelity_reports,
            "categories": [cat for cat, _png in parsed],
            "approved_shas": [p["sha256"] for p in approved_frozen],
        }
    else:
        estimate = estimate_try_on_cost_cents()

    max_exposure = resolve_max_exposure_cents()
    # Reservation must cover the provider-specific estimate (two-piece FASHN = 2 credits).
    if estimate > max_exposure > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Estimated Try On cost exceeds the configured max exposure per run.",
        )
    ceiling_cents = int(round(float(settings.my_croquis_ai_spend_ceiling_usd or 0) * 100))
    day_cap = int(round(float(settings.my_croquis_ai_max_usd_per_user_day or 0) * 100))
    max_gens = int(settings.my_croquis_ai_max_generations_per_user_day or 0)

    _lock_spend_tx(db, user.id)

    # Re-check idempotency under lock.
    existing = _find_try_on_by_idempotency(db, user.id, key)
    if existing is not None:
        return existing
    existing_res = (
        db.query(PersonalCroquisSpendReservation)
        .filter(
            PersonalCroquisSpendReservation.owner_id == user.id,
            PersonalCroquisSpendReservation.idempotency_key == key,
        )
        .one_or_none()
    )
    if existing_res is not None:
        if existing_res.status == RESERVATION_RECONCILIATION:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Previous Try On Person needs reconciliation — no automatic paid retry.",
            )
        # Reservation without job — refuse silent re-bill.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Try On Person idempotency key already used — recover the existing job or use a new key.",
        )

    if max_gens > 0 and _count_generations_today(db, user) >= max_gens:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily Create My Croquis / Try On Person generation limit reached.",
        )
    operator_total = _sum_billable_cents(db, owner_id=None, since=None)
    if ceiling_cents > 0 and operator_total + max_exposure > ceiling_cents:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator AI spend ceiling would be exceeded.",
        )
    if day_cap > 0:
        day_ago = _utcnow() - timedelta(days=1)
        user_day = _sum_billable_cents(db, owner_id=user.id, since=day_ago)
        if user_day + max_exposure > day_cap:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Daily AI spend limit would be exceeded.",
            )

    consent = _record_try_on_consent(db, user, provider=provider_name)
    reservation = PersonalCroquisSpendReservation(
        id=uuid.uuid4(),
        owner_id=user.id,
        croquis_id=croquis.id,
        source_asset_id=source.id,
        version_id=version.id,
        idempotency_key=key,
        status=RESERVATION_OPEN,
        estimate_cents=estimate,
        max_exposure_cents=max_exposure,
        provider_called=False,
    )
    db.add(reservation)

    # Store garment as base64 in input (same pattern as sketch_polish) — immutable freeze.
    garment_b64 = base64.b64encode(garment_png).decode("ascii")
    input_data: dict[str, Any] = {
        "idempotency_key": key,
        "croquis_id": str(croquis.id),
        "croquis_version": int(version.version),
        "source_asset_id": str(source.id),
        "version_id": str(version.id),
        "garment_image_base64": f"data:image/png;base64,{garment_b64}",
        "garment_fingerprint": garment_fp,
        "content_fingerprint": fp,
        "source_revision": int(source_revision),
        "consent_id": str(consent.id),
        "consent_version": consent_ver,
        "prompt_version": expected_prompt_version,
        "provider": provider_name,
        "reservation_id": str(reservation.id),
        "mode": "try_on_person",
        "design_hints": hints,
    }
    if fashn_prep_meta is not None:
        input_data["fashn_prep"] = fashn_prep_meta
    if approved_frozen is not None:
        input_data["approved_garment_pieces"] = approved_frozen
    if garment_realism_job_id is not None:
        input_data["garment_realism_job_id"] = str(garment_realism_job_id)

    job = AIJob(
        id=uuid.uuid4(),
        user_id=user.id,
        design_id=design_id,
        job_type=TRY_ON_JOB_TYPE,
        status="queued",
        input_data=input_data,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Lost race on spend unique — return existing job if present.
        existing = _find_try_on_by_idempotency(db, user.id, key)
        if existing is not None:
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Try On Person could not be enqueued (idempotency conflict).",
        ) from exc
    db.refresh(job)
    return job


def _try_on_user_failure_payload(exc: BaseException) -> tuple[str, dict[str, Any]]:
    """Build owner-safe UI copy + private support diagnostics for a definite refusal."""
    safe_meta = getattr(exc, "safe_meta", None)
    meta = safe_meta if isinstance(safe_meta, dict) else {}
    detail = str(exc)
    error_code = str(meta.get("error_code") or "")
    if not error_code:
        from app.services.personal_croquis_provider import (
            provider_rejection_code_from_text,
        )

        code = provider_rejection_code_from_text(detail)
        error_code = (
            "PROVIDER_MODERATION_BLOCKED"
            if code == "moderation_blocked"
            else "PROVIDER_REJECTED"
        )
    user_msg = (
        TRY_ON_USER_MODERATION_MESSAGE
        if error_code == "PROVIDER_MODERATION_BLOCKED"
        else TRY_ON_USER_PROVIDER_REJECT_MESSAGE
    )
    provider_rejection = {
        "code": meta.get("provider_code") or ("moderation_blocked" if error_code == "PROVIDER_MODERATION_BLOCKED" else None),
        "http_status": meta.get("http_status"),
        "moderation_stage": meta.get("moderation_stage"),
        "categories": meta.get("categories"),
        "request_id": meta.get("request_id"),
    }
    # Drop empty diagnostic keys; keep only support-useful fields.
    provider_rejection = {k: v for k, v in provider_rejection.items() if v not in (None, "", [])}
    result = {
        "status": "failed",
        "summary": user_msg,
        "error_code": error_code,
        "mode": "try_on_person",
        "prompt_version": TRY_ON_PROMPT_VERSION,
        "provider_rejection": provider_rejection or None,
        # Operator-only hint in result_data (not shown by FE extractMagicSummary).
        "operator_summary": (meta.get("operator_summary") or detail)[:400],
    }
    return user_msg, result


def complete_try_on_job(db: Session, job: AIJob) -> dict[str, Any]:
    """Worker entry: call provider once, store private look image, settle spend."""
    if job.job_type != TRY_ON_JOB_TYPE:
        raise ValueError(f"unexpected job_type {job.job_type!r}")
    data = job.input_data if isinstance(job.input_data, dict) else {}
    reservation_id = data.get("reservation_id")
    reservation: PersonalCroquisSpendReservation | None = None
    if reservation_id:
        try:
            reservation = db.get(PersonalCroquisSpendReservation, uuid.UUID(str(reservation_id)))
        except Exception:  # noqa: BLE001
            reservation = None

    def _fail(
        msg: str,
        *,
        settle_release: bool = True,
        error_code: str | None = None,
        result_extra: dict[str, Any] | None = None,
        operator_detail: str | None = None,
    ) -> dict[str, Any]:
        job.status = "failed"
        job.error_message = msg[:240]
        result: dict[str, Any] = {
            "status": "failed",
            "summary": msg,
            "mode": "try_on_person",
            "prompt_version": TRY_ON_PROMPT_VERSION,
        }
        if error_code:
            result["error_code"] = error_code
        if result_extra:
            result.update(result_extra)
        job.result_data = result
        if reservation is not None and reservation.status == RESERVATION_OPEN:
            if settle_release:
                reservation.status = RESERVATION_RELEASED
                reservation.error_detail = (operator_detail or msg)[:500]
        return result

    try:
        user = db.get(User, job.user_id)
        if user is None:
            return _fail("Owner account missing for Try On Person.")
        croquis_id = uuid.UUID(str(data["croquis_id"]))
        source_asset_id = uuid.UUID(str(data["source_asset_id"]))
        croquis_version = int(data["croquis_version"])
        # Re-validate ownership + source still present (no wrong-photo attribution).
        croquis = pcs.get_owned_croquis(db, user, croquis_id)
        if croquis.source_asset_id != source_asset_id:
            return _fail("Original photograph binding changed — refusing Try On Person.")
        version = pcs.get_exact_version(db, user, croquis_id, croquis_version)
        if version.status != VERSION_STATUS_ACCEPTED:
            return _fail("Croquis version is no longer accepted.")
        photo_path = pcs.resolve_croquis_asset_file(db, user, source_asset_id)
        photo_png = photo_path.read_bytes()
        garment_png = _decode_garment_png(str(data.get("garment_image_base64") or ""))
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Try On Person validation failed."
        return _fail(detail)
    except Exception:  # noqa: BLE001
        return _fail("Try On Person could not load the frozen photo or garment.")

    provider_name = _normalize_provider(
        str(data.get("provider") or TRY_ON_PROVIDER_OPENAI), strict=False
    )
    prompt_version = str(
        data.get("prompt_version")
        or (FASHN_PROMPT_VERSION if provider_name == TRY_ON_PROVIDER_FASHN else TRY_ON_PROMPT_VERSION)
    )
    try:
        provider = get_try_on_provider(provider_name)
        if reservation is not None:
            reservation.provider_called = True
            db.flush()
        hints = _normalize_design_hints(
            data.get("design_hints") if isinstance(data.get("design_hints"), list) else None
        )
        # #170/#172 — additive trouser/jumpsuit hints from frozen garment geometry (OpenAI V2 only).
        # Geometry hints take priority in the 8-hint budget so they cannot be crowded out.
        # Does not rewrite TRY_ON_PROMPT_VERSION; skips FASHN and ambiguous silhouettes.
        if provider_name == TRY_ON_PROVIDER_OPENAI:
            geo_hints = openai_trouser_design_hints(analyze_lower_garment_geometry(garment_png))
            if geo_hints:
                hints = _normalize_design_hints(
                    merge_openai_design_hints(hints, geo_hints, max_hints=8)
                )
        generate_kwargs: dict[str, Any] = {
            "photo_png": photo_png,
            "garment_png": garment_png,
            "design_hints": hints,
        }
        if provider_name == TRY_ON_PROVIDER_FASHN:
            approved = data.get("approved_garment_pieces")
            if not isinstance(approved, list) or not approved:
                return _fail(
                    "FASHN Try On is missing the accepted realistic garment product image.",
                    settle_release=True,
                    error_code="APPROVED_GARMENT_REQUIRED",
                )
            parsed: list[tuple[PieceCategory, bytes]] = []
            for item in approved:
                if not isinstance(item, dict):
                    return _fail("Invalid frozen approved garment piece.")
                cat = str(item.get("category") or "auto").strip().lower()
                try:
                    png_piece = decode_data_url_png(str(item.get("image_base64") or ""))
                except ValueError as exc:
                    return _fail(str(exc))
                parsed.append((cat, png_piece))  # type: ignore[arg-type]
            generate_kwargs["prep"] = prep_from_approved_product_pieces(
                pieces=parsed,
                source_fingerprint=str(data.get("garment_fingerprint") or ""),
            )
        png, meta = provider.generate(**generate_kwargs)
    except ProviderNotAvailableError as exc:
        # Definitive pre-submit or HTTP 4xx refusal — release reservation at $0.
        # Never auto-retry. Do not leak raw provider JSON into owner UI.
        user_msg, result = _try_on_user_failure_payload(exc)
        return _fail(
            user_msg,
            settle_release=True,
            error_code=str(result.get("error_code") or "PROVIDER_REJECTED"),
            result_extra={
                k: v
                for k, v in result.items()
                if k not in {"status", "summary", "mode", "prompt_version"}
            },
            operator_detail=str(exc)[:500],
        )
    except ProviderOutcomeUnknownError as exc:
        # Ambiguous post-dispatch — hold reservation in reconciliation, no auto-retry.
        if reservation is not None and reservation.status == RESERVATION_OPEN:
            reservation.status = RESERVATION_RECONCILIATION
            reservation.error_detail = str(exc)[:500]
        job.status = "failed"
        job.error_message = (
            "Try On Person outcome is unknown after the provider call. "
            "No automatic retry — contact support if you were charged."
        )[:240]
        result = {
            "status": "failed",
            "summary": job.error_message,
            "mode": "try_on_person",
            "error_code": "PROVIDER_OUTCOME_UNKNOWN",
            "reconciliation_required": True,
            "prompt_version": TRY_ON_PROMPT_VERSION,
        }
        job.result_data = result
        return result

    key = f"ai/{job.id.hex}_tryon_{uuid.uuid4().hex[:10]}.png"
    storage = LocalStorageBackend()
    url = storage.save_file(key=key, data=io.BytesIO(png), content_type="image/png")

    actual = meta.get("actual_cost_cents")
    if reservation is not None and reservation.status == RESERVATION_OPEN:
        reservation.status = RESERVATION_SETTLED
        reservation.actual_cost_cents = int(actual) if isinstance(actual, int) else reservation.estimate_cents
        reservation.provider_called = True

    result = {
        "status": "completed",
        "summary": "Try On Person preview ready (concept preview — not a fit guarantee).",
        "bullets": [
            "Original photo and sketch were not overwritten.",
            "Face, pose and background preserved where the model allowed.",
            f"Prompt {prompt_version}",
            f"Provider {meta.get('provider') or provider_name}",
        ],
        "image_url": url,
        "mode": "try_on_person",
        "prompt_version": prompt_version,
        "provider": meta.get("provider") or provider_name,
        "croquis_id": str(data.get("croquis_id")),
        "croquis_version": data.get("croquis_version"),
        "source_asset_id": str(data.get("source_asset_id")),
        "garment_fingerprint": data.get("garment_fingerprint"),
        "content_fingerprint": data.get("content_fingerprint"),
        "source_revision": data.get("source_revision"),
        "cost_cents": reservation.actual_cost_cents if reservation else actual,
        "design_hints": hints if provider_name == TRY_ON_PROVIDER_OPENAI else None,
    }
    if provider_name == TRY_ON_PROVIDER_OPENAI:
        # Soft structural review (#170/#171/#172). Server provenance marks the provider PNG as
        # a photoreal try-on photo — never authorize plate comparison from pixel heuristics.
        # Only confirmed like-for-like trusted plate failures downgrade presentation / My Looks.
        review = soft_try_on_structure_review(
            source_png=garment_png,
            result_png=png,
            result_kind=RESULT_KIND_OPENAI_TRY_ON_PHOTO,
        )
        result["structure_review"] = review
        state = str(review.get("state") or "")
        if state == "failed":
            result["status"] = "completed_unverified"
            result["fidelity_ok"] = False
            result["summary"] = str(review.get("message") or result["summary"])
            result["bullets"] = [
                "Provider returned an image, but FashionRise flagged a major silhouette mismatch.",
                "This is not a faithful try-on of your sketch — do not treat it as production-ready.",
                "This preview is kept for private review and is not presented as an accepted My Look.",
                "Provider charges may still apply; FashionRise customer credit is a separate owner decision.",
                f"Prompt {prompt_version}",
            ]
        else:
            # not_applicable / inconclusive / passed_soft — keep ordinary completed preview.
            # Soft pass or skip is not a fidelity certificate.
            result["fidelity_ok"] = None
            if state == "inconclusive":
                # Non-alarming diagnostic only; ordinary concept-preview copy stays primary.
                result["structure_review_note"] = str(review.get("message") or "")
    if provider_name == TRY_ON_PROVIDER_FASHN:
        result["fashn_prediction_ids"] = meta.get("prediction_ids")
        result["fashn_calls"] = meta.get("fashn_calls")
        result["fashn_layout"] = meta.get("layout")
    job.status = "completed"
    job.error_message = None
    job.result_data = result
    return result


def try_on_preflight_public() -> dict[str, Any]:
    """Safe public preflight for FE (no image bytes / no secret values)."""
    settings = get_settings()
    fashn_ready = fashn_configured()
    fashn_per = int(settings.fashn_try_on_estimate_cents or 8)
    realism_per = int(
        getattr(settings, "fashn_garment_realism_estimate_cents", None)
        or settings.my_croquis_ai_estimate_cents
        or 8
    )
    return {
        "enabled": bool(settings.my_croquis_ai_enabled and settings.my_croquis_ai_spend_ceiling_usd > 0),
        "live_http": bool(settings.my_croquis_ai_live_http),
        "consent_version": TRY_ON_CONSENT_VERSION,
        "notice_text": TRY_ON_NOTICE_TEXT,
        "notice_hash": try_on_notice_text_hash(),
        "prompt_version": TRY_ON_PROMPT_VERSION,
        "estimate_cents": estimate_try_on_cost_cents(),
        "max_exposure_cents": int(settings.my_croquis_ai_max_exposure_cents or 0),
        "fashn_enabled": bool(settings.fashn_try_on_enabled),
        "fashn_configured": fashn_ready,
        "fashn_live_http": bool(settings.fashn_try_on_live_http) and fashn_ready,
        "fashn_consent_version": FASHN_CONSENT_VERSION,
        "fashn_notice_text": FASHN_NOTICE_TEXT,
        "fashn_notice_hash": fashn_notice_text_hash(),
        "fashn_estimate_cents_per_call": fashn_per,
        "fashn_prompt_version": FASHN_PROMPT_VERSION,
        # Soft one-click combined estimate (1 piece / 1 credit). Two-piece doubles both stages.
        "fashn_realism_estimate_cents_per_piece": realism_per,
        "fashn_combined_estimate_cents_one_piece": realism_per + fashn_per,
        "fashn_one_click": True,
    }


def prepare_fashn_garment_public(garment_image_base64: str) -> dict[str, Any]:
    """Offline FASHN garment prep preview — no provider HTTP, no spend."""
    _require_ai_gate()
    settings = get_settings()
    if not settings.fashn_try_on_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FASHN Try On is not enabled.",
        )
    garment_png = _decode_garment_png(garment_image_base64)
    try:
        prep = prepare_garment_reference(garment_png)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    per = int(settings.fashn_try_on_estimate_cents or 8)
    realism_per = int(settings.fashn_garment_realism_estimate_cents or settings.my_croquis_ai_estimate_cents or 8)
    payload = prep.public_dict(cents_per_call=per, realism_cents_per_piece=realism_per)
    payload.update(
        {
            "consent_version": FASHN_CONSENT_VERSION,
            "notice_text": FASHN_NOTICE_TEXT,
            "notice_hash": fashn_notice_text_hash(),
            "provider": TRY_ON_PROVIDER_FASHN,
            "configured": fashn_configured(),
            "live_http": fashn_live_armed(),
            "openai_live_http": bool(settings.my_croquis_ai_live_http),
        }
    )
    return payload


def _find_realism_by_idempotency(db: Session, user_id: uuid.UUID, key: str) -> AIJob | None:
    return db.scalar(
        select(AIJob)
        .where(
            AIJob.user_id == user_id,
            AIJob.job_type == GARMENT_REALISM_JOB_TYPE,
            AIJob.input_data["idempotency_key"].astext == key,
        )
        .order_by(AIJob.created_at.desc())
        .limit(1)
    )


def enqueue_garment_realism(
    db: Session,
    user: User,
    *,
    croquis_id: uuid.UUID,
    croquis_version: int,
    garment_image_base64: str,
    plate_pieces: list[dict[str, Any]],
    garment_fingerprint: str,
    idempotency_key: str,
    design_id: uuid.UUID | None,
    consent_acknowledged: bool,
    consent_version: str,
) -> AIJob:
    """Paid OpenAI product-image stage — separate from FASHN credits (#161)."""
    _require_ai_gate()
    settings = get_settings()
    if not settings.fashn_try_on_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FASHN Try On is not enabled.")
    if not consent_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garment realism requires explicit consent acknowledgment.",
        )
    if consent_version != FASHN_CONSENT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FASHN Try On consent version is outdated.",
        )

    key = (idempotency_key or "").strip()
    if not key or len(key) > 128:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="idempotency_key is required.")
    if not key.startswith("try_on:garment_realism:"):
        key = f"try_on:garment_realism:{key.removeprefix('try_on:')}"

    existing = _find_realism_by_idempotency(db, user.id, key)
    if existing is not None:
        return existing

    croquis = pcs.get_owned_croquis(db, user, croquis_id)
    version = pcs.get_exact_version(db, user, croquis_id, croquis_version)
    if version.status != VERSION_STATUS_ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garment realism requires an accepted personal croquis version.",
        )
    if croquis.source_asset_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This croquis has no retained original photo.",
        )
    source = pcs.get_owned_media_asset(db, user, croquis.source_asset_id, allow_erased_meta=False)
    pcs.resolve_croquis_asset_file(db, user, source.id)

    garment_png = _decode_garment_png(garment_image_base64)
    garment_fp = hashlib.sha256(garment_png).hexdigest()
    if garment_fingerprint and garment_fingerprint.strip() != garment_fp:
        # Soft check — allow if client fingerprint matches prep output; else recompute trust server-side.
        pass
    # Bound Studio croquis for OpenAI second-image context (#167) — plate remains authoritative.
    studio_context_png = downscale_studio_context(garment_png)
    studio_context_b64 = (
        "data:image/png;base64," + base64.b64encode(studio_context_png).decode("ascii")
        if studio_context_png
        else None
    )

    frozen_plates: list[dict[str, str]] = []
    for item in plate_pieces:
        if not isinstance(item, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plate piece.")
        cat = str(item.get("category") or "auto").strip().lower()
        if cat not in {"tops", "bottoms", "one-pieces", "auto"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid piece category: {cat}")
        try:
            png = decode_data_url_png(str(item.get("image_base64") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        frozen_plates.append(
            {
                "category": cat,
                "image_base64": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
                "sha256": hashlib.sha256(png).hexdigest(),
            }
        )
    if not frozen_plates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one plate piece is required.")

    # Always paid OpenAI realism before FASHN — never local plate re-encode (#164/#166).
    prefer_local = False
    estimate = estimate_garment_realism_cents(pieces=len(frozen_plates))
    max_exposure = resolve_max_exposure_cents()
    if estimate > max_exposure > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Estimated garment realism cost exceeds the configured max exposure per run.",
        )
    ceiling_cents = int(round(float(settings.my_croquis_ai_spend_ceiling_usd or 0) * 100))
    day_cap = int(round(float(settings.my_croquis_ai_max_usd_per_user_day or 0) * 100))
    max_gens = int(settings.my_croquis_ai_max_generations_per_user_day or 0)

    _lock_spend_tx(db, user.id)
    existing = _find_realism_by_idempotency(db, user.id, key)
    if existing is not None:
        return existing
    existing_res = (
        db.query(PersonalCroquisSpendReservation)
        .filter(
            PersonalCroquisSpendReservation.owner_id == user.id,
            PersonalCroquisSpendReservation.idempotency_key == key,
        )
        .one_or_none()
    )
    if existing_res is not None:
        if existing_res.status == RESERVATION_RECONCILIATION:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Previous garment realism needs reconciliation — no automatic paid retry.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Garment realism idempotency key already used — recover the existing job or use a new key.",
        )

    if max_gens > 0 and _count_generations_today(db, user) >= max_gens:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily Create My Croquis / Try On Person generation limit reached.",
        )
    operator_total = _sum_billable_cents(db, owner_id=None, since=None)
    if ceiling_cents > 0 and operator_total + max_exposure > ceiling_cents:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator AI spend ceiling would be exceeded.",
        )
    if day_cap > 0:
        day_ago = _utcnow() - timedelta(days=1)
        user_day = _sum_billable_cents(db, owner_id=user.id, since=day_ago)
        if user_day + max_exposure > day_cap:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Daily AI spend limit would be exceeded.",
            )

    consent = _record_try_on_consent(db, user, provider=TRY_ON_PROVIDER_FASHN)
    reservation = PersonalCroquisSpendReservation(
        id=uuid.uuid4(),
        owner_id=user.id,
        croquis_id=croquis.id,
        source_asset_id=source.id,
        version_id=version.id,
        idempotency_key=key,
        status=RESERVATION_OPEN,
        estimate_cents=estimate,
        max_exposure_cents=max_exposure,
        provider_called=False,
    )
    db.add(reservation)

    input_data: dict[str, Any] = {
        "idempotency_key": key,
        "croquis_id": str(croquis.id),
        "croquis_version": int(version.version),
        "source_asset_id": str(source.id),
        "version_id": str(version.id),
        "garment_fingerprint": garment_fp,
        "client_garment_fingerprint": (garment_fingerprint or "").strip() or None,
        "plate_pieces": frozen_plates,
        "studio_context_base64": studio_context_b64,
        "studio_context_sha256": hashlib.sha256(studio_context_png).hexdigest() if studio_context_png else None,
        "consent_id": str(consent.id),
        "consent_version": FASHN_CONSENT_VERSION,
        "prompt_version": GARMENT_REALISM_PROMPT_VERSION,
        "provider": GARMENT_REALISM_PROVIDER_ID,
        "prefer_local_product": prefer_local,
        "reservation_id": str(reservation.id),
        "mode": "garment_realism",
        "estimate_cents": estimate,
    }
    job = AIJob(
        id=uuid.uuid4(),
        user_id=user.id,
        design_id=design_id,
        job_type=GARMENT_REALISM_JOB_TYPE,
        status="queued",
        input_data=input_data,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = _find_realism_by_idempotency(db, user.id, key)
        if existing is not None:
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Garment realism could not be enqueued (idempotency conflict).",
        ) from exc
    db.refresh(job)
    return job


def complete_garment_realism_job(db: Session, job: AIJob) -> dict[str, Any]:
    """Worker: OpenAI product images for each plate; never calls FASHN; never local plate passthrough."""
    if job.job_type != GARMENT_REALISM_JOB_TYPE:
        raise ValueError(f"unexpected job_type {job.job_type!r}")
    data = job.input_data if isinstance(job.input_data, dict) else {}
    # Hard-disable local plate passthrough even if an old queued job still has the flag.
    prefer_local = False
    provider_id = GARMENT_REALISM_PROVIDER_ID
    prompt_version = GARMENT_REALISM_PROMPT_VERSION
    reservation_id = data.get("reservation_id")
    reservation: PersonalCroquisSpendReservation | None = None
    if reservation_id:
        try:
            reservation = db.get(PersonalCroquisSpendReservation, uuid.UUID(str(reservation_id)))
        except Exception:  # noqa: BLE001
            reservation = None

    def _fail(msg: str, *, settle_release: bool = True, error_code: str | None = None) -> dict[str, Any]:
        job.status = "failed"
        job.error_message = msg[:240]
        result: dict[str, Any] = {
            "status": "failed",
            "summary": msg,
            "mode": "garment_realism",
            "prompt_version": prompt_version,
            "provider": provider_id,
            "prefer_local_product": prefer_local,
        }
        if error_code:
            result["error_code"] = error_code
        job.result_data = result
        if reservation is not None and reservation.status == RESERVATION_OPEN and settle_release:
            reservation.status = RESERVATION_RELEASED
            reservation.error_detail = msg[:500]
        return result

    plates = data.get("plate_pieces")
    if not isinstance(plates, list) or not plates:
        return _fail("Garment realism job is missing plate pieces.")

    studio_context_png: bytes | None = None
    raw_ctx = data.get("studio_context_base64")
    if isinstance(raw_ctx, str) and raw_ctx.strip():
        try:
            studio_context_png = decode_data_url_png(raw_ctx)
        except ValueError:
            studio_context_png = None

    try:
        adapter = OpenAIGarmentRealismAdapter()
        if reservation is not None:
            reservation.provider_called = True
            db.flush()
        out_pieces: list[dict[str, Any]] = []
        metas: list[dict[str, Any]] = []
        storage = LocalStorageBackend()
        for item in plates:
            if not isinstance(item, dict):
                return _fail("Invalid plate piece in realism job.")
            cat = str(item.get("category") or "auto")
            plate_png = decode_data_url_png(str(item.get("image_base64") or ""))
            # Prefer explicit one-pieces over auto for one-piece plates.
            feats = compute_silhouette_features(plate_png)
            gen_cat = recommend_fashn_category(layout="one_piece", piece_category=cat, features=feats)
            if cat in {"tops", "bottoms"}:
                gen_cat = cat  # type: ignore[assignment]
            product_png, meta = adapter.generate_piece(
                plate_png=plate_png,
                category=gen_cat,
                studio_context_png=studio_context_png,
            )
            # Reject near-identical plate passthrough (sketch look into FASHN).
            if hashlib.sha256(product_png).hexdigest() == hashlib.sha256(plate_png).hexdigest():
                return _fail(
                    "Realistic garment generation returned the sketch plate unchanged. FASHN was not started.",
                    settle_release=False,
                    error_code="FIDELITY_SKETCH_PASSTHROUGH",
                )
            verdict = assert_structural_fidelity(
                source_png=plate_png,
                product_png=product_png,
                layout="two_piece" if cat in {"tops", "bottoms"} else "one_piece",
            )
            meta = {**meta, "fidelity": verdict.public_dict(), "category": gen_cat}
            # Always persist product bytes (including fidelity failures) for private diagnosis (#167).
            key = f"ai/{job.id.hex}_garment_{gen_cat}_{uuid.uuid4().hex[:8]}.png"
            url = storage.save_file(key=key, data=io.BytesIO(product_png), content_type="image/png")
            if not verdict.ok:
                # Paid OpenAI already ran — settle realism spend, but block FASHN.
                # Keep status completed so the owner can review the product image (#169);
                # Accept and FASHN enqueue both refuse fidelity_ok=false / block_fashn.
                if reservation is not None and reservation.status == RESERVATION_OPEN:
                    reservation.status = RESERVATION_SETTLED
                    reservation.actual_cost_cents = reservation.estimate_cents
                    reservation.provider_called = True
                failed_piece = {
                    "category": gen_cat,
                    "image_base64": "data:image/png;base64,"
                    + base64.b64encode(product_png).decode("ascii"),
                    "image_url": url,
                    "sha256": hashlib.sha256(product_png).hexdigest(),
                    "source_plate_sha256": str(item.get("sha256") or ""),
                    "fidelity": verdict.public_dict(),
                }
                # Preserve any earlier OK pieces so two-piece review can show both sides.
                review_pieces = [*out_pieces, failed_piece]
                job.status = "completed"
                job.error_message = None
                job.result_data = {
                    "status": "completed",
                    "summary": verdict.message,
                    "mode": "garment_realism",
                    "error_code": verdict.code,
                    "fidelity": verdict.public_dict(),
                    "prompt_version": prompt_version,
                    "provider": provider_id,
                    "prefer_local_product": False,
                    "pieces": review_pieces,
                    "failed_product": {
                        "category": gen_cat,
                        "image_url": url,
                        "sha256": hashlib.sha256(product_png).hexdigest(),
                        "source_plate_sha256": str(item.get("sha256") or ""),
                    },
                    "garment_fingerprint": data.get("garment_fingerprint"),
                    "cost_cents": reservation.actual_cost_cents if reservation else data.get("estimate_cents"),
                    "requires_owner_acceptance": True,
                    "owner_accepted": False,
                    "fidelity_ok": False,
                    "block_fashn": True,
                }
                return job.result_data
            out_pieces.append(
                {
                    "category": gen_cat,
                    "image_base64": "data:image/png;base64," + base64.b64encode(product_png).decode("ascii"),
                    "image_url": url,
                    "sha256": hashlib.sha256(product_png).hexdigest(),
                    "source_plate_sha256": str(item.get("sha256") or ""),
                    "fidelity": verdict.public_dict(),
                }
            )
            metas.append(meta)
    except ProviderNotAvailableError as exc:
        return _fail(str(exc)[:240], settle_release=True, error_code="PROVIDER_REJECTED")
    except ProviderOutcomeUnknownError as exc:
        if reservation is not None and reservation.status == RESERVATION_OPEN:
            reservation.status = RESERVATION_RECONCILIATION
            reservation.error_detail = str(exc)[:500]
        job.status = "failed"
        job.error_message = (
            "Garment realism outcome is unknown after the provider call. "
            "No automatic retry — contact support if you were charged."
        )[:240]
        job.result_data = {
            "status": "failed",
            "summary": job.error_message,
            "mode": "garment_realism",
            "error_code": "PROVIDER_OUTCOME_UNKNOWN",
            "reconciliation_required": True,
            "prompt_version": prompt_version,
            "provider": provider_id,
        }
        return job.result_data

    if reservation is not None and reservation.status == RESERVATION_OPEN:
        reservation.status = RESERVATION_SETTLED
        reservation.actual_cost_cents = reservation.estimate_cents
        reservation.provider_called = True

    result = {
        "status": "completed",
        "summary": "Realistic garment product image ready (fidelity checks passed).",
        "mode": "garment_realism",
        "prompt_version": prompt_version,
        "provider": provider_id,
        "prefer_local_product": False,
        "pieces": out_pieces,
        "piece_meta": metas,
        "garment_fingerprint": data.get("garment_fingerprint"),
        "cost_cents": reservation.actual_cost_cents if reservation else data.get("estimate_cents"),
        # #169 — owner must Accept product images before any FASHN credit is spent.
        "requires_owner_acceptance": True,
        "owner_accepted": False,
        "fidelity_ok": True,
        "block_fashn": False,
    }
    job.status = "completed"
    job.error_message = None
    job.result_data = result
    return result


def accept_garment_realism_job(db: Session, user: User, job_id: uuid.UUID) -> AIJob:
    """Stamp owner acceptance on a completed, fidelity-OK realism job (#169).

    Does not call OpenAI or FASHN. Rejects hard fidelity failures — Accept cannot override.
    """
    job = db.get(AIJob, job_id)
    if job is None or job.user_id != user.id or job.job_type != GARMENT_REALISM_JOB_TYPE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Garment realism job not found.")
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a completed realistic garment job can be accepted.",
        )
    data = job.result_data if isinstance(job.result_data, dict) else {}
    if data.get("fidelity_ok") is False or data.get("block_fashn"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fidelity checks failed — Accept cannot override. Regenerate or edit the sketch.",
        )
    pieces = data.get("pieces")
    if not isinstance(pieces, list) or not pieces:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Realistic garment job has no product images to accept.",
        )
    if str(data.get("provider") or "") != GARMENT_REALISM_PROVIDER_ID:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only OpenAI realistic product images can be accepted for FASHN.",
        )
    if data.get("owner_accepted") is True:
        return job
    updated = {
        **data,
        "owner_accepted": True,
        "owner_accepted_at": _utcnow().isoformat(),
        "requires_owner_acceptance": True,
    }
    job.result_data = updated
    db.add(job)
    db.flush()
    return job
