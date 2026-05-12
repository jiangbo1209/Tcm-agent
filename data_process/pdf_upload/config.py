"""Database and environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def dsn(self) -> str:
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass(frozen=True)
class MinioConfig:
    endpoint: str
    access_key: str
    secret_key: str
    bucket_name: str


@dataclass(frozen=True)
class UploadConfig:
    max_file_size_mb: int
    allowed_extensions: tuple[str, ...]


def get_postgres_config() -> PostgresConfig:
    return PostgresConfig(
        host=os.getenv("POSTGRES_HOST", "172.16.150.45"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        database=os.getenv("POSTGRES_DB", "papers_records"),
    )


def get_minio_config() -> MinioConfig:
    return MinioConfig(
        endpoint=os.getenv("MINIO_ENDPOINT", "172.16.150.45:9000"),
        access_key=os.getenv("MINIO_ROOT_USER", "admin"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", ""),
        bucket_name=os.getenv("MINIO_BUCKET_NAME", "tcm-documents"),
    )


def get_upload_config() -> UploadConfig:
    return UploadConfig(
        max_file_size_mb=int(os.getenv("UPLOAD_MAX_SIZE_MB", "100")),
        allowed_extensions=tuple(
            os.getenv("UPLOAD_ALLOWED_EXTENSIONS", ".pdf").split(",")
        ),
    )
