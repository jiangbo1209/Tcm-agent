"""ORM models for the graph tables (``nodes`` / ``edges``).

The shared models (CoreFile, LitMetadata, MedCase, GuidelineMetadata) are
re-exported from :mod:`app.models` for backward compatibility — code that
imports them from this module continues to work.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .core_file import CoreFile  # noqa: F401  (re-export)
from .guideline import GuidelineMetadata  # noqa: F401  (re-export)
from .lit_metadata import LitMetadata  # noqa: F401  (re-export)
from .med_case import MedCase  # noqa: F401  (re-export)


class GraphBase(DeclarativeBase):
    pass


class Node(GraphBase):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    metric_value: Mapped[int | None] = mapped_column(nullable=True)
    top_k_value: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, server_default=text("1.0000"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Edge(GraphBase):
    __tablename__ = "edges"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(String(32), nullable=False)
    similarity_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    raw_score: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
