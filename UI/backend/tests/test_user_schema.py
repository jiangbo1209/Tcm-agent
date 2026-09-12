"""User request schema validation tests; no database access."""

import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserLogin


def test_user_create_normalizes_username_and_email():
    user = UserCreate(
        username="  alice  ",
        email="  Alice@EXAMPLE.com  ",
        password="secret1",
    )

    assert user.username == "alice"
    assert user.email == "alice@example.com"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("username", "x" * 51),
        ("email", f"{'x' * 89}@example.com"),
        ("password", "short"),
        ("password", "密" * 25),
    ],
)
def test_user_create_rejects_invalid_lengths(field, value):
    payload = {
        "username": "alice",
        "email": "alice@example.com",
        "password": "secret1",
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        UserCreate(**payload)


def test_user_login_rejects_password_beyond_bcrypt_limit():
    with pytest.raises(ValidationError):
        UserLogin(username="alice", password="a" * 73)
