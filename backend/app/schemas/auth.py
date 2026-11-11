from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

# Keep in sync with web-ui validateRegister USERNAME_RE.
UsernameStr = Annotated[
    str,
    StringConstraints(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_]+$"),
]


class UserRegister(BaseModel):
    email: EmailStr
    username: UsernameStr
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    display_name: str | None = Field(default=None, max_length=120)
    # Required only in invite_only mode (enforced in auth_service, not here).
    # Public mode ignores this field. Never log or echo this value.
    invitation_code: str | None = Field(default=None, max_length=128)

    @field_validator("invitation_code", mode="before")
    @classmethod
    def empty_invite_to_none(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterResponse(BaseModel):
    """Invite registration returns tokens; public registration returns verification_pending."""

    status: Literal["authenticated", "verification_pending"]
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    email: str | None = None
    message: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: Annotated[str, StringConstraints(min_length=16, max_length=200)]


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class RegistrationStatusResponse(BaseModel):
    mode: Literal["closed", "invite_only", "public"]
    configured_mode: Literal["closed", "invite_only", "public"]
    registration_available: bool
    requires_invitation: bool
    requires_email_verification: bool
    email_delivery_configured: bool
    prerequisite: str | None = None
    note: str | None = None
