"""Retrieval schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    citation_index: int | None = None
    source_type: str
    title: str
    file_uuid: str | None = None
    document_id: str | None = None
    dataset_id: str | None = None
    chunk_id: str | None = None
    chunk: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceSource(BaseModel):
    index: int
    source_type: str
    title: str
    file_uuid: str | None = None
    document_id: str | None = None
    dataset_id: str | None = None
    chunk_id: str | None = None
    snippet: str | None = None
    authors: str | None = None
    journal: str | None = None
    year: str | None = None
    source_site: str | None = None
    source_url: str | None = None


class RetrievalResult(BaseModel):
    evidence: list[Evidence]
    total: int
    evidence_status: str = "not_checked"
    warnings: list[str] = Field(default_factory=list)
