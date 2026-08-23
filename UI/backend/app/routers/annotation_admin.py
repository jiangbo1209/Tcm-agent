"""数据标注管理后台路由（/api/annotation/admin）。

与业务路由共用同一 :func:`annotation_gate` 总闸；每个端点再叠加
:func:`require_admin` 管理员校验。池的创建/预览/列表/PATCH 委托
:mod:`app.services.annotation_service`。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_admin
from app.models.user import User
from app.routers.annotation import annotation_gate
from app.services import annotation_service

router = APIRouter(
    prefix="/api/annotation/admin", dependencies=[Depends(annotation_gate)]
)


class PoolFiltersRequest(BaseModel):
    table_name: str
    q: str | None = None
    crawl_status: str | None = None
    year_min: int | None = None
    year_max: int | None = None


class PoolCreateRequest(PoolFiltersRequest):
    deadline_days: int | None = None


class PoolPatchRequest(BaseModel):
    priority: int | None = None
    status: str | None = None


@router.post("/pools/preview")
def preview_pool(
    body: PoolFiltersRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """只读预览命中与可选数量；零 DB 写入。"""
    try:
        return annotation_service.preview_pool(
            db, body.table_name, body.model_dump(exclude={"table_name"})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/pools")
def create_pool(
    body: PoolCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """按筛选快照建池；空候选或未知表 -> 400，shortfall>0 时随响应提示。"""
    try:
        return annotation_service.create_pool(
            db,
            body.table_name,
            body.model_dump(exclude={"table_name", "deadline_days"}),
            body.deadline_days,
            admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/pools")
def list_pools(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return annotation_service.list_pools(db)


@router.patch("/pools/{pool_id}")
def patch_pool(
    pool_id: int,
    body: PoolPatchRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return annotation_service.update_pool(
            db, pool_id, priority=body.priority, status=body.status
        )
    except annotation_service.PoolNotFoundError:
        raise HTTPException(status_code=404, detail="Pool not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class AssignRequest(BaseModel):
    pool_id: int
    user_ids: list[int]


@router.post("/tasks/assign")
def assign_tasks(
    body: AssignRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """把池代派给若干标注员：逐用户走与 claim 完全相同的抽取路径。

    池级问题（不存在/未开放）整体 404/400；单个用户的问题（不存在、
    非标注员、已禁用、已有任务等）只落该用户的错误条目，不影响其他用户。
    """
    try:
        annotation_service.resolve_pool(db, body.pool_id)
    except annotation_service.PoolNotFoundError:
        raise HTTPException(status_code=404, detail="Pool not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results: list[dict] = []
    for user_id in body.user_ids:
        target = db.get(User, user_id)
        if target is None:
            results.append({"user_id": user_id, "ok": False, "error": "用户不存在"})
            continue
        if target.role != "annotator":
            results.append({"user_id": user_id, "ok": False, "error": "用户不是标注员"})
            continue
        if not target.is_active:
            results.append({"user_id": user_id, "ok": False, "error": "用户已禁用"})
            continue
        try:
            drawn = annotation_service.draw_and_create_task(
                db, target, pool_id=body.pool_id, action="assign", actor=admin
            )
        except ValueError as exc:
            results.append({"user_id": user_id, "ok": False, "error": str(exc)})
            continue
        results.append(
            {
                "user_id": user_id,
                "ok": True,
                "task_id": drawn["task_id"],
                "count": drawn["count"],
                "deadline_at": drawn["deadline_at"],
            }
        )
    return {"results": results}
