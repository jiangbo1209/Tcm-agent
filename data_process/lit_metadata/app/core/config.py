from __future__ import annotations

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./paper_info.db"
    INPUT_SOURCE: str = "core_file"
    DATASET_DIR: str = "./dataset"
    OUTPUT_DIR: str = "./outputs"
    CORE_FILE_PENDING_LIMIT: int = 0

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

    ENABLE_CNKI: bool = True
    CNKI_BASE_URL: str = "https://kns.cnki.net"
    CNKI_COOKIE_TTL_SEC: int = 300
    CNKI_HEADLESS_BOOTSTRAP: bool = False
    CNKI_BROWSER_CHANNEL: str = ""
    CNKI_HUMAN_PAUSE_MIN: float = 0.8
    CNKI_HUMAN_PAUSE_MAX: float = 2.4

    @field_validator("INPUT_SOURCE")
    @classmethod
    def validate_input_source(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"dataset", "core_file"}:
            raise ValueError("INPUT_SOURCE must be either 'dataset' or 'core_file'")
        return normalized

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
