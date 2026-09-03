"""Admin routes for editing lit_metadata, case_metadata, guideline_metadata."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_admin
from app.models.user import User
from app.repositories.admin_repo import (
    AdminQueryRepository,
    RecordNotFoundError,
    StaleRecordError,
)
from app.services import annotation_service
from app.services.admin_service import AdminDeleteRecordNotFound, AdminService

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminUpdateRequest(BaseModel):
    fields: dict[str, Any]
    updated_at: str | None = None


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
    try:
        return AdminQueryRepository(db).list_records(
            table, page, q, crawl_status, year_min, year_max
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{table}/{record_id}")
def get_record(
    table: str,
    record_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = AdminQueryRepository(db).get_record(table, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return result


@router.put("/{table}/{record_id}")
def update_record(
    table: str,
    record_id: int,
    body: AdminUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # F4-V1/G3：直改前快照可编辑字段现值，成功后落 save_direct 审计（与 gate 无关）
    old_snapshot = annotation_service.snapshot_core_record(db, table, record_id)
    try:
        result = AdminQueryRepository(db).update_record(
            table, record_id, body.fields, body.updated_at
        )
    except RecordNotFoundError:
        raise HTTPException(status_code=404, detail="Record not found") from None
    except StaleRecordError:
        raise HTTPException(
            status_code=409,
            detail="该记录已被其他人修改，请刷新后重试",
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    changed_keys = [
        key
        for key in result["updated_fields"]
        if old_snapshot is not None and key in old_snapshot
    ]
    annotation_service.log_direct_edit(
        db,
        table_name=table,
        record_id=record_id,
        actor=admin,
        old_values={key: old_snapshot[key] for key in changed_keys} if old_snapshot else {},
        new_values={key: result["record"][key] for key in changed_keys},
    )
    db.commit()
    return result


@router.delete("/lit/{record_id}")
def delete_lit_record(
    record_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return AdminService(db).delete_lit(record_id)
    except AdminDeleteRecordNotFound:
        raise HTTPException(status_code=404, detail="Literature record not found") from None


@router.delete("/case/{record_id}")
def delete_case_record(
    record_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return AdminService(db).delete_case(record_id)
    except AdminDeleteRecordNotFound:
        raise HTTPException(status_code=404, detail="Case record not found") from None
