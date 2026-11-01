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
PROMPT_VERSION_V1 = "croquis-lineart-v1"
DESIGN_W = 768
DESIGN_H = 1024

# Provider request size must be an explicitly allowlisted Sunburst size.
# Output is always post-normalized to the design plane (768×1024 fit-contain).
CROQUIS_PROVIDER_SIZE = "1024x1536"
CROQUIS_PROVIDER_QUALITY_DEFAULT = "medium"

# Versioned croquis prompt — fashion line art, not identity recreation / measurements.
CROQUIS_LINEART_PROMPT_V1 = (
    "Convert the attached full-body fashion photograph into a neutral fashion croquis "
    "line-art figure for garment design. Output a clean black line drawing on a "
    "transparent background. Preserve pose proportions suitable for fashion illustration. "
    "Do not recreate a realistic facial likeness, do not invent measurements, do not add "
    "garments, logos, text, or color fills. Keep the entire figure visible (no crop)."
)

# Official gpt-image-2.5-sunburst token rates (USD per 1M tokens) — design §9.1.
_RATE_TEXT_IN = 5.0
_RATE_IMAGE_IN = 8.0
_RATE_IMAGE_OUT = 30.0


@dataclass(frozen=True)
class CroquisProviderResult:
    png_bytes: bytes
    provider_job_id: str
    # Authoritative usage when the provider reports it; otherwise 0 and estimate is used.
    actual_cost_cents: int
    estimated_cost_cents: int
    geometry_profile: str = GEOMETRY_PROFILE_V1
    prompt_version: str = PROMPT_VERSION_V1
    usage_source: str = "estimate"  # "provider_usage" | "estimate"


class CroquisProvider(Protocol):
    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        """Transform a private source photo into fit-contain line-art PNG bytes."""


class ProviderNotAvailableError(RuntimeError):
    """Definitely pre-submit refusal — safe to release reservation at $0."""


class ProviderOutcomeUnknownError(RuntimeError):
    """Request may have been sent/billed; outcome unknown — reconciliation required.

    Raised for any failure after ``images.edit`` invocation begins (SDK timeout,
    connection error, HTTP 5xx, missing/malformed result bytes, etc.).
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
                prompt=CROQUIS_LINEART_PROMPT_V1,
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
        return kwargs

    def preflight_report(self, source_png: bytes) -> dict[str, Any]:
        """Operator-facing preflight (no HTTP). Safe to log — no image bytes."""
        settings = get_settings()
        kwargs = self.build_edit_kwargs(source_png)
        estimate = max(1, int(settings.my_croquis_ai_estimate_cents or 0))
        max_exposure = int(settings.my_croquis_ai_max_exposure_cents or 0)
        return {
            "model": kwargs.get("model"),
            "size": kwargs.get("size"),
            "quality": kwargs.get("quality"),
            "background": kwargs.get("background"),
            "output_format": kwargs.get("output_format"),
            "n": kwargs.get("n"),
            "prompt_version": PROMPT_VERSION_V1,
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
