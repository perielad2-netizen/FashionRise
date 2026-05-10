import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.auth import UserLogin, UserRegister


def register_user(db: Session, data: UserRegister) -> User:
    if db.scalar(select(User).where(User.email == data.email)):
        raise ConflictError("Email already registered")
    if db.scalar(select(User).where(User.username == data.username)):
        raise ConflictError("Username already taken")

    user = User(
        email=str(data.email),
        username=data.username,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.flush()
    profile = UserProfile(
        user_id=user.id,
        display_name=data.display_name or data.username,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, data: UserLogin) -> User:
    user = db.scalar(select(User).where(User.email == str(data.email)))
    if not user or not verify_password(data.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account disabled")
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, str]:
    access = create_access_token(user.id)
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    row = RefreshToken(user_id=user.id, token_hash=digest, expires_at=expires_at)
    db.add(row)
    db.commit()
    return access, raw


def _expires_ok(expires_at: datetime) -> bool:
    now = datetime.now(timezone.utc)
    exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    return exp >= now


def refresh_session(db: Session, raw_refresh: str) -> tuple[str, str]:
    digest = hashlib.sha256(raw_refresh.encode()).hexdigest()
    row = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == digest,
            RefreshToken.revoked_at.is_(None),
        )
    )
    if not row or not _expires_ok(row.expires_at):
        raise UnauthorizedError("Invalid or expired refresh token")
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("User inactive")

    row.revoked_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    return issue_tokens(db, user)
