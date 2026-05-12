from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.auth import RefreshRequest, TokenResponse, UserLogin, UserRegister
from app.schemas.user import UserRead
from app.services import auth_service
from app.auth.dependencies import CurrentUser

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
