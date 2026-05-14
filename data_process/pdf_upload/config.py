"""Database and environment configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the project root directory (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class PostgresConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "172.16.150.45"
    port: int = 5432
    user: str = "postgres"
    password: str = ""
    database: str = "papers_records"

    @property
    def dsn(self) -> str:
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class MinioConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MINIO_",
        env_file=str(ENV_FILE),
        extra="ignore",
        env_file_encoding="utf-8",
    )

    endpoint: str = "172.16.150.45:9000"
    root_user: str = "admin"
    root_password: str = ""
    bucket_name: str = "tcm-documents"

    @property
    def access_key(self) -> str:
        return self.root_user

    @property
    def secret_key(self) -> str:
        return self.root_password


class UploadConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UPLOAD_",
        env_file=str(ENV_FILE),
        extra="ignore",
        env_file_encoding="utf-8",
    )

    max_file_size_mb: int = 100
    allowed_extensions: str = ".pdf"

    @property
    def extensions_tuple(self) -> Tuple[str, ...]:
        return tuple(self.allowed_extensions.split(","))


def get_postgres_config() -> PostgresConfig:
    return PostgresConfig()


def get_minio_config() -> MinioConfig:
    return MinioConfig()


def get_upload_config() -> UploadConfig:
    return UploadConfig()
