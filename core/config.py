from __future__ import annotations

from urllib.parse import unquote, urlsplit, urlunsplit

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PLACEHOLDER_PASSWORD_MARKERS = (
    "<url-encoded-password>",
    "<password>",
    "your-password",
    "your_password",
)


def database_url_has_placeholder_password(value: str) -> bool:
    """Return True when DATABASE_URL still contains an example password."""

    try:
        parsed = urlsplit(value)
    except ValueError:
        return False

    password = parsed.password
    if password is None:
        return False

    normalized = unquote(password).strip().lower()
    return any(marker in normalized for marker in PLACEHOLDER_PASSWORD_MARKERS)


def redact_database_url(value: str) -> str:
    """Redact the password part of a database URL for logs and errors."""

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"

        try:
            port = parsed.port
        except ValueError:
            port = None

        host = f"{hostname}:{port}" if port is not None else hostname
        if parsed.username:
            userinfo = parsed.username
            if parsed.password is not None:
                userinfo = f"{userinfo}:<redacted>"
            netloc = f"{userinfo}@{host}"
        else:
            netloc = host

        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    except ValueError:
        return "<invalid DATABASE_URL>"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/papers_records"
    OUTPUT_DIR: str = "./outputs"
    CORE_FILE_PENDING_LIMIT: int = 0
    CORE_FILE_BATCH_SIZE: int = 50

    CRAWLER_TIMEOUT: int = 30
    CRAWLER_MAX_RETRIES: int = 2
    CRAWLER_CONCURRENCY: int = 1
    REQUEST_DELAY_MIN: float = 2.0
    REQUEST_DELAY_MAX: float = 5.0

    ENABLE_NSTL: bool = True
    LOG_LEVEL: str = "INFO"
    EXPORT_FAILED_CSV: bool = True

    YIDU_BASE_URL: str = "https://yidu.calis.edu.cn"
    NSTL_BASE_URL: str = "https://www.nstl.gov.cn"
    USER_AGENT: str = "Mozilla/5.0"
    SKIP_EXISTING_RECORDS: bool = True
    SKIP_FAILED_RECORDS: bool = True
    REPAIR_METADATA_STATE: bool = False

    ENABLE_CNKI: bool = True
    CNKI_BASE_URL: str = "https://kns.cnki.net"
    CNKI_COOKIE_TTL_SEC: int = 300
    CNKI_HEADLESS_BOOTSTRAP: bool = False
    CNKI_BROWSER_CHANNEL: str = ""
    CNKI_HUMAN_PAUSE_MIN: float = 0.8
    CNKI_HUMAN_PAUSE_MAX: float = 2.4

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("DATABASE_URL must be set")
        if not normalized.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg://")
        return normalized

    @field_validator(
        "CRAWLER_TIMEOUT",
        "CRAWLER_MAX_RETRIES",
        "CRAWLER_CONCURRENCY",
        "CORE_FILE_PENDING_LIMIT",
        "CORE_FILE_BATCH_SIZE",
    )
    @classmethod
    def validate_non_negative_int(cls, value: int, info: ValidationInfo) -> int:
        if value < 0:
            raise ValueError(f"{info.field_name} must be non-negative")
        if info.field_name in {"CRAWLER_TIMEOUT", "CRAWLER_CONCURRENCY", "CORE_FILE_BATCH_SIZE"} and value == 0:
            raise ValueError(f"{info.field_name} must be greater than 0")
        return value

    @field_validator("REQUEST_DELAY_MIN", "REQUEST_DELAY_MAX")
    @classmethod
    def validate_non_negative_delay(cls, value: float, info: ValidationInfo) -> float:
        if value < 0:
            raise ValueError(f"{info.field_name} must be non-negative")
        return value

    @field_validator("REQUEST_DELAY_MAX")
    @classmethod
    def validate_delay_range(cls, value: float, info: ValidationInfo) -> float:
        min_value = info.data.get("REQUEST_DELAY_MIN", 0.0)
        if value < min_value:
            raise ValueError("REQUEST_DELAY_MAX must be greater than or equal to REQUEST_DELAY_MIN")
        return value

    @property
    def redacted_database_url(self) -> str:
        return redact_database_url(self.DATABASE_URL)

    @property
    def database_url_uses_placeholder_password(self) -> bool:
        return database_url_has_placeholder_password(self.DATABASE_URL)


settings = Settings()
