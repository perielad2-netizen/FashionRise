"""Derive WEB-V2.2 brand variants from the approved FashionRise artwork.

Non-destructive: original files are read and never overwritten.
Outputs are transparent PNGs unless a PWA icon requires an opaque navy field.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "public"
LOGO = ROOT / "branding" / "fashion_rise_logo.png"
MARK = ROOT / "branding" / "fashion_rise_mark.png"
NAVY = (9, 15, 31, 255)


def erode_cream_fringe(im: Image.Image, passes: int = 2) -> Image.Image:
    """Remove the baked cream edge left by the original background knockout."""
    out = im.convert("RGBA")
    w, h = out.size
    for _ in range(passes):
        px = out.load()
        kill: list[tuple[int, int]] = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a < 250:
                    continue
                if abs(r - 248) + abs(g - 236) + abs(b - 238) > 48:
                    continue
                touches = False
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= w or ny >= h or px[nx, ny][3] < 16:
                        touches = True
                        break
                if touches:
                    kill.append((x, y))
        for x, y in kill:
            px[x, y] = (0, 0, 0, 0)
    return out


def remove_edge_dark(im: Image.Image, lum_max: int = 115) -> Image.Image:
    """Clear a dark matte that is connected to the image edge. Figure ink stays."""
    from collections import deque

    out = im.convert("RGBA").copy()
    px = out.load()
    w, h = out.size
    seen = bytearray(w * h)
    q: deque[tuple[int, int]] = deque()

    def is_bg(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        if a < 12:
            return True
        lum = (r + g + b) / 3
        chroma = max(r, g, b) - min(r, g, b)
        return lum < lum_max and chroma < 45

    for x in range(w):
        for y in (0, h - 1):
            if is_bg(x, y):
                seen[y * w + x] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            i = y * w + x
            if not seen[i] and is_bg(x, y):
                seen[i] = 1
                q.append((x, y))
    while q:
        x, y = q.popleft()
        if px[x, y][3] >= 12:
            px[x, y] = (0, 0, 0, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                i = ny * w + nx
                if not seen[i] and is_bg(nx, ny):
                    seen[i] = 1
                    q.append((nx, ny))
    return out


def strip_dark_fringe(im: Image.Image, alpha_max: int = 48, channel_max: int = 52) -> Image.Image:
    """Drop near-black, low-alpha residue. Leaves opaque figure ink untouched."""
    out = im.convert("RGBA")
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < alpha_max and r < channel_max and g < channel_max and b < channel_max + 8:
                px[x, y] = (0, 0, 0, 0)
    return out


def trim(im: Image.Image, pad: int = 0) -> Image.Image:
    bbox = im.getbbox()
    if not bbox:
        return im
    l, t, r, b = bbox
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(im.width, r + pad)
    b = min(im.height, b + pad)
    return im.crop((l, t, r, b))


def crop_rows(im: Image.Image, y0: int, y1: int) -> Image.Image:
    band = im.crop((0, y0, im.width, y1))
    return trim(band, 8)


def frame_figure(im: Image.Image, clear_edge_matte: bool = False) -> Image.Image:
    if clear_edge_matte:
        im = remove_edge_dark(im)
    im = trim(strip_dark_fringe(im), 0)
    side = 0.08
    top = 0.035
    bottom = 0.14
    cw = max(im.width, int(im.width / (1 - 2 * side)))
    ch = int(cw * 4 / 3)
    max_h = int(ch * (1 - top - bottom))
    max_w = int(cw * (1 - 2 * side))
    scale = min(max_w / im.width, max_h / im.height, 1)
    nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS) if scale < 0.999 else im
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    x = (cw - resized.width) // 2
    y = int(ch * top)
    canvas.paste(resized, (x, y), resized)
    return canvas


def frame_icon(im: Image.Image) -> Image.Image:
    im = trim(strip_dark_fringe(im), 2)
    cw, ch = 480, 640
    target = int(cw * 0.58)
    scale = target / max(im.width, im.height)
    nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    x = (cw - nw) // 2
    y = (ch - nh) // 2 - int(ch * 0.04)
    canvas.paste(resized, (x, y), resized)
    return canvas


def app_icon(mark: Image.Image, size: int) -> Image.Image:
    trimmed = trim(erode_cream_fringe(mark.convert("RGBA")), 2)
    canvas = Image.new("RGBA", (size, size), NAVY)
    # Keep the emblem inside the maskable safe zone.
    inner = int(size * 0.62)
    scale = inner / max(trimmed.width, trimmed.height)
    nw, nh = max(1, int(trimmed.width * scale)), max(1, int(trimmed.height * scale))
    emblem = trimmed.resize((nw, nh), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.paste(emblem, ((size - nw) // 2, (size - nh) // 2 - int(size * 0.02)), emblem)
    canvas.alpha_composite(layer)
    # PWA and favicon tiles are opaque navy. Partial edge pixels stay on that field.
    return canvas.convert("RGB").convert("RGBA")


def save_png(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="PNG", optimize=True)
    print(f"wrote {path.relative_to(ROOT)} {im.size} mode={im.mode}")


def main() -> None:
    logo = Image.open(LOGO).convert("RGBA")
    mark = Image.open(MARK).convert("RGBA")

    # Emblem block ends just before the wordmark (wordmark ink begins ~y844).
    emblem = erode_cream_fringe(crop_rows(logo, 100, 838))
    save_png(emblem, ROOT / "branding" / "fashion_rise_emblem.png")

    # Emblem + approved wordmark. Omits the tiny tagline and pill CTA.
    login = erode_cream_fringe(crop_rows(logo, 100, 976))
    if login.width > 960:
        login = login.resize((960, int(login.height * 960 / login.width)), Image.Resampling.LANCZOS)
    save_png(login, ROOT / "branding" / "fashion_rise_login.png")

    models = ROOT / "assets" / "ui" / "models"
    save_png(
        frame_figure(Image.open(models / "fr_model_female.png"), clear_edge_matte=True),
        models / "fr_model_female_card.png",
    )
    save_png(frame_figure(Image.open(models / "fr_model_male.png")), models / "fr_model_male_card.png")
    save_png(frame_icon(Image.open(models / "fr_model_custom.png")), models / "fr_model_custom_card.png")
    save_png(frame_icon(Image.open(models / "fr_model_blank.png")), models / "fr_model_blank_card.png")

    icons = ROOT / "icons"
    save_png(app_icon(mark, 32), icons / "favicon-32.png")
    save_png(app_icon(mark, 180), icons / "apple-touch-icon.png")
    save_png(app_icon(mark, 192), icons / "icon-192.png")
    # Square opaque tile. The emblem sits inside the maskable safe zone.
    save_png(app_icon(mark, 512), icons / "icon-512.png")


if __name__ == "__main__":
    main()
