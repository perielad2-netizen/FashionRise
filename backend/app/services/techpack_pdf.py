"""reportlab multi-page Create Real Design PDF.

Fixes relative to the FR-5608 prototype:
- Accurate Page N of M footers (no mismatched labels)
- Body Height appears once
- Cutting / reference page reuses authenticated Magic look images (never a fabricated figure)
- Every measurement row shows Source (Designer / Estimate / Empty / AI / Look)
- DRAFT / UNVERIFIED banner on every page
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm

INK = colors.HexColor("#1a2233")
MUTED = colors.HexColor("#5a6578")
RULE = colors.HexColor("#c9d0dc")
BANNER_BG = colors.HexColor("#f3e8c8")
BANNER_FG = colors.HexColor("#6b4e16")
HEADER_BG = colors.HexColor("#eef2f7")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "tp_title",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=INK,
            spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "tp_h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "tp_body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=INK,
            leading=12,
        ),
        "muted": ParagraphStyle(
            "tp_muted",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            leading=11,
        ),
        "banner": ParagraphStyle(
            "tp_banner",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=BANNER_FG,
            alignment=TA_CENTER,
            leading=11,
        ),
        "small": ParagraphStyle(
            "tp_small",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            textColor=MUTED,
            leading=9,
        ),
    }


def _fmt_value(cell: Any) -> str:
    if not isinstance(cell, dict):
        return "—"
    value = cell.get("value")
    unit = cell.get("unit") or ""
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        text = f"{value:g}"
    else:
        text = str(value)
    return f"{text} {unit}".strip() if unit else text


def _fmt_source(cell: Any) -> str:
    if not isinstance(cell, dict):
        return "Empty"
    source = str(cell.get("source") or "empty").lower()
    return {
        "designer": "Designer",
        "estimate": "Estimate",
        "ai": "AI (unverified)",
        "look": "Look",
        "empty": "Empty",
    }.get(source, "Empty")


def _measurement_table(rows: list[tuple[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        [
            Paragraph("<b>Point</b>", styles["small"]),
            Paragraph("<b>Value</b>", styles["small"]),
            Paragraph("<b>Source</b>", styles["small"]),
            Paragraph("<b>Note</b>", styles["small"]),
        ]
    ]
    for label, cell in rows:
        note = ""
        if isinstance(cell, dict) and isinstance(cell.get("note"), str):
            note = cell["note"]
        data.append(
            [
                Paragraph(label, styles["body"]),
                Paragraph(_fmt_value(cell), styles["body"]),
                Paragraph(_fmt_source(cell), styles["muted"]),
                Paragraph(note or "—", styles["muted"]),
            ]
        )
    table = Table(data, colWidths=[42 * mm, 28 * mm, 32 * mm, 58 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


class _SizedImage(Flowable):
    """Image with explicit wrap size so 1×1 fixtures cannot explode layout."""

    def __init__(self, path: Path, width: float, height: float) -> None:
        super().__init__()
        self._path = path
        self.drawWidth = width
        self.drawHeight = height

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:  # noqa: N803
        _ = (availWidth, availHeight)
        return self.drawWidth, self.drawHeight

    def draw(self) -> None:
        self.canv.drawImage(
            str(self._path),
            0,
            0,
            width=self.drawWidth,
            height=self.drawHeight,
            preserveAspectRatio=True,
            mask="auto",
        )


def _look_image(path: Path | None, max_w: float, max_h: float, styles: dict[str, ParagraphStyle]) -> Any:
    if path is None or not path.is_file():
        return Paragraph("Look image unavailable", styles["muted"])
    try:
        from PIL import Image as PILImage

        with PILImage.open(path) as pil:
            iw, ih = pil.size
    except Exception:  # noqa: BLE001
        return Paragraph("Look image unavailable", styles["muted"])
    if iw <= 0 or ih <= 0:
        return Paragraph("Look image unavailable", styles["muted"])
    scale = min(max_w / float(iw), max_h / float(ih))
    draw_w = min(max_w, max(24.0, float(iw) * scale))
    draw_h = min(max_h, max(24.0, float(ih) * scale))
    return _SizedImage(path, draw_w, draw_h)


def _side_cell(label: str, path: Path | None, styles: dict[str, ParagraphStyle], *, max_h: float = 95 * mm) -> Table:
    content = [
        [Paragraph(f"<b>{label}</b>", styles["body"])],
        [_look_image(path, 78 * mm, max_h, styles) if path else Paragraph("Unavailable — not fabricated.", styles["muted"])],
    ]
    cell = Table(content, colWidths=[82 * mm])
    cell.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
    return cell


def _build_story(
    *,
    title: str,
    style_code: str,
    revision: int,
    status_label: str,
    look_id: str,
    front_image: Path | None,
    back_image: Path | None,
    spec: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    story: list[Any] = []

    story.append(Paragraph("FashionRise · Create Real Design", styles["muted"]))
    story.append(Paragraph(title or "Untitled look", styles["title"]))
    cover_meta = [
        [Paragraph("<b>Style</b>", styles["body"]), Paragraph(style_code, styles["body"])],
        [Paragraph("<b>Revision</b>", styles["body"]), Paragraph(str(revision), styles["body"])],
        [Paragraph("<b>Status</b>", styles["body"]), Paragraph(status_label, styles["body"])],
        [Paragraph("<b>Look ID</b>", styles["body"]), Paragraph(look_id, styles["muted"])],
        [
            Paragraph("<b>Size system</b>", styles["body"]),
            Paragraph(str(spec.get("size_system") or "—"), styles["body"]),
        ],
        [
            Paragraph("<b>Units</b>", styles["body"]),
            Paragraph(str(spec.get("units") or "cm"), styles["body"]),
        ],
        [
            Paragraph("<b>Sample size</b>", styles["body"]),
            Paragraph(str(spec.get("sample_size") or "—"), styles["body"]),
        ],
    ]
    meta_table = Table(cover_meta, colWidths=[36 * mm, 120 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, RULE),
                ("BACKGROUND", (0, 0), (0, -1), HEADER_BG),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(Spacer(1, 6))
    story.append(meta_table)
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            str(spec.get("disclaimer") or "DRAFT / UNVERIFIED. Patternmaker review required."),
            styles["body"],
        )
    )
    notes = (spec.get("look_notes") or "").strip()
    if notes:
        story.append(Paragraph("Look notes", styles["h2"]))
        story.append(Paragraph(notes, styles["body"]))
    designer = (spec.get("designer_notes") or "").strip()
    if designer:
        story.append(Paragraph("Designer notes", styles["h2"]))
        story.append(Paragraph(designer, styles["body"]))

    story.append(PageBreak())
    story.append(Paragraph("Magic look references", styles["h2"]))
    story.append(
        Paragraph(
            "Images below are the authenticated Magic Front/Back jobs for this look. "
            "Missing sides are not invented.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 6))
    looks_row = Table(
        [
            [
                _side_cell("Front", front_image, styles, max_h=105 * mm),
                _side_cell("Back", back_image, styles, max_h=105 * mm),
            ]
        ],
        colWidths=[88 * mm, 88 * mm],
    )
    looks_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(looks_row)

    story.append(PageBreak())
    story.append(Paragraph("Garment specification", styles["h2"]))
    mats = spec.get("materials") if isinstance(spec.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    lining = mats.get("lining") if isinstance(mats.get("lining"), dict) else {}
    closures = spec.get("closures") if isinstance(spec.get("closures"), dict) else {}
    fit = spec.get("fit") if isinstance(spec.get("fit"), dict) else {}
    story.append(
        Paragraph(
            f"Shell: {shell.get('name') or '—'} · "
            f"Composition: {shell.get('composition') or '—'} · "
            f"Stretch: {shell.get('stretch') or '—'} · "
            f"Lining: {lining.get('name') or '—'} · "
            f"Closure: {closures.get('type') or '—'} · "
            f"Silhouette: {fit.get('silhouette') or '—'}",
            styles["body"],
        )
    )
    story.append(Paragraph("Body measurements", styles["h2"]))
    story.append(
        Paragraph(
            "Each body point appears once. Empty values stay empty — no invented precision.",
            styles["muted"],
        )
    )
    body = spec.get("body") if isinstance(spec.get("body"), dict) else {}
    # Height exactly once — FR-5608 had a repeated Height row.
    body_rows = [
        ("Height", body.get("height")),
        ("Bust", body.get("bust")),
        ("Waist", body.get("waist")),
        ("Hip", body.get("hip")),
    ]
    story.append(_measurement_table(body_rows, styles))

    story.append(Paragraph("Finished garment measurements", styles["h2"]))
    garment = spec.get("garment") if isinstance(spec.get("garment"), dict) else {}
    garment_rows = [
        ("Garment length", garment.get("garment_length")),
        ("Shoulder width", garment.get("shoulder_width")),
        ("Sleeve length", garment.get("sleeve_length")),
        ("Inseam", garment.get("inseam")),
        ("Hem circumference", garment.get("hem_circumference")),
        ("Ease", fit.get("ease")),
        ("Seam allowance", spec.get("seam_allowance")),
    ]
    story.append(_measurement_table(garment_rows, styles))

    story.append(PageBreak())
    story.append(Paragraph("Bill of materials", styles["h2"]))
    bom = spec.get("bom") if isinstance(spec.get("bom"), list) else []
    if bom:
        bom_data = [[Paragraph("<b>Item</b>", styles["small"]), Paragraph("<b>Notes</b>", styles["small"])]]
        for row in bom[:40]:
            if not isinstance(row, dict):
                continue
            bom_data.append(
                [
                    Paragraph(str(row.get("item") or row.get("name") or "—"), styles["body"]),
                    Paragraph(str(row.get("notes") or row.get("source") or "—"), styles["muted"]),
                ]
            )
        bom_table = Table(bom_data, colWidths=[70 * mm, 90 * mm])
        bom_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                    ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(bom_table)
    else:
        story.append(
            Paragraph(
                "No BOM rows yet. Add materials after designer validation — estimates only until confirmed.",
                styles["muted"],
            )
        )

    story.append(Paragraph("Construction notes", styles["h2"]))
    construction = spec.get("construction") if isinstance(spec.get("construction"), list) else []
    if construction:
        for row in construction[:30]:
            if not isinstance(row, dict):
                continue
            step = row.get("step", "")
            instruction = str(row.get("instruction") or "")
            src = _fmt_source(row)
            story.append(Paragraph(f"{step}. {instruction} <font color='#5a6578'>({src})</font>", styles["body"]))
    else:
        story.append(Paragraph("No construction steps recorded.", styles["muted"]))

    story.append(Paragraph("QC / approval checklist", styles["h2"]))
    qc = spec.get("qc_checklist") if isinstance(spec.get("qc_checklist"), list) else []
    for row in qc[:20]:
        if not isinstance(row, dict):
            continue
        mark = "[x]" if row.get("checked") else "[ ]"
        story.append(Paragraph(f"{mark} {row.get('item') or '—'}", styles["body"]))

    story.append(PageBreak())
    story.append(Paragraph("Pattern & cutting reference", styles["h2"]))
    story.append(
        Paragraph(
            "Cutting reference uses the same authenticated Magic look images shown earlier. "
            "FashionRise does not invent graded pattern pieces or alternate-color figures.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 6))
    pieces = spec.get("pattern_pieces") if isinstance(spec.get("pattern_pieces"), list) else []
    if pieces:
        for piece in pieces[:30]:
            if not isinstance(piece, dict):
                continue
            story.append(
                Paragraph(
                    f"* {piece.get('name') or 'Piece'} — {piece.get('notes') or 'qualified only'} "
                    f"({_fmt_source(piece)})",
                    styles["body"],
                )
            )
    else:
        story.append(
            Paragraph(
                "No qualified pattern inventory yet. Do not treat look images as graded cut pieces.",
                styles["body"],
            )
        )
    story.append(Spacer(1, 8))
    # Reuse the same front/back paths — FR-5608 bug was a mismatched green figure.
    ref_row = Table(
        [
            [
                _side_cell("Front reference (same Magic job)", front_image, styles, max_h=90 * mm),
                _side_cell("Back reference (same Magic job)", back_image, styles, max_h=90 * mm),
            ]
        ],
        colWidths=[88 * mm, 88 * mm],
    )
    ref_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(ref_row)
    return story


def build_techpack_pdf(
    *,
    title: str,
    style_code: str,
    revision: int,
    status: str,
    verification: str,
    look_id: str,
    front_image: Path | None,
    back_image: Path | None,
    spec: dict[str, Any],
) -> tuple[bytes, int]:
    """Return (pdf_bytes, page_count) with accurate Page N of M footers."""
    styles = _styles()
    status_label = f"{status} / {verification}"
    story_kwargs = dict(
        title=title,
        style_code=style_code,
        revision=revision,
        status_label=status_label,
        look_id=look_id,
        front_image=front_image,
        back_image=back_image,
        spec=spec,
        styles=styles,
    )

    # Pass 1: count pages with a discarded buffer.
    count_state = {"n": 0}

    def _count_page(canvas: Any, doc_obj: Any) -> None:
        count_state["n"] = max(count_state["n"], int(doc_obj.page))

    count_buf = io.BytesIO()
    count_doc = SimpleDocTemplate(
        count_buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
    )
    count_doc.build(
        _build_story(**story_kwargs),
        onFirstPage=_count_page,
        onLaterPages=_count_page,
    )
    page_count = count_state["n"] or 1

    # Pass 2: real PDF with Page N of M.
    out_buf = io.BytesIO()
    doc = SimpleDocTemplate(
        out_buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=f"{style_code} — {title}",
        author="FashionRise",
    )

    def _draw_page(canvas: Any, doc_obj: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(BANNER_BG)
        canvas.rect(MARGIN, PAGE_H - 14 * mm, PAGE_W - 2 * MARGIN, 8 * mm, fill=1, stroke=0)
        canvas.setFillColor(BANNER_FG)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawCentredString(
            PAGE_W / 2,
            PAGE_H - 11.5 * mm,
            f"{status_label}  ·  {style_code}  ·  Rev {revision}  ·  Patternmaker review required",
        )
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN, 10 * mm, "FashionRise Create Real Design")
        canvas.drawRightString(
            PAGE_W - MARGIN,
            10 * mm,
            f"Page {doc_obj.page} of {page_count}",
        )
        canvas.restoreState()

    doc.build(
        _build_story(**story_kwargs),
        onFirstPage=_draw_page,
        onLaterPages=_draw_page,
    )
    return out_buf.getvalue(), page_count
