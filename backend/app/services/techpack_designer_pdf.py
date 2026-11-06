"""V4 Designer-perfect Create Real Design PDF — dense industry tech-pack layout.

Page flow (inspired by factory spec sheets / GarmentSpec practice):
  1 Style sheet — compact meta + Magic refs + body + AI fabric strip (one page)
  2+ Per garment: flats + callout legend beside · POM · BOM · construction + cutting
  Closing — colorways + labels + revision + readiness (merged, no orphan blanks)
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
    FORMAL_DRESS_CALLOUTS,
    FORMAL_DRESS_QC,
    GRADE_SIZES,
    enrich_piece_for_designer_pdf,
    finished_pom_rows,
    formal_dress_bom,
    is_formal_dress_category,
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


def _fabric_strip(piece: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
    """Compact fabric / key-spec strip like industry bodycon / MK spec sheets."""
    analysis = _piece_analysis(piece)
    fab = analysis.get("fabric_estimate") if isinstance(analysis.get("fabric_estimate"), dict) else {}
    mats = piece.get("materials") if isinstance(piece.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    rows = [
        ("Silhouette", str(analysis.get("silhouette") or piece.get("label") or "—")[:140]),
        ("Neckline", str(analysis.get("neckline") or "—")[:100]),
        ("Sleeves / length", f"{analysis.get('sleeves') or '—'} · {analysis.get('length') or '—'}"),
        (
            "Shell / fiber",
            str(
                shell.get("composition")
                or fab.get("likely_fiber")
                or shell.get("name")
                or "—"
            )[:140],
        ),
        ("GSM / hand", f"{shell.get('weight_gsm') or fab.get('gsm_range') or '—'} · {shell.get('hand') or fab.get('hand') or '—'}"),
        ("Drape / opacity", f"{shell.get('drape') or fab.get('drape') or '—'} · {shell.get('opacity') or fab.get('opacity') or '—'}"),
        ("Color", str(piece.get("color_hint") or "—")),
        ("Fit", str(analysis.get("fit") or "—")),
    ]
    out: list[Any] = [Paragraph("Key garment / fabric specs", styles["h3"])]
    out.append(
        _kv_table([(a, b) for a, b in rows if str(b).strip() and str(b).strip() != "—"], styles)
    )
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

    story.append(Paragraph("FashionRise · GARMENT TECH SHEET", styles["muted"]))
    story.append(Paragraph(title or "Untitled look", styles["title"]))
    story.append(
        Paragraph(
            f"<b>{cover_prov['label']}</b> · {readiness_label} · {status_label} · "
            "Schematics NOT TO SCALE · Sample-development pack",
            styles["small"],
        )
    )

    # Two-column metadata like industry tech sheets (left identity / right sample).
    left_meta = _kv_table(
        [
            ("Brand", "FashionRise"),
            ("Style name", title or "—"),
            ("Style number", style_code),
            ("Revision", str(revision)),
            ("Look ID", look_id[:18] + "…" if len(look_id) > 20 else look_id),
            ("Components", component_list[:160]),
        ],
        styles,
    )
    right_meta = _kv_table(
        [
            ("Season / drop", str(v2.get("season") or "—")),
            ("Size system", str(v2.get("size_system") or "—")),
            ("Sample size", str(v2.get("sample_size") or "—")),
            ("Units", str(v2.get("units") or "cm")),
            ("Fit preference", str(prefs.get("fit_preference") or "—")),
            ("Generation", cover_prov["label"]),
        ],
        styles,
    )
    meta_row = Table([[left_meta, right_meta]], colWidths=[90 * mm, 90 * mm])
    meta_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(meta_row)
    story.append(Spacer(1, 3))

    # Magic refs + body side-by-side (dense overview, not a separate sparse page).
    from app.services.techpack_pdf import _measurement_table

    body = v2.get("body") if isinstance(v2.get("body"), dict) else {}
    looks = Table(
        [
            [
                _side_cell("Front Magic look", front_image, styles, max_h=72 * mm),
                _side_cell(
                    "Back Magic look" if back_image else "Back — not provided (AI proposes)",
                    back_image,
                    styles,
                    max_h=72 * mm,
                ),
            ]
        ],
        colWidths=[90 * mm, 90 * mm],
    )
    looks.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(looks)
    if not back_image:
        story.append(
            Paragraph(
                "<b>Proposed back:</b> No Magic back — pack invents a coherent rear flat "
                "(PROPOSED / UNVERIFIED). Confirm before cutting.",
                styles["warn"],
            )
        )

    body_and_specs: list[Any] = [
        Paragraph("Body measurements (shared — not finished POMs)", styles["h3"]),
        _measurement_table(
            [
                ("Height", body.get("height")),
                ("Bust", body.get("bust")),
                ("Waist", body.get("waist")),
                ("Hip", body.get("hip")),
                ("Inseam (body)", body.get("inseam")),
            ],
            styles,
        ),
    ]
    if pieces:
        body_and_specs.extend(_fabric_strip(pieces[0], styles))
    story.extend(body_and_specs)

    notes = (v2.get("look_notes") or "").strip()
    skip_notes = (not notes) or notes.lower().startswith("try on person preview")
    if not skip_notes:
        story.append(Paragraph(f"<b>Look notes:</b> {notes[:320]}", styles["small"]))
    designer = (v2.get("designer_notes") or "").strip()
    if designer:
        story.append(Paragraph(f"<b>Designer notes:</b> {designer[:280]}", styles["small"]))

    warn_n = len(v2.get("warnings") if isinstance(v2.get("warnings"), list) else []) + len(
        collect_compatibility_warnings(v2)
    )
    if warn_n:
        story.append(
            Paragraph(
                f"{warn_n} measurement / review note(s) → Manufacturing readiness (last page).",
                styles["muted"],
            )
        )
    story.append(
        Paragraph(
            "Pack: Style sheet · Flats &amp; callouts · POM · BOM · Construction &amp; cutting · "
            "Factory close (colorways / labels / readiness).",
            styles["muted"],
        )
    )
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
    """Flats + callout legend side-by-side (MK-style), then detail callouts — no orphan legend page."""
    story: list[Any] = []
    heading = _piece_heading(piece)
    cat = str(piece.get("category") or "other")
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
                "AI PROFESSIONAL flats · DRAFT / UNVERIFIED · annotate callout #s on flats before factory send."
                if professional
                else "Category schematics — run AI Professional for source-faithful flats."
            ),
            styles["muted"],
        )
    )
    if analysis.get("back_construction_proposal") and arts.get("flat_back_proposed") and not arts.get("flat_back"):
        story.append(
            Paragraph(
                f"<b>Proposed back:</b> {str(analysis.get('back_construction_proposal'))[:280]}",
                styles["small"],
            )
        )

    front_img = (
        _look_image(front_art, 62 * mm, 95 * mm, styles)
        if front_art
        else flat_for_category(cat, back=False)
    )
    if back_art:
        back_label = (
            "PROPOSED BACK"
            if arts.get("flat_back_proposed") and not arts.get("flat_back")
            else "BACK"
        )
        back_img = _look_image(back_art, 62 * mm, 95 * mm, styles)
    else:
        back_label = "BACK (schematic)"
        back_img = flat_for_category(cat, back=True)

    flats_block = Table(
        [
            [
                Paragraph("<b>FRONT</b>", styles["small"]),
                Paragraph(f"<b>{back_label}</b>", styles["small"]),
            ],
            [front_img, back_img],
        ],
        colWidths=[66 * mm, 66 * mm],
    )
    flats_block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    # Right-rail callout / POM legend (industry spec-sheet density).
    legend_rows: list[list[Any]] = [
        [
            Paragraph("<b>#</b>", styles["small"]),
            Paragraph("<b>Callout / POM point</b>", styles["small"]),
        ]
    ]
    callouts = list(FORMAL_DRESS_CALLOUTS) if is_formal_dress_category(cat) else [
        ("1", "Neckline / collar finish"),
        ("2", "Shoulder / armhole"),
        ("3", "Side seam / closure"),
        ("4", "Hem finish"),
        ("5", "Special feature (slit / pocket / trim)"),
    ]
    # Append distinctive AI features as extra callouts when present.
    features = analysis.get("distinctive_features") if isinstance(analysis.get("distinctive_features"), list) else []
    extra_n = len(callouts)
    for feat in features[:6]:
        extra_n += 1
        callouts.append((str(extra_n), str(feat)[:90]))
    for num, label in callouts:
        legend_rows.append(
            [Paragraph(str(num), styles["small"]), Paragraph(str(label)[:110], styles["small"])]
        )
    # POM codes quick reference
    pom_bits = []
    for row in finished_pom_rows(piece)[:10]:
        val = row.get("value")
        if val in (None, ""):
            continue
        pom_bits.append(f"{row.get('code')}: {val:g}" if isinstance(val, float) else f"{row.get('code')}: {val}")
    legend_cells: list[list[Any]] = [
        [Paragraph("<b>Callout / POM legend</b>", styles["small"])],
        [_table(legend_rows, [8 * mm, 40 * mm], styles)],
    ]
    if pom_bits:
        legend_cells.append([Paragraph("<b>Base POM values</b>", styles["small"])])
        legend_cells.append([Paragraph(" · ".join(pom_bits)[:420], styles["small"])])
    legend_block = Table(legend_cells, colWidths=[52 * mm])
    legend_block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    rail = Table([[flats_block, legend_block]], colWidths=[134 * mm, 52 * mm])
    rail.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(rail)

    if arts.get("flat_back_proposed") and not arts.get("flat_back"):
        story.append(
            Paragraph(
                "<b>PROPOSED BACK:</b> Confirm rear construction before sampling.",
                styles["warn"],
            )
        )

    # Detail callouts — keep the fabric/detail sheet the user likes, full width.
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
        if not detail_decision.get("manufacturing_evidence"):
            story.append(
                Paragraph(
                    "<b>UNVERIFIED DETAIL ART</b> — reviewable; not designer-approved manufacturing evidence.",
                    styles["warn"],
                )
            )
        story.append(_look_image(detail_art, 178 * mm, 78 * mm, styles))
    elif detail_excl:
        story.append(Paragraph(f"<b>MISSING / EXCLUDED:</b> {detail_excl}", styles["warn"]))
    else:
        story.append(
            Paragraph(
                "Detail sheet not generated — annotate neckline, zip, darts, hem, straps on flats.",
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


def _pom_page(piece: dict[str, Any], *, units: str, sample_size: str, styles: dict[str, Any]) -> list[Any]:
    """Dense POM table — base + tol only (no empty grade dash columns that waste width)."""
    story: list[Any] = []
    heading = _piece_heading(piece)
    story.append(Paragraph(f"Points of measure — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            f"Finished-garment POMs ({units}), measured flat. Sample size <b>{sample_size or '—'}</b>. "
            "Half measurements edge-to-edge unless noted full circumference. "
            f"Grade columns ({', '.join(GRADE_SIZES)}) filled after sample seal — not invented here.",
            styles["muted"],
        )
    )
    rows = finished_pom_rows(piece)
    header = [
        Paragraph("<b>Code</b>", styles["small"]),
        Paragraph("<b>POM</b>", styles["small"]),
        Paragraph("<b>How to measure</b>", styles["small"]),
        Paragraph(f"<b>Base ({sample_size or 'sample'})</b>", styles["small"]),
        Paragraph("<b>Tol ±</b>", styles["small"]),
        Paragraph("<b>Source</b>", styles["small"]),
    ]
    data: list[list[Any]] = [header]
    if not rows:
        story.append(
            Paragraph(
                "No finished measurements recorded — enter POMs before sampling.",
                styles["warn"],
            )
        )
    for row in rows:
        val = row["value"]
        if val is None or val == "":
            base_txt = "—"
        elif isinstance(val, float):
            base_txt = f"{val:g}"
        else:
            base_txt = str(val)
        review = str(row.get("review_status") or "")
        if review == "needs_review":
            base_txt = f"{base_txt} · REVIEW"
        how = str(row["how_to"])
        if len(how) > 140:
            how = how[:137] + "…"
        data.append(
            [
                Paragraph(str(row["code"]), styles["small"]),
                Paragraph(str(row["label"]), styles["small"]),
                Paragraph(how, styles["small"]),
                Paragraph(base_txt, styles["small"]),
                Paragraph(f"{row['tolerance_cm']:g}", styles["small"]),
                Paragraph(_fmt_source({"source": row.get("source")}), styles["small"]),
            ]
        )
    story.append(_table(data, [12 * mm, 36 * mm, 78 * mm, 22 * mm, 14 * mm, 20 * mm], styles))
    story.append(PageBreak())
    return story


def _bom_page(piece: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
    story: list[Any] = []
    heading = _piece_heading(piece)
    cat = str(piece.get("category") or "other")
    color = str(piece.get("color_hint") or "")
    story.append(Paragraph(f"Bill of materials — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            "List every material and trim down to thread and polybag. "
            "Color codes: Pantone TCX, supplier number, or lab-dip reference — never color name alone for production.",
            styles["muted"],
        )
    )
    piece_n = normalize_shell_material(piece)
    mats = piece_n.get("materials") if isinstance(piece_n.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    lining = mats.get("lining") if isinstance(mats.get("lining"), dict) else {}
    closures = normalize_closure_display(
        piece_n.get("closures") if isinstance(piece_n.get("closures"), dict) else {}
    )
    shell_name = str(shell.get("name") or shell.get("suggestion") or "Not confirmed")
    composition = str(shell.get("composition") or "Unknown / not confirmed")
    story.append(
        _kv_table(
            [
                ("Garment color", str(piece_n.get("color_hint") or color or "—")),
                ("Shell material", shell_name if shell_name.strip() not in ("", "—") else "Not confirmed"),
                ("Composition", composition),
                ("Weight / GSM", str(shell.get("weight_gsm") or shell.get("gsm") or "not confirmed")),
                ("Lining", str(lining.get("name") or "—")),
                ("Closure", str(closures.get("display_type") or "—")),
            ],
            styles,
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
    bom = piece.get("bom") if isinstance(piece.get("bom"), list) else []
    if not bom:
        bom = (
            formal_dress_bom(color_hint=color)
            if is_formal_dress_category(cat)
            else default_bom(cat, color_hint=color)
        )
    bom = normalize_bom_rows(bom, piece=piece)
    data = [
        [
            Paragraph("<b>Item</b>", styles["small"]),
            Paragraph("<b>Description</b>", styles["small"]),
            Paragraph("<b>Placement</b>", styles["small"]),
            Paragraph("<b>Color / code</b>", styles["small"]),
            Paragraph("<b>Qty</b>", styles["small"]),
            Paragraph("<b>Unit</b>", styles["small"]),
            Paragraph("<b>Supplier ref</b>", styles["small"]),
            Paragraph("<b>Notes</b>", styles["small"]),
        ]
    ]
    for row in bom[:50]:
        if not isinstance(row, dict):
            continue
        item = str(row.get("item") or row.get("name") or "—")
        if str(row.get("review_status") or "") == "needs_review":
            item = f"{item} · NEEDS REVIEW"
        data.append(
            [
                Paragraph(item, styles["small"]),
                Paragraph(str(row.get("description") or row.get("notes") or "—"), styles["small"]),
                Paragraph(str(row.get("placement") or "—"), styles["small"]),
                Paragraph(str(row.get("color_code") or color or "—"), styles["small"]),
                Paragraph(str(row.get("qty") or "—"), styles["small"]),
                Paragraph(str(row.get("unit") or "—"), styles["small"]),
                Paragraph(str(row.get("supplier_ref") or "TBD"), styles["small"]),
                Paragraph(str(row.get("notes") or "—")[:120], styles["small"]),
            ]
        )
    story.append(
        _table(
            data,
            [28 * mm, 36 * mm, 28 * mm, 22 * mm, 12 * mm, 12 * mm, 18 * mm, 24 * mm],
            styles,
        )
    )
    story.append(PageBreak())
    return story


def _construction_page(piece: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
    story: list[Any] = []
    heading = _piece_heading(piece)
    cat = str(piece.get("category") or "other")
    story.append(Paragraph(f"Construction — {heading}", styles["h2"]))
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
    steps = piece.get("construction_steps") if isinstance(piece.get("construction_steps"), list) else []
    if not steps:
        steps = default_construction_steps(cat)
    steps = filter_construction_steps(list(steps), analysis=analysis)
    ai_sourced = any(
        isinstance(s, dict)
        and str(s.get("source") or "").lower() in {"ai", "ai_vision", "ai_inferred"}
        for s in steps
    )
    story.append(
        Paragraph(
            (
                "AI sew-order operations for this look (ISO 4915 stitch classes). "
                "Confirm before factory send."
                if ai_sourced
                else "Operations in sew order. Quote stitch class (ISO 4915) and SPI/SPCM. "
                "Defaults are draft aids until designer confirms."
            ),
            styles["muted"],
        )
    )

    data = [
        [
            Paragraph("<b>#</b>", styles["small"]),
            Paragraph("<b>Operation</b>", styles["small"]),
            Paragraph("<b>Stitch type</b>", styles["small"]),
            Paragraph("<b>SPI / SPCM</b>", styles["small"]),
            Paragraph("<b>SA (cm)</b>", styles["small"]),
            Paragraph("<b>Notes</b>", styles["small"]),
        ]
    ]
    for idx, row in enumerate(steps[:40], start=1):
        if isinstance(row, dict):
            op = str(row.get("operation") or row.get("instruction") or "—")
            stitch = str(row.get("stitch_type") or "301 lockstitch (confirm)")
            spi = str(row.get("spi") or "3.5–4 /cm")
            sa = row.get("seam_allowance_cm")
            sa_txt = "—" if sa is None else str(sa)
            notes = str(row.get("notes") or "")
            step_no = row.get("step", idx)
        else:
            op = str(row)
            stitch, spi, sa_txt, notes = "301", "3.5–4 /cm", "1.0", ""
            step_no = idx
        data.append(
            [
                Paragraph(str(step_no), styles["small"]),
                Paragraph(op, styles["small"]),
                Paragraph(stitch, styles["small"]),
                Paragraph(spi, styles["small"]),
                Paragraph(sa_txt, styles["small"]),
                Paragraph(notes or "—", styles["small"]),
            ]
        )
    story.append(_table(data, [10 * mm, 48 * mm, 32 * mm, 22 * mm, 14 * mm, 54 * mm], styles))
    story.append(
        Paragraph(
            "Common stitch classes (ISO 4915): 301 lockstitch · 401 chainstitch · "
            "504 overlock 3-thread · 514 overlock 4-thread · 516 safety · 406/605 coverstitch.",
            styles["muted"],
        )
    )

    # Pattern inventory on same logical block (may spill page)
    story.append(Paragraph("Pattern piece development (NOT TO SCALE)", styles["h3"]))
    story.append(
        Paragraph(
            "Planning inventory for the patternmaker — not a print-to-scale cutter. "
            "An actual sewing pattern is not supplied with this pack.",
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

    # Fabric cutting / pattern-development schematic (AI art when present).
    story.append(Paragraph("Cutting layout / pattern development", styles["h3"]))
    story.append(
        Paragraph(
            "AI cutting schematic for sample development — <b>NOT TO SCALE</b>. "
            "Not a print-to-cutter marker. Patternmaker must draft the sewing pattern from "
            "confirmed POMs + this inventory before fabric cutting.",
            styles["warn"],
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

    if is_formal_dress_category(cat):
        story.append(Paragraph("Sample QC checklist", styles["h3"]))
        # Two-column compact checklist — avoids a nearly blank orphan page.
        qc_left = FORMAL_DRESS_QC[: (len(FORMAL_DRESS_QC) + 1) // 2]
        qc_right = FORMAL_DRESS_QC[(len(FORMAL_DRESS_QC) + 1) // 2 :]
        left_tbl = Table(
            [[Paragraph(f"☐ {item}", styles["small"])] for item in qc_left],
            colWidths=[88 * mm],
        )
        right_tbl = Table(
            [[Paragraph(f"☐ {item}", styles["small"])] for item in qc_right],
            colWidths=[88 * mm],
        )
        qc_table = Table([[left_tbl, right_tbl]], colWidths=[90 * mm, 90 * mm])
        qc_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(qc_table)

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
            Paragraph("<b>Colorway 2</b>", styles["small"]),
            Paragraph("<b>Colorway 3</b>", styles["small"]),
        ]
    ]
    for piece in pieces:
        label = _piece_heading(piece)
        color = str(piece.get("color_hint") or "—")
        data.append(
            [
                Paragraph(f"{label} — shell", styles["small"]),
                Paragraph(color, styles["small"]),
                Paragraph("—", styles["small"]),
                Paragraph("—", styles["small"]),
            ]
        )
        data.append(
            [
                Paragraph(f"{label} — lining / thread / zip", styles["small"]),
                Paragraph("match / TBD", styles["small"]),
                Paragraph("—", styles["small"]),
                Paragraph("—", styles["small"]),
            ]
        )
    story.append(_table(data, [55 * mm, 40 * mm, 40 * mm, 40 * mm], styles))
    return story


def _labels_packing_page(styles: dict[str, Any]) -> list[Any]:
    """Labels block without forced page break (merged into factory close)."""
    story: list[Any] = []
    story.append(Paragraph("Labels and packing", styles["h3"]))
    story.append(
        Paragraph(
            "Measure label positions from a fixed seam or edge. Care symbols follow ISO 3758.",
            styles["muted"],
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


def _revision_and_readiness(
    *,
    style_code: str,
    revision: int,
    v2: dict[str, Any],
    pieces: list[dict[str, Any]],
    styles: dict[str, Any],
) -> list[Any]:
    story: list[Any] = []
    story.append(Paragraph("Revision log", styles["h2"]))
    rev_data = [
        [
            Paragraph("<b>Rev</b>", styles["small"]),
            Paragraph("<b>Date</b>", styles["small"]),
            Paragraph("<b>What changed</b>", styles["small"]),
            Paragraph("<b>By</b>", styles["small"]),
        ],
        [
            Paragraph(str(revision), styles["small"]),
            Paragraph("—", styles["small"]),
            Paragraph(f"Create Real Design export · {style_code}", styles["small"]),
            Paragraph("FashionRise", styles["small"]),
        ],
    ]
    story.append(_table(rev_data, [18 * mm, 28 * mm, 100 * mm, 30 * mm], styles))

    story.append(Paragraph("Manufacturing readiness & review", styles["h2"]))
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
    story.append(
        Paragraph(
            f"<b>Current readiness:</b> {readiness_label}. "
            "DESIGN CONCEPT → SAMPLE-DEVELOPMENT READY → PRODUCTION APPROVED. "
            "AI completion alone never grants SAMPLE or PRODUCTION approval.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Proposed</b> = AI or default draft (backs, generic SA, inferred closures). "
            "<b>Unresolved</b> = blocking SAMPLE-DEVELOPMENT READY until corrected. "
            "Designer-entered values are <b>not</b> automatically confirmed specifications.",
            styles["muted"],
        )
    )
    missing = mfg.get("missing_required") if isinstance(mfg.get("missing_required"), list) else []
    if missing:
        story.append(Paragraph("Missing for SAMPLE-DEVELOPMENT READY", styles["h3"]))
        for item in missing[:40]:
            story.append(Paragraph(f"• {item}", styles["warn"]))
    # All measurement / compatibility notes live here (not on overview) to avoid orphan pages.
    overview_warnings = [
        w for w in (v2.get("warnings") if isinstance(v2.get("warnings"), list) else [])
    ] + collect_compatibility_warnings(v2)
    if overview_warnings:
        story.append(Paragraph("Measurement / review notes", styles["h3"]))
        seen_w: set[str] = set()
        for w in overview_warnings[:24]:
            key = (
                f"{w.get('code')}|{w.get('piece_id')}|{w.get('pom')}|{w.get('message')}"
                if isinstance(w, dict)
                else str(w)
            )
            if key in seen_w:
                continue
            seen_w.add(key)
            msg = w.get("message") if isinstance(w, dict) else w
            story.append(Paragraph(f"• {str(msg)[:280]}", styles["warn"]))
    story.append(
        Paragraph(
            "Before factory send, confirm: (1) every POM has how-to + tolerance, "
            "(2) size table grades or sample is sealed, (3) every material has supplier ref + color code, "
            "(4) every operation has stitch type + SPI, (5) label positions measured from a fixed point, "
            "(6) revision log matches cover revision.",
            styles["body"],
        )
    )
    story.append(Paragraph("Per-garment completeness", styles["h3"]))
    for piece in pieces:
        story.append(
            Paragraph(
                f"• {_piece_heading(piece)} — category {piece.get('category') or '—'}; "
                f"POMs {len(finished_pom_rows(piece))}; "
                f"BOM rows {len(piece.get('bom') or [])}",
                styles["body"],
            )
        )
    return story


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
    # Dense style sheet absorbs former cover + overview (Magic + body + fabric strip).
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
    # Factory close — one continuous section (no sparse colorways/labels-only pages).
    story.append(Paragraph("Factory close — colorways, labels, readiness", styles["h2"]))
    story.extend(_colorways_page(pieces, styles))
    story.extend(_labels_packing_page(styles))
    story.extend(
        _revision_and_readiness(
            style_code=style_code,
            revision=revision,
            v2=v2,
            pieces=pieces,
            styles=styles,
        )
    )
    return story
