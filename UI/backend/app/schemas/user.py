"""Pydantic schemas for user."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator


Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
]
Email = Annotated[EmailStr, Field(max_length=100)]


def _validate_bcrypt_password(value: str) -> str:
    """Reject values bcrypt cannot safely distinguish instead of truncating them."""
    if len(value.encode("utf-8")) > 72:
        raise ValueError("密码不能超过 72 个字节")
    return value


class UserCreate(BaseModel):
    username: Username
    email: Email
    password: Annotated[str, Field(min_length=6)]

    _password_within_bcrypt_limit = field_validator("password")(
        _validate_bcrypt_password
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class UserLogin(BaseModel):
    username: Username
    password: Annotated[str, Field(min_length=1)]

    _password_within_bcrypt_limit = field_validator("password")(
        _validate_bcrypt_password
    )


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None
    role: str | None = None
