import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
    ValidationAppError,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.auth import (
    RegisterResponse,
    RegistrationStatusResponse,
    UserLogin,
    UserRegister,
)
from app.services import ai_stars, email_verification, invitation_service

_log = logging.getLogger(__name__)


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


def registration_status_payload() -> RegistrationStatusResponse:
    settings = get_settings()
    configured = settings.configured_registration_mode()
    effective = settings.effective_registration_mode()
    prerequisite = settings.registration_public_prerequisite()
    available = effective in ("invite_only", "public")
    requires_verification = effective == "public" and bool(settings.email_verification_required)
    note = None
    if configured == "public" and effective != "public":
        note = prerequisite
    elif effective == "invite_only":
        note = "Invitation code required for email registration."
    elif effective == "public" and requires_verification:
        note = "Public email registration with email verification."
    elif effective == "public":
        note = "Public email registration — create an account and enter the Studio."
    elif effective == "closed":
        note = "Email registration is closed."
    return RegistrationStatusResponse(
        mode=effective,
        configured_mode=configured,
        registration_available=available,
        requires_invitation=effective == "invite_only",
        requires_email_verification=requires_verification,
        email_delivery_configured=settings.email_delivery_configured(),
        prerequisite=prerequisite,
        note=note,
    )


def _assert_registration_open(mode: str) -> None:
    if mode == "closed":
        settings = get_settings()
        prereq = settings.registration_public_prerequisite()
        if prereq and settings.configured_registration_mode() == "public":
            raise ForbiddenError(prereq)
        raise ForbiddenError("Registration is not available")


def register_user(db: Session, data: UserRegister) -> RegisterResponse:
    settings = get_settings()
    mode = settings.effective_registration_mode()
    _assert_registration_open(mode)

    email_norm = _normalize_email(str(data.email))
    username = data.username.strip()
    if not username:
        raise ValidationAppError("Username is required")

    if mode == "invite_only":
        return _register_invite_only(db, data, email_norm=email_norm, username=username)
    if mode == "public":
        return _register_public(db, data, email_norm=email_norm, username=username)
    raise ForbiddenError("Registration is not available")


def _register_invite_only(
    db: Session,
    data: UserRegister,
    *,
    email_norm: str,
    username: str,
) -> RegisterResponse:
    raw_invite = (data.invitation_code or "").strip()
    if not raw_invite:
        raise ValidationAppError("Invitation code is required")
    if len(raw_invite) < 16:
        raise ValidationAppError("Invitation code looks incomplete")

    # Lock + validate invitation before creating the user. Same transaction as insert.
    invitation = invitation_service.assert_invitation_redeemable(
        db,
        raw_token=raw_invite,
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
        email_verified=True,
    )
    ai_stars.apply_new_user_stars(user)
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
            raise conflict from None
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(user)
    access, refresh = issue_tokens(db, user)
    return RegisterResponse(
        status="authenticated",
        access_token=access,
        refresh_token=refresh,
        email=user.email,
        message="Account created",
    )


def _register_public(
    db: Session,
    data: UserRegister,
    *,
    email_norm: str,
    username: str,
) -> RegisterResponse:
    """Public self-serve registration.

    Default (EMAIL_VERIFICATION_REQUIRED=false): create a verified account and
    issue a session immediately — no SMTP. When verification is re-enabled later,
    the mint/send path below remains available.
    """
    settings = get_settings()
    require_verify = bool(settings.email_verification_required)
    if require_verify and not settings.email_delivery_configured():
        raise ForbiddenError(
            settings.registration_public_prerequisite()
            or "Public registration requires email delivery"
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
        # Immediate access when verification is off; otherwise pending proof.
        email_verified=not require_verify,
    )
    # Normal starting Stars — never admin / never unlimited via this path.
    ai_stars.apply_new_user_stars(user)
    if user.is_admin or user.ai_stars_unlimited:
        user.is_admin = False
        user.ai_stars_unlimited = False
    db.add(user)

    raw_token: str | None = None
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
        if require_verify:
            locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
            assert locked is not None
            raw_token = email_verification.mint_verification_token(db, locked)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        conflict = _conflict_from_integrity(exc)
        if conflict is not None:
            raise conflict from None
        raise
    except Exception:
        db.rollback()
        raise

    if not require_verify:
        db.refresh(user)
        access, refresh = issue_tokens(db, user)
        return RegisterResponse(
            status="authenticated",
            access_token=access,
            refresh_token=refresh,
            email=user.email,
            message="Account created",
        )

    delivery_note = (
        "Check your email to verify your account before signing in. "
        "Open the link, then confirm on the page — opening alone does not verify."
    )
    try:
        assert raw_token is not None
        email_verification.send_verification_for_raw_token(
            to_email=email_norm,
            raw_token=raw_token,
        )
    except Exception:  # noqa: BLE001 — delivery failure must not undo committed account
        _log.warning("public_register_verification_email_deferred")
        delivery_note = (
            "Your account was created, but the verification email could not be sent yet. "
            "Use Resend verification from the registration page, then confirm the link."
        )

    return RegisterResponse(
        status="verification_pending",
        email=email_norm,
        message=delivery_note,
    )


def _email_verification_blocks_access(user: User) -> bool:
    """When verification is required, unverified password users cannot get a session."""
    settings = get_settings()
    return bool(settings.email_verification_required) and not user.email_verified


def authenticate(db: Session, data: UserLogin) -> User:
    email_norm = _normalize_email(str(data.email))
    user = db.scalar(select(User).where(func.lower(User.email) == email_norm))
    if not user or not verify_password(_login_password(data.password), user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account disabled")
    if _email_verification_blocks_access(user):
        raise UnauthorizedError(
            "Email not verified. Check your inbox for the verification link, or request a new one."
        )
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, str]:
    if _email_verification_blocks_access(user):
        raise UnauthorizedError("Email not verified")
    access = create_access_token(user.id)
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    row = RefreshToken(user_id=user.id, token_hash=digest, expires_at=expires_at)
    db.add(row)
    db.commit()
    return access, raw


def _expires_ok(expires_at: datetime) -> bool:
    now = datetime.now(UTC)
    exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
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
    if _email_verification_blocks_access(user):
        raise UnauthorizedError("Email not verified")

    row.revoked_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    return issue_tokens(db, user)


def revoke_all_refresh_tokens_for_user(db: Session, user: User) -> None:
    """Invalidate every active refresh token for this user (sign-out all sessions)."""
    now = datetime.now(UTC)
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()


def delete_account(db: Session, user: User) -> None:
    """Permanently delete the signed-in account and cascade owned rows.

    Queues private media cleanup in the same transaction (see
    ``prepare_owner_account_croquis_cleanup``) so filesystem unlinks happen after
    a successful commit. Apple App Store Guideline 5.1.1(v) requires in-app
    account deletion when account creation is offered.

    Uses a SQL DELETE (not ``session.delete``) so SQLAlchemy does not try to
    NULL out non-nullable child FKs before the database CASCADE runs.
    """
    from sqlalchemy import delete as sa_delete

    from app.services import personal_croquis_service

    user_id = user.id
    email = user.email
    personal_croquis_service.prepare_owner_account_croquis_cleanup(db, user_id)
    db.execute(sa_delete(User).where(User.id == user_id))
    db.commit()
    _log.info("account_deleted user_id=%s email_suffix=%s", user_id, (email or "")[-12:])
