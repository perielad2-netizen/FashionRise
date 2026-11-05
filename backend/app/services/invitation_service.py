"""Invite-only beta registration ledger.

Plaintext invitation tokens are returned once at creation time and never stored.
Only SHA-256 digests are persisted.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ConflictError, ForbiddenError
from app.models.registration_invitation import RegistrationInvitation


def normalize_email(email: str) -> str:
    return str(email).strip().lower()


def hash_invitation_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def generate_invitation_token() -> str:
    # ~256 bits of entropy; URL-safe for out-of-band delivery.
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class CreatedInvitation:
    id: uuid.UUID
    email: str
    expires_at: datetime
    # Returned once to the operator — never log or persist.
    plaintext_token: str


def create_invitation(
    db: Session,
    *,
    email: str,
    expires_in_hours: int = 72,
    note: str | None = None,
) -> CreatedInvitation:
    if expires_in_hours < 1 or expires_in_hours > 24 * 30:
        raise AppError("invalid_expiry", "expires_in_hours must be between 1 and 720", 400)

    email_norm = normalize_email(email)
    if not email_norm or "@" not in email_norm:
        raise AppError("invalid_email", "A valid invitation email is required", 400)

    raw = generate_invitation_token()
    digest = hash_invitation_token(raw)
    now = datetime.now(timezone.utc)
    row = RegistrationInvitation(
        email_normalized=email_norm,
        token_hash=digest,
        expires_at=now + timedelta(hours=expires_in_hours),
        note=(note.strip() if note and note.strip() else None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CreatedInvitation(
        id=row.id,
        email=row.email_normalized,
        expires_at=row.expires_at,
        plaintext_token=raw,
    )


def invitation_status(row: RegistrationInvitation) -> str:
    now = datetime.now(timezone.utc)
    if row.redeemed_at is not None:
        return "redeemed"
    if row.revoked_at is not None:
        return "revoked"
    exp = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if exp < now:
        return "expired"
    return "pending"


def get_invitation(db: Session, invitation_id: uuid.UUID) -> RegistrationInvitation | None:
    return db.get(RegistrationInvitation, invitation_id)


def list_invitations_for_email(db: Session, email: str) -> list[RegistrationInvitation]:
    email_norm = normalize_email(email)
    return list(
        db.scalars(
            select(RegistrationInvitation)
            .where(RegistrationInvitation.email_normalized == email_norm)
            .order_by(RegistrationInvitation.created_at.desc())
        ).all()
    )


def _lock_invitation_by_id(db: Session, invitation_id: uuid.UUID) -> RegistrationInvitation | None:
    return db.scalar(
        select(RegistrationInvitation)
        .where(RegistrationInvitation.id == invitation_id)
        .with_for_update()
    )


def revoke_invitation(db: Session, invitation_id: uuid.UUID) -> RegistrationInvitation:
    """Revoke under the same row lock used by redemption so races have a single winner."""
    row = _lock_invitation_by_id(db, invitation_id)
    if not row:
        raise AppError("not_found", "Invitation not found", 404)
    status = invitation_status(row)
    if status == "redeemed":
        raise ConflictError("Invitation was already redeemed")
    if status == "revoked":
        db.commit()
        db.refresh(row)
        return row
    row.revoked_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _lock_invitation_by_token(db: Session, raw_token: str) -> RegistrationInvitation | None:
    digest = hash_invitation_token(raw_token)
    # Row lock so concurrent redemptions/revocations serialize correctly.
    return db.scalar(
        select(RegistrationInvitation)
        .where(RegistrationInvitation.token_hash == digest)
        .with_for_update()
    )


def assert_invitation_redeemable(
    db: Session,
    *,
    raw_token: str,
    email: str,
) -> RegistrationInvitation:
    """Validate and lock an invitation for redemption. Does not mark redeemed."""
    token = (raw_token or "").strip()
    if not token:
        raise ForbiddenError("A valid invitation is required to create an account")

    row = _lock_invitation_by_token(db, token)
    if row is None:
        raise ForbiddenError("Invitation is not valid")

    status = invitation_status(row)
    if status == "revoked":
        raise ForbiddenError("Invitation is not valid")
    if status == "expired":
        raise ForbiddenError("Invitation has expired")
    if status == "redeemed":
        raise ForbiddenError("Invitation has already been used")

    if row.email_normalized != normalize_email(email):
        raise ForbiddenError("Invitation does not match this email")

    return row


def mark_redeemed(db: Session, row: RegistrationInvitation, user_id: uuid.UUID) -> None:
    if row.redeemed_at is not None:
        raise ForbiddenError("Invitation has already been used")
    row.redeemed_at = datetime.now(timezone.utc)
    row.redeemed_by_user_id = user_id
    db.add(row)
