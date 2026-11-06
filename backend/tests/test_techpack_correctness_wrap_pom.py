"""Technical correctness: full-circ POM labeling + wrap closure consistency."""

from __future__ import annotations

from app.services.techpack_designer_spec import (
    DRESS_POM_HOW_TO,
    detect_closure_family,
    enrich_piece_for_designer_pdf,
    formal_dress_bom,
    finished_pom_rows,
    qc_for_piece,
    scrub_conflicting_closure_bom,
)


def test_dress_pom_howto_is_full_circumference_not_half():
    for key in ("chest_bust", "waist", "hip", "hem"):
        text = DRESS_POM_HOW_TO[key].lower()
        assert "full" in text
        assert "1/2" not in text
        assert "half" not in text or "flat half" in text or "×2" in text or "x2" in text


def test_detect_wrap_when_no_visible_closure():
    piece = {
        "category": "dress",
        "label": "Long-sleeve deep-V wrap dress",
        "illustrations": {
            "analysis": {
                "silhouette": "fitted wrap",
                "closure_visible": "No closure hardware visible; waist sash",
                "distinctive_features": ["wrap front", "thigh slit", "asymmetric drape"],
            }
        },
    }
    assert detect_closure_family(piece) == "wrap"


def test_wrap_bom_has_no_invisible_zipper():
    bom = formal_dress_bom(color_hint="beige", closure_family="wrap")
    blob = " ".join(str(r.get("item") or "") for r in bom).lower()
    assert "invisible zipper" not in blob
    assert "sash" in blob or "tie" in blob
    assert any("proposed" in str(r.get("notes") or "").lower() for r in bom)


def test_scrub_removes_zip_from_legacy_bom():
    legacy = [
        {"item": "Invisible zipper", "qty": "1", "placement": "CB"},
        {"item": "Hook and eye", "qty": "1", "placement": "Top of zipper"},
        {"item": "Shell fabric", "qty": "2", "unit": "m"},
    ]
    cleaned = scrub_conflicting_closure_bom(legacy, closure_family="wrap")
    items = " ".join(str(r.get("item") or "").lower() for r in cleaned)
    assert "zip" not in items
    assert "shell" in items


def test_enrich_wrap_piece_qc_and_missing_design_poms():
    piece = {
        "category": "dress",
        "label": "Wrap dress",
        "color_hint": "beige",
        "bom": [
            {"item": "Invisible zipper", "qty": "1", "unit": "pcs", "placement": "CB"},
            {"item": "Shell", "qty": "2", "unit": "m"},
        ],
        "finished_measurements": {
            "chest_bust": {"value": 89, "unit": "cm", "source": "calculated"},
            "waist": {"value": 79, "unit": "cm", "source": "calculated"},
            "hip": {"value": 99, "unit": "cm", "source": "calculated"},
        },
        "illustrations": {
            "analysis": {
                "closure_visible": "No closure hardware visible; narrow waist tie",
                "silhouette": "wrap bodice",
                "distinctive_features": ["deep V wrap", "thigh slit"],
            }
        },
    }
    enriched = enrich_piece_for_designer_pdf(piece)
    assert enriched["_closure_family"] == "wrap"
    bom_blob = " ".join(str(r.get("item") or "") for r in enriched["bom"]).lower()
    assert "invisible zipper" not in bom_blob
    qc = " ".join(qc_for_piece(enriched)).lower()
    assert "wrap overlap" in qc
    assert "no zipper qc" in qc or "unless a zip" in qc
    assert "invisible zip smooth" not in qc
    finished = enriched["finished_measurements"]
    assert finished["wrap_overlap"]["value"] is None
    assert "missing" in str(finished["slit_start"].get("note") or "").lower()
    rows = finished_pom_rows(enriched)
    bust = next(r for r in rows if r["key"] == "chest_bust")
    assert "full" in bust["how_to"].lower()
    assert "1/2 bust" not in bust["how_to"].lower()


def test_circ_grades_suppressed_until_confirmed():
    from app.services.techpack_tailor_ready import graded_pom_rows

    piece = {
        "category": "dress",
        "finished_measurements": {
            "chest_bust": {
                "value": 89,
                "unit": "cm",
                "source": "calculated",
                "review_status": "needs_review",
            },
            "sleeve_length": {
                "value": 59,
                "unit": "cm",
                "source": "ai",
                "review_status": "open",
            },
        },
    }
    rows = {r["key"]: r for r in graded_pom_rows(piece, sample_size="38")}
    assert all(v is None for v in rows["chest_bust"]["grades"].values())
    # AI / open length POMs also withhold grades until designer confirms.
    assert all(v is None for v in rows["sleeve_length"]["grades"].values())


def test_wrap_callouts_exclude_zipper_even_if_ai_lists_one():
    from app.services.techpack_tailor_ready import callout_legend_for_piece

    piece = {
        "category": "dress",
        "label": "Wrap dress",
        "illustrations": {
            "analysis": {
                "closure_visible": "No zipper; waist sash",
                "silhouette": "wrap",
                "distinctive_features": ["deep V wrap", "Invisible zipper (CB)", "thigh slit"],
                "callout_points": [
                    {"n": 1, "label": "Invisible zipper (CB or SS) + hook & eye"},
                    {"n": 2, "label": "Deep overlapping V-front"},
                ],
            }
        },
    }
    legend = " ".join(lab for _n, lab in callout_legend_for_piece(piece)).lower()
    assert "zip" not in legend
    assert "wrap" in legend or "deep" in legend


