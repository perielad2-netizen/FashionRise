"""Identity lock for Fitting Room Social try-on.

chatgpt-image-latest / gpt-image-2.6-sunburst do not expose input_fidelity, and
FashionRise does not send a native clothing mask for those models. Prompt-only
identity rules still allow face drift. This module restores original face/hair
pixels from the person photo onto the try-on result (registered + feathered),
then validates that the protected region matches the source.

Never logs image bytes or biometric embeddings.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

IDENTITY_PROMPT_VERSION = "fitting-room-identity-v1"

# Work size for registration / MAD (keep cheap and stable).
_WORK = (256, 384)

# Face/hair protect band as fractions of frame height (outdoor full-body crops).
_FACE_Y0 = 0.02
_FACE_Y1 = 0.34
_FACE_WIDTH = 0.42  # of frame width, centered on detected head column
_FEATHER_PX = 7

# After composite, protected-region mean abs luma delta must stay under this.
_MAX_FACE_LUMA_MAD = 6.0
# Before composite, above this ⇒ model rewrote the face (telemetry + gate input).
_FACE_DRIFT_LUMA_MAD = 14.0


def _open_rgb(png: bytes) -> Image.Image:
    with Image.open(io.BytesIO(png)) as im:
        if im.mode == "RGBA":
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            return bg
        return im.convert("RGB")


def _png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _is_skin_like(r: int, g: int, b: int) -> bool:
    if r < 70 or g < 30 or b < 15:
        return False
    if r <= g or r <= b:
        return False
    if abs(r - g) < 10:
        return False
    # Reject metallic gold / bronze props (common behind outdoor portraits).
    if b < 70 and g > 120 and (r - b) > 90:
        return False
    mx, mn = max(r, g, b), min(r, g, b)
    if (mx - mn) < 12:
        return False
    sat = (mx - mn) / float(mx or 1)
    if sat > 0.58 and r > 170 and g < 85:
        return False
    return True


def _head_center_x(rgb: Image.Image) -> float:
    """Estimate head column from skin-like pixels in the upper third.

    Search is limited to the central half of the frame so side sculptures / props
    cannot pull the protect ellipse off the face.
    """
    w, h = rgb.size
    y0, y1 = int(h * 0.04), int(h * 0.32)
    x0, x1 = int(w * 0.22), int(w * 0.78)
    step = max(1, w // 64)
    col_hits = [0] * w
    px = rgb.load()
    for y in range(y0, y1, max(1, (y1 - y0) // 48)):
        for x in range(x0, x1, step):
            r, g, b = px[x, y]
            if _is_skin_like(r, g, b):
                col_hits[x] += 1
    best_x, best = w // 2, -1
    win = max(3, w // 16)
    for x in range(max(win, x0), min(w - win, x1)):
        s = sum(col_hits[x - win : x + win + 1])
        if s > best:
            best, best_x = s, x
    if best <= 0:
        return 0.5
    return best_x / float(w)


def build_face_hair_protect_mask(rgb: Image.Image) -> Image.Image:
    """Soft L mask (0–255) covering face + hair; garment torso stays editable."""
    w, h = rgb.size
    cx = _head_center_x(rgb)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    x0 = int((cx - _FACE_WIDTH / 2.0) * w)
    x1 = int((cx + _FACE_WIDTH / 2.0) * w)
    y0 = int(_FACE_Y0 * h)
    y1 = int(_FACE_Y1 * h)
    x0, x1 = max(0, x0), min(w, x1)
    y0, y1 = max(0, y0), min(h, y1)
    # Ellipse covers face + voluminous curly hair better than a box.
    draw.ellipse((x0, y0, x1, y1), fill=255)
    # Slight downward neck wedge — still above typical bodice.
    neck_y1 = min(h, int(y1 + 0.04 * h))
    nx0 = int(cx * w - 0.08 * w)
    nx1 = int(cx * w + 0.08 * w)
    draw.rectangle((nx0, y1 - 2, nx1, neck_y1), fill=255)
    return mask.filter(ImageFilter.GaussianBlur(_FEATHER_PX))


def _register_person_onto_result(
    result: Image.Image, person: Image.Image
) -> tuple[Image.Image, dict[str, Any]]:
    """Warp person to result frame using look_color_lock registration."""
    from app.services.look_color_lock import _IDENTITY_FRAME, _register_person_frame, _warp_frame

    rw, rh = result.size
    person_fit = person.resize((rw, rh), Image.Resampling.LANCZOS)
    work_r = result.resize(_WORK, Image.Resampling.BILINEAR)
    work_p = person_fit.resize(_WORK, Image.Resampling.BILINEAR)
    frame, reg = _register_person_frame(work_r, work_p)
    meta = dict(reg) if isinstance(reg, dict) else {"registered": False}
    meta["frame"] = list(frame) if frame != _IDENTITY_FRAME else [1.0, 1.0, 0.0, 0.0]
    if frame != _IDENTITY_FRAME:
        # Apply the same affine at full result resolution.
        warped = _warp_frame(person_fit, frame)
    else:
        warped = person_fit
    return warped, meta


def measure_face_luma_mad(
    result_rgb: Image.Image,
    person_aligned: Image.Image,
    protect: Image.Image,
) -> float:
    """Mean abs luma delta inside protect mask (protect > 128)."""
    ry, _, _ = result_rgb.convert("YCbCr").split()
    py, _, _ = person_aligned.convert("YCbCr").split()
    diff = ImageChops.difference(ry, py)
    # Weight by protect strength.
    w, h = diff.size
    dp = diff.load()
    mp = protect.load()
    total = 0.0
    weight = 0.0
    step = max(1, w // 128)
    for y in range(0, h, step):
        for x in range(0, w, step):
            m = mp[x, y]
            if m < 32:
                continue
            total += dp[x, y] * (m / 255.0)
            weight += m / 255.0
    if weight < 1e-3:
        return 255.0
    return total / weight


def composite_identity_from_person(
    result_png: bytes,
    person_png: bytes,
) -> tuple[bytes, dict[str, Any]]:
    """Paste original face/hair pixels onto the try-on result (feathered).

    Returns (png, meta). Meta never includes image bytes.
    """
    result = _open_rgb(result_png)
    person = _open_rgb(person_png)
    aligned, reg = _register_person_onto_result(result, person)
    protect = build_face_hair_protect_mask(aligned)
    # Ensure protect matches result size.
    if protect.size != result.size:
        protect = protect.resize(result.size, Image.Resampling.BILINEAR)

    mad_before = measure_face_luma_mad(result, aligned, protect)
    # Composite: where protect is strong, keep person pixels.
    locked = Image.composite(aligned, result, protect)
    mad_after = measure_face_luma_mad(locked, aligned, protect)

    meta: dict[str, Any] = {
        "strategy": "face_hair_pixel_composite",
        "prompt_version": IDENTITY_PROMPT_VERSION,
        "registration": {
            "registered": bool(reg.get("registered")),
            "frame": reg.get("frame"),
            "mismatch_before": reg.get("mismatch_before"),
            "mismatch_after": reg.get("mismatch_after"),
        },
        "face_luma_mad_before": round(mad_before, 2),
        "face_luma_mad_after": round(mad_after, 2),
        "face_drift_detected": mad_before >= _FACE_DRIFT_LUMA_MAD,
        "applied": True,
    }
    return _png_bytes(locked), meta


def validate_identity_lock(
    result_png: bytes,
    person_png: bytes,
    *,
    composite_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hard gate: protected face region must match the person photo.

    ``ok=False`` ⇒ do not deliver as a successful try-on.
    """
    result = _open_rgb(result_png)
    person = _open_rgb(person_png)
    aligned, reg = _register_person_onto_result(result, person)
    protect = build_face_hair_protect_mask(aligned)
    if protect.size != result.size:
        protect = protect.resize(result.size, Image.Resampling.BILINEAR)
    mad = measure_face_luma_mad(result, aligned, protect)
    ok = mad <= _MAX_FACE_LUMA_MAD
    # If frames are wildly misaligned, do not claim identity success.
    if not reg.get("registered") and mad > _MAX_FACE_LUMA_MAD * 2:
        ok = False
        reason = "unaligned_high_face_delta"
    elif not ok:
        reason = "face_pixels_differ"
    else:
        reason = "ok"
    out: dict[str, Any] = {
        "ok": ok,
        "reason": reason,
        "face_luma_mad": round(mad, 2),
        "threshold": _MAX_FACE_LUMA_MAD,
        "registration_registered": bool(reg.get("registered")),
        "prompt_version": IDENTITY_PROMPT_VERSION,
    }
    if isinstance(composite_meta, dict):
        out["composite"] = {
            k: composite_meta.get(k)
            for k in (
                "strategy",
                "face_luma_mad_before",
                "face_luma_mad_after",
                "face_drift_detected",
                "applied",
            )
        }
    return out
