"""SQLAlchemy ORM model for the med_case table."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from data_process.pdf_upload.models import Base


class MedCase(Base):
    __tablename__ = "med_case"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("core_file.file_uuid"), nullable=False
    )
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

    __table_args__ = (
        Index("idx_med_case_file_uuid", "file_uuid"),
        Index("idx_med_case_created_at", created_at.desc()),
    )
