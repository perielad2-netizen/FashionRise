"""FASHN Virtual Try-On v1.6 adapter for FashionRise Try On Person.

Separate from the OpenAI images.edit path. Explicitly selected by the user —
never auto-switched after an OpenAI refusal.

Contract matches OpenAITryOnImagesEditAdapter.generate(...).
"""

from __future__ import annotations

import base64
import io
import logging
import time
from typing import Any

import httpx
from PIL import Image

from app.core.config import get_settings
from app.services.fashn_garment_prep import GarmentPrepResult, prepare_garment_reference
from app.services.personal_croquis_provider import (
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
)

logger = logging.getLogger(__name__)

FASHN_PROVIDER_ID = "fashn_tryon_v1_6"
FASHN_MODEL_NAME = "tryon-v1.6"
FASHN_CONSENT_VERSION = "try-on-fashn-preview-v1"
FASHN_PROMPT_VERSION = "fashn-tryon-v1.6"

FASHN_NOTICE_TEXT = (
    "FASHN Try On sends your original Create My Croquis photo and a prepared "
    "flat-lay of this garment sketch to FASHN AI (Virtual Try-On v1.6) to create "
    "a private photorealistic preview. Ordinary swimwear is supported with "
    "moderation kept on (permissive). Two-piece designs use two provider credits "
    "(top then bottom). This is a concept preview — not a fit or measurement "
    "guarantee. Your original photo and sketch stay private and are not overwritten. "
    "Refused attempts are not charged by FashionRise; FASHN only bills successful outputs."
)


def fashn_notice_text_hash() -> str:
    import hashlib

    return hashlib.sha256(FASHN_NOTICE_TEXT.encode("utf-8")).hexdigest()


def fashn_configured() -> bool:
    settings = get_settings()
    return bool((settings.fashn_api_key or "").strip()) and bool(settings.fashn_try_on_enabled)


def fashn_live_armed() -> bool:
    settings = get_settings()
    return fashn_configured() and bool(settings.fashn_try_on_live_http)


def estimate_fashn_cost_cents(*, fashn_calls: int = 1) -> int:
    settings = get_settings()
    per = max(1, int(settings.fashn_try_on_estimate_cents or 8))
    return per * max(1, int(fashn_calls))


