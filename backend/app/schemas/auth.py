from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

UsernameStr = Annotated[str, StringConstraints(min_length=2, max_length=64)]


class UserRegister(BaseModel):
    email: EmailStr
    username: UsernameStr
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    display_name: str | None = Field(default=None, max_length=120)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
