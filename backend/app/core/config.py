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

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    ai_worker_enabled: bool = True
    ai_worker_poll_interval_seconds: float = 1.5
    ai_worker_batch_size: int = 12

    # OpenAI (optional — sketch + tech_pack jobs use vision + JSON when OPENAI_API_KEY is set)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    openai_timeout_seconds: float = 120.0
    openai_http_timeout_seconds: float = 45.0
    # Image generation for sketch_polish (“Your look”). Empty = skip image gen (text-only).
    openai_image_model: str = "gpt-image-1"
    openai_image_size: str = "1024x1536"
    openai_image_quality: str = "standard"

    max_upload_size_mb: int = 25
    allowed_upload_image_types: str = "image/jpeg,image/png,image/webp"

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
        """Keep uploads under backend/ even if the process cwd is the repo root."""
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
