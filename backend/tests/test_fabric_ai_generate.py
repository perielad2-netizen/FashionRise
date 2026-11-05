"""AI fabric generate route — mocked image provider, no live OpenAI spend."""

from __future__ import annotations

import io
from unittest.mock import patch

from PIL import Image

from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes(w: int = 128, h: int = 128, color=(212, 160, 23)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_ai_generate_saves_prompt_short(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "aifab@example.com", "aifab")
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_LIVE_HTTP", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "100")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    from app.core.config import get_settings

    get_settings.cache_clear()

    with patch(
        "app.services.fabric_ai_service.default_generate_fabric_png",
        return_value=_png_bytes(),
    ):
        res = client.post(
            "/api/v1/fabrics/ai-generate",
            headers=_auth(tokens),
            json={
                "prompt": "gold shiny with diamonds like glitters fabric",
                "name": "Gold glitter",
            },
        )
    get_settings.cache_clear()
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["source"] == "ai"
    assert body["prompt_short"]
    assert "gold" in body["prompt_short"].lower()
    assert body["color_hex"] == "#D4A017"
    assert body["name"] == "Gold glitter"

    image = client.get(f"/api/v1/fabrics/{body['id']}/image", headers=_auth(tokens))
    assert image.status_code == 200
    assert image.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_ai_generate_missing_color_400(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "aifab2@example.com", "aifab2")
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_LIVE_HTTP", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "100")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    from app.core.config import get_settings

    get_settings.cache_clear()
    res = client.post(
        "/api/v1/fabrics/ai-generate",
        headers=_auth(tokens),
        json={"prompt": "shiny sequin fabric with glitter sparkle"},
    )
    get_settings.cache_clear()
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert detail["code"] == "missing_fields"
    assert "color" in detail["missing"]
