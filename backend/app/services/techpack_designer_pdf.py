"""V4 Designer-perfect Create Real Design PDF — industry tech-pack page order.

Page flow (per GarmentSpec / atelier practice):
  1 Cover & style info
  2 Design overview (Magic refs + body)
  3+ Per garment: flats + callouts → POM → BOM → construction → pattern inventory
  Colorways · Labels & packing · Revision log · Manufacturing readiness
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
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


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
    story.append(Paragraph("FashionRise · Designer Technical Pack", styles["muted"]))
    story.append(Paragraph(title or "Untitled look", styles["title"]))
    story.append(
        Paragraph(
            f"<b>Pack type:</b> {cover_prov['label']} · <b>Readiness:</b> {readiness_label} · "
            "Factory-facing layout · Schematics NOT TO SCALE",
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
                ("Brand", "FashionRise"),
                ("Style name", title or "—"),
                ("Style number", style_code),
                ("Revision", str(revision)),
                ("Status", status_label),
                ("Generation", cover_prov["label"]),
                ("Look ID", look_id),
                ("Category / components", component_list),
                ("Size system", str(v2.get("size_system") or "—")),
                ("Base (sample) size", str(v2.get("sample_size") or "—")),
                ("Units", str(v2.get("units") or "cm")),
                ("Season / drop", str(v2.get("season") or "—")),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            "<b>Pages in this pack:</b> Cover · Design overview · Flats &amp; callouts · "
            "Points of measure · Bill of materials · Construction · Pattern inventory · "
            "Fabric cutting · "
            "Colorways · Labels &amp; packing · Revision log · Manufacturing readiness",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            str(
                v2.get("disclaimer")
                or (
                    "This pack is for sample development with a patternmaker / atelier. "
                    "Technical flats and pattern inventories are NOT TO SCALE. "
                    "Confirm POMs, materials, closures, and construction before cutting."
                )
            ),
            styles["body"],
        )
    )
    story.append(Spacer(1, 4))
    # Slightly shorter hero so cover metadata + notes stay on one page (avoids a near-empty page 2).
    story.append(
        Table(
            [[_look_image(front_image or back_image, 88 * mm, 95 * mm, styles)]],
            colWidths=[100 * mm],
        )
    )
    notes = (v2.get("look_notes") or "").strip()
    # Skip try-on boilerplate / empty notes — they created orphan nearly-blank pages.
    skip_notes = (not notes) or notes.lower().startswith("try on person preview")
    if not skip_notes:
        story.append(Paragraph("Look notes", styles["h3"]))
        story.append(Paragraph(notes[:500], styles["body"]))
    # Prefer AI silhouette blurb when look notes were skipped.
    if skip_notes and pieces:
        illust = pieces[0].get("illustrations") if isinstance(pieces[0].get("illustrations"), dict) else {}
        analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
        blurb = " · ".join(
            str(analysis.get(k) or "").strip()
            for k in ("silhouette", "neckline", "sleeves", "length")
            if str(analysis.get(k) or "").strip() and str(analysis.get(k) or "").strip() != "—"
        )
        if blurb:
            story.append(Paragraph("AI design read", styles["h3"]))
            story.append(Paragraph(blurb[:600], styles["body"]))
    story.append(PageBreak())
    return story


def _overview_page(
    *,
    front_image: Path | None,
    back_image: Path | None,
    v2: dict[str, Any],
    styles: dict[str, Any],
) -> list[Any]:
    story: list[Any] = []
    story.append(Paragraph("Design overview", styles["h2"]))
    story.append(
        Paragraph(
            "Authenticated Magic references. When a back Magic look is missing, AI proposes a "
            "rear flat for sampling (clearly marked proposed). Manufacturing flats follow on "
            "component sheets.",
            styles["muted"],
        )
    )
    looks = Table(
        [
            [
                _side_cell("Front Magic look", front_image, styles, max_h=100 * mm),
                _side_cell(
                    "Back Magic look" if back_image else "Back Magic look — not provided",
                    back_image,
                    styles,
                    max_h=100 * mm,
                ),
            ]
        ],
        colWidths=[88 * mm, 88 * mm],
    )
    looks.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(looks)
    if not back_image:
        story.append(
            Paragraph(
                "<b>Proposed back:</b> No Magic back image — the pack invents a coherent rear "
                "flat and construction for sampling (marked PROPOSED / UNVERIFIED). "
                "Confirm with your patternmaker before cutting.",
                styles["warn"],
            )
        )
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
            ],
            styles,
        )
    )
    body = v2.get("body") if isinstance(v2.get("body"), dict) else {}
    story.append(Paragraph("Body measurements (shared — not finished POMs)", styles["h3"]))
    from app.services.techpack_pdf import _measurement_table

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
    seen: set[str] = set()
    merged: list[Any] = []
    for w in list(warnings) + collect_compatibility_warnings(v2):
        key = (
            f"{w.get('code')}|{w.get('piece_id')}|{w.get('pom')}|{w.get('message')}"
            if isinstance(w, dict)
            else str(w)
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(w)
    if merged:
        story.append(Paragraph("Measurement review warnings", styles["h3"]))
        # Cap on this page so warnings don't spill into a near-empty orphan page.
        for w in merged[:6]:
            msg = w.get("message") if isinstance(w, dict) else w
            story.append(Paragraph(f"• {str(msg)[:220]}", styles["warn"]))
        if len(merged) > 6:
            story.append(
                Paragraph(
                    f"• …and {len(merged) - 6} more — see Manufacturing readiness at the end of this pack.",
                    styles["muted"],
                )
            )
    story.append(PageBreak())
    return story


def _flats_page(piece: dict[str, Any], styles: dict[str, Any]) -> list[Any]:
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

    if professional:
        story.append(
            Paragraph(
                "AI PROFESSIONAL technical flats from the Magic look. DRAFT / UNVERIFIED until designer confirms.",
                styles["muted"],
            )
        )
        analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
        if analysis:
            story.append(
                Paragraph(
                    f"Vision — silhouette: {analysis.get('silhouette') or '—'}; "
                    f"neckline: {analysis.get('neckline') or '—'}; "
                    f"sleeves: {analysis.get('sleeves') or '—'}; "
                    f"pattern: {analysis.get('fabric_pattern') or '—'} "
                    f"({analysis.get('stripe_direction') or 'n/a'}).",
                    styles["body"],
                )
            )
            fab = analysis.get("fabric_estimate") if isinstance(analysis.get("fabric_estimate"), dict) else {}
            if fab:
                story.append(
                    Paragraph(
                        f"Fabric estimate — {fab.get('likely_fiber') or '—'}; "
                        f"hand {fab.get('hand') or '—'}; GSM {fab.get('gsm_range') or '—'}; "
                        f"drape {fab.get('drape') or '—'}; opacity {fab.get('opacity') or '—'}.",
                        styles["body"],
                    )
                )
            back_prop = str(analysis.get("back_construction_proposal") or "").strip()
            if back_prop and arts.get("flat_back_proposed") and not arts.get("flat_back"):
                story.append(
                    Paragraph(f"Proposed back construction: {back_prop[:420]}", styles["body"])
                )
        front_img = _look_image(front_art, 86 * mm, 118 * mm, styles) if front_art else flat_for_category(cat, back=False)
        if back_art:
            back_label = (
                "PROPOSED BACK — UNVERIFIED"
                if arts.get("flat_back_proposed") and not arts.get("flat_back")
                else "BACK — AI FLAT"
            )
            back_img = _look_image(back_art, 86 * mm, 118 * mm, styles)
        else:
            back_label = "BACK — category schematic"
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
        story.append(KeepTogether([flats]))
        if arts.get("flat_back_proposed") and not arts.get("flat_back"):
            story.append(
                Paragraph(
                    "<b>PROPOSED BACK:</b> No Magic back image — confirm rear construction before sampling.",
                    styles["warn"],
                )
            )
    else:
        story.append(
            Paragraph(
                "Category schematics (placeholder). Run AI Professional for source-faithful flats.",
                styles["muted"],
            )
        )
        flats = Table(
            [[flat_for_category(cat, back=False), flat_for_category(cat, back=True)]],
            colWidths=[88 * mm, 88 * mm],
        )
        flats.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(KeepTogether([flats]))

    story.append(Paragraph("Detail callouts", styles["h3"]))
    detail_excl = _art_exclusion_note(piece, "detail_callouts")
    detail_meta = _art_meta(piece, "detail_callouts")
    detail_decision = evaluate_artifact_for_piece(
        piece, kind="detail_callouts", artifact_meta=detail_meta
    )
    has_detail_meta = isinstance(detail_meta, dict)
    show_detail_review = bool(
        detail_art
        or (
            has_detail_meta
            and detail_decision.get("include")
            and not detail_excl
        )
    )
    if show_detail_review:
        if not detail_decision.get("manufacturing_evidence"):
            story.append(
                Paragraph(
                    "<b>UNVERIFIED DETAIL ART:</b> "
                    + str(
                        detail_decision.get("reason")
                        or (detail_meta or {}).get("review_message")
                        or "Visual content has not been independently confirmed. "
                        "Artifact↔piece IDs and analysis text are not proof of correct image pixels. "
                        "This illustration is reviewable but does not count as designer-approved "
                        "manufacturing evidence."
                    ),
                    styles["warn"],
                )
            )
        if detail_art is not None:
            story.append(_look_image(detail_art, 170 * mm, 95 * mm, styles))
        else:
            story.append(
                Paragraph(
                    "Detail artwork metadata is present but the stored image file is unavailable "
                    "in this preview environment. Original bytes are preserved — not substituted.",
                    styles["muted"],
                )
            )
    elif detail_excl:
        story.append(
            Paragraph(
                f"<b>MISSING / EXCLUDED:</b> {detail_excl} "
                "Original file and provenance are preserved; another garment’s artwork "
                "was not substituted.",
                styles["warn"],
            )
        )
    else:
        story.append(
            Paragraph(
                "Number construction callouts on the flats (neckline, zip, darts, hem, straps). "
                "Detail sheet not generated for this run — designer should annotate before factory send.",
                styles["muted"],
            )
        )
    if is_formal_dress_category(cat):
        story.append(Paragraph("Callout legend (annotate on flats)", styles["h3"]))
        legend = [
            [
                Paragraph("<b>#</b>", styles["small"]),
                Paragraph("<b>Construction / design detail</b>", styles["small"]),
            ]
        ]
        for num, label in FORMAL_DRESS_CALLOUTS:
            legend.append(
                [
                    Paragraph(num, styles["small"]),
                    Paragraph(label, styles["small"]),
                ]
            )
        story.append(_table(legend, [12 * mm, 168 * mm], styles))
    # Also surface excluded front/back flats when present (PDF-only rebuild after reject).
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
    story: list[Any] = []
    heading = _piece_heading(piece)
    story.append(Paragraph(f"Points of measure — {heading}", styles["h2"]))
    story.append(
        Paragraph(
            f"Finished-garment POMs ({units}). Measure garment flat, not stretched. "
            f"Base / sample size: <b>{sample_size or '—'}</b>. "
            "Grade other sizes from the approved sample. Half measurements are edge-to-edge unless noted as full circumference.",
            styles["muted"],
        )
    )
    rows = finished_pom_rows(piece)
    header = [
        Paragraph("<b>Code</b>", styles["small"]),
        Paragraph("<b>Point of measure</b>", styles["small"]),
        Paragraph("<b>How to measure</b>", styles["small"]),
        Paragraph(f"<b>Base ({sample_size or 'sample'})</b>", styles["small"]),
        Paragraph("<b>Tol ±</b>", styles["small"]),
        Paragraph("<b>Source</b>", styles["small"]),
    ]
    # Grade placeholders
    for sz in GRADE_SIZES:
        header.append(Paragraph(f"<b>{sz}</b>", styles["small"]))

    data: list[list[Any]] = [header]
    if not rows:
        data.append(
            [Paragraph("—", styles["muted"])] * (6 + len(GRADE_SIZES))
        )
        story.append(
            Paragraph(
                "No finished measurements recorded — patternmaker cannot grade. "
                "Enter POMs in Create Real Design before sampling.",
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
        cells = [
            Paragraph(str(row["code"]), styles["small"]),
            Paragraph(str(row["label"]), styles["small"]),
            Paragraph(str(row["how_to"]), styles["small"]),
            Paragraph(base_txt, styles["small"]),
            Paragraph(f"{row['tolerance_cm']:g}", styles["small"]),
            Paragraph(_fmt_source({"source": row.get("source")}), styles["small"]),
        ]
        for _sz in GRADE_SIZES:
            cells.append(Paragraph("—", styles["small"]))
        data.append(cells)

    # Compact columns for A4
    widths = [10 * mm, 28 * mm, 48 * mm, 22 * mm, 12 * mm, 18 * mm] + [10 * mm] * len(GRADE_SIZES)
    story.append(_table(data, widths, styles))
    story.append(
        Paragraph(
            "Grade rules: fill XS–2XL from the approved sample, or leave blank until sample is sealed. "
            "Do not invent grades.",
            styles["muted"],
        )
    )
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
    story.append(Paragraph("Pattern piece inventory (NOT TO SCALE)", styles["h3"]))
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
    story.append(Paragraph("Fabric cutting / pattern development", styles["h3"]))
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
        story.append(Paragraph("Formalwear sample QC checklist", styles["h3"]))
        for item in FORMAL_DRESS_QC:
            story.append(Paragraph(f"☐ {item}", styles["body"]))

    story.append(PageBreak())
    return story


def _colorways_page(pieces: list[dict[str, Any]], styles: dict[str, Any]) -> list[Any]:
    story: list[Any] = []
    story.append(Paragraph("Colorways by component", styles["h2"]))
    story.append(
        Paragraph(
            "One column per colorway. Every colored component needs a textile color reference "
            "(Pantone TCX or approved lab dip) — not a color name alone.",
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
    story.append(PageBreak())
    return story


def _labels_packing_page(styles: dict[str, Any]) -> list[Any]:
    story: list[Any] = []
    story.append(Paragraph("Labels and packing", styles["h2"]))
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
    story.append(PageBreak())
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
    # Spillover warnings from overview (capped there to avoid empty pages).
    overview_warnings = [
        w for w in (v2.get("warnings") if isinstance(v2.get("warnings"), list) else [])
    ] + collect_compatibility_warnings(v2)
    if len(overview_warnings) > 6:
        story.append(Paragraph("Additional measurement / review notes", styles["h3"]))
        for w in overview_warnings[6:24]:
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
    story.extend(
        _overview_page(
            front_image=front_image,
            back_image=back_image,
            v2=v2,
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
