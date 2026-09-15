from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps, ImageChops

SRC = Path(r"C:\Users\perie\.cursor\projects\d-projects-FashionRise\assets")
DST = Path(r"d:\projects\FashionRise\FashionRise\Assets\FashionRise\Resources\SketchReference")
W, H = 1024, 1536

MAPPING = {
    "female_pose_01_preview.png": "female_01.png",
    "female_02.png": "female_02.png",
    "female_03.png": "female_03.png",
    "female_04.png": "female_04.png",
    "female_05.png": "female_05.png",
    "male_01.png": "male_01.png",
    "male_02.png": "male_02.png",
    "male_03.png": "male_03.png",
    "male_04.png": "male_04.png",
    "male_05.png": "male_05.png",
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
    # Luminance threshold: anything bright enough becomes white
    gray = rgb.convert("L")
    # Keep dark lines; blast light areas to white
    mask = gray.point(lambda v: 255 if v >= 205 else 0)
    white = Image.new("RGB", rgb.size, (255, 255, 255))
    rgb = Image.composite(white, rgb, mask)
    return rgb


def main():
    DST.mkdir(parents=True, exist_ok=True)
    for sname, dname in MAPPING.items():
        p = SRC / sname
        if not p.exists():
            print("MISSING", sname)
            continue
        out = flatten(Image.open(p))
        out.save(DST / dname, optimize=True)
        print("saved", dname, out.size)
    Image.open(DST / "female_01.png").save(DST / "female_model.png", optimize=True)
    Image.open(DST / "male_01.png").save(DST / "male_model.png", optimize=True)
    print("updated legacy aliases")


if __name__ == "__main__":
    main()
