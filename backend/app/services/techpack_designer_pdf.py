"""V4 Create Real Design PDF — custom / made-to-measure tailor brief.

Page flow (for bringing a design to an experienced tailor):
  1 Design brief — Magic look + reference-only body inputs
  2 Large scrubbed technical flats (no contradictory zipper stamps)
  3 Design dimensions + practical tailor worksheet + consultation changes
  4 Fabric guidance
  5 Construction guidance (not compulsory) + illustrative pattern inventory
  6 Single final consultation checklist
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
)
from app.services.techpack_tailor_ready import (
    annotate_flat_callouts,
    callout_legend_for_piece,
    care_icons_drawing,
    care_recommendation,
    extract_fabric_swatch,
    pantone_or_color_code,
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
        [Paragraph(f"<b>{k}</b>", styles["small"]), Paragraph((v or "—")[:160], styles["small"])]
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
        ("Silhouette", str(analysis.get("silhouette") or piece.get("label") or "—")[:110]),
        ("Neckline", str(analysis.get("neckline") or "—")[:90]),
        ("Sleeves", str(analysis.get("sleeves") or "—")[:70]),
        ("Length", str(analysis.get("length") or "—")[:70]),
        (
            "Shell / fiber",
            str(
                shell.get("composition")
                or fab.get("likely_fiber")
                or shell.get("name")
                or "—"
            )[:110],
        ),
        ("GSM / hand", f"{shell.get('weight_gsm') or fab.get('gsm_range') or '—'} · {str(shell.get('hand') or fab.get('hand') or '—')[:50]}"),
        ("Drape", str(shell.get("drape") or fab.get("drape") or "—")[:70]),
        ("Opacity", str(shell.get("opacity") or fab.get("opacity") or "—")[:70]),
        ("Color / code", pantone_or_color_code(piece)[:90]),
        ("Fit", str(analysis.get("fit") or "—")[:90]),
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
    """Large front/back flats for the tailor — fewer, clearer views; no crowded overlays."""
    story: list[Any] = []
    heading = _piece_heading(piece)
    cat = str(piece.get("category") or "other")
    closure_family = detect_closure_family(piece)
    story.append(Paragraph(f"Technical flats — {heading}", styles["h2"]))
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    arts = illust.get("artifacts") if isinstance(illust.get("artifacts"), dict) else {}
    front_art = _art_path(piece, "flat_front")
    back_art = _art_path(piece, "flat_back") or _art_path(piece, "flat_back_proposed")
    detail_art = _art_path(piece, "detail_callouts")
    professional = str(illust.get("mode") or "") == "professional" and front_art is not None
    analysis = _piece_analysis(piece)

    story.append(
        Paragraph(
            (
                "Large garment views for the tailor · DRAFT / UNVERIFIED visual reference. "
                "The written brief is authoritative — do not treat burned-in AI construction "
                "labels as approved instructions."
                if professional
                else "Category schematics — run AI Professional for source-faithful flats."
            ),
            styles["muted"],
        )
    )
    if analysis.get("back_construction_proposal") and arts.get("flat_back_proposed") and not arts.get("flat_back"):
        back_txt = str(analysis.get("back_construction_proposal") or "")
        if closure_family == "wrap":
            # Do not present invented CB zip as wrap-compatible construction.
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

    # Wrap / MTM: scrub contradictory zipper stamps; skip red numbered overlays that crowd the art.
    callouts = callout_legend_for_piece(piece)[:8]
    if closure_family == "wrap":
        front_show = (
            scrub_contradictory_flat_labels(front_art) if front_art else None
        ) or front_art
        back_show = (
            scrub_contradictory_flat_labels(back_art) if back_art else None
        ) or back_art
    else:
        front_show = annotate_flat_callouts(front_art, callouts, side="left") if front_art else None
        front_show = front_show or front_art
        back_show = annotate_flat_callouts(back_art, callouts, side="right") if back_art else None
        back_show = back_show or back_art

    front_img = (
        _look_image(front_show, 92 * mm, 130 * mm, styles)
        if front_show
        else flat_for_category(cat, back=False)
    )
    if back_show:
        back_label = (
            "PROPOSED BACK (UNVERIFIED)"
            if arts.get("flat_back_proposed") and not arts.get("flat_back")
            else "BACK"
        )
        back_img = _look_image(back_show, 92 * mm, 130 * mm, styles)
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
    if closure_family == "wrap":
        story.append(
            Paragraph(
                "No numbered overlay on the drawings (keeps the garment readable). "
                "Use this short list with the customer — the tailor confirms exact placement "
                "when drafting the pattern.",
                styles["muted"],
            )
        )
    legend_rows: list[list[Any]] = [
        [
            Paragraph("<b>#</b>", styles["small"]),
            Paragraph("<b>Design detail</b>", styles["small"]),
            Paragraph("<b>#</b>", styles["small"]),
            Paragraph("<b>Design detail</b>", styles["small"]),
        ]
    ]
    mid = (len(callouts) + 1) // 2
    left_c = callouts[:mid]
    right_c = callouts[mid:]
    for i in range(max(len(left_c), len(right_c))):
        ln, ll = left_c[i] if i < len(left_c) else ("", "")
        rn, rl = right_c[i] if i < len(right_c) else ("", "")
        legend_rows.append(
            [
                Paragraph(str(ln), styles["small"]),
                Paragraph(str(ll)[:90], styles["small"]),
                Paragraph(str(rn), styles["small"]),
                Paragraph(str(rl)[:90], styles["small"]),
            ]
        )
    story.append(_table(legend_rows, [10 * mm, 82 * mm, 10 * mm, 82 * mm], styles))

    if arts.get("flat_back_proposed") and not arts.get("flat_back"):
        story.append(
            Paragraph(
                "<b>PROPOSED BACK:</b> Confirm rear construction before the first toile.",
                styles["warn"],
            )
        )

    # Crowded detail sheets often re-introduce zipper stamps + tiny overlapping labels.
    # For wrap MTM briefs, prefer the large flats above; skip the duplicate detail collage.
    if closure_family == "wrap":
        story.append(
            Paragraph(
                "Detail collage omitted for clarity — the original Magic look (page 1) and "
                "the large flats above are the visual references for this consultation.",
                styles["muted"],
            )
        )
    else:
        story.append(Paragraph("Detail callouts / construction close-ups", styles["h3"]))
        detail_excl = _art_exclusion_note(piece, "detail_callouts")
        detail_meta = _art_meta(piece, "detail_callouts")
        detail_decision = evaluate_artifact_for_piece(
            piece, kind="detail_callouts", artifact_meta=detail_meta
        )
        show_detail = bool(
            detail_art
            or (
                isinstance(detail_meta, dict)
                and detail_decision.get("include")
                and not detail_excl
            )
        )
        if show_detail and detail_art is not None:
            scrubbed_detail = scrub_contradictory_flat_labels(detail_art) or detail_art
            if not detail_decision.get("manufacturing_evidence"):
                story.append(
                    Paragraph(
                        "<b>UNVERIFIED DETAIL ART</b> — reviewable; not designer-approved manufacturing evidence.",
                        styles["warn"],
                    )
                )
            story.append(_look_image(scrubbed_detail, 178 * mm, 88 * mm, styles))
        elif detail_excl:
            story.append(Paragraph(f"<b>MISSING / EXCLUDED:</b> {detail_excl}", styles["warn"]))
        else:
            story.append(
                Paragraph(
                    "Detail sheet not generated — annotate neckline, closure, darts, hem on flats.",
                    styles["muted"],
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


_MTM_DESIGN_DIM_KEYS = (
    "neckline",
    "v_depth",
    "wrap_overlap",
    "slit_start",
    "overlay_length",
    "sash_width",
    "sash_length",
    "hem_high",
    "hem_low",
    "garment_length",
)


def _pom_page(piece: dict[str, Any], *, units: str, sample_size: str, styles: dict[str, Any]) -> list[Any]:
    """Made-to-measure: unique design dimensions + blank tailor measurement worksheet."""
    story: list[Any] = []
    heading = _piece_heading(piece)
    story.append(Paragraph(f"Design dimensions & tailor measurements — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            f"<b>MADE-TO-MEASURE.</b> The tailor takes the customer’s actual body measurements "
            f"({units}) and drafts the pattern. FashionRise does <b>not</b> provide sealed "
            "production size grades. Values below are <b>design intent</b> for features the "
            "customer must agree with the tailor — AI estimates are starting points only.",
            styles["body"],
        )
    )

    # Fastening — one authoritative statement for wrap.
    closure_family = detect_closure_family(piece)
    story.append(Paragraph("Fastening / closure", styles["h3"]))
    if closure_family == "wrap":
        story.append(
            Paragraph(
                "<b>Appears to be a WRAP / TIE dress</b> (no visible zipper in the Magic look). "
                "Final fastening — sash/tie only, optional hidden snap, or another method — "
                "<b>must be agreed with the tailor</b>. Do not assume an invisible zipper "
                "unless the customer and tailor explicitly choose one.",
                styles["warn"],
            )
        )
    elif closure_family == "zip":
        story.append(
            Paragraph(
                "Design appears to use a zipper closure. Confirm type, length, and placement "
                "with the tailor before cutting.",
                styles["body"],
            )
        )
    else:
        story.append(
            Paragraph(
                "Closure is unresolved. Customer and tailor must agree fastening before the first toile.",
                styles["warn"],
            )
        )

    # Design-critical dimensions only.
    story.append(Paragraph("Unique design dimensions (agree with customer)", styles["h3"]))
    finished = finished_pom_rows(piece)
    by_key = {str(r.get("key")): r for r in finished}
    dim_header = [
        Paragraph("<b>Feature</b>", styles["small"]),
        Paragraph("<b>Suggested (cm)</b>", styles["small"]),
        Paragraph("<b>Source</b>", styles["small"]),
        Paragraph("<b>How to interpret</b>", styles["small"]),
        Paragraph("<b>Agreed with tailor</b>", styles["small"]),
    ]
    dim_data: list[list[Any]] = [dim_header]
    for key in _MTM_DESIGN_DIM_KEYS:
        row = by_key.get(key)
        if not row:
            continue
        # Skip empty v_depth if neckline already listed with same value.
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
            src_txt = "AI estimate"
        else:
            val_txt = f"{float(val):g}" if isinstance(val, (int, float)) else str(val)
            src_txt = status or "noted"
        how = str(row.get("how_to") or "")[:120]
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
                Paragraph("Discuss neckline, slit, wrap, length with tailor.", styles["small"]),
                Paragraph("☐", styles["small"]),
            ]
        )
    story.append(_table(dim_data, [32 * mm, 22 * mm, 20 * mm, 78 * mm, 28 * mm], styles))

    # Blank tailor worksheet — practical appointment space.
    story.append(Paragraph("Tailor measurement worksheet (fill at fitting)", styles["h3"]))
    story.append(
        Paragraph(
            "Record the customer’s live body measurements here. These values override any "
            "reference numbers on the cover. Pattern, ease, and grading are the tailor’s responsibility.",
            styles["muted"],
        )
    )
    blank_rows = [
        ("Date / tailor", ""),
        ("Customer name", ""),
        ("Height", "cm"),
        ("Bust (body circ)", "cm"),
        ("Underbust (if needed)", "cm"),
        ("Waist (body circ)", "cm"),
        ("High hip", "cm"),
        ("Hip (body circ)", "cm"),
        ("Across front", "cm"),
        ("Across back", "cm"),
        ("Back width / back length (nape→waist)", "cm"),
        ("Shoulder width", "cm"),
        ("Arm length (shoulder→wrist)", "cm"),
        ("Upper arm circ", "cm"),
        ("Wrist / cuff", "cm"),
        ("Waist → knee", "cm"),
        ("Waist → floor / preferred hem", "cm"),
        ("Preferred finished length (HPS→hem)", "cm"),
        ("Ease / fit preference notes", ""),
    ]
    ws = [
        [
            Paragraph("<b>Measurement</b>", styles["small"]),
            Paragraph("<b>Value</b>", styles["small"]),
            Paragraph("<b>Unit / notes</b>", styles["small"]),
        ]
    ]
    for label, unit in blank_rows:
        ws.append(
            [
                Paragraph(label, styles["small"]),
                Paragraph("____________________", styles["small"]),
                Paragraph(unit or "____________________", styles["small"]),
            ]
        )
    story.append(_table(ws, [68 * mm, 48 * mm, 64 * mm], styles))

    story.append(Paragraph("Consultation changes (design decisions at the appointment)", styles["h3"]))
    story.append(
        Paragraph(
            "Use this block to lock the look with the customer. One value and one approval status "
            "per feature — update the design-dimension table above if anything changes.",
            styles["muted"],
        )
    )
    decision_rows = [
        [
            Paragraph("<b>Decision</b>", styles["small"]),
            Paragraph("<b>Agreed value / choice</b>", styles["small"]),
            Paragraph("<b>Status</b>", styles["small"]),
            Paragraph("<b>Initials</b>", styles["small"]),
        ],
        [
            Paragraph("Fastening", styles["small"]),
            Paragraph("wrap/tie only · optional snap · other: ______", styles["small"]),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("____", styles["small"]),
        ],
        [
            Paragraph("Back construction", styles["small"]),
            Paragraph("cut on fold · CB seam · other: ______", styles["small"]),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("____", styles["small"]),
        ],
        [
            Paragraph("Sash width × length", styles["small"]),
            Paragraph("______ cm × ______ cm", styles["small"]),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("____", styles["small"]),
        ],
        [
            Paragraph("Neckline / V depth", styles["small"]),
            Paragraph("______ cm", styles["small"]),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("____", styles["small"]),
        ],
        [
            Paragraph("Wrap overlap / slit / hems", styles["small"]),
            Paragraph("notes: ________________________", styles["small"]),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("____", styles["small"]),
        ],
        [
            Paragraph("Fabric / lining choice", styles["small"]),
            Paragraph("______________________________", styles["small"]),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("____", styles["small"]),
        ],
        [
            Paragraph("Other changes this visit", styles["small"]),
            Paragraph("______________________________", styles["small"]),
            Paragraph("☐ noted", styles["small"]),
            Paragraph("____", styles["small"]),
        ],
    ]
    story.append(_table(decision_rows, [40 * mm, 78 * mm, 36 * mm, 20 * mm], styles))
    _ = sample_size  # retained for API compatibility; not used for MTM grading
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
                ("Suggested weight", str(shell.get("weight_gsm") or shell.get("gsm") or fab.get("gsm") or "Medium — enough body for wrap edges")),
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
    story.append(
        Paragraph(
            "Stay tape / clear elastic is recommended on deep-V and wrap edges. "
            "Trims and notions are selected with the tailor — this brief does not lock suppliers.",
            styles["muted"],
        )
    )
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
    for idx, row in enumerate(steps[:24], start=1):
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
    story.append(_table(data, [12 * mm, 95 * mm, 75 * mm], styles))
    story.append(
        Paragraph(
            "Stitch classes, SPI/SPCM, and seam allowances are intentionally omitted as "
            "mandatory fields — lock them only after fabric and pattern are chosen.",
            styles["muted"],
        )
    )

    # Pattern inventory — illustrative only for MTM.
    story.append(Paragraph("Illustrative pattern pieces (NOT a sewing pattern)", styles["h3"]))
    story.append(
        Paragraph(
            "The tailor drafts the real pattern from customer measurements. "
            "The list below only communicates the design’s piece breakdown. "
            "Where fold vs center-back seam (or sash size) conflicts appear, treat them as "
            "<b>open choices</b> — agree one option on the consultation worksheet.",
            styles["warn"],
        )
    )
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
    pdata = [
        [
            Paragraph("<b>ID</b>", styles["small"]),
            Paragraph("<b>Name</b>", styles["small"]),
            Paragraph("<b>Cut</b>", styles["small"]),
            Paragraph("<b>Fabric</b>", styles["small"]),
            Paragraph("<b>Grain / fold</b>", styles["small"]),
            Paragraph("<b>Review</b>", styles["small"]),
            Paragraph("<b>Notes</b>", styles["small"]),
        ]
    ]
    review_labels = {
        "proposed_unverified": "Proposed · unverified",
        "proposed": "Proposed",
        "approved_template": "Approved template",
        "needs_review": "Needs review",
        "ai_suggested": "AI suggested",
        "designer_confirmed": "Designer confirmed",
    }
    for row in patterns[:30]:
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
                Paragraph(str(row.get("notes") or "—"), styles["small"]),
            ]
        )
    story.append(
        _table(pdata, [12 * mm, 28 * mm, 10 * mm, 16 * mm, 28 * mm, 28 * mm, 50 * mm], styles)
    )

    story.append(Paragraph("Pattern-development sketch (NOT TO SCALE)", styles["h3"]))
    story.append(
        Paragraph(
            "Visual aid for piece shapes only — the tailor drafts the cuttable pattern.",
            styles["muted"],
        )
    )
    pattern_art = _art_path(piece, "pattern_sheet")
    pattern_excl = _art_exclusion_note(piece, "pattern_sheet")
    if pattern_art is not None:
        story.append(
            Paragraph(
                "AI pattern-development schematic — NOT TO SCALE — PATTERNMAKER VALIDATION REQUIRED.",
                styles["warn"],
            )
        )
        story.append(_look_image(pattern_art, 160 * mm, 110 * mm, styles))
    elif pattern_excl:
        story.append(
            Paragraph(
                f"<b>MISSING / EXCLUDED:</b> {pattern_excl} Original preserved.",
                styles["warn"],
            )
        )
    else:
        story.append(
            Paragraph(
                "Pattern-sheet illustration was not generated for this run. "
                "Use the inventory above with the Magic look and flats to brief the patternmaker.",
                styles["muted"],
            )
        )
        # Honest placeholder — never present generic boxes as a cutter marker.
        from app.services.techpack_pdf import _cutting_layout_schematic

        story.append(_cutting_layout_schematic(cat))

    # QC moved to factory close so it never orphans under cutting art.
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
    """Single final checklist — no repeated warning blocks across pages."""
    story: list[Any] = []
    story.append(Paragraph("Final consultation checklist", styles["h2"]))
    story.append(
        Paragraph(
            "One checklist for the appointment. Mark each row agreed or still open. "
            "FashionRise provides the design brief; the tailor owns measurements, pattern, "
            "fabric recommendation, and fittings.",
            styles["body"],
        )
    )

    wrap_pieces = [p for p in pieces if detect_closure_family(p) == "wrap"]
    has_proposed_back = any(
        isinstance((p.get("illustrations") or {}).get("artifacts"), dict)
        and (p.get("illustrations") or {}).get("artifacts", {}).get("flat_back_proposed")
        and not (p.get("illustrations") or {}).get("artifacts", {}).get("flat_back")
        for p in pieces
        if isinstance(p, dict)
    )

    rows: list[list[Any]] = [
        [
            Paragraph("<b>Decision</b>", styles["small"]),
            Paragraph("<b>What to agree</b>", styles["small"]),
            Paragraph("<b>Status</b>", styles["small"]),
            Paragraph("<b>Approved by</b>", styles["small"]),
        ],
        [
            Paragraph("Fastening", styles["small"]),
            Paragraph(
                "Wrap/tie only, optional hidden snap, or another method — no zipper unless chosen"
                if wrap_pieces
                else "Confirm closure type, length, and placement",
                styles["small"],
            ),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("Cust ____  Tailor ____", styles["small"]),
        ],
        [
            Paragraph("Back construction", styles["small"]),
            Paragraph(
                (
                    "Choose cut-on-fold OR center-back seam"
                    + (" · proposed back is UNVERIFIED" if has_proposed_back else "")
                ),
                styles["small"],
            ),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("Cust ____  Tailor ____", styles["small"]),
        ],
        [
            Paragraph("Design dimensions", styles["small"]),
            Paragraph(
                "Neckline/V, wrap overlap, slit, overlay, sash width×length, hem lengths "
                "(one value each — update worksheet if changed)",
                styles["small"],
            ),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("Cust ____  Tailor ____", styles["small"]),
        ],
        [
            Paragraph("Body measurements", styles["small"]),
            Paragraph(
                "Live tailor worksheet completed — cover reference body values are NOT authority",
                styles["small"],
            ),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("Tailor ____", styles["small"]),
        ],
        [
            Paragraph("Fabric & lining", styles["small"]),
            Paragraph(
                "Drape, weight, opacity, stretch, lining — care remains provisional until cloth is chosen",
                styles["small"],
            ),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("Cust ____  Tailor ____", styles["small"]),
        ],
        [
            Paragraph("Construction method", styles["small"]),
            Paragraph(
                "Tailor selects stitch / seam approach for the chosen fabric — pack outline is guidance only",
                styles["small"],
            ),
            Paragraph("☐ open  ☐ agreed", styles["small"]),
            Paragraph("Tailor ____", styles["small"]),
        ],
        [
            Paragraph("Illustrations", styles["small"]),
            Paragraph(
                "Treat AI flats as unverified visual references — written brief wins on conflicts",
                styles["small"],
            ),
            Paragraph("☐ noted", styles["small"]),
            Paragraph("Cust ____  Tailor ____", styles["small"]),
        ],
        [
            Paragraph("Next step", styles["small"]),
            Paragraph("Draft pattern → toile → fit → cut fashion fabric", styles["small"]),
            Paragraph("☐ scheduled", styles["small"]),
            Paragraph("Tailor ____", styles["small"]),
        ],
    ]
    story.append(_table(rows, [32 * mm, 78 * mm, 32 * mm, 40 * mm], styles))

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
