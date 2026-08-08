"""Admin routes for editing lit_metadata, case_metadata, guideline_metadata."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import Integer, func, or_, select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.core.database import get_db
from app.models import CoreFile, GuidelineMetadata, LitMetadata, MedCase, Node, Edge
from app.models.user import User
from app.storage import S3Client
from app.config import get_s3_config

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


class AdminUpdateRequest(BaseModel):
    fields: dict[str, Any]
    updated_at: str | None = None


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


def _apply_filters(model: type, stmt, crawl_status: str | None, year_min: int | None, year_max: int | None):
    if crawl_status:
        stmt = stmt.where(model.crawl_status == crawl_status)
    if year_min is not None:
        stmt = stmt.where(func.cast(func.substring(model.pub_year, 1, 4), Integer) >= year_min)
    if year_max is not None:
        stmt = stmt.where(func.cast(func.substring(model.pub_year, 1, 4), Integer) <= year_max)
    return stmt


@router.get("/{table}")
def list_records(
    table: str,
    page: int = Query(1, ge=1),
    q: str = Query("", description="Search keyword"),
    crawl_status: str | None = Query(None, description="Filter by crawl_status"),
    year_min: int | None = Query(None, description="Min pub_year"),
    year_max: int | None = Query(None, description="Max pub_year"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    model = _get_model(table)
    stmt = select(model)

    search = q.strip()
    if search:
        filt = _build_search_filter(model, search)
        if filt is not None:
            stmt = stmt.where(filt)

    stmt = _apply_filters(model, stmt, crawl_status, year_min, year_max)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(model.id.desc()).offset((page - 1) * _PAGE_SIZE).limit(_PAGE_SIZE)
    rows = db.execute(stmt).scalars().all()

    records = []
    for r in rows:
        records.append(_serialize(r, table))

    year_range = _get_year_range(model, db)

    return {
        "total": total,
        "page": page,
        "page_size": _PAGE_SIZE,
        "records": records,
        "editable_fields": _EDITABLE_FIELDS.get(table, []),
        "year_min": year_range["min_year"],
        "year_max": year_range["max_year"],
    }


def _get_year_range(model, db: Session) -> dict[str, int | None]:
    try:
        min_row = db.execute(select(func.min(func.nullif(func.cast(func.substring(model.pub_year, 1, 4), Integer), 0)))).scalar()
        max_row = db.execute(select(func.max(func.nullif(func.cast(func.substring(model.pub_year, 1, 4), Integer), 0)))).scalar()
        return {
            "min_year": int(min_row) if min_row else None,
            "max_year": int(max_row) if max_row else None,
        }
    except Exception:
        return {"min_year": None, "max_year": None}


@router.get("/{table}/{record_id}")
def get_record(
    table: str,
    record_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    model = _get_model(table)
    record = db.query(model).filter(model.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"record": _serialize(record, table), "editable_fields": _EDITABLE_FIELDS.get(table, [])}


def _delete_s3_file(storage_path: str) -> None:
    try:
        s3_config = get_s3_config()
        if s3_config.access_key and s3_config.secret_key:
            s3 = S3Client(s3_config)
            s3.remove_object(storage_path)
    except Exception:
        LOGGER.exception("S3 deletion failed for %s, proceeding", storage_path)


@router.delete("/lit/{record_id}")
def delete_lit_record(
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    record = db.query(LitMetadata).filter(LitMetadata.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Literature record not found")

    file_uuid = record.file_uuid

    core_file = db.query(CoreFile).filter(CoreFile.file_uuid == file_uuid).first()
    if core_file:
        _delete_s3_file(core_file.storage_path)
        db.delete(core_file)

    related_cases = db.query(MedCase).filter(MedCase.file_uuid == file_uuid).all()
    for case in related_cases:
        db.delete(case)

    node = db.query(Node).filter(Node.title == record.title, Node.node_type == "paper").first()
    if node:
        db.query(Edge).filter(
            or_(Edge.source_id == node.id, Edge.target_id == node.id)
        ).delete()
        db.delete(node)

    db.delete(record)
    db.commit()
    return {"deleted": True, "id": record_id, "file_uuid": file_uuid}


@router.delete("/case/{record_id}")
def delete_case_record(
    record_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    record = db.query(MedCase).filter(MedCase.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Case record not found")

    lit = db.query(LitMetadata).filter(LitMetadata.file_uuid == record.file_uuid).first()
    if lit:
        node = db.query(Node).filter(Node.title == lit.title, Node.node_type == "record").first()
        if node:
            db.query(Edge).filter(
                or_(Edge.source_id == node.id, Edge.target_id == node.id)
            ).delete()
            db.delete(node)

    db.delete(record)
    db.commit()
    return {"deleted": True, "id": record_id}


@router.put("/{table}/{record_id}")
def update_record(
    table: str,
    record_id: int,
    body: AdminUpdateRequest,
    db: Session = Depends(get_db),
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
        if key == "abstract" and isinstance(value, str):
            value = _clean_pdf_text(value)
        updates[key] = value

    if not updates:
        raise HTTPException(status_code=400, detail="No valid editable fields provided")

    if hasattr(record, "crawl_status") and record.crawl_status == "partial" and _is_complete(record, table, updates):
        updates["crawl_status"] = "success"
        updates["error_message"] = None

    now = datetime.now(timezone.utc)
    updates["updated_at"] = now

    if body.updated_at:
        expected_dt = datetime.fromisoformat(body.updated_at)
        result = db.execute(
            update(model)
            .where(model.id == record_id, model.updated_at == expected_dt)
            .values(**updates)
        )
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="该记录已被其他人修改，请刷新后重试",
            )
    else:
        for key, value in updates.items():
            setattr(record, key, value)

    db.commit()
    db.refresh(record)
    return {"record": _serialize(record, table), "updated_fields": list(updates.keys())}
