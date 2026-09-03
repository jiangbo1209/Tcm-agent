"""Annotation ORM models — pool/task/submission/log tables for data annotation.

Six tables backing the human-annotation workflow:
``annotation_pools`` -> ``annotation_pool_items`` -> ``annotation_tasks`` ->
``annotation_task_items`` -> ``annotation_submissions``, with
``annotation_logs`` as an append-only audit trail.

JSON columns use :data:`_JSON` (JSON on SQLite, JSONB on PostgreSQL).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Portable JSON: plain JSON on SQLite, JSONB on PostgreSQL. NEVER bare JSONB.
_JSON = JSON().with_variant(JSONB(), "postgresql")


class AnnotationPool(Base):
    __tablename__ = "annotation_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(20), nullable=False)
    filter_json: Mapped[dict] = mapped_column(_JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AnnotationPoolItem(Base):
    __tablename__ = "annotation_pool_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pool_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("annotation_pools.id", ondelete="CASCADE"), nullable=False
    )
    table_name: Mapped[str] = mapped_column(String(20), nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("pool_id", "table_name", "record_id"),
    )


class AnnotationTask(Base):
    __tablename__ = "annotation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pool_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("annotation_pools.id", ondelete="SET NULL"), nullable=True
    )
    claimed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AnnotationTaskItem(Base):
    __tablename__ = "annotation_task_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("annotation_tasks.id", ondelete="CASCADE"), nullable=False
    )
    table_name: Mapped[str] = mapped_column(String(20), nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_pool_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("task_id", "record_id"),
    )


class AnnotationSubmission(Base):
    __tablename__ = "annotation_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("annotation_task_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    annotator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshot of the annotator's username at submission time.
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    proposed_fields: Mapped[dict] = mapped_column(_JSON, nullable=False)
    base_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    reviewer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AnnotationLog(Base):
    __tablename__ = "annotation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(20), nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshot of the actor's username (audit trail must survive user deletion).
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    old_fields: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    new_fields: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    submission_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("annotation_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
