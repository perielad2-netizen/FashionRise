"""Create My Croquis Stage C — provider adapter boundary.

Default path is fail-closed. Live OpenAI images.edit is never invoked unless
MY_CROQUIS_AI_ENABLED is on, operator spend ceiling > 0, and a caller
explicitly uses the production adapter. Tests inject ``MockCroquisProvider``.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Protocol

from PIL import Image, ImageDraw

from app.core.config import get_settings

GEOMETRY_PROFILE_V1 = "fit_contain_768x1024_v1"
PROMPT_VERSION_V1 = "croquis-lineart-v1"


@dataclass(frozen=True)
class CroquisProviderResult:
    png_bytes: bytes
    provider_job_id: str
    cost_cents: int
    geometry_profile: str = GEOMETRY_PROFILE_V1
    prompt_version: str = PROMPT_VERSION_V1


class CroquisProvider(Protocol):
    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        """Transform a private source photo into fit-contain line-art PNG bytes."""


class ProviderNotAvailableError(RuntimeError):
    """Raised when a provider would be required but is disabled / fail-closed."""


class FailClosedCroquisProvider:
    """Never performs network I/O. Used as the default production-safe stub."""

    def __init__(self, reason: str = "Create My Croquis AI provider is not available.") -> None:
        self.reason = reason

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        _ = source_png
        raise ProviderNotAvailableError(self.reason)


class MockCroquisProvider:
    """Deterministic offline provider for unit/integration tests only.

    Does not call OpenAI or any network. Draws a fit-contain outline placeholder
    into the 768×1024 design plane from the source aspect ratio.
    """

    def __init__(self, *, cost_cents: int = 1, job_id: str = "mock-job") -> None:
        self.cost_cents = cost_cents
        self.job_id = job_id
        self.calls = 0

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        self.calls += 1
        with Image.open(io.BytesIO(source_png)) as src:
            src = src.convert("RGBA")
            sw, sh = src.size
        # Fit-contain into 768×1024 design plane (transparent letterbox).
        box_w, box_h = 768, 1024
        scale = min(box_w / max(sw, 1), box_h / max(sh, 1))
        dw, dh = max(1, int(sw * scale)), max(1, int(sh * scale))
        canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        x0 = (box_w - dw) // 2
        y0 = (box_h - dh) // 2
        draw.rectangle([x0, y0, x0 + dw - 1, y0 + dh - 1], outline=(20, 20, 20, 255), width=2)
        # Stable fingerprint mark so tests can assert deterministic output.
        digest = hashlib.sha256(source_png).hexdigest()[:8]
        draw.text((x0 + 8, y0 + 8), digest, fill=(20, 20, 20, 255))
        out = io.BytesIO()
        canvas.save(out, format="PNG")
        return CroquisProviderResult(
            png_bytes=out.getvalue(),
            provider_job_id=f"{self.job_id}-{self.calls}",
            cost_cents=self.cost_cents,
            geometry_profile=GEOMETRY_PROFILE_V1,
            prompt_version=PROMPT_VERSION_V1,
        )


class UnknownOutcomeCroquisProvider:
    """Test double: simulates timeout-after-send (provider called, outcome unknown)."""

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        _ = source_png
        raise TimeoutError("simulated provider timeout after send")


class OpenAICroquisImagesEditAdapter:
    """Production adapter shell for images.edit.

    Stage C ships the boundary only. This adapter refuses to run when gates or
    spend ceiling are not explicitly authorized — and tests never select it.
    Live paid calls require separate owner authorization beyond this PR.
    """

    def generate_line_art(self, source_png: bytes) -> CroquisProviderResult:
        _ = source_png
        settings = get_settings()
        if not settings.my_croquis_ai_enabled:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false")
        if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_SPEND_CEILING_USD is 0 (fail closed)")
        if not (settings.openai_api_key or "").strip():
            raise ProviderNotAvailableError("OPENAI_API_KEY missing")
        # Explicitly refuse automatic paid execution in this Stage C PR.
        # Owner-authorized paid validation is a separate activation step.
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
