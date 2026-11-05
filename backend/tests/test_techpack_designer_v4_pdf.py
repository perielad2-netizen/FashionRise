"""V4 designer-perfect PDF — industry page order for atelier/factory handoff."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from pypdf import PdfReader

from app.services.techpack_ai import enrich_spec_heuristic
from app.services.techpack_designer_spec import finished_pom_rows, formal_dress_bom
from app.services.techpack_pdf import build_techpack_pdf
from app.services.techpack_spec import default_spec


def _tiny_png(path: Path) -> None:
    import base64

    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
    )


def test_v4_dress_pack_has_industry_sections():
    with tempfile.TemporaryDirectory() as tmp:
        front = Path(tmp) / "front.png"
        _tiny_png(front)
        spec = enrich_spec_heuristic(
            default_spec(look_summary="gold sequin evening midi dress with deep V neckline")
        )
        # Seed a finished POM so the table is non-empty.
        pieces = spec["outfit"]["pieces"]
        assert pieces
        pieces[0]["finished_measurements"] = {
            "chest_bust": {"value": 88, "unit": "cm", "source": "estimate"},
            "waist": {"value": 70, "unit": "cm", "source": "estimate"},
            "hip": {"value": 94, "unit": "cm", "source": "estimate"},
            "garment_length": {"value": 110, "unit": "cm", "source": "estimate"},
        }
        pieces[0]["color_hint"] = "gold"
        pdf, pages = build_techpack_pdf(
            title="Gold evening dress",
            style_code="FR-GOLD-1",
            revision=1,
            status="DRAFT",
            verification="UNVERIFIED",
            look_id="00000000-0000-0000-0000-000000000099",
            front_image=front,
            back_image=None,
            spec=spec,
        )
        assert pages >= 8
        text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages)
        assert "Designer Technical Pack" in text or "V4 Designer" in text
        assert "Points of measure" in text
        assert "How to measure" in text or "how to measure" in text.lower()
        assert "Bill of materials" in text
        assert "Invisible zipper" in text or "invisible zip" in text.lower()
        assert "Construction" in text
        assert "301" in text  # ISO lockstitch called out
        assert "Colorways" in text
        assert "Labels and packing" in text or "Labels & packing" in text
        assert "Revision log" in text
        assert "NOT TO SCALE" in text
        assert "Callout legend" in text
        assert "Invisible zipper" in text or "invisible zip" in text.lower()
        assert "Formalwear sample QC" in text or "sample QC" in text.lower()
        assert "1/2 bust" in text or "side seam to side seam" in text.lower()


def test_formal_bom_and_pom_helpers():
    bom = formal_dress_bom(color_hint="ivory")
    assert any("Lining" in str(r.get("item")) for r in bom)
    assert any("Invisible zipper" in str(r.get("item")) for r in bom)
    assert any("Stay tape" in str(r.get("item")) for r in bom)
    piece = {
        "category": "dress",
        "finished_measurements": {
            "chest_bust": {"value": 90, "unit": "cm", "source": "designer"},
            "garment_length": {"value": 140, "unit": "cm", "source": "designer"},
        }
    }
    rows = finished_pom_rows(piece)
    assert rows[0]["code"] in {"A", "D"}
    assert "tolerance_cm" in rows[0]
    bust = next(r for r in rows if r["key"] == "chest_bust")
    assert "1/2 bust" in bust["how_to"] or "side seam" in bust["how_to"].lower()
