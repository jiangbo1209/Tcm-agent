"""数据标注管理后台路由（/api/annotation/admin）。

与业务路由共用同一 :func:`annotation_gate` 总闸；每个端点再叠加
:func:`require_admin` 管理员校验。池的创建/预览/列表/PATCH 委托
:mod:`app.services.annotation_service`。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
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
    include_annotated: bool = False


class PoolCreateRequest(PoolFiltersRequest):
    deadline_days: int | None = None
    record_ids: list[int] | None = None


class PoolPatchRequest(BaseModel):
    priority: int | None = None
    status: str | None = None


@router.post("/pools/preview")
def preview_pool(
    body: PoolFiltersRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """只读预览命中与可选数量，附当前页候选明细；零 DB 写入。"""
    try:
        return annotation_service.preview_pool(
            db,
            body.table_name,
            body.model_dump(exclude={"table_name", "include_annotated"}),
            include_annotated=body.include_annotated,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/pools")
def create_pool(
    body: PoolCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """按筛选快照建池，或按 record_ids 显式清单建池；空候选或未知表 -> 400。"""
    try:
        return annotation_service.create_pool(
            db,
            body.table_name,
            body.model_dump(
                exclude={"table_name", "deadline_days", "record_ids", "include_annotated"}
            ),
            body.deadline_days,
            admin,
            record_ids=body.record_ids,
            include_annotated=body.include_annotated,
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


@router.delete("/pools/{pool_id}")
def delete_pool(
    pool_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """删除已关闭的池：仅 closed 可删；不存在 -> 404，其余状态 -> 409。"""
    try:
        return annotation_service.delete_pool(db, admin, pool_id)
    except annotation_service.PoolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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


class ReviewRejectRequest(BaseModel):
    comment: str


@router.get("/review/queue")
def review_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return annotation_service.review_queue(db, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class BatchApproveRequest(BaseModel):
    submission_ids: list[int]


class BatchRejectDecision(BaseModel):
    submission_id: int
    comment: str


class BatchRejectRequest(BaseModel):
    decisions: list[BatchRejectDecision]


@router.post("/review/batch-approve")
def batch_approve(
    body: BatchApproveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not body.submission_ids:
        raise HTTPException(status_code=400, detail="submission_ids 不能为空")
    return annotation_service.batch_approve(db, admin, body.submission_ids)


@router.post("/review/batch-reject")
def batch_reject(
    body: BatchRejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not body.decisions:
        raise HTTPException(status_code=400, detail="decisions 不能为空")
    decisions = [d.model_dump() for d in body.decisions]
    return annotation_service.batch_reject(db, admin, decisions)


def _map_review_errors(exc: Exception) -> HTTPException:
    """服务层异常 -> HTTP：404 缺失 / 400 负载非法 / 其余 ValueError 409。

    各子类均继承 ValueError，必须按 子类 -> ValueError 的顺序判定。
    """
    if isinstance(exc, annotation_service.AnnotationNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, annotation_service.AnnotationFieldValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    assert isinstance(exc, ValueError)
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/review/{submission_id}/approve")
def approve_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """逐条批准：经 update_record 落库；base 冲突转 expired（响应体标记，不报错）。"""
    try:
        return annotation_service.approve_submission(db, admin, submission_id)
    except ValueError as exc:
        raise _map_review_errors(exc) from exc


@router.post("/review/{submission_id}/reject")
def reject_submission(
    submission_id: int,
    body: ReviewRejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """逐条驳回：必须附复核意见；条目进返工箱。"""
    try:
        return annotation_service.reject_submission(db, admin, submission_id, body.comment)
    except ValueError as exc:
        raise _map_review_errors(exc) from exc


@router.get("/logs")
def query_logs(
    table_name: str | None = Query(None),
    record_id: int | None = Query(None),
    actor_id: int | None = Query(None),
    action: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1),
    page_size: int = Query(20),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """分页检索审计日志（id 倒序）；日期参数为 ISO 字符串，非法 -> 400。"""
    try:
        parsed_from = datetime.fromisoformat(date_from) if date_from else None
        parsed_to = datetime.fromisoformat(date_to) if date_to else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式无效，应为 ISO 格式") from exc
    try:
        return annotation_service.query_logs(
            db,
            table_name=table_name,
            record_id=record_id,
            actor_id=actor_id,
            action=action,
            date_from=parsed_from,
            date_to=parsed_to,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/logs/{log_id}/rollback")
def rollback_log(
    log_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """一键回滚：反向应用源日志 old_fields 并追加一条 rollback 审计行。

    404 缺失 / 400 无可回滚字段 / 409 乐观锁冲突（复用复核错误映射）。
    """
    try:
        return annotation_service.rollback_log(db, admin, log_id)
    except ValueError as exc:
        raise _map_review_errors(exc) from exc


@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """仪表盘聚合：先跑惰性清扫保证池余量/在办任务数字新鲜，再分组聚合。"""
    annotation_service.run_lazy_sweep(db)
    return annotation_service.dashboard_stats(db)


@router.get("/export.csv")
def export_workload_csv(
    user_id: int | None = Query(None),
    pool_id: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """工作量明细 CSV 导出（attachment）：先清扫再导出；日期参数非法 -> 400。"""
    try:
        parsed_from = datetime.fromisoformat(date_from) if date_from else None
        parsed_to = datetime.fromisoformat(date_to) if date_to else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式无效，应为 ISO 格式") from exc
    annotation_service.run_lazy_sweep(db)
    csv_text = annotation_service.export_workload_csv(
        db, user_id=user_id, pool_id=pool_id, date_from=parsed_from, date_to=parsed_to
    )
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="workload.csv"'},
    )
