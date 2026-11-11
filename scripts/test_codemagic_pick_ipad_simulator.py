#!/usr/bin/env python3
"""Offline regression: 13-inch-only iPad picker (no invent/upscale)."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PICK = ROOT / "scripts" / "codemagic-pick-ipad-simulator.sh"


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


def main() -> int:
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

    # Without 13" Pro, prefer 13" Air (still supported).
    payload["devices"]["com.apple.CoreSimulator.SimRuntime.iOS-18-5"] = [
        {
            "name": "iPad Pro (12.9-inch) (6th generation)",
            "udid": "pro129-1",
            "isAvailable": True,
        },
        {"name": "iPad Air (13-inch) (M2)", "udid": "air13-1", "isAvailable": True},
    ]
    cp = run_pick(payload)
    assert cp.returncode == 0, cp.stderr
    line = cp.stdout.strip().splitlines()[-1]
    udid, name, _ = line.split("|", 2)
    assert udid == "air13-1", line

    # Only unsupported tablets → fail closed (do not invent/upscale).
    payload["devices"]["com.apple.CoreSimulator.SimRuntime.iOS-18-5"] = [
        {
            "name": "iPad Pro (12.9-inch) (6th generation)",
            "udid": "pro129-1",
            "isAvailable": True,
        },
        {"name": "iPad mini (A17 Pro)", "udid": "mini-1", "isAvailable": True},
    ]
    cp = run_pick(payload)
    assert cp.returncode != 0, "expected failure when no 13-inch device"
    assert "13-inch" in (cp.stderr or "").lower() or "FAIL" in (cp.stderr or "")

    print("test_codemagic_pick_ipad_simulator: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
