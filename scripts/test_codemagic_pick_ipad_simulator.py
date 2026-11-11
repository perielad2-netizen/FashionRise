#!/usr/bin/env python3
"""Offline regression: 13-inch-only iPad picker (no invent/upscale)."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PICK = ROOT / "scripts" / "codemagic-pick-ipad-simulator.sh"
sys.path.insert(0, str(ROOT / "scripts"))
from fr_ipad_screenshot_lib import is_supported_13_inch_ipad_name, score_13_inch_ipad  # noqa: E402


def run_pick(payload: dict) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh)
        path = fh.name
    env = os.environ.copy()
    env["FR_SIMCTL_LIST_JSON"] = path
    return subprocess.run(
        ["bash", str(PICK)],
        env=env,
        text=True,
        capture_output=True,
    )


def test_name_variants() -> None:
    """Exact names observed on Codemagic + legacy parenthesized forms."""
    supported = [
        "iPad Pro 13-inch (M5)",  # Codemagic / newer Xcode
        "iPad Air 13-inch (M4)",
        "iPad Air 13-inch (M3)",
        "iPad Pro (13-inch) (M4)",  # legacy parenthesized size
        "iPad Air (13-inch) (M2)",
    ]
    rejected = [
        "iPad Pro 11-inch (M5)",
        "iPad Air 11-inch (M3)",
        "iPad mini (A17 Pro)",
        "iPad Pro (12.9-inch) (6th generation)",
        "iPad Pro (11-inch) (M4)",
        "iPhone 16 Pro",
    ]
    for name in supported:
        assert is_supported_13_inch_ipad_name(name), name
    for name in rejected:
        assert not is_supported_13_inch_ipad_name(name), name
        assert score_13_inch_ipad(name) is None, name

    assert score_13_inch_ipad("iPad Pro 13-inch (M5)") == 100
    assert score_13_inch_ipad("iPad Air 13-inch (M4)") == 90


def main() -> int:
    test_name_variants()

    # Codemagic-style names from the failed live run — Pro preferred over Air.
    payload = {
        "devices": {
            "com.apple.CoreSimulator.SimRuntime.iOS-26-0": [
                {"name": "iPhone 16 Pro", "udid": "phone-1", "isAvailable": True},
                {"name": "iPad mini (A17 Pro)", "udid": "mini-1", "isAvailable": True},
                {"name": "iPad Pro 11-inch (M5)", "udid": "pro11-1", "isAvailable": True},
                {"name": "iPad Air 13-inch (M3)", "udid": "air13-m3", "isAvailable": True},
                {"name": "iPad Air 13-inch (M4)", "udid": "air13-m4", "isAvailable": True},
                {"name": "iPad Pro 13-inch (M5)", "udid": "pro13-m5", "isAvailable": True},
            ]
        }
    }
    cp = run_pick(payload)
    assert cp.returncode == 0, cp.stderr
    line = cp.stdout.strip().splitlines()[-1]
    udid, name, _runtime = line.split("|", 2)
    assert udid == "pro13-m5", line
    assert name == "iPad Pro 13-inch (M5)", line

    # Legacy parenthesized names still work; Pro over Air.
    payload = {
        "devices": {
            "com.apple.CoreSimulator.SimRuntime.iOS-18-5": [
                {"name": "iPhone 16 Pro", "udid": "phone-1", "isAvailable": True},
                {"name": "iPad mini (A17 Pro)", "udid": "mini-1", "isAvailable": True},
                {
                    "name": "iPad Pro (12.9-inch) (6th generation)",
                    "udid": "pro129-1",
                    "isAvailable": True,
                },
                {"name": "iPad Air (13-inch) (M2)", "udid": "air13-1", "isAvailable": True},
                {"name": "iPad Pro (13-inch) (M4)", "udid": "pro13-1", "isAvailable": True},
            ]
        }
    }
    cp = run_pick(payload)
    assert cp.returncode == 0, cp.stderr
    line = cp.stdout.strip().splitlines()[-1]
    udid, name, _runtime = line.split("|", 2)
    assert udid == "pro13-1", line
    assert "13-inch" in name and "Pro" in name, line

    # Without 13" Pro, prefer 13" Air (Codemagic-style name).
    payload["devices"]["com.apple.CoreSimulator.SimRuntime.iOS-18-5"] = [
        {
            "name": "iPad Pro (12.9-inch) (6th generation)",
            "udid": "pro129-1",
            "isAvailable": True,
        },
        {"name": "iPad Air 13-inch (M4)", "udid": "air13-m4", "isAvailable": True},
        {"name": "iPad Pro 11-inch (M5)", "udid": "pro11-1", "isAvailable": True},
    ]
    cp = run_pick(payload)
    assert cp.returncode == 0, cp.stderr
    line = cp.stdout.strip().splitlines()[-1]
    udid, name, _ = line.split("|", 2)
    assert udid == "air13-m4", line

    # Only unsupported tablets → fail closed (do not invent/upscale).
    payload["devices"]["com.apple.CoreSimulator.SimRuntime.iOS-18-5"] = [
        {
            "name": "iPad Pro (12.9-inch) (6th generation)",
            "udid": "pro129-1",
            "isAvailable": True,
        },
        {"name": "iPad mini (A17 Pro)", "udid": "mini-1", "isAvailable": True},
        {"name": "iPad Pro 11-inch (M5)", "udid": "pro11-1", "isAvailable": True},
    ]
    cp = run_pick(payload)
    assert cp.returncode != 0, "expected failure when no 13-inch device"
    assert "13-inch" in (cp.stderr or "").lower() or "FAIL" in (cp.stderr or "")

    print("test_codemagic_pick_ipad_simulator: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
