from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FailedRecord(Base):
    __tablename__ = "failed_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_title: Mapped[str] = mapped_column(Text, nullable=False)
    attempted_sites: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    failure_reason: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CoreFile(Base):
    __tablename__ = "core_file"

    file_uuid: Mapped[str] = mapped_column(String, primary_key=True)
    original_name: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    upload_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    status_metadata: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_case: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LitMetadata(Base):
    __tablename__ = "lit_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_uuid: Mapped[str] = mapped_column(
        String,
        ForeignKey("core_file.file_uuid"),
        nullable=False,
        unique=True,
        index=True,
    )
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_title: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    paper_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_site: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal: Mapped[str | None] = mapped_column(String(256), nullable=True)
    pub_year: Mapped[str | None] = mapped_column(String(16), nullable=True)
    matched_title: Mapped[str] = mapped_column(Text, nullable=False)
    is_exact_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    crawl_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_lit_metadata_title", "title"),
    )
