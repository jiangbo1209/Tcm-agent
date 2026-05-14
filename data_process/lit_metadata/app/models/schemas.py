from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatasetFile(BaseModel):
    file_name: str
    file_path: str
    suffix: str
    file_uuid: str


class SearchResult(BaseModel):
    title: str
    detail_url: str | None
    source_site: str
    raw_data: dict[str, Any] | None = None


class PaperMetadata(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    paper_type: str | None = None
    source_site: str
    source_url: str | None
    journal: str | None = None
    pub_year: str | None = None
    raw_data: dict[str, Any] | None = None


class FailedRecordCreate(BaseModel):
    file_name: str
    file_path: str
    cleaned_title: str
    attempted_sites: list[str] = Field(default_factory=list)
    failure_reason: str
    error_message: str | None = None
    suggested_action: str


class LitMetadataCreate(BaseModel):
    file_uuid: str
    original_name: str
    storage_path: str
    cleaned_title: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    paper_type: str | None = None
    source_site: str
    source_url: str | None = None
    journal: str | None = None
    pub_year: str | None = None
    matched_title: str
    is_exact_match: bool
    crawl_status: str
    error_message: str | None = None


class ProcessingSummary(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    total_files: int = 0
    success_count: int = 0
    partial_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    failed_export_path: str | None = None
