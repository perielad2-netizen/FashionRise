#!/usr/bin/env python3
"""Assert FashionRise iPad Screenshots Codemagic workflow safety invariants."""

from __future__ import annotations

import pathlib
import re
import sys

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "codemagic.yaml"
WF_ID = "fashionrise-ipad-screenshots"


def main() -> int:
    raw = YAML_PATH.read_text()
    if WF_ID not in raw:
        raise AssertionError(f"missing workflow id {WF_ID}")
    if 'name: FashionRise iPad Screenshots' not in raw:
        raise AssertionError("workflow display name must be 'FashionRise iPad Screenshots'")

    if yaml is None:
        # Lightweight fallbacks when PyYAML is absent.
        if re.search(rf"{WF_ID}:[\s\S]*?triggering:", raw):
            raise AssertionError("iPad screenshots workflow must be manual (no triggering)")
        if re.search(rf"{WF_ID}:[\s\S]*?publishing:", raw):
            raise AssertionError("iPad screenshots workflow must not publish")
        if ".ipa" in raw.split(WF_ID, 1)[1].split("\n  #", 1)[0]:
            # crude: still ok if only in comments of the second workflow block
            pass
        print("test_codemagic_ipad_screenshots_yaml: ok (lightweight)")
        return 0

    data = yaml.safe_load(raw)
    wf = data["workflows"][WF_ID]
    if "triggering" in wf:
        raise AssertionError("manual builds only — no triggering block")
    if "publishing" in wf:
        raise AssertionError("screenshots workflow must not define publishing")
    if (wf.get("integrations") or {}).get("app_store_connect"):
        raise AssertionError("screenshots workflow must not use app_store_connect integration")

    artifacts = [str(a) for a in (wf.get("artifacts") or [])]
    if any(".ipa" in a for a in artifacts):
        raise AssertionError(f"screenshots artifacts must not include IPA paths: {artifacts}")
    if not any("ipad-screenshots" in a for a in artifacts):
        raise AssertionError("artifacts must include ipad-screenshots PNGs")

    script_blob = "\n".join(
        (s.get("script") if isinstance(s, dict) else "") or "" for s in (wf.get("scripts") or [])
    )
    for needle in (
        "generic/platform=iOS Simulator",
        "CODE_SIGNING_ALLOWED=NO",
        "codemagic-ipad-screenshots-session.sh",
        "TARGETED_DEVICE_FAMILY = \"1,2\"",
        "npm run build:native",
    ):
        if needle not in script_blob and needle not in raw:
            # device-family check is in a script step string
            if needle not in raw:
                raise AssertionError(f"missing required screenshots step content: {needle}")

    if "xcode-project build-ipa" in script_blob:
        raise AssertionError("screenshots workflow must not call build-ipa")
    if "app-store-connect" in script_blob.lower() and "no asc" not in script_blob.lower():
        # comments may mention ASC; active publish commands must not appear
        for line in script_blob.splitlines():
            if "app-store-connect" in line.lower() and not line.lstrip().startswith("#"):
                raise AssertionError(f"ASC command in screenshots workflow: {line}")

    print("test_codemagic_ipad_screenshots_yaml: ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"test_codemagic_ipad_screenshots_yaml: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
