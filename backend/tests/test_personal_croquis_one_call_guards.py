"""Zero-network guards for the authorized Create My Croquis one-paid-call plan."""

from __future__ import annotations

import hashlib
import io
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.services.personal_croquis_one_call import (
    APPROVED_FIXTURE_SHA256,
    APPROVED_MODEL,
    APPROVED_QUALITY,
    APPROVED_SIZE,
    ONE_CALL_STORAGE_MARKER,
    OneCallGuardError,
    assert_alembic_revision_014,
    assert_dedicated_one_call_storage,
    assert_disposable_db_fresh_for_one_call,
    assert_edit_kwargs_match_envelope,
    assert_effective_one_call_settings,
    assert_official_effective_base_url,
    default_backend_storage_root,
    edit_kwargs_public_preview,
    load_approved_fixture_bytes,
)
from app.services.personal_croquis_provider import (
    OpenAICroquisImagesEditAdapter,
    ProviderNotAvailableError,
)


def _arm_exact_envelope(monkeypatch, **overrides: str) -> None:
    get_settings.cache_clear()
    env = {
        "MY_CROQUIS_AI_ENABLED": "true",
        "MY_CROQUIS_AI_LIVE_HTTP": "true",
        "MY_CROQUIS_AI_SPEND_CEILING_USD": "1.00",
        "MY_CROQUIS_AI_MAX_USD_PER_RUN": "1.00",
        "MY_CROQUIS_AI_MAX_USD_PER_USER_DAY": "1.00",
        "MY_CROQUIS_AI_MAX_EXPOSURE_CENTS": "100",
        "MY_CROQUIS_AI_ESTIMATE_CENTS": "40",
        "MY_CROQUIS_AI_IMAGE_SIZE": APPROVED_SIZE,
        "MY_CROQUIS_AI_IMAGE_QUALITY": APPROVED_QUALITY,
        "OPENAI_IMAGE_MODEL": APPROVED_MODEL,
        "OPENAI_API_KEY": "sk-test-not-real",
    }
    env.update(overrides)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_approved_fixture_hash_matches_committed_bytes():
    data = load_approved_fixture_bytes()
    assert hashlib.sha256(data).hexdigest() == APPROVED_FIXTURE_SHA256
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_tampered_fixture_bytes_refused(tmp_path, monkeypatch):
    from pathlib import Path

    from app.services import personal_croquis_one_call as one_call

    real = load_approved_fixture_bytes()
    fixture_dir = tmp_path / "tests" / "fixtures" / "croquis"
    fixture_dir.mkdir(parents=True)
    target = fixture_dir / "synthetic_clothed_adult_model.png"
    target.write_bytes(real + b"\x00tamper")
    monkeypatch.setattr(one_call, "BACKEND_ROOT", tmp_path)
    monkeypatch.setattr(
        one_call,
        "APPROVED_FIXTURE_RELATIVE",
        Path("tests/fixtures/croquis/synthetic_clothed_adult_model.png"),
    )
    with pytest.raises(OneCallGuardError, match="SHA256 mismatch"):
        one_call.load_approved_fixture_bytes()


def test_effective_settings_refuse_high_quality(monkeypatch):
    _arm_exact_envelope(monkeypatch, MY_CROQUIS_AI_IMAGE_QUALITY="high")
    with pytest.raises(OneCallGuardError, match="quality"):
        assert_effective_one_call_settings(get_settings())


def test_effective_settings_refuse_wrong_size(monkeypatch):
    _arm_exact_envelope(monkeypatch, MY_CROQUIS_AI_IMAGE_SIZE="1024x1024")
    with pytest.raises(OneCallGuardError, match="size"):
        assert_effective_one_call_settings(get_settings())


def test_effective_settings_refuse_wrong_estimate_or_run(monkeypatch):
    _arm_exact_envelope(monkeypatch, MY_CROQUIS_AI_ESTIMATE_CENTS="8")
    with pytest.raises(OneCallGuardError, match="estimate"):
        assert_effective_one_call_settings(get_settings())
    _arm_exact_envelope(monkeypatch, MY_CROQUIS_AI_MAX_USD_PER_RUN="0.50")
    with pytest.raises(OneCallGuardError, match="max/run"):
        assert_effective_one_call_settings(get_settings())


