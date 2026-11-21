"""Shared OpenAI images.edit: person photo + garment design (two images).

Used by the owner-only model-compare Arm B path and the Fitting Room
Model B (``gpt-image-2.6-sunburst``) workflow. No mask, no input_fidelity
hacks, no automatic paid retries.
"""

from __future__ import annotations

import io
import time
from typing import Any

from app.core.config import get_settings


def run_openai_person_garment_images_edit(
    *,
    person_png: bytes,
    design_png: bytes,
    model: str,
    prompt: str,
    prompt_version: str,
    path: str = "openai_images_edit_person_garment",
    quality: str = "high",
    estimate_cents: int | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Single ``images.edit``: image1=person, image2=design.

    ``max_retries=0`` — callers must not wrap this in silent paid retries.
    """
    from openai import OpenAI

    from app.services.personal_croquis_provider import extract_edit_png_bytes
    from app.services.sketch_openai import assert_image_model_editable, build_image_edit_kwargs

    settings = get_settings()
    if not (settings.openai_api_key or "").strip():
        raise RuntimeError("OPENAI_API_KEY missing")
    model_id = (model or "").strip()
    if not model_id:
        raise RuntimeError("OpenAI image model id is required")
    assert_image_model_editable(model_id)

    size = (settings.openai_image_size or "1024x1536").strip()
    quality_id = (quality or "high").strip() or "high"
    kwargs = build_image_edit_kwargs(
        model=model_id,
        prompt=prompt,
        sketch=(person_png, "image/png"),
        size=size,
        quality=quality_id,
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
    meta: dict[str, Any] = {
        "provider": "openai",
        "model": kwargs.get("model"),
        "path": path,
        "prompt_version": prompt_version,
        "prompt": prompt,
        "image_order": ["person", "garment"],
        "size": kwargs.get("size"),
        "quality": kwargs.get("quality"),
        "duration_ms": ms,
        "openai_calls": 1,
        "preprocessing": "none",
        "postprocessing": "none",
        "identity_lock": False,
        "materialize": False,
        "color_lock": False,
        "mask": False,
        "face_patch": False,
        "paid_retries": 0,
    }
    if estimate_cents is not None:
        meta["estimate_cents"] = int(estimate_cents)
    return png, meta
