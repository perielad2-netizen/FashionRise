"""V2 PDF acceptance fixtures — garment-specific content + measurement warnings."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from pypdf import PdfReader

from app.services.techpack_ai import enrich_spec_heuristic
from app.services.techpack_detect import detect_pieces_from_evidence
from app.services.techpack_garments import collect_measurement_warnings, default_piece
from app.services.techpack_pdf import build_techpack_pdf
from app.services.techpack_spec import default_spec, ensure_v2


def _tiny_png(path: Path) -> None:
    import base64

    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
    )


def _pdf_text(spec: dict, *, front: Path | None, back: Path | None = None) -> tuple[str, int, bytes]:
    pdf, pages = build_techpack_pdf(
        title="Fixture look",
        style_code="FR-TEST",
        revision=1,
        status="DRAFT",
        verification="UNVERIFIED",
        look_id="00000000-0000-0000-0000-000000000001",
        front_image=front,
        back_image=back,
        spec=spec,
    )
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    return text, pages, pdf


def test_dress_fixture_relevant_poms_and_flats():
    with tempfile.TemporaryDirectory() as tmp:
        front = Path(tmp) / "front.png"
        _tiny_png(front)
        spec = enrich_spec_heuristic(default_spec(look_summary="fitted cream dress"))
        text, pages, _ = _pdf_text(spec, front=front)
        assert pages >= 5
        assert "dress" in text.lower() or "DRESS" in text
        assert "Chest / bust" in text or "chest" in text.lower()
        assert "NOT TO SCALE" in text
        assert "Pattern piece development" in text
        assert "Bill of materials" in text


def test_two_piece_shirt_trousers_separate_sections():
    with tempfile.TemporaryDirectory() as tmp:
        front = Path(tmp) / "front.png"
        _tiny_png(front)
        spec = enrich_spec_heuristic(
            default_spec(look_summary="black shirt and light beige trousers two-piece outfit")
        )
        assert spec["outfit"]["piece_count"] == 2
        text, pages, _ = _pdf_text(spec, front=front)
        assert pages >= 8
        assert "shirt" in text.lower()
        assert "trouser" in text.lower()
        # Trousers sheet should mention inseam; shirt sheet shoulder.
        assert "Inseam" in text
        assert "Shoulder" in text
        assert "CUTTING LAYOUT" in text.upper() or "Cutting layout" in text
        # Must not claim Magic images are cut patterns on cutting pages.
        assert "same Magic job" not in text


def test_trousers_only_excludes_bust_sleeve_fields():
    detection = detect_pieces_from_evidence(look_summary="navy trousers pants only")
    assert detection["piece_count"] == 1
    assert detection["pieces"][0]["category"] == "trousers"
    finished = detection["pieces"][0]["finished_measurements"]
    assert "waist" in finished and "inseam" in finished
    assert "chest_bust" not in finished
    assert "sleeve_length" not in finished
    assert "shoulder_width" not in finished

    with tempfile.TemporaryDirectory() as tmp:
        front = Path(tmp) / "front.png"
        _tiny_png(front)
        spec = enrich_spec_heuristic(
            {
                **default_spec(look_summary="navy trousers"),
                "outfit": detection,
            }
        )
        text, _, _ = _pdf_text(spec, front=front)
        assert "Sleeve length" not in text
        assert "Shoulder width" not in text
        assert "Inseam" in text


def test_partial_single_view_missing_back_not_fabricated():
    with tempfile.TemporaryDirectory() as tmp:
        front = Path(tmp) / "front.png"
        _tiny_png(front)
        spec = enrich_spec_heuristic(default_spec(look_summary="shirt"))
        text, _, _ = _pdf_text(spec, front=front, back=None)
        assert "not fabricated" in text.lower() or "not invented" in text.lower()
        assert "BACK — SHIRT" in text  # schematic back ok
        # But Magic back unavailable message present
        assert "unavailable" in text.lower()


def test_implausible_shoulder_triggers_warning():
    piece = default_piece(piece_id="p1", category="shirt", label="Test shirt")
    piece["finished_measurements"]["shoulder_width"] = {
        "value": 120,
        "unit": "cm",
        "source": "designer",
        "definition": "Shoulder width",
        "confidence": "unknown",
        "review_status": "open",
        "assumptions": [],
    }
    spec = ensure_v2(
        {
            "schema_version": "2.0",
            "units": "cm",
            "outfit": {"piece_count": 1, "pieces": [piece]},
            "body": {},
            "preferences": {},
        }
    )
    warnings = collect_measurement_warnings(spec)
    assert any(w.get("pom") == "shoulder_width" for w in warnings)
    assert any("120" in (w.get("message") or "") for w in warnings)
    enriched = enrich_spec_heuristic(spec)
    # Designer value preserved through enrich
    assert enriched["outfit"]["pieces"][0]["finished_measurements"]["shoulder_width"]["value"] == 120

    with tempfile.TemporaryDirectory() as tmp:
        front = Path(tmp) / "front.png"
        _tiny_png(front)
        text, _, _ = _pdf_text(enriched, front=front)
        assert "implausible" in text.lower() or "120" in text


def test_long_multipage_two_piece_document():
    with tempfile.TemporaryDirectory() as tmp:
        front = Path(tmp) / "front.png"
        back = Path(tmp) / "back.png"
        _tiny_png(front)
        _tiny_png(back)
        spec = enrich_spec_heuristic(
            default_spec(look_summary="black shirt and beige trousers with jacket notes")
        )
        # Force two pieces even if detector saw jacket word oddly
        if spec["outfit"]["piece_count"] < 2:
            spec["outfit"] = detect_pieces_from_evidence(
                look_summary="black shirt and beige trousers"
            )
            spec = enrich_spec_heuristic(spec)
        text, pages, pdf = _pdf_text(spec, front=front, back=back)
        assert pages >= 8
        assert len(pdf) > 2000
        assert (
            "Review and production readiness" in text
            or "Manufacturing readiness" in text
        )
        assert "Create Real Design V2" not in text or "FashionRise" in text
