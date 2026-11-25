#!/usr/bin/env python3
"""Validate FashionRise Google Play listing image constraints."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent

CHECKS = [
    {
        "name": "fashionrise-app-icon.png",
        "required": True,
        "size": (512, 512),
        "max_bytes": 1 * 1024 * 1024,
        "modes": {"RGB", "RGBA"},
        "opaque_corners": True,
    },
    {
        "name": "fashionrise-feature-graphic.png",
        "required": True,
        "size": (1024, 500),
        "max_bytes": 15 * 1024 * 1024,
        "modes": {"RGB"},  # fully opaque store requirement
        "opaque_corners": True,
    },
    {
        "name": "fashionrise-icon-1024.png",
        "required": False,
        "size": (1024, 1024),
        "max_bytes": 10 * 1024 * 1024,
        "modes": {"RGB", "RGBA"},
        "opaque_corners": False,
    },
    {
        "name": "fashionrise-logo-transparent.png",
        "required": False,
        "size": None,
        "max_bytes": 10 * 1024 * 1024,
        "modes": {"RGBA", "RGB"},
        "opaque_corners": False,
    },
]


def main() -> int:
    failed = 0
    for spec in CHECKS:
        path = HERE / spec["name"]
        if not path.exists():
            if spec["required"]:
                print(f"FAIL  missing required {spec['name']}")
                failed += 1
            else:
                print(f"SKIP  optional missing {spec['name']}")
            continue
        im = Image.open(path)
        nbytes = path.stat().st_size
        ok = True
        if spec["size"] and im.size != spec["size"]:
            print(f"FAIL  {spec['name']} size {im.size} != {spec['size']}")
            ok = False
        if nbytes > spec["max_bytes"]:
            print(f"FAIL  {spec['name']} {nbytes} bytes > {spec['max_bytes']}")
            ok = False
        if im.mode not in spec["modes"]:
            print(f"FAIL  {spec['name']} mode {im.mode} not in {spec['modes']}")
            ok = False
        if spec.get("opaque_corners") and im.mode == "RGB":
            w, h = im.size
            for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
                px = im.getpixel(xy)
                if isinstance(px, tuple) and len(px) == 4 and px[3] < 255:
                    print(f"FAIL  {spec['name']} transparent corner {xy}")
                    ok = False
        if ok:
            print(f"OK    {spec['name']} {im.size} {im.mode} {nbytes} bytes")
        else:
            failed += 1

    svg = HERE / "fashionrise-logo.svg"
    if svg.exists():
        print("NOTE  fashionrise-logo.svg present")
    else:
        print("NOTE  fashionrise-logo.svg omitted (no genuine vector source in repo)")

    if failed:
        print(f"VALIDATION_FAILED ({failed})")
        return 1
    print("VALIDATION_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
