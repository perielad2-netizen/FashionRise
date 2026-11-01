"""Create My Croquis — provider adapter boundary (Stage C + live images.edit).

Default path is fail-closed. Live OpenAI ``images.edit`` is never invoked unless
``MY_CROQUIS_AI_ENABLED`` is on, operator spend ceiling > 0, ``MY_CROQUIS_AI_LIVE_HTTP``
is explicitly true, an API key is present, and the offline tripwire is disarmed.

Tests inject ``MockCroquisProvider`` or a fake OpenAI client override.
Importing this module must not open network connections.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from PIL import Image, ImageDraw, ImageOps

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GEOMETRY_PROFILE_V1 = "fit_contain_768x1024_v1"
# v2: fashion-underlay wording (historical).
# v3: explicitly preserves clothed garment silhouettes — never asks to undress
# or "not add garments" in a way that implies clothing removal from a photo.
PROMPT_VERSION_V1 = "croquis-lineart-v1"  # historical
PROMPT_VERSION_V2 = "croquis-lineart-v2"  # historical
PROMPT_VERSION_V3 = "croquis-lineart-v3"
PROMPT_VERSION_CURRENT = PROMPT_VERSION_V3
DESIGN_W = 768
DESIGN_H = 1024

# Provider request size must be an explicitly allowlisted Sunburst size.
# Output is always post-normalized to the design plane (768×1024 fit-contain).
CROQUIS_PROVIDER_SIZE = "1024x1536"
CROQUIS_PROVIDER_QUALITY_DEFAULT = "medium"

# Versioned croquis prompt — clothed fashion-illustration underlay for garment design.
CROQUIS_LINEART_PROMPT_V3 = (
    "Create a fashion-design croquis underlay as clean black line art on a transparent "
    "background for garment sketching. From the attached fully clothed fashion photograph, "
    "draw a clothed fashion-illustration figure that preserves the model's pose, "
    "proportions, and visible garment silhouettes (for example tops, bottoms, and shoes). "
    "Keep the figure fully clothed — do not undress, remove clothing, or invent nude "
    "anatomy. Do not add logos, text, color fills, shading, or photorealistic detail. "
    "Keep the full figure visible (no crop)."
)
# Back-compat aliases — current prompt is V3.
CROQUIS_LINEART_PROMPT_V2 = CROQUIS_LINEART_PROMPT_V3
CROQUIS_LINEART_PROMPT_V1 = CROQUIS_LINEART_PROMPT_V3
CROQUIS_LINEART_PROMPT = CROQUIS_LINEART_PROMPT_V3

# Official gpt-image-2.5-sunburst token rates (USD per 1M tokens) — design §9.1.
_RATE_TEXT_IN = 5.0
_RATE_IMAGE_IN = 8.0
_RATE_IMAGE_OUT = 30.0


# User-visible copy for definitive provider rejections (never bypass safety).
_MODERATION_USER_MESSAGE = (
    "OpenAI's safety system rejected this photo for croquis generation "
    "(moderation_blocked). FashionRise cannot override that provider decision. "
    "Try a different fully clothed fashion pose photo with clear lighting and "
    "no sensitive content. This attempt was not charged."
)
_GENERIC_REJECT_USER_MESSAGE = (
    "The image provider rejected this generate request and produced no croquis. "
    "You may try a different photo. This attempt was not charged."
)


def provider_rejection_code_from_text(detail: str | None) -> str | None:
    """Extract structured provider rejection code from error_detail / exception text."""
    if not detail:
        return None
    import re

    m = re.search(r"\bcode=([A-Za-z0-9_\-]+)", detail)
    if m:
        return m.group(1)[:64]
    if "moderation_blocked" in detail:
        return "moderation_blocked"
    return None


def user_safe_provider_rejection_message(*, code: str | None = None, detail: str | None = None) -> str:
    """Owner-facing explanation for definite provider rejections (no secrets/bytes)."""
    resolved = (code or provider_rejection_code_from_text(detail) or "").strip().lower()
    if resolved == "moderation_blocked":
        return _MODERATION_USER_MESSAGE
    return _GENERIC_REJECT_USER_MESSAGE


@dataclass(frozen=True)
class CroquisProviderResult:
    png_bytes: bytes
    provider_job_id: str
    # Authoritative usage when the provider reports it; otherwise 0 and estimate is used.
    actual_cost_cents: int
    estimated_cost_cents: int
    geometry_profile: str = GEOMETRY_PROFILE_V1
    prompt_version: str = PROMPT_VERSION_CURRENT
    usage_source: str = "estimate"  # "provider_usage" | "estimate"


class CroquisProvider(Protocol):
    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        """Transform a private source photo into fit-contain line-art PNG bytes."""


class ProviderNotAvailableError(RuntimeError):
    """Definite no-billable-result refusal — safe to release reservation at $0.

    Covers pre-submit gate failures and definitive provider HTTP 4xx rejections
    (e.g. ``BadRequestError``) where OpenAI returned a completed error response
    with no generated image.
    """


class ProviderOutcomeUnknownError(RuntimeError):
    """Request may have been sent/billed; outcome unknown — reconciliation required.

    Raised for ambiguous post-submit failures: SDK timeout, connection error,
    HTTP 5xx, missing/malformed result bytes after a 2xx response, etc.
    Definitive HTTP 4xx rejections are NOT outcome-unknown — use
    ``ProviderNotAvailableError`` instead.
    """


class ProviderNetworkForbiddenError(RuntimeError):
    """Raised by the offline tripwire if a real network call is attempted."""


# ---------------------------------------------------------------------------
# Offline network tripwire (tests only)
# ---------------------------------------------------------------------------

_NETWORK_TRIPWIRE_ARMED = False
_NETWORK_TRIPWIRE_HITS = 0


def arm_provider_network_tripwire() -> None:
    """Fail any accidental real HTTP from croquis provider code during tests."""
    global _NETWORK_TRIPWIRE_ARMED, _NETWORK_TRIPWIRE_HITS
    _NETWORK_TRIPWIRE_ARMED = True
    _NETWORK_TRIPWIRE_HITS = 0


def disarm_provider_network_tripwire() -> None:
    global _NETWORK_TRIPWIRE_ARMED
    _NETWORK_TRIPWIRE_ARMED = False


def provider_network_tripwire_hits() -> int:
    return _NETWORK_TRIPWIRE_HITS


def assert_no_provider_network() -> None:
    if _NETWORK_TRIPWIRE_ARMED:
        global _NETWORK_TRIPWIRE_HITS
        _NETWORK_TRIPWIRE_HITS += 1
        raise ProviderNetworkForbiddenError(
            "Create My Croquis tripwire: real provider network call forbidden offline"
        )


def fit_contain_normalize_png(
    raw_png: bytes,
    *,
    box_w: int = DESIGN_W,
    box_h: int = DESIGN_H,
) -> bytes:
    """Fit-contain onto the design plane with transparent padding; strip EXIF."""
    with Image.open(io.BytesIO(raw_png)) as opened:
        oriented = ImageOps.exif_transpose(opened)
        rgba = oriented.convert("RGBA")
        sw, sh = rgba.size
        scale = min(box_w / max(sw, 1), box_h / max(sh, 1))
        dw, dh = max(1, round(sw * scale)), max(1, round(sh * scale))
        resized = rgba.resize((dw, dh), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        canvas.paste(resized, ((box_w - dw) // 2, (box_h - dh) // 2), resized)
        out = io.BytesIO()
        canvas.save(out, format="PNG", optimize=True)
        return out.getvalue()


class FailClosedCroquisProvider:
    """Never performs network I/O. Used as the default production-safe stub."""

    def __init__(self, reason: str = "Create My Croquis AI provider is not available.") -> None:
        self.reason = reason

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        _ = source_png
        raise ProviderNotAvailableError(self.reason)


class MockCroquisProvider:
    """Deterministic offline provider for unit/integration tests only."""

    def __init__(
        self,
        *,
        cost_cents: int = 1,
        job_id: str = "mock-job",
        estimated_cost_cents: int | None = None,
    ) -> None:
        self.cost_cents = cost_cents
        self.estimated_cost_cents = (
            estimated_cost_cents if estimated_cost_cents is not None else cost_cents
        )
        self.job_id = job_id
        self.calls = 0

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        # Offline mock — never touches the network tripwire (tripwire guards live HTTP only).
        self.calls += 1
        with Image.open(io.BytesIO(source_png)) as opened:
            rgba = opened.convert("RGBA")
            sw, sh = rgba.size
        scale = min(DESIGN_W / max(sw, 1), DESIGN_H / max(sh, 1))
        dw, dh = max(1, int(sw * scale)), max(1, int(sh * scale))
        canvas = Image.new("RGBA", (DESIGN_W, DESIGN_H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        x0 = (DESIGN_W - dw) // 2
        y0 = (DESIGN_H - dh) // 2
        draw.rectangle([x0, y0, x0 + dw - 1, y0 + dh - 1], outline=(20, 20, 20, 255), width=2)
        digest = hashlib.sha256(source_png).hexdigest()[:8]
        draw.text((x0 + 8, y0 + 8), digest, fill=(20, 20, 20, 255))
        out = io.BytesIO()
        canvas.save(out, format="PNG")
        normalized = fit_contain_normalize_png(out.getvalue())
        return CroquisProviderResult(
            png_bytes=normalized,
            provider_job_id=f"{self.job_id}-{self.calls}",
            actual_cost_cents=self.cost_cents,
            estimated_cost_cents=self.estimated_cost_cents,
            usage_source="provider_usage",
        )


class UnknownOutcomeCroquisProvider:
    """Test double: outcome unknown after submission would have started."""

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        _ = source_png
        raise ProviderOutcomeUnknownError("simulated provider outcome unknown after send")


class CrashBeforeSubmitCroquisProvider:
    """Test double: fails before any provider submission."""

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        _ = source_png
        raise ProviderNotAvailableError("crash before provider submission")


def _croquis_image_quality(settings: Any) -> str:
    raw = (getattr(settings, "my_croquis_ai_image_quality", None) or "").strip().lower()
    if raw:
        return raw
    # Prefer croquis-safe medium for first live validations; Magic default remains high.
    return CROQUIS_PROVIDER_QUALITY_DEFAULT


def _croquis_image_size(settings: Any) -> str:
    raw = (getattr(settings, "my_croquis_ai_image_size", None) or "").strip()
    return raw or CROQUIS_PROVIDER_SIZE


def _croquis_image_model(settings: Any) -> str:
    return (settings.openai_image_model or "gpt-image-2.5-sunburst").strip()


def cost_cents_from_images_usage(usage: Any, *, fallback_cents: int) -> tuple[int, str]:
    """Derive cents from Images API usage when token details are present.

    Returns (cents, usage_source) where usage_source is ``provider_usage`` or ``estimate``.
    """
    if usage is None:
        return max(1, int(fallback_cents)), "estimate"

    text_in = 0
    image_in = 0
    image_out = 0

    details = getattr(usage, "input_tokens_details", None)
    if details is not None:
        text_in = int(getattr(details, "text_tokens", 0) or 0)
        image_in = int(getattr(details, "image_tokens", 0) or 0)
    elif isinstance(usage, dict):
        d = usage.get("input_tokens_details") or {}
        if isinstance(d, dict):
            text_in = int(d.get("text_tokens") or 0)
            image_in = int(d.get("image_tokens") or 0)

    out = getattr(usage, "output_tokens", None)
    if out is None and isinstance(usage, dict):
        out = usage.get("output_tokens")
    image_out = int(out or 0)

    if text_in <= 0 and image_in <= 0 and image_out <= 0:
        return max(1, int(fallback_cents)), "estimate"

    dollars = (
        (text_in / 1_000_000.0) * _RATE_TEXT_IN
        + (image_in / 1_000_000.0) * _RATE_IMAGE_IN
        + (image_out / 1_000_000.0) * _RATE_IMAGE_OUT
    )
    cents = max(1, round(dollars * 100.0))
    return cents, "provider_usage"


def _safe_request_id_from_exc(exc: BaseException) -> str | None:
    """Best-effort request id for logs — never log bodies/secrets."""
    for attr in ("request_id", "request"):
        raw = getattr(exc, attr, None)
        if isinstance(raw, str) and 8 <= len(raw.strip()) <= 128:
            return raw.strip()[:128]
        headers = getattr(raw, "headers", None) if raw is not None else None
        if headers is not None:
            try:
                rid = headers.get("x-request-id") or headers.get("X-Request-Id")
            except Exception:  # noqa: BLE001
                rid = None
            if isinstance(rid, str) and 8 <= len(rid.strip()) <= 128:
                return rid.strip()[:128]
    return None


def _api_status_code(exc: BaseException) -> int | None:
    raw = getattr(exc, "status_code", None)
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _is_presubmit_sdk_contract_error(exc: BaseException) -> bool:
    """True when the SDK rejected kwargs before any HTTP (definite no-spend).

    Example: OpenAI Python 1.109 ``Images.edit()`` has no top-level ``moderation``
    parameter — passing it raises TypeError with no request_id. That must not be
    classified as outcome-unknown / reconciliation_required.
    """
    if not isinstance(exc, TypeError):
        return False
    msg = str(exc).lower()
    return (
        "unexpected keyword argument" in msg
        or "got an unexpected keyword" in msg
        or "images.edit()" in msg
    )


def _is_definitive_images_edit_rejection(exc: BaseException) -> bool:
    """True when the provider completed an HTTP 4xx rejection (no image result).

    OpenAI ``images.edit`` 4xx responses (Bad Request, auth, permission, not found,
    unprocessable, rate limit) do not return generated image bytes. Treat as a
    definite no-billable-result for this attempt so spend can be released. Keep
    timeouts, connection drops, and HTTP 5xx as outcome-unknown.
    """
    if _is_presubmit_sdk_contract_error(exc):
        return True
    try:
        import openai
    except Exception:  # noqa: BLE001
        openai = None  # type: ignore[assignment]

    if openai is not None:
        # Prefer named 4xx subclasses when the SDK is available.
        named_4xx = tuple(
            cls
            for cls in (
                getattr(openai, "BadRequestError", None),
                getattr(openai, "AuthenticationError", None),
                getattr(openai, "PermissionDeniedError", None),
                getattr(openai, "NotFoundError", None),
                getattr(openai, "ConflictError", None),
                getattr(openai, "UnprocessableEntityError", None),
                getattr(openai, "RateLimitError", None),
            )
            if cls is not None
        )
        if named_4xx and isinstance(exc, named_4xx):
            return True
        api_status = getattr(openai, "APIStatusError", None)
        if api_status is not None and isinstance(exc, api_status):
            code = _api_status_code(exc)
            return code is not None and 400 <= code < 500

    code = _api_status_code(exc)
    return code is not None and 400 <= code < 500


def _api_error_code(exc: BaseException) -> str | None:
    """Best-effort OpenAI error code from SDK attrs or response/body JSON."""
    raw = getattr(exc, "code", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:64]
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(err, dict):
            code = err.get("code")
            if isinstance(code, str) and code.strip():
                return code.strip()[:64]
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            data = None
        if isinstance(data, dict):
            err = data.get("error") if isinstance(data.get("error"), dict) else data
            if isinstance(err, dict):
                code = err.get("code")
                if isinstance(code, str) and code.strip():
                    return code.strip()[:64]
    # Fall back to scanning the stringified exception.
    return provider_rejection_code_from_text(str(exc))


def _moderation_details_sanitized(exc: BaseException) -> dict[str, Any] | None:
    """Extract coarse moderation_stage + categories only (never raw body secrets)."""
    body = getattr(exc, "body", None)
    details: Any = None
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(err, dict):
            details = err.get("moderation_details")
    if not isinstance(details, dict):
        resp = getattr(exc, "response", None)
        if resp is not None:
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                data = None
            if isinstance(data, dict):
                err = data.get("error") if isinstance(data.get("error"), dict) else data
                if isinstance(err, dict):
                    details = err.get("moderation_details")
    if not isinstance(details, dict):
        return None
    out: dict[str, Any] = {}
    stage = details.get("moderation_stage")
    if isinstance(stage, str) and stage.strip().lower() in {"input", "output", "unknown"}:
        out["moderation_stage"] = stage.strip().lower()
    cats = details.get("categories")
    if isinstance(cats, list):
        cleaned = [
            c.strip().lower()[:48]
            for c in cats
            if isinstance(c, str) and c.strip() and len(c.strip()) <= 64
        ]
        if cleaned:
            out["categories"] = cleaned[:8]
    return out or None


def _safe_api_error_summary(exc: BaseException) -> str:
    """Short operator-safe summary — type, status, code, truncated message (no bytes)."""
    parts = [type(exc).__name__]
    status = _api_status_code(exc)
    if status is not None:
        parts.append(f"status={status}")
    code = _api_error_code(exc)
    if code:
        parts.append(f"code={code}")
    rid = _safe_request_id_from_exc(exc)
    if rid:
        parts.append(f"request_id={rid}")
    mod = _moderation_details_sanitized(exc)
    if mod:
        if "moderation_stage" in mod:
            parts.append(f"moderation_stage={mod['moderation_stage']}")
        cats = mod.get("categories")
        if isinstance(cats, list) and cats:
            parts.append("categories=" + ",".join(str(c) for c in cats))
    msg = str(exc).strip().replace("\n", " ")
    if msg:
        parts.append(msg[:180])
    return " ".join(parts)[:400]


def extract_edit_png_bytes(result: Any) -> bytes:
    """Pull PNG bytes from an images.edit response (b64 required).

    Called only after a completed API response — failures here are outcome-unknown
    (the request may already have been billed).
    """
    data = getattr(result, "data", None) or []
    if not data:
        raise ProviderOutcomeUnknownError("images.edit returned no data after submit")
    item = data[0]
    b64 = getattr(item, "b64_json", None)
    if b64 is None and isinstance(item, dict):
        b64 = item.get("b64_json")
    if b64:
        return base64.b64decode(b64)
    url = getattr(item, "url", None)
    if url is None and isinstance(item, dict):
        url = item.get("url")
    if url:
        # Croquis path refuses URL fetch — require b64 to avoid a second network hop.
        raise ProviderOutcomeUnknownError(
            "images.edit returned URL without b64_json after submit; "
            "croquis adapter requires b64_json (outcome unknown / may be billed)"
        )
    raise ProviderOutcomeUnknownError("images.edit item missing b64_json after submit")


class OpenAICroquisImagesEditAdapter:
    """Production images.edit adapter for Create My Croquis (gpt-image-2.5-sunburst).

    Request shape (fail-closed before HTTP when invalid):
      - model: configured ``OPENAI_IMAGE_MODEL`` (must be editable / non-retired)
      - one image input, ``n=1``
      - size: allowlisted portrait (default ``1024x1536``)
      - quality: FashionRise-allowed (default croquis ``medium``)
      - ``background=transparent``, ``output_format=png``
      - no ``input_fidelity`` for sunburst

    Response bytes are always fit-contain normalized to exactly 768×1024 RGBA.
    """

    incomplete = False

    def __init__(self) -> None:
        # Fail closed on construct if gates are off — no client creation / network.
        settings = get_settings()
        if not settings.my_croquis_ai_enabled:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false")
        if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_SPEND_CEILING_USD is 0 (fail closed)")

    def build_edit_kwargs(self, source_png: bytes) -> dict[str, Any]:
        """Assemble images.edit kwargs without performing HTTP.

        Croquis path refuses silent size/quality substitution: configured size and
        quality must be allowlisted and must survive ``build_image_edit_kwargs``
        unchanged.
        """
        from app.services.sketch_openai import (
            SketchCompletionError,
            assert_image_model_editable,
            build_image_edit_kwargs,
        )

        if not source_png:
            raise ProviderNotAvailableError("Empty source PNG for croquis edit")

        settings = get_settings()
        model = _croquis_image_model(settings)
        # Fail closed on retired/unknown before any paid HTTP.
        caps = assert_image_model_editable(model)
        size = _croquis_image_size(settings)
        quality = _croquis_image_quality(settings)
        if size not in caps.sizes:
            raise ProviderNotAvailableError(
                f"Croquis image size {size!r} not allowlisted for {model} "
                "(no silent size fallback)"
            )

        try:
            kwargs = build_image_edit_kwargs(
                model=model,
                prompt=CROQUIS_LINEART_PROMPT_V3,
                sketch=(source_png, "image/png"),
                size=size,
                quality=quality,
                fabric_swatch=None,
            )
        except SketchCompletionError as exc:
            raise ProviderNotAvailableError(str(exc)) from exc

        # Croquis-specific: transparent PNG background; single output already n=1.
        kwargs["background"] = "transparent"
        kwargs["output_format"] = "png"
        kwargs["n"] = 1
        # Official Images Edit API supports moderation=auto|low. OpenAI Python SDK
        # 1.109 Images.edit() has no top-level ``moderation`` kwarg — passing it
        # raises TypeError before HTTP. Send via extra_body so the wire request
        # still carries moderation=low without an SDK upgrade.
        # Provider safety enforcement remains — this is not a bypass.
        extra = dict(kwargs.get("extra_body") or {})
        extra["moderation"] = "low"
        kwargs["extra_body"] = extra
        # Never send a second image / fabric swatch on this path.
        if isinstance(kwargs.get("image"), list):
            raise ProviderNotAvailableError("Croquis edit must use exactly one image input")
        # Refuse silent substitution from the shared helper.
        if kwargs.get("size") != size:
            raise ProviderNotAvailableError(
                f"Croquis edit size substituted {size!r} → {kwargs.get('size')!r}; refusing"
            )
        if kwargs.get("quality") != quality:
            raise ProviderNotAvailableError(
                f"Croquis edit quality substituted {quality!r} → {kwargs.get('quality')!r}; "
                "refusing"
            )
        if "moderation" in kwargs:
            raise ProviderNotAvailableError(
                "Croquis edit must not pass top-level moderation= (SDK TypeError); "
                "use extra_body only"
            )
        return kwargs

    def preflight_report(self, source_png: bytes) -> dict[str, Any]:
        """Operator-facing preflight (no HTTP). Safe to log — no image bytes."""
        settings = get_settings()
        kwargs = self.build_edit_kwargs(source_png)
        estimate = max(1, int(settings.my_croquis_ai_estimate_cents or 0))
        max_exposure = int(settings.my_croquis_ai_max_exposure_cents or 0)
        extra = kwargs.get("extra_body") if isinstance(kwargs.get("extra_body"), dict) else {}
        return {
            "model": kwargs.get("model"),
            "size": kwargs.get("size"),
            "quality": kwargs.get("quality"),
            "background": kwargs.get("background"),
            "output_format": kwargs.get("output_format"),
            "moderation": (extra or {}).get("moderation"),
            "n": kwargs.get("n"),
            "prompt_version": PROMPT_VERSION_CURRENT,
            "geometry_profile": GEOMETRY_PROFILE_V1,
            "design_plane": f"{DESIGN_W}x{DESIGN_H}",
            "source_sha256": hashlib.sha256(source_png).hexdigest(),
            "source_bytes": len(source_png),
            "estimate_cents": estimate,
            "max_exposure_cents": max_exposure,
            "spend_ceiling_usd": float(settings.my_croquis_ai_spend_ceiling_usd or 0),
            "live_http_armed": bool(getattr(settings, "my_croquis_ai_live_http", False)),
            "ai_enabled": bool(settings.my_croquis_ai_enabled),
            "api_key_present": bool((settings.openai_api_key or "").strip()),
            "incomplete": bool(self.incomplete),
        }

    def assert_pre_submit_ready(self) -> None:
        """Definite pre-submit checks — must run BEFORE ``provider_called`` fence.

        When a test client override is installed, LIVE_HTTP/API key are not required
        (mocked HTTP). Otherwise LIVE_HTTP + API key must be armed. Also fail closed
        on retired/unknown image model before any spend marker.
        """
        from app.services.sketch_openai import assert_image_model_editable

        settings = get_settings()
        assert_image_model_editable(_croquis_image_model(settings))
        if _openai_client_override is not None:
            return
        if not bool(getattr(settings, "my_croquis_ai_live_http", False)):
            raise ProviderNotAvailableError(
                "MY_CROQUIS_AI_LIVE_HTTP is false — live images.edit not armed "
                "(offline mock / client override only)"
            )
        if not (settings.openai_api_key or "").strip():
            raise ProviderNotAvailableError("OPENAI_API_KEY missing for live croquis edit")

    def _live_openai_client(self) -> Any:
        """Create a real OpenAI client after LIVE_HTTP + tripwire checks."""
        # Prefer explicit LIVE_HTTP fail-closed before the offline tripwire so
        # unarmed environments never look like an accidental network attempt.
        self.assert_pre_submit_ready()
        assert_no_provider_network()
        from openai import OpenAI

        settings = get_settings()
        return OpenAI(
            api_key=(settings.openai_api_key or "").strip(),
            base_url=settings.openai_base_url or None,
            timeout=settings.openai_timeout_seconds,
        )

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        settings = get_settings()
        estimate = max(1, int(settings.my_croquis_ai_estimate_cents or 0))
        # Pre-submit (definite no-spend): config / gates / kwargs assembly.
        kwargs = self.build_edit_kwargs(source_png)

        client = _openai_client_override
        if client is None:
            client = self._live_openai_client()

        # --- Request-in-flight boundary: images.edit may bill from this point. ---
        try:
            result = client.with_options(max_retries=0).images.edit(**kwargs)
        except ProviderNetworkForbiddenError:
            # Tripwire during live-client construction path — definite no-spend.
            raise
        except ProviderNotAvailableError:
            raise
        except ProviderOutcomeUnknownError:
            raise
        except Exception as exc:
            rid = _safe_request_id_from_exc(exc)
            summary = _safe_api_error_summary(exc)
            if _is_presubmit_sdk_contract_error(exc):
                # SDK rejected kwargs before HTTP — definite $0, never reconciliation.
                logger.warning(
                    "Croquis images.edit SDK contract error type=%s summary=%s",
                    type(exc).__name__[:80],
                    summary[:240],
                )
                raise ProviderNotAvailableError(
                    f"images.edit refused before HTTP (SDK contract): {summary}"
                ) from exc
            if _is_definitive_images_edit_rejection(exc):
                # Completed HTTP 4xx — no generated image; safe $0 release path.
                logger.warning(
                    "Croquis images.edit rejected type=%s request_id=%s summary=%s",
                    type(exc).__name__[:80],
                    rid or "-",
                    summary[:240],
                )
                raise ProviderNotAvailableError(
                    f"images.edit rejected by provider: {summary}"
                ) from exc
            logger.warning(
                "Croquis images.edit outcome unknown type=%s request_id=%s",
                type(exc).__name__[:80],
                rid or "-",
            )
            raise ProviderOutcomeUnknownError(
                f"images.edit outcome unknown after submit: {type(exc).__name__}"
            ) from exc

        try:
            raw = extract_edit_png_bytes(result)
            normalized = fit_contain_normalize_png(raw)
            with Image.open(io.BytesIO(normalized)) as img:
                if img.size != (DESIGN_W, DESIGN_H):
                    raise ProviderOutcomeUnknownError(
                        f"Normalized croquis geometry invalid after submit: {img.size}"
                    )
                if img.mode != "RGBA":
                    raise ProviderOutcomeUnknownError(
                        f"Normalized croquis must be RGBA after submit, got {img.mode}"
                    )
        except ProviderOutcomeUnknownError:
            raise
        except Exception as exc:
            logger.warning(
                "Croquis post-submit result handling failed type=%s",
                type(exc).__name__[:80],
            )
            raise ProviderOutcomeUnknownError(
                f"Post-submit croquis result handling failed: {type(exc).__name__}"
            ) from exc

        usage = getattr(result, "usage", None)
        cost_cents, usage_source = cost_cents_from_images_usage(
            usage, fallback_cents=estimate
        )
        job_id = (
            getattr(result, "id", None)
            or getattr(result, "created", None)
            or hashlib.sha256(normalized).hexdigest()[:16]
        )
        return CroquisProviderResult(
            png_bytes=normalized,
            provider_job_id=str(job_id),
            actual_cost_cents=cost_cents,
            estimated_cost_cents=estimate,
            usage_source=usage_source,
        )


class BlockingCroquisProvider:
    """Test double: blocks inside generate_line_art until ``release`` is set.

    Used for reject/erase-during-provider concurrency coverage.
    """

    def __init__(self, *, release_event, entered_event=None, cost_cents: int = 3) -> None:
        self.release_event = release_event
        self.entered_event = entered_event
        self.cost_cents = cost_cents
        self.calls = 0
        self._inner = MockCroquisProvider(cost_cents=cost_cents)

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        self.calls += 1
        if self.entered_event is not None:
            self.entered_event.set()
        self.release_event.wait(timeout=30)
        return self._inner.generate_line_art(source_png)


_provider_override: CroquisProvider | None = None
_openai_client_override: Any | None = None


def set_croquis_provider_override(provider: CroquisProvider | None) -> None:
    """Test / local harness injection. Never set a live provider in production code paths."""
    global _provider_override
    _provider_override = provider


def set_croquis_openai_client_override(client: Any | None) -> None:
    """Inject a fake OpenAI client for mocked HTTP tests (no live network)."""
    global _openai_client_override
    _openai_client_override = client


def get_croquis_provider() -> CroquisProvider:
    if _provider_override is not None:
        return _provider_override
    settings = get_settings()
    if settings.testing:
        return FailClosedCroquisProvider(
            "Stage C tests must inject MockCroquisProvider via set_croquis_provider_override"
        )
    if not settings.my_croquis_ai_enabled:
        return FailClosedCroquisProvider("MY_CROQUIS_AI_ENABLED is false")
    if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
        return FailClosedCroquisProvider("MY_CROQUIS_AI_SPEND_CEILING_USD is 0 (fail closed)")
    return OpenAICroquisImagesEditAdapter()
