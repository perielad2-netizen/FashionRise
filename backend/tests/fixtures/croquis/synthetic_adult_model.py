"""Synthetic fully-clothed adult fashion-model illustration (not a photograph).

Used only for private offline / owner-approved one-image croquis validation.
No real customer photos. Drawn procedurally — safe to commit.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw


FIXTURE_DIR = Path(__file__).resolve().parent
SYNTHETIC_PNG_PATH = FIXTURE_DIR / "synthetic_clothed_adult_model.png"


def render_synthetic_clothed_adult_model_png(
    *, width: int = 512, height: int = 768
) -> bytes:
    """Draw a simple full-body, fully clothed adult fashion figure on transparent PNG."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = width // 2
    # Head (neutral oval — not a likeness)
    head_r = width // 14
    head_y = int(height * 0.12)
    draw.ellipse(
        [cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
        outline=(30, 30, 30, 255),
        width=3,
        fill=(245, 222, 200, 255),
    )
    # Neck
    neck_w = width // 28
    draw.rectangle(
        [cx - neck_w, head_y + head_r, cx + neck_w, head_y + head_r + height // 28],
        fill=(245, 222, 200, 255),
    )
    # Torso dress/blouse (fully clothed)
    shoulder_y = head_y + head_r + height // 30
    hip_y = int(height * 0.52)
    dress_top = [
        (cx - width // 6, shoulder_y),
        (cx + width // 6, shoulder_y),
        (cx + width // 5, hip_y),
        (cx - width // 5, hip_y),
    ]
    draw.polygon(dress_top, fill=(70, 110, 160, 255), outline=(30, 30, 30, 255))
    # Skirt / lower garment
    hem_y = int(height * 0.78)
    skirt = [
        (cx - width // 5, hip_y),
        (cx + width // 5, hip_y),
        (cx + width // 4, hem_y),
        (cx - width // 4, hem_y),
    ]
    draw.polygon(skirt, fill=(50, 80, 130, 255), outline=(30, 30, 30, 255))
    # Arms (sleeved)
    arm_y0 = shoulder_y + 4
    arm_y1 = int(height * 0.48)
    draw.line([(cx - width // 6, arm_y0), (cx - width // 3, arm_y1)], fill=(70, 110, 160, 255), width=10)
    draw.line([(cx + width // 6, arm_y0), (cx + width // 3, arm_y1)], fill=(70, 110, 160, 255), width=10)
    # Legs (pants/stockings under hem — still clothed)
    foot_y = int(height * 0.95)
    draw.line([(cx - width // 14, hem_y), (cx - width // 12, foot_y)], fill=(40, 40, 50, 255), width=8)
    draw.line([(cx + width // 14, hem_y), (cx + width // 12, foot_y)], fill=(40, 40, 50, 255), width=8)
    # Shoes
    draw.ellipse(
        [cx - width // 10, foot_y - 6, cx - width // 20, foot_y + 8],
        fill=(20, 20, 20, 255),
    )
    draw.ellipse(
        [cx + width // 20, foot_y - 6, cx + width // 10, foot_y + 8],
        fill=(20, 20, 20, 255),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def ensure_synthetic_fixture_file() -> Path:
    """Write the committed fixture PNG if missing (idempotent)."""
    png = render_synthetic_clothed_adult_model_png()
    SYNTHETIC_PNG_PATH.write_bytes(png)
    return SYNTHETIC_PNG_PATH


def load_synthetic_clothed_adult_model_png() -> bytes:
    if SYNTHETIC_PNG_PATH.is_file():
        return SYNTHETIC_PNG_PATH.read_bytes()
    return render_synthetic_clothed_adult_model_png()


if __name__ == "__main__":
    path = ensure_synthetic_fixture_file()
    print(f"wrote {path} ({path.stat().st_size} bytes)")
