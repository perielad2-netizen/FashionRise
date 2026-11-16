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

    def workflow_block(name: str) -> str | None:
        m = re.search(rf"(?m)^  {re.escape(name)}:\n", text)
        if not m:
            return None
        rest = text[m.end() :]
        nxt = re.search(r"(?m)^  [a-z0-9_-]+:\n", rest)
        return rest[: nxt.start()] if nxt else rest

    # Do not auto-submit to production from this workflow.
    wf_block = workflow_block(WF_NAME)
    if wf_block is None:
        print(f"FAIL: could not locate workflow block {WF_NAME}", file=sys.stderr)
        return 1
    for forbidden in ("track: production", "submit_as_draft: false"):
        for line in wf_block.splitlines():
            if line.lstrip().startswith("#"):
                continue
            if forbidden in line:
                print(f"FAIL: production submit must not be active: {line}", file=sys.stderr)
                return 1

    # Android Play AAB must build on Linux (not mac).
    if not re.search(r"(?m)^\s*instance_type:\s*linux_x2\s*$", wf_block):
        print("FAIL: android workflow must use instance_type: linux_x2", file=sys.stderr)
        return 1
    if re.search(r"(?m)^\s*instance_type:\s*mac_mini_m2\s*$", wf_block):
        print("FAIL: android workflow must not use mac_mini_m2", file=sys.stderr)
        return 1

    # Linux-compatible Android builder surface still present (SDK + signing + Gradle).
    if "ANDROID_SDK_ROOT" not in wf_block:
        print("FAIL: android workflow missing ANDROID_SDK_ROOT usage", file=sys.stderr)
        return 1
    if "java: 21" not in wf_block:
        print("FAIL: android workflow missing java: 21", file=sys.stderr)
        return 1
    if "android_signing:" not in wf_block:
        print("FAIL: android workflow missing android_signing", file=sys.stderr)
        return 1
    if "./gradlew bundleRelease" not in wf_block:
        print("FAIL: android workflow missing ./gradlew bundleRelease", file=sys.stderr)
        return 1

    # iOS workflows must remain present on mac (do not regress iOS release config).
    if "fashionrise-ios-app-store:" not in text:
        print("FAIL: iOS App Store workflow missing after Android edit", file=sys.stderr)
        return 1
    ios_block = workflow_block("fashionrise-ios-app-store")
    if ios_block is None or not re.search(r"(?m)^\s*instance_type:\s*mac_mini_m2\s*$", ios_block):
        print("FAIL: iOS App Store workflow must stay on mac_mini_m2", file=sys.stderr)
        return 1

    print(f"OK: {WF_NAME} Codemagic Android YAML asserts passed (linux_x2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
