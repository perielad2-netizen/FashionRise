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
    # FashionRise Runway publish — rights to share with users + display license.
    runway_share_consent_version: str = "runway-share-2026-11-08"
    runway_share_notice_text: str = (
        "I confirm I have the rights to share this design and its images with other "
        "FashionRise users, and I grant FashionRise permission to display this content "
        "on the Runway."
    )
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

    # Legacy invite gate. Prefer REGISTRATION_MODE. When mode is unset:
    # false → closed, true → invite_only. Default false keeps production closed.
    registration_enabled: bool = False
    # Explicit registration mode. When set, overrides registration_enabled.
    registration_mode: Literal["closed", "invite_only", "public"] | None = None

    # When true, public registration requires SMTP and email ownership proof before
    # login. Default false: Create Account signs users in immediately (App Store 1.0).
    # Verification endpoints remain available for a future re-enable.
    email_verification_required: bool = False

    # Email delivery for optional public registration verification. Empty host → not configured.
    # Prefer existing SMTP over a new provider. Capture backend is for tests only.
    email_delivery_backend: Literal["smtp", "capture"] = "smtp"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = ""
    smtp_from_name: str = "FashionRise"
    email_verification_token_ttl_minutes: int = 60
    # Soft per-email resend cooldown (seconds) in addition to SlowAPI IP limits.
    email_verification_resend_cooldown_seconds: int = 60

    # Forgot-password email recovery. Default off — enable only after SMTP works.
    # SPA shows the Forgot password? link only when enabled AND email delivery is configured.
    password_reset_enabled: bool = False
    password_reset_token_ttl_minutes: int = 60
    # Soft per-email cooldown (seconds) in addition to SlowAPI IP limits on /forgot-password.
    password_reset_request_cooldown_seconds: int = 60

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
    # Opt-in finite-wallet override for purchase testing. Empty by default.
    # Wins over both the unlimited email list and User.ai_stars_unlimited.
    # Does not touch is_admin. Example: AI_STARS_FINITE_OVERRIDE_EMAILS=perielad2@gmail.com
    # Clear / remove an email here to restore that account's unlimited Stars.
    ai_stars_finite_override_emails: str = ""
    # Shop checkout remains disabled until payment is wired.
    stars_shop_checkout_enabled: bool = False

    # Web Push (VAPID). Empty = push subscribe/send disabled (fail closed).
    # Generate with: python -c "from py_vapid import Vapid01; v=Vapid01(); v.generate_keys(); print(v.public_key); print(v.private_key)"
    # Or: npx web-push generate-vapid-keys
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:ops@fashionrise.app"

    # Native push (FCM / APNs). Separate fail-closed flags — incomplete infra must not
    # break Web Push. Never commit private keys; set paths/IDs via secrets only.
    native_push_android_enabled: bool = False
    native_push_ios_enabled: bool = False
    # Optional FCM HTTP v1: path to service-account JSON (outside repo) + project id.
    native_push_fcm_service_account_json: str = ""
    native_push_fcm_project_id: str = ""
    # Optional APNs: path to .p8 (outside repo), key id, team id, topic (= bundle id).
    native_push_apns_key_path: str = ""
    native_push_apns_key_id: str = ""
    native_push_apns_team_id: str = ""
    native_push_apns_topic: str = "app.fashionrise.studio"
    native_push_apns_use_sandbox: bool = True

    # Store IAP verification (App Store / Play Store). Confirm stays fail-closed until ready.
    # Never commit real secrets. Legacy shared secret is unused (StoreKit 2 JWS only).
    iap_apple_shared_secret: str = ""
    # Path or inline JSON for Google Play Developer API service account.
    iap_google_service_account_json: str = ""
    # Dev-only escape hatch (historical). Forced OFF in production; Apple Phase A also
    # refuses unverified credit even in non-prod — send signed sandbox JWS instead.
    iap_allow_unverified_sandbox: bool = False
    # Phase B client: allow initiating *new* StoreKit purchases in the native shop.
    # Default OFF. Distinct from credit/reconcile (below).
    iap_apple_purchasing_enabled: bool = False
    # Server: allow verifying JWS + crediting Stars for completed Apple transactions
    # (including unfinished-txn recovery). Default OFF until Phase B ASN/refunds.
    # Never treat this as a production “bypass” — both gates stay false in Phase A.
    iap_apple_credit_enabled: bool = False
    # Controlled sandbox: comma-separated FashionRise account emails that may Buy +
    # confirm while public purchasing/credit gates stay OFF. Empty = no allowlist.
    # Does not enable unverified credit. Keep the list short (designated Testers only).
    iap_apple_sandbox_tester_emails: str = ""
    iap_apple_bundle_id: str = "app.fashionrise.studio"
    # App Store Connect Apple ID (public). Required for Production SignedDataVerifier.
    iap_apple_app_apple_id: int = 6832116469
    # OCSP / online chain checks for Apple roots (disable in offline unit tests).
    iap_apple_online_checks: bool = True
    # App Store Server API (ASC In-App Purchase key) — outbound API only.
    # Used for Request/Get Test Notification and future history lookups.
    # Private key stays on disk outside the repo; never commit .p8 contents.
    iap_apple_asc_issuer_id: str = ""
    iap_apple_asc_key_id: str = ""
    iap_apple_asc_private_key_path: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def strip_cors(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def production_safety(self) -> "Settings":
        # Always coerce — misconfiguration must not enable unverified credits in prod.
        if self.environment == "production" and self.iap_allow_unverified_sandbox:
            self.iap_allow_unverified_sandbox = False
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
        if self.iap_allow_unverified_sandbox:
            raise ValueError("IAP_ALLOW_UNVERIFIED_SANDBOX must be false in production")
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

    def email_delivery_configured(self) -> bool:
        """True when verification mail can be sent for the current environment.

        ``capture`` is test-only and never satisfies public registration in
        production (``ENVIRONMENT=production``), even if ``TESTING=true``.
        Authenticated SMTP requires encrypted transport (STARTTLS or implicit TLS).
        """
        backend = (self.email_delivery_backend or "smtp").strip().lower()
        if backend == "capture":
            # Capture is disposable-test only: TESTING=true AND not production.
            return bool(self.testing) and self.environment != "production"
        host = (self.smtp_host or "").strip()
        from_addr = (self.smtp_from_email or "").strip()
        if not (host and from_addr):
            return False
        user = (self.smtp_username or "").strip()
        if user:
            # Authenticated SMTP must use encrypted transport.
            if self.smtp_use_tls:
                return True
            # Implicit TLS (SMTPS) on 465 is acceptable without STARTTLS flag.
            return int(self.smtp_port) == 465
        return True

    def configured_registration_mode(self) -> Literal["closed", "invite_only", "public"]:
        if self.registration_mode is not None:
            return self.registration_mode
        return "invite_only" if self.registration_enabled else "closed"

    def effective_registration_mode(self) -> Literal["closed", "invite_only", "public"]:
        """Authoritative mode for register/status.

        When email verification is required, public without delivery stays closed.
        When verification is off, public mode does not depend on SMTP.
        """
        configured = self.configured_registration_mode()
        if (
            configured == "public"
            and self.email_verification_required
            and not self.email_delivery_configured()
        ):
            return "closed"
        return configured

    def password_reset_available(self) -> bool:
        """True only when the feature flag is on and outbound email can send."""
        return bool(self.password_reset_enabled) and self.email_delivery_configured()

    def password_reset_prerequisite(self) -> str | None:
        if self.password_reset_available():
            return None
        if not self.password_reset_enabled:
            return (
                "PASSWORD_RESET_ENABLED is false. Set PASSWORD_RESET_ENABLED=true after "
                "SMTP_HOST and SMTP_FROM_EMAIL (and credentials + TLS) are verified."
            )
        backend = (self.email_delivery_backend or "smtp").strip().lower()
        if backend == "capture":
            return (
                "PASSWORD_RESET_ENABLED=true rejects EMAIL_DELIVERY_BACKEND=capture unless "
                "TESTING=true and ENVIRONMENT is not production. Set EMAIL_DELIVERY_BACKEND=smtp "
                "with SMTP_HOST, SMTP_FROM_EMAIL, and encrypted transport "
                "(SMTP_USE_TLS=true or port 465) when using SMTP auth."
            )
        user = (self.smtp_username or "").strip()
        if user and not self.smtp_use_tls and int(self.smtp_port) != 465:
            return (
                "PASSWORD_RESET_ENABLED=true needs encrypted SMTP for authenticated relays: "
                "set SMTP_USE_TLS=true (STARTTLS) or use port 465 (SMTPS)."
            )
        return (
            "PASSWORD_RESET_ENABLED=true needs email delivery: set EMAIL_DELIVERY_BACKEND=smtp "
            "with SMTP_HOST and SMTP_FROM_EMAIL (and credentials + TLS as needed)."
        )

    def registration_public_prerequisite(self) -> str | None:
        if self.configured_registration_mode() != "public":
            return None
        if not self.email_verification_required:
            return None
        if self.email_delivery_configured():
            return None
        backend = (self.email_delivery_backend or "smtp").strip().lower()
        if backend == "capture":
            return (
                "PUBLIC registration with EMAIL_VERIFICATION_REQUIRED=true rejects "
                "EMAIL_DELIVERY_BACKEND=capture unless TESTING=true and ENVIRONMENT is "
                "not production. Set EMAIL_DELIVERY_BACKEND=smtp with SMTP_HOST, "
                "SMTP_FROM_EMAIL, and encrypted transport (SMTP_USE_TLS=true or port 465) "
                "when using SMTP auth — or set EMAIL_VERIFICATION_REQUIRED=false."
            )
        user = (self.smtp_username or "").strip()
        if user and not self.smtp_use_tls and int(self.smtp_port) != 465:
            return (
                "EMAIL_VERIFICATION_REQUIRED=true needs encrypted SMTP for authenticated "
                "relays: set SMTP_USE_TLS=true (STARTTLS) or use port 465 (SMTPS)."
            )
        return (
            "EMAIL_VERIFICATION_REQUIRED=true needs email delivery: set "
            "EMAIL_DELIVERY_BACKEND=smtp with SMTP_HOST and SMTP_FROM_EMAIL "
            "(and credentials + TLS as needed), or set EMAIL_VERIFICATION_REQUIRED=false "
            "for immediate public registration without verification."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
