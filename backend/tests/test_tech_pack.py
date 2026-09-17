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
    assert isinstance(result["special_instructions"], list) and result["special_instructions"]
    assert isinstance(result["cutting_layout"], dict)
    assert result["cutting_layout"].get("fabric_width_cm") == 150

    # Image URLs may be None in stub mode (Unity still gets keys).
    assert "image_url" in result
    assert "back_image_url" in result
    assert "pattern_image_url" in result
    assert "pdf_url" in result


def test_complete_tech_pack_job_uses_stub_without_openai(monkeypatch):
    monkeypatch.setattr(tech_pack_openai, "is_configured", lambda: False)
    monkeypatch.setattr(tech_pack_openai, "_attach_pdf", lambda job, result: {**result, "pdf_url": "http://example.test/t.pdf"})
    job = SimpleNamespace(id=uuid4(), job_type="tech_pack", input_data={"fabric": "denim"})
    result = tech_pack_openai.complete_tech_pack_job(job)
    assert result["message"] == "stub"
    assert result["pipeline"] == "tech_pack"
    assert result["disclaimer"] == tech_pack_openai.DISCLAIMER
    assert result["measurements"]["body"]["height_cm"] == 170
    assert result["pdf_url"] == "http://example.test/t.pdf"


def test_render_tech_pack_pdf_bytes():
    from app.services.tech_pack_pdf import render_tech_pack_pdf

    job = SimpleNamespace(id=uuid4(), job_type="tech_pack", input_data={"fabric": "satin"})
    data = tech_pack_openai.stub_tech_pack(job)
    pdf = render_tech_pack_pdf(data, images={})
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500
    assert pdf.rstrip().endswith(b"%%EOF")


def test_blueprints_render_in_parallel(monkeypatch):
    """Three sequential image calls can outlive the client poll window, so they must overlap."""
    import time

    started: list[float] = []

    def slow_blueprint(_client, _job, _prompt, label):
        started.append(time.monotonic())
        time.sleep(0.4)
        return f"https://example.test/{label}.png"

    monkeypatch.setattr(tech_pack_openai, "_generate_and_store_blueprint", slow_blueprint)
    job = SimpleNamespace(id=uuid4(), job_type="tech_pack", input_data={})

    t0 = time.monotonic()
    out = tech_pack_openai._generate_blueprints(
        None, job, [("front", "f"), ("back", "b"), ("pattern", "p")]
    )
    elapsed = time.monotonic() - t0

    assert out["front"] and out["back"] and out["pattern"]
    assert len(started) == 3
    # Sequential would be >=1.2s; parallel stays close to a single call.
    assert elapsed < 0.9, f"blueprints appear sequential ({elapsed:.2f}s)"


def test_blueprint_failure_does_not_fail_the_sheet(monkeypatch):
    def flaky(_client, _job, _prompt, label):
        if label == "back":
            raise RuntimeError("image model unavailable")
        return f"https://example.test/{label}.png"

    monkeypatch.setattr(tech_pack_openai, "_generate_and_store_blueprint", flaky)
    job = SimpleNamespace(id=uuid4(), job_type="tech_pack", input_data={})

    out = tech_pack_openai._generate_blueprints(
        None, job, [("front", "f"), ("back", "b"), ("pattern", "p")]
    )

    assert out["front"] is not None
    assert out["back"] is None
    assert out["pattern"] is not None


def test_blueprint_budget_returns_partial(monkeypatch):
    import time

    def slow(_client, _job, _prompt, label):
        time.sleep(5 if label == "pattern" else 0.1)
        return f"https://example.test/{label}.png"

    monkeypatch.setattr(tech_pack_openai, "_generate_and_store_blueprint", slow)
    monkeypatch.setattr(
        tech_pack_openai,
        "get_settings",
        lambda: SimpleNamespace(openai_tech_pack_image_budget_seconds=0.6),
    )
    job = SimpleNamespace(id=uuid4(), job_type="tech_pack", input_data={})

    out = tech_pack_openai._generate_blueprints(
        None, job, [("front", "f"), ("back", "b"), ("pattern", "p")]
    )

    assert out["front"] is not None
    assert out["back"] is not None
    assert out["pattern"] is None


MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
    b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _rgb_png(size: int = 16) -> bytes:
    from io import BytesIO

    from PIL import Image as PILImage

    buf = BytesIO()
    PILImage.new("RGB", (size, size), (210, 190, 160)).save(buf, format="PNG")
    return buf.getvalue()


def test_local_storage_reads_public_url_without_http():
    from io import BytesIO

    from app.storage.local import LocalStorageBackend, is_loopback_url

    assert is_loopback_url("http://127.0.0.1:8001/static/uploads/ai/x.png")
    assert is_loopback_url("http://localhost:8001/static/uploads/ai/x.png")
    assert not is_loopback_url("https://cdn.openai.com/img.png")

    storage = LocalStorageBackend()
    key = f"ai/test_local_read_{uuid4().hex}.png"
    url = storage.save_file(key=key, data=BytesIO(MIN_PNG), content_type="image/png")
    try:
        assert storage.read_public_url(url) == MIN_PNG
        assert storage.read_public_url(url.replace("127.0.0.1", "localhost")) == MIN_PNG
        from app.services.tech_pack_pdf import _fetch_png

        assert _fetch_png(url) == MIN_PNG
    finally:
        storage.delete_file(key=key)


def test_fetch_image_skips_loopback_http(monkeypatch):
    import pytest

    class Boom:
        def __init__(self, *a, **k):
            raise AssertionError("must not HTTP-fetch loopback")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(tech_pack_openai.httpx, "Client", Boom)
    with pytest.raises(FileNotFoundError):
        tech_pack_openai._fetch_image("http://127.0.0.1:8001/static/uploads/ai/missing.png")


def test_pdf_embeds_in_memory_blueprint_pngs():
    from app.services.tech_pack_pdf import render_tech_pack_pdf

    job = SimpleNamespace(id=uuid4(), job_type="tech_pack", input_data={"fabric": "satin"})
    data = tech_pack_openai.stub_tech_pack(job)
    empty = render_tech_pack_pdf(data, images={})
    png = _rgb_png()
    filled = render_tech_pack_pdf(
        data, images={"front": png, "back": png, "pattern": png}
    )
    assert filled.startswith(b"%PDF")
    assert len(filled) > len(empty)

