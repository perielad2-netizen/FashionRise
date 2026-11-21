"""Owner-only Fitting Room model comparison (clean one-call A/B/C).

Purpose: find which provider produces an acceptable **raw** try-on in a single
call — no masks, face composites, materialize, color-lock, or provider chains.

Arms:
  A) OpenAI ``chatgpt-image-latest`` via ``images.edit`` (person + design)
  B) OpenAI ``gpt-image-2.6-sunburst`` via ``images.edit`` (person + design)
  C) FASHN ``tryon-max`` (model_image + product_image)

Fail closed: feature flag + owner allowlist + explicit ``authorize_paid``.
Does **not** change the live Fitting Room path or Stars billing.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import time
import uuid
from typing import Any, Callable

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.user import User
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

COMPARE_PROMPT_VERSION = "fitting-room-model-compare-v1"
COMPARE_CONSENT = "fitting-room-model-compare-v1"

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


def _decode_data_url_png(raw: str, *, field: str) -> bytes:
    text = (raw or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail=f"Missing {field} image.")
    if "," in text and text.lower().startswith("data:"):
        text = text.split(",", 1)[1]
    try:
        data = base64.b64decode(text, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid {field} image.") from exc
    if len(data) < 32 or data[:8] != b"\x89PNG\r\n\x1a\n":
        # Accept JPEG too — providers can ingest; normalize later if needed.
        if not (data[:2] == b"\xff\xd8" or data[:4] == b"RIFF"):
            raise HTTPException(status_code=400, detail=f"{field} must be an image.")
    return data


def _fingerprint(png: bytes) -> str:
    return hashlib.sha256(png).hexdigest()[:16]


def _estimate_cents(arm: dict[str, str]) -> int:
    if arm["provider"] == "openai":
        return _OPENAI_HIGH_PORTRAIT_ESTIMATE_CENTS
    return _FASHN_MAX_QUALITY_2K_CREDITS * _FASHN_CREDIT_CENTS


def preflight_model_compare(user: User) -> dict[str, Any]:
    s = get_settings()
    allowlisted = user_on_model_compare_allowlist(user)
    return {
        "status": "preflight",
        "enabled": bool(s.fitting_room_model_compare_enabled),
        "live_http": bool(s.fitting_room_model_compare_live_http),
        "armed": model_compare_armed() and allowlisted,
        "owner_allowlisted": allowlisted,
        "prompt_version": COMPARE_PROMPT_VERSION,
        "prompt": COMPARE_PROMPT,
        "authorize_paid": False,
        "stars_touched": False,
        "paid_calls": 0,
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
            "Does not change live Fitting Room, Stars, or other AI features.",
        ],
    }


def _save_private_png(png: bytes, *, label: str) -> str:
    key = f"private/fitting_room_compare/{uuid.uuid4().hex[:12]}_{label}.png"
    return LocalStorageBackend().save_file(
        key=key, data=io.BytesIO(png), content_type="image/png"
    )


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

    model_bytes = _ensure_rgb_jpegish_png(person_png)
    product_bytes = _ensure_rgb_jpegish_png(design_png)
    # FASHN Max prompt field is separate from OpenAI image-index wording.
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


def run_model_compare(
    *,
    user: User,
    person_image_base64: str,
    design_image_base64: str,
    authorize_paid: bool = False,
    arms: list[str] | None = None,
) -> dict[str, Any]:
    """Run (or dry-run) the A/B/C comparison. Never charges Stars."""
    assert_model_compare_allowed(user)
    person_png = _decode_data_url_png(person_image_base64, field="person")
    design_png = _decode_data_url_png(design_image_base64, field="design")
    wanted = {a.strip().upper() for a in (arms or ["A", "B", "C"]) if a.strip()}
    selected = [spec for spec in ARM_SPECS if spec["arm"] in wanted]
    if not selected:
        raise HTTPException(status_code=400, detail="Select at least one arm: A, B, C.")

    report: dict[str, Any] = {
        "status": "dry_run" if not authorize_paid else "completed",
        "prompt_version": COMPARE_PROMPT_VERSION,
        "prompt": COMPARE_PROMPT,
        "person_fingerprint": _fingerprint(person_png),
        "design_fingerprint": _fingerprint(design_png),
        "authorize_paid": bool(authorize_paid),
        "live_http": model_compare_armed(),
        "stars_touched": False,
        "paid_calls": 0,
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
                    "result_url": None,
                    "note": "Dry-run only. Set authorize_paid=true after explicit approval.",
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

    for spec in selected:
        arm_result: dict[str, Any] = {
            **spec,
            "estimate_cents": _estimate_cents(spec),
            "preprocessing": "none",
            "postprocessing": "none",
        }
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
            url = _save_private_png(png, label=f"arm_{spec['arm']}")
            arm_result.update(
                {
                    "status": "ok",
                    "result_url": url,
                    "meta": meta,
                    "duration_ms": meta.get("duration_ms"),
                    "estimate_cents": meta.get("estimate_cents", arm_result["estimate_cents"]),
                }
            )
            report["paid_calls"] = int(report["paid_calls"]) + int(
                meta.get("openai_calls") or meta.get("fashn_calls") or 1
            )
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "model-compare arm %s failed: %s",
                spec["arm"],
                type(exc).__name__,
                exc_info=True,
            )
            arm_result.update(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                    "result_url": None,
                }
            )
        report["arms"].append(arm_result)

    report["status"] = "completed"
    return report
