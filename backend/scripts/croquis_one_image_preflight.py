#!/usr/bin/env python3
"""Private one-image Create My Croquis preflight — STOP before any paid request.

Default mode never opens sockets and never calls OpenAI. Prints exact provider
configuration, expected exposure, and the owner-approved one-call plan.

Usage (from backend/):
  python scripts/croquis_one_image_preflight.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.personal_croquis_provider import (
    OpenAICroquisImagesEditAdapter,
    ProviderNotAvailableError,
    arm_provider_network_tripwire,
)
from tests.fixtures.croquis.synthetic_adult_model import (
    load_synthetic_clothed_adult_model_png,
)

# Revised PM envelope (2026-11-01): reserve full $1.00; 40¢ soft estimate only.
PROPOSED_CEILING_USD = 1.00
PROPOSED_MAX_RUN_USD = 1.00
PROPOSED_MAX_DAY_USD = 1.00
PROPOSED_MAX_EXPOSURE_CENTS = 100
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
    print("Fixture class: procedural clothed cartoon (NOT a photograph / fidelity proof)")
    print(f"Fixture bytes: {len(source)}")
    print()
    print("Current process settings (fail-closed defaults expected):")
    print(
        json.dumps(
            {
                "my_croquis_ai_enabled": settings.my_croquis_ai_enabled,
                "my_croquis_ai_live_http": getattr(settings, "my_croquis_ai_live_http", False),
                "my_croquis_ai_spend_ceiling_usd": settings.my_croquis_ai_spend_ceiling_usd,
                "my_croquis_ai_max_usd_per_user_day": settings.my_croquis_ai_max_usd_per_user_day,
                "my_croquis_ai_max_exposure_cents": settings.my_croquis_ai_max_exposure_cents,
                "my_croquis_ai_estimate_cents": settings.my_croquis_ai_estimate_cents,
                "openai_image_model": settings.openai_image_model,
                "api_key_present": bool((settings.openai_api_key or "").strip()),
            },
            indent=2,
        )
    )
    print()
    print("Proposed ONE-CALL execution envelope (NOT armed; owner+PM approval required):")
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
                "estimate_cents_soft_only": PROPOSED_ESTIMATE_CENTS,
                "max_exposure_cents": PROPOSED_MAX_EXPOSURE_CENTS,
                "spend_ceiling_usd": PROPOSED_CEILING_USD,
                "max_usd_per_run": PROPOSED_MAX_RUN_USD,
                "max_usd_per_user_day": PROPOSED_MAX_DAY_USD,
                "live_http": True,
                "openai_base_url": "https://api.openai.com/v1 (official only)",
                "source": "synthetic_clothed_adult_model.png only",
                "db": "DATABASE_URL_TEST disposable only — never fashionrise_beta",
                "gates": "temporary process env only — no production flag flip",
                "note": "Reservation is NOT a provider-enforced hard cap; verify invoice/usage after any paid call.",
            },
            indent=2,
        )
    )
    print()

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
    print("See scripts/croquis_one_image_executor.py for the disposable-DB one-call plan.")
    print("Owner must explicitly approve the revised $1.00 / 100¢ envelope before any paid run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
