"""FASHN Try-On Max experimental adapter (owner-only lane).

Separate from v1.6. Uses documented Max request fields only:
  model_name=tryon-max
  inputs: product_image, model_image, prompt?, resolution?, generation_mode?,
          seed?, num_images?, output_format?, return_base64?

Never auto-selected after an OpenAI or v1.6 refusal.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import time
from typing import Any, Literal

import httpx
from PIL import Image

from app.core.config import get_settings
from app.services.fashn_garment_prep import GarmentPrepResult, prepare_garment_reference
from app.services.fashn_try_on_provider import (
    _safe_fashn_error,
    _to_data_uri_png,
    _ensure_rgb_jpegish_png,
    estimate_fashn_cost_cents,
    fashn_configured,
)
from app.services.personal_croquis_provider import (
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
)

logger = logging.getLogger(__name__)

FASHN_MAX_PROVIDER_ID = "fashn_tryon_max"
FASHN_MAX_MODEL_NAME = "tryon-max"
FASHN_MAX_PROMPT_VERSION = "fashn-tryon-max-exp-v1"
FASHN_MAX_CONSENT_VERSION = "try-on-fashn-oneclick-v1"  # same Accept gate as v1.6

GenerationMode = Literal["fast", "balanced", "quality"]
ResolutionTier = Literal["1k", "2k", "4k"]

# Official Max credit table (docs.fashn.ai/api-reference/tryon-max).
MAX_CREDIT_TABLE: dict[str, dict[str, int]] = {
    "fast": {"1k": 1, "2k": 2, "4k": 3},
    "balanced": {"1k": 2, "2k": 3, "4k": 4},
    "quality": {"1k": 3, "2k": 4, "4k": 5},
}

DEFAULT_MAX_PROMPT = (
    "Fit the exact garment from the provided approved product image onto the person. "
    "Preserve the garment's silhouette, neckline depth, leg openings, color, and overall "
    "construction. Do not turn it into a skirt, dress, or different garment. Preserve the "
    "person's identity, pose, proportions, and background."
)


def fashn_max_prompt_hash(prompt: str) -> str:
    return hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()


def fashn_max_credits_per_image(
    *,
    generation_mode: GenerationMode = "balanced",
    resolution: ResolutionTier = "1k",
) -> int:
    mode = generation_mode if generation_mode in MAX_CREDIT_TABLE else "balanced"
    res = resolution if resolution in MAX_CREDIT_TABLE[mode] else "1k"
    return int(MAX_CREDIT_TABLE[mode][res])


def estimate_fashn_max_cost_cents(
    *,
    generation_mode: GenerationMode = "balanced",
    resolution: ResolutionTier = "1k",
    fashn_calls: int = 1,
    num_images: int = 1,
) -> int:
    """Soft USD¢ estimate = (credits per image × calls × num_images) × ¢/credit."""
    credits = fashn_max_credits_per_image(
        generation_mode=generation_mode, resolution=resolution
    ) * max(1, int(fashn_calls)) * max(1, int(num_images))
    return estimate_fashn_cost_cents(fashn_calls=credits)


def normalize_max_generation_mode(raw: str | None) -> GenerationMode:
    name = (raw or "balanced").strip().lower()
    if name in {"fast", "balanced", "quality"}:
        return name  # type: ignore[return-value]
    return "balanced"


def normalize_max_resolution(raw: str | None) -> ResolutionTier:
    name = (raw or "1k").strip().lower()
    if name in {"1k", "2k", "4k"}:
        return name  # type: ignore[return-value]
    return "1k"


def normalize_max_prompt(raw: str | None) -> str:
    text = " ".join((raw or "").split()).strip()
    if not text:
        return DEFAULT_MAX_PROMPT
    return text[:1000]


def normalize_max_seed(raw: int | None) -> int:
    if raw is None:
        return 42
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 42
    return max(0, min(value, 2**32 - 1))


def fashn_max_configured() -> bool:
    settings = get_settings()
    return (
        fashn_configured()
        and bool(getattr(settings, "fashn_try_on_max_enabled", False))
    )


def fashn_max_live_armed() -> bool:
    settings = get_settings()
    return fashn_max_configured() and bool(
        getattr(settings, "fashn_try_on_max_live_http", False)
    )


def _normalize_max_allowlist() -> set[str]:
    settings = get_settings()
    raw = (getattr(settings, "fashn_try_on_max_owner_allowlist", None) or "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def user_on_fashn_max_allowlist(user: Any) -> bool:
    """Server-enforced owner gate. Empty allowlist = nobody."""
    allow = _normalize_max_allowlist()
    if not allow:
        return False
    email = str(getattr(user, "email", "") or "").strip().lower()
    username = str(getattr(user, "username", "") or "").strip().lower()
    uid = str(getattr(user, "id", "") or "").strip().lower()
    return bool({email, username, uid} & allow)


def build_tryon_max_run_payload(
    *,
    model_image: str,
    product_image: str,
    prompt: str,
    generation_mode: GenerationMode,
    resolution: ResolutionTier,
    seed: int,
    num_images: int = 1,
) -> dict[str, Any]:
    """Exact Max /v1/run body — documented field names only."""
    return {
        "model_name": FASHN_MAX_MODEL_NAME,
        "inputs": {
            "model_image": model_image,
            "product_image": product_image,
            "prompt": prompt,
            "resolution": resolution,
            "generation_mode": generation_mode,
            "seed": seed,
            "num_images": max(1, min(4, int(num_images))),
            "output_format": "png",
            "return_base64": True,
        },
    }


class FashnTryOnMaxAdapter:
    """POST /v1/run model_name=tryon-max + status poll. return_base64=true."""

    incomplete = False

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.my_croquis_ai_enabled:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false")
        if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_SPEND_CEILING_USD is 0 (fail closed)")
        if not settings.fashn_try_on_enabled:
            raise ProviderNotAvailableError("FASHN_TRY_ON_ENABLED is false")
        if not bool(getattr(settings, "fashn_try_on_max_enabled", False)):
            raise ProviderNotAvailableError("FASHN_TRY_ON_MAX_ENABLED is false")
        if not (settings.fashn_api_key or "").strip():
            raise ProviderNotAvailableError("FASHN_API_KEY missing")

    def prepare(self, garment_png: bytes) -> GarmentPrepResult:
        return prepare_garment_reference(garment_png)

    def generate(
        self,
        *,
        photo_png: bytes,
        garment_png: bytes,
        design_hints: list[str] | None = None,
        prep: GarmentPrepResult | None = None,
        generation_mode: GenerationMode = "balanced",
        resolution: ResolutionTier = "1k",
        prompt: str | None = None,
        seed: int = 42,
        num_images: int = 1,
    ) -> tuple[bytes, dict[str, Any]]:
        _ = design_hints
        settings = get_settings()
        if not bool(getattr(settings, "fashn_try_on_max_live_http", False)):
            raise ProviderNotAvailableError(
                "FASHN_TRY_ON_MAX_LIVE_HTTP is false — Max experiment not armed"
            )
        if not settings.fashn_try_on_live_http:
            raise ProviderNotAvailableError(
                "FASHN_TRY_ON_LIVE_HTTP is false — live FASHN try-on not armed"
            )
        api_key = (settings.fashn_api_key or "").strip()
        if not api_key:
            raise ProviderNotAvailableError("FASHN_API_KEY missing")

        mode = normalize_max_generation_mode(generation_mode)
        res = normalize_max_resolution(resolution)
        prompt_text = normalize_max_prompt(prompt)
        seed_value = normalize_max_seed(seed)
        images_n = max(1, min(4, int(num_images or 1)))

        prepared = prep or prepare_garment_reference(garment_png)
        model_bytes = _ensure_rgb_jpegish_png(photo_png)
        prediction_ids: list[str] = []
        credits_used = 0

        timeout = float(settings.fashn_poll_timeout_seconds or 120)
        interval = float(settings.fashn_poll_interval_seconds or 2)
        base = (settings.fashn_api_base_url or "https://api.fashn.ai").rstrip("/")

        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                current_model = model_bytes
                final_png: bytes | None = None
                for piece in prepared.pieces:
                    pred_id = self._run(
                        client,
                        base=base,
                        api_key=api_key,
                        model_image=_to_data_uri_png(current_model),
                        product_image=_to_data_uri_png(piece.png_bytes),
                        prompt=prompt_text,
                        generation_mode=mode,
                        resolution=res,
                        seed=seed_value,
                        num_images=images_n,
                    )
                    prediction_ids.append(pred_id)
                    status_body, used = self._poll(
                        client,
                        base=base,
                        api_key=api_key,
                        prediction_id=pred_id,
                        timeout=timeout,
                        interval=interval,
                    )
                    credits_used += used
                    out = status_body.get("output")
                    if not isinstance(out, list) or not out:
                        raise ProviderNotAvailableError("FASHN Max completed with empty output")
                    final_png = self._decode_output(out[0])
                    current_model = final_png
        except ProviderNotAvailableError:
            raise
        except ProviderOutcomeUnknownError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderOutcomeUnknownError(
                f"FASHN Max HTTP timeout after dispatch: {type(exc).__name__}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderOutcomeUnknownError(
                f"FASHN Max HTTP error after dispatch: {type(exc).__name__}"
            ) from exc

        if not final_png:
            raise ProviderNotAvailableError("FASHN Max produced no image")

        expected_credits = fashn_max_credits_per_image(
            generation_mode=mode, resolution=res
        ) * prepared.fashn_calls * images_n
        settled_credits = credits_used or expected_credits
        meta: dict[str, Any] = {
            "prompt_version": FASHN_MAX_PROMPT_VERSION,
            "provider": FASHN_MAX_PROVIDER_ID,
            "model": FASHN_MAX_MODEL_NAME,
            "layout": prepared.layout,
            "fashn_calls": prepared.fashn_calls,
            "prediction_ids": prediction_ids,
            "credits_used": settled_credits,
            "actual_cost_cents": estimate_fashn_cost_cents(fashn_calls=settled_credits),
            "generation_mode": mode,
            "resolution": res,
            "seed": seed_value,
            "num_images": images_n,
            "prompt_text": prompt_text,
            "prompt_hash": fashn_max_prompt_hash(prompt_text),
            "experiment": True,
            "looks_eligible": False,
        }
        return final_png, meta

    def _run(
        self,
        client: httpx.Client,
        *,
        base: str,
        api_key: str,
        model_image: str,
        product_image: str,
        prompt: str,
        generation_mode: GenerationMode,
        resolution: ResolutionTier,
        seed: int,
        num_images: int,
    ) -> str:
        payload = build_tryon_max_run_payload(
            model_image=model_image,
            product_image=product_image,
            prompt=prompt,
            generation_mode=generation_mode,
            resolution=resolution,
            seed=seed,
            num_images=num_images,
        )
        try:
            resp = client.post(
                f"{base}/v1/run",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise ProviderOutcomeUnknownError(
                f"FASHN Max /v1/run timeout: {type(exc).__name__}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderOutcomeUnknownError(
                f"FASHN Max /v1/run transport error: {type(exc).__name__}"
            ) from exc

        if resp.status_code in (401, 403):
            raise ProviderNotAvailableError("FASHN API key rejected (unauthorized)")
        if resp.status_code == 429:
            err = ProviderNotAvailableError("FASHN rate limit / quota — try again later")
            err.safe_meta = {  # type: ignore[attr-defined]
                "error_code": "PROVIDER_REJECTED",
                "provider_code": "rate_limited",
                "http_status": 429,
            }
            raise err
        if 400 <= resp.status_code < 500:
            safe = _safe_fashn_error(resp)
            err = ProviderNotAvailableError(f"FASHN Max refused request: {safe['message']}")
            err.safe_meta = {  # type: ignore[attr-defined]
                "error_code": safe.get("error_code") or "PROVIDER_REJECTED",
                "provider_code": safe.get("provider_code"),
                "http_status": resp.status_code,
                "operator_summary": safe.get("message", "")[:400],
            }
            raise err
        if resp.status_code >= 500:
            raise ProviderOutcomeUnknownError(f"FASHN Max /v1/run HTTP {resp.status_code}")

        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderOutcomeUnknownError("FASHN Max /v1/run returned non-JSON") from exc
        pred_id = body.get("id") if isinstance(body, dict) else None
        if not isinstance(pred_id, str) or not pred_id.strip():
            raise ProviderNotAvailableError("FASHN Max /v1/run missing prediction id")
        return pred_id.strip()

    def _poll(
        self,
        client: httpx.Client,
        *,
        base: str,
        api_key: str,
        prediction_id: str,
        timeout: float,
        interval: float,
    ) -> tuple[dict[str, Any], int]:
        deadline = time.monotonic() + max(5.0, timeout)
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            try:
                resp = client.get(
                    f"{base}/v1/status/{prediction_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            except httpx.TimeoutException as exc:
                raise ProviderOutcomeUnknownError(
                    f"FASHN Max status timeout for {prediction_id[:16]}"
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderOutcomeUnknownError(
                    f"FASHN Max status transport error: {type(exc).__name__}"
                ) from exc

            if resp.status_code >= 500:
                raise ProviderOutcomeUnknownError(f"FASHN Max status HTTP {resp.status_code}")
            if 400 <= resp.status_code < 500:
                safe = _safe_fashn_error(resp)
                err = ProviderNotAvailableError(f"FASHN Max status refused: {safe['message']}")
                err.safe_meta = {  # type: ignore[attr-defined]
                    "error_code": "PROVIDER_REJECTED",
                    "http_status": resp.status_code,
                    "request_id": prediction_id,
                    "operator_summary": safe.get("message", "")[:400],
                }
                raise err

            try:
                last = resp.json()
            except Exception as exc:  # noqa: BLE001
                raise ProviderOutcomeUnknownError("FASHN Max status non-JSON") from exc
            if not isinstance(last, dict):
                raise ProviderOutcomeUnknownError("FASHN Max status malformed")

            status = str(last.get("status") or "")
            if status == "completed":
                used = 0
                hdr = resp.headers.get("x-fashn-credits-used")
                if hdr:
                    try:
                        used = max(0, int(float(hdr)))
                    except ValueError:
                        used = 0
                return last, used or 0
            if status == "failed":
                err_obj = last.get("error") if isinstance(last.get("error"), dict) else {}
                name = str(err_obj.get("name") or "FashnError")
                msg = str(err_obj.get("message") or "prediction failed")[:240]
                error_code = (
                    "PROVIDER_MODERATION_BLOCKED"
                    if "moderat" in name.lower() or "moderat" in msg.lower()
                    else "PROVIDER_REJECTED"
                )
                err = ProviderNotAvailableError(f"FASHN Max prediction failed: {name}: {msg}")
                err.safe_meta = {  # type: ignore[attr-defined]
                    "error_code": error_code,
                    "provider_code": name,
                    "request_id": prediction_id,
                    "operator_summary": f"{name}: {msg}"[:400],
                }
                raise err
            time.sleep(max(0.5, interval))

        raise ProviderOutcomeUnknownError(
            f"FASHN Max prediction timed out while polling {prediction_id[:16]}"
        )

    def _decode_output(self, item: Any) -> bytes:
        if not isinstance(item, str) or not item:
            raise ProviderNotAvailableError("FASHN Max output entry invalid")
        raw = item.strip()
        if raw.startswith("data:"):
            try:
                _, b64 = raw.split(",", 1)
            except ValueError as exc:
                raise ProviderNotAvailableError("FASHN Max base64 data URI malformed") from exc
            try:
                blob = base64.b64decode(b64, validate=False)
            except Exception as exc:  # noqa: BLE001
                raise ProviderNotAvailableError("FASHN Max base64 decode failed") from exc
        elif raw.startswith("http://") or raw.startswith("https://"):
            raise ProviderNotAvailableError(
                "FASHN Max returned a CDN URL despite return_base64=true — refusing external fetch"
            )
        else:
            try:
                blob = base64.b64decode(raw, validate=False)
            except Exception as exc:  # noqa: BLE001
                raise ProviderNotAvailableError("FASHN Max output is not decodable base64") from exc
        if len(blob) < 32:
            raise ProviderNotAvailableError("FASHN Max output image empty")
        try:
            with Image.open(io.BytesIO(blob)) as img:
                img.load()
                out = io.BytesIO()
                img.convert("RGB").save(out, format="PNG")
                return out.getvalue()
        except Exception as exc:  # noqa: BLE001
            raise ProviderNotAvailableError("FASHN Max output is not a valid image") from exc
