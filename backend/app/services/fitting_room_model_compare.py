"""Owner-only Fitting Room model comparison (clean one-call A/B/C).

Purpose: find which provider produces an acceptable **raw** try-on in a single
call — no masks, face composites, materialize, color-lock, or provider chains.

Arms:
  A) OpenAI ``chatgpt-image-latest`` via ``images.edit`` (person + design)
  B) OpenAI ``gpt-image-2.6-sunburst`` via ``images.edit`` (person + design)
  C) FASHN ``tryon-max`` (model_image + product_image)

Fail closed: feature flag + owner allowlist + explicit consent +
``authorize_paid`` + server-enforced one-shot paid budget.
Does **not** change the live Fitting Room path or Stars billing.
Private outputs never land under ``/static/uploads``.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException, status
from PIL import Image, ImageOps
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.upload_validation import probe_image_dimensions, sniff_image_kind
from app.models.fitting_room_model_compare import (
    MODEL_COMPARE_GLOBAL_LOCK_KEY,
    OP_STATUS_COMPLETED,
    OP_STATUS_EXHAUSTED,
    OP_STATUS_FAILED,
    OP_STATUS_RECONCILIATION,
    OP_STATUS_RUNNING,
    TERMINAL_OP_STATUSES,
    FittingRoomModelCompareOperation,
)
from app.models.user import User
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

COMPARE_PROMPT_VERSION = "fitting-room-model-compare-v1"
COMPARE_CONSENT_VERSION = "fitting-room-model-compare-v1"
COMPARE_NOTICE = (
    "Owner-only model comparison sends your person photo and fashion design to "
    "third-party AI providers (OpenAI and/or FASHN) for one native generation per "
    "selected arm. Outputs are stored in private, owner-only storage for this "
    "experiment and are not published. Stars are not charged."
)

# Short prompt — intentionally minimal. No enormous instruction set.
COMPARE_PROMPT = (
    "Fit the exact garment design from image 2 onto the real person in image 1. "
    "Preserve the person's original face, hair, body, pose, and background. "
    "Keep the garment's exact colors, silhouette, decorative details, and length. "
    "Make the clothing naturally photorealistic. Do not change anything else."
)

# Soft USD¢ estimates for the report (not billed here — Stars untouched).
_OPENAI_HIGH_PORTRAIT_ESTIMATE_CENTS = 6
_FASHN_MAX_QUALITY_2K_CREDITS = 4
_FASHN_CREDIT_CENTS = 8

# Base64 string ceiling ≈ decoded max_upload_bytes * 4/3 + data-URL header slack.
_B64_HEADER_SLACK = 128

ARM_SPECS: tuple[dict[str, str], ...] = (
    {
        "arm": "A",
        "provider": "openai",
        "model": "chatgpt-image-latest",
        "path": "openai_images_edit_person_garment",
    },
    {
        "arm": "B",
        "provider": "openai",
        "model": "gpt-image-2.6-sunburst",
        "path": "openai_images_edit_person_garment",
    },
    {
        "arm": "C",
        "provider": "fashn",
        "model": "tryon-max",
        "path": "fashn_tryon_max_raw_person_product",
    },
)


def _normalize_allowlist() -> set[str]:
    raw = (get_settings().fitting_room_model_compare_owner_allowlist or "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def user_on_model_compare_allowlist(user: User) -> bool:
    allow = _normalize_allowlist()
    if not allow:
        return False
    email = str(getattr(user, "email", "") or "").strip().lower()
    username = str(getattr(user, "username", "") or "").strip().lower()
    uid = str(getattr(user, "id", "") or "").strip().lower()
    return bool({email, username, uid} & allow)


def model_compare_armed() -> bool:
    s = get_settings()
    return bool(
        s.fitting_room_model_compare_enabled and s.fitting_room_model_compare_live_http
    )


def assert_model_compare_allowed(user: User) -> None:
    s = get_settings()
    if not bool(s.fitting_room_model_compare_enabled):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fitting Room model compare is disabled.",
        )
    if not user_on_model_compare_allowlist(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fitting Room model compare is owner-only.",
        )


def _max_provider_calls() -> int:
    return max(1, int(get_settings().fitting_room_model_compare_max_provider_calls or 3))


def _max_paid_ops() -> int:
    return max(0, int(get_settings().fitting_room_model_compare_max_paid_ops or 0))


def _retention_hours() -> int:
    return max(1, int(get_settings().fitting_room_model_compare_retention_hours or 72))


def _stale_seconds() -> int:
    return max(60, int(get_settings().fitting_room_model_compare_stale_seconds or 900))


def _max_b64_chars() -> int:
    max_bytes = get_settings().max_upload_bytes
    return (max_bytes * 4 // 3) + _B64_HEADER_SLACK


def _decode_and_validate_image(raw: str, *, field: str) -> bytes:
    """Bound base64 size, sniff type/dims, orient to PNG for provider compatibility."""
    if not isinstance(raw, str) or not raw.strip():
        raise HTTPException(status_code=400, detail=f"Missing {field} image.")
    text = raw.strip()
    if len(text) > _max_b64_chars():
        raise HTTPException(status_code=400, detail=f"{field} payload exceeds upload limit.")
    if "," in text and text.lower().startswith("data:"):
        text = text.split(",", 1)[1]
    if len(text) > _max_b64_chars():
        raise HTTPException(status_code=400, detail=f"{field} payload exceeds upload limit.")
    try:
        data = base64.b64decode(text, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid {field} image.") from exc
    settings = get_settings()
    if len(data) < 32:
        raise HTTPException(status_code=400, detail=f"{field} is empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail=f"{field} is too large.")
    kind = sniff_image_kind(data)
    if kind not in {"png", "jpeg"}:
        raise HTTPException(status_code=400, detail=f"{field} must be a PNG or JPEG image.")
    max_dim = max(
        int(settings.max_fabric_dimension_px or 2048),
        int(settings.max_croquis_dimension_px or 4096),
    )
    probed = probe_image_dimensions(data, kind)
    if probed is not None:
        w, h = probed
        if w < 1 or h < 1 or w > max_dim or h > max_dim:
            raise HTTPException(
                status_code=400,
                detail=f"{field} dimensions exceed allowed limits.",
            )
    try:
        opened = Image.open(io.BytesIO(data))
        oriented = ImageOps.exif_transpose(opened) or opened
        oriented.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"{field} is not a readable image.") from exc
    if oriented.mode in ("RGBA", "LA") or (
        oriented.mode == "P" and "transparency" in oriented.info
    ):
        converted = oriented.convert("RGBA")
    else:
        converted = oriented.convert("RGB")
    if converted.width > max_dim or converted.height > max_dim:
        raise HTTPException(
            status_code=400,
            detail=f"{field} dimensions exceed allowed limits.",
        )
    buf = io.BytesIO()
    converted.save(buf, format="PNG", optimize=True)
    out = buf.getvalue()
    if len(out) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail=f"{field} is too large.")
    return out


def _fingerprint(png: bytes) -> str:
    return hashlib.sha256(png).hexdigest()[:16]


def _estimate_cents(arm: dict[str, str]) -> int:
    if arm["provider"] == "openai":
        return _OPENAI_HIGH_PORTRAIT_ESTIMATE_CENTS
    return _FASHN_MAX_QUALITY_2K_CREDITS * _FASHN_CREDIT_CENTS


def _require_consent(*, consent_acknowledged: bool, consent_version: str) -> None:
    if not consent_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Model compare requires explicit consent that the person photo "
                "will be sent to third-party AI providers (OpenAI / FASHN)."
            ),
        )
    if (consent_version or "").strip() != COMPARE_CONSENT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model compare consent version is outdated.",
        )


def _budget_snapshot(db: Session) -> dict[str, Any]:
    max_ops = _max_paid_ops()
    claimed = (
        db.scalar(
            select(func.count())
            .select_from(FittingRoomModelCompareOperation)
            .where(
                FittingRoomModelCompareOperation.status.in_(
                    (
                        OP_STATUS_RUNNING,
                        OP_STATUS_COMPLETED,
                        OP_STATUS_FAILED,
                        OP_STATUS_EXHAUSTED,
                        OP_STATUS_RECONCILIATION,
                    )
                )
            )
        )
        or 0
    )
    dispatched = (
        db.scalar(
            select(func.coalesce(func.sum(FittingRoomModelCompareOperation.dispatched_requests), 0))
        )
        or 0
    )
    return {
        "max_paid_ops": max_ops,
        "ops_claimed": int(claimed),
        "ops_remaining": max(0, max_ops - int(claimed)),
        "max_provider_calls": _max_provider_calls(),
        "provider_calls_dispatched": int(dispatched),
        "authorization_exhausted": int(claimed) >= max_ops or max_ops <= 0,
    }


def _durable_commit(db: Session) -> None:
    """Persist the current unit of work. Fail closed if the commit fails."""
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not persist model-compare ledger; no provider call made.",
        ) from exc


def _arm_ledger(op: FittingRoomModelCompareOperation) -> dict[str, Any]:
    report = op.report if isinstance(op.report, dict) else {}
    ledger = report.get("arm_ledger")
    return dict(ledger) if isinstance(ledger, dict) else {}


def _set_arm_ledger(op: FittingRoomModelCompareOperation, ledger: dict[str, Any]) -> None:
    report = dict(op.report) if isinstance(op.report, dict) else {}
    report["arm_ledger"] = ledger
    op.report = report


def _assert_idempotency_identity(
    op: FittingRoomModelCompareOperation,
    *,
    person_fp: str,
    design_fp: str,
    arms: list[str],
) -> None:
    existing_arms = [str(a).upper() for a in (op.arms_requested or [])]
    if (
        (op.person_fingerprint or "") != person_fp
        or (op.design_fingerprint or "") != design_fp
        or existing_arms != list(arms)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "idempotency_key already used with different person/design fingerprints "
                "or selected arms."
            ),
        )


def _operation_is_stale(op: FittingRoomModelCompareOperation) -> bool:
    """True when a running op has had no durable ledger activity for too long."""
    ref = op.updated_at or op.created_at
    if ref is None:
        return True
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - ref
    return age.total_seconds() >= float(_stale_seconds())


def provider_gates_no_network() -> dict[str, Any]:
    """Credential / live-flag readiness without outbound provider HTTP."""
    s = get_settings()
    openai_key = bool((s.openai_api_key or "").strip())
    fashn_key = bool((s.fashn_api_key or "").strip())
    fashn_live = bool(s.fashn_try_on_live_http)
    fashn_max_live = bool(s.fashn_try_on_max_live_http)
    fashn_ready = fashn_key and fashn_live and fashn_max_live
    return {
        "openai": {
            "api_key_present": openai_key,
            "models": ["chatgpt-image-latest", "gpt-image-2.6-sunburst"],
            "ready": openai_key,
        },
        "fashn_tryon_max": {
            "api_key_present": fashn_key,
            "fashn_try_on_live_http": fashn_live,
            "fashn_try_on_max_live_http": fashn_max_live,
            "ready": fashn_ready,
        },
        "all_ready": openai_key and fashn_ready,
    }


def tick_model_compare_maintenance(db: Session, *, limit: int = 50) -> dict[str, int]:
    """Bounded maintenance tick — retention sweep without requiring an API request.

    Intended for the existing competition/public-cleanup maintenance loop.
    """
    _ = limit
    try:
        return run_model_compare_retention_sweep(db, dry_run=False, commit=True)
    except Exception:  # noqa: BLE001
        logger.info("model-compare maintenance tick failed", exc_info=True)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {"examined": 0, "files_removed": 0, "dry_run": 0, "error": 1}


def preflight_model_compare(user: User, db: Session) -> dict[str, Any]:
    s = get_settings()
    allowlisted = user_on_model_compare_allowlist(user)
    # Best-effort sweep on preflight; scheduled maintenance is the durable path.
    try:
        run_model_compare_retention_sweep(db, dry_run=False, commit=True)
    except Exception:  # noqa: BLE001
        logger.info("model-compare retention sweep skipped on preflight", exc_info=True)
    budget = _budget_snapshot(db)
    gates = provider_gates_no_network()
    return {
        "status": "preflight",
        "enabled": bool(s.fitting_room_model_compare_enabled),
        "live_http": bool(s.fitting_room_model_compare_live_http),
        "armed": model_compare_armed() and allowlisted and not budget["authorization_exhausted"],
        "owner_allowlisted": allowlisted,
        "prompt_version": COMPARE_PROMPT_VERSION,
        "prompt": COMPARE_PROMPT,
        "consent_version": COMPARE_CONSENT_VERSION,
        "notice_text": COMPARE_NOTICE,
        "authorize_paid": False,
        "stars_touched": False,
        "paid_calls": 0,
        "budget": budget,
        "provider_gates": gates,
        "stale_seconds": _stale_seconds(),
        "retention_hours": _retention_hours(),
        "arms": [
            {
                **spec,
                "estimate_cents": _estimate_cents(spec),
                "preprocessing": "none",
                "postprocessing": "none",
            }
            for spec in ARM_SPECS
        ],
        "human_review": {
            "instruction": (
                "Compare Face · Dress · Shoulders · Pose · Background. "
                "Do not auto-select a winner — human visual approval required."
            ),
            "winner": None,
        },
        "compare_dimensions": [
            "identity_face",
            "dress_accuracy",
            "shoulder_decorations",
            "pose",
            "background",
        ],
        "notes": [
            "One native call per arm. No materialize, mask, face composite, or color-lock.",
            "authorize_paid=false returns a dry-run plan only (0 paid calls).",
            "Paid budget is server-enforced (default 1 op / 3 provider calls). No auto retries.",
            "Results are private owner-only files — never public /static/uploads URLs.",
            "Does not change live Fitting Room, Stars, or other AI features.",
        ],
    }


def _result_ref(*, operation_id: uuid.UUID, arm: str) -> dict[str, str]:
    arm_u = arm.upper()
    return {
        "operation_id": str(operation_id),
        "arm": arm_u,
        "retrieval_path": (
            f"/api/v1/ai/fitting-room/model-compare/results/{operation_id}/{arm_u}"
        ),
    }


def _save_private_arm_png(
    *,
    owner_id: uuid.UUID,
    operation_id: uuid.UUID,
    arm: str,
    png: bytes,
) -> str:
    storage = LocalStorageBackend()
    key = storage.fitting_compare_storage_key(
        owner_id=owner_id, operation_id=operation_id, arm=arm
    )
    path = storage.save_private_fitting_compare_file(
        key=key, data=io.BytesIO(png), content_type="image/png"
    )
    # Refuse accidental public placement.
    try:
        path.resolve().relative_to(storage.public_upload_root())
    except ValueError:
        pass
    else:
        raise RuntimeError("refusing public placement of compare output")
    return key


def run_model_compare_retention_sweep(
    db: Session,
    *,
    dry_run: bool = False,
    commit: bool = True,
    owner_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """Delete expired private compare outputs (offline-capable sweeper).

    Expiration-on-retrieval alone is not enough — this walks expired ledger rows
    and unlinks files under ``private_fitting_compare/``.
    """
    now = datetime.now(timezone.utc)
    q = select(FittingRoomModelCompareOperation).where(
        FittingRoomModelCompareOperation.expires_at.is_not(None),
        FittingRoomModelCompareOperation.expires_at < now,
    )
    if owner_id is not None:
        q = q.where(FittingRoomModelCompareOperation.owner_id == owner_id)
    rows = list(db.scalars(q).all())
    storage = LocalStorageBackend()
    examined = len(rows)
    removed = 0
    for row in rows:
        report = dict(row.report) if isinstance(row.report, dict) else {}
        arms = list(report.get("arms") or [])
        changed = False
        for arm in arms:
            if not isinstance(arm, dict):
                continue
            key = arm.get("storage_key")
            if isinstance(key, str) and key:
                if dry_run:
                    removed += 1
                elif storage.delete_private_fitting_compare_file(key=key):
                    removed += 1
                    arm["storage_key"] = None
                    arm["result_ref"] = None
                    arm["expired"] = True
                    changed = True
        # Also unlink any ledger keys not mirrored in arms[].
        ledger = report.get("arm_ledger") if isinstance(report.get("arm_ledger"), dict) else {}
        for arm_key, entry in list(ledger.items()):
            if not isinstance(entry, dict):
                continue
            key = entry.get("storage_key")
            if isinstance(key, str) and key:
                if dry_run:
                    removed += 1
                elif storage.delete_private_fitting_compare_file(key=key):
                    removed += 1
                    entry["storage_key"] = None
                    entry["expired"] = True
                    ledger[arm_key] = entry
                    changed = True
        if changed and not dry_run:
            report["arms"] = arms
            report["arm_ledger"] = ledger
            row.report = report
    if rows and not dry_run:
        if commit:
            _durable_commit(db)
        else:
            db.flush()
    return {"examined": examined, "files_removed": removed, "dry_run": int(dry_run)}


def _purge_expired_outputs(db: Session, *, owner_id: uuid.UUID | None = None) -> int:
    """Compatibility wrapper — prefer ``run_model_compare_retention_sweep``."""
    result = run_model_compare_retention_sweep(
        db, dry_run=False, commit=False, owner_id=owner_id
    )
    return int(result["files_removed"])


def resolve_compare_result_file(
    db: Session, user: User, operation_id: uuid.UUID, arm: str
) -> Path:
    """Authenticated owner-only retrieval with path validation + retention."""
    assert_model_compare_allowed(user)
    run_model_compare_retention_sweep(db, dry_run=False, commit=True, owner_id=user.id)
    arm_u = (arm or "").strip().upper()
    if arm_u not in {"A", "B", "C"}:
        raise HTTPException(status_code=404, detail="Compare result not found.")
    op = db.get(FittingRoomModelCompareOperation, operation_id)
    if op is None or op.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Compare result not found.")
    if op.expires_at is not None and op.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Compare result expired.")
    storage = LocalStorageBackend()
    key = storage.fitting_compare_storage_key(
        owner_id=user.id, operation_id=operation_id, arm=arm_u
    )
    # Ownership is encoded in the validated key + DB owner check above.
    path = storage.resolve_private_fitting_compare_file(key=key)
    if path is None:
        raise HTTPException(status_code=404, detail="Compare result not found.")
    # Defense in depth: path must stay under private root and match owner.
    try:
        storage.validate_fitting_compare_storage_key(key)
        path.relative_to(storage.private_fitting_compare_root())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Compare result not found.") from exc
    owner_segment = path.parent.parent.name
    if owner_segment.lower() != str(user.id).lower():
        raise HTTPException(status_code=404, detail="Compare result not found.")
    return path


def _run_openai_images_edit(
    *,
    person_png: bytes,
    design_png: bytes,
    model: str,
) -> tuple[bytes, dict[str, Any]]:
    """Single images.edit: image1=person, image2=design. No mask / fidelity hacks."""
    from openai import OpenAI

    from app.services.personal_croquis_provider import extract_edit_png_bytes
    from app.services.sketch_openai import assert_image_model_editable, build_image_edit_kwargs

    settings = get_settings()
    if not (settings.openai_api_key or "").strip():
        raise RuntimeError("OPENAI_API_KEY missing")
    assert_image_model_editable(model)
    size = (settings.openai_image_size or "1024x1536").strip()
    kwargs = build_image_edit_kwargs(
        model=model,
        prompt=COMPARE_PROMPT,
        sketch=(person_png, "image/png"),
        size=size,
        quality="high",
        fabric_swatch=(design_png, "image/png"),
    )
    kwargs["image"] = [
        ("person.png", io.BytesIO(person_png), "image/png"),
        ("garment.png", io.BytesIO(design_png), "image/png"),
    ]
    kwargs["n"] = 1
    kwargs["output_format"] = "png"
    kwargs.pop("background", None)
    extra = dict(kwargs.get("extra_body") or {})
    extra["moderation"] = "low"
    kwargs["extra_body"] = extra

    t0 = time.perf_counter()
    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        timeout=float(settings.openai_timeout_seconds or 180),
    )
    # max_retries=0 — no automatic paid retries.
    result = client.with_options(max_retries=0).images.edit(**kwargs)
    png = extract_edit_png_bytes(result)
    ms = int((time.perf_counter() - t0) * 1000)
    meta = {
        "provider": "openai",
        "model": kwargs.get("model"),
        "path": "openai_images_edit_person_garment",
        "prompt_version": COMPARE_PROMPT_VERSION,
        "prompt": COMPARE_PROMPT,
        "image_order": ["person", "garment"],
        "size": kwargs.get("size"),
        "quality": kwargs.get("quality"),
        "duration_ms": ms,
        "estimate_cents": _OPENAI_HIGH_PORTRAIT_ESTIMATE_CENTS,
        "openai_calls": 1,
        "preprocessing": "none",
        "postprocessing": "none",
        "identity_lock": False,
        "materialize": False,
        "color_lock": False,
    }
    return png, meta


def _run_fashn_tryon_max_raw(
    *,
    person_png: bytes,
    design_png: bytes,
) -> tuple[bytes, dict[str, Any]]:
    """Single FASHN tryon-max call with raw person + raw design (no prep split)."""
    import httpx

    from app.services.fashn_try_on_max_provider import (
        FASHN_MAX_MODEL_NAME,
        build_tryon_max_run_payload,
        estimate_fashn_max_cost_cents,
        fashn_max_prompt_hash,
    )
    from app.services.fashn_try_on_provider import (
        _ensure_rgb_jpegish_png,
        _to_data_uri_png,
    )

    settings = get_settings()
    api_key = (settings.fashn_api_key or "").strip()
    if not api_key:
        raise RuntimeError("FASHN_API_KEY missing")
    if not bool(settings.fashn_try_on_max_live_http):
        raise RuntimeError("FASHN_TRY_ON_MAX_LIVE_HTTP is false")
    if not bool(settings.fashn_try_on_live_http):
        raise RuntimeError("FASHN_TRY_ON_LIVE_HTTP is false")

    # Provider-compatibility normalize only (RGB/JPEG-ish), not garment materialize.
    model_bytes = _ensure_rgb_jpegish_png(person_png)
    product_bytes = _ensure_rgb_jpegish_png(design_png)
    fashn_prompt = (
        "Fit the exact garment from the product image onto the person. "
        "Preserve the person's original face, hair, body, pose, and background. "
        "Keep the garment's exact colors, silhouette, decorative details, and length. "
        "Make the clothing naturally photorealistic. Do not change anything else."
    )
    payload = build_tryon_max_run_payload(
        model_image=_to_data_uri_png(model_bytes),
        product_image=_to_data_uri_png(product_bytes),
        prompt=fashn_prompt,
        generation_mode="quality",
        resolution="2k",
        seed=42,
        num_images=1,
    )
    base = (settings.fashn_api_base_url or "https://api.fashn.ai").rstrip("/")
    timeout = float(settings.fashn_poll_timeout_seconds or 120)
    interval = float(settings.fashn_poll_interval_seconds or 2)

    t0 = time.perf_counter()
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        run = client.post(
            f"{base}/v1/run",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        run.raise_for_status()
        body = run.json()
        pred_id = str(body.get("id") or body.get("prediction_id") or "")
        if not pred_id:
            raise RuntimeError("FASHN Max run missing prediction id")
        deadline = time.time() + timeout
        status_body: dict[str, Any] = {}
        while time.time() < deadline:
            st = client.get(
                f"{base}/v1/status/{pred_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            st.raise_for_status()
            status_body = st.json()
            state = str(status_body.get("status") or "").lower()
            if state in {"completed", "succeeded", "success"}:
                break
            if state in {"failed", "error", "cancelled"}:
                raise RuntimeError(f"FASHN Max failed: {state}")
            time.sleep(interval)
        else:
            raise RuntimeError("FASHN Max poll timeout")

    out = status_body.get("output")
    if not isinstance(out, list) or not out:
        raise RuntimeError("FASHN Max empty output")
    item = out[0]
    if isinstance(item, str) and item.startswith("data:"):
        b64 = item.split(",", 1)[1]
        png = base64.b64decode(b64)
    elif isinstance(item, str) and item.startswith("http"):
        with httpx.Client(timeout=60.0) as client:
            r = client.get(item)
            r.raise_for_status()
            png = r.content
    elif isinstance(item, dict) and item.get("b64_json"):
        png = base64.b64decode(item["b64_json"])
    else:
        # Ambiguous shape — fail closed; do not invent another provider call.
        raise RuntimeError("Unrecognized FASHN Max output shape")

    ms = int((time.perf_counter() - t0) * 1000)
    credits = int(status_body.get("credits") or _FASHN_MAX_QUALITY_2K_CREDITS)
    meta = {
        "provider": "fashn",
        "model": FASHN_MAX_MODEL_NAME,
        "path": "fashn_tryon_max_raw_person_product",
        "prompt_version": COMPARE_PROMPT_VERSION,
        "prompt": fashn_prompt,
        "prompt_hash": fashn_max_prompt_hash(fashn_prompt),
        "generation_mode": "quality",
        "resolution": "2k",
        "prediction_id": pred_id,
        "credits_used": credits,
        "duration_ms": ms,
        "estimate_cents": estimate_fashn_max_cost_cents(
            generation_mode="quality", resolution="2k", fashn_calls=1
        ),
        "fashn_calls": 1,
        "preprocessing": "none",
        "postprocessing": "none",
        "identity_lock": False,
        "materialize": False,
        "color_lock": False,
    }
    return png, meta


# Injected in tests — never live OpenAI/FASHN unless authorize_paid + armed.
_openai_runner: Callable[..., tuple[bytes, dict[str, Any]]] | None = None
_fashn_runner: Callable[..., tuple[bytes, dict[str, Any]]] | None = None


def set_model_compare_runners_for_tests(
    *,
    openai_runner: Callable[..., tuple[bytes, dict[str, Any]]] | None = None,
    fashn_runner: Callable[..., tuple[bytes, dict[str, Any]]] | None = None,
) -> None:
    global _openai_runner, _fashn_runner
    _openai_runner = openai_runner
    _fashn_runner = fashn_runner


def _claim_paid_operation(
    db: Session,
    *,
    user: User,
    idempotency_key: str,
    consent_version: str,
    arms: list[str],
    person_fp: str,
    design_fp: str,
) -> tuple[FittingRoomModelCompareOperation, bool]:
    """Atomically claim + COMMIT the one-shot budget, or return a durable replay.

    The advisory transaction lock, budget check, insert, and COMMIT are one unit.
    Returns ``(operation, is_replay)``. Replay never dispatches again.
    """
    key = (idempotency_key or "").strip()
    if not key or len(key) < 8 or len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="idempotency_key is required (8–128 chars).",
        )

    # Serialize claims globally so concurrent POSTs cannot double-spend budget.
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": MODEL_COMPARE_GLOBAL_LOCK_KEY})

    existing = db.scalar(
        select(FittingRoomModelCompareOperation).where(
            FittingRoomModelCompareOperation.owner_id == user.id,
            FittingRoomModelCompareOperation.idempotency_key == key,
        )
    )
    if existing is not None:
        _assert_idempotency_identity(
            existing, person_fp=person_fp, design_fp=design_fp, arms=arms
        )
        return existing, True

    budget = _budget_snapshot(db)
    if budget["authorization_exhausted"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Model compare paid authorization is exhausted "
                f"({budget['ops_claimed']}/{budget['max_paid_ops']} ops used)."
            ),
        )

    op = FittingRoomModelCompareOperation(
        id=uuid.uuid4(),
        owner_id=user.id,
        idempotency_key=key,
        status=OP_STATUS_RUNNING,
        consent_version=consent_version,
        arms_requested=list(arms),
        dispatched_requests=0,
        successful_outputs=0,
        max_provider_calls=_max_provider_calls(),
        person_fingerprint=person_fp,
        design_fingerprint=design_fp,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=_retention_hours()),
        report={
            "status": "running",
            "arms": [],
            "arm_ledger": {},
            "dispatched_requests": 0,
            "successful_outputs": 0,
        },
    )
    try:
        with db.begin_nested():
            db.add(op)
            db.flush()
    except IntegrityError as exc:
        # Concurrent same-key insert — reload replay (savepoint keeps outer txn alive).
        replay = db.scalar(
            select(FittingRoomModelCompareOperation).where(
                FittingRoomModelCompareOperation.owner_id == user.id,
                FittingRoomModelCompareOperation.idempotency_key == key,
            )
        )
        if replay is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not claim compare operation; retry dry-run only.",
            ) from exc
        _assert_idempotency_identity(
            replay, person_fp=person_fp, design_fp=design_fp, arms=arms
        )
        return replay, True

    # Durable claim — must land before any provider generation request.
    _durable_commit(db)
    db.refresh(op)
    return op, False


def _finalize_replay_without_dispatch(
    db: Session, op: FittingRoomModelCompareOperation
) -> dict[str, Any]:
    """HTTP replay of an existing op — never dispatch again.

    Healthy in-flight (recent ``updated_at``): return current running status so a
    concurrent same-key replay cannot kill remaining arms.

    Only when the attempt is safely identified as interrupted/stale do pending
    ``dispatched`` arms become ``unknown`` → ``reconciliation_required``.
    Unknown paid outcomes are never retried.
    """
    if op.status in TERMINAL_OP_STATUSES:
        return _report_from_operation(op)

    if op.status == OP_STATUS_RUNNING and not _operation_is_stale(op):
        # Active request still progressing — do not reconcile.
        out = _report_from_operation(op)
        out["status"] = OP_STATUS_RUNNING
        out["replay"] = True
        out["in_flight"] = True
        out["note"] = (
            "Operation still running; same-key replay does not redispatch or "
            "mark reconciliation."
        )
        return out

    # Stale / interrupted running op with unresolved dispatches.
    ledger = _arm_ledger(op)
    changed = False
    for arm_key, entry in list(ledger.items()):
        if not isinstance(entry, dict):
            continue
        if entry.get("status") == "dispatched":
            entry["status"] = "unknown"
            entry["error_type"] = "ReconciliationRequired"
            entry["error"] = (
                "Provider outcome unknown after interrupted/stale attempt; "
                "budget retained; no retry."
            )
            entry["no_retry"] = True
            ledger[arm_key] = entry
            changed = True

    if changed or op.status == OP_STATUS_RUNNING:
        _set_arm_ledger(op, ledger)
        report = dict(op.report) if isinstance(op.report, dict) else {}
        arms_out = list(report.get("arms") or [])
        by_arm = {
            str(a.get("arm")).upper(): a for a in arms_out if isinstance(a, dict) and a.get("arm")
        }
        for arm_key, entry in ledger.items():
            if entry.get("status") == "unknown":
                row = dict(by_arm.get(arm_key) or {"arm": arm_key})
                row.update(
                    {
                        "status": "unknown",
                        "error_type": entry.get("error_type"),
                        "error": entry.get("error"),
                        "no_retry": True,
                        "result_ref": None,
                        "result_url": None,
                    }
                )
                by_arm[arm_key] = row
        report["arms"] = list(by_arm.values())
        report["status"] = OP_STATUS_RECONCILIATION
        op.report = report
        op.status = OP_STATUS_RECONCILIATION
        op.error_detail = (op.error_detail or "reconciliation_required")[:512]
        _durable_commit(db)
        db.refresh(op)

    return _report_from_operation(op)


def _report_from_operation(op: FittingRoomModelCompareOperation) -> dict[str, Any]:
    if isinstance(op.report, dict) and op.report:
        out = dict(op.report)
        out["operation_id"] = str(op.id)
        out["idempotency_key"] = op.idempotency_key
        out["status"] = op.status if op.status in TERMINAL_OP_STATUSES else out.get("status", op.status)
        out["replay"] = True
        out["dispatched_requests"] = op.dispatched_requests
        out["successful_outputs"] = op.successful_outputs
        out["person_fingerprint"] = op.person_fingerprint
        out["design_fingerprint"] = op.design_fingerprint
        out["authorize_paid"] = True
        out["stars_touched"] = False
        out["paid_calls"] = int(op.dispatched_requests or 0)
        out.setdefault(
            "human_review",
            {
                "instruction": (
                    "Compare Face · Dress · Shoulders · Pose · Background. "
                    "Do not auto-select a winner — human visual approval required."
                ),
                "winner": None,
            },
        )
        out.setdefault(
            "compare_dimensions",
            [
                "identity_face",
                "dress_accuracy",
                "shoulder_decorations",
                "pose",
                "background",
            ],
        )
        return out
    return {
        "status": op.status,
        "operation_id": str(op.id),
        "idempotency_key": op.idempotency_key,
        "prompt_version": COMPARE_PROMPT_VERSION,
        "prompt": COMPARE_PROMPT,
        "consent_version": op.consent_version,
        "person_fingerprint": op.person_fingerprint,
        "design_fingerprint": op.design_fingerprint,
        "authorize_paid": True,
        "live_http": model_compare_armed(),
        "stars_touched": False,
        "paid_calls": int(op.dispatched_requests or 0),
        "dispatched_requests": int(op.dispatched_requests or 0),
        "successful_outputs": int(op.successful_outputs or 0),
        "replay": True,
        "arms": [],
        "human_review": {
            "instruction": (
                "Compare Face · Dress · Shoulders · Pose · Background. "
                "Do not auto-select a winner — human visual approval required."
            ),
            "winner": None,
        },
        "compare_dimensions": [
            "identity_face",
            "dress_accuracy",
            "shoulder_decorations",
            "pose",
            "background",
        ],
        "error_detail": op.error_detail,
    }


def _commit_arm_dispatch(
    db: Session,
    op: FittingRoomModelCompareOperation,
    *,
    arm: str,
    spec: dict[str, str],
) -> dict[str, Any]:
    """Durably record a dispatched attempt BEFORE the paid provider call."""
    # Re-lock the row so concurrent workers cannot double-dispatch.
    locked = db.scalar(
        select(FittingRoomModelCompareOperation)
        .where(FittingRoomModelCompareOperation.id == op.id)
        .with_for_update()
    )
    if locked is None:
        raise HTTPException(status_code=409, detail="Compare operation missing.")
    if locked.status in TERMINAL_OP_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Compare operation is terminal; no further provider calls.",
        )
    ledger = _arm_ledger(locked)
    if arm in ledger:
        raise HTTPException(
            status_code=409,
            detail=f"Arm {arm} was already dispatched; no retry.",
        )
    if int(locked.dispatched_requests) >= int(locked.max_provider_calls):
        raise HTTPException(
            status_code=403,
            detail="Provider call budget exhausted for this operation.",
        )

    locked.dispatched_requests = int(locked.dispatched_requests) + 1
    entry = {
        "arm": arm,
        "status": "dispatched",
        "provider": spec.get("provider"),
        "model": spec.get("model"),
        "path": spec.get("path"),
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
        "no_retry": True,
    }
    ledger[arm] = entry
    report = dict(locked.report) if isinstance(locked.report, dict) else {}
    report["arm_ledger"] = ledger
    report["dispatched_requests"] = locked.dispatched_requests
    arms_out = list(report.get("arms") or [])
    arms_out.append(
        {
            **spec,
            "status": "dispatched",
            "estimate_cents": _estimate_cents(spec),
            "preprocessing": "none",
            "postprocessing": "none",
            "result_url": None,
            "no_retry": True,
        }
    )
    report["arms"] = arms_out
    locked.report = report
    _durable_commit(db)
    db.refresh(locked)
    # Keep caller reference in sync.
    op.dispatched_requests = locked.dispatched_requests
    op.report = locked.report
    op.status = locked.status
    return entry


def _commit_arm_outcome(
    db: Session,
    op: FittingRoomModelCompareOperation,
    *,
    arm: str,
    arm_result: dict[str, Any],
) -> None:
    locked = db.scalar(
        select(FittingRoomModelCompareOperation)
        .where(FittingRoomModelCompareOperation.id == op.id)
        .with_for_update()
    )
    if locked is None:
        return
    ledger = _arm_ledger(locked)
    entry = dict(ledger.get(arm) or {"arm": arm})
    entry["status"] = arm_result.get("status")
    entry["storage_key"] = arm_result.get("storage_key")
    entry["result_ref"] = arm_result.get("result_ref")
    entry["error_type"] = arm_result.get("error_type")
    entry["error"] = arm_result.get("error")
    entry["no_retry"] = True
    entry["completed_at"] = datetime.now(timezone.utc).isoformat()
    ledger[arm] = entry

    if arm_result.get("status") == "ok":
        locked.successful_outputs = int(locked.successful_outputs) + 1

    report = dict(locked.report) if isinstance(locked.report, dict) else {}
    report["arm_ledger"] = ledger
    report["successful_outputs"] = locked.successful_outputs
    report["dispatched_requests"] = locked.dispatched_requests
    arms_out = []
    replaced = False
    for existing in report.get("arms") or []:
        if isinstance(existing, dict) and str(existing.get("arm")).upper() == arm:
            arms_out.append({**existing, **arm_result})
            replaced = True
        elif isinstance(existing, dict):
            arms_out.append(existing)
    if not replaced:
        arms_out.append(arm_result)
    report["arms"] = arms_out
    locked.report = report
    _durable_commit(db)
    db.refresh(locked)
    op.successful_outputs = locked.successful_outputs
    op.dispatched_requests = locked.dispatched_requests
    op.report = locked.report


def _commit_operation_finished(
    db: Session,
    op: FittingRoomModelCompareOperation,
    *,
    report: dict[str, Any],
    final_status: str,
) -> None:
    locked = db.scalar(
        select(FittingRoomModelCompareOperation)
        .where(FittingRoomModelCompareOperation.id == op.id)
        .with_for_update()
    )
    if locked is None:
        return
    locked.status = final_status
    lean = {
        k: v
        for k, v in report.items()
        if k not in {"notice_text"}
    }
    lean["status"] = final_status
    lean["arm_ledger"] = _arm_ledger(locked)
    locked.report = lean
    _durable_commit(db)
    db.refresh(locked)
    op.status = locked.status
    op.report = locked.report


def run_model_compare(
    *,
    db: Session,
    user: User,
    person_image_base64: str,
    design_image_base64: str,
    authorize_paid: bool = False,
    arms: list[str] | None = None,
    consent_acknowledged: bool = False,
    consent_version: str = "",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Run (or dry-run) the A/B/C comparison. Never charges Stars."""
    assert_model_compare_allowed(user)
    run_model_compare_retention_sweep(db, dry_run=False, commit=True, owner_id=user.id)

    # Consent required for any paid path; dry-run also asks so the owner sees the notice.
    _require_consent(
        consent_acknowledged=consent_acknowledged,
        consent_version=consent_version,
    )

    person_png = _decode_and_validate_image(person_image_base64, field="person")
    design_png = _decode_and_validate_image(design_image_base64, field="design")
    wanted = {a.strip().upper() for a in (arms or ["A", "B", "C"]) if a.strip()}
    selected = [spec for spec in ARM_SPECS if spec["arm"] in wanted]
    if not selected:
        raise HTTPException(status_code=400, detail="Select at least one arm: A, B, C.")
    if len(selected) > _max_provider_calls():
        raise HTTPException(
            status_code=400,
            detail=f"At most {_max_provider_calls()} arms allowed for one compare operation.",
        )

    person_fp = _fingerprint(person_png)
    design_fp = _fingerprint(design_png)
    budget = _budget_snapshot(db)
    selected_arms = [s["arm"] for s in selected]

    report: dict[str, Any] = {
        "status": "dry_run" if not authorize_paid else "completed",
        "prompt_version": COMPARE_PROMPT_VERSION,
        "prompt": COMPARE_PROMPT,
        "consent_version": COMPARE_CONSENT_VERSION,
        "notice_text": COMPARE_NOTICE,
        "person_fingerprint": person_fp,
        "design_fingerprint": design_fp,
        "authorize_paid": bool(authorize_paid),
        "live_http": model_compare_armed(),
        "stars_touched": False,
        "paid_calls": 0,
        "dispatched_requests": 0,
        "successful_outputs": 0,
        "budget": budget,
        "replay": False,
        "arms": [],
        "human_review": {
            "instruction": (
                "Compare Face · Dress · Shoulders · Pose · Background. "
                "Do not auto-select a winner — human visual approval required."
            ),
            "winner": None,
        },
        "compare_dimensions": [
            "identity_face",
            "dress_accuracy",
            "shoulder_decorations",
            "pose",
            "background",
        ],
    }

    if not authorize_paid:
        for spec in selected:
            report["arms"].append(
                {
                    **spec,
                    "status": "planned",
                    "estimate_cents": _estimate_cents(spec),
                    "preprocessing": "none",
                    "postprocessing": "none",
                    "result_ref": None,
                    "result_url": None,
                    "note": (
                        "Dry-run only. Set authorize_paid=true with consent + "
                        "idempotency_key after explicit approval."
                    ),
                }
            )
        return report

    if not model_compare_armed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Paid model compare is not armed "
                "(FITTING_ROOM_MODEL_COMPARE_ENABLED + LIVE_HTTP)."
            ),
        )

    op, is_replay = _claim_paid_operation(
        db,
        user=user,
        idempotency_key=idempotency_key or "",
        consent_version=COMPARE_CONSENT_VERSION,
        arms=selected_arms,
        person_fp=person_fp,
        design_fp=design_fp,
    )
    if is_replay:
        return _finalize_replay_without_dispatch(db, op)

    report["operation_id"] = str(op.id)
    report["idempotency_key"] = op.idempotency_key
    report["status"] = "running"

    for spec in selected:
        arm = spec["arm"]
        arm_result: dict[str, Any] = {
            **spec,
            "estimate_cents": _estimate_cents(spec),
            "preprocessing": "none",
            "postprocessing": "none",
            "result_url": None,  # never public
            "no_retry": True,
        }

        # Durably COMMIT the dispatch attempt before any paid provider call.
        try:
            _commit_arm_dispatch(db, op, arm=arm, spec=spec)
        except HTTPException as exc:
            if exc.status_code in {403, 409}:
                arm_result.update(
                    {
                        "status": "skipped_budget",
                        "error_type": "BudgetExhausted",
                        "error": str(exc.detail),
                        "result_ref": None,
                    }
                )
                report["arms"].append(arm_result)
                continue
            raise

        report["dispatched_requests"] = int(op.dispatched_requests)
        report["paid_calls"] = int(op.dispatched_requests)

        try:
            if spec["provider"] == "openai":
                runner = _openai_runner or _run_openai_images_edit
                png, meta = runner(
                    person_png=person_png,
                    design_png=design_png,
                    model=spec["model"],
                )
            else:
                runner = _fashn_runner or _run_fashn_tryon_max_raw
                png, meta = runner(person_png=person_png, design_png=design_png)

            # Ambiguous empty output → fail this arm; do not retry.
            if not png or len(png) < 32:
                raise RuntimeError("Provider returned empty/ambiguous image")

            storage_key = _save_private_arm_png(
                owner_id=user.id,
                operation_id=op.id,
                arm=arm,
                png=png,
            )
            arm_result.update(
                {
                    "status": "ok",
                    "storage_key": storage_key,
                    "result_ref": _result_ref(operation_id=op.id, arm=arm),
                    "meta": meta,
                    "duration_ms": meta.get("duration_ms"),
                    "estimate_cents": meta.get("estimate_cents", arm_result["estimate_cents"]),
                }
            )
        except Exception as exc:  # noqa: BLE001
            # Ambiguous / failed outcomes do NOT trigger another attempt.
            logger.info(
                "model-compare arm %s failed: %s",
                arm,
                type(exc).__name__,
                exc_info=True,
            )
            arm_result.update(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                    "result_ref": None,
                    "storage_key": None,
                    "no_retry": True,
                }
            )

        _commit_arm_outcome(db, op, arm=arm, arm_result=arm_result)
        report["arms"].append(arm_result)
        report["successful_outputs"] = int(op.successful_outputs)

    report["status"] = "completed"
    report["budget"] = _budget_snapshot(db)
    report["human_review"]["winner"] = None
    report["dispatched_requests"] = int(op.dispatched_requests)
    report["paid_calls"] = int(op.dispatched_requests)
    _commit_operation_finished(db, op, report=report, final_status=OP_STATUS_COMPLETED)
    report["status"] = OP_STATUS_COMPLETED
    return report
