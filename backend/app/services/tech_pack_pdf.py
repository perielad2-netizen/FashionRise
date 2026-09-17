"""Two-page FashionRise tech pack PDF (technical spec + pattern/cutting sheet)."""

from __future__ import annotations

import io
import logging
from typing import Any

import httpx
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.storage.local import LocalStorageBackend, is_loopback_url

logger = logging.getLogger(__name__)

INK = colors.HexColor("#2A2420")
RULE = colors.HexColor("#C9BBA8")
BAND = colors.HexColor("#EDE4D6")
PAPER = colors.HexColor("#F7F1E8")
MUTED = colors.HexColor("#6B6258")

DISCLAIMER = "AI first production draft — not guaranteed final manufacturing measurements."


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "FrTitle",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=16,
            leading=19,
            textColor=INK,
            alignment=TA_CENTER,
            spaceAfter=2,
            tracking=1.4,
        ),
        "kicker": ParagraphStyle(
            "FrKicker",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "h": ParagraphStyle(
            "FrH",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=9,
            leading=11,
            textColor=INK,
            alignment=TA_CENTER,
            spaceBefore=6,
            spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "FrMeta",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            leading=11,
            textColor=INK,
        ),
        "cell": ParagraphStyle(
            "FrCell",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "cellb": ParagraphStyle(
            "FrCellB",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "note": ParagraphStyle(
            "FrNote",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=7.5,
            leading=10,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        "foot": ParagraphStyle(
            "FrFoot",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=7,
            textColor=MUTED,
            alignment=TA_LEFT,
        ),
        "caption": ParagraphStyle(
            "FrCap",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=7,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=2,
        ),
        "right": ParagraphStyle(
            "FrRight",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            leading=11,
            textColor=INK,
            alignment=TA_RIGHT,
        ),
    }


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    raw = "" if text is None else str(text)
    raw = (
        raw.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return Paragraph(raw or "—", style)


def _table(data: list[list], col_widths: list[float], header: bool = True) -> Table:
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
        ("BACKGROUND", (0, 0), (-1, 0), BAND) if header else ("BACKGROUND", (0, 0), (-1, 0), PAPER),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold") if header else ("FONTNAME", (0, 0), (-1, 0), "Times-Roman"),
    ]
    t.setStyle(TableStyle(cmds))
    return t


def _kv_table(pairs: list[tuple[str, str]], col_w: list[float], s: dict[str, ParagraphStyle]) -> Table:
    rows = [[_p(k, s["cellb"]), _p(v, s["cell"])] for k, v in pairs if str(v).strip()]
    if not rows:
        rows = [[_p("—", s["cell"]), _p("", s["cell"])]]
    return _table(rows, col_w, header=False)


def _fmt_cm(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value):g} cm"
    except (TypeError, ValueError):
        text = str(value).strip()
        return text if text.endswith("cm") else f"{text} cm"


def _qty(item: dict[str, Any]) -> str:
    q = item.get("quantity_m")
    if q is None or q == "":
        return "1 pc"
    try:
        return f"{float(q):g} m"
    except (TypeError, ValueError):
        return str(q)


def _fetch_png(url: str | None) -> bytes | None:
    if not url or not str(url).strip():
        return None
    raw = str(url).strip()
    local = LocalStorageBackend().read_public_url(raw)
    if local:
        return local
    if is_loopback_url(raw):
        logger.warning("tech pack pdf: loopback image not on disk, skip HTTP %s", url)
        return None
    if not raw.startswith("http"):
        return None
    try:
        timeout = min(8.0, float(get_settings().openai_http_timeout_seconds))
        with httpx.Client(timeout=timeout) as client:
            r = client.get(raw, follow_redirects=True)
            r.raise_for_status()
            return r.content
    except Exception as e:
        logger.warning("tech pack pdf: could not fetch image %s: %s", url, e)
        return None


def _image_flow(raw: bytes | None, max_w: float, max_h: float, placeholder: Paragraph) -> Any:
    if not raw:
        return placeholder
    try:
        from PIL import Image as PILImage

        probe = PILImage.open(io.BytesIO(raw))
        probe.load()
        if probe.size[0] <= 0 or probe.size[1] <= 0:
            return placeholder
        img = Image(io.BytesIO(raw))
        img.hAlign = "CENTER"
        iw, ih = float(img.imageWidth), float(img.imageHeight)
        if iw <= 0 or ih <= 0:
            return placeholder
        scale = min(max_w / iw, max_h / ih, 1.0)
        img.drawWidth = iw * scale
        img.drawHeight = ih * scale
        return img
    except Exception:
        return placeholder


def render_tech_pack_pdf(data: dict[str, Any], images: dict[str, bytes | None] | None = None) -> bytes:
    """Build a 2-page landscape A4 spec: technical sheet + pattern/cutting sheet."""
    images = images or {}
    s = _styles()
    garment = data.get("garment") if isinstance(data.get("garment"), dict) else {}
    measurements = data.get("measurements") if isinstance(data.get("measurements"), dict) else {}
    body = measurements.get("body") if isinstance(measurements.get("body"), dict) else {}
    finished = measurements.get("finished") if isinstance(measurements.get("finished"), dict) else {}
    materials = data.get("materials") if isinstance(data.get("materials"), list) else []
    pieces = data.get("pattern_pieces") if isinstance(data.get("pattern_pieces"), list) else []
    steps = data.get("construction_steps") if isinstance(data.get("construction_steps"), list) else []
    special = data.get("special_instructions") if isinstance(data.get("special_instructions"), list) else []
    cutting = data.get("cutting_layout") if isinstance(data.get("cutting_layout"), dict) else {}
    gtype = str(garment.get("type") or "Garment")
    desc = str(garment.get("construction_description") or data.get("summary") or "")
    sample = str(measurements.get("sample_size") or "EU 36 / US 4")
    page_w, page_h = landscape(A4)
    margin = 12 * mm
    inner = page_w - 2 * margin

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=margin,
        rightMargin=margin,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"FashionRise Tech Pack — {gtype}",
        author="FashionRise",
    )

    story: list[Any] = []
    story.append(_p("FASHION TECHNICAL SPECIFICATION", s["title"]))
    story.append(_p("First production draft  ·  FashionRise", s["kicker"]))

    meta_left = _kv_table(
        [
            ("STYLE NO.", str(data.get("style_no") or "FR-001")),
            ("GARMENT", gtype),
            ("CATEGORY", str(garment.get("silhouette") or "—")),
            ("NECKLINE", str(garment.get("neckline") or "—")),
            ("SLEEVES", str(garment.get("sleeves") or "—")),
            ("CLOSURE", str(garment.get("closure") or "—")),
        ],
        [38 * mm, 72 * mm],
        s,
    )
    meta_right = _kv_table(
        [
            ("SAMPLE SIZE", sample),
            ("DATE", "studio draft"),
            ("PAGE", "1 of 2"),
            ("DESCRIPTION", desc[:280] or "—"),
        ],
        [38 * mm, inner - 38 * mm - 110 * mm - 8 * mm],
        s,
    )
    story.append(Table([[meta_left, meta_right]], colWidths=[110 * mm, inner - 110 * mm]))
    story.append(Spacer(1, 4 * mm))

    col = (inner - 8 * mm) / 2
    pending = _p("(technical drawing pending)", s["caption"])
    story.append(
        Table(
            [
                [_p("FRONT VIEW", s["caption"]), _p("BACK VIEW", s["caption"])],
                [
                    _image_flow(images.get("front"), col, 72 * mm, pending),
                    _image_flow(images.get("back"), col, 72 * mm, pending),
                ],
            ],
            colWidths=[col, col],
        )
    )

    story.append(_p("SAMPLE SIZE BASE", s["h"]))
    keys: list[str] = []
    for k in list(body.keys()) + [x for x in finished.keys() if x not in body]:
        if k not in keys:
            keys.append(k)
    if not keys:
        keys = ["height_cm", "bust_cm", "waist_cm", "hip_cm"]
    mdata = [[_p("Measurement", s["cellb"]), _p("Body", s["cellb"]), _p("Finished garment", s["cellb"])]]
    for k in keys:
        label = k.replace("_cm", "").replace("_", " ").title()
        mdata.append(
            [_p(label, s["cell"]), _p(_fmt_cm(body.get(k)), s["cell"]), _p(_fmt_cm(finished.get(k)), s["cell"])]
        )
    story.append(_table(mdata, [70 * mm, 50 * mm, 50 * mm]))

    story.append(_p("MATERIALS &amp; NOTIONS", s["h"]))
    mat_rows = [[_p("Item", s["cellb"]), _p("Specification", s["cellb"]), _p("Qty", s["cellb"])]]
    for m in materials:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name") or "Item")
        role = str(m.get("role") or "")
        if role:
            name = f"{name} ({role})"
        spec = " ".join(x for x in (str(m.get("recommendation") or ""), str(m.get("notes") or "")) if x).strip()
        mat_rows.append([_p(name, s["cell"]), _p(spec, s["cell"]), _p(_qty(m), s["cell"])])
    if len(mat_rows) == 1:
        mat_rows.append([_p("—", s["cell"]), _p("", s["cell"]), _p("", s["cell"])])
    story.append(_table(mat_rows, [55 * mm, inner - 85 * mm, 30 * mm]))
    story.append(Spacer(1, 4 * mm))
    story.append(_p(f"NOTES: {DISCLAIMER}  Sample body 170 cm / 84-64-90. SCALE: NTS.", s["foot"]))

    # Page 2 — pattern / cutting
    story.append(PageBreak())
    story.append(_p("FASHION PATTERN DRAFTING &amp; CUTTING SHEET", s["title"]))
    story.append(_p(gtype.upper(), s["kicker"]))
    story.append(_image_flow(images.get("pattern"), inner, 72 * mm, _p("Pattern blueprint pending — piece table below is the first draft.", s["caption"])))

    story.append(_p("PATTERN PIECES", s["h"]))
    piece_rows = [[
        _p("Piece", s["cellb"]),
        _p("Cut", s["cellb"]),
        _p("Grain / fold / notches", s["cellb"]),
        _p("Approx. size", s["cellb"]),
        _p("SA", s["cellb"]),
    ]]
    for p in pieces:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "Piece")
        qty = p.get("qty")
        cut = f"Cut {qty}" if qty not in (None, "") else "Cut 1"
        if p.get("on_fold") is True:
            cut += " · on fold"
        grain = str(p.get("grainline") or "")
        notches = p.get("notches")
        if isinstance(notches, list) and notches:
            grain = (grain + "  ·  notches: " + ", ".join(str(n) for n in notches)).strip(" ·")
        w, hgt = p.get("approx_w_cm"), p.get("approx_h_cm")
        size = "—"
        try:
            if w is not None and hgt is not None:
                size = f"{float(w):g} × {float(hgt):g} cm"
        except (TypeError, ValueError):
            size = f"{w} × {hgt}"
        sa = p.get("seam_allowance_cm")
        try:
            sa_txt = f"{float(sa):g} cm" if sa is not None else "1 cm"
        except (TypeError, ValueError):
            sa_txt = str(sa or "1 cm")
        piece_rows.append([
            _p(name, s["cell"]),
            _p(cut, s["cell"]),
            _p(grain, s["cell"]),
            _p(size, s["cell"]),
            _p(sa_txt, s["cell"]),
        ])
    if len(piece_rows) == 1:
        piece_rows.append([_p("—", s["cell"]), _p("", s["cell"]), _p("", s["cell"]), _p("", s["cell"]), _p("", s["cell"])])
    story.append(_table(piece_rows, [48 * mm, 32 * mm, inner - 140 * mm, 40 * mm, 20 * mm]))

    width = cutting.get("fabric_width_cm") or 150
    story.append(_p("CUTTING LAYOUT", s["h"]))
    story.append(_p(
        f"Standard fabric width {width} cm. {cutting.get('notes') or ''} {cutting.get('efficiency_tip') or ''}".strip(),
        s["note"],
    ))

    story.append(_p("CONSTRUCTION SEQUENCE", s["h"]))
    step_txt = []
    for i, step in enumerate(steps, 1):
        t = str(step).strip()
        if t:
            step_txt.append(f"{i}. {t}")
    story.append(_p("\n".join(step_txt) or "—", s["note"]))

    if special:
        story.append(_p("SPECIAL CONSTRUCTION INSTRUCTIONS", s["h"]))
        spec_txt = []
        for i, item in enumerate(special, 1):
            t = str(item).strip()
            if t:
                spec_txt.append(f"{i}. {t}")
        story.append(_p("\n".join(spec_txt), s["note"]))

    story.append(Spacer(1, 4 * mm))
    story.append(_p(
        f"NOTES: {DISCLAIMER} Edit measurements, fabric, body size and pattern values before manufacturing export.",
        s["foot"],
    ))

    def _paint(canvas, _doc) -> None:
        canvas.saveState()
        canvas.setFillColor(PAPER)
        canvas.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(0.6)
        canvas.rect(8 * mm, 8 * mm, page_w - 16 * mm, page_h - 16 * mm, fill=0, stroke=1)
        canvas.restoreState()

    doc.build(story, onFirstPage=_paint, onLaterPages=_paint)
    return buf.getvalue()


