"""Working data types for the offline graph builder.

The ORM definitions of the ``nodes`` and ``edges`` tables live in
:mod:`UI.backend.app.models` (see :class:`~UI.backend.app.models.GraphBase`).
This module holds the builder-internal dataclasses that the offline script uses while
computing node tokens and edge scores. They are distinct from the ORM
``Node``/``Edge`` and are intentionally renamed (``GraphNode``/``GraphEdge``)
to avoid shadowing the ORM classes in the same module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GraphNode:
    node_id: str
    node_type: str
    title: str
    metric_value: int | None
    tokens: set[str]
    file_uuid: str | None = None


@dataclass
class GraphEdge:
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
    device: str = "auto"  # "auto" | "cpu" | "cuda"
