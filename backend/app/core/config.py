from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load backend/.env (same file Alembic uses), not cwd-relative ".env" — avoids migrating one DB while the API connects to another.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ENV = _BACKEND_ROOT / ".env"
_settings_env_kw: dict = {"env_file_encoding": "utf-8", "extra": "ignore"}
if _BACKEND_ENV.is_file():
    _settings_env_kw["env_file"] = str(_BACKEND_ENV)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(**_settings_env_kw)

    app_name: str = "FashionRise API"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    testing: bool = False

    sqlalchemy_echo: bool = False

    database_url: str = "postgresql+psycopg2://fashionrise:fashionrise@localhost:5432/fashionrise"

    secret_key: str = "CHANGE_ME"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    algorithm: str = "HS256"

    cors_origins: str = "*"

    storage_backend: Literal["local"] = "local"
    local_storage_root: str = "./data/storage"
    public_upload_base_url: str = "http://127.0.0.1:8001/static/uploads"
    upload_subdir: str = "uploads"
    # Private fabric bytes live here — sibling of upload_subdir, never mounted publicly.
    private_fabric_subdir: str = "private_fabrics"
    # Private tech-pack PDFs — never mounted under /static/uploads.
    private_techpack_subdir: str = "private_techpacks"
    # Create Real Design V1 flag (legacy). Prefer techpack_ai_enabled.
    techpack_ai_draft_enabled: bool = False
    # Create Real Design V2 — explicit user-confirmed AI. Fail closed without spend ceiling.
    techpack_ai_enabled: bool = False
    # Operator must set a positive ceiling (USD) before any paid techpack AI call.
    techpack_ai_spend_ceiling_usd: float = 0.0
    techpack_ai_max_usd_per_run: float = 0.50
    techpack_ai_max_usd_per_user_day: float = 2.0
    # Estimated chat cost used for pre-flight budgeting (cents).
    techpack_ai_estimate_chat_cents: int = 8
    # Entitlement boundary placeholder for future premium billing (not charged here).
    techpack_ai_requires_entitlement: bool = False

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    ai_worker_enabled: bool = True
    ai_worker_poll_interval_seconds: float = 1.5
    ai_worker_batch_size: int = 12

    # OpenAI (optional — sketch pipeline jobs use vision + JSON when OPENAI_API_KEY is set)
    # Default chat model is gpt-6-luna (official replacement for deprecated gpt-4o-mini).
    # Override with OPENAI_MODEL. Image edit/generate stays on OPENAI_IMAGE_MODEL.
    openai_api_key: str | None = None
    openai_model: str = "gpt-6-luna"
    openai_base_url: str | None = None
    openai_timeout_seconds: float = 180.0
    openai_http_timeout_seconds: float = 60.0
    # Chat Completions reasoning_effort. Default "none" is for gpt-6-luna only.
    # gpt-6-astra / gpt-6.1-sol reject "none"; gpt-4o* omits the field (rollback).
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "none"
    # Visible JSON budget. With reasoning_effort=none this is not shared with hidden
    # reasoning tokens. 1400 covers summary + bullets + optional image_prompt.
    openai_max_completion_tokens: int = 1400
    # sketch_polish look image (images.edit). Set OPENAI_IMAGE_MODEL=off to disable.
    # Default: gpt-image-2.5-sunburst (gpt-image-1 shut down 2026-10-23).
    openai_image_model: str = "gpt-image-2.5-sunburst"
    openai_image_size: str = "1024x1536"
    # FashionRise default quality is high. Legacy "standard" maps to high in code.
    # Explicit xhigh/max (and unknown values) fail closed before any paid images.edit.
    openai_image_quality: str = "high"

    max_upload_size_mb: int = 25
    allowed_upload_image_types: str = "image/jpeg,image/png,image/webp"
    # Private Studio fabric library (WEB-V4C). Separate from public /static/uploads.
    max_fabric_upload_size_mb: int = 8
    max_fabric_dimension_px: int = 2048
    fabric_name_max_length: int = 80

    # Invite-only beta registration. Default false so production stays closed until
    # an independently approved deployment flips the gate (and Nginx allowlists POST).
    registration_enabled: bool = False

    # When true, rate limiting may key on X-Real-IP set by a trusted reverse proxy
    # that overwrites the header with $remote_addr. Default false ignores client XFF.
    trust_proxy_headers: bool = False

    # Origin Cloudflare Access JWT gate for /api/** (default off until approved deploy).
    # When true, CF_ACCESS_TEAM_DOMAIN + CF_ACCESS_AUD are required (fail closed at startup).
    cf_access_jwt_validation: bool = False
    cf_access_team_domain: str = ""
    cf_access_aud: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def strip_cors(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def production_safety(self) -> "Settings":
        if self.testing:
            return self
        if self.environment != "production":
            return self
        if not self.secret_key or self.secret_key in ("CHANGE_ME", "change-me-to-a-long-random-string-in-production"):
            raise ValueError("SECRET_KEY must be set to a long random value in production")
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY should be at least 32 characters in production")
        if self.cors_origins.strip() == "*":
            raise ValueError("CORS_ORIGINS must not be * in production; list explicit HTTPS origins")
        if self.debug:
            raise ValueError("DEBUG must be false in production")
        return self

    @model_validator(mode="after")
    def resolve_local_storage_root(self) -> "Settings":
        """Keep uploads under backend/ even if process cwd is the repo root."""
        root = Path(self.local_storage_root)
        if not root.is_absolute():
            self.local_storage_root = str((_BACKEND_ROOT / root).resolve())
        return self

    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def allowed_upload_content_types(self) -> set[str]:
        return {x.strip().lower() for x in self.allowed_upload_image_types.split(",") if x.strip()}

    @property
    def max_upload_bytes(self) -> int:
        return max(1, self.max_upload_size_mb) * 1024 * 1024

    @property
    def max_fabric_upload_bytes(self) -> int:
        return max(1, self.max_fabric_upload_size_mb) * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
