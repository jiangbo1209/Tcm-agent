from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from pydantic import ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MODULE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
MODULE_ENV_FILE = MODULE_DIR / ".env"
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ENV_FILE), str(MODULE_ENV_FILE)),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    DATABASE_URL: str = ""
    POSTGRES_HOST: str = "172.16.150.45"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "papers_records"
    OUTPUT_DIR: str = "./outputs"
    CORE_FILE_PENDING_LIMIT: int = 0

    CRAWLER_TIMEOUT: int = 30
    CRAWLER_MAX_RETRIES: int = 2
    CRAWLER_CONCURRENCY: int = 1
    REQUEST_DELAY_MIN: float = 2.0
    REQUEST_DELAY_MAX: float = 5.0

    ENABLE_NSTL: bool = True
    LOG_LEVEL: str = "INFO"

    YIDU_BASE_URL: str = "https://yidu.calis.edu.cn"
    NSTL_BASE_URL: str = "https://www.nstl.gov.cn"
    USER_AGENT: str = "Mozilla/5.0"
    SKIP_EXISTING_RECORDS: bool = True

    ENABLE_CNKI: bool = False
    CNKI_BASE_URL: str = "https://kns.cnki.net"
    CNKI_COOKIE_TTL_SEC: int = 300
    CNKI_HEADLESS_BOOTSTRAP: bool = False
    CNKI_BROWSER_CHANNEL: str = ""
    CNKI_HUMAN_PAUSE_MIN: float = 0.8
    CNKI_HUMAN_PAUSE_MAX: float = 2.4

    @model_validator(mode="after")
    def build_database_url_from_postgres_settings(self) -> "Settings":
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError("DATABASE_URL must point to PostgreSQL, not SQLite")
            return self
        if not self.POSTGRES_HOST or not self.POSTGRES_USER or not self.POSTGRES_DB:
            raise ValueError("DATABASE_URL is empty and POSTGRES_HOST/POSTGRES_USER/POSTGRES_DB are required")

        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        self.DATABASE_URL = (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
        return self

    @field_validator("CRAWLER_TIMEOUT", "CRAWLER_MAX_RETRIES", "CRAWLER_CONCURRENCY", "CORE_FILE_PENDING_LIMIT")
    @classmethod
    def validate_non_negative_int(cls, value: int, info: ValidationInfo) -> int:
        if value < 0:
            raise ValueError(f"{info.field_name} must be non-negative")
        if info.field_name in {"CRAWLER_TIMEOUT", "CRAWLER_CONCURRENCY"} and value == 0:
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


settings = Settings()
