#!/usr/bin/env python3
"""Regression checks for FashionRise Codemagic Android Play AAB YAML."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "codemagic.yaml"
WF_NAME = "fashionrise-android-play-internal"


def main() -> int:
    text = YAML_PATH.read_text()
    if f"{WF_NAME}:" not in text:
        print(f"FAIL: missing workflow {WF_NAME}", file=sys.stderr)
        return 1

    required = [
        "FashionRise Android (Play AAB)",
        "android_signing:",
        "fashionrise_android_upload",
        "fashionrise_native",
        "GOOGLE_PLAY_PACKAGE_NAME",
        "app.fashionrise.studio",
        "npm run build:native",
        "npx cap sync android",
        "codemagic-set-android-version-code.sh",
        "bundleRelease",
        "check:android-appicon",
        # Artifacts: signed AAB only (manual Play Console upload / optional later publish).
        "outputs/bundle/release/*.aab",
    ]
    for needle in required:
        if needle not in text:
            print(f"FAIL: android workflow missing {needle!r}", file=sys.stderr)
            return 1

    # Do not auto-submit to production from this workflow.
    wf_block = text.split(f"{WF_NAME}:", 1)[1]
    # Truncate at next top-level workflow-ish key if present; keep simple.
    next_wf = re.search(r"\n  [a-z0-9_-]+:\n", wf_block[1:])
    if next_wf:
        wf_block = wf_block[: next_wf.start() + 1]
    for forbidden in ("track: production", "submit_as_draft: false"):
        for line in wf_block.splitlines():
            if line.lstrip().startswith("#"):
                continue
            if forbidden in line:
                print(f"FAIL: production submit must not be active: {line}", file=sys.stderr)
                return 1

    # iOS workflows must remain present (do not regress iOS release config).
    if "fashionrise-ios-app-store:" not in text:
        print("FAIL: iOS App Store workflow missing after Android edit", file=sys.stderr)
        return 1

    print(f"OK: {WF_NAME} Codemagic Android YAML asserts passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
