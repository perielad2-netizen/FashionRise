from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.auth import RefreshRequest, TokenResponse, UserLogin, UserRegister
from app.schemas.user import UserRead
from app.services import auth_service, cf_access_sso

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
@limiter.limit("20/minute")
def register(request: Request, data: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    user = auth_service.register_user(db, data)
    access, refresh = auth_service.issue_tokens(db, user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("30/minute")
def login(request: Request, data: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = auth_service.authenticate(db, data)
    access, refresh = auth_service.issue_tokens(db, user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/cf-access/status")
def cf_access_sso_status() -> dict[str, Any]:
    """Whether seamless Cloudflare Access login is configured (never starts a session)."""
    return {
        "sso_enabled": cf_access_sso.sso_configured(),
        "note": (
            "When enabled, POST /auth/cf-access/login verifies Cf-Access-Jwt-Assertion "
            "and maps the verified email to an existing FashionRise user."
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


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("60/minute")
def refresh_token(request: Request, data: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    access, refresh = auth_service.refresh_session(db, data.refresh_token)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
def logout(request: Request, user: CurrentUser, db: Session = Depends(get_db)) -> Response:
    """Revoke all refresh tokens for the current user. Access token remains valid until expiry."""
    auth_service.revoke_all_refresh_tokens_for_user(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
