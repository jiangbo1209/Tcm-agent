"""ORM models for PostgreSQL graph tables (nodes, edges, lit_metadata, case_metadata, core_file)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GraphBase(DeclarativeBase):
    pass


class CoreFile(GraphBase):
    __tablename__ = "core_file"

    file_uuid: Mapped[str] = mapped_column(String, primary_key=True)
    original_name: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    upload_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    status_metadata: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_case: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_guidelinemeta: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status_ragflow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    document_type: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LitMetadata(GraphBase):
    __tablename__ = "lit_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_uuid: Mapped[str] = mapped_column(String, ForeignKey("core_file.file_uuid"), nullable=False)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_title: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list] = mapped_column(Text, nullable=False, default=list)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list] = mapped_column(Text, nullable=False, default=list)
    paper_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_site: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal: Mapped[str | None] = mapped_column(String(256), nullable=True)
    pub_year: Mapped[str | None] = mapped_column(String(16), nullable=True)
    matched_title: Mapped[str] = mapped_column(Text, nullable=False)
    is_exact_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    crawl_status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class MedCase(GraphBase):
    __tablename__ = "case_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_uuid: Mapped[str] = mapped_column(String, ForeignKey("core_file.file_uuid"), nullable=False)
    age: Mapped[str | None] = mapped_column(Text)
    bmi: Mapped[str | None] = mapped_column(Text)
    menstruation: Mapped[str | None] = mapped_column(Text)
    infertility: Mapped[str | None] = mapped_column(Text)
    lifestyle: Mapped[str | None] = mapped_column(Text)
    present_symptoms: Mapped[str | None] = mapped_column(Text)
    medical_history: Mapped[str | None] = mapped_column(Text)
    lab_tests: Mapped[str | None] = mapped_column(Text)
    ultrasound: Mapped[str | None] = mapped_column(Text)
    followup: Mapped[str | None] = mapped_column(Text)
    western_diagnosis: Mapped[str | None] = mapped_column(Text)
    tcm_diagnosis: Mapped[str | None] = mapped_column(Text)
    treatment_principle: Mapped[str | None] = mapped_column(Text)
    prescription: Mapped[str | None] = mapped_column(Text)
    acupoints: Mapped[str | None] = mapped_column(Text)
    assisted_reproduction: Mapped[str | None] = mapped_column(Text)
    western_medicine: Mapped[str | None] = mapped_column(Text)
    efficacy: Mapped[str | None] = mapped_column(Text)
    adverse_reactions: Mapped[str | None] = mapped_column(Text)
    commentary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Node(GraphBase):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    metric_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
