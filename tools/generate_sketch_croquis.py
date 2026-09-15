#!/usr/bin/env python3
"""Generate FashionRise sketch croquis (5 female + 5 male) as clean line-art PNGs."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 1024, 1536
INK = (48, 46, 44, 255)
INK_SOFT = (90, 86, 82, 255)
WHITE = (255, 255, 255, 255)
OUT = Path(r"d:\projects\FashionRise\FashionRise\Assets\FashionRise\Resources\SketchReference")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def draw_thick_line(draw: ImageDraw.ImageDraw, a, b, width, fill=INK):
    draw.line([a, b], fill=fill, width=max(1, int(width)), joint="curve")
    r = max(1, int(width * 0.55))
    for p in (a, b):
        draw.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=fill)


def draw_joint(draw, p, r, fill=INK):
    x, y = p
    draw.ellipse((x - r, y - r, x + r, y + r), outline=fill, width=max(2, r // 3))


def draw_head(draw, cx, cy, r, tilt_deg=0.0):
    # oval head
    draw.ellipse((cx - r * 0.85, cy - r, cx + r * 0.85, cy + r), outline=INK, width=3)
    rad = math.radians(tilt_deg)
    # crosshair
    dx = math.sin(rad) * r * 0.75
    dy = math.cos(rad) * r * 0.75
    draw_thick_line(draw, (cx - dx, cy + dy * 0.15), (cx + dx, cy - dy * 0.15), 2, INK_SOFT)
    draw_thick_line(draw, (cx, cy - r * 0.55), (cx, cy + r * 0.55), 2, INK_SOFT)


def lerp(a, b, t):
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def draw_limb(draw, joints, width):
    for i in range(len(joints) - 1):
        draw_thick_line(draw, joints[i], joints[i + 1], width)
    for j in joints[1:-1]:
        draw_joint(draw, j, max(4, int(width * 0.9)))


def draw_torso_block(draw, shoulder_l, shoulder_r, hip_l, hip_r):
    pts = [shoulder_l, shoulder_r, hip_r, hip_l]
    draw.line(pts + [pts[0]], fill=INK, width=3)
    # center guide
    mid_s = lerp(shoulder_l, shoulder_r, 0.5)
    mid_h = lerp(hip_l, hip_r, 0.5)
    draw_thick_line(draw, mid_s, mid_h, 2, INK_SOFT)
    waist = lerp(mid_s, mid_h, 0.45)
    wl = (waist[0] - abs(hip_r[0] - hip_l[0]) * 0.22, waist[1])
    wr = (waist[0] + abs(hip_r[0] - hip_l[0]) * 0.22, waist[1])
    draw_thick_line(draw, wl, wr, 2, INK_SOFT)


def render(pose_name: str, gender: str, joints: dict) -> Image.Image:
    img = Image.new("RGBA", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    head_r = joints["head_r"]
    draw_head(draw, *joints["head"], head_r, joints.get("tilt", 0.0))

    # neck
    draw_thick_line(draw, joints["neck"], joints["head"], 4 if gender == "male" else 3)

    draw_torso_block(draw, joints["sh_l"], joints["sh_r"], joints["hip_l"], joints["hip_r"])
    draw_joint(draw, joints["sh_l"], 7)
    draw_joint(draw, joints["sh_r"], 7)
    draw_joint(draw, joints["hip_l"], 6)
    draw_joint(draw, joints["hip_r"], 6)

    arm_w = 7 if gender == "male" else 6
    leg_w = 8 if gender == "male" else 7
    draw_limb(draw, [joints["sh_l"], joints["el_l"], joints["wr_l"]], arm_w)
    draw_limb(draw, [joints["sh_r"], joints["el_r"], joints["wr_r"]], arm_w)
    draw_limb(draw, [joints["hip_l"], joints["kn_l"], joints["an_l"]], leg_w)
    draw_limb(draw, [joints["hip_r"], joints["kn_r"], joints["an_r"]], leg_w)

    # feet hints
    for an, side in ((joints["an_l"], -1), (joints["an_r"], 1)):
        tip = (an[0] + side * 18, an[1] + 6)
        draw_thick_line(draw, an, tip, 4)

    # ground line
    y = max(joints["an_l"][1], joints["an_r"][1]) + 18
    draw_thick_line(draw, (W * 0.22, y), (W * 0.78, y), 2, INK_SOFT)

    return img.convert("RGB")


def base_female():
    cx = W * 0.5
    return {
        "head": (cx, H * 0.13),
        "head_r": 48,
        "tilt": 0.0,
        "neck": (cx, H * 0.185),
        "sh_l": (cx - 78, H * 0.23),
        "sh_r": (cx + 78, H * 0.23),
        "hip_l": (cx - 70, H * 0.42),
        "hip_r": (cx + 70, H * 0.42),
        "el_l": (cx - 120, H * 0.34),
        "el_r": (cx + 120, H * 0.34),
        "wr_l": (cx - 95, H * 0.44),
        "wr_r": (cx + 95, H * 0.44),
        "kn_l": (cx - 62, H * 0.62),
        "kn_r": (cx + 62, H * 0.62),
        "an_l": (cx - 58, H * 0.86),
        "an_r": (cx + 58, H * 0.86),
    }


def base_male():
    cx = W * 0.5
    return {
        "head": (cx, H * 0.125),
        "head_r": 50,
        "tilt": 0.0,
        "neck": (cx, H * 0.18),
        "sh_l": (cx - 105, H * 0.225),
        "sh_r": (cx + 105, H * 0.225),
        "hip_l": (cx - 62, H * 0.40),
        "hip_r": (cx + 62, H * 0.40),
        "el_l": (cx - 120, H * 0.33),
        "el_r": (cx + 120, H * 0.33),
        "wr_l": (cx - 115, H * 0.45),
        "wr_r": (cx + 115, H * 0.45),
        "kn_l": (cx - 58, H * 0.60),
        "kn_r": (cx + 58, H * 0.60),
        "an_l": (cx - 55, H * 0.86),
        "an_r": (cx + 55, H * 0.86),
    }


def female_poses():
    poses = []

    # 1 classic hands on hips
    j = base_female()
    j.update(
        {
            "tilt": -6,
            "el_l": (W * 0.5 - 130, H * 0.33),
            "el_r": (W * 0.5 + 130, H * 0.33),
            "wr_l": (W * 0.5 - 78, H * 0.41),
            "wr_r": (W * 0.5 + 78, H * 0.41),
            "hip_l": (W * 0.5 - 82, H * 0.42),
            "hip_r": (W * 0.5 + 62, H * 0.415),
            "kn_l": (W * 0.5 - 70, H * 0.63),
            "kn_r": (W * 0.5 + 50, H * 0.61),
            "an_l": (W * 0.5 - 66, H * 0.86),
            "an_r": (W * 0.5 + 42, H * 0.86),
        }
    )
    poses.append(("01", "hands_hips", j))

    # 2 walking / strut
    j = base_female()
    j.update(
        {
            "tilt": 4,
            "sh_l": (W * 0.5 - 70, H * 0.23),
            "sh_r": (W * 0.5 + 86, H * 0.225),
            "el_l": (W * 0.5 - 40, H * 0.34),
            "wr_l": (W * 0.5 - 10, H * 0.42),
            "el_r": (W * 0.5 + 150, H * 0.35),
            "wr_r": (W * 0.5 + 175, H * 0.46),
            "hip_l": (W * 0.5 - 55, H * 0.42),
            "hip_r": (W * 0.5 + 75, H * 0.415),
            "kn_l": (W * 0.5 - 20, H * 0.60),
            "an_l": (W * 0.5 + 10, H * 0.84),
            "kn_r": (W * 0.5 + 95, H * 0.62),
            "an_r": (W * 0.5 + 120, H * 0.87),
        }
    )
    poses.append(("02", "walk", j))

    # 3 arms gently out
    j = base_female()
    j.update(
        {
            "el_l": (W * 0.5 - 160, H * 0.30),
            "wr_l": (W * 0.5 - 210, H * 0.38),
            "el_r": (W * 0.5 + 160, H * 0.30),
            "wr_r": (W * 0.5 + 210, H * 0.38),
            "hip_l": (W * 0.5 - 68, H * 0.42),
            "hip_r": (W * 0.5 + 68, H * 0.42),
        }
    )
    poses.append(("03", "arms_out", j))

    # 4 weight on one hip, one arm raised
    j = base_female()
    j.update(
        {
            "tilt": 8,
            "head": (W * 0.52, H * 0.125),
            "neck": (W * 0.51, H * 0.18),
            "sh_l": (W * 0.5 - 70, H * 0.235),
            "sh_r": (W * 0.5 + 90, H * 0.22),
            "el_l": (W * 0.5 - 40, H * 0.16),
            "wr_l": (W * 0.5 - 5, H * 0.09),
            "el_r": (W * 0.5 + 135, H * 0.34),
            "wr_r": (W * 0.5 + 95, H * 0.43),
            "hip_l": (W * 0.5 - 55, H * 0.425),
            "hip_r": (W * 0.5 + 90, H * 0.41),
            "kn_l": (W * 0.5 - 48, H * 0.63),
            "an_l": (W * 0.5 - 45, H * 0.86),
            "kn_r": (W * 0.5 + 100, H * 0.60),
            "an_r": (W * 0.5 + 70, H * 0.86),
        }
    )
    poses.append(("04", "arm_up", j))

    # 5 three-quarter lean
    j = base_female()
    j.update(
        {
            "tilt": -10,
            "head": (W * 0.54, H * 0.13),
            "neck": (W * 0.53, H * 0.185),
            "sh_l": (W * 0.5 - 40, H * 0.235),
            "sh_r": (W * 0.5 + 105, H * 0.22),
            "el_l": (W * 0.5 - 95, H * 0.33),
            "wr_l": (W * 0.5 - 70, H * 0.43),
            "el_r": (W * 0.5 + 145, H * 0.32),
            "wr_r": (W * 0.5 + 120, H * 0.42),
            "hip_l": (W * 0.5 - 30, H * 0.425),
            "hip_r": (W * 0.5 + 95, H * 0.41),
            "kn_l": (W * 0.5 - 15, H * 0.62),
            "an_l": (W * 0.5 - 5, H * 0.86),
            "kn_r": (W * 0.5 + 110, H * 0.61),
            "an_r": (W * 0.5 + 125, H * 0.855),
        }
    )
    poses.append(("05", "three_quarter", j))
    return poses


def male_poses():
    poses = []

    # 1 neutral stand
    j = base_male()
    poses.append(("01", "stand", j))

    # 2 arms crossed
    j = base_male()
    j.update(
        {
            "el_l": (W * 0.5 + 20, H * 0.30),
            "wr_l": (W * 0.5 + 70, H * 0.305),
            "el_r": (W * 0.5 - 20, H * 0.31),
            "wr_r": (W * 0.5 - 70, H * 0.315),
        }
    )
    poses.append(("02", "arms_crossed", j))

    # 3 walking
    j = base_male()
    j.update(
        {
            "tilt": 3,
            "sh_l": (W * 0.5 - 95, H * 0.23),
            "sh_r": (W * 0.5 + 110, H * 0.22),
            "el_l": (W * 0.5 - 50, H * 0.34),
            "wr_l": (W * 0.5 - 15, H * 0.44),
            "el_r": (W * 0.5 + 155, H * 0.34),
            "wr_r": (W * 0.5 + 175, H * 0.46),
            "hip_l": (W * 0.5 - 50, H * 0.40),
            "hip_r": (W * 0.5 + 70, H * 0.395),
            "kn_l": (W * 0.5 - 10, H * 0.58),
            "an_l": (W * 0.5 + 25, H * 0.84),
            "kn_r": (W * 0.5 + 95, H * 0.61),
            "an_r": (W * 0.5 + 115, H * 0.87),
        }
    )
    poses.append(("03", "walk", j))

    # 4 hand on hip
    j = base_male()
    j.update(
        {
            "el_l": (W * 0.5 - 140, H * 0.32),
            "wr_l": (W * 0.5 - 70, H * 0.40),
            "el_r": (W * 0.5 + 125, H * 0.34),
            "wr_r": (W * 0.5 + 120, H * 0.46),
            "hip_l": (W * 0.5 - 75, H * 0.405),
            "hip_r": (W * 0.5 + 55, H * 0.40),
            "kn_l": (W * 0.5 - 80, H * 0.61),
            "an_l": (W * 0.5 - 85, H * 0.86),
            "kn_r": (W * 0.5 + 45, H * 0.60),
            "an_r": (W * 0.5 + 40, H * 0.86),
        }
    )
    poses.append(("04", "hand_hip", j))

    # 5 athletic / ready
    j = base_male()
    j.update(
        {
            "tilt": -4,
            "sh_l": (W * 0.5 - 115, H * 0.235),
            "sh_r": (W * 0.5 + 115, H * 0.235),
            "el_l": (W * 0.5 - 170, H * 0.34),
            "wr_l": (W * 0.5 - 195, H * 0.45),
            "el_r": (W * 0.5 + 170, H * 0.34),
            "wr_r": (W * 0.5 + 195, H * 0.45),
            "hip_l": (W * 0.5 - 70, H * 0.405),
            "hip_r": (W * 0.5 + 70, H * 0.405),
            "kn_l": (W * 0.5 - 95, H * 0.60),
            "an_l": (W * 0.5 - 110, H * 0.85),
            "kn_r": (W * 0.5 + 95, H * 0.60),
            "an_r": (W * 0.5 + 110, H * 0.85),
        }
    )
    poses.append(("05", "athletic", j))
    return poses


def write_meta(png_path: Path, guid: str):
    meta = png_path.with_suffix(".png.meta")
    if meta.exists():
        return
    meta.write_text(
        f"""fileFormatVersion: 2
