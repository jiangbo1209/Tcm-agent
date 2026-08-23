"""标注池服务：筛选快照建池（三类排除）、只读预览、池列表与优先级/状态管理。

候选筛选必须与 admin 列表页口径完全一致：复用
``AdminQueryRepository._build_search_filter`` / ``_apply_filters``
（@staticmethod，经类调用），且所有排除都在 SQL 层完成，禁止取回后在
Python 里二次过滤。

审计约定：annotation_logs 本是逐记录的审计行；**池级事件以 record_id=0
落一行日志**（new_fields 携带 pool_id/count 等）。本模块的 :func:`_write_log`
是后续所有标注 todo 共用的唯一写日志入口——它只 add 不 commit，
事务由调用方控制。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, exists, func, insert, select
from sqlalchemy.orm import Session

from app.models import (
    AnnotationLog,
    AnnotationPool,
    AnnotationPoolItem,
    AnnotationTask,
    AnnotationTaskItem,
)
from app.models.user import User
from app.repositories.admin_repo import AdminQueryRepository, _TABLE_MAP

# 占用记录的池状态：active/paused 中的记录不可再入新池
_BLOCKING_POOL_STATUSES = ("active", "paused")
# 占用记录的任务状态
_ACTIVE_TASK_STATUSES = ("open", "in_progress")
# PATCH 允许的目标池状态
_PATCHABLE_POOL_STATUSES = ("paused", "closed")


class PoolNotFoundError(Exception):
    """PATCH 目标池不存在。"""


def _validate_table(table_name: str) -> type:
    model = _TABLE_MAP.get(table_name)
    if model is None:
        raise ValueError(f"Unknown table: {table_name}")
    return model


def _exclusion_predicates(model: type, table_name: str) -> list[Any]:
    """三类排除，全部编译为相关子查询 NOT EXISTS（SQL 层过滤）。

    (a) 已存在于任何 active/paused 池的 annotation_pool_items；
    (b) 已挂在任何 open/in_progress 任务的 annotation_task_items 上；
    (c) 曾有 status='approved' 的 annotation_task_items（永久占用）。
    """
    in_blocking_pool = (
        select(AnnotationPoolItem.id)
        .join(AnnotationPool, AnnotationPool.id == AnnotationPoolItem.pool_id)
        .where(
            AnnotationPoolItem.table_name == table_name,
            AnnotationPoolItem.record_id == model.id,
            AnnotationPool.status.in_(_BLOCKING_POOL_STATUSES),
        )
    )
    in_running_task = (
        select(AnnotationTaskItem.id)
        .join(AnnotationTask, AnnotationTask.id == AnnotationTaskItem.task_id)
        .where(
            AnnotationTaskItem.table_name == table_name,
            AnnotationTaskItem.record_id == model.id,
            AnnotationTask.status.in_(_ACTIVE_TASK_STATUSES),
        )
    )
    approved_before = select(AnnotationTaskItem.id).where(
        AnnotationTaskItem.table_name == table_name,
        AnnotationTaskItem.record_id == model.id,
        AnnotationTaskItem.status == "approved",
    )
    return [
        ~exists(in_blocking_pool),
        ~exists(in_running_task),
        ~exists(approved_before),
    ]


def _filtered_stmt(model: type, filters: dict[str, Any]):
    """与 admin 列表页同口径的候选语句（搜索 + crawl_status + 年份区间）。"""
    stmt = select(model)
    search = str(filters.get("q") or "").strip()
    if search:
        search_filter = AdminQueryRepository._build_search_filter(model, search)
        if search_filter is not None:
            stmt = stmt.where(search_filter)
    return AdminQueryRepository._apply_filters(
        model,
        stmt,
        filters.get("crawl_status"),
        filters.get("year_min"),
        filters.get("year_max"),
    )


def _count(db: Session, stmt) -> int:
    # 与 AdminQueryRepository.list_records 相同的计数模式
    return int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0)


def preview_pool(db: Session, table_name: str, filters: dict[str, Any] | None) -> dict[str, int]:
    """只读预览：返回 {total_matched, eligible}。绝不产生任何 DB 写入。"""
    model = _validate_table(table_name)
    filters = filters or {}
    base = _filtered_stmt(model, filters)
    total_matched = _count(db, base)
    eligible = _count(db, base.where(*_exclusion_predicates(model, table_name)))
    return {"total_matched": total_matched, "eligible": eligible}


def create_pool(
    db: Session,
    table_name: str,
    filters: dict[str, Any] | None,
    deadline_days: int | None,
    created_by_user: User | None,
) -> dict[str, Any]:
    """按当前筛选快照建池：pool(active) + 每条 eligible 记录一条 pool_item(available)。

    返回含 pool_id/total；matched 但被三类排除的记录数 >0 时附带 shortfall 信息字段。
    空候选集抛 ValueError（路由层转 400），不残留任何行。
    """
    model = _validate_table(table_name)
    filters = dict(filters or {})
    base = _filtered_stmt(model, filters)
    matched = _count(db, base)

    eligible_stmt = (
        base.with_only_columns(model.id)
        .where(*_exclusion_predicates(model, table_name))
        .order_by(model.id.desc())
    )
    eligible_ids: list[int] = [row for row in db.execute(eligible_stmt).scalars()]
    if not eligible_ids:
        raise ValueError("无可加入池中的候选记录：请调整筛选条件")

    pool = AnnotationPool(
        table_name=table_name,
        filter_json=filters,
        status="active",
        priority=0,
        deadline_days=deadline_days,
        created_by=created_by_user.id if created_by_user is not None else None,
    )
    db.add(pool)
    db.flush()
    db.execute(
        insert(AnnotationPoolItem),
        [
            {
                "pool_id": pool.id,
                "table_name": table_name,
                "record_id": record_id,
                "status": "available",
            }
            for record_id in eligible_ids
        ],
    )
    _write_log(
        db,
        table_name=table_name,
        record_id=0,
        actor=created_by_user,
        action="create_pool",
        new_fields={"pool_id": pool.id, "count": len(eligible_ids)},
    )
    db.commit()

    result: dict[str, Any] = {
        "pool_id": pool.id,
        "table_name": pool.table_name,
        "status": pool.status,
        "priority": pool.priority,
        "deadline_days": pool.deadline_days,
        "created_at": pool.created_at.isoformat() if pool.created_at else None,
        "total": len(eligible_ids),
    }
    shortfall = max(0, matched - len(eligible_ids))
    if shortfall > 0:
        result["shortfall"] = shortfall
    return result


def _serialize_pool(pool: AnnotationPool, total_items: int, remaining_items: int) -> dict[str, Any]:
    return {
        "id": pool.id,
        "table_name": pool.table_name,
        "status": pool.status,
        "priority": pool.priority,
        "deadline_days": pool.deadline_days,
        "total_items": total_items,
        "remaining_items": remaining_items,
        "created_at": pool.created_at.isoformat() if pool.created_at else None,
    }


def list_pools(db: Session) -> list[dict[str, Any]]:
    """全部池 + 余量统计（单条 GROUP BY 聚合，无 N+1）。"""
    available_count = func.count(case((AnnotationPoolItem.status == "available", 1)))
    rows = db.execute(
        select(AnnotationPool, func.count(AnnotationPoolItem.id), available_count)
        .outerjoin(AnnotationPoolItem, AnnotationPoolItem.pool_id == AnnotationPool.id)
        .group_by(AnnotationPool.id)
        .order_by(
            AnnotationPool.priority.desc(),
            AnnotationPool.created_at.desc(),
            AnnotationPool.id.desc(),
        )
    ).all()
    return [_serialize_pool(pool, int(total), int(remaining)) for pool, total, remaining in rows]


def update_pool(
    db: Session,
    pool_id: int,
    *,
    priority: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """调整池优先级 / 状态（仅 paused|closed）；未知池抛 PoolNotFoundError。"""
    if status is not None and status not in _PATCHABLE_POOL_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    pool = db.get(AnnotationPool, pool_id)
    if pool is None:
        raise PoolNotFoundError("Pool not found")

    if status is not None:
        pool.status = status
    if priority is not None:
        pool.priority = priority
    db.commit()
    db.refresh(pool)

    counts = db.execute(
        select(
            func.count(AnnotationPoolItem.id),
            func.count(case((AnnotationPoolItem.status == "available", 1))),
        ).where(AnnotationPoolItem.pool_id == pool_id)
    ).one()
    return _serialize_pool(pool, int(counts[0]), int(counts[1]))


def _write_log(
    db: Session,
    *,
    table_name: str,
    record_id: int,
    actor: User | None,
    action: str,
    old_fields: dict[str, Any] | None = None,
    new_fields: dict[str, Any] | None = None,
    submission_id: int | None = None,
) -> None:
    """追加一条审计行；只 add 不 commit —— 提交时机由调用方掌控。

    record_id=0 为池级事件约定（日志表本身是逐记录粒度）。
    username 冗余快照保证用户被删后审计仍可读。
    """
    db.add(
        AnnotationLog(
            table_name=table_name,
            record_id=record_id,
            actor_id=actor.id if actor is not None else None,
            username=actor.username if actor is not None else "system",
            action=action,
            old_fields=old_fields,
            new_fields=new_fields,
            submission_id=submission_id,
        )
    )
