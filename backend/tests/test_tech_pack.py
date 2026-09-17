"""Contract tests for tech pack stub / Unity result_data shape (no OpenAI required)."""

from types import SimpleNamespace
from uuid import uuid4

from app.services import tech_pack_openai


def test_stub_tech_pack_unity_shape():
    job = SimpleNamespace(
        id=uuid4(),
        job_type="tech_pack",
        input_data={
            "notes": "party dress",
            "fabric": "velvet",
            "color": "navy",
            "image_base64": "",
            "polished_image_url": None,
            "material_pairs": "navy:velvet:#001F3F",
        },
    )
    result = tech_pack_openai.stub_tech_pack(job)

    assert result["disclaimer"] == tech_pack_openai.DISCLAIMER
    assert "Draft" in result["disclaimer"]
    assert result["summary"]
    assert result["sections"] == tech_pack_openai.SECTIONS
    assert set(result["sections"]) >= {"design", "measurements", "pattern", "cutting", "materials", "construction"}

    assert isinstance(result["garment"], dict)
    assert result["garment"].get("type")
    assert result["garment"].get("construction_description")

    m = result["measurements"]
    assert m["sample_size"] == "EU 36 / US 4"
    assert m["body"]["height_cm"] == 170
    assert m["body"]["bust_cm"] == 84
    assert m["body"]["waist_cm"] == 64
    assert m["body"]["hip_cm"] == 90
    assert isinstance(m["finished"], dict)
    assert m["finished"].get("bust_cm")

    assert isinstance(result["materials"], list) and len(result["materials"]) >= 3
    roles = {x.get("role") for x in result["materials"]}
    assert "shell" in roles
    assert any(x.get("role") == "notion" for x in result["materials"])

    assert isinstance(result["pattern_pieces"], list) and result["pattern_pieces"]
    piece = result["pattern_pieces"][0]
    for key in ("name", "qty", "approx_w_cm", "approx_h_cm", "seam_allowance_cm", "grainline", "on_fold", "notches"):
        assert key in piece

    assert isinstance(result["construction_steps"], list) and result["construction_steps"]
    assert isinstance(result["cutting_layout"], dict)
    assert result["cutting_layout"].get("fabric_width_cm") == 150

    # Image URLs may be None in stub mode (Unity still gets keys).
    assert "image_url" in result
    assert "back_image_url" in result
    assert "pattern_image_url" in result


def test_complete_tech_pack_job_uses_stub_without_openai(monkeypatch):
    monkeypatch.setattr(tech_pack_openai, "is_configured", lambda: False)
    job = SimpleNamespace(id=uuid4(), job_type="tech_pack", input_data={"fabric": "denim"})
    result = tech_pack_openai.complete_tech_pack_job(job)
    assert result["message"] == "stub"
    assert result["pipeline"] == "tech_pack"
    assert result["disclaimer"] == tech_pack_openai.DISCLAIMER
    assert result["measurements"]["body"]["height_cm"] == 170
