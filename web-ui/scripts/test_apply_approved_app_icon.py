#!/usr/bin/env python3
"""Offline quality checks for exterior flood-fill app-icon masking."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "branding-src" / "fashion_rise_app_icon_1024.png"
MARK = ROOT / "public" / "branding" / "fashion_rise_mark.png"
IOS = ROOT / "ios" / "App" / "App" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon-512@2x.png"
LOGIN = ROOT / "public" / "branding" / "fashion_rise_login.png"
LOGO = ROOT / "public" / "branding" / "fashion_rise_logo.png"


def _load_mod():
    path = ROOT / "scripts" / "apply_approved_app_icon.py"
    spec = importlib.util.spec_from_file_location("apply_approved_app_icon", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    mod = _load_mod()
    rgb = Image.open(SRC).convert("RGB")
    mask = mod.exterior_matte_mask(rgb)
    # Exterior corners transparent in mask.
    assert mask.getpixel((0, 0)) == 0
    assert mask.getpixel((1023, 1023)) == 0
    # Center artwork opaque in mask.
    assert mask.getpixel((512, 512)) == 255
    # Interior pale pixels survive.
    pale_kept = 0
    px = rgb.load()
    mp = mask.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            if mp[x, y] and mod.is_presentation_matte(*px[x, y]):
                pale_kept += 1
    assert pale_kept > 1000, pale_kept

    master = Image.open(IOS)
    assert master.size == (1024, 1024) and master.mode == "RGB"
    assert master.getpixel((0, 0)) == mod.FILL_RGB

    mark = Image.open(MARK).convert("RGBA")
    assert mark.getpixel((0, 0))[3] == 0

    # Home / full lockup must remain present and distinct from mark bytes.
    assert LOGIN.is_file() and LOGO.is_file()
    assert LOGIN.read_bytes() != MARK.read_bytes()
    print("test_apply_approved_app_icon: ok")


if __name__ == "__main__":
    main()
