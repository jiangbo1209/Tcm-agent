"""Configuration for the storage layer.

Two pydantic-settings classes:

* :class:`S3Config` — S3-compatible object storage (Tencent COS, AWS S3, MinIO).
  Reads from ``S3_*`` environment variables.
* :class:`UploadConfig` — upload limits and concurrency. Reads from
  ``UPLOAD_*`` environment variables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = PROJECT_ROOT / ".env"


class S3Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="S3_",
        env_file=str(ENV_FILE),
        extra="ignore",
        env_file_encoding="utf-8",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return init_settings, dotenv_settings, env_settings, file_secret_settings

    endpoint: str = "https://cos.ap-beijing.myqcloud.com"
    access_key: str = ""
    secret_key: str = ""
    bucket_name: str = "tcm-documents"
    region: str = "ap-beijing"


class UploadConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UPLOAD_",
        env_file=str(ENV_FILE),
        extra="ignore",
        env_file_encoding="utf-8",
    )

    max_file_size_mb: int = 100
    allowed_extensions: str = ".pdf"
    batch_concurrency: int = 5

    @property
    def extensions_tuple(self) -> Tuple[str, ...]:
        return tuple(self.allowed_extensions.split(","))


def get_s3_config() -> S3Config:
    return S3Config()


def get_upload_config() -> UploadConfig:
    return UploadConfig()
