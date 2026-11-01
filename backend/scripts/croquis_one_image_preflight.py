#!/usr/bin/env python3
"""Private one-image Create My Croquis preflight — STOP before any paid request.

Default mode never opens sockets and never calls OpenAI. Prints exact provider
configuration, expected exposure, and the owner-approved one-call plan.

Usage (from backend/):
  python scripts/croquis_one_image_preflight.py

Does NOT accept --execute-paid in this build. Owner must explicitly authorize
a follow-up change before any billable images.edit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.personal_croquis_provider import (  # noqa: E402
    OpenAICroquisImagesEditAdapter,
    ProviderNotAvailableError,
    arm_provider_network_tripwire,
)
from tests.fixtures.croquis.synthetic_adult_model import (  # noqa: E402
    load_synthetic_clothed_adult_model_png,
)

# Proposed one-call validation envelope (owner must approve before LIVE_HTTP).
PROPOSED_CEILING_USD = 1.00
PROPOSED_MAX_RUN_USD = 1.00
PROPOSED_MAX_EXPOSURE_CENTS = 80
PROPOSED_ESTIMATE_CENTS = 40
PROPOSED_QUALITY = "medium"
PROPOSED_SIZE = "1024x1536"
PROPOSED_MODEL = "gpt-image-2.5-sunburst"


def main() -> int:
    arm_provider_network_tripwire()
    settings = get_settings()
    source = load_synthetic_clothed_adult_model_png()

    print("=== Create My Croquis — ONE-IMAGE PREFLIGHT (OFFLINE) ===")
    print("Fixture: tests/fixtures/croquis/synthetic_clothed_adult_model.png")
    print(f"Fixture bytes: {len(source)}")
    print()
    print("Current process settings (fail-closed defaults expected):")
    print(
        json.dumps(
            {
                "my_croquis_ai_enabled": settings.my_croquis_ai_enabled,
                "my_croquis_ai_live_http": getattr(settings, "my_croquis_ai_live_http", False),
                "my_croquis_ai_spend_ceiling_usd": settings.my_croquis_ai_spend_ceiling_usd,
                "my_croquis_ai_max_exposure_cents": settings.my_croquis_ai_max_exposure_cents,
                "my_croquis_ai_estimate_cents": settings.my_croquis_ai_estimate_cents,
                "openai_image_model": settings.openai_image_model,
                "api_key_present": bool((settings.openai_api_key or "").strip()),
            },
            indent=2,
        )
    )
    print()
    print("Proposed ONE-CALL execution envelope (NOT armed; owner approval required):")
    print(
        json.dumps(
            {
                "model": PROPOSED_MODEL,
                "size": PROPOSED_SIZE,
                "quality": PROPOSED_QUALITY,
                "background": "transparent",
                "output_format": "png",
                "n": 1,
                "design_plane_after_normalize": "768x1024",
                "estimate_cents": PROPOSED_ESTIMATE_CENTS,
                "max_exposure_cents": PROPOSED_MAX_EXPOSURE_CENTS,
                "spend_ceiling_usd": PROPOSED_CEILING_USD,
                "max_usd_per_run": PROPOSED_MAX_RUN_USD,
                "live_http": True,
                "source": "synthetic_clothed_adult_model.png only",
                "gates": "temporary process env only — no production flag flip",
            },
            indent=2,
        )
    )
    print()

    # Attempt adapter construct under current (likely fail-closed) settings.
    try:
        adapter = OpenAICroquisImagesEditAdapter()
        report = adapter.preflight_report(source)
        print("Adapter preflight_report (kwargs assembled, 0 HTTP):")
        print(json.dumps(report, indent=2))
        try:
            adapter.generate_line_art(source)
            print("ERROR: generate_line_art returned without HTTP arming — abort")
            return 2
        except ProviderNotAvailableError as exc:
            print(f"generate_line_art fail-closed as expected: {exc}")
    except ProviderNotAvailableError as exc:
        print(f"Adapter construct fail-closed under current settings: {exc}")
        print("(Expected when MY_CROQUIS_AI_ENABLED / ceiling are still 0.)")

    print()
    print("=== STOP BEFORE FIRST PAID REQUEST ===")
    print("No OpenAI sockets opened. No images.edit executed.")
    print("Owner must explicitly approve the proposed dollar ceiling and one-call plan")
    print("before any MY_CROQUIS_AI_LIVE_HTTP=true validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
