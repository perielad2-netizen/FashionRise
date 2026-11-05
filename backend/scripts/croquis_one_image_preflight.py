#!/usr/bin/env python3
"""Private one-image Create My Croquis preflight — STOP before any paid request.

Default mode never opens sockets and never calls OpenAI. Prints exact provider
configuration, expected exposure, and the owner-approved one-call plan.

Usage (from backend/):
  python scripts/croquis_one_image_preflight.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.personal_croquis_one_call import (
    OneCallGuardError,
    approved_envelope,
    load_approved_fixture_bytes,
)
from app.services.personal_croquis_provider import (
    OpenAICroquisImagesEditAdapter,
    ProviderNotAvailableError,
    arm_provider_network_tripwire,
)


def main() -> int:
    arm_provider_network_tripwire()
    settings = get_settings()
    try:
        source = load_approved_fixture_bytes()
        fixture_ok = True
        fixture_err = None
    except OneCallGuardError as exc:
        source = b""
        fixture_ok = False
        fixture_err = str(exc)

    print("=== Create My Croquis — ONE-IMAGE PREFLIGHT (OFFLINE) ===")
    print("Fixture: tests/fixtures/croquis/synthetic_clothed_adult_model.png")
    print("Fixture class: procedural clothed cartoon (NOT a photograph / fidelity proof)")
    if fixture_ok:
        print(f"Fixture bytes: {len(source)}")
        print(f"Fixture sha256: {hashlib.sha256(source).hexdigest()}")
    else:
        print(f"Fixture GUARD FAILED: {fixture_err}")
    print()
    print("Current process settings (fail-closed defaults expected):")
    print(
        json.dumps(
            {
                "my_croquis_ai_enabled": settings.my_croquis_ai_enabled,
                "my_croquis_ai_live_http": getattr(settings, "my_croquis_ai_live_http", False),
                "my_croquis_ai_spend_ceiling_usd": settings.my_croquis_ai_spend_ceiling_usd,
                "my_croquis_ai_max_usd_per_run": settings.my_croquis_ai_max_usd_per_run,
                "my_croquis_ai_max_usd_per_user_day": settings.my_croquis_ai_max_usd_per_user_day,
                "my_croquis_ai_max_exposure_cents": settings.my_croquis_ai_max_exposure_cents,
                "my_croquis_ai_estimate_cents": settings.my_croquis_ai_estimate_cents,
                "my_croquis_ai_image_size": settings.my_croquis_ai_image_size,
                "my_croquis_ai_image_quality": settings.my_croquis_ai_image_quality,
                "openai_image_model": settings.openai_image_model,
                "openai_base_url": settings.openai_base_url,
                "api_key_present": bool((settings.openai_api_key or "").strip()),
            },
            indent=2,
        )
    )
    print()
    print("Proposed ONE-CALL execution envelope (NOT armed; owner+PM approval required):")
    print(json.dumps(approved_envelope(), indent=2))
    print()

    if not fixture_ok:
        print("=== STOP — fixture guard failed; no paid path ===")
        return 2

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
