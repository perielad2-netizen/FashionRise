"""#169 — owner Accept before FASHN; server-enforced acceptance; no paid calls."""

from __future__ import annotations

import base64
import hashlib
import io
import uuid

import pytest
from PIL import Image, ImageDraw

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.services.ai_worker import run_magic_worker_tick
from app.services.fashn_garment_fidelity import assert_structural_fidelity
from app.services.fashn_garment_realism import (
    GARMENT_REALISM_JOB_TYPE,
    GARMENT_REALISM_PROVIDER_ID,
    GARMENT_REALISM_PROMPT_VERSION,
)
from app.services.personal_croquis_provider import (
    arm_provider_network_tripwire,
    disarm_provider_network_tripwire,
    set_croquis_provider_override,
)
from app.services.personal_try_on_provider import set_try_on_provider_override
from tests.auth_test_helpers import register_with_invite
from tests.croquis_test_fixtures import enable_synthetic_croquis_notices
from tests.test_personal_try_on import (
    TRY_ON,
    _accept_personal_croquis,
    _auth,
    _enable_ai_spend,
    _png_bytes,
    _try_on_body,
    _upload_ready,
)


@pytest.fixture(autouse=True)
def _synthetic_notices_169(monkeypatch):
    enable_synthetic_croquis_notices(monkeypatch)
    set_croquis_provider_override(None)
    set_try_on_provider_override(None)
    arm_provider_network_tripwire()
    yield
    disarm_provider_network_tripwire()
    set_try_on_provider_override(None)
    set_croquis_provider_override(None)


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _skimpy_triangle_bottom_plate() -> bytes:
    """Narrow lower-band triangle bottoms (brown/yellow-dot coverage defect)."""
    img = Image.new("RGBA", (400, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.polygon(
        [
            (120, 80),
            (280, 80),
            (300, 160),
            (200, 420),
            (100, 160),
        ],
        fill=(140, 90, 40, 255),
    )
    return _png(img)


def _thick_coverage_bottom_product() -> bytes:
    """Substantial thicker bottoms that keep a crotch notch (not a skirt/dress)."""
    img = Image.new("RGB", (512, 640), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    # Wide high-waisted panel with a clear crotch notch — thicker coverage, still bottoms.
    draw.polygon(
        [
            (80, 40),
            (430, 40),
            (450, 180),
            (420, 360),
            (340, 520),
            (300, 460),
            (256, 500),
            (212, 460),
            (170, 520),
            (90, 360),
            (60, 180),
        ],
        fill=(140, 90, 40),
    )
    return _png(img)


def test_fidelity_blocks_skimpy_to_thick_bottoms():
    verdict = assert_structural_fidelity(
        source_png=_skimpy_triangle_bottom_plate(),
        product_png=_thick_coverage_bottom_product(),
        layout="two_piece",
    )
    assert verdict.ok is False
    assert verdict.code == "FIDELITY_COVERAGE_EXPANDED"


def test_owner_two_piece_v5_bottoms_coverage_artifact():
    """Regression on Nov 2 owner brown/yellow-dot bottoms when diag artifacts exist."""
    from pathlib import Path

    base = Path("/tmp/fr169-diag")
    plate = base / "preview_two_piece_v5_plate_1_bottoms.png"
    product = base / "preview_two_piece_v5_product_1_bottoms.png"
    if not plate.exists() or not product.exists():
        return
    verdict = assert_structural_fidelity(
        source_png=plate.read_bytes(),
        product_png=product.read_bytes(),
        layout="two_piece",
    )
    assert verdict.ok is False
    assert verdict.code == "FIDELITY_COVERAGE_EXPANDED"


def test_fidelity_passes_matching_triangle_bottoms():
    source = _skimpy_triangle_bottom_plate()
    # Matching product silhouette family (still triangle-ish lower band).
    img = Image.new("RGB", (512, 640), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.polygon(
        [
            (150, 100),
            (360, 100),
            (380, 180),
            (256, 500),
            (130, 180),
        ],
        fill=(140, 90, 40),
    )
    product = _png(img)
    verdict = assert_structural_fidelity(
        source_png=source, product_png=product, layout="two_piece"
    )
    assert verdict.ok is True


def _seed_realism_job(
    db_session,
    *,
    owner_id,
    owner_accepted: bool = False,
    fidelity_ok: bool = True,
    block_fashn: bool = False,
    garment_fingerprint: str | None = None,
    pieces: list[dict] | None = None,
):
    if pieces is None:
        prod = _png_bytes((96, 128), (40, 120, 210, 255))
        pieces = [
            {
                "category": "one-pieces",
                "image_base64": "data:image/png;base64," + base64.b64encode(prod).decode("ascii"),
                "sha256": hashlib.sha256(prod).hexdigest(),
                "source_plate_sha256": "plate-sha",
                "fidelity": {"ok": fidelity_ok, "code": "FIDELITY_OK" if fidelity_ok else "FIDELITY_COVERAGE_EXPANDED"},
            }
        ]
    job = AIJob(
        id=uuid.uuid4(),
        user_id=owner_id,
        design_id=None,
        job_type=GARMENT_REALISM_JOB_TYPE,
        status="completed",
        input_data={
            "mode": "garment_realism",
            "garment_fingerprint": garment_fingerprint or "fp-test-169",
        },
        result_data={
            "status": "completed",
            "mode": "garment_realism",
            "provider": GARMENT_REALISM_PROVIDER_ID,
            "prompt_version": GARMENT_REALISM_PROMPT_VERSION,
            "prefer_local_product": False,
            "fidelity_ok": fidelity_ok,
            "block_fashn": block_fashn,
            "requires_owner_acceptance": True,
            "owner_accepted": owner_accepted,
            "pieces": pieces,
            "summary": "Realistic garment product image ready."
            if fidelity_ok
            else "Fidelity checks failed.",
        },
    )
    db_session.add(job)
    db_session.commit()
    return job


def test_accept_endpoint_stamps_owner_accepted(client, monkeypatch, db_session):
    from app.models.user import User

    tokens = register_with_invite(client, db_session, "accept169@example.com", "accept169")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _accept_personal_croquis(client, tokens, monkeypatch, db_session, croquis["id"], "g-accept169")
    owner = db_session.query(User).filter(User.email == "accept169@example.com").one()
    job = _seed_realism_job(db_session, owner_id=owner.id, owner_accepted=False)
    job_id = job.id

    r = client.post(
        f"{TRY_ON}/fashn/garment-realism/{job.id}/accept",
        headers=_auth(tokens),
    )
    assert r.status_code == 200, r.text
    # Expire so we re-read what commit persisted (not just the in-memory Accept object).
    db_session.expire_all()
    job = db_session.get(type(job), job_id)
    assert job is not None
    assert job.result_data.get("owner_accepted") is True
    assert job.result_data.get("requires_owner_acceptance") is True
    assert "owner_accepted_at" in job.result_data
    # Response body must also reflect the stamp (prior bug: 200 with memory-only True).
    body = r.json().get("result_data") or {}
    assert body.get("owner_accepted") is True

    # Idempotent re-accept.
    r2 = client.post(
        f"{TRY_ON}/fashn/garment-realism/{job.id}/accept",
        headers=_auth(tokens),
    )
    assert r2.status_code == 200, r2.text


def test_accept_cannot_override_fidelity_failure(client, monkeypatch, db_session):
    from app.models.user import User

    tokens = register_with_invite(client, db_session, "fidfail169@example.com", "fidfail169")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _accept_personal_croquis(client, tokens, monkeypatch, db_session, croquis["id"], "g-fidfail169")
    owner = db_session.query(User).filter(User.email == "fidfail169@example.com").one()
    job = _seed_realism_job(
        db_session,
        owner_id=owner.id,
        fidelity_ok=False,
        block_fashn=True,
    )
    r = client.post(
        f"{TRY_ON}/fashn/garment-realism/{job.id}/accept",
        headers=_auth(tokens),
    )
    assert r.status_code == 422, r.text
    assert "fidelity" in r.json()["detail"].lower()
    db_session.refresh(job)
    assert job.result_data.get("owner_accepted") is not True


def test_fashn_enqueue_requires_owner_acceptance(client, monkeypatch, db_session):
    from app.models.user import User
    from app.services.fashn_try_on_provider import FASHN_CONSENT_VERSION

    tokens = register_with_invite(client, db_session, "noaccept169@example.com", "noaccept169")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _accept_personal_croquis(client, tokens, monkeypatch, db_session, croquis["id"], "g-noaccept169")

    get_settings.cache_clear()
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-fashn-key-not-real")
    monkeypatch.setenv("FASHN_TRY_ON_ESTIMATE_CENTS", "8")
    get_settings.cache_clear()

    owner = db_session.query(User).filter(User.email == "noaccept169@example.com").one()
    job = _seed_realism_job(db_session, owner_id=owner.id, owner_accepted=False)

    class MockFashn:
        def __init__(self):
            self.calls = 0

        def generate(self, **kwargs):
            self.calls += 1
            return _png_bytes((80, 120)), {"actual_cost_cents": 8, "provider": "fashn_tryon_v1_6"}

    mock = MockFashn()
    set_try_on_provider_override(mock)

    body = _try_on_body(croquis_id=croquis["id"], key="try_on:fashn:no-accept-169")
    body["provider"] = "fashn"
    body["consent_version"] = FASHN_CONSENT_VERSION
    body["garment_realism_job_id"] = str(job.id)
    body["approved_garment_pieces"] = [
        {"category": p["category"], "image_base64": p["image_base64"]}
        for p in job.result_data["pieces"]
    ]
    r = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r.status_code == 400, r.text
    assert "accept" in r.json()["detail"].lower()
    assert mock.calls == 0


def test_fashn_enqueue_rejects_stale_garment_fingerprint(client, monkeypatch, db_session):
    from app.models.user import User
    from app.services.fashn_try_on_provider import FASHN_CONSENT_VERSION

    tokens = register_with_invite(client, db_session, "stale169@example.com", "stale169")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _accept_personal_croquis(client, tokens, monkeypatch, db_session, croquis["id"], "g-stale169")

    get_settings.cache_clear()
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-fashn-key-not-real")
    get_settings.cache_clear()

    owner = db_session.query(User).filter(User.email == "stale169@example.com").one()
    # Seed accepted realism bound to a fingerprint that will not match the garment bytes sent.
    job = _seed_realism_job(
        db_session,
        owner_id=owner.id,
        owner_accepted=True,
        garment_fingerprint="fp-old-design",
    )

    class MockFashn:
        calls = 0

        def generate(self, **kwargs):
            MockFashn.calls += 1
            return _png_bytes((80, 120)), {"actual_cost_cents": 8, "provider": "fashn_tryon_v1_6"}

    set_try_on_provider_override(MockFashn())
    body = _try_on_body(croquis_id=croquis["id"], key="try_on:fashn:stale-fp-169")
    body["provider"] = "fashn"
    body["consent_version"] = FASHN_CONSENT_VERSION
    body["garment_realism_job_id"] = str(job.id)
    # Force mismatch: try-on garment SHA != realism job garment_fingerprint.
    other = _png_bytes((64, 96), (255, 0, 0, 200))
    body["garment_image_base64"] = "data:image/png;base64," + base64.b64encode(other).decode("ascii")
    body["approved_garment_pieces"] = [
        {"category": p["category"], "image_base64": p["image_base64"]}
        for p in job.result_data["pieces"]
    ]
    r = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r.status_code in (400, 409), r.text
    assert MockFashn.calls == 0


def test_openai_try_on_unaffected_by_fashn_accept_gate(client, monkeypatch, db_session):
    """Ordinary OpenAI Try On V2 must not require garment-realism acceptance."""
    tokens = register_with_invite(client, db_session, "openai169@example.com", "openai169")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _accept_personal_croquis(client, tokens, monkeypatch, db_session, croquis["id"], "g-openai169")
    _enable_ai_spend(monkeypatch)

    class MockOpenAI:
        def __init__(self):
            self.calls = 0

        def generate(self, *, photo_png, garment_png, design_hints=None, prep=None):
            self.calls += 1
            assert photo_png and garment_png
            out = _png_bytes((80, 120), (9, 9, 9, 255))
            return out, {
                "actual_cost_cents": 3,
                "prompt_version": "try-on-person-v2",
                "provider": "openai_images_edit",
            }

    mock = MockOpenAI()
    set_try_on_provider_override(mock)
    body = _try_on_body(croquis_id=croquis["id"], key="try_on:openai-169")
    r = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r.status_code == 201, r.text
    run_magic_worker_tick(db_session, limit=4)
    assert mock.calls == 1