def store_tech_pack_pdf(
    job: AIJob,
    data: dict[str, Any],
    images: dict[str, bytes | None] | None = None,
) -> str | None:
    """Render PDF, save under local storage, return public URL."""
    packed: dict[str, bytes | None] = dict(images or {})
    packed["front"] = packed.get("front") or _fetch_png(
        data.get("image_url") if isinstance(data.get("image_url"), str) else None
    )
    packed["back"] = packed.get("back") or _fetch_png(
        data.get("back_image_url") if isinstance(data.get("back_image_url"), str) else None
    )
    packed["pattern"] = packed.get("pattern") or _fetch_png(
        data.get("pattern_image_url") if isinstance(data.get("pattern_image_url"), str) else None
    )
    images = packed
    payload = dict(data)
    payload["style_no"] = "FR-" + (
        job.id.hex[:4].upper() if hasattr(job.id, "hex") else str(job.id).replace("-", "")[:4].upper()
    )
    raw = render_tech_pack_pdf(payload, images)
    key = (
        f"ai/{job.id.hex if hasattr(job.id, 'hex') else str(job.id).replace('-', '')}"
        f"_techpack.pdf"
    )
    url = LocalStorageBackend().save_file(key=key, data=io.BytesIO(raw), content_type="application/pdf")
    logger.info("Tech pack job %s: stored PDF → %s", job.id, url)
    return url