def test_effective_settings_refuse_ai_disabled(monkeypatch):
    _arm_exact_envelope(monkeypatch, MY_CROQUIS_AI_ENABLED="false")
    with pytest.raises(OneCallGuardError, match="MY_CROQUIS_AI_ENABLED"):
        assert_effective_one_call_settings(get_settings())


def test_effective_base_url_refuses_dotenv_style_override(monkeypatch):
    _arm_exact_envelope(monkeypatch)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://evil.example/v1")
    get_settings.cache_clear()
    with pytest.raises(OneCallGuardError, match="non-official"):
        assert_official_effective_base_url(get_settings())


def test_effective_base_url_allows_official_or_unset(monkeypatch):
    _arm_exact_envelope(monkeypatch)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    get_settings.cache_clear()
    assert_official_effective_base_url(get_settings())
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    get_settings.cache_clear()
    assert_official_effective_base_url(get_settings())


def test_exact_envelope_builds_matching_edit_kwargs(monkeypatch):
    _arm_exact_envelope(monkeypatch)
    source = load_approved_fixture_bytes()
    adapter = OpenAICroquisImagesEditAdapter()
    kwargs = adapter.build_edit_kwargs(source)
    assert_edit_kwargs_match_envelope(kwargs)
    preview = edit_kwargs_public_preview(
        kwargs, source_sha256=hashlib.sha256(source).hexdigest()
    )
    assert preview["model"] == APPROVED_MODEL
    assert preview["size"] == APPROVED_SIZE
    assert preview["quality"] == APPROVED_QUALITY
    assert preview["image_count"] == 1
    assert preview["input_fidelity_present"] is False
    assert "image" not in preview


def test_adapter_refuses_non_allowlisted_size_without_silent_fallback(monkeypatch):
    _arm_exact_envelope(monkeypatch, MY_CROQUIS_AI_IMAGE_SIZE="512x512")
    # Settings guard would also refuse; adapter must independently fail closed.
    adapter = OpenAICroquisImagesEditAdapter()
    buf = io.BytesIO()
    Image.new("RGB", (32, 48), (10, 20, 30)).save(buf, format="PNG")
    with pytest.raises(ProviderNotAvailableError, match="not allowlisted|silent"):
        adapter.build_edit_kwargs(buf.getvalue())


def test_edit_kwargs_mismatch_refuses_high_quality_shape():
    with pytest.raises(OneCallGuardError, match="quality"):
        assert_edit_kwargs_match_envelope(
            {
                "model": APPROVED_MODEL,
                "size": APPROVED_SIZE,
                "quality": "high",
                "background": "transparent",
                "output_format": "png",
                "n": 1,
                "image": ("sketch.png", io.BytesIO(b"x"), "image/png"),
            }
        )


