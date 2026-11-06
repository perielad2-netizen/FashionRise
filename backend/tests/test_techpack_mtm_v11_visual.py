"""V11 — visual pattern breakdown, POM sanitization, construction sync."""

from __future__ import annotations

from pathlib import Path

from app.services.techpack_designer_spec import enrich_piece_for_designer_pdf
from app.services.techpack_pattern_art import render_pattern_breakdown_png
from app.services.techpack_structure import plan_professional_image_kinds


def test_pattern_breakdown_png_renders_shirt_pieces(tmp_path: Path):
    patterns = [
        {"id": "A", "name": "Front body, left", "cut_qty": 1, "fabric": "shell", "grainline": "straight"},
        {"id": "B", "name": "Front body, right", "cut_qty": 1, "fabric": "shell", "grainline": "straight"},
        {"id": "C", "name": "Back body", "cut_qty": 1, "fabric": "shell", "grainline": "straight"},
        {"id": "D", "name": "Stand collar", "cut_qty": 2, "fabric": "shell", "grainline": "straight"},
        {"id": "E", "name": "Sleeve", "cut_qty": 2, "fabric": "shell", "grainline": "straight"},
    ]
    out = render_pattern_breakdown_png(patterns, category="shirt", label="Red Shirt")
    assert out is not None
    assert out.exists()
    assert out.stat().st_size > 20_000
    out.unlink(missing_ok=True)


def test_misleading_shirt_poms_cleared():
    piece = {
        "id": "p1",
        "category": "shirt",
        "label": "Burgundy shirt",
        "closures": {"type": "button-front"},
        "illustrations": {
            "analysis": {
                "length": "Hip length",
                "neckline": "standing collar",
                "closure_visible": "front button placket",
            }
        },
        "finished_measurements": {
            "garment_length": {"value": 115, "unit": "cm", "source": "ai"},
            "neckline": {"value": 45, "unit": "cm", "source": "ai"},
            "chest_bust": {"value": 104, "unit": "cm", "source": "ai"},
        },
    }
    out = enrich_piece_for_designer_pdf(piece)
    fm = out["finished_measurements"]
    assert fm["garment_length"]["value"] is None
    assert "withheld" in str(fm["garment_length"].get("note") or "").lower()
    assert fm["neckline"]["value"] is None
    assert fm["chest_bust"]["value"] == 104


def test_shirt_no_pleat_reconciles_construction():
    piece = {
        "id": "p1",
        "category": "shirt",
        "closures": {"type": "button-front"},
        "illustrations": {
            "analysis": {
                "back_construction_proposal": "Plain back with no pleat; match slim front fit.",
                "closure_visible": "buttons",
            }
        },
        "construction_steps": [
            {"step": 1, "operation": "Join optional back yoke; add 2 cm box pleat", "notes": ""},
            {"step": 2, "operation": "Set sleeves", "notes": "Turn sleeve lower edges inward twice"},
        ],
        "pattern_pieces": [
            {"id": "E", "name": "Sleeve", "cut_qty": 2},
            {"id": "F", "name": "Sleeve placket", "cut_qty": 2},
            {"id": "G", "name": "Sleeve cuff", "cut_qty": 2},
        ],
    }
    out = enrich_piece_for_designer_pdf(piece)
    steps_blob = " ".join(
        str(s.get("operation") or "") + " " + str(s.get("notes") or "") for s in out["construction_steps"]
    ).lower()
    assert "no pleat" in steps_blob or "omit box pleat" in steps_blob
    cuff = next(r for r in out["pattern_pieces"] if "cuff" in str(r.get("name") or "").lower())
    assert "optional" in str(cuff.get("notes") or "").lower()


def test_two_piece_budget_prioritizes_pattern_sheet():
    pieces = [
        {"id": "top-1", "category": "shirt", "label": "Shirt"},
        {"id": "tr-1", "category": "trousers", "label": "Jeans"},
    ]
    plan = plan_professional_image_kinds(
        pieces, propose_back=True, has_back_image=False, max_images=6
    )
    assert "pattern_sheet" in plan["per_piece"]["top-1"]["all"]
    assert "pattern_sheet" in plan["per_piece"]["tr-1"]["all"]
    # With budget 6, details may be skipped after pattern sheets.
    skipped = " ".join(plan.get("skipped_optional") or [])
    assert "detail_callouts" in skipped or "detail_callouts" not in plan["per_piece"]["top-1"]["all"]
