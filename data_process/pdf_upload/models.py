"""SQLAlchemy ORM models for the pdf_upload module."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CoreFile(Base):
    __tablename__ = "core_file"

    file_uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pdf"
    )
    upload_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    status_metadata: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status_case: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    __table_args__ = (
        Index(
            "idx_core_file_status_meta",
            "status_metadata",
            postgresql_where=text("status_metadata = FALSE"),
        ),
        Index(
            "idx_core_file_status_case",
            "status_case",
            postgresql_where=text("status_case = FALSE"),
        ),
        Index("idx_core_file_upload_time", upload_time.desc()),
    )
