"""Application settings using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.search_history import SearchBackendMode
from app.storage.config import S3Config, UploadConfig


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_", extra="ignore",
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
    )

    host: str = Field(default="127.0.0.1", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    user: str = Field(default="postgres", alias="POSTGRES_USER")
    password: str = Field(default="", alias="POSTGRES_PASSWORD")
    database: str = Field(default="postgres", alias="POSTGRES_DB")

    @property
    def dsn(self) -> str:
        """Sync (psycopg2) DSN — used by existing sync routers."""
        return (
            f"postgresql+psycopg2://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def async_dsn(self) -> str:
        """Async (asyncpg) DSN — used by the new files router."""
        return (
            f"postgresql+asyncpg://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class SearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEARCH_", extra="ignore")

    backend_mode: SearchBackendMode = SearchBackendMode.AUTO
    suggest_default_size: int = 8


DEFAULT_JWT_SECRET_KEY = "tcm-agent-secret-key-change-in-production"


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JWT_", extra="ignore")

    secret_key: str = DEFAULT_JWT_SECRET_KEY
    expire_minutes: int = 1440
    app_env: str = Field(default="development", alias="APP_ENV")
    file_token_secret: str = Field(default="", alias="FILE_TOKEN_SECRET")


class AnnotationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANNOTATION_", extra="ignore", case_sensitive=True,
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
    )

    ENABLED: bool = False
    TASK_DEADLINE_DAYS: int = 7
    REWORK_DAYS: int = 5
    MAX_PENDING_REWORK: int = 0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres: PostgresSettings = PostgresSettings()
    s3: S3Config = S3Config()
    upload: UploadConfig = UploadConfig()
    search: SearchSettings = SearchSettings()
    auth: AuthSettings = AuthSettings()

    cors_allow_origins: str = "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8080,http://localhost:8080"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_annotation_config() -> AnnotationSettings:
    return AnnotationSettings()


def get_database_config() -> PostgresSettings:
    return get_settings().postgres


def get_s3_config() -> S3Config:
    return get_settings().s3


def get_upload_config() -> UploadConfig:
    return get_settings().upload


def get_search_config() -> SearchSettings:
    return get_settings().search


def get_auth_config() -> AuthSettings:
    return get_settings().auth
