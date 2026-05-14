from __future__ import annotations

from core.config import database_url_has_placeholder_password, redact_database_url


def test_database_url_has_placeholder_password() -> None:
    assert database_url_has_placeholder_password(
        "postgresql+asyncpg://postgres:<url-encoded-password>@172.16.150.45:5432/papers_records"
    )


def test_database_url_redacts_password() -> None:
    redacted = redact_database_url(
        "postgresql+asyncpg://postgres:secret%40123@172.16.150.45:5432/papers_records"
    )

    assert redacted == "postgresql+asyncpg://postgres:<redacted>@172.16.150.45:5432/papers_records"
    assert "secret" not in redacted
