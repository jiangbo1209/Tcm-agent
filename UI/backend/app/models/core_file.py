"""CoreFile ORM model — central record of every uploaded PDF.

A row is created by the upload service (UI/backend/app/storage/service.py).
The ``uploader_id`` column references ``users.id`` from the UI/backend SQLite
database; the reference is logical (no real FK) because users live in a
different database engine (SQLite vs. PostgreSQL).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


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
    status_guidelinemeta: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status_ragflow: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    document_type: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    uploader_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    __table_args__ = (
        Index("idx_core_file_document_type", "document_type"),
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
        Index(
            "idx_core_file_status_guidelinemeta",
            "status_guidelinemeta",
            postgresql_where=text("status_guidelinemeta = FALSE"),
        ),
        Index(
            "idx_core_file_status_ragflow",
            "status_ragflow",
            postgresql_where=text("status_ragflow = FALSE"),
        ),
        Index("idx_core_file_upload_time", upload_time.desc()),
        Index("idx_core_file_uploader", "uploader_id"),
    )