guid: {guid}
TextureImporter:
  internalIDToNameTable: []
  externalObjects: {{}}
  serializedVersion: 12
  mipmaps:
    mipMapMode: 0
    enableMipMap: 0
    sRGBTexture: 1
    linearTexture: 0
    fadeOut: 0
    borderMipMap: 0
    mipMapsPreserveCoverage: 0
    alphaTestReferenceValue: 0.5
    mipMapFadeDistanceStart: 1
    mipMapFadeDistanceEnd: 3
  bumpmap:
    convertToNormalMap: 0
    externalNormalMap: 0
    heightScale: 0.25
    normalMapFilter: 0
  isReadable: 0
  streamingMipmaps: 0
  streamingMipmapsPriority: 0
  vTOnly: 0
  grayScaleToAlpha: 0
  generateCubemap: 6
  cubemapConvolution: 0
  seamlessCubemap: 0
  textureFormat: 1
  maxTextureSize: 8192
  textureSettings:
    serializedVersion: 2
    filterMode: 1
    aniso: 1
    mipBias: 0
    wrapU: 0
    wrapV: 0
    wrapW: 0
  nPOTScale: 1
  lightmap: 0
  compressionQuality: 50
  spriteMode: 0
  spriteExtrude: 1
  spriteMeshType: 1
  alignment: 0
  spritePivot: {{x: 0.5, y: 0.5}}
  spritePixelsToUnits: 100
  spriteBorder: {{x: 0, y: 0, z: 0, w: 0}}
  spriteGenerateFallbackPhysicsShape: 0
  alphaUsage: 1
  alphaIsTransparency: 1
  spriteTessellationDetail: -1
  textureType: 0
  textureShape: 1
  singleChannelComponent: 0
  flipbookRows: 1
  flipbookColumns: 1
  maxTextureSizeSet: 0
  compressionQualitySet: 0
  textureFormatSet: 0
  ignorePngGamma: 0
  applyGammaDecoding: 0
  platformSettings:
  - serializedVersion: 3
    buildTarget: DefaultTexturePlatform
    maxTextureSize: 8192
    resizeAlgorithm: 0
    textureFormat: -1
    textureCompression: 0
    compressionQuality: 50
    crunchedCompression: 0
    allowsAlphaSplitting: 0
    overridden: 0
    androidETC2FallbackOverride: 0
    forceMaximumCompressionQuality_BC6H_BC7: 0
  spriteSheet:
    serializedVersion: 2
    sprites: []
    outline: []
    physicsShape: []
    bones: []
    spriteID: 
    internalID: 0
    vertices: []
    indices: 
    edges: []
    weights: []
    secondaryTextures: []
    nameFileIdTable: {{}}
  pSDRemoveMatte: 0
  userData: 
  assetBundleName: 
  assetBundleVariant: 
