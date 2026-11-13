from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.errors import AppError, ValidationAppError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.auth import (
    DeleteAccountRequest,
    ForgotPasswordRequest,
    GoogleNativeHandoffRequest,
    PasswordResetStatusResponse,
    RefreshRequest,
    RegisterResponse,
    RegistrationStatusResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    VerifyEmailRequest,
)
from app.schemas.user import UserRead
from app.services import (
    ai_stars,
    auth_service,
    cf_access_sso,
    email_verification,
    google_oauth,
    password_reset,
)

router = APIRouter()


@router.get("/registration/status", response_model=RegistrationStatusResponse)
@limiter.limit("60/minute")
def registration_status(request: Request) -> RegistrationStatusResponse:
    """Public capability probe — SPA uses this to show/hide Create Account."""
    return auth_service.registration_status_payload()


@router.post("/register", response_model=RegisterResponse)
@limiter.limit("10/minute;40/hour")
def register(request: Request, data: UserRegister, db: Session = Depends(get_db)) -> RegisterResponse:
    return auth_service.register_user(db, data)


@router.post("/verify-email", response_model=TokenResponse)
@limiter.limit("20/minute;60/hour")
def verify_email(
    request: Request,
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = email_verification.verify_email_token(db, data.token)
    access, refresh = auth_service.issue_tokens(db, user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute;20/hour")
def resend_verification(
    request: Request,
    data: ResendVerificationRequest,
    db: Session = Depends(get_db),
) -> Response:
    email_verification.resend_verification(db, str(data.email))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("30/minute")
def login(request: Request, data: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = auth_service.authenticate(db, data)
    access, refresh = auth_service.issue_tokens(db, user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/password-reset/status", response_model=PasswordResetStatusResponse)
@limiter.limit("60/minute")
def password_reset_status(request: Request) -> PasswordResetStatusResponse:
    """Public capability probe — SPA shows Forgot password? only when available."""
    return PasswordResetStatusResponse(**password_reset.status_payload())


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute;20/hour")
def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> Response:
    """Email a single-use reset link. Opaque success (no account oracle) when available."""
    password_reset.request_password_reset(db, str(data.email))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", response_model=TokenResponse)
@limiter.limit("20/minute;60/hour")
def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Redeem reset token, set new password, revoke other sessions, sign the user in."""
    user = password_reset.reset_password_with_token(db, data.token, data.password)
    # Drop every prior refresh session before issuing a fresh pair.
    auth_service.revoke_all_refresh_tokens_for_user(db, user)
    access, refresh = auth_service.issue_tokens(db, user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/cf-access/status")
def cf_access_sso_status() -> dict[str, Any]:
    """Whether seamless Cloudflare Access login is configured (prefer Google OAuth)."""
    return {
        "sso_enabled": cf_access_sso.sso_configured(),
        "note": (
            "When enabled, POST /auth/cf-access/login verifies Cf-Access-Jwt-Assertion "
            "and maps the verified email to an existing FashionRise user. "
            "Prefer /auth/google when Cloudflare Access is disabled."
        ),
    }


@router.post("/cf-access/login", response_model=TokenResponse)
@limiter.limit("30/minute")
async def cf_access_login(
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
) -> TokenResponse:
    """Seamless login from a verified Cloudflare Access JWT (existing users only)."""
    result = await cf_access_sso.login_with_access_assertion(db, request)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    )


@router.get("/google/status")
def google_oauth_status() -> dict[str, Any]:
    """Public: whether Google Sign-In is configured (no secrets)."""
    return google_oauth.status_payload()


@router.get("/google/start")
@limiter.limit("40/minute")
def google_oauth_start(
    request: Request,
    next: str = "/studio",
    client: str = "web",
) -> RedirectResponse:
    """Begin Google OAuth — redirects the browser to Google accounts.

    ``client=android`` marks the signed OAuth state so the callback returns a
    custom-scheme handoff URL instead of SPA hash tokens.
    """
    if not google_oauth.google_oauth_configured():
        raise ValidationAppError("Google sign-in is not configured")
    state = google_oauth.mint_oauth_state(next_path=next or "/studio", client=client)
    return RedirectResponse(url=google_oauth.authorization_url(state=state), status_code=302)


@router.get("/google/callback")
@limiter.limit("40/minute")
async def google_oauth_callback(
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Google redirects here; exchange code, upsert user, redirect SPA or native handoff."""
    app_url = (get_settings().public_app_url or "https://fashionrise.app").rstrip("/")
    if error:
        return RedirectResponse(url=f"{app_url}/login?error={quote(error)}", status_code=302)
    if not code or not state:
        return RedirectResponse(url=f"{app_url}/login?error=google_missing_code", status_code=302)
    try:
        state_data = google_oauth.parse_oauth_state(state)
        userinfo = await google_oauth.exchange_code_for_userinfo(code)
        user = google_oauth.upsert_google_user(db, userinfo=userinfo)
        access, refresh = google_oauth.issue_tokens_for_google_user(db, user)
        next_path = str(state_data.get("next") or "/studio")
        client = str(state_data.get("client") or "web")
        return RedirectResponse(
            url=google_oauth.complete_login_redirect(
                access=access, refresh=refresh, next_path=next_path, client=client
            ),
            status_code=302,
        )
    except AppError as exc:
        return RedirectResponse(
            url=f"{app_url}/login?error={quote(str(exc.message)[:180])}",
            status_code=302,
        )
    except Exception:  # noqa: BLE001 — browser UX: never dump stack to redirect target
        return RedirectResponse(
            url=f"{app_url}/login?error=google_sign_in_failed",
            status_code=302,
        )


@router.post("/google/native-handoff", response_model=TokenResponse)
@limiter.limit("30/minute;120/hour")
def google_native_handoff(
    request: Request,
    data: GoogleNativeHandoffRequest,
) -> TokenResponse:
    """Redeem a one-time Android OAuth handoff code for FashionRise session tokens."""
    redeemed = google_oauth.redeem_native_handoff(data.code)
    return TokenResponse(
        access_token=redeemed["access_token"],
        refresh_token=redeemed["refresh_token"],
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("60/minute")
def refresh_token(request: Request, data: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    access, refresh = auth_service.refresh_session(db, data.refresh_token)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    data = UserRead.model_validate(user)
    # Always publish the *effective* unlimited flag (finite override wins over DB).
    return data.model_copy(
        update={"ai_stars_unlimited": ai_stars.user_has_unlimited_stars(user)}
    )


@router.get("/stars")
def stars_wallet(user: CurrentUser) -> dict:
    """Public wallet + feature costs for Studio UI."""
    bal = ai_stars.public_balance(user)
    return bal


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
def logout(request: Request, user: CurrentUser, db: Session = Depends(get_db)) -> Response:
    """Revoke all refresh tokens for the current user. Access token remains valid until expiry."""
    auth_service.revoke_all_refresh_tokens_for_user(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute;20/hour")
def delete_account(
    request: Request,
    data: DeleteAccountRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Response:
    """Permanently delete the current user's account (App Store Guideline 5.1.1(v))."""
    if data.confirm != "DELETE":
        raise ValidationAppError("Confirmation required")
    auth_service.delete_account(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
