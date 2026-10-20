import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.auth import UserLogin, UserRegister
from app.services import invitation_service


def _normalize_email(email: str) -> str:
    return invitation_service.normalize_email(email)


def _login_password(plain: str) -> str:
    """Trim accidental whitespace from UI / paste (password body is rarely intentionally all-space)."""
    return (plain or "").strip()


def _conflict_from_integrity(exc: IntegrityError) -> ConflictError | None:
    """Map recognized users uniqueness violations to HTTP 409. Return None for unrelated errors."""
    orig = getattr(exc, "orig", None)
    text = f"{orig} {exc}".lower()
    # PostgreSQL constraint / column hints from ix_users_email / users_email_key, etc.
    if "ix_users_email" in text or "users_email" in text or "(email)" in text:
        return ConflictError("Email already registered")
    if "ix_users_username" in text or "users_username" in text or "(username)" in text:
        return ConflictError("Username already taken")
    diag = getattr(orig, "diag", None)
    constraint = (getattr(diag, "constraint_name", None) or "").lower()
    if "email" in constraint:
        return ConflictError("Email already registered")
    if "username" in constraint:
        return ConflictError("Username already taken")
    return None


def register_user(db: Session, data: UserRegister) -> User:
    settings = get_settings()
    if not settings.registration_enabled:
        raise ForbiddenError("Registration is not available")

    email_norm = _normalize_email(str(data.email))
    username = data.username.strip()
    if not username:
        raise ConflictError("Username already taken")

    # Lock + validate invitation before creating the user. Same transaction as insert.
    invitation = invitation_service.assert_invitation_redeemable(
        db,
        raw_token=data.invitation_code,
        email=email_norm,
    )

    if db.scalar(select(User).where(func.lower(User.email) == email_norm)):
        raise ConflictError("Email already registered")
    if db.scalar(select(User).where(User.username == username)):
        raise ConflictError("Username already taken")

    user = User(
        email=email_norm,
        username=username,
        hashed_password=hash_password(_login_password(data.password)),
        is_admin=False,
        is_active=True,
    )
    db.add(user)

    try:
        db.flush()
        profile = UserProfile(
            user_id=user.id,
            display_name=(
                data.display_name.strip()
                if data.display_name and data.display_name.strip()
                else username
            ),
        )
        db.add(profile)
        invitation_service.mark_redeemed(db, invitation, user.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        conflict = _conflict_from_integrity(exc)
        if conflict is not None:
            # Invitation was never committed as redeemed; loser may retry with a fresh invite
            # or the other invite remains pending when this invite lost on username/email.
            raise conflict from None
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(user)
    return user


def authenticate(db: Session, data: UserLogin) -> User:
    email_norm = _normalize_email(str(data.email))
    user = db.scalar(select(User).where(func.lower(User.email) == email_norm))
    if not user or not verify_password(_login_password(data.password), user.hashed_password):
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


def revoke_all_refresh_tokens_for_user(db: Session, user: User) -> None:
    """Invalidate every active refresh token for this user (sign-out all sessions)."""
    now = datetime.now(timezone.utc)
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