def test_enrich_syncs_v_depth_length_and_sash_bom():
    piece = {
        "category": "dress",
        "label": "Wrap dress",
        "color_hint": "beige",
        "illustrations": {
            "analysis": {
                "closure_visible": "No zipper; waist sash wrap",
                "silhouette": "wrap",
                "distinctive_features": ["deep V wrap"],
            }
        },
        "finished_measurements": {
            "neckline": {"value": 31, "unit": "cm", "source": "ai", "review_status": "proposed"},
            "garment_length": {"value": 142, "unit": "cm", "source": "ai", "review_status": "proposed"},
            "hem_low": {"value": 145, "unit": "cm", "source": "ai", "review_status": "proposed"},
            "sash_width": {"value": 4, "unit": "cm", "source": "ai", "review_status": "proposed"},
            "sash_length": {"value": 190, "unit": "cm", "source": "ai", "review_status": "proposed"},
        },
        "bom": [{"item": "Invisible zipper", "qty": "1", "placement": "CB"}],
    }
    enriched = enrich_piece_for_designer_pdf(piece)
    assert enriched["finished_measurements"]["v_depth"]["value"] == 31.0
    assert enriched["finished_measurements"]["garment_length"]["value"] == 145.0
    assert enriched["finished_measurements"]["hem_low"]["value"] == 145.0
    sash = next(r for r in enriched["bom"] if "sash" in str(r.get("item") or "").lower())
    assert "4" in str(sash.get("description") or "")
    assert "190" in str(sash.get("description") or "")
    from app.services.techpack_designer_spec import humanize_readiness_gap, pom_code

    assert pom_code("slit_start") == "S1"
    assert pom_code("v_depth") == "I2"
    assert "Confirm the dress fastening" in humanize_readiness_gap("piece-aa3:closures_specified")


def test_enrich_wrap_redacts_invented_back_zip():
    piece = {
        "category": "dress",
        "label": "Wrap dress",
        "illustrations": {
            "analysis": {
                "closure_visible": "No zipper; waist sash wrap",
                "silhouette": "wrap",
                "distinctive_features": ["wrap front"],
                "back_construction_proposal": (
                    "Propose modest back neckline with center-back seam, "
                    "concealed short invisible zip from upper back to waist, "
                    "and center-back skirt seam."
                ),
            }
        },
        "construction_steps": [
            {"operation": "Install invisible zipper", "notes": "CB"},
            {"operation": "Finish wrap neckline", "notes": "stay tape"},
        ],
    }
    enriched = enrich_piece_for_designer_pdf(piece)
    prop = str(enriched["illustrations"]["analysis"]["back_construction_proposal"]).lower()
    assert "invisible zip" not in prop
    assert "wrap closure" in prop
    steps = " ".join(
        str(s.get("operation") or "") for s in enriched["construction_steps"] if isinstance(s, dict)
    ).lower()
    assert "zip" not in steps
    assert "wrap neckline" in steps


def test_enrich_syncs_sash_and_flags_fold_vs_cb_choice():
    piece = {
        "category": "dress",
        "label": "Wrap dress",
        "illustrations": {
            "analysis": {
                "closure_visible": "No zipper; waist sash wrap",
                "silhouette": "wrap",
                "distinctive_features": ["wrap front"],
                "back_construction_proposal": (
                    "Propose fitted back bodice with center-back seam and ankle-length skirt."
                ),
            }
        },
        "finished_measurements": {
            "sash_width": {"value": 4, "unit": "cm", "source": "ai", "review_status": "proposed"},
            "sash_length": {"value": 190, "unit": "cm", "source": "ai", "review_status": "proposed"},
        },
        "pattern_pieces": [
            {
                "id": "C",
                "name": "Back bodice",
                "fold": "none",
                "notes": "Cut on fold; proposed high back neckline",
            },
            {
                "id": "H",
                "name": "Self waist sash",
                "fold": "none",
                "notes": "Long finished sash, approx. 6 cm wide, anchored at side waist",
            },
        ],
    }
    enriched = enrich_piece_for_designer_pdf(piece)
    by_id = {str(r.get("id")): r for r in enriched["pattern_pieces"]}
    back = by_id["C"]
    assert "choice" in str(back.get("notes") or "").lower()
    assert "needs_review" in str(back.get("review_state") or "")
    sash = by_id["H"]
    notes = str(sash.get("notes") or "").lower()
    assert "4 cm" in notes
    assert "6 cm" not in notes
    assert notes.count("from sash_width pom") <= 1


def test_scrub_removes_center_back_zipper_label(tmp_path):
    from PIL import Image, ImageDraw, ImageFont

    from app.services.techpack_tailor_ready import scrub_contradictory_flat_labels

    src = tmp_path / "flat.png"
    im = Image.new("RGB", (1000, 1400), color=(245, 240, 232))
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    draw.text((780, 1140), "CENTER BACK ZIPPER", fill=(30, 30, 30), font=font)
    draw.text((790, 1180), "Invisible zipper at center back", fill=(30, 30, 30), font=font)
    im.save(src)

    out = scrub_contradictory_flat_labels(src)
    assert out is not None and out.exists()
    # Prefer OCR path when tesseract is present; always expect a banner/output image.
    from PIL import Image as _Image

    scrubbed = _Image.open(out)
    assert scrubbed.size == im.size
    # Pixel band at the top banner should differ from the paper background.
    assert scrubbed.getpixel((10, 8)) != (245, 240, 232)
