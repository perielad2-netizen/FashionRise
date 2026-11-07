"""Paid AI fabric tile generation → private fabric_assets library."""

from __future__ import annotations

import base64
import logging
from typing import Any, Callable

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.fabric_asset import FabricAsset
from app.models.user import User
from app.services.fabric_ai_prompt import FabricPromptPlan, validate_ai_fabric_prompt
from app.services.fabric_asset_service import create_fabric_asset_from_png
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

# Soft estimate for one 1024² medium generate (operator ceiling still applies).
AI_FABRIC_ESTIMATE_CENTS = 12
AI_FABRIC_SIZE = "1024x1024"

_GenerateFn = Callable[[str], bytes]


class FabricAiNotAvailableError(Exception):
    """AI fabric generation not armed / configured."""


def assert_ai_fabric_armed() -> None:
    settings = get_settings()
    if not settings.my_croquis_ai_enabled:
        raise FabricAiNotAvailableError("AI fabric creation is not enabled.")
    if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
        raise FabricAiNotAvailableError("AI spend ceiling is closed.")
    if not (settings.openai_api_key or "").strip():
        raise FabricAiNotAvailableError("OpenAI API key is not configured.")
    if not settings.my_croquis_ai_live_http:
        raise FabricAiNotAvailableError("Live AI HTTP is not armed.")


def _extract_png_bytes(result: Any) -> bytes:
    data = getattr(result, "data", None) or []
    if not data:
        raise RuntimeError("Image generate returned no data")
    item = data[0]
    b64 = getattr(item, "b64_json", None)
    if b64 is None and isinstance(item, dict):
        b64 = item.get("b64_json")
    if not b64:
        raise RuntimeError("Image generate missing b64_json")
    raw = base64.b64decode(b64)
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Image generate did not return PNG bytes")
    return raw


def default_generate_fabric_png(plan: FabricPromptPlan) -> bytes:
    """One images.generate call for a seamless textile tile."""
    assert_ai_fabric_armed()
    settings = get_settings()
    model = (settings.openai_image_model or "gpt-image-2.5-sunburst").strip()
    quality = (settings.openai_image_quality or "medium").strip() or "medium"
    # Prefer square tile; fall back if model rejects unknown size via API error.
    size = AI_FABRIC_SIZE

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        timeout=float(settings.openai_timeout_seconds or 180),
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "prompt": plan.generate_prompt,
        "size": size,
        "n": 1,
    }
    # Newer image models accept quality / output_format; older ones ignore extras poorly.
    if model.startswith("gpt-image"):
        kwargs["quality"] = quality
        kwargs["output_format"] = "png"

    try:
        result = client.with_options(max_retries=0).images.generate(**kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI fabric generate failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Fabric generation failed. Try a clearer fabric description.",
        ) from exc

    try:
        return _extract_png_bytes(result)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Fabric generation returned an unusable image.",
        ) from exc


def create_ai_fabric_asset(
    db: Session,
    user: User,
    *,
    prompt: str,
    color_hex: str | None = None,
    name: str | None = None,
    generate_png: _GenerateFn | None = None,
) -> FabricAsset:
    """Validate → generate tile → store as private fabric with Magic prompt_short."""
    try:
        assert_ai_fabric_armed()
    except FabricAiNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    plan = validate_ai_fabric_prompt(prompt=prompt, color_hex=color_hex, name=name)
    from app.core.errors import ForbiddenError
    from app.services import ai_stars

    # Affordability gate only — Stars debit after a usable tile is saved.
    try:
        ai_stars.assert_can_spend(db, user, "fabric")
    except ForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    # generate_png hook receives the generate prompt string for easy mocking.
    if generate_png is not None:
        png = generate_png(plan.generate_prompt)
    else:
        png = default_generate_fabric_png(plan)

    row = create_fabric_asset_from_png(
        db,
        user,
        png_bytes=png,
        name=plan.name,
        source="ai",
        prompt_raw=plan.prompt_raw,
        prompt_short=plan.prompt_short,
        color_hex=plan.color_hex,
    )
    # Touch storage path exists (defense — create already saved).
    storage = LocalStorageBackend()
    if storage.resolve_private_file(key=row.storage_key) is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fabric file failed to save.",
        )
    try:
        ai_stars.debit_stars(db, user, "fabric")
    except ForbiddenError:
        # Tile already generated; rare race — keep the fabric, skip wallet debit.
        logger.warning("fabric_ai stars debit skipped after success user_id=%s", user.id)
    return row
