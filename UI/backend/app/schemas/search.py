"""Pydantic schemas for search."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    source_types: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    years: list[str] = Field(default_factory=list)
    journals: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    search_type: str = "both"  # 'literature' | 'case' | 'both'
    page: int = 1
    size: int = 10
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchResultItem(BaseModel):
    source_type: str
    node_id: str | None = None
    file_uuid: str | None = None
    title: str | None = None
    authors: str | None = None
    publish_year: int | None = None
    keywords: str | None = None
    abstract: str | None = None
    tcm_diagnosis: str | None = None
    western_diagnosis: str | None = None
    score: float | None = None


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    total: int
    total_pages: int
    page: int
    size: int
    facets: dict[str, list[dict[str, int | str]]] = Field(default_factory=dict)


class SearchHistoryItem(BaseModel):
    id: int
    query: str
    search_type: str
    result_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchHistoryResponse(BaseModel):
    items: list[SearchHistoryItem]
    total: int
