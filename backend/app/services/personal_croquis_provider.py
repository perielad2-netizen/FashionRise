"""Create My Croquis Stage C — provider adapter boundary.

Default path is fail-closed. Live OpenAI images.edit is never invoked unless
MY_CROQUIS_AI_ENABLED is on, operator spend ceiling > 0, and a caller
explicitly uses the production adapter. Tests inject ``MockCroquisProvider``.

Importing this module must not open network connections.
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass
from typing import Protocol

from PIL import Image, ImageDraw, ImageOps

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GEOMETRY_PROFILE_V1 = "fit_contain_768x1024_v1"
PROMPT_VERSION_V1 = "croquis-lineart-v1"
DESIGN_W = 768
DESIGN_H = 1024

# Versioned croquis prompt — fashion line art, not identity recreation / measurements.
CROQUIS_LINEART_PROMPT_V1 = (
    "Convert the attached full-body fashion photograph into a neutral fashion croquis "
    "line-art figure for garment design. Output a clean black line drawing on a "
    "transparent background. Preserve pose proportions suitable for fashion illustration. "
    "Do not recreate a realistic facial likeness, do not invent measurements, do not add "
    "garments, logos, text, or color fills. Keep the entire figure visible (no crop)."
)


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
    """Raised when a provider would be required but is disabled / fail-closed."""


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
            "Create My Croquis Stage C tripwire: real provider network call forbidden offline"
        )


def fit_contain_normalize_png(
    raw_png: bytes,
    *,
    box_w: int = DESIGN_W,
    box_h: int = DESIGN_H,
) -> bytes:
    """Fit-contain onto the design plane with transparent padding; strip EXIF."""
    with Image.open(io.BytesIO(raw_png)) as src:
        src = ImageOps.exif_transpose(src)
        src = src.convert("RGBA")
        sw, sh = src.size
        scale = min(box_w / max(sw, 1), box_h / max(sh, 1))
        dw, dh = max(1, int(round(sw * scale))), max(1, int(round(sh * scale)))
        resized = src.resize((dw, dh), Image.Resampling.LANCZOS)
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
        with Image.open(io.BytesIO(source_png)) as src:
            src = src.convert("RGBA")
            sw, sh = src.size
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
    """Test double: timeout after submission would have started."""

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        _ = source_png
        raise TimeoutError("simulated provider timeout after send")


class CrashBeforeSubmitCroquisProvider:
    """Test double: fails before any provider submission."""

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        _ = source_png
        raise ProviderNotAvailableError("crash before provider submission")


class OpenAICroquisImagesEditAdapter:
    """Production adapter shell wrapping images.edit for croquis line art.

    Construction and prompt assembly never open sockets. Live HTTP is blocked
    unless gates + ceiling allow AND the offline tripwire is disarmed. Stage C
    still refuses automatic paid execution until separate owner authorization.
    """

    def __init__(self) -> None:
        # Fail closed on construct if gates are off — no client creation / network.
        settings = get_settings()
        if not settings.my_croquis_ai_enabled:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false")
        if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_SPEND_CEILING_USD is 0 (fail closed)")

    def build_edit_kwargs(self, source_png: bytes) -> dict:
        """Assemble images.edit kwargs without performing HTTP."""
        settings = get_settings()
        model = (settings.openai_image_model or "gpt-image-2.5-sunburst").strip()
        return {
            "model": model,
            "prompt": CROQUIS_LINEART_PROMPT_V1,
            "prompt_version": PROMPT_VERSION_V1,
            "size": f"{DESIGN_W}x{DESIGN_H}",
            "source_sha256": hashlib.sha256(source_png).hexdigest(),
            "geometry_profile": GEOMETRY_PROFILE_V1,
        }

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        _ = self.build_edit_kwargs(source_png)
        # Would be the sole live HTTP entry — tripwire fails offline tests if reached.
        assert_no_provider_network()
        # Explicitly refuse automatic paid execution in this Stage C PR.
        raise ProviderNotAvailableError(
            "Live OpenAI croquis generation is not activated in this Stage C build. "
            "Use a mocked provider in tests; paid validation requires separate authorization."
        )


_provider_override: CroquisProvider | None = None


def set_croquis_provider_override(provider: CroquisProvider | None) -> None:
    """Test / local harness injection. Never set a live provider in production code paths."""
    global _provider_override
    _provider_override = provider


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
