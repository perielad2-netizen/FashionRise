from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

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
    # Required for invite-only beta. Never log or echo this value.
    invitation_code: Annotated[str, StringConstraints(min_length=16, max_length=128)]


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
