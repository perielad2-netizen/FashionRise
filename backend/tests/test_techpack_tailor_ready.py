"""Tailor-ready helpers — grades, callouts, hardware, care, swatch."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.services.techpack_tailor_ready import (
    annotate_flat_callouts,
    callout_legend_for_piece,
    care_recommendation,
    extract_fabric_swatch,
    grade_value,
    graded_pom_rows,
    hardware_rows,
    pantone_or_color_code,
)


def test_grade_value_steps_from_sample():
    # Sample M / 38: L is +1 step → full-circ bust +2.0
    assert grade_value(89.0, key="chest_bust", size="M", sample_size="38") == 89.0
    assert grade_value(89.0, key="chest_bust", size="L", sample_size="38") == 91.0
    assert grade_value(89.0, key="chest_bust", size="S", sample_size="38") == 87.0
    assert grade_value(142.0, key="garment_length", size="XL", sample_size="38") == 143.4


def test_graded_pom_rows_fill_sizes():
    piece = {
        "category": "dress",
        "finished_measurements": {
            "chest_bust": {"value": 89, "unit": "cm", "source": "ai"},
            "garment_length": {"value": 142, "unit": "cm", "source": "ai"},
        },
    }
    rows = graded_pom_rows(piece, sample_size="38")
    assert rows
    bust = next(r for r in rows if r["key"] == "chest_bust")
    assert bust["grades"]["M"] == 89.0
    assert bust["grades"]["L"] == 91.0
    assert bust["grades"]["XS"] is not None


def test_callout_legend_includes_features():
    piece = {
        "category": "dress",
        "illustrations": {
            "analysis": {
                "distinctive_features": ["High thigh slit", "Wrap sash"],
            }
        },
    }
    legend = callout_legend_for_piece(piece)
    assert len(legend) >= 10
    blob = " ".join(l for _, l in legend).lower()
    assert "slit" in blob or "sash" in blob or "neckline" in blob


def test_hardware_rows_from_bom():
    piece = {
        "color_hint": "beige",
        "bom": [
            {"item": "Invisible zipper", "description": "60 cm", "placement": "CB", "qty": "1", "unit": "pcs"},
            {"item": "Shell fabric", "description": "crepe", "placement": "body", "qty": "2", "unit": "m"},
            {"item": "Hook and eye", "description": "metal", "placement": "zip top", "qty": "1", "unit": "set"},
        ],
    }
    hw = hardware_rows(piece)
    names = " ".join(r["item"].lower() for r in hw)
    assert "zip" in names
    assert "hook" in names
    assert "shell fabric" not in names


def test_care_delicate_crepe():
    piece = {
        "illustrations": {
            "analysis": {"fabric_estimate": {"likely_fiber": "polyester crepe", "hand": "fluid soft"}}
        }
    }
    care = care_recommendation(piece)
    assert "bleach" in care["bleach"].lower()
    assert care["dry_clean"]


def test_pantone_estimate_marked_proposed():
    piece = {
        "color_hint": "champagne beige",
        "illustrations": {"analysis": {"pantone_estimate": "14-1112 TCX"}},
    }
    assert "14-1112" in pantone_or_color_code(piece)
    assert "confirm" in pantone_or_color_code(piece).lower() or "proposed" in pantone_or_color_code(piece).lower()


def test_swatch_and_annotate_flat_temp_files():
    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "look.png"
        Image.new("RGB", (400, 800), color=(200, 180, 150)).save(src)
        sw = extract_fabric_swatch(src, size=64)
        assert sw is not None and sw.exists()
        ann = annotate_flat_callouts(src, [("1", "Neck"), ("2", "Hem"), ("3", "Slit")], side="left")
        assert ann is not None and ann.exists()
