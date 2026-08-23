"""数据标注 API 路由。

所有标注端点统一受 :func:`annotation_gate` 总闸保护：仅当
``ANNOTATION_ENABLED=true`` 时放行，否则返回 503。
路由在导入期零副作用（不连接数据库），配置经 ``get_annotation_config``
的 lru_cache 在请求期读取。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_annotation_config
from app.core.database import get_db
from app.dependencies.auth import require_annotator
from app.models.user import User
from app.services import annotation_service


def annotation_gate() -> None:
    """功能总闸：未开启时拒绝一切数据标注端点。"""
    if not get_annotation_config().ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据标注功能未开启",
        )


router = APIRouter(prefix="/api/annotation", dependencies=[Depends(annotation_gate)])


@router.get("/health")
def annotation_health() -> dict[str, bool]:
    """占位探活端点：能到达即代表总闸已放行。"""
    return {"enabled": True}


class ClaimRequest(BaseModel):
    """领取请求体；当前无字段，保留扩展位（前端可传 {}）。"""


@router.post("/tasks/claim")
def claim_task(
    body: ClaimRequest | None = None,
    db: Session = Depends(get_db),
    annotator: User = Depends(require_annotator),
):
    """标注员领取任务：原子随机抽取（≤50 条）并创建 in_progress 任务。

    无进行中任务冲突/待返工超限/池被抢占等状态类失败统一映射 409；
    显式池不存在为 404。
    """
    try:
        result = annotation_service.draw_and_create_task(db, annotator, action="claim")
    except annotation_service.PoolNotFoundError:
        raise HTTPException(status_code=404, detail="任务池不存在") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {
        "task_id": result["task_id"],
        "count": result["count"],
        "deadline_at": result["deadline_at"],
        "table_name": result["table_name"],
    }


def _map_item_errors(exc: Exception) -> HTTPException:
    """服务层异常 -> HTTP：403 越权 / 404 缺失 / 400 负载非法 / 其余 ValueError 409。

    各子类均继承 ValueError，必须按 子类 -> ValueError 的顺序判定。
    """
    if isinstance(exc, annotation_service.AnnotationPermissionDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, annotation_service.AnnotationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, annotation_service.AnnotationFieldValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    assert isinstance(exc, ValueError)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


class DraftRequest(BaseModel):
    """逐条暂存请求体；键值对为 {可编辑字段: 新值}，空 dict = 标记无需修改。"""

    proposed_fields: dict[str, Any] = {}


@router.put("/items/{item_id}/draft")
def draft_item(
    item_id: int,
    body: DraftRequest,
    db: Session = Depends(get_db),
    annotator: User = Depends(require_annotator),
):
    """暂存单条目（含覆盖自己的草稿与驳回重做），返回提交单 id 与动作类型。"""
    try:
        return annotation_service.item_draft(db, annotator, item_id, body.proposed_fields)
    except ValueError as exc:
        raise _map_item_errors(exc) from exc


@router.post("/tasks/{task_id}/submit")
def submit_task(
    task_id: int,
    db: Session = Depends(get_db),
    annotator: User = Depends(require_annotator),
):
    """整批提交复核：全部条目已暂存才放行；瞬时完成任务，响应携带 base 失效预警清单。"""
    try:
        return annotation_service.batch_submit(db, annotator, task_id)
    except ValueError as exc:
        raise _map_item_errors(exc) from exc
