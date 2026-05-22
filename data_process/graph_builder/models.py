"""Dataclasses for graph nodes, edges, and build options."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Node:
    node_id: str
    node_type: str
    title: str
    metric_value: int | None
    tokens: set[str]
    file_uuid: str | None = None


@dataclass
class Edge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str
    similarity_score: float
    raw_score: float


@dataclass(frozen=True)
class BuildGraphOptions:
    host: str
    port: int
    user: str
    password: str
    database: str
    schema_sql: str
    strategy: str
    paper_top_k: int
    record_top_k: int
    paper_min_score: float
    record_min_score: float
