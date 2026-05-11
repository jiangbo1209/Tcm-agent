"""Database and environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.search.settings import SearchBackendMode, SearchConfig


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class MinioConfig:
    endpoint: str
    access_key: str
    secret_key: str
    bucket_name: str


def parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_database_config() -> DatabaseConfig:
    db_host = os.getenv("DB_HOST") or os.getenv("MYSQL_HOST", "127.0.0.1")
    db_port_raw = os.getenv("DB_PORT") or os.getenv("MYSQL_PORT")
    db_port_default = int(db_port_raw) if db_port_raw and db_port_raw.isdigit() else 3306
    db_port = parse_int_env("DB_PORT", db_port_default)

    db_user = os.getenv("DB_USER") or os.getenv("MYSQL_USER", "root")
    db_password = os.getenv("DB_PASSWORD")
    if db_password is None:
        db_password = os.getenv("MYSQL_PASSWORD", "123456")

    db_name = os.getenv("DB_NAME") or os.getenv("MYSQL_DATABASE", "papers_records")
    return DatabaseConfig(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
    )


def get_search_config() -> SearchConfig:
    raw_mode = (os.getenv("SEARCH_BACKEND_MODE") or "auto").strip().lower()
    try:
        backend_mode = SearchBackendMode(raw_mode)
    except ValueError:
        backend_mode = SearchBackendMode.AUTO

    suggest_default_size = parse_int_env("SEARCH_SUGGEST_DEFAULT_SIZE", 8)
    suggest_default_size = max(1, min(20, suggest_default_size))

    return SearchConfig(
        backend_mode=backend_mode,
        suggest_default_size=suggest_default_size,
    )


def get_minio_config() -> MinioConfig:
    endpoint = (os.getenv("MINIO_ENDPOINT") or "localhost:9000").strip()
    access_key = (os.getenv("MINIO_ACCESS_KEY") or "").strip()
    secret_key = (os.getenv("MINIO_SECRET_KEY") or "").strip()
    bucket_name = (os.getenv("MINIO_BUCKET_NAME") or "tcm-documents").strip() or "tcm-documents"

    return MinioConfig(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket_name=bucket_name,
    )
