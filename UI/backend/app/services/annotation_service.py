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

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case, exists, func, insert, select, update
from sqlalchemy.orm import Session

from app.config import get_annotation_config
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
# 单次随机抽取的记录数上限
_MAX_DRAW_SIZE = 50


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


def resolve_pool(db: Session, pool_id: int | None = None) -> AnnotationPool:
    """解析抽取目标池。

    显式 pool_id：池必须存在（否则 PoolNotFoundError）且 status='active'
    （否则 ValueError）。pool_id 为 None 时按 priority DESC / created_at DESC /
    id DESC 找第一个仍有 available 余量的 active 池；一个都没有抛 ValueError。
    """
    if pool_id is not None:
        pool = db.get(AnnotationPool, pool_id)
        if pool is None:
            raise PoolNotFoundError("Pool not found")
        if pool.status != "active":
            raise ValueError("任务池未开放")
        return pool

    available_cnt = func.count(case((AnnotationPoolItem.status == "available", 1)))
    row = db.execute(
        select(AnnotationPool, available_cnt)
        .outerjoin(AnnotationPoolItem, AnnotationPoolItem.pool_id == AnnotationPool.id)
        .where(AnnotationPool.status == "active")
        .group_by(AnnotationPool.id)
        .having(available_cnt > 0)
        .order_by(
            AnnotationPool.priority.desc(),
            AnnotationPool.created_at.desc(),
            AnnotationPool.id.desc(),
        )
        .limit(1)
    ).first()
    if row is None:
        raise ValueError("暂无可领取的任务池")
    return row[0]


def _assert_user_can_receive_task(db: Session, user: User) -> None:
    """领取前置约束（应用层校验）：进行中任务唯一 + 待返工条目上限。"""
    has_active_task = db.execute(
        select(AnnotationTask.id)
        .where(
            AnnotationTask.claimed_by == user.id,
            AnnotationTask.status.in_(_ACTIVE_TASK_STATUSES),
        )
        .limit(1)
    ).first()
    if has_active_task is not None:
        raise ValueError("已有进行中的任务")

    max_pending_rework = get_annotation_config().MAX_PENDING_REWORK
    if max_pending_rework > 0:
        rejected_count = (
            db.execute(
                select(func.count())
                .select_from(AnnotationTaskItem)
                .join(AnnotationTask, AnnotationTask.id == AnnotationTaskItem.task_id)
                .where(
                    AnnotationTask.claimed_by == user.id,
                    AnnotationTaskItem.status == "rejected",
                )
            ).scalar()
            or 0
        )
        if int(rejected_count) >= max_pending_rework:
            raise ValueError("待返工条目过多")


def _available_count(db: Session, pool_id: int) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(AnnotationPoolItem)
            .where(
                AnnotationPoolItem.pool_id == pool_id,
                AnnotationPoolItem.status == "available",
            )
        ).scalar()
        or 0
    )


def _random_candidate_ids(db: Session, pool_id: int, n: int) -> list[int]:
    """随机抽 n 个 available 候选 id（ORDER BY random() LIMIT n，SQLite/PG 通用）。"""
    stmt = (
        select(AnnotationPoolItem.id)
        .where(
            AnnotationPoolItem.pool_id == pool_id,
            AnnotationPoolItem.status == "available",
        )
        .order_by(func.random())
        .limit(n)
    )
    return [item_id for item_id in db.execute(stmt).scalars()]


