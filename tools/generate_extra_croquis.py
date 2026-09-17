"""Generate extra kid-friendly fashion croquis (poses 06–08) into Resources/SketchReference."""
from __future__ import annotations

import base64
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from openai import OpenAI  # noqa: E402

DST = ROOT / "FashionRise" / "Assets" / "FashionRise" / "Resources" / "SketchReference"
W, H = 1024, 1536

POSES = {
    6: (
        "Arms",
        "standing fashion croquis, both arms raised slightly away from the body so a dress silhouette is easy to draw, "
        "front three-quarter view, head looking forward",
    ),
    7: (
        "Side",
        "standing fashion croquis in clear SIDE PROFILE facing left, arms relaxed, full body from head to feet, "
        "easy blank torso for clothing",
    ),
    8: (
        "Back",
        "standing fashion croquis BACK VIEW, head from behind, arms slightly away from sides, "
        "full body head to feet, blank back for drawing a dress or jacket",
    ),
}


def flatten(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    im.thumbnail((W, H), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    x = (W - im.width) // 2
    y = (H - im.height) // 2
    canvas.alpha_composite(im, (x, y))
    rgb = canvas.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.15)
    gray = rgb.convert("L")
    mask = gray.point(lambda v: 255 if v >= 210 else 0)
    white = Image.new("RGB", rgb.size, (255, 255, 255))
    return Image.composite(white, rgb, mask)


def prompt_for(gender: str, pose_desc: str) -> str:
    kid = "girl" if gender == "female" else "boy"
    return (
        f"Simple kid-friendly fashion design croquis of a {kid} figure for drawing clothes on top. "
        f"Pose: {pose_desc}. "
        "Very light gray pencil construction lines on pure white paper. "
        "Minimal face (dots for eyes, simple mouth), no hair detail beyond a simple outline, "
        "NO clothes, NO shoes styling — just a blank body mannequin with clear joints. "
        "Fashion proportions (slightly elongated legs), centered, full figure visible, "
        "easy for a child to draw a dress or outfit over. No text, no shading washes, no background."
    )


def main() -> None:
    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY missing in backend/.env")

    client = OpenAI(api_key=key, timeout=180)
    DST.mkdir(parents=True, exist_ok=True)

    for gender in ("female", "male"):
        for n, (_label, desc) in POSES.items():
            name = f"{gender}_{n:02d}.png"
            out_path = DST / name
            print(f"generating {name}…")
            result = client.images.generate(
                model="gpt-image-1",
                prompt=prompt_for(gender, desc),
                size="1024x1536",
                n=1,
            )
            b64 = result.data[0].b64_json
            if not b64:
                print("SKIP no b64", name)
                continue
            raw = base64.b64decode(b64)
            flat = flatten(Image.open(BytesIO(raw)))
            # Lighten lines so ink drawing pops on top
            flat = ImageOps.autocontrast(flat, cutoff=2)
            flat.save(out_path, optimize=True)
            print("saved", out_path, flat.size)

    print("done — reopen Unity so it imports new PNGs")


if __name__ == "__main__":
    main()
