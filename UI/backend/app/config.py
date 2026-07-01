"""Application settings using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.search_history import SearchBackendMode


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    host: str = Field(default="127.0.0.1", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    user: str = Field(default="postgres", alias="POSTGRES_USER")
    password: str = Field(default="", alias="POSTGRES_PASSWORD")
    database: str = Field(default="postgres", alias="POSTGRES_DB")


class MinioSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MINIO_", extra="ignore")

    endpoint: str = "localhost:9000"
    root_user: str = ""
    root_password: str = ""
    bucket_name: str = "tcm-documents"


class SearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEARCH_", extra="ignore")

    backend_mode: SearchBackendMode = SearchBackendMode.AUTO
    suggest_default_size: int = 8


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JWT_", extra="ignore")

    secret_key: str = "tcm-agent-secret-key-change-in-production"
    expire_minutes: int = 1440


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres: PostgresSettings = PostgresSettings()
    minio: MinioSettings = MinioSettings()
    search: SearchSettings = SearchSettings()
    auth: AuthSettings = AuthSettings()

    cors_allow_origins: str = "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8080,http://localhost:8080"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_database_config() -> PostgresSettings:
    return get_settings().postgres


def get_minio_config() -> MinioSettings:
    return get_settings().minio


def get_search_config() -> SearchSettings:
    return get_settings().search


def get_auth_config() -> AuthSettings:
    return get_settings().auth
