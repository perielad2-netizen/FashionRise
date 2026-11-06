"""V4 Create Real Design PDF — custom / made-to-measure tailor brief.

Page flow (for bringing a design to an experienced tailor):
  1 Design brief — Magic look + reference-only body inputs (full specs)
  2 Clean large front/back flats (AI text wiped; discussion list in PDF)
  3 Design dimensions + consultation decisions
  4 Tailor measurement worksheet
  5 Fabric guidance
  6 Construction guidance + pattern-piece inventory (conditional cuts)
  7 Large pattern-development illustration
  8 Design-detail close-ups + final consultation checklist
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle

from app.services.techpack_compatibility import (
    collect_compatibility_warnings,
    filter_construction_steps,
    filter_pattern_inventory,
    material_contradiction,
)
from app.services.techpack_designer_spec import (
    detect_closure_family,
    enrich_piece_for_designer_pdf,
    finished_pom_rows,
    formal_dress_bom,
    humanize_readiness_gap,
    is_formal_dress_category,
    mtm_checklist_rows_for_piece,
    mtm_closure_statement,
    mtm_consultation_decisions,
    mtm_design_dim_keys,
    mtm_detail_focus,
    mtm_dim_priority_note,
    mtm_worksheet_rows,
)
from app.services.techpack_tailor_ready import (
    callout_legend_for_piece,
    care_icons_drawing,
    care_recommendation,
    extract_fabric_swatch,
    pantone_or_color_code,
    pattern_inventory_schematic,
    prepare_mtm_flat,
    scrub_contradictory_flat_labels,
)
from app.services.techpack_flats import (
    default_bom,
    default_construction_steps,
    flat_for_category,
    pattern_inventory_for_category,
)
from app.services.techpack_manufacturing import (
    READINESS_LABELS,
    enrich_spec_for_manufacturing_preview,
    evaluate_artifact_for_piece,
    normalize_bom_rows,
    normalize_closure_display,
    normalize_shell_material,
)
from app.services.techpack_pdf import (
    HEADER_BG,
    RULE,
    _fmt_source,
    _fmt_value,
    _kv_table,
    _look_image,
    _side_cell,
    resolve_generation_provenance,
)
from app.services.techpack_spec import ensure_v2
from app.storage.local import LocalStorageBackend


def _table(data: list[list[Any]], col_widths: list[float], styles: dict[str, Any]) -> Table:
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("GRID", (0, 0), (-1, -1), 0.35, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ]
        )
    )
    return t


def _piece_analysis(piece: dict[str, Any]) -> dict[str, Any]:
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
    return analysis if isinstance(analysis, dict) else {}


def _compact_kv(rows: list[tuple[str, str]], styles: dict[str, Any], *, width: float = 88 * mm) -> Table:
    """Fixed-width key/value table that fits nested columns (avoids 120mm overflow)."""
    col0 = 26 * mm
    data = [
        # Do not hard-truncate — Paragraph wraps so tailor-facing specs stay complete.
        [Paragraph(f"<b>{k}</b>", styles["small"]), Paragraph(v or "—", styles["small"])]
        for k, v in rows
    ]
    t = Table(data, colWidths=[col0, max(30 * mm, width - col0)])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, RULE),
                ("BACKGROUND", (0, 0), (0, -1), HEADER_BG),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return t


def _fabric_strip(
    piece: dict[str, Any],
    styles: dict[str, Any],
    *,
    swatch_path: Path | None = None,
) -> list[Any]:
    """Compact fabric / key-spec strip like industry bodycon / MK spec sheets."""
    analysis = _piece_analysis(piece)
    fab = analysis.get("fabric_estimate") if isinstance(analysis.get("fabric_estimate"), dict) else {}
    mats = piece.get("materials") if isinstance(piece.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    rows = [
        ("Silhouette", str(analysis.get("silhouette") or piece.get("label") or "—")),
        ("Neckline", str(analysis.get("neckline") or "—")),
        ("Sleeves", str(analysis.get("sleeves") or "—")),
        ("Length", str(analysis.get("length") or "—")),
        (
            "Shell / fiber",
            str(
                shell.get("composition")
                or fab.get("likely_fiber")
                or shell.get("name")
                or "—"
            ),
        ),
        (
            "GSM / hand",
            f"{shell.get('weight_gsm') or fab.get('gsm_range') or '—'} · "
            f"{str(shell.get('hand') or fab.get('hand') or '—')}",
        ),
        ("Drape", str(shell.get("drape") or fab.get("drape") or "—")),
        ("Opacity", str(shell.get("opacity") or fab.get("opacity") or "—")),
        ("Color / code", pantone_or_color_code(piece)),
        ("Fit", str(analysis.get("fit") or "—")),
    ]
    filtered = [(a, b) for a, b in rows if str(b).strip() and str(b).strip() != "—"]
    out: list[Any] = [Paragraph("Key garment / fabric specs", styles["h3"])]
    kv = _compact_kv(filtered, styles, width=140 * mm if swatch_path else 180 * mm)
    if swatch_path is not None:
        swatch = Table(
            [
                [Paragraph("<b>Fabric swatch</b> (from Magic look)", styles["small"])],
                [_look_image(swatch_path, 36 * mm, 36 * mm, styles)],
                [Paragraph("Confirm fibre / lab dip before cut", styles["muted"])],
            ],
            colWidths=[40 * mm],
        )
        row = Table([[kv, swatch]], colWidths=[140 * mm, 42 * mm])
        row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        out.append(row)
    else:
        out.append(kv)
    return out


def _art_meta(piece: dict[str, Any], kind: str) -> dict[str, Any] | None:
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    arts = illust.get("artifacts") if isinstance(illust.get("artifacts"), dict) else {}
    meta = arts.get(kind) if isinstance(arts.get(kind), dict) else None
    return meta if isinstance(meta, dict) else None


def _art_path(piece: dict[str, Any], kind: str) -> Path | None:
    meta = _art_meta(piece, kind)
    if not meta:
        return None
    decision = evaluate_artifact_for_piece(piece, kind=kind, artifact_meta=meta)
    if not decision.get("include", True) or meta.get("preview_include") is False:
        return None
    key = meta.get("storage_key")
    if not isinstance(key, str) or not key:
        return None
    return LocalStorageBackend().resolve_private_techpack_file(key=key)


def _art_exclusion_note(piece: dict[str, Any], kind: str) -> str | None:
    meta = _art_meta(piece, kind)
    if not meta:
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


def _piece_heading(piece: dict[str, Any]) -> str:
    cat = str(piece.get("category") or "other")
    label = str(piece.get("label") or cat.title())
    role = str(piece.get("role") or "").upper()
    return f"{role + ' — ' if role else ''}{label}".strip(" —")


def _cover_page(
    *,
    title: str,
    style_code: str,
    revision: int,
    status_label: str,
    look_id: str,
    front_image: Path | None,
    back_image: Path | None,
    v2: dict[str, Any],
    pieces: list[dict[str, Any]],
    styles: dict[str, Any],
) -> list[Any]:
    """Dense style sheet: meta + Magic refs + body + AI fabric (no orphan overview page)."""
    story: list[Any] = []
    mfg = (
        (v2.get("ai") or {}).get("manufacturing_readiness")
        if isinstance(v2.get("ai"), dict)
        else {}
    )
    if not isinstance(mfg, dict):
        mfg = {}
    readiness_label = str(
        mfg.get("label") or READINESS_LABELS.get("DESIGN_CONCEPT", "DESIGN CONCEPT / DRAFT")
    )
    cover_prov = resolve_generation_provenance(v2)
    prefs = v2.get("preferences") if isinstance(v2.get("preferences"), dict) else {}
    component_list = ", ".join(
        f"{(p.get('role') or p.get('category') or 'piece')}".upper()
        + f": {p.get('label') or p.get('category')}"
        for p in pieces
    ) or "—"

    story.append(Paragraph("FashionRise · CUSTOM TAILORING DESIGN BRIEF", styles["muted"]))
    story.append(Paragraph(title or "Untitled look", styles["title"]))
    story.append(
        Paragraph(
            f"<b>MADE-TO-MEASURE</b> · {cover_prov['label']} · {status_label} · "
            "Schematics NOT TO SCALE · Take this brief to a professional tailor",
            styles["small"],
        )
    )
    story.append(
        Paragraph(
            "Purpose: help a customer and tailor agree the design. The tailor takes the "
            "customer’s real measurements, drafts the sewing pattern, recommends fabric, "
            "and completes fittings. This PDF is a design brief — not a print-to-cut "
            "industrial pattern or sealed factory tech pack.",
            styles["body"],
        )
    )

    # Two-column metadata like industry tech sheets (fixed widths — no overflow).
    left_meta = _compact_kv(
        [
            ("Brand", "FashionRise"),
            ("Style name", (title or "—")[:48]),
            ("Style #", style_code),
            ("Revision", str(revision)),
            ("Look ID", look_id[:18] + "…" if len(look_id) > 20 else look_id),
            ("Components", component_list[:90]),
        ],
        styles,
        width=88 * mm,
    )
    sample_raw = str(v2.get("sample_size") or "").strip()
    sample_txt = (
        f"{sample_raw} · reference only (not customer size)"
        if sample_raw
        else "— · made-to-measure (no sample size)"
    )
    right_meta = _compact_kv(
        [
            ("Season", str(v2.get("season") or "—")),
            ("Size system", str(v2.get("size_system") or "—")),
            ("Sample size", sample_txt[:48]),
            ("Units", str(v2.get("units") or "cm")),
            ("Fit", str(prefs.get("fit_preference") or "—")),
            ("Generation", str(cover_prov.get("label") or "—")[:42]),
        ],
        styles,
        width=88 * mm,
    )
    meta_row = Table([[left_meta, right_meta]], colWidths=[90 * mm, 90 * mm])
    meta_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(meta_row)
    story.append(Spacer(1, 2))

    # Magic look + body/fabric column (fills the blank "no back" side with useful data).
    from app.services.techpack_pdf import _measurement_table

    body = v2.get("body") if isinstance(v2.get("body"), dict) else {}
    look_cell = Table(
        [
            [Paragraph("<b>Front Magic look</b>", styles["small"])],
            [_look_image(front_image or back_image, 78 * mm, 88 * mm, styles)],
        ],
        colWidths=[82 * mm],
    )
    right_bits: list[list[Any]] = [
        [
            Paragraph(
                "<b>Back Magic look</b>"
                if back_image
                else "<b>Back — not provided (AI proposes rear)</b>",
                styles["small"],
            )
        ],
    ]
    if back_image:
        right_bits.append([_look_image(back_image, 78 * mm, 55 * mm, styles)])
    else:
        right_bits.append(
            [
                Paragraph(
                    "No Magic back image. Pack invents a coherent rear flat "
                    "(PROPOSED / UNVERIFIED) — confirm before cutting.",
                    styles["warn"],
                )
            ]
        )
    right_bits.append(
        [
            Paragraph(
                "<b>Reference body inputs</b> (historical designer / croquis values — "
                "<b>NOT</b> the customer’s current measurements)",
                styles["warn"],
            )
        ]
    )
    right_bits.append(
        [
            _measurement_table(
                [
                    ("Height (ref)", body.get("height")),
                    ("Bust (ref)", body.get("bust")),
                    ("Waist (ref)", body.get("waist")),
                    ("Hip (ref)", body.get("hip")),
                    ("Inseam (ref)", body.get("inseam")),
                ],
                styles,
            )
        ]
    )
    right_bits.append(
        [
            Paragraph(
                "Authority: the tailor’s live worksheet measurements on page 3 — not this cover.",
                styles["muted"],
            )
        ]
    )
    right_cell = Table(right_bits, colWidths=[92 * mm])
    right_cell.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    hero = Table([[look_cell, right_cell]], colWidths=[84 * mm, 96 * mm])
    hero.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(hero)
    if not back_image:
        story.append(
            Paragraph(
                "<b>Proposed back:</b> No Magic back image — AI invents a coherent rear flat "
                "(PROPOSED / UNVERIFIED). Confirm before cutting.",
                styles["warn"],
            )
        )

    if pieces:
        swatch = extract_fabric_swatch(front_image or back_image)
        story.extend(_fabric_strip(pieces[0], styles, swatch_path=swatch))

    notes = (v2.get("look_notes") or "").strip()
    skip_notes = (not notes) or notes.lower().startswith("try on person preview")
    if not skip_notes:
        story.append(Paragraph(f"<b>Look notes:</b> {notes[:240]}", styles["small"]))
    designer = (v2.get("designer_notes") or "").strip()
    if designer:
        story.append(Paragraph(f"<b>Designer notes:</b> {designer[:200]}", styles["small"]))

    warn_n = len(v2.get("warnings") if isinstance(v2.get("warnings"), list) else []) + len(
        collect_compatibility_warnings(v2)
    )
    footer_bits = [
        "Made-to-measure brief · Design look · Technical flats · Design dims · Fabric guidance · Tailor checklist"
    ]
    if warn_n:
        footer_bits.insert(0, f"{warn_n} review note(s) → readiness (last page)")
    story.append(Paragraph(" · ".join(footer_bits), styles["muted"]))
    story.append(PageBreak())
    return story


def _overview_page(
    *,
    front_image: Path | None,
    back_image: Path | None,
    v2: dict[str, Any],
    styles: dict[str, Any],
) -> list[Any]:
    """Deprecated standalone overview — content merged into the style-sheet cover.

    Kept for unit tests that assert proposed-back / readiness pointer copy.
    """
    story: list[Any] = []
    story.append(Paragraph("Design overview", styles["h2"]))
    story.append(
        Paragraph(
            "Authenticated Magic references. When a back Magic look is missing, AI proposes a "
            "rear flat for sampling (clearly marked proposed).",
            styles["muted"],
        )
    )
    if not back_image:
        story.append(
            Paragraph(
                "<b>Proposed back:</b> No Magic back image — the pack invents a coherent rear "
                "flat and construction for sampling (marked PROPOSED / UNVERIFIED).",
                styles["warn"],
            )
        )
    warn_n = len(v2.get("warnings") if isinstance(v2.get("warnings"), list) else []) + len(
        collect_compatibility_warnings(v2)
    )
    if warn_n:
        story.append(
            Paragraph(
                f"{warn_n} measurement / review note(s) — see Manufacturing readiness at the end of this pack.",
                styles["muted"],
            )
        )
    story.append(PageBreak())
    return story


def _flats_page(piece: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
    """Large clean front/back flats — AI text wiped; discussion list lives in the PDF."""
    story: list[Any] = []
    heading = _piece_heading(piece)
    cat = str(piece.get("category") or "other")
    closure_family = detect_closure_family(piece)
    story.append(Paragraph(f"Technical flats — {heading}", styles["h2"]))
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    arts = illust.get("artifacts") if isinstance(illust.get("artifacts"), dict) else {}
    front_art = _art_path(piece, "flat_front")
    back_art = _art_path(piece, "flat_back") or _art_path(piece, "flat_back_proposed")
    professional = str(illust.get("mode") or "") == "professional" and front_art is not None
    analysis = _piece_analysis(piece)

    story.append(
        Paragraph(
            (
                "<b>UNVERIFIED concept illustrations.</b> Burned-in AI text has been cleared so "
                "the garment is readable. Use the discussion list below — not labels inside the "
                "drawing — and treat the written brief as authoritative."
                if professional
                else "Category schematics — run AI Professional for source-faithful flats."
            ),
            styles["muted"],
        )
    )
    if analysis.get("back_construction_proposal") and arts.get("flat_back_proposed") and not arts.get("flat_back"):
        back_txt = str(analysis.get("back_construction_proposal") or "")
        if closure_family == "wrap":
            import re as _re

            back_txt = _re.sub(
                r"[^.]*\b(?:invisible\s+)?zip(?:per)?\b[^.]*\.",
                "",
                back_txt,
                flags=_re.I,
            ).strip()
            back_txt = (
                f"{back_txt} "
                "WRAP CLOSURE: proposed back must NOT introduce a CB zipper unless the designer "
                "explicitly confirms one — current pack assumes sash/tie wrap only."
            ).strip()
        story.append(
            Paragraph(
                f"<b>Proposed back (UNVERIFIED):</b> {back_txt[:360]}",
                styles["small"],
            )
        )
    if closure_family == "wrap" or is_formal_dress_category(cat):
        story.append(
            Paragraph(
                "<b>Front ↔ back coherence:</b> Treat front and back as one dress. If the "
                "asymmetric drape wraps toward the back, the proposed back must show that "
                "continuation; if the panel hangs only at the front, the back must stay clean. "
                "Do not invent a different silhouette between views.",
                styles["muted"],
            )
        )

    # Always wipe burned-in AI markers for MTM — never re-stamp numbered callouts
    # onto the drawing (that recreates the half-erased annotation look).
    callouts = callout_legend_for_piece(piece)[:8]
    front_show = prepare_mtm_flat(front_art) if front_art else None
    front_show = front_show or front_art
    back_show = prepare_mtm_flat(back_art) if back_art else None
    back_show = back_show or back_art

    front_img = (
        _look_image(front_show, 92 * mm, 145 * mm, styles)
        if front_show
        else flat_for_category(cat, back=False)
    )
    if back_show:
        back_label = (
            "PROPOSED BACK (UNVERIFIED)"
            if arts.get("flat_back_proposed") and not arts.get("flat_back")
            else "BACK"
        )
        back_img = _look_image(back_show, 92 * mm, 145 * mm, styles)
    else:
        back_label = "BACK (schematic)"
        back_img = flat_for_category(cat, back=True)

    flats_block = Table(
        [
            [
                Paragraph("<b>FRONT</b>", styles["body"]),
                Paragraph(f"<b>{back_label}</b>", styles["body"]),
            ],
            [front_img, back_img],
        ],
        colWidths=[94 * mm, 94 * mm],
    )
    flats_block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(flats_block)

    story.append(Paragraph("Design details to discuss", styles["h3"]))
    story.append(
        Paragraph(
            "Clean illustration — no on-drawing numbers. Use this written list only. "
            "Confirm exact placement at the fitting.",
            styles["muted"],
        )
    )
    legend_rows: list[list[Any]] = [
        [
            Paragraph("<b>Design detail</b>", styles["small"]),
            Paragraph("<b>Design detail</b>", styles["small"]),
        ]
    ]
    mid = (len(callouts) + 1) // 2
    left_c = callouts[:mid]
    right_c = callouts[mid:]
    for i in range(max(len(left_c), len(right_c))):
        _ln, ll = left_c[i] if i < len(left_c) else ("", "")
        _rn, rl = right_c[i] if i < len(right_c) else ("", "")
        legend_rows.append(
            [
                Paragraph(f"• {ll}"[:110] if ll else "", styles["small"]),
                Paragraph(f"• {rl}"[:110] if rl else "", styles["small"]),
            ]
        )
    story.append(_table(legend_rows, [92 * mm, 92 * mm], styles))

    if arts.get("flat_back_proposed") and not arts.get("flat_back"):
        story.append(
            Paragraph(
                "<b>PROPOSED BACK:</b> Confirm rear construction before the first toile.",
                styles["warn"],
            )
        )

    for kind, label in (
        ("flat_front", "Front flat"),
        ("flat_back", "Back flat"),
        ("flat_back_proposed", "Proposed back flat"),
    ):
        note = _art_exclusion_note(piece, kind)
        if note and _art_path(piece, kind) is None and _art_meta(piece, kind):
            story.append(
                Paragraph(
                    f"<b>MISSING / EXCLUDED ({label}):</b> {note} Original preserved.",
                    styles["warn"],
                )
            )
    story.append(PageBreak())
    return story


def _pom_page(piece: dict[str, Any], *, units: str, sample_size: str, styles: dict[str, Any]) -> list[Any]:
    """Made-to-measure: category-aware design dimensions + tailor worksheet."""
    story: list[Any] = []
    heading = _piece_heading(piece)
    cat = str(piece.get("category") or "other")
    story.append(Paragraph(f"Design dimensions & tailor measurements — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            f"<b>MADE-TO-MEASURE.</b> The tailor takes the customer’s actual body measurements "
            f"({units}) and drafts the pattern. FashionRise does <b>not</b> provide sealed "
            "production size grades. Values below are <b>design intent</b> for this "
            f"<b>{cat}</b> — AI estimates are starting points only.",
            styles["body"],
        )
    )

    closure_family = detect_closure_family(piece)
    story.append(Paragraph("Fastening / closure", styles["h3"]))
    level, statement = mtm_closure_statement(piece)
    story.append(Paragraph(statement, styles["warn"] if level == "warn" else styles["body"]))

    # Design-critical dimensions — category-filtered (no dress sash/slit on shirts/jeans).
    story.append(Paragraph("Unique design dimensions (optional starting points)", styles["h3"]))
    story.append(
        Paragraph(
            "Values are <b>AI / design estimates only</b>. The tailor and customer set the final "
            f"numbers. {mtm_dim_priority_note(cat)}",
            styles["muted"],
        )
    )
    finished = finished_pom_rows(piece)
    by_key = {str(r.get("key")): r for r in finished}
    dim_header = [
        Paragraph("<b>Feature</b>", styles["small"]),
        Paragraph("<b>Starting point (cm)</b>", styles["small"]),
        Paragraph("<b>Source</b>", styles["small"]),
        Paragraph("<b>How to interpret</b>", styles["small"]),
        Paragraph("<b>Agreed</b>", styles["small"]),
    ]
    dim_data: list[list[Any]] = [dim_header]
    for key in mtm_design_dim_keys(cat):
        row = by_key.get(key)
        if not row:
            continue
        if key == "v_depth":
            neck = by_key.get("neckline")
            if (
                neck
                and isinstance(neck.get("value"), (int, float))
                and isinstance(row.get("value"), (int, float))
                and float(neck["value"]) == float(row["value"])
            ):
                continue
        val = row.get("value")
        status = str(row.get("source") or "").lower()
        review = str(row.get("review_status") or "").lower()
        if val in (None, "", "—"):
            val_txt = "TO AGREE"
            src_txt = "missing"
        elif status in {"ai", "ai_vision", "ai_inferred", "estimate", "calculated"} or review in {
            "proposed",
            "needs_review",
            "open",
        }:
            val_txt = f"{float(val):g}" if isinstance(val, (int, float)) else str(val)
            src_txt = "Optional AI estimate"
        else:
            val_txt = f"{float(val):g}" if isinstance(val, (int, float)) else str(val)
            src_txt = status or "noted"
        how = str(row.get("how_to") or "")
        dim_data.append(
            [
                Paragraph(str(row.get("label") or key), styles["small"]),
                Paragraph(val_txt, styles["small"]),
                Paragraph(src_txt, styles["small"]),
                Paragraph(how, styles["small"]),
                Paragraph("☐ ____ cm", styles["small"]),
            ]
        )
    if len(dim_data) == 1:
        dim_data.append(
            [
                Paragraph("—", styles["small"]),
                Paragraph("TO AGREE", styles["small"]),
                Paragraph("—", styles["small"]),
                Paragraph(mtm_dim_priority_note(cat), styles["small"]),
                Paragraph("☐", styles["small"]),
            ]
        )
    story.append(_table(dim_data, [30 * mm, 24 * mm, 28 * mm, 70 * mm, 28 * mm], styles))

    story.append(Paragraph("Consultation decisions (agree at the appointment)", styles["h3"]))
    story.append(
        Paragraph(
            "Garment-specific decisions for this piece. One value and one approval status per row.",
            styles["muted"],
        )
    )
    decision_rows: list[list[Any]] = [
        [
            Paragraph("<b>Decision</b>", styles["small"]),
            Paragraph("<b>Agreed value / choice</b>", styles["small"]),
            Paragraph("<b>Status</b>", styles["small"]),
            Paragraph("<b>Initials</b>", styles["small"]),
        ]
    ]
    for label, prompt in mtm_consultation_decisions(piece):
        decision_rows.append(
            [
                Paragraph(label, styles["small"]),
                Paragraph(prompt, styles["small"]),
                Paragraph("☐ open  ☐ agreed" if "Other changes" not in label else "☐ noted", styles["small"]),
                Paragraph("____", styles["small"]),
            ]
        )
    story.append(_table(decision_rows, [40 * mm, 78 * mm, 36 * mm, 20 * mm], styles))
    # Keep worksheet on the same flow when short categories leave space; still page-break
    # after decisions so multi-piece packs stay readable.
    story.append(PageBreak())

    story.append(Paragraph(f"Tailor measurement worksheet — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            f"Record live body measurements for this <b>{cat}</b>. These override cover reference "
            "values. Pattern, ease, and grading are the tailor’s responsibility.",
            styles["muted"],
        )
    )
    ws = [
        [
            Paragraph("<b>Measurement</b>", styles["small"]),
            Paragraph("<b>Value</b>", styles["small"]),
            Paragraph("<b>Unit / notes</b>", styles["small"]),
        ]
    ]
    for label, unit in mtm_worksheet_rows(piece):
        ws.append(
            [
                Paragraph(label, styles["small"]),
                Paragraph("____________________", styles["small"]),
                Paragraph(unit or "____________________", styles["small"]),
            ]
        )
    story.append(_table(ws, [68 * mm, 48 * mm, 64 * mm], styles))
    _ = sample_size
    _ = closure_family
    story.append(PageBreak())
    return story


def _bom_page(piece: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
    story: list[Any] = []
    heading = _piece_heading(piece)
    cat = str(piece.get("category") or "other")
    color = str(piece.get("color_hint") or "")
    story.append(Paragraph(f"Fabric guidance & materials — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            "These are <b>recommended fabric characteristics</b> for the look — not a locked "
            "purchase order. The tailor should recommend and source the actual material with "
            "the customer (drape, weight, opacity, stretch).",
            styles["body"],
        )
    )
    closure_family = detect_closure_family(piece)
    piece_n = normalize_shell_material(piece)
    mats = piece_n.get("materials") if isinstance(piece_n.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    lining = mats.get("lining") if isinstance(mats.get("lining"), dict) else {}
    analysis = _piece_analysis(piece)
    fab = analysis.get("fabric_estimate") if isinstance(analysis.get("fabric_estimate"), dict) else {}
    shell_name = str(shell.get("name") or shell.get("suggestion") or fab.get("likely_fiber") or "To select with tailor")
    composition = str(shell.get("composition") or fab.get("composition") or "To agree — fibre TBD")
    story.append(Paragraph("Recommended fabric characteristics", styles["h3"]))
    story.append(
        _kv_table(
            [
                ("Look color (reference)", str(piece_n.get("color_hint") or color or "—")),
                ("Suggested hand / drape", str(fab.get("hand") or fab.get("drape") or shell.get("hand") or "Fluid, soft drape preferred")),
                (
                    "Suggested weight",
                    str(
                        shell.get("weight_gsm")
                        or shell.get("gsm")
                        or fab.get("gsm")
                        or (
                            "Medium — enough body for wrap edges"
                            if closure_family == "wrap" or is_formal_dress_category(cat)
                            else (
                                "Denim mid-weight — confirm oz with tailor"
                                if cat in {"trousers", "shorts", "jeans"}
                                else "Light–medium shirting / shell — confirm GSM with tailor"
                            )
                        )
                    ),
                ),
                ("Opacity", str(fab.get("opacity") or "Check in one layer; line if sheer")),
                ("Stretch", str(fab.get("stretch") or "Low–moderate; stretch knit changes the pattern")),
                ("Lining", str(lining.get("name") or "Recommend if shell is sheer or clingy — tailor decides")),
                ("Example fibres (suggestions only)", composition),
            ],
            styles,
        )
    )
    story.append(
        Paragraph(
            "<b>Care:</b> provisional until fabric is chosen. Follow the supplier care label for the "
            "selected cloth — do not treat the icons in this pack as final care instructions.",
            styles["muted"],
        )
    )
    if closure_family == "wrap":
        story.append(
            Paragraph(
                "<b>Fastening reminder:</b> wrap/tie is the working assumption. Optional hidden "
                "snap only if customer + tailor agree. No zipper unless explicitly chosen.",
                styles["warn"],
            )
        )
    elif closure_family == "button":
        story.append(
            Paragraph(
                "<b>Fastening reminder:</b> button-front is proposed from the look. Confirm "
                "button count and placket with the tailor before locking the sample.",
                styles["muted"],
            )
        )
    elif closure_family == "fly":
        story.append(
            Paragraph(
                "<b>Fastening reminder:</b> front fly is proposed from the look. Keep zipper / "
                "waistband details as proposed until the appointment confirms them.",
                styles["muted"],
            )
        )
    bom = piece.get("bom") if isinstance(piece.get("bom"), list) else []
    if not bom:
        bom = (
            formal_dress_bom(
                color_hint=color,
                closure_family=detect_closure_family(piece),
            )
            if is_formal_dress_category(cat)
            else default_bom(cat, color_hint=color)
        )
    bom = normalize_bom_rows(bom, piece=piece)
    # Drop factory packing / mass-production rows from the tailor brief.
    skip_tokens = (
        "polybag",
        "carton",
        "hangtag",
        "supplier",
        "main / size / care labels",
        "care labels",
    )
    slim: list[dict[str, Any]] = []
    for row in bom:
        if not isinstance(row, dict):
            continue
        item = str(row.get("item") or row.get("name") or "").lower()
        if any(tok in item for tok in skip_tokens):
            continue
        slim.append(row)
    story.append(Paragraph("Materials checklist (discuss with tailor)", styles["h3"]))
    data = [
        [
            Paragraph("<b>Item</b>", styles["small"]),
            Paragraph("<b>Guidance</b>", styles["small"]),
            Paragraph("<b>Status</b>", styles["small"]),
        ]
    ]
    for row in slim[:20]:
        item = str(row.get("item") or row.get("name") or "—")
        guidance = str(row.get("description") or row.get("notes") or "—")[:160]
        status = "Proposed — confirm"
        if str(row.get("review_status") or "") == "needs_review":
            status = "Needs customer / tailor decision"
        data.append(
            [
                Paragraph(item, styles["small"]),
                Paragraph(guidance, styles["small"]),
                Paragraph(status, styles["small"]),
            ]
        )
    story.append(_table(data, [48 * mm, 100 * mm, 36 * mm], styles))
    if detect_closure_family(piece) == "wrap" or is_formal_dress_category(cat):
        story.append(
            Paragraph(
                "Stay tape / clear elastic is recommended on deep-V and wrap edges. "
                "Trims and notions are selected with the tailor — this brief does not lock suppliers.",
                styles["muted"],
            )
        )
    else:
        story.append(
            Paragraph(
                "Trims and notions are selected with the tailor — this brief does not lock suppliers.",
                styles["muted"],
            )
        )
    story.append(PageBreak())
    return story


def _construction_page(piece: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
    story: list[Any] = []
    heading = _piece_heading(piece)
    cat = str(piece.get("category") or "other")
    closure_family = detect_closure_family(piece)
    story.append(Paragraph(f"Construction guidance — {heading}", styles["h2"]))
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
    steps = piece.get("construction_steps") if isinstance(piece.get("construction_steps"), list) else []
    if not steps:
        steps = default_construction_steps(cat)
    steps = filter_construction_steps(list(steps), analysis=analysis)
    # Wrap dresses: drop zip-install steps that contradict the declared wrap closure.
    if closure_family == "wrap":
        filtered_steps: list[Any] = []
        for step in steps:
            blob = (
                " ".join(
                    str(step.get(k) or "")
                    for k in ("operation", "instruction", "notes", "stitch_type")
                ).lower()
                if isinstance(step, dict)
                else str(step).lower()
            )
            if "zip" in blob or "zipper" in blob:
                continue
            filtered_steps.append(step)
        steps = filtered_steps
    story.append(
        Paragraph(
            "<b>GUIDANCE ONLY — not a compulsory sew procedure.</b> An experienced tailor "
            "chooses stitch types, seam allowances, and sequence from the actual fabric, "
            "fit, and pattern. The outline below is a discussion aid for the appointment.",
            styles["warn"],
        )
    )

    # Slim MTM table — operations + notes only (no SPI/SA that look like factory orders).
    data = [
        [
            Paragraph("<b>#</b>", styles["small"]),
            Paragraph("<b>Suggested operation (discuss)</b>", styles["small"]),
            Paragraph("<b>Tailor notes / alternatives</b>", styles["small"]),
        ]
    ]
    for idx, row in enumerate(steps[:12], start=1):
        if isinstance(row, dict):
            op = str(row.get("operation") or row.get("instruction") or "—")
            notes = str(row.get("notes") or "")
            stitch = str(row.get("stitch_type") or "").strip()
            if stitch and stitch.lower() not in notes.lower():
                notes = (f"Typical: {stitch}. " + notes).strip()
            step_no = row.get("step", idx)
        else:
            op = str(row)
            notes = ""
            step_no = idx
        data.append(
            [
                Paragraph(str(step_no), styles["small"]),
                Paragraph(op, styles["small"]),
                Paragraph(notes or "Tailor decides method for fabric / fit", styles["small"]),
            ]
        )
    # Cap sew-guidance length so inventory can share this page (denser layout).
    story.append(_table(data, [12 * mm, 95 * mm, 75 * mm], styles))
    story.append(
        Paragraph(
            "Stitch classes, SPI/SPCM, and seam allowances are intentionally omitted as "
            "mandatory fields — lock them only after fabric and pattern are chosen.",
            styles["muted"],
        )
    )

    # Pattern-piece inventory on the same page as construction (reduces empty pages).
    illust2 = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    analysis2 = illust2.get("analysis") if isinstance(illust2.get("analysis"), dict) else {}
    patterns = piece.get("pattern_pieces") if isinstance(piece.get("pattern_pieces"), list) else []
    if not patterns:
        patterns = pattern_inventory_for_category(cat)
    patterns = filter_pattern_inventory(
        [p for p in patterns if isinstance(p, dict)],
        analysis=analysis2,
        ai_suggested=analysis2.get("pattern_pieces_suggested")
        if isinstance(analysis2.get("pattern_pieces_suggested"), list)
        else None,
    )
    story.append(Paragraph(f"Pattern-piece inventory — {heading}", styles["h3"]))
    story.append(
        Paragraph(
            "<b>NOT A PRINTABLE SEWING PATTERN.</b> IDs below must match the next-page "
            "illustration (or ID map). The tailor drafts the real pattern from customer "
            "measurements. Open choices (fold vs CB seam) must be agreed before the toile.",
            styles["warn"],
        )
    )
    pdata = [
        [
            Paragraph("<b>ID</b>", styles["small"]),
            Paragraph("<b>Name</b>", styles["small"]),
            Paragraph("<b>Cut qty</b>", styles["small"]),
            Paragraph("<b>Fabric</b>", styles["small"]),
            Paragraph("<b>Grain / fold</b>", styles["small"]),
            Paragraph("<b>Status</b>", styles["small"]),
            Paragraph("<b>Notes</b>", styles["small"]),
        ]
    ]
    review_labels = {
        "proposed_unverified": "Proposed · unverified",
        "proposed": "Proposed",
        "approved_template": "Approved template",
        "needs_review": "Open choice",
        "ai_suggested": "AI suggested",
        "designer_confirmed": "Designer confirmed",
    }
    for row in patterns[:18]:
        cut = row.get("cut_qty")
        review = str(row.get("review_state") or row.get("source") or "—")
        review_txt = review_labels.get(review.lower(), review.replace("_", " "))
        pdata.append(
            [
                Paragraph(str(row.get("id") or "—"), styles["small"]),
                Paragraph(str(row.get("name") or "—"), styles["small"]),
                Paragraph("—" if cut is None else str(cut), styles["small"]),
                Paragraph(str(row.get("fabric") or "shell"), styles["small"]),
                Paragraph(
                    f"{row.get('grainline') or 'straight'} / {row.get('fold') or 'none'}",
                    styles["small"],
                ),
                Paragraph(review_txt, styles["small"]),
                Paragraph(str(row.get("notes") or "—")[:90], styles["small"]),
            ]
        )
    story.append(
        _table(pdata, [10 * mm, 26 * mm, 22 * mm, 14 * mm, 28 * mm, 24 * mm, 58 * mm], styles)
    )
    story.append(
        Paragraph(
            "Full-page piece-breakdown illustration follows — examine at readable size.",
            styles["muted"],
        )
    )
    story.append(PageBreak())
    return story


def _pattern_visual_page(piece: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
    """Full-page pattern-piece illustration (or honest ID map when art is missing)."""
    story: list[Any] = []
    heading = _piece_heading(piece)
    cat = str(piece.get("category") or "other")
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
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

    story.append(Paragraph(f"Piece-breakdown illustration — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            "Large visual breakdown of the pieces needed to construct this garment. "
            "Match each drawn piece to the inventory IDs on the previous page. "
            "NOT TO SCALE · NOT a printable sewing pattern.",
            styles["muted"],
        )
    )
    pattern_art = _art_path(piece, "pattern_sheet")
    pattern_excl = _art_exclusion_note(piece, "pattern_sheet")
    if pattern_art is not None:
        # ID key first so piece A/B/C stay tied to the large illustration on one page.
        id_bits = [
            f"{row.get('id') or '?'}={str(row.get('name') or '')[:24]}"
            for row in patterns[:10]
            if isinstance(row, dict)
        ]
        if id_bits:
            story.append(
                Paragraph(
                    "<b>Inventory key:</b> " + " · ".join(id_bits),
                    styles["small"],
                )
            )
        clean = prepare_mtm_flat(pattern_art) or pattern_art
        story.append(_look_image(clean, 180 * mm, 205 * mm, styles))
    elif pattern_excl:
        story.append(
            Paragraph(
                f"<b>MISSING / EXCLUDED:</b> {pattern_excl} Original preserved.",
                styles["warn"],
            )
        )
        story.append(pattern_inventory_schematic(patterns, category=cat))
    else:
        story.append(
            Paragraph(
                "<b>Full piece-breakdown illustration was not generated for this run.</b> "
                "The ID map below is a planning aid only — it is <b>not</b> equivalent to the "
                "large cutting illustration. Use Magic look + flats + inventory with the tailor.",
                styles["warn"],
            )
        )
        story.append(pattern_inventory_schematic(patterns, category=cat))
        from app.services.techpack_pdf import _cutting_layout_schematic

        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                "Optional fabric-width / grain planning sketch (also not a cutting pattern):",
                styles["muted"],
            )
        )
        story.append(_cutting_layout_schematic(cat))
    story.append(PageBreak())
    return story


def _design_details_page(piece: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
    """Large design-detail close-ups — visual explanation, not approved sew instructions."""
    story: list[Any] = []
    heading = _piece_heading(piece)
    story.append(Paragraph(f"Design-detail close-ups — {heading}", styles["h2"]))
    focus = mtm_detail_focus(piece)
    focus_titles = ", ".join(t for t, _ in focus[:4])
    story.append(
        Paragraph(
            f"<b>UNVERIFIED visual references</b> for this garment — {focus_titles}. "
            "Not approved construction instructions; the tailor chooses the method.",
            styles["muted"],
        )
    )
    detail_art = _art_path(piece, "detail_callouts")
    detail_excl = _art_exclusion_note(piece, "detail_callouts")
    detail_meta = _art_meta(piece, "detail_callouts")
    detail_decision = evaluate_artifact_for_piece(
        piece, kind="detail_callouts", artifact_meta=detail_meta
    )
    if detail_art is not None and detail_decision.get("include", True) and not detail_excl:
        clean = prepare_mtm_flat(detail_art) or scrub_contradictory_flat_labels(
            detail_art, wipe_all_text=True, always_banner=False
        ) or detail_art
        story.append(_look_image(clean, 180 * mm, 155 * mm, styles))
    elif detail_excl:
        story.append(Paragraph(f"<b>MISSING / EXCLUDED:</b> {detail_excl}", styles["warn"]))
    else:
        story.append(
            Paragraph(
                "Detail sheet not generated — use the Magic look and large flats with the "
                "discussion points below.",
                styles["muted"],
            )
        )

    story.append(Paragraph("What to examine in the close-ups", styles["h3"]))
    rows = [
        [
            Paragraph("<b>Detail</b>", styles["small"]),
            Paragraph("<b>What the tailor should confirm</b>", styles["small"]),
        ]
    ]
    for title, note in focus:
        rows.append(
            [Paragraph(title, styles["small"]), Paragraph(note, styles["small"])]
        )
    story.append(_table(rows, [48 * mm, 132 * mm], styles))
    story.append(PageBreak())
    return story


def _colorways_page(pieces: list[dict[str, Any]], styles: dict[str, Any]) -> list[Any]:
    """Colorways block without forced page break (merged into factory close)."""
    story: list[Any] = []
    story.append(Paragraph("Colorways by component", styles["h3"]))
    story.append(
        Paragraph(
            "Textile color reference (Pantone TCX / lab dip) required before production — not color name alone.",
            styles["muted"],
        )
    )
    data = [
        [
            Paragraph("<b>Component</b>", styles["small"]),
            Paragraph("<b>Colorway 1</b>", styles["small"]),
            Paragraph("<b>Color code</b>", styles["small"]),
            Paragraph("<b>CW2 / CW3</b>", styles["small"]),
        ]
    ]
    for piece in pieces:
        label = _piece_heading(piece)
        color = str(piece.get("color_hint") or "—")
        code = pantone_or_color_code(piece)
        data.append(
            [
                Paragraph(f"{label} — shell", styles["small"]),
                Paragraph(color, styles["small"]),
                Paragraph(code[:60], styles["small"]),
                Paragraph("— / —", styles["small"]),
            ]
        )
        trim_label = (
            f"{label} — lining / thread / sash"
            if detect_closure_family(piece) == "wrap"
            else f"{label} — lining / thread / closure"
        )
        data.append(
            [
                Paragraph(trim_label, styles["small"]),
                Paragraph("match / TBD", styles["small"]),
                Paragraph("match shell · confirm", styles["small"]),
                Paragraph("— / —", styles["small"]),
            ]
        )
    story.append(_table(data, [50 * mm, 35 * mm, 55 * mm, 30 * mm], styles))
    return story


def _labels_packing_page(styles: dict[str, Any], *, pieces: list[dict[str, Any]] | None = None) -> list[Any]:
    """Labels + care icons without forced page break (merged into factory close)."""
    story: list[Any] = []
    story.append(Paragraph("Labels, care & packing", styles["h3"]))
    story.append(
        Paragraph(
            "Measure label positions from a fixed seam or edge. Care symbols follow ISO 3758 "
            "(schematic icons below — confirm market language).",
            styles["muted"],
        )
    )
    if pieces:
        care = care_recommendation(pieces[0])
        story.append(care_icons_drawing())
        story.append(
            _compact_kv(
                [
                    ("Wash", care["wash"]),
                    ("Bleach", care["bleach"]),
                    ("Dry", care["dry"]),
                    ("Iron", care["iron"]),
                    ("Dry clean", care["dry_clean"]),
                ],
                styles,
                width=180 * mm,
            )
        )
    data = [
        [
            Paragraph("<b>Label</b>", styles["small"]),
            Paragraph("<b>Position (from)</b>", styles["small"]),
            Paragraph("<b>Size / material</b>", styles["small"]),
            Paragraph("<b>Attachment</b>", styles["small"]),
        ],
        [
            Paragraph("Main label", styles["small"]),
            Paragraph("CB lining neck — TBD cm below seam", styles["small"]),
            Paragraph("TBD", styles["small"]),
            Paragraph("Sewn", styles["small"]),
        ],
        [
            Paragraph("Size label", styles["small"]),
            Paragraph("With main or side seam", styles["small"]),
            Paragraph("TBD", styles["small"]),
            Paragraph("Sewn", styles["small"]),
        ],
        [
            Paragraph("Care label", styles["small"]),
            Paragraph("Side seam LH", styles["small"]),
            Paragraph("Fibre + care symbols", styles["small"]),
            Paragraph("Sewn", styles["small"]),
        ],
        [
            Paragraph("Hangtag", styles["small"]),
            Paragraph("Hanger loop / side seam", styles["small"]),
            Paragraph("Brand card", styles["small"]),
            Paragraph("String / fastener", styles["small"]),
        ],
    ]
    story.append(_table(data, [32 * mm, 55 * mm, 45 * mm, 40 * mm], styles))
    story.append(Paragraph("Packing", styles["h3"]))
    story.append(
        _kv_table(
            [
                ("Fold method", "Tissue / bust pad as fabric requires — TBD"),
                ("Polybag", "Clear, warning text as market requires"),
                ("Units per polybag", "1"),
                ("Carton marks", "Style · size · qty · destination"),
                ("Care content", "Fibre composition + ISO care symbols — confirm market language"),
            ],
            styles,
        )
    )
    return story


def _final_consultation_checklist(
    *,
    style_code: str,
    revision: int,
    v2: dict[str, Any],
    pieces: list[dict[str, Any]],
    styles: dict[str, Any],
) -> list[Any]:
    """Garment-aware final checklist + space for handwritten appointment notes."""
    story: list[Any] = []
    story.append(Paragraph("Final consultation checklist", styles["h2"]))
    story.append(
        Paragraph(
            "Approve each garment separately, then the complete outfit. FashionRise provides "
            "the design brief; the tailor owns measurements, pattern, fabric, and fittings.",
            styles["body"],
        )
    )

    rows: list[list[Any]] = [
        [
            Paragraph("<b>Decision</b>", styles["small"]),
            Paragraph("<b>What to agree</b>", styles["small"]),
            Paragraph("<b>Status</b>", styles["small"]),
            Paragraph("<b>Approved by</b>", styles["small"]),
        ]
    ]
    for piece in pieces:
        for label, prompt in mtm_checklist_rows_for_piece(piece):
            rows.append(
                [
                    Paragraph(label, styles["small"]),
                    Paragraph(prompt, styles["small"]),
                    Paragraph("☐ open  ☐ agreed", styles["small"]),
                    Paragraph("Cust ____  Tailor ____", styles["small"]),
                ]
            )
    if len(pieces) > 1:
        labels = [
            str(p.get("label") or p.get("category") or "piece").strip()
            for p in pieces
            if isinstance(p, dict)
        ]
        outfit_txt = " + ".join(labels[:4]) if labels else "all pieces"
        rows.append(
            [
                Paragraph("OUTFIT", styles["small"]),
                Paragraph(
                    f"{outfit_txt} look right together — proportions, colour, styling",
                    styles["small"],
                ),
                Paragraph("☐ open  ☐ agreed", styles["small"]),
                Paragraph("Cust ____  Tailor ____", styles["small"]),
            ]
        )
    rows.append(
        [
            Paragraph("Body measurements", styles["small"]),
            Paragraph(
                "Live tailor worksheet(s) completed — cover reference body values are NOT authority",
                styles["small"],
            ),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("Tailor ____", styles["small"]),
        ]
    )
    rows.append(
        [
            Paragraph("Next step", styles["small"]),
            Paragraph("Draft pattern → toile → fit → cut fashion fabric", styles["small"]),
            Paragraph("☐ scheduled", styles["small"]),
            Paragraph("Tailor ____", styles["small"]),
        ]
    )
    story.append(_table(rows, [36 * mm, 74 * mm, 32 * mm, 40 * mm], styles))

    story.append(Paragraph("Appointment notes (handwritten)", styles["h3"]))
    note_rows = [
        [
            Paragraph("<b>Topic</b>", styles["small"]),
            Paragraph("<b>Notes / final decision</b>", styles["small"]),
        ]
    ]
    for _ in range(8):
        note_rows.append(
            [
                Paragraph("____________________", styles["small"]),
                Paragraph("________________________________________________", styles["small"]),
            ]
        )
    story.append(_table(note_rows, [50 * mm, 132 * mm], styles))
    story.append(
        Paragraph(
            "Customer signature ______________  Tailor signature ______________  Date __________",
            styles["body"],
        )
    )

    # MTM briefs: do not dump factory readiness leftovers (sample grades, sew-order
    # mandates) that contradict the consultation checklist above.
    mfg = (
        (v2.get("ai") or {}).get("manufacturing_readiness")
        if isinstance(v2.get("ai"), dict)
        else {}
    )
    if not isinstance(mfg, dict):
        mfg = {}
    readiness_label = str(
        mfg.get("label") or READINESS_LABELS.get("DESIGN_CONCEPT", "DESIGN CONCEPT / DRAFT")
    )
    skip_tokens = (
        "sample size",
        "sample cut",
        "production",
        "tolerance",
        "sew-order",
        "construction / sew",
        "construction decisions",
        "finished poms",
        "designer confirmation checklist",
        "manufacturing specs",
        "generic defaults",
    )
    open_items: list[str] = []
    seen_human: set[str] = set()
    for item in (mfg.get("missing_required") if isinstance(mfg.get("missing_required"), list) else [])[:20]:
        human = humanize_readiness_gap(str(item))
        low = human.lower()
        if human in seen_human or any(tok in low for tok in skip_tokens):
            continue
        seen_human.add(human)
        open_items.append(human)

    story.append(
        Paragraph(
            f"<b>Brief status:</b> {readiness_label}. Rev {revision} · {style_code}. "
            "This pack is ready for a tailor consultation when the rows above are agreed. "
            "Industrial grading, supplier refs, and packing specs are intentionally omitted.",
            styles["body"],
        )
    )
    if open_items:
        story.append(
            Paragraph(
                "Additional notes: " + " · ".join(open_items[:4]),
                styles["muted"],
            )
        )

    story.append(
        Paragraph(
            f"Revision {revision} · Create Real Design · custom tailoring brief · {style_code} · FashionRise",
            styles["muted"],
        )
    )
    return story


def _revision_and_readiness(
    *,
    style_code: str,
    revision: int,
    v2: dict[str, Any],
    pieces: list[dict[str, Any]],
    styles: dict[str, Any],
) -> list[Any]:
    """Back-compat alias — final page is now a single consultation checklist."""
    return _final_consultation_checklist(
        style_code=style_code,
        revision=revision,
        v2=v2,
        pieces=pieces,
        styles=styles,
    )


def build_story_v4_designer(
    *,
    title: str,
    style_code: str,
    revision: int,
    status_label: str,
    look_id: str,
    front_image: Path | None,
    back_image: Path | None,
    spec: dict[str, Any],
    styles: dict[str, Any],
) -> list[Any]:
    v2 = enrich_spec_for_manufacturing_preview(ensure_v2(spec))
    units = str(v2.get("units") or "cm")
    sample_size = str(v2.get("sample_size") or "")
    outfit = v2.get("outfit") if isinstance(v2.get("outfit"), dict) else {}
    raw_pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]
    pieces = [enrich_piece_for_designer_pdf(p) for p in raw_pieces]

    story: list[Any] = []
    story.extend(
        _cover_page(
            title=title,
            style_code=style_code,
            revision=revision,
            status_label=status_label,
            look_id=look_id,
            front_image=front_image,
            back_image=back_image,
            v2=v2,
            pieces=pieces,
            styles=styles,
        )
    )
    if not pieces:
        story.append(Paragraph("No garment components confirmed.", styles["body"]))
        story.append(PageBreak())
    for piece in pieces:
        story.extend(_flats_page(piece, styles))
        story.extend(_pom_page(piece, units=units, sample_size=sample_size, styles=styles))
        story.extend(_bom_page(piece, styles))
        story.extend(_construction_page(piece, styles))
        story.extend(_pattern_visual_page(piece, styles))
        story.extend(_design_details_page(piece, styles))
    # Single final consultation checklist — no repeated warning pages.
    story.extend(
        _final_consultation_checklist(
            style_code=style_code,
            revision=revision,
            v2=v2,
            pieces=pieces,
            styles=styles,
        )
    )
    return story
