"""Admin routes for editing lit_metadata, case_metadata, guideline_metadata."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.core.database_pg import get_pg_db
from app.models.graph import GuidelineMetadata, LitMetadata, MedCase
from app.models.user import User

LOGGER = logging.getLogger("admin_api")

router = APIRouter(prefix="/api/admin", tags=["admin"])

_PAGE_SIZE = 20

_TABLE_MAP: dict[str, type] = {
    "lit": LitMetadata,
    "case": MedCase,
    "guideline": GuidelineMetadata,
}

_EDITABLE_FIELDS: dict[str, list[str]] = {
    "lit": [
        "title", "cleaned_title", "authors", "abstract", "keywords",
        "paper_type", "source_site", "source_url", "journal", "pub_year",
        "matched_title", "is_exact_match", "ai_summary",
    ],
    "case": [
        "age", "bmi", "menstruation", "infertility", "lifestyle",
        "present_symptoms", "medical_history", "lab_tests", "ultrasound",
        "followup", "western_diagnosis", "tcm_diagnosis", "treatment_principle",
        "prescription", "acupoints", "assisted_reproduction", "western_medicine",
        "efficacy", "adverse_reactions", "commentary",
    ],
    "guideline": [
        "title", "cleaned_title", "authors", "abstract", "keywords",
        "paper_type", "source_site", "source_url", "journal", "pub_year",
        "matched_title", "is_exact_match",
    ],
}


class AdminUpdateRequest(BaseModel):
    fields: dict[str, Any]


def _get_model(table: str) -> type:
    model = _TABLE_MAP.get(table)
    if model is None:
        raise HTTPException(status_code=400, detail=f"Unknown table: {table}")
    return model


def _serialize(record: Any, table: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for col in record.__table__.columns:
        key = str(col.name)
        value = getattr(record, key, None)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[key] = value
    return data


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


@router.get("/{table}")
def list_records(
    table: str,
    page: int = Query(1, ge=1),
    q: str = Query("", description="Search keyword"),
    db: Session = Depends(get_pg_db),
    _admin: User = Depends(require_admin),
):
    model = _get_model(table)
    stmt = select(model)

    search = q.strip()
    if search:
        filt = _build_search_filter(model, search)
        if filt is not None:
            stmt = stmt.where(filt)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(model.id.desc()).offset((page - 1) * _PAGE_SIZE).limit(_PAGE_SIZE)
    rows = db.execute(stmt).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": _PAGE_SIZE,
        "records": [_serialize(r, table) for r in rows],
        "editable_fields": _EDITABLE_FIELDS.get(table, []),
        "hint": _get_table_hint(table),
    }


@router.get("/{table}/{record_id}")
def get_record(
    table: str,
    record_id: int,
    db: Session = Depends(get_pg_db),
    _admin: User = Depends(require_admin),
):
    model = _get_model(table)
    record = db.query(model).filter(model.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"record": _serialize(record, table), "editable_fields": _EDITABLE_FIELDS.get(table, [])}


@router.put("/{table}/{record_id}")
def update_record(
    table: str,
    record_id: int,
    body: AdminUpdateRequest,
    db: Session = Depends(get_pg_db),
    _admin: User = Depends(require_admin),
):
    model = _get_model(table)
    record = db.query(model).filter(model.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")

    allowed = set(_EDITABLE_FIELDS.get(table, []))
    updates: dict[str, Any] = {}
    for key, value in body.fields.items():
        if key not in allowed:
            continue
        col = model.__table__.columns.get(key)
        if col is None:
            continue
        updates[key] = value

    if not updates:
        raise HTTPException(status_code=400, detail="No valid editable fields provided")

    updates["updated_at"] = datetime.now(timezone.utc)
    for key, value in updates.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return {"record": _serialize(record, table), "updated_fields": list(updates.keys())}


def _get_table_hint(table: str) -> str:
    hints = {
        "lit": "编辑文献元数据，包括标题、摘要、关键词、AI摘要等字段。authors 和 keywords 为 JSON 数组格式。",
        "case": "编辑病案结构化数据，包括诊断、治法、方剂等 20 个字段。",
        "guideline": "编辑指南/报告元数据，字段结构与文献元数据类似。",
    }
    return hints.get(table, "")
