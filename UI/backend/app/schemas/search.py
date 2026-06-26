"""Pydantic schemas for search."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    search_type: str = "both"  # 'literature' | 'case' | 'both'
    page: int = 1
    size: int = 10


class SearchResultItem(BaseModel):
    source_type: str
    node_id: str | None = None
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
