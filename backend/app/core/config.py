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
    # Private Create My Croquis bytes — sibling of private_fabrics; never public static.
    private_croquis_subdir: str = "private_croquis"

    # Create My Croquis gates (independent of Studio FRONT_BACK/MAGIC/DUAL). Fail closed.
    my_croquis_upload_enabled: bool = False
    my_croquis_ai_enabled: bool = False
    # Stage C spend controls — operator ceiling default 0 → fail closed (no paid calls).
    my_croquis_ai_spend_ceiling_usd: float = 0.0
    my_croquis_ai_max_usd_per_run: float = 0.0
    my_croquis_ai_max_usd_per_user_day: float = 0.0
    my_croquis_ai_max_generations_per_user_day: int = 3
    # Soft expected cost (informational only). Not the reserved hard cap.
    my_croquis_ai_estimate_cents: int = 8
    # Conservative maximum authorized exposure (cents) reserved before enqueue.
    # Fail closed at 0 — must be explicitly configured for any live/test spend path.
    # Soft MY_CROQUIS_AI_ESTIMATE_CENTS must never be treated as this hard cap.
    my_croquis_ai_max_exposure_cents: int = 0
    # Live images.edit arming switch (default false). Even with AI gate + ceiling on,
    # real OpenAI HTTP requires this flag. Mocked client overrides bypass it in tests.
    my_croquis_ai_live_http: bool = False
    # Croquis-specific images.edit size/quality (must be allowlisted for the model).
    # Provider size is NOT the design plane — output is always fit-contain 768×1024.
    my_croquis_ai_image_size: str = "1024x1536"
    my_croquis_ai_image_quality: str = "medium"
    # Stale worker claim lease (seconds) before safe requeue / reconciliation.
    # Must exceed openai_timeout_seconds (+ normalization/attach margin). A 120s
    # lease with a 180s OpenAI timeout can mark a still-running images.edit as
    # reconciliation_required. Default 300 = 180s timeout + 120s margin.
    my_croquis_ai_claim_lease_seconds: int = 300
    my_croquis_ai_consent_max_age_seconds: int = 3600
    # Consent notice versions. Collection remains fail-closed until approved notice text is set.
    my_croquis_storage_consent_version: str = "storage-2026-11-01"
    my_croquis_ai_consent_version: str = "ai-provider-2026-11-01"
    my_croquis_adults_attestation_version: str = "adults-beta-2026-11-01"
    # Approved notice bodies. Empty (default) → refuse to record consent (not legal-authoritative).
    # Tests may inject synthetic fixtures via env; never ship production-legal copy here.
    my_croquis_adults_notice_text: str = ""
    my_croquis_storage_notice_text: str = ""
    my_croquis_ai_notice_text: str = ""
    # Consent / attestation validity windows (seconds).
    my_croquis_storage_consent_max_age_seconds: int = 3600
    # Adults-only account attestation: 0 = durable for this notice version (no daily re-check).
    # Bump my_croquis_adults_attestation_version / notice text when the legal copy changes.
    my_croquis_adults_attestation_max_age_seconds: int = 0
    # Upload bounds (source photos). Separate from fabric limits.
    max_croquis_upload_size_mb: int = 10
    max_croquis_dimension_px: int = 4096
    max_croquis_total_pixels: int = 4096 * 4096
    croquis_name_max_length: int = 80
    # Retention defaults (design §6.2) — offline sweeper only; no production timers.
    my_croquis_abandoned_upload_hours: int = 24
    my_croquis_source_retention_days: int = 7
    my_croquis_accepted_source_purge_hours: int = 24
    my_croquis_cleanup_batch_size: int = 50
    # Create Real Design V1 flag (legacy). Prefer techpack_ai_enabled.
    techpack_ai_draft_enabled: bool = False
    # Create Real Design AI — fail closed without spend ceiling + (for professional) allowlist.
    techpack_ai_enabled: bool = False
    # Operator must set a positive ceiling (USD) before any paid techpack AI call.
    techpack_ai_spend_ceiling_usd: float = 0.0
    # Professional image-aware runs need a higher ceiling than text tips ($0.50 is inadequate).
    techpack_ai_max_usd_per_run: float = 8.0
    techpack_ai_max_usd_per_user_day: float = 20.0
    # Legacy V2 text-only estimate (cents). Professional uses image-aware estimator.
    techpack_ai_estimate_chat_cents: int = 8
    # Conservative professional estimate floor/ceiling used for UI + preflight (cents).
    techpack_ai_estimate_professional_cents_base: int = 250
    techpack_ai_estimate_professional_cents_per_piece: int = 180
    techpack_ai_estimate_professional_cents_propose_back: int = 80
    # Comma-separated owner emails and/or user UUIDs allowed for paid professional AI.
    # Empty = nobody (fail closed even if techpack_ai_enabled). Never commit real IDs.
    techpack_ai_owner_allowlist: str = ""
    # Max concurrent paid professional runs system-wide (reservation lock).
    techpack_ai_max_concurrent_runs: int = 2
    # Max image generations per professional run (front/back/detail/pattern).
    # 10 allows 2-piece outfits: front+back+pattern+detail per garment.
    techpack_ai_max_images_per_run: int = 10
    # Entitlement boundary placeholder for future premium billing (not charged here).
    techpack_ai_requires_entitlement: bool = False

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    ai_worker_enabled: bool = True
    ai_worker_poll_interval_seconds: float = 1.5
    ai_worker_batch_size: int = 12

    # FASHN Virtual Try-On (optional specialist path — OpenAI try-on remains default).
    # Fail closed: enabled + live_http + non-empty FASHN_API_KEY required for paid calls.
    # Never expose the key to the frontend or commit it.
    fashn_api_key: str | None = None
    fashn_try_on_enabled: bool = False
    fashn_try_on_live_http: bool = False
    # Soft estimate per FASHN credit (~$0.075 on-demand ≈ 8¢). Two-piece = 2×.
    fashn_try_on_estimate_cents: int = 8
    # Soft estimate per OpenAI garment-realism images.edit (one call per plate).
    fashn_garment_realism_estimate_cents: int = 8
    fashn_api_base_url: str = "https://api.fashn.ai"
    fashn_poll_interval_seconds: float = 2.0
    fashn_poll_timeout_seconds: float = 120.0
    # Owner-only FASHN Try-On Max experimental lane (#173). Fail closed:
    # enabled + live_http + non-empty owner allowlist required. Empty allowlist = nobody.
    fashn_try_on_max_enabled: bool = False
    fashn_try_on_max_live_http: bool = False
    fashn_try_on_max_owner_allowlist: str = ""
    # Soft UI budget target (credits). Does not hard-block; spend ceilings still apply.
    fashn_try_on_max_soft_budget_credits: int = 90

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
    # Optional seamless app login: verify Access JWT → map email to existing User → issue tokens.
    # Requires team domain + AUD. Never auto-provisions users. Default off until AUD is configured.
    # Prefer Google OAuth for public login; keep CF Access SSO off when Access is removed.
    cf_access_sso_login: bool = False

    # Google Sign-In (Gmail) — app login/register without Cloudflare Access.
    # When client id+secret+redirect are set, /auth/google/* is enabled.
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    # Where to send the browser after Google callback (SPA).
    public_app_url: str = "https://fashionrise.app"
    # Auto-create FashionRise users on first Google sign-in (no invite).
    google_oauth_auto_register: bool = True

    # AI Stars wallet — spend gates for AI features.
    # New profiles start with starting_balance (first Magic free when magic_cost equals it).
    ai_stars_starting_balance: int = 10
    ai_stars_magic_cost: int = 10
    ai_stars_croquis_cost: int = 10
    ai_stars_pdf_cost: int = 50
    ai_stars_fabric_cost: int = 5
    # Comma-separated emails with endless Stars (never debit).
    ai_stars_unlimited_emails: str = "perielad@gmail.com,perielad2@gmail.com"
    # Shop checkout remains disabled until payment is wired.
    stars_shop_checkout_enabled: bool = False

    # Web Push (VAPID). Empty = push subscribe/send disabled (fail closed).
    # Generate with: python -c "from py_vapid import Vapid01; v=Vapid01(); v.generate_keys(); print(v.public_key); print(v.private_key)"
    # Or: npx web-push generate-vapid-keys
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:ops@fashionrise.app"

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

    @property
    def max_croquis_upload_bytes(self) -> int:
        return max(1, self.max_croquis_upload_size_mb) * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
