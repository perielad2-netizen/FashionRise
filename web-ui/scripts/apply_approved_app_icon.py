#!/usr/bin/env python3
"""Apply the PM-approved FashionRise app icon across small brand surfaces.

Uses the attached/approved 1024×1024 RGB artwork exactly — no redesign and no
AI background removal. Only the pale presentation matte outside the gold frame
is keyed so platform assets stay full-bleed and crisp.

Preserved (never written by this script):
  - public/branding/fashion_rise_logo.png   (full lockup)
  - public/branding/fashion_rise_login.png  (Home + login lockup)
  - public/branding/fashion_rise_emblem.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "branding-src" / "fashion_rise_app_icon_1024.png"
# Deep purple sampled from the approved icon field (not the pink ribbons).
FILL_RGB = (28, 16, 48)


def is_presentation_matte(r: int, g: int, b: int) -> bool:
    """True for the pale pink/cream canvas behind the gold squircle."""
    if r < 228 or g < 205 or b < 205:
        return False
    if r < g - 4:
        return False
    return abs(r - g) < 50 and abs(g - b) < 50 and abs(r - b) < 60


def matte_mask(rgb: Image.Image) -> Image.Image:
    """Alpha mask: 0 on presentation matte, 255 on approved artwork."""
    px = rgb.load()
    w, h = rgb.size
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            if not is_presentation_matte(*px[x, y]):
                mp[x, y] = 255
    return mask


def content_bbox(mask: Image.Image, pad: int = 2) -> tuple[int, int, int, int]:
    bbox = mask.getbbox()
    if not bbox:
        raise SystemExit("approved icon appears empty after matte key")
    l, t, r, b = bbox
    return (
        max(0, l - pad),
        max(0, t - pad),
        min(mask.width, r + pad),
        min(mask.height, b + pad),
    )


def opaque_square(rgb: Image.Image, mask: Image.Image, size: int = 1024) -> Image.Image:
    """Full-bleed opaque square for iOS / PWA / legacy Android launchers.

    Scales the gold-framed artwork to cover the square so Apple's mask does not
    leave a pale double-rounded ring. Corners outside the artwork stay FILL_RGB.
    """
    l, t, r, b = content_bbox(mask)
    cropped = rgb.crop((l, t, r, b))
    cropped_mask = mask.crop((l, t, r, b))
    cw, ch = cropped.size
    scale = max(size / cw, size / ch)
    nw, nh = max(1, int(round(cw * scale))), max(1, int(round(ch * scale)))
    resized = cropped.resize((nw, nh), Image.Resampling.LANCZOS).convert("RGBA")
    resized_mask = cropped_mask.resize((nw, nh), Image.Resampling.LANCZOS)
    resized.putalpha(resized_mask)
    layer = Image.new("RGBA", (nw, nh), (*FILL_RGB, 255))
    layer.alpha_composite(resized)
    left = (nw - size) // 2
    top = (nh - size) // 2
    return layer.crop((left, top, left + size, top + size)).convert("RGB")


def header_mark(rgb: Image.Image, mask: Image.Image, size: int = 512) -> Image.Image:
    """Transparent-corner mark for GlobalHeader / Privacy / design-lab."""
    l, t, r, b = content_bbox(mask, pad=4)
    cropped = rgb.crop((l, t, r, b)).convert("RGBA")
    cropped_mask = mask.crop((l, t, r, b))
    cropped.putalpha(cropped_mask)
    cw, ch = cropped.size
    side = max(cw, ch)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - cw) // 2, (side - ch) // 2), cropped)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def adaptive_foreground(rgb: Image.Image, mask: Image.Image, size: int) -> Image.Image:
    """Android adaptive foreground — icon inside ~66% safe zone, transparent pad."""
    mark = header_mark(rgb, mask, size=max(64, int(size * 0.72)))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(mark, ((size - mark.width) // 2, (size - mark.height) // 2), mark)
    return canvas


def save_rgb(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(path, format="PNG", optimize=True)
    print(f"wrote {path} {im.size} RGB")


def save_rgba(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGBA").save(path, format="PNG", optimize=True)
    print(f"wrote {path} {im.size} RGBA")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    args = ap.parse_args()
    src_path = args.src
    if not src_path.is_file():
        raise SystemExit(f"missing approved source: {src_path}")

    rgb = Image.open(src_path).convert("RGB")
    if rgb.size != (1024, 1024):
        raise SystemExit(f"approved source must be 1024x1024 RGB, got {rgb.size} {rgb.mode}")
    mask = matte_mask(rgb)

    master = opaque_square(rgb, mask, 1024)
    mark = header_mark(rgb, mask, 512)

    # Header / in-app mark (separate from Home lockup assets).
    save_rgba(mark, ROOT / "public" / "branding" / "fashion_rise_mark.png")

    # Capacitor iOS App Store icon — opaque RGB, fail-closed assert preserved.
    save_rgb(master, ROOT / "ios" / "App" / "App" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon-512@2x.png")

    # Favicon + PWA / Apple Touch (opaque full-bleed).
    icons = ROOT / "public" / "icons"
    for name, size in (
        ("favicon-32.png", 32),
        ("apple-touch-icon.png", 180),
        ("icon-192.png", 192),
        ("icon-512.png", 512),
    ):
        save_rgb(master.resize((size, size), Image.Resampling.LANCZOS), icons / name)

    # Android legacy + adaptive launchers.
    android_res = ROOT / "android" / "app" / "src" / "main" / "res"
    launcher_sizes = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    fg_sizes = {
        "mipmap-mdpi": 108,
        "mipmap-hdpi": 162,
        "mipmap-xhdpi": 216,
        "mipmap-xxhdpi": 324,
        "mipmap-xxxhdpi": 432,
    }
    for folder, size in launcher_sizes.items():
        tile = master.resize((size, size), Image.Resampling.LANCZOS)
        save_rgb(tile, android_res / folder / "ic_launcher.png")
        save_rgba(tile.convert("RGBA"), android_res / folder / "ic_launcher_round.png")
    for folder, size in fg_sizes.items():
        save_rgba(adaptive_foreground(rgb, mask, size), android_res / folder / "ic_launcher_foreground.png")

    bg_xml = android_res / "values" / "ic_launcher_background.xml"
    bg_xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        f'    <color name="ic_launcher_background">#{FILL_RGB[0]:02X}{FILL_RGB[1]:02X}{FILL_RGB[2]:02X}</color>\n'
        "</resources>\n",
        encoding="utf-8",
    )
    print(f"wrote {bg_xml}")

    # Replace unused Vite purple favicon.svg with a tiny PNG-backed note via raster
    # is awkward in SVG — write a 32px data-free stub pointer isn't needed; keep
    # index.html on favicon-32.png. Overwrite favicon.svg with a simple solid mark
    # reference PNG isn't SVG. Delete content risk — leave file but point docs.

    print("apply_approved_app_icon: ok")


if __name__ == "__main__":
    main()
