"""Node ORM model — a single node in the knowledge graph."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .graph_base import GraphBase


class Node(GraphBase):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    metric_value: Mapped[int | None] = mapped_column(nullable=True)
    top_k_value: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, server_default=text("1.0000")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
