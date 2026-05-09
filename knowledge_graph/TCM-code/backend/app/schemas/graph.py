"""Pydantic request/response schemas for graph APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    node_type: str
    title: str
    metric_value: int | None
    publish_year: int | None = None
    age: int | None = None
    top_k_value: float | None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str
    similarity_score: float | None
    raw_score: float | None


class GraphExpandResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class SearchItem(BaseModel):
    source_type: str
    node_id: str | None
    title: str | None
    authors: str | None = None
    publish_year: int | None = None
    keywords: str | None = None
    abstract: str | None = None
    tcm_diagnosis: str | None = None
    western_diagnosis: str | None = None
    score: float | None = None


class SearchResponse(BaseModel):
    items: list[SearchItem]
    total: int
    total_pages: int
    page: int
    size: int


class SearchIndexTableStatus(BaseModel):
    name: str
    required_columns: list[str]
    indexed_columns: list[str]
    missing_columns: list[str]


class SearchIndexStatusResponse(BaseModel):
    configured_backend: str
    effective_backend: str
    fulltext_ready: bool
    tables: list[SearchIndexTableStatus]
    suggested_scripts: list[str]
    recommendations: list[str]


class RecordField(BaseModel):
    name: str
    value: Any


class NodeDetailResponse(BaseModel):
    node: GraphNode
    detail_type: str
    paper: dict[str, Any] | None = None
    record_fields: list[RecordField] | None = None


class FileUrlResponse(BaseModel):
    node_id: str
    node_type: str
    bucket: str
    object_name: str
    file_name: str
    download: bool
    url: str


