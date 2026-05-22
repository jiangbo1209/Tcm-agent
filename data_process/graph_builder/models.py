"""Dataclasses for graph nodes, edges, build options, and ORM table definitions."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    text,
)

_METADATA = MetaData()

_NODES_TABLE = Table(
    "nodes",
    _METADATA,
    Column("id", String(128), primary_key=True),
    Column("node_type", String(32), nullable=False),
    Column("title", String(512), nullable=False),
    Column("metric_value", Integer, nullable=True),
    Column("top_k_value", Numeric(10, 4), nullable=False, server_default=text("1.0000")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
)

Index("idx_nodes_type", _NODES_TABLE.c.node_type)
Index("idx_nodes_metric", _NODES_TABLE.c.metric_value)

_EDGES_TABLE = Table(
    "edges",
    _METADATA,
    Column("id", String(40), primary_key=True),
    Column(
        "source_id",
        String(128),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "target_id",
        String(128),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("edge_type", String(32), nullable=False),
    Column("similarity_score", Numeric(6, 4), nullable=False),
    Column("raw_score", Numeric(12, 8), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint(
        "similarity_score >= 0.0000 AND similarity_score <= 1.0000",
        name="chk_edges_score_range",
    ),
    CheckConstraint(
        "edge_type IN ('paper-paper', 'record-record', 'ref')",
        name="chk_edges_type",
    ),
)

Index("uk_edges_type_pair", _EDGES_TABLE.c.edge_type, _EDGES_TABLE.c.source_id, _EDGES_TABLE.c.target_id, unique=True)
Index("idx_edges_source_score", _EDGES_TABLE.c.source_id, _EDGES_TABLE.c.similarity_score)
Index("idx_edges_target_score", _EDGES_TABLE.c.target_id, _EDGES_TABLE.c.similarity_score)
Index("idx_edges_seed_expand", _EDGES_TABLE.c.source_id, _EDGES_TABLE.c.target_id)


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
    strategy: str
    paper_top_k: int
    record_top_k: int
    paper_min_score: float
    record_min_score: float
