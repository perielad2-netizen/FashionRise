"""Generate professional fashion croquis poses into Resources/SketchReference.

Replaces kid-style blank figures with adult fashion-illustration mannequins
(elongated proportions, clean construction lines, no clothes) for serious designers.

Usage (from repo root, with OPENAI_API_KEY in backend/.env):
  python tools/generate_pro_croquis.py
  python tools/generate_pro_croquis.py --only 09,10,11,12   # extra poses
"""
from __future__ import annotations

import argparse
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

# Core 8 — regenerate for professional look
CORE_POSES = {
    1: ("Front", "classic front standing fashion croquis, weight on one leg, arms relaxed at sides"),
    2: ("Walk", "fashion walk pose, one leg stepping forward, slight contrapposto, arms natural"),
    3: ("Runway", "dramatic runway pose, hand on hip, elongated legs, confident stance"),
    4: ("Hand on hip", "both hands near hips / one hand on hip, elbows out, fashion editorial stance"),
    5: ("Three-quarter", "three-quarter turned body, head looking toward viewer, elegant S-curve"),
    6: ("Arms out", "arms slightly away from torso so sleeves and jackets are easy to draw"),
    7: ("Profile", "clear side profile facing left, full body head to feet, blank silhouette"),
    8: ("Back", "back view fashion croquis, head from behind, arms slightly away from sides"),
}

# Extra poses (09+) — add when user wants more variety
EXTRA_POSES = {
    9: ("Contrapposto", "strong contrapposto, weight on right leg, left knee soft, arms asymmetric"),
    10: ("Seated", "fashion seated pose on invisible stool, legs crossed at ankle, torso upright"),
    11: ("Over shoulder", "body three-quarter back, head looking over shoulder toward viewer"),
    12: ("High kick walk", "dynamic fashion step with higher knee, arms swinging lightly"),
}


def flatten(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    im.thumbnail((W, H), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    x = (W - im.width) // 2
    y = (H - im.height) // 2
    canvas.alpha_composite(im, (x, y))
    rgb = canvas.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.2)
    gray = rgb.convert("L")
    mask = gray.point(lambda v: 255 if v >= 208 else 0)
    white = Image.new("RGB", rgb.size, (255, 255, 255))
    return Image.composite(white, rgb, mask)


def prompt_for(gender: str, pose_desc: str) -> str:
    who = "adult female" if gender == "female" else "adult male"
    return (
        f"Professional fashion design croquis of an {who} figure for drawing clothes on top. "
        f"Pose: {pose_desc}. "
        "Clean light graphite pencil construction lines on pure white paper. "
        "9-heads fashion proportions, elongated elegant legs, minimal face (no detailed features), "
        "NO clothes, NO shoes styling, NO hair texture — blank body mannequin with clear joints and center line. "
        "Centered, full figure visible head to toe, easy to sketch a gown or suit over. "
        "No text, no heavy shading, no background, no cartoon kid style."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help="Comma list of pose numbers, e.g. 1,2,9,10")
    parser.add_argument("--gender", default="both", choices=("female", "male", "both"))
    args = parser.parse_args()

    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise SystemExit("OPENAI_API_KEY missing in backend/.env")

    poses = {**CORE_POSES, **EXTRA_POSES}
    if args.only.strip():
        wanted = {int(x.strip()) for x in args.only.split(",") if x.strip()}
        poses = {k: v for k, v in poses.items() if k in wanted}
        if not poses:
            raise SystemExit("No matching pose numbers")

    genders = ("female", "male") if args.gender == "both" else (args.gender,)
    client = OpenAI(api_key=key, timeout=180)
    DST.mkdir(parents=True, exist_ok=True)

    for gender in genders:
        for n, (_label, desc) in sorted(poses.items()):
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
            flat = flatten(Image.open(BytesIO(base64.b64decode(b64))))
            flat = ImageOps.autocontrast(flat, cutoff=2)
            flat.save(out_path, optimize=True)
            print("saved", out_path, flat.size)
            # Keep legacy aliases for pose 1
            if n == 1:
                alias = DST / f"{gender}_model.png"
                flat.save(alias, optimize=True)
                print("saved", alias)

    print("done — reopen Unity so it imports new PNGs")
    print("If you add poses 09–12, bump PoseCount + PoseLabels in SketchFigurePreferences.cs")


if __name__ == "__main__":
    main()
