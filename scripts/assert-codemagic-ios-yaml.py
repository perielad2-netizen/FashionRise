#!/usr/bin/env python3
"""Regression checks for FashionRise Codemagic iOS YAML (no Codemagic required)."""

from __future__ import annotations

import pathlib
import re
import sys

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - fallback parser for environments without PyYAML
    yaml = None


ROOT = pathlib.Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "codemagic.yaml"


def load_workflow() -> dict:
    text = YAML_PATH.read_text()
    if yaml is not None:
        data = yaml.safe_load(text)
        return data["workflows"]["fashionrise-ios-app-store"]

    # Minimal fallback: enough structure for our asserts without PyYAML.
    if "fashionrise-ios-app-store:" not in text:
        raise SystemExit("missing fashionrise-ios-app-store workflow")
    return {"_raw": text}


def assert_single_ipa_artifact(wf: dict, raw: str) -> None:
    if "_raw" in wf:
        artifacts = re.findall(r"^\s+-\s+(\S*\.ipa\S*)\s*$", raw, flags=re.M)
    else:
        artifacts = [str(a) for a in (wf.get("artifacts") or [])]
        artifacts = [a for a in artifacts if ".ipa" in a]

    if len(artifacts) != 1:
        raise AssertionError(f"expected exactly one .ipa artifact entry, got {artifacts!r}")

    only = artifacts[0]
    expected = "$CM_BUILD_DIR/web-ui/ios/App/build/ios/ipa/App.ipa"
    if only != expected and not only.endswith("/ios/App/build/ios/ipa/App.ipa"):
        raise AssertionError(f"IPA artifact must be the verified absolute App.ipa path, got {only!r}")

    forbidden = (
        "codemagic-artifacts/*.ipa",
        "$CM_EXPORT_DIR/*.ipa",
        "build/ios/ipa/*.ipa",
    )
    for bad in forbidden:
        if bad in raw:
            # allow comment mentions only if prefixed with Do not / # explanation
            for line in raw.splitlines():
                if bad in line and not line.lstrip().startswith("#"):
                    raise AssertionError(f"forbidden IPA artifact/staging pattern still active: {bad}")


def assert_no_ipa_staging_copies(raw: str) -> None:
    for line in raw.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if re.search(r"cp\s+-f\s+.*App\.ipa", line):
            raise AssertionError(f"IPA must not be copied to staging dirs: {line}")
        if "CM_EXPORT_DIR/App.ipa" in line or "codemagic-artifacts/App.ipa" in line:
            raise AssertionError(f"IPA staging path referenced outside comments: {line}")


def assert_unique_build_number_policy(raw: str, wf: dict) -> None:
    if "IOS_BUILD_NUMBER_OFFSET" not in raw:
        raise AssertionError("missing IOS_BUILD_NUMBER_OFFSET")
    for line in raw.splitlines():
        if "MIN_IOS_BUILD_NUMBER" in line and not line.lstrip().startswith("#"):
            raise AssertionError("MIN_IOS_BUILD_NUMBER floor must not remain as an active var")

    if "codemagic-set-ios-build-number.sh" not in raw:
        raise AssertionError("Set build number must call scripts/codemagic-set-ios-build-number.sh")
    if "codemagic-verify-ios-ipa.sh" not in raw:
        raise AssertionError("Verify step must call scripts/codemagic-verify-ios-ipa.sh")

    if "_raw" not in wf:
        vars_ = (wf.get("environment") or {}).get("vars") or {}
        if "IOS_BUILD_NUMBER_OFFSET" not in vars_:
            raise AssertionError("environment.vars.IOS_BUILD_NUMBER_OFFSET required")
        if vars_.get("IOS_BUILD_NUMBER_OFFSET") in (None, "", "0"):
            raise AssertionError("IOS_BUILD_NUMBER_OFFSET must be a positive offset string")
        pub = (wf.get("publishing") or {}).get("app_store_connect") or {}
        if pub.get("auth") != "integration":
            raise AssertionError("publishing must use auth: integration")
        if pub.get("submit_to_testflight") is not False:
            raise AssertionError("submit_to_testflight must be false")
        if pub.get("submit_to_app_store") is not False:
            raise AssertionError("submit_to_app_store must be false")
        if "triggering" in wf:
            raise AssertionError("manual builds only — no triggering block")
        if (wf.get("environment") or {}).get("xcode") != 26.5 and str(
            (wf.get("environment") or {}).get("xcode")
        ) != "26.5":
            raise AssertionError("xcode must remain 26.5")


def main() -> int:
    raw = YAML_PATH.read_text()
    wf = load_workflow()
    assert_single_ipa_artifact(wf if "_raw" not in wf else {"_raw": raw}, raw)
    assert_no_ipa_staging_copies(raw)
    assert_unique_build_number_policy(raw, wf)
    print("assert-codemagic-ios-yaml: ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"assert-codemagic-ios-yaml: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