def _draw_atomically(db: Session, target_pool_id: int, n: int) -> list[int]:
    """原子地把 n 个 available 记录置为 assigned 并返回被抽中的 pool_item id。

    postgresql：SELECT ... ORDER BY random() LIMIT n FOR UPDATE SKIP LOCKED，
    行锁保证并发事务抽到互斥子集；锁到的行数不足即并发抢占。
    其余方言（如 SQLite）：选 id 后用条件 UPDATE（WHERE status='available'）
    对账 rowcount——短缺说明候选已被并发改写，回滚后重试一次，仍短缺则报错。
    """
    if db.get_bind().dialect.name == "postgresql":
        locked_stmt = (
            select(AnnotationPoolItem.id)
            .where(
                AnnotationPoolItem.pool_id == target_pool_id,
                AnnotationPoolItem.status == "available",
            )
            .order_by(func.random())
            .limit(n)
            .with_for_update(skip_locked=True)
        )
        drawn_ids = [item_id for item_id in db.execute(locked_stmt).scalars()]
        if len(drawn_ids) != n:
            db.rollback()
            raise ValueError("任务池已被抢占，请重试")
        db.execute(
            update(AnnotationPoolItem)
            .where(AnnotationPoolItem.id.in_(drawn_ids))
            .values(status="assigned")
        )
        return drawn_ids

    drawn_ids: list[int] | None = None
    for _attempt in range(2):
        candidate_ids = _random_candidate_ids(db, target_pool_id, n)
        if not candidate_ids:
            db.rollback()
            continue
        result = db.execute(
            update(AnnotationPoolItem)
            .where(
                AnnotationPoolItem.id.in_(candidate_ids),
                AnnotationPoolItem.status == "available",
            )
            .values(status="assigned")
        )
        if result.rowcount == len(candidate_ids):
            drawn_ids = list(candidate_ids)
            break
        # rowcount 对账失败：候选中有记录在选取与更新之间被并发占用
        db.rollback()
    if drawn_ids is None:
        raise ValueError("任务池已被抢占，请重试")
    return drawn_ids


def draw_and_create_task(
    db: Session,
    user: User,
    pool_id: int | None = None,
    action: str = "claim",
    actor: User | None = None,
) -> dict[str, Any]:
    """随机抽取并创建标注任务（annotator 领取与 admin 代派共用的唯一路径）。

    流程：前置约束校验 -> 解析目标池 -> min(50, available) 原子抽取 ->
    建 AnnotationTask(in_progress) + 逐条 TaskItem(pending) -> 审计日志 -> commit。
    抛出的 ValueError 由路由映射为 409/400 或逐用户错误条目。
    """
    if action not in ("claim", "assign"):
        raise ValueError(f"Invalid action: {action}")

    _assert_user_can_receive_task(db, user)
    pool = resolve_pool(db, pool_id)

    draw_size = min(_MAX_DRAW_SIZE, _available_count(db, pool.id))
    if draw_size <= 0:
        raise ValueError("暂无可领取的任务池")
    drawn_ids = _draw_atomically(db, pool.id, draw_size)

    deadline_days = pool.deadline_days or get_annotation_config().TASK_DEADLINE_DAYS
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    task = AnnotationTask(
        pool_id=pool.id,
        claimed_by=user.id,
        claimed_at=now_utc,
        deadline_at=now_utc + timedelta(days=deadline_days),
        status="in_progress",
    )
    db.add(task)
    db.flush()

    claimed_pool_items = (
        db.query(AnnotationPoolItem)
        .filter(AnnotationPoolItem.id.in_(drawn_ids))
        .all()
    )
    task_items = [
        AnnotationTaskItem(
            task_id=task.id,
            table_name=pool_item.table_name,
            record_id=pool_item.record_id,
            source_pool_item_id=pool_item.id,
            status="pending",
        )
        for pool_item in claimed_pool_items
    ]
    db.add_all(task_items)
    _write_log(
        db,
        table_name=pool.table_name,
        record_id=0,
        actor=actor if actor is not None else user,
        action=action,
        new_fields={"task_id": task.id, "count": len(task_items)},
    )
    db.commit()

    return {
        "task_id": task.id,
        "pool_id": pool.id,
        "table_name": pool.table_name,
        "count": len(task_items),
        "deadline_at": task.deadline_at.isoformat() if task.deadline_at else None,
    }


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
