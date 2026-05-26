"""Build graph service-layer tables (nodes, edges) from lit_metadata and med_case."""

from __future__ import annotations

from .database import (
    Error,
    build_nodes,
    chunked,
    connect_postgres,
    create_graph_schema,
    write_edges,
    write_nodes,
)
from .engine import run
from .models import BuildGraphOptions, Edge, Node
from .processor import (
    CJK_RE,
    WORD_RE,
    build_pair_edges,
    build_ref_edges,
    compute_node_top_k,
    ensure_minimum_edge_types,
    extract_age,
    extract_year,
    jaccard_similarity,
    join_text,
    normalize_list_value,
    normalize_pair,
    normalize_title,
    stable_edge_id,
    stable_node_id,
    tokenize_text,
)

__all__ = [
    "CJK_RE",
    "WORD_RE",
    "Node",
    "Edge",
    "BuildGraphOptions",
    "Error",
    "connect_postgres",
    "create_graph_schema",
    "normalize_title",
    "extract_age",
    "extract_year",
    "tokenize_text",
    "normalize_list_value",
    "join_text",
    "jaccard_similarity",
    "stable_node_id",
    "normalize_pair",
    "stable_edge_id",
    "build_nodes",
    "build_pair_edges",
    "build_ref_edges",
    "ensure_minimum_edge_types",
    "compute_node_top_k",
    "chunked",
    "write_nodes",
    "write_edges",
    "run",
]
