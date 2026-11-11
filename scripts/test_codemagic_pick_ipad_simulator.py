#!/usr/bin/env python3
"""Offline regression for codemagic-pick-ipad-simulator.sh preference order."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PICK = ROOT / "scripts" / "codemagic-pick-ipad-simulator.sh"


def run_pick(payload: dict) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh)
        path = fh.name
    env = os.environ.copy()
    env["FR_SIMCTL_LIST_JSON"] = path
    out = subprocess.check_output(["bash", str(PICK)], env=env, text=True)
    return out.strip().splitlines()[-1]


def main() -> int:
    payload = {
        "devices": {
            "com.apple.CoreSimulator.SimRuntime.iOS-18-5": [
                {
                    "name": "iPhone 16 Pro",
                    "udid": "phone-1",
                    "isAvailable": True,
                },
                {
                    "name": "iPad mini (A17 Pro)",
                    "udid": "mini-1",
                    "isAvailable": True,
                },
                {
                    "name": "iPad Pro (12.9-inch) (6th generation)",
                    "udid": "pro129-1",
                    "isAvailable": True,
                },
                {
                    "name": "iPad Air (13-inch) (M2)",
                    "udid": "air13-1",
                    "isAvailable": True,
                },
                {
                    "name": "iPad Pro (13-inch) (M4)",
                    "udid": "pro13-1",
                    "isAvailable": True,
                },
            ]
        }
    }
    line = run_pick(payload)
    udid, name, _runtime = line.split("|", 2)
    assert udid == "pro13-1", line
    assert "13-inch" in name and "Pro" in name, line

    # Without 13" Pro, prefer 13" Air over 12.9" Pro.
    payload["devices"]["com.apple.CoreSimulator.SimRuntime.iOS-18-5"] = [
        {
            "name": "iPad Pro (12.9-inch) (6th generation)",
            "udid": "pro129-1",
            "isAvailable": True,
        },
        {
            "name": "iPad Air (13-inch) (M2)",
            "udid": "air13-1",
            "isAvailable": True,
        },
    ]
    line = run_pick(payload)
    udid, name, _ = line.split("|", 2)
    assert udid == "air13-1", line

    print("test_codemagic_pick_ipad_simulator: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