def test_alembic_014_required(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('013')"))
    with pytest.raises(OneCallGuardError, match="014"):
        assert_alembic_revision_014(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num = '014'"))
    assert assert_alembic_revision_014(engine) == "014"


def test_alembic_missing_table_refused(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    with pytest.raises(OneCallGuardError, match="alembic_version"):
        assert_alembic_revision_014(engine)


def test_settings_namespace_smoke():
    # Keep SimpleNamespace path honest for unit callers.
    s = SimpleNamespace(
        my_croquis_ai_enabled=True,
        my_croquis_ai_live_http=True,
        my_croquis_ai_spend_ceiling_usd=1.00,
        my_croquis_ai_max_usd_per_run=1.00,
        my_croquis_ai_max_usd_per_user_day=1.00,
        my_croquis_ai_max_exposure_cents=100,
        my_croquis_ai_estimate_cents=40,
        openai_image_model=APPROVED_MODEL,
        my_croquis_ai_image_size=APPROVED_SIZE,
        my_croquis_ai_image_quality=APPROVED_QUALITY,
        openai_api_key="sk-test",
        openai_base_url=None,
    )
    assert_effective_one_call_settings(s)
    assert_official_effective_base_url(s)


def test_storage_refuses_default_backend_root():
    with pytest.raises(OneCallGuardError, match="default app storage"):
        assert_dedicated_one_call_storage(
            SimpleNamespace(local_storage_root=str(default_backend_storage_root()))
        )


def test_storage_refuses_production_looking_path(tmp_path):
    bad = tmp_path / "var" / "www" / ONE_CALL_STORAGE_MARKER / "storage"
    bad.mkdir(parents=True)
    # Path string must contain forbidden fragment when resolved under /var/www-style.
    with pytest.raises(OneCallGuardError, match="production-looking|/var/www"):
        assert_dedicated_one_call_storage(
            SimpleNamespace(local_storage_root="/var/www/fashionrise/" + ONE_CALL_STORAGE_MARKER)
        )


def test_storage_refuses_missing_marker(tmp_path):
    root = tmp_path / "executor-storage"
    root.mkdir()
    with pytest.raises(OneCallGuardError, match=ONE_CALL_STORAGE_MARKER):
        assert_dedicated_one_call_storage(SimpleNamespace(local_storage_root=str(root)))


def test_storage_accepts_dedicated_marker_path(tmp_path):
    root = tmp_path / ONE_CALL_STORAGE_MARKER / "storage"
    root.mkdir(parents=True)
    assert assert_dedicated_one_call_storage(
        SimpleNamespace(local_storage_root=str(root))
    ) == root.resolve()


def _sqlite_freshness_schema(conn) -> None:
    """Mirror mapped ``__tablename__`` values (singular version table)."""
    from app.models.ai_job import AIJob
    from app.models.personal_croquis import PersonalCroquis, PersonalCroquisVersion
    from app.models.personal_croquis_spend import PersonalCroquisSpendReservation

    conn.execute(
        text(
            f"CREATE TABLE {AIJob.__tablename__} ("
            "id VARCHAR PRIMARY KEY, job_type VARCHAR, status VARCHAR)"
        )
    )
    conn.execute(text(f"CREATE TABLE {PersonalCroquis.__tablename__} (id VARCHAR PRIMARY KEY)"))
    conn.execute(
        text(
            f"CREATE TABLE {PersonalCroquisSpendReservation.__tablename__} "
            "(id VARCHAR PRIMARY KEY)"
        )
    )
    conn.execute(
        text(f"CREATE TABLE {PersonalCroquisVersion.__tablename__} (id VARCHAR PRIMARY KEY)")
    )


def test_fresh_db_refuses_existing_croquis_jobs(tmp_path):
    from app.models.ai_job import AIJob
    from app.models.personal_croquis import CROQUIS_GENERATE_JOB_TYPE

    engine = create_engine(f"sqlite:///{tmp_path / 'reuse.db'}")
    with engine.begin() as conn:
        _sqlite_freshness_schema(conn)
        conn.execute(
            text(
                f"INSERT INTO {AIJob.__tablename__} (id, job_type, status) "
                f"VALUES ('j1', '{CROQUIS_GENERATE_JOB_TYPE}', 'queued')"
            )
        )
    with pytest.raises(OneCallGuardError, match="reused disposable DB"):
        assert_disposable_db_fresh_for_one_call(engine)


def test_fresh_db_accepts_empty_croquis_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    with engine.begin() as conn:
        _sqlite_freshness_schema(conn)
    assert_disposable_db_fresh_for_one_call(engine)


def test_freshness_sql_uses_singular_version_tablename():
    from app.models.personal_croquis import PersonalCroquisVersion
    from app.services.personal_croquis_one_call import _croquis_freshness_count_sql

    assert PersonalCroquisVersion.__tablename__ == "personal_croquis_version"
    sqls = " ".join(sql for sql, _ in _croquis_freshness_count_sql())
    assert "personal_croquis_version" in sqls
    assert "personal_croquis_versions" not in sqls
