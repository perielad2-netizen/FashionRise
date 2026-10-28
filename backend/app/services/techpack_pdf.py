"""reportlab Create Real Design PDF — V1 compatible + V2 multi-piece technical packs.

V2 produces content-driven page counts with per-garment flats, BOM, pattern
schematics (NOT TO SCALE), construction, and measurement sheets.
Magic look photos appear on cover/overview only — never as cutting patterns.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.techpack_compatibility import (
    collect_compatibility_warnings,
    filter_construction_steps,
    filter_pattern_inventory,
    material_contradiction,
)
from app.services.techpack_flats import (
    default_bom,
    default_construction_steps,
    flat_for_category,
    pattern_inventory_for_category,
)
from app.services.techpack_garments import POM_LABELS
from app.services.techpack_manufacturing import (
    READINESS_LABELS,
    enrich_spec_for_manufacturing_preview,
    evaluate_artifact_for_piece,
    normalize_closure_display,
    normalize_shell_material,
)
from app.services.techpack_spec import ensure_v2
from app.storage.local import LocalStorageBackend

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm


def resolve_generation_provenance(spec: dict[str, Any]) -> dict[str, Any]:
    """Derive truthful Basic vs AI Professional labels from draft spec (no secrets)."""
    v2 = ensure_v2(spec if isinstance(spec, dict) else {})
    ai = v2.get("ai") if isinstance(v2.get("ai"), dict) else {}
    outfit = v2.get("outfit") if isinstance(v2.get("outfit"), dict) else {}
    pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]
    professional_pieces = 0
    artifact_kinds: list[str] = []
    for piece in pieces:
        ill = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        arts = ill.get("artifacts") if isinstance(ill.get("artifacts"), dict) else {}
        if str(ill.get("mode") or "") == "professional" and arts:
            professional_pieces += 1
            for kind, meta in arts.items():
                if isinstance(meta, dict) and meta.get("storage_key"):
                    artifact_kinds.append(str(kind))
    mode = str(ai.get("last_mode") or "").strip().lower() or "none"
    # Only claim Professional when mode matches and at least one illustration artifact exists.
    is_professional = mode == "professional" and professional_pieces > 0
    if is_professional:
        label = "AI Professional"
        short = "professional"
    elif mode in ("heuristic", "ai"):
        label = "Basic / No AI Professional"
        short = "heuristic" if mode == "heuristic" else "ai_text"
    else:
        label = "Basic / No AI generated"
        short = "none"
    return {
        "mode": short,
        "label": label,
        "is_professional": is_professional,
        "run_id": str(ai.get("last_run_id") or "") if is_professional else "",
        "vision_model": str(ai.get("vision_model") or "") if is_professional else "",
        "image_model": str(ai.get("image_model") or "") if is_professional else "",
        "actual_cost_usd_cents": int(ai.get("actual_cost_usd_cents") or 0) if is_professional else 0,
        "paid_sections": list(ai.get("paid_sections") or []) if is_professional else [],
        "artifact_kinds": sorted(set(artifact_kinds)),
        "professional_piece_count": professional_pieces,
    }

INK = colors.HexColor("#1a2233")
MUTED = colors.HexColor("#5a6578")
RULE = colors.HexColor("#c9d0dc")
BANNER_BG = colors.HexColor("#f3e8c8")
BANNER_FG = colors.HexColor("#6b4e16")
HEADER_BG = colors.HexColor("#eef2f7")
ACCENT = colors.HexColor("#c45d8c")
CREAM = colors.HexColor("#f7f1ea")


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
        "h3": ParagraphStyle(
            "tp_h3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=4,
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
        "warn": ParagraphStyle(
            "tp_warn",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            textColor=colors.HexColor("#8a2b2b"),
            leading=11,
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
        "calculated": "Calculated",
        "unknown": "Unknown",
    }.get(source, source.title() if source else "Empty")


def _measurement_table(rows: list[tuple[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [
        [
            Paragraph("<b>Point</b>", styles["small"]),
            Paragraph("<b>Value</b>", styles["small"]),
            Paragraph("<b>Source</b>", styles["small"]),
            Paragraph("<b>Confidence</b>", styles["small"]),
            Paragraph("<b>Note / assumptions</b>", styles["small"]),
        ]
    ]
    for label, cell in rows:
        note = ""
        confidence = "—"
        point_label = label
        if isinstance(cell, dict):
            parts = []
            review = str(cell.get("review_status") or "").lower()
            if review in {"needs_review", "proposed", "proposed_unverified"}:
                point_label = f"{label} · REVIEW"
            if isinstance(cell.get("note"), str) and cell["note"]:
                parts.append(cell["note"])
            assumptions = cell.get("assumptions")
            if isinstance(assumptions, list) and assumptions:
                parts.append("Assumptions: " + "; ".join(str(a) for a in assumptions[:4]))
            note = " · ".join(parts)
            confidence = str(cell.get("confidence") or cell.get("review_status") or "—")
        data.append(
            [
                Paragraph(point_label, styles["body"]),
                Paragraph(_fmt_value(cell), styles["body"]),
                Paragraph(_fmt_source(cell), styles["muted"]),
                Paragraph(confidence, styles["muted"]),
                Paragraph(note or "—", styles["muted"]),
            ]
        )
    table = Table(data, colWidths=[36 * mm, 22 * mm, 26 * mm, 24 * mm, 52 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
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
        # Fit within available width while preserving intended aspect.
        if availWidth and self.drawWidth > availWidth:
            scale = availWidth / self.drawWidth
            self.drawWidth = availWidth
            self.drawHeight = self.drawHeight * scale
        if availHeight and self.drawHeight > availHeight:
            scale = availHeight / self.drawHeight
            self.drawHeight = availHeight
            self.drawWidth = self.drawWidth * scale
        return self.drawWidth, self.drawHeight

    def draw(self) -> None:
        # Normalize to RGB via ImageReader so reportlab never chokes on odd PNG streams.
        try:
            from PIL import Image as PILImage
            from reportlab.lib.utils import ImageReader

            with PILImage.open(self._path) as pil:
                rgb = pil.convert("RGB")
                buf = io.BytesIO()
                rgb.save(buf, format="PNG")
                buf.seek(0)
                self.canv.drawImage(
                    ImageReader(buf),
                    0,
                    0,
                    width=self.drawWidth,
                    height=self.drawHeight,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                return
        except Exception:  # noqa: BLE001
            pass
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
        return Paragraph("Look image unavailable — not fabricated.", styles["muted"])
    try:
        from PIL import Image as PILImage

        with PILImage.open(path) as pil:
            pil.load()
            rgb = pil.convert("RGB")
            iw, ih = rgb.size
            # Rewrite a normalized temp sibling so reportlab always gets a clean RGB PNG.
            norm = path.with_name(path.stem + "_rl.png")
            rgb.save(norm, format="PNG")
            path = norm
    except Exception:  # noqa: BLE001
        return Paragraph("Look image unavailable — not fabricated.", styles["muted"])
    if iw <= 0 or ih <= 0:
        return Paragraph("Look image unavailable — not fabricated.", styles["muted"])
    scale = min(max_w / float(iw), max_h / float(ih))
    draw_w = min(max_w, max(24.0, float(iw) * scale))
    draw_h = min(max_h, max(24.0, float(ih) * scale))
    return _SizedImage(path, draw_w, draw_h)


def _side_cell(label: str, path: Path | None, styles: dict[str, ParagraphStyle], *, max_h: float = 95 * mm) -> Table:
    content = [
        [Paragraph(f"<b>{label}</b>", styles["body"])],
        [_look_image(path, 78 * mm, max_h, styles)],
    ]
    cell = Table(content, colWidths=[82 * mm])
    cell.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
    return cell


def _cutting_layout_schematic(category: str) -> Drawing:
    """Deterministic fabric-width / grain / fold planning sketch — NOT TO SCALE.

    Intentionally avoids generic Piece A/B/C rectangles presented as cutting layouts.
    """
    d = Drawing(420, 160)
    d.add(Rect(20, 20, 380, 120, strokeColor=INK, strokeWidth=1.2, fillColor=CREAM))
    d.add(
        String(
            28,
            128,
            f"PATTERN PLANNING AID — {category.upper()} (NOT A CUTTING PATTERN)",
            fontName="Helvetica-Bold",
            fontSize=8,
            fillColor=INK,
        )
    )
    d.add(
        String(
            28,
            112,
            "Shows fabric width / fold / grain concepts only. No nested cut pieces are supplied.",
            fontName="Helvetica",
            fontSize=7,
            fillColor=MUTED,
        )
    )
    d.add(Line(40, 40, 40, 100, strokeColor=ACCENT, strokeWidth=1.2))
    d.add(String(44, 70, "grain →", fontName="Helvetica", fontSize=6, fillColor=ACCENT))
    d.add(Line(60, 95, 360, 95, strokeColor=MUTED, strokeWidth=0.8, strokeDashArray=[4, 3]))
    d.add(String(64, 82, "fold edge (planning)", fontName="Helvetica", fontSize=7, fillColor=MUTED))
    d.add(Rect(70, 40, 280, 8, strokeColor=INK, strokeWidth=0.8, fillColor=colors.white))
    d.add(String(76, 42, "fabric width example 140–150 cm", fontName="Helvetica", fontSize=6, fillColor=INK))
    d.add(
        String(
            28,
            22,
            "NOT TO SCALE · NOT A CUTTER MARKER · Patternmaker must develop the sewing pattern",
            fontName="Helvetica",
            fontSize=6.5,
            fillColor=MUTED,
        )
    )
    return d


def _kv_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle], *, col0: float = 40 * mm) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", styles["body"]), Paragraph(v or "—", styles["body"])] for k, v in rows]
    table = Table(data, colWidths=[col0, 120 * mm - (col0 - 40 * mm)])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, RULE),
                ("BACKGROUND", (0, 0), (0, -1), HEADER_BG),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _build_story_v1(
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
    """Legacy V1 sparse pack — retained for older unmigrated specs only."""
    story: list[Any] = []
    story.append(Paragraph("FashionRise · Create Real Design", styles["muted"]))
    story.append(Paragraph(title or "Untitled look", styles["title"]))
    story.append(
        _kv_table(
            [
                ("Style", style_code),
                ("Revision", str(revision)),
                ("Status", status_label),
                ("Look ID", look_id),
                ("Size system", str(spec.get("size_system") or "—")),
                ("Units", str(spec.get("units") or "cm")),
                ("Sample size", str(spec.get("sample_size") or "—")),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            str(spec.get("disclaimer") or "DRAFT / UNVERIFIED. Patternmaker review required."),
            styles["body"],
        )
    )
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
        [[_side_cell("Front", front_image, styles), _side_cell("Back", back_image, styles)]],
        colWidths=[88 * mm, 88 * mm],
    )
    looks_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(looks_row)
    story.append(PageBreak())
    story.append(Paragraph("Garment specification", styles["h2"]))
    mats = spec.get("materials") if isinstance(spec.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    closures = spec.get("closures") if isinstance(spec.get("closures"), dict) else {}
    fit = spec.get("fit") if isinstance(spec.get("fit"), dict) else {}
    story.append(
        Paragraph(
            f"Shell: {shell.get('name') or '—'} · Closure: {closures.get('type') or '—'} · "
            f"Silhouette: {fit.get('silhouette') or '—'}",
            styles["body"],
        )
    )
    story.append(Paragraph("Body measurements", styles["h2"]))
    body = spec.get("body") if isinstance(spec.get("body"), dict) else {}
    story.append(
        _measurement_table(
            [
                ("Height", body.get("height")),
                ("Bust", body.get("bust")),
                ("Waist", body.get("waist")),
                ("Hip", body.get("hip")),
            ],
            styles,
        )
    )
    story.append(Paragraph("Finished garment measurements", styles["h2"]))
    garment = spec.get("garment") if isinstance(spec.get("garment"), dict) else {}
    story.append(
        _measurement_table(
            [
                ("Garment length", garment.get("garment_length")),
                ("Shoulder width", garment.get("shoulder_width")),
                ("Sleeve length", garment.get("sleeve_length")),
                ("Inseam", garment.get("inseam")),
                ("Hem circumference", garment.get("hem_circumference")),
            ],
            styles,
        )
    )
    story.append(PageBreak())
    story.append(Paragraph("Bill of materials", styles["h2"]))
    story.append(Paragraph("No BOM rows yet (legacy draft).", styles["muted"]))
    story.append(Paragraph("Construction notes", styles["h2"]))
    story.append(Paragraph("No construction steps recorded.", styles["muted"]))
    story.append(PageBreak())
    story.append(Paragraph("Pattern & cutting reference", styles["h2"]))
    story.append(
        Paragraph(
            "Cutting reference uses the same authenticated Magic look images. "
            "Do not treat look images as graded cut pieces.",
            styles["muted"],
        )
    )
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


def _piece_sections(
    piece: dict[str, Any],
    *,
    styles: dict[str, ParagraphStyle],
    units: str,
) -> list[Any]:
    """Per-garment technical + construction + pattern block (may span pages)."""
    story: list[Any] = []
    cat = str(piece.get("category") or "other")
    label = str(piece.get("label") or cat.title())
    role = str(piece.get("role") or "").upper()
    color = str(piece.get("color_hint") or "")
    heading = f"{role + ' — ' if role else ''}{label}".strip(" —")
    story.append(Paragraph(f"Component: {heading}", styles["h2"]))
    story.append(
        Paragraph(
            f"Category: {cat} · Color hint: {color or '—'} · Detection: {piece.get('detection_source') or '—'}",
            styles["muted"],
        )
    )

    piece_norm = normalize_shell_material(piece)
    mats = piece_norm.get("materials") if isinstance(piece_norm.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    lining = mats.get("lining") if isinstance(mats.get("lining"), dict) else {}
    rib = mats.get("rib") if isinstance(mats.get("rib"), dict) else {}
    closures = normalize_closure_display(
        piece_norm.get("closures") if isinstance(piece_norm.get("closures"), dict) else {}
    )
    fit = piece.get("fit") if isinstance(piece.get("fit"), dict) else {}
    story.append(Paragraph("Materials & construction identity", styles["h3"]))
    shell_name = str(shell.get("name") or shell.get("suggestion") or "—")
    composition = str(shell.get("composition") or "Unknown / not confirmed")
    garment_color = str(piece_norm.get("color_hint") or piece.get("color_hint") or "—")
    colorway_note = str(shell.get("colorway_note") or "")
    story.append(
        _kv_table(
            [
                ("Garment color", garment_color),
                ("Shell material", shell_name if shell_name.strip() not in ("", "—") else "Not confirmed"),
                ("Composition", composition),
                ("Fabric structure", str(shell.get("fabric_structure") or "knit/woven — not confirmed")),
                ("Stretch", str(shell.get("stretch") or "not confirmed")),
                ("Weight / GSM", str(shell.get("weight_gsm") or shell.get("gsm") or "not confirmed")),
                ("Lining", str(lining.get("name") or "—")),
                ("Rib / band", str(rib.get("name") or "—")),
                ("Closure / fastener", str(closures.get("display_type") or "—")),
                ("Closure notes", str(closures.get("notes") or "—")),
                ("Silhouette", str(fit.get("silhouette") or fit.get("suggestion") or "—")),
                ("Length style", str(fit.get("length_style") or "—")),
                ("Ease note", str(fit.get("ease_note") or "—")),
                (
                    "Seam allowance",
                    _fmt_value(piece.get("seam_allowance"))
                    + " (default draft SA — not designer-approved unless confirmed)",
                ),
            ],
            styles,
        )
    )
    if colorway_note:
        story.append(
            Paragraph(
                f"<b>REVIEW:</b> Outfit color list was previously stored as shell name "
                f"(“{colorway_note[:120]}”). Color and fabric are separated above — confirm shell quality.",
                styles["warn"],
            )
        )
    if str(closures.get("review_status") or "") == "needs_review":
        story.append(
            Paragraph(
                "<b>REVIEW:</b> Closure must be named (zipper type/length, button, elastic, etc.). "
                "Boolean placeholders such as “True” are not manufacturing specifications.",
                styles["warn"],
            )
        )
    contrad = material_contradiction(shell_name, composition)
    if contrad:
        story.append(Paragraph(f"<b>REVIEW:</b> {contrad}", styles["warn"]))

    story.append(Paragraph("Technical flat drawings", styles["h3"]))
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    arts = illust.get("artifacts") if isinstance(illust.get("artifacts"), dict) else {}
    storage = LocalStorageBackend()

    def _art_path(kind: str) -> Path | None:
        meta = arts.get(kind) if isinstance(arts.get(kind), dict) else None
        if not meta:
            return None
        decision = evaluate_artifact_for_piece(piece, kind=kind, artifact_meta=meta)
        if not decision.get("include", True) or meta.get("preview_include") is False:
            return None
        key = meta.get("storage_key")
        if not isinstance(key, str) or not key:
            return None
        return storage.resolve_private_techpack_file(key=key)

    def _art_exclusion_note(kind: str) -> str | None:
        meta = arts.get(kind) if isinstance(arts.get(kind), dict) else None
        if not isinstance(meta, dict):
            return None
        decision = evaluate_artifact_for_piece(piece, kind=kind, artifact_meta=meta)
        rejected = (
            not decision.get("include", True)
            or meta.get("preview_include") is False
            or str(meta.get("review_state") or "").lower()
            in {"rejected_category_mismatch", "excluded_mismatch", "rejected"}
        )
        if not rejected:
            return None
        return str(
            decision.get("reason")
            or meta.get("review_message")
            or f"{kind} excluded from corrected preview (original preserved)."
        )

    front_art = _art_path("flat_front")
    back_art = _art_path("flat_back") or _art_path("flat_back_proposed")
    detail_art = _art_path("detail_callouts")
    pattern_art = _art_path("pattern_sheet")
    professional = str(illust.get("mode") or "") == "professional" and front_art is not None

    if professional:
        story.append(
            Paragraph(
                "AI PROFESSIONAL technical illustrations generated from the Magic look image. "
                "DRAFT / UNVERIFIED. Pattern sheets remain NOT TO SCALE — patternmaker validation required.",
                styles["muted"],
            )
        )
        analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
        if analysis:
            story.append(
                Paragraph(
                    f"Vision summary — silhouette: {analysis.get('silhouette') or '—'}; "
                    f"neckline: {analysis.get('neckline') or '—'}; "
                    f"sleeves: {analysis.get('sleeves') or '—'}; "
                    f"pattern: {analysis.get('fabric_pattern') or '—'} "
                    f"({analysis.get('stripe_direction') or 'direction n/a'}).",
                    styles["body"],
                )
            )
        front_img = (
            _look_image(front_art, 86 * mm, 120 * mm, styles)
            if front_art
            else flat_for_category(cat, back=False)
        )
        if back_art:
            back_label = (
                "PROPOSED BACK — UNVERIFIED"
                if arts.get("flat_back_proposed") and not arts.get("flat_back")
                else "BACK — AI FLAT"
            )
            back_img = _look_image(back_art, 86 * mm, 120 * mm, styles)
        else:
            back_label = "BACK — category schematic (no AI back)"
            back_img = flat_for_category(cat, back=True)
        flats = Table(
            [
                [
                    Paragraph("<b>FRONT — AI FLAT</b>", styles["small"]),
                    Paragraph(f"<b>{back_label}</b>", styles["small"]),
                ],
                [front_img, back_img],
            ],
            colWidths=[88 * mm, 88 * mm],
        )
        flats.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(flats)
        if arts.get("flat_back_proposed") and not arts.get("flat_back"):
            story.append(
                Paragraph(
                    "<b>PROPOSED BACK:</b> No real Magic back image was available. "
                    "Back construction is proposed for designer confirmation — not confirmed rear detailing.",
                    styles["warn"],
                )
            )
        detail_excl = _art_exclusion_note("detail_callouts")
        if detail_art:
            story.append(Paragraph("Garment detail illustrations", styles["h3"]))
            # Use nearly full content width so detail sheets are legible (not tiny top-left).
            story.append(_look_image(detail_art, 170 * mm, 145 * mm, styles))
        elif detail_excl:
            story.append(Paragraph("Garment detail illustrations", styles["h3"]))
            story.append(
                Paragraph(
                    f"<b>MISSING / EXCLUDED:</b> {detail_excl} "
                    "Original file and provenance are preserved; another garment’s artwork was not substituted.",
                    styles["warn"],
                )
            )
        else:
            story.append(Paragraph("Garment detail illustrations", styles["h3"]))
            story.append(
                Paragraph(
                    "No category-confirmed detail callout sheet is available for this component.",
                    styles["muted"],
                )
            )
    else:
        story.append(
            Paragraph(
                "BASIC / NO AI PROFESSIONAL — PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE. "
                "Back view is a category schematic, not an invented Magic photo. "
                "These are not source-faithful AI flats. Run AI Professional to replace them.",
                styles["muted"],
            )
        )
        flats = Table(
            [[flat_for_category(cat, back=False), flat_for_category(cat, back=True)]],
            colWidths=[90 * mm, 90 * mm],
        )
        flats.setStyle(
            TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER")])
        )
        story.append(KeepTogether([flats]))
        # Still surface excluded Professional detail sheets (original preserved, not substituted).
        detail_excl = _art_exclusion_note("detail_callouts")
        if detail_excl:
            story.append(Paragraph("Garment detail illustrations", styles["h3"]))
            story.append(
                Paragraph(
                    f"<b>MISSING / EXCLUDED:</b> {detail_excl} "
                    "Original file and provenance are preserved; another garment’s artwork was not substituted.",
                    styles["warn"],
                )
            )

    story.append(PageBreak())
    story.append(Paragraph(f"Measurement specification — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            f"Finished-garment points of measure for this {cat} only ({units}). "
            "Body measurements are listed separately on the outfit overview. "
            "Calculated/AI values require designer review.",
            styles["muted"],
        )
    )
    # PDF-time compatibility: mark sleeveless/sleeve mismatches even on older drafts.
    from app.services.techpack_compatibility import collect_compatibility_warnings

    _ = collect_compatibility_warnings({"outfit": {"pieces": [piece]}})
    finished = piece.get("finished_measurements") if isinstance(piece.get("finished_measurements"), dict) else {}
    finished_rows = [
        (POM_LABELS.get(key, key), cell)
        for key, cell in finished.items()
        if isinstance(cell, dict)
    ]
    if finished_rows:
        story.append(_measurement_table(finished_rows, styles))
        sleeve_cell = finished.get("sleeve_length")
        analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
        if (
            isinstance(sleeve_cell, dict)
            and isinstance(sleeve_cell.get("value"), (int, float))
            and str(sleeve_cell.get("review_status") or "") == "needs_review"
        ):
            story.append(
                Paragraph(
                    "<b>REVIEW:</b> Sleeve length is recorded but may not apply to this garment "
                    f"(analysis sleeves: {analysis.get('sleeves') or '—'}). "
                    "Designer value preserved — confirm before manufacturing.",
                    styles["warn"],
                )
            )
    else:
        story.append(Paragraph("No finished measurements recorded for this piece.", styles["muted"]))

    story.append(Paragraph("Bill of materials", styles["h3"]))
    bom = piece.get("bom") if isinstance(piece.get("bom"), list) else []
    if not bom:
        bom = default_bom(cat, color_hint=color)
    bom_data = [
        [
            Paragraph("<b>Item</b>", styles["small"]),
            Paragraph("<b>Qty</b>", styles["small"]),
            Paragraph("<b>Unit</b>", styles["small"]),
            Paragraph("<b>Source</b>", styles["small"]),
            Paragraph("<b>Notes</b>", styles["small"]),
        ]
    ]
    for row in bom[:40]:
        if not isinstance(row, dict):
            continue
        bom_data.append(
            [
                Paragraph(str(row.get("item") or row.get("name") or "—"), styles["body"]),
                Paragraph(str(row.get("qty") or "—"), styles["body"]),
                Paragraph(str(row.get("unit") or "—"), styles["muted"]),
                Paragraph(_fmt_source(row), styles["muted"]),
                Paragraph(str(row.get("notes") or "—"), styles["muted"]),
            ]
        )
    bom_table = Table(bom_data, colWidths=[48 * mm, 22 * mm, 18 * mm, 28 * mm, 44 * mm])
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

    story.append(PageBreak())
    story.append(Paragraph(f"Pattern piece development — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            "PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE. "
            "These are planning illustrations, not production-validated cut patterns.",
            styles["warn"],
        )
    )
    analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
    patterns = piece.get("pattern_pieces") if isinstance(piece.get("pattern_pieces"), list) else []
    if not patterns:
        patterns = pattern_inventory_for_category(cat)
    patterns = filter_pattern_inventory(
        [p for p in patterns if isinstance(p, dict)],
        analysis=analysis,
        ai_suggested=analysis.get("pattern_pieces_suggested")
        if isinstance(analysis.get("pattern_pieces_suggested"), list)
        else None,
    )
    story.append(
        Paragraph(
            "Approved template pieces vs AI-proposed additions are labeled in notes. "
            "Uncertain cut quantities stay blank — never invented.",
            styles["muted"],
        )
    )
    pat_data = [
        [
            Paragraph("<b>ID</b>", styles["small"]),
            Paragraph("<b>Name</b>", styles["small"]),
            Paragraph("<b>Cut</b>", styles["small"]),
            Paragraph("<b>Fabric</b>", styles["small"]),
            Paragraph("<b>Grain / fold</b>", styles["small"]),
            Paragraph("<b>Review</b>", styles["small"]),
        ]
    ]
    for row in patterns[:30]:
        if not isinstance(row, dict):
            continue
        cut = row.get("cut_qty")
        cut_txt = "—" if cut is None else str(cut)
        review = str(row.get("review_state") or row.get("source") or "—")
        notes = str(row.get("notes") or "")
        name_txt = str(row.get("name") or "—")
        if notes:
            name_txt = f"{name_txt} — {notes[:80]}"
        pat_data.append(
            [
                Paragraph(str(row.get("id") or "—"), styles["body"]),
                Paragraph(name_txt, styles["body"]),
                Paragraph(cut_txt, styles["body"]),
                Paragraph(str(row.get("fabric") or "shell"), styles["muted"]),
                Paragraph(
                    f"{row.get('grainline') or 'straight'} / {row.get('fold') or 'none'}",
                    styles["muted"],
                ),
                Paragraph(review, styles["muted"]),
            ]
        )
    pat_table = Table(pat_data, colWidths=[18 * mm, 40 * mm, 14 * mm, 22 * mm, 50 * mm, 16 * mm])
    pat_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(pat_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph("Cutting layout / pattern development", styles["h3"]))
    story.append(
        Paragraph(
            "Sample development: an actual sewing pattern is <b>not</b> supplied with this pack. "
            "A patternmaker must develop the pattern from confirmed POMs and construction. "
            "NOT-TO-SCALE schematics are planning aids only — not usable cutting patterns.",
            styles["warn"],
        )
    )
    if professional and pattern_art is not None:
        story.append(
            Paragraph(
                "AI pattern-development schematic — NOT TO SCALE — PATTERNMAKER VALIDATION REQUIRED.",
                styles["warn"],
            )
        )
        story.append(_look_image(pattern_art, 160 * mm, 110 * mm, styles))
    else:
        # Honest about skipped pattern-sheet generation (budget/optional) — do not imply a cutter.
        skipped = bool(professional and pattern_art is None)
        if skipped:
            story.append(
                Paragraph(
                    "Pattern-sheet illustration was not generated for this run (optional budget skip or unavailable). "
                    "This is not a completed cutting layout.",
                    styles["muted"],
                )
            )
        story.append(_cutting_layout_schematic(cat))

    story.append(Paragraph("Construction process", styles["h3"]))
    story.append(
        Paragraph(
            "Default seam allowances and generic sewing steps are draft aids only — not designer-approved "
            "construction unless explicitly confirmed.",
            styles["muted"],
        )
    )
    steps = piece.get("construction_steps") if isinstance(piece.get("construction_steps"), list) else []
    if not steps:
        steps = default_construction_steps(cat)
    steps = filter_construction_steps(list(steps), analysis=analysis)
    for idx, row in enumerate(steps[:40], start=1):
        if isinstance(row, dict):
            step = row.get("step", idx)
            instruction = str(row.get("instruction") or "")
            src = _fmt_source(row)
        else:
            step = idx
            instruction = str(row)
            src = "validated"
        story.append(
            Paragraph(
                f"<b>{step}.</b> {instruction} <font color='#5a6578'>({src})</font>",
                styles["body"],
            )
        )
    story.append(PageBreak())
    return story


def _build_story_v2(
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
    v2 = enrich_spec_for_manufacturing_preview(ensure_v2(spec))
    units = str(v2.get("units") or "cm")
    outfit = v2.get("outfit") if isinstance(v2.get("outfit"), dict) else {}
    pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]
    mfg = (
        (v2.get("ai") or {}).get("manufacturing_readiness")
        if isinstance(v2.get("ai"), dict)
        else {}
    )
    if not isinstance(mfg, dict):
        mfg = {}
    readiness_label = str(mfg.get("label") or READINESS_LABELS.get("DESIGN_CONCEPT", "DESIGN CONCEPT / DRAFT"))
    story: list[Any] = []

    # A. Cover
    story.append(Paragraph("FashionRise · Create Real Design Technical Pack", styles["muted"]))
    story.append(Paragraph(title or "Untitled look", styles["title"]))
    cover_prov = resolve_generation_provenance(v2)
    story.append(
        Paragraph(
            f"<b>Pack type:</b> {cover_prov['label']} · <b>Readiness:</b> {readiness_label} · "
            "Schematics NOT TO SCALE · AI completion ≠ sample-development ready",
            styles["body"],
        )
    )
    component_list = ", ".join(
        f"{(p.get('role') or p.get('category') or 'piece')}".upper()
        + f": {p.get('label') or p.get('category')}"
        for p in pieces
    ) or "—"
    story.append(
        _kv_table(
            [
                ("Style number", style_code),
                ("Revision", str(revision)),
                ("Status", status_label),
                ("Generation", cover_prov["label"]),
                ("Look ID", look_id),
                ("Size system", str(v2.get("size_system") or "—")),
                ("Sample size", str(v2.get("sample_size") or "—")),
                ("Units", units),
                ("Outfit pieces", str(outfit.get("piece_count") or len(pieces))),
                ("Components", component_list),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            str(
                v2.get("disclaimer")
                or (
                    "DRAFT / UNVERIFIED. Technical flats and pattern pieces are "
                    "PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE. Patternmaker review required."
                )
            ),
            styles["body"],
        )
    )
    story.append(Spacer(1, 6))
    cover_img = Table(
        [[_look_image(front_image or back_image, 100 * mm, 120 * mm, styles)]],
        colWidths=[110 * mm],
    )
    story.append(cover_img)
    notes = (v2.get("look_notes") or "").strip()
    if notes:
        story.append(Paragraph("Look notes", styles["h3"]))
        story.append(Paragraph(notes, styles["body"]))

    # B. Design overview
    story.append(PageBreak())
    story.append(Paragraph("Design overview", styles["h2"]))
    story.append(
        Paragraph(
            "Authenticated Magic references only. Missing opposite sides are not invented. "
            "Technical flats for manufacturing appear on component sheets.",
            styles["muted"],
        )
    )
    looks_row = Table(
        [
            [
                _side_cell("Front Magic look", front_image, styles, max_h=100 * mm),
                _side_cell("Back Magic look", back_image, styles, max_h=100 * mm),
            ]
        ],
        colWidths=[88 * mm, 88 * mm],
    )
    looks_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(looks_row)
    designer = (v2.get("designer_notes") or "").strip()
    if designer:
        story.append(Paragraph("Designer notes", styles["h3"]))
        story.append(Paragraph(designer, styles["body"]))
    prefs = v2.get("preferences") if isinstance(v2.get("preferences"), dict) else {}
    story.append(Paragraph("Shared preferences", styles["h3"]))
    story.append(
        _kv_table(
            [
                ("Fit preference", str(prefs.get("fit_preference") or "—")),
                ("Preference notes", str(prefs.get("notes") or "—")),
                ("Detection confidence", str(outfit.get("detection_confidence") or "—")),
            ],
            styles,
        )
    )
    story.append(Paragraph("Body measurements (shared)", styles["h3"]))
    story.append(
        Paragraph(
            "Body points appear once for the outfit. Do not confuse with finished-garment POMs.",
            styles["muted"],
        )
    )
    body = v2.get("body") if isinstance(v2.get("body"), dict) else {}
    story.append(
        _measurement_table(
            [
                ("Height", body.get("height")),
                ("Bust", body.get("bust")),
                ("Waist", body.get("waist")),
                ("Hip", body.get("hip")),
                ("Inseam (body)", body.get("inseam")),
            ],
            styles,
        )
    )

    warnings = [w for w in (v2.get("warnings") if isinstance(v2.get("warnings"), list) else [])]
    # Merge PDF-time compatibility warnings once (material / sleeveless POM), de-duped.
    seen_warn: set[str] = set()
    merged_warns: list[Any] = []
    for w in list(warnings) + collect_compatibility_warnings(v2):
        if isinstance(w, dict):
            key = f"{w.get('code')}|{w.get('piece_id')}|{w.get('pom')}|{w.get('message')}"
        else:
            key = str(w)
        if key in seen_warn:
            continue
        seen_warn.add(key)
        merged_warns.append(w)
    if merged_warns:
        story.append(Paragraph("Measurement review warnings", styles["h3"]))
        for w in merged_warns[:30]:
            if isinstance(w, dict):
                story.append(Paragraph(f"• {w.get('message') or w}", styles["warn"]))
            else:
                story.append(Paragraph(f"• {w}", styles["warn"]))

    # C–G per piece
    story.append(PageBreak())
    if not pieces:
        story.append(Paragraph("No garment components confirmed.", styles["body"]))
        story.append(PageBreak())
    for piece in pieces:
        story.extend(_piece_sections(piece, styles=styles, units=units))

    # H. Review / readiness (manufacturing gate)
    story.append(Paragraph("Manufacturing readiness & review", styles["h2"]))
    story.append(
        Paragraph(
            f"<b>Current readiness:</b> {readiness_label}. "
            "Levels: DESIGN CONCEPT / DRAFT → SAMPLE-DEVELOPMENT READY → PRODUCTION APPROVED "
            "(reserved for separately verified approval). "
            "AI completion alone never grants SAMPLE-DEVELOPMENT READY or PRODUCTION APPROVED.",
            styles["body"],
        )
    )
    pattern_status = mfg.get("pattern_status") if isinstance(mfg.get("pattern_status"), dict) else {}
    story.append(
        Paragraph(
            str(
                pattern_status.get("message")
                or (
                    "No production sewing pattern is supplied. Patternmaker must develop the sample pattern."
                )
            ),
            styles["warn"],
        )
    )
    missing = mfg.get("missing_required") if isinstance(mfg.get("missing_required"), list) else []
    if missing:
        story.append(Paragraph("Missing requirements for SAMPLE-DEVELOPMENT READY", styles["h3"]))
        for item in missing[:40]:
            story.append(Paragraph(f"• {item}", styles["warn"]))
    # Per-garment completeness
    story.append(Paragraph("Per-garment completeness", styles["h3"]))
    for piece in pieces:
        pid = str(piece.get("id") or "")
        label = str(piece.get("label") or piece.get("category") or pid)
        piece_issues = [
            w
            for w in (v2.get("warnings") if isinstance(v2.get("warnings"), list) else [])
            if isinstance(w, dict) and str(w.get("piece_id") or "") == pid
        ]
        status = "NEEDS REVIEW" if piece_issues else "No blocking findings on this pass (still draft)"
        story.append(Paragraph(f"<b>{label}</b> ({piece.get('category')}) — {status}", styles["body"]))
        for w in piece_issues[:12]:
            story.append(Paragraph(f"  • {w.get('message') or w}", styles["warn"]))
        # Confirmed vs proposed vs unresolved legend
        ill = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        arts = ill.get("artifacts") if isinstance(ill.get("artifacts"), dict) else {}
        if arts.get("flat_back_proposed") and not arts.get("flat_back"):
            story.append(
                Paragraph(
                    "  • Back flat is PROPOSED (no real Magic back) — designer confirmation required.",
                    styles["muted"],
                )
            )
    story.append(Paragraph("Legend", styles["h3"]))
    story.append(
        Paragraph(
            "<b>Confirmed</b> = designer-entered / checklist-checked. "
            "<b>Proposed</b> = AI or default draft (backs, generic SA, inferred closures). "
            "<b>Unresolved</b> = blocking SAMPLE-DEVELOPMENT READY until corrected.",
            styles["muted"],
        )
    )
    qc = v2.get("qc_checklist") if isinstance(v2.get("qc_checklist"), list) else []
    story.append(Paragraph("Designer confirmation checklist", styles["h3"]))
    for row in qc[:30]:
        if not isinstance(row, dict):
            continue
        mark = "[x]" if row.get("checked") else "[ ]"
        story.append(Paragraph(f"{mark} {row.get('item') or '—'}", styles["body"]))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Coordination notes: for multi-piece outfits, keep colorways and size consistency "
            "aligned across components. Patternmaker must validate seam allowances, notches, "
            "and graded sizes before any production cut. "
            "Do not treat default construction steps as approved manufacturing instructions.",
            styles["body"],
        )
    )
    prov = resolve_generation_provenance(v2)
    story.append(Paragraph("AI generation identification", styles["h3"]))
    if prov["is_professional"]:
        story.append(
            Paragraph(
                "This export includes AI Professional technical illustrations from a completed "
                "paid generation run. Still DRAFT / UNVERIFIED. Pattern sheets NOT TO SCALE.",
                styles["body"],
            )
        )
        story.append(
            _kv_table(
                [
                    ("Generation mode", prov["label"]),
                    ("AI run reference", prov["run_id"] or "—"),
                    ("Vision model", prov["vision_model"] or "—"),
                    ("Image model", prov["image_model"] or "—"),
                    (
                        "Actual cost (¢)",
                        str(prov["actual_cost_usd_cents"]) if prov["actual_cost_usd_cents"] else "—",
                    ),
                    (
                        "Paid sections",
                        ", ".join(prov["paid_sections"]) if prov["paid_sections"] else "—",
                    ),
                    (
                        "Illustration kinds",
                        ", ".join(prov["artifact_kinds"]) if prov["artifact_kinds"] else "—",
                    ),
                    ("Draft revision", str(revision)),
                    ("Notices", "DRAFT / UNVERIFIED · NOT TO SCALE"),
                ],
                styles,
            )
        )
    else:
        story.append(
            Paragraph(
                "BASIC / NO AI PROFESSIONAL GENERATED for this export. "
                "Technical drawings are heuristic or category schematics only. "
                "Preview/Download never executes paid AI.",
                styles["body"],
            )
        )
        story.append(
            _kv_table(
                [
                    ("Generation mode", prov["label"]),
                    ("Mode code", prov["mode"]),
                    ("Paid sections", "none"),
                    ("AI run reference", "—"),
                    ("Draft revision", str(revision)),
                    ("Notices", "DRAFT / UNVERIFIED · NOT TO SCALE"),
                ],
                styles,
            )
        )
    story.append(
        Paragraph(
            f"Generation mode: {prov['mode']} · Paid sections: "
            f"{', '.join(prov['paid_sections']) or 'none'}",
            styles["muted"],
        )
    )
    return story


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
    if isinstance(spec, dict) and (
        str(spec.get("schema_version") or "").startswith("2")
        or isinstance((spec.get("outfit") or {}).get("pieces"), list)
    ):
        return _build_story_v2(
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
    return _build_story_v1(
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
    # Normalize V1 drafts into V2 for export so manufacturing packs are rich.
    render_spec = ensure_v2(spec) if isinstance(spec, dict) else ensure_v2({})
    story_kwargs = dict(
        title=title,
        style_code=style_code,
        revision=revision,
        status_label=status_label,
        look_id=look_id,
        front_image=front_image,
        back_image=back_image,
        spec=render_spec,
        styles=styles,
    )

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
            f"{status_label}  ·  {style_code}  ·  Rev {revision}  ·  Schematics NOT TO SCALE",
        )
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN, 10 * mm, "FashionRise Create Real Design V3.1")
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
