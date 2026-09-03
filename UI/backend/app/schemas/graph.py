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


class NodeSearchItem(BaseModel):
    node_id: str | None
    title: str | None
    source_type: str | None


class NodeSearchResponse(BaseModel):
    items: list[NodeSearchItem]
    total: int
    page: int


class RecordField(BaseModel):
    name: str
    value: Any


class RecordSummary(BaseModel):
    diagnosis: str | None = None
    syndrome: str | None = None
    treatment_principle: str | None = None
    prescription: str | None = None


class NodeDetailResponse(BaseModel):
    node: GraphNode
    detail_type: str
    paper: dict[str, Any] | None = None
    record_fields: list[RecordField] | None = None
    record: RecordSummary | None = None


