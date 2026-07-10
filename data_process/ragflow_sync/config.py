"""Runtime settings for syncing project data to RAGFlow."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RagflowSyncSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = Field(default="127.0.0.1", validation_alias=AliasChoices("DB_HOST", "POSTGRES_HOST"))
    db_port: int = Field(default=5432, validation_alias=AliasChoices("DB_PORT", "POSTGRES_PORT"))
    db_user: str = Field(default="postgres", validation_alias=AliasChoices("DB_USER", "POSTGRES_USER"))
    db_password: str = Field(default="", validation_alias=AliasChoices("DB_PASSWORD", "POSTGRES_PASSWORD"))
    db_name: str = Field(default="papers_records", validation_alias=AliasChoices("DB_NAME", "POSTGRES_DB"))

    s3_endpoint: str = Field(default="https://cos.ap-beijing.myqcloud.com", validation_alias=AliasChoices("S3_ENDPOINT"))
    s3_access_key: str = Field(default="", validation_alias=AliasChoices("S3_ACCESS_KEY"))
    s3_secret_key: str = Field(default="", validation_alias=AliasChoices("S3_SECRET_KEY"))
    s3_bucket_name: str = Field(default="tcm-documents", validation_alias=AliasChoices("S3_BUCKET"))
    s3_region: str = Field(default="ap-beijing", validation_alias=AliasChoices("S3_REGION"))

    ragflow_base_url: str = Field(default="http://127.0.0.1:9380", validation_alias=AliasChoices("RAGFLOW_BASE_URL"))
    ragflow_api_key: str = Field(default="", validation_alias=AliasChoices("RAGFLOW_API_KEY"))
    ragflow_literature_dataset_id: str = Field(default="", validation_alias=AliasChoices("RAGFLOW_LITERATURE_DATASET_ID"))
    ragflow_case_dataset_id: str = Field(default="", validation_alias=AliasChoices("RAGFLOW_CASE_DATASET_ID"))
    ragflow_guideline_dataset_id: str = Field(default="", validation_alias=AliasChoices("RAGFLOW_GUIDELINE_DATASET_ID"))
    ragflow_parse_after_upload: bool = Field(default=True, validation_alias=AliasChoices("RAGFLOW_PARSE_AFTER_UPLOAD"))
    ragflow_request_timeout: int = Field(default=120, validation_alias=AliasChoices("RAGFLOW_REQUEST_TIMEOUT"))
    ragflow_domain: str = Field(default="DOR infertility", validation_alias=AliasChoices("RAGFLOW_DOMAIN"))

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg2",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def normalized_ragflow_base_url(self) -> str:
        return self.ragflow_base_url.rstrip("/")

