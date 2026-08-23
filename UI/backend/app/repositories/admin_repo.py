"""Admin data-access for lit/case/guideline metadata (query, serialize, optimistic-lock update)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Integer, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import GuidelineMetadata, LitMetadata, MedCase


class RecordNotFoundError(Exception): ...


class StaleRecordError(Exception): ...

_PAGE_SIZE = 20

_TABLE_MAP: dict[str, type] = {
    "lit": LitMetadata,
    "case": MedCase,
    "guideline": GuidelineMetadata,
}

_EDITABLE_FIELDS: dict[str, list[str]] = {
    "lit": [
        "title", "authors", "abstract", "keywords",
        "paper_type", "source_site", "source_url", "journal", "pub_year",
        "matched_title", "ai_summary",
    ],
    "case": [
        "age", "bmi", "menstruation", "infertility", "lifestyle",
        "present_symptoms", "medical_history", "lab_tests", "ultrasound",
        "followup", "western_diagnosis", "tcm_diagnosis", "treatment_principle",
        "prescription", "acupoints", "assisted_reproduction", "western_medicine",
        "efficacy", "adverse_reactions", "commentary",
    ],
    "guideline": [
        "title", "authors", "abstract", "keywords",
        "paper_type", "source_site", "source_url", "journal", "pub_year",
        "matched_title",
    ],
}

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "lit": ["title", "authors", "abstract", "keywords", "paper_type", "journal", "pub_year"],
    "guideline": ["title", "authors", "abstract", "keywords", "paper_type", "journal", "pub_year"],
}


class AdminQueryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _get_model(self, table: str) -> type:
        model = _TABLE_MAP.get(table)
        if model is None:
            raise ValueError(f"Unknown table: {table}")
        return model

    @staticmethod
    def _serialize(record: Any, table: str) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for col in record.__table__.columns:
            key = str(col.name)
            value = getattr(record, key, None)
            if isinstance(value, datetime):
                value = value.isoformat()
            data[key] = value
        return data

    @staticmethod
    def _build_search_filter(model: type, q: str):
        if model is LitMetadata or model is GuidelineMetadata:
            return or_(
                model.title.ilike(f"%{q}%"),
                model.original_name.ilike(f"%{q}%"),
                model.abstract.ilike(f"%{q}%"),
                model.journal.ilike(f"%{q}%"),
            )
        if model is MedCase:
            return or_(
                model.western_diagnosis.ilike(f"%{q}%"),
                model.tcm_diagnosis.ilike(f"%{q}%"),
                model.prescription.ilike(f"%{q}%"),
            )
        return None

    @staticmethod
    def _apply_filters(model: type, stmt, crawl_status: str | None, year_min: int | None, year_max: int | None):
        if crawl_status:
            stmt = stmt.where(model.crawl_status == crawl_status)
        if year_min is not None:
            stmt = stmt.where(func.cast(func.substring(model.pub_year, 1, 4), Integer) >= year_min)
        if year_max is not None:
            stmt = stmt.where(func.cast(func.substring(model.pub_year, 1, 4), Integer) <= year_max)
        return stmt

    def _get_year_range(self, model) -> dict[str, int | None]:
        try:
            min_row = self._db.execute(select(func.min(func.nullif(func.cast(func.substring(model.pub_year, 1, 4), Integer), 0)))).scalar()
            max_row = self._db.execute(select(func.max(func.nullif(func.cast(func.substring(model.pub_year, 1, 4), Integer), 0)))).scalar()
            return {
                "min_year": int(min_row) if min_row else None,
                "max_year": int(max_row) if max_row else None,
            }
        except Exception:
            return {"min_year": None, "max_year": None}

    @staticmethod
    def _is_complete(record: Any, table: str, updates: dict[str, Any] | None = None) -> bool:
        required = _REQUIRED_FIELDS.get(table, [])
        if not required:
            return True
        updates = updates or {}
        for field in required:
            value = updates[field] if field in updates else getattr(record, field, None)
            if not value:
                return False
            if isinstance(value, list) and len(value) == 0:
                return False
            if field == "paper_type" and value == "unknown":
                return False
        return True

    @staticmethod
    def _clean_pdf_text(text: str) -> str:
        """Remove spurious line breaks introduced by PDF copy-paste.

        Only removes line wraps (newline without preceding punctuation),
        preserves legitimate line breaks that follow punctuation.
        """
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Remove trailing spaces before newlines
        text = re.sub(r" *\n", "\n", text)
        # Remove single \n NOT preceded by sentence-ending punctuation and NOT part of \n\n
        # This targets PDF wraps (line break without punctuation)
        text = re.sub(r"(?<![.!?。！？…：:；;\n])\n(?!\n)", " ", text)
        # Collapse multiple spaces
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    def list_records(
        self,
        table: str,
        page: int,
        q: str,
        crawl_status: str | None,
        year_min: int | None,
        year_max: int | None,
    ) -> dict[str, Any]:
        model = self._get_model(table)
        stmt = select(model)

        search = q.strip()
        if search:
            filt = self._build_search_filter(model, search)
            if filt is not None:
                stmt = stmt.where(filt)

        stmt = self._apply_filters(model, stmt, crawl_status, year_min, year_max)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self._db.execute(count_stmt).scalar() or 0

        stmt = stmt.order_by(model.id.desc()).offset((page - 1) * _PAGE_SIZE).limit(_PAGE_SIZE)
        rows = self._db.execute(stmt).scalars().all()

        records = []
        for r in rows:
            records.append(self._serialize(r, table))

        year_range = self._get_year_range(model)

        return {
            "total": total,
            "page": page,
            "page_size": _PAGE_SIZE,
            "records": records,
            "editable_fields": _EDITABLE_FIELDS.get(table, []),
            "year_min": year_range["min_year"],
            "year_max": year_range["max_year"],
        }

    def get_record(self, table: str, record_id: int) -> dict[str, Any] | None:
        model = self._get_model(table)
        record = self._db.query(model).filter(model.id == record_id).first()
        if record is None:
            return None
        return {"record": self._serialize(record, table), "editable_fields": _EDITABLE_FIELDS.get(table, [])}

    def update_record(
        self,
        table: str,
        record_id: int,
        fields: dict[str, Any],
        updated_at: str | None,
    ) -> dict[str, Any]:
        model = self._get_model(table)
        record = self._db.query(model).filter(model.id == record_id).first()
        if record is None:
            raise RecordNotFoundError("Record not found")

        allowed = set(_EDITABLE_FIELDS.get(table, []))
        updates: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed:
                continue
            col = model.__table__.columns.get(key)
            if col is None:
                continue
            if key == "abstract" and isinstance(value, str):
                value = self._clean_pdf_text(value)
            updates[key] = value

        if not updates:
            raise ValueError("No valid editable fields provided")

        if hasattr(record, "crawl_status") and record.crawl_status == "partial" and self._is_complete(record, table, updates):
            updates["crawl_status"] = "success"
            updates["error_message"] = None

        now = datetime.now(timezone.utc)
        updates["updated_at"] = now

        if updated_at:
            expected_dt = datetime.fromisoformat(updated_at)
            result = self._db.execute(
                update(model)
                .where(model.id == record_id, model.updated_at == expected_dt)
                .values(**updates)
            )
            if result.rowcount == 0:
                self._db.rollback()
                raise StaleRecordError("该记录已被其他人修改，请刷新后重试")
        else:
            for key, value in updates.items():
                setattr(record, key, value)

        self._db.commit()
        self._db.refresh(record)
        return {"record": self._serialize(record, table), "updated_fields": list(updates.keys())}