""",
        encoding="utf-8",
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    guids = {
        ("female", "01"): "a1b2c3d4e5f64789a0b1c2d3e4f50601",
        ("female", "02"): "a1b2c3d4e5f64789a0b1c2d3e4f50602",
        ("female", "03"): "a1b2c3d4e5f64789a0b1c2d3e4f50603",
        ("female", "04"): "a1b2c3d4e5f64789a0b1c2d3e4f50604",
        ("female", "05"): "a1b2c3d4e5f64789a0b1c2d3e4f50605",
        ("male", "01"): "b1b2c3d4e5f64789a0b1c2d3e4f50601",
        ("male", "02"): "b1b2c3d4e5f64789a0b1c2d3e4f50602",
        ("male", "03"): "b1b2c3d4e5f64789a0b1c2d3e4f50603",
        ("male", "04"): "b1b2c3d4e5f64789a0b1c2d3e4f50604",
        ("male", "05"): "b1b2c3d4e5f64789a0b1c2d3e4f50605",
    }

    for gender, poses in (("female", female_poses()), ("male", male_poses())):
        for num, name, joints in poses:
            img = render(name, gender, joints)
            path = OUT / f"{gender}_{num}.png"
            img.save(path, optimize=True)
            write_meta(path, guids[(gender, num)])
            print("wrote", path.name, name)

    # Keep legacy names pointing at pose 01 for older callers
    for gender in ("female", "male"):
        src = OUT / f"{gender}_01.png"
        dst = OUT / f"{gender}_model.png"
        Image.open(src).save(dst, optimize=True)
        print("updated", dst.name)


if __name__ == "__main__":
    main()
