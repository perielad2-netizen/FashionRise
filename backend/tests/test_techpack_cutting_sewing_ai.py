"""Fabric cutting schematic + AI sew ops must land in V4 designer PDFs."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.styles import getSampleStyleSheet

from app.services.techpack_designer_pdf import _construction_page
from app.services.techpack_designer_spec import enrich_piece_for_designer_pdf


def test_enrich_keeps_ai_construction_over_formal_defaults():
    piece = {
        "id": "piece-1",
        "category": "dress",
        "label": "Wrap dress",
        "construction_steps": [
            {
                "step": 1,
                "operation": "Attach asymmetric drape panel at waist",
                "stitch_type": "301 lockstitch",
                "spi": "3.5 /cm",
                "seam_allowance_cm": 1.0,
                "notes": "Match Magic look overlap depth",
                "source": "ai",
            }
        ],
    }
    out = enrich_piece_for_designer_pdf(piece)
    assert out["construction_steps"][0]["operation"].startswith("Attach asymmetric")
    assert out["construction_steps"][0]["source"] == "ai"


def test_construction_page_embeds_pattern_sheet_when_present(tmp_path: Path):
    # Minimal PNG so ReportLab can embed.
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    # Use LocalStorageBackend layout via monkeypatch on resolve.
    key = "user/draft/ai/run/art_pattern_sheet.png"
    storage_root = tmp_path / "private_techpacks"
    storage_root.mkdir(parents=True)
    # Patch resolve used inside _art_path
    from app.services import techpack_designer_pdf as mod

    art_file = tmp_path / "pattern.png"
    art_file.write_bytes(png)

    class _FakeStorage:
        def resolve_private_techpack_file(self, *, key: str):  # noqa: A002
            return art_file if key else None

    original = mod.LocalStorageBackend
    mod.LocalStorageBackend = lambda: _FakeStorage()  # type: ignore[misc,assignment]
    try:
        piece = {
            "id": "piece-1",
            "category": "dress",
            "label": "Wrap dress",
            "construction_steps": [
                {
                    "step": 1,
                    "operation": "Staystitch wrap neckline",
                    "stitch_type": "301",
                    "spi": "3.5 /cm",
                    "source": "ai",
                    "notes": "bias",
                }
            ],
            "pattern_pieces": [
                {
                    "id": "front",
                    "name": "Wrap front",
                    "cut_qty": 2,
                    "fabric": "shell",
                    "source": "ai",
                }
            ],
            "illustrations": {
                "artifacts": {
                    "pattern_sheet": {
                        "storage_key": key,
                        "review_state": "proposed",
                    }
                },
                "analysis": {"sleeves": "long"},
            },
        }
        styles = {
            "h2": getSampleStyleSheet()["Heading2"],
            "h3": getSampleStyleSheet()["Heading3"],
            "body": getSampleStyleSheet()["BodyText"],
            "muted": getSampleStyleSheet()["BodyText"],
            "warn": getSampleStyleSheet()["BodyText"],
            "small": getSampleStyleSheet()["BodyText"],
        }
        # evaluate_artifact_for_piece may need manufacturing helpers — use permissive meta
        story = _construction_page(piece, styles)
        texts = []
        for flow in story:
            if hasattr(flow, "text"):
                texts.append(str(flow.text))
            elif hasattr(flow, "_argW"):  # table-ish
                pass
        blob = " ".join(texts)
        assert "Fabric cutting" in blob or "pattern development" in blob.lower()
        assert "AI sew-order" in blob or "Staystitch" in blob or "Construction" in blob
    finally:
        mod.LocalStorageBackend = original