def _to_data_uri_png(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _ensure_rgb_jpegish_png(photo_png: bytes) -> bytes:
    """Normalize person photo to opaque PNG (FASHN accepts PNG/JPEG data URIs)."""
    with Image.open(io.BytesIO(photo_png)) as img:
        img.load()
        rgb = img.convert("RGB")
        out = io.BytesIO()
        rgb.save(out, format="PNG")
        return out.getvalue()


class FashnTryOnV16Adapter:
    """POST /v1/run model_name=tryon-v1.6 + status poll. return_base64=true."""

    incomplete = False

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.my_croquis_ai_enabled:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false")
        if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_SPEND_CEILING_USD is 0 (fail closed)")
        if not settings.fashn_try_on_enabled:
            raise ProviderNotAvailableError("FASHN_TRY_ON_ENABLED is false")
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
    ) -> tuple[bytes, dict[str, Any]]:
        _ = design_hints  # FASHN v1.6 has no prompt field; hints are inspection-only.
        settings = get_settings()
        if not settings.fashn_try_on_live_http:
            raise ProviderNotAvailableError(
                "FASHN_TRY_ON_LIVE_HTTP is false — live FASHN try-on not armed"
            )
        api_key = (settings.fashn_api_key or "").strip()
        if not api_key:
            raise ProviderNotAvailableError("FASHN_API_KEY missing")

        prepared = prep or prepare_garment_reference(garment_png)
        model_bytes = _ensure_rgb_jpegish_png(photo_png)
        prediction_ids: list[str] = []
        credits_used = 0

        timeout = float(settings.fashn_poll_timeout_seconds or 120)
        interval = float(settings.fashn_poll_interval_seconds or 2)
        base = (settings.fashn_api_base_url or "https://api.fashn.ai").rstrip("/")

        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                current_model = model_bytes
                final_png: bytes | None = None
                for piece in prepared.pieces:
                    pred_id = self._run(
                        client,
                        base=base,
                        api_key=api_key,
                        model_image=_to_data_uri_png(current_model),
                        garment_image=_to_data_uri_png(piece.png_bytes),
                        category=piece.category,
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
                        raise ProviderNotAvailableError("FASHN completed with empty output")
                    final_png = self._decode_output(out[0])
                    current_model = final_png  # chain bottoms onto tops result
        except ProviderNotAvailableError:
            raise
        except ProviderOutcomeUnknownError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderOutcomeUnknownError(
                f"FASHN HTTP timeout after dispatch: {type(exc).__name__}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderOutcomeUnknownError(
                f"FASHN HTTP error after dispatch: {type(exc).__name__}"
            ) from exc

        if not final_png:
            raise ProviderNotAvailableError("FASHN produced no image")

        meta: dict[str, Any] = {
            "prompt_version": FASHN_PROMPT_VERSION,
            "provider": FASHN_PROVIDER_ID,
            "model": FASHN_MODEL_NAME,
            "layout": prepared.layout,
            "fashn_calls": prepared.fashn_calls,
            "prediction_ids": prediction_ids,
            "credits_used": credits_used or prepared.fashn_calls,
            "actual_cost_cents": estimate_fashn_cost_cents(
                fashn_calls=credits_used or prepared.fashn_calls
            ),
        }
        return final_png, meta

    def _run(
        self,
        client: httpx.Client,
        *,
        base: str,
        api_key: str,
        model_image: str,
        garment_image: str,
        category: str,
    ) -> str:
        payload = {
            "model_name": FASHN_MODEL_NAME,
            "inputs": {
                "model_image": model_image,
                "garment_image": garment_image,
                "category": category,
                "garment_photo_type": "flat-lay",
                "moderation_level": "permissive",
                "segmentation_free": True,
                "mode": "balanced",
                "num_samples": 1,
                "output_format": "png",
                "return_base64": True,
            },
        }
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
                f"FASHN /v1/run timeout: {type(exc).__name__}"
            ) from exc
        except httpx.HTTPError as exc:
            # Connection failures before a clear HTTP response — treat as unknown if
            # we cannot prove the provider never started work.
            raise ProviderOutcomeUnknownError(
                f"FASHN /v1/run transport error: {type(exc).__name__}"
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
            err = ProviderNotAvailableError(f"FASHN refused request: {safe['message']}")
            err.safe_meta = {  # type: ignore[attr-defined]
                "error_code": safe.get("error_code") or "PROVIDER_REJECTED",
                "provider_code": safe.get("provider_code"),
                "http_status": resp.status_code,
                "operator_summary": safe.get("message", "")[:400],
            }
            raise err
        if resp.status_code >= 500:
            raise ProviderOutcomeUnknownError(f"FASHN /v1/run HTTP {resp.status_code}")

        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderOutcomeUnknownError("FASHN /v1/run returned non-JSON") from exc
        pred_id = body.get("id") if isinstance(body, dict) else None
        if not isinstance(pred_id, str) or not pred_id.strip():
            raise ProviderNotAvailableError("FASHN /v1/run missing prediction id")
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
                    f"FASHN status timeout for {prediction_id[:16]}"
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderOutcomeUnknownError(
                    f"FASHN status transport error: {type(exc).__name__}"
                ) from exc

            if resp.status_code >= 500:
                raise ProviderOutcomeUnknownError(f"FASHN status HTTP {resp.status_code}")
            if 400 <= resp.status_code < 500:
                safe = _safe_fashn_error(resp)
                err = ProviderNotAvailableError(f"FASHN status refused: {safe['message']}")
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
                raise ProviderOutcomeUnknownError("FASHN status non-JSON") from exc
            if not isinstance(last, dict):
                raise ProviderOutcomeUnknownError("FASHN status malformed")

            status = str(last.get("status") or "")
            if status == "completed":
                used = 0
                hdr = resp.headers.get("x-fashn-credits-used")
                if hdr:
                    try:
                        used = max(0, int(float(hdr)))
                    except ValueError:
                        used = 0
                return last, used or 1
            if status == "failed":
                err_obj = last.get("error") if isinstance(last.get("error"), dict) else {}
                name = str(err_obj.get("name") or "FashnError")
                msg = str(err_obj.get("message") or "prediction failed")[:240]
                error_code = (
                    "PROVIDER_MODERATION_BLOCKED"
                    if "moderat" in name.lower() or "moderat" in msg.lower()
                    else "PROVIDER_REJECTED"
                )
                err = ProviderNotAvailableError(f"FASHN prediction failed: {name}: {msg}")
                err.safe_meta = {  # type: ignore[attr-defined]
                    "error_code": error_code,
                    "provider_code": name,
                    "request_id": prediction_id,
                    "operator_summary": f"{name}: {msg}"[:400],
                }
                raise err
            # starting | in_queue | processing
            time.sleep(max(0.5, interval))

        raise ProviderOutcomeUnknownError(
            f"FASHN prediction timed out while polling {prediction_id[:16]}"
        )

    def _decode_output(self, item: Any) -> bytes:
        if not isinstance(item, str) or not item:
            raise ProviderNotAvailableError("FASHN output entry invalid")
        raw = item.strip()
        if raw.startswith("data:"):
            try:
                _, b64 = raw.split(",", 1)
            except ValueError as exc:
                raise ProviderNotAvailableError("FASHN base64 data URI malformed") from exc
            try:
                blob = base64.b64decode(b64, validate=False)
            except Exception as exc:  # noqa: BLE001
                raise ProviderNotAvailableError("FASHN base64 decode failed") from exc
        elif raw.startswith("http://") or raw.startswith("https://"):
            # return_base64=true should avoid CDN URLs; fail closed rather than fetch.
            raise ProviderNotAvailableError(
                "FASHN returned a CDN URL despite return_base64=true — refusing external fetch"
            )
        else:
            try:
                blob = base64.b64decode(raw, validate=False)
            except Exception as exc:  # noqa: BLE001
                raise ProviderNotAvailableError("FASHN output is not decodable base64") from exc
        if len(blob) < 32:
            raise ProviderNotAvailableError("FASHN output image empty")
        # Validate image
        try:
            with Image.open(io.BytesIO(blob)) as img:
                img.load()
                out = io.BytesIO()
                img.convert("RGB").save(out, format="PNG")
                return out.getvalue()
        except Exception as exc:  # noqa: BLE001
            raise ProviderNotAvailableError("FASHN output is not a valid image") from exc


def _safe_fashn_error(resp: httpx.Response) -> dict[str, str]:
    message = f"HTTP {resp.status_code}"
    provider_code = ""
    error_code = "PROVIDER_REJECTED"
    try:
        body = resp.json()
        if isinstance(body, dict):
            provider_code = str(body.get("error") or body.get("name") or "")[:80]
            message = str(body.get("message") or body.get("error") or message)[:240]
            low = message.lower()
            if "moderat" in low or "nsfw" in low:
                error_code = "PROVIDER_MODERATION_BLOCKED"
    except Exception:  # noqa: BLE001
        message = (resp.text or message)[:240]
    return {"message": message, "provider_code": provider_code, "error_code": error_code}
