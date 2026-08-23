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
    AnnotationSubmission,
    AnnotationTask,
    AnnotationTaskItem,
)
from app.models.user import User
from app.repositories.admin_repo import (
    _EDITABLE_FIELDS,
    AdminQueryRepository,
    _TABLE_MAP,
    StaleRecordError,
)

# 占用记录的池状态：active/paused 中的记录不可再入新池
_BLOCKING_POOL_STATUSES = ("active", "paused")
# 占用记录的任务状态
_ACTIVE_TASK_STATUSES = ("open", "in_progress")
# PATCH 允许的目标池状态
_PATCHABLE_POOL_STATUSES = ("paused", "closed")
# 单次随机抽取的记录数上限
_MAX_DRAW_SIZE = 50
# pending=首次暂存 drafted=覆盖自己草稿 rejected=返工重做；submitted/approved 已进复核流
_DRAFTABLE_ITEM_STATUSES = ("pending", "drafted", "rejected")


class PoolNotFoundError(Exception):
    """PATCH 目标池不存在。"""


class AnnotationNotFoundError(ValueError):
    """条目/任务/核心记录不存在；路由须先于 ValueError 捕获并映射 404。"""


class AnnotationPermissionDeniedError(ValueError):
    """越权操作他人任务；路由须先于 ValueError 捕获并映射 403。

    故意继承 ValueError：旧式 ``except ValueError`` 兜底仍能兜住，
    但路由层必须按 子类 -> ValueError 的顺序捕获才能精确映射。
    """


class AnnotationFieldValidationError(ValueError):
    """请求负载校验失败（如字段不可编辑）；路由映射 400。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


def _load_owned_task(db: Session, user: User, task_id: int) -> AnnotationTask:
    """取任务并校验属主；缺失 404、越权 403，由调用方继续做状态类校验。"""
    task = db.get(AnnotationTask, task_id)
    if task is None:
        raise AnnotationNotFoundError("任务不存在")
    if task.claimed_by != user.id:
        raise AnnotationPermissionDeniedError("只能操作自己任务中的条目")
    return task


def _latest_submission(db: Session, item_id: int) -> AnnotationSubmission | None:
    return (
        db.query(AnnotationSubmission)
        .filter(AnnotationSubmission.item_id == item_id)
        .order_by(AnnotationSubmission.id.desc())
        .first()
    )


def item_draft(
    db: Session,
    user: User,
    item_id: int,
    proposed_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """逐条暂存：upsert 一条 draft 提交单并快照核心记录 updated_at。

    - proposed_fields 为空 dict 表达「标记无需修改」；
    - 已有 draft 提交单 -> 原位覆盖（同一行）；rejected -> 新建行保留驳回历史；
    - base_updated_at 取核心记录当前 updated_at，供整批提交时做 C8 失效预警；
    - 本函数不把 proposed_fields 写入核心表（T8 审批时才落库）。
    """
    item = db.get(AnnotationTaskItem, item_id)
    if item is None:
        raise AnnotationNotFoundError("条目不存在")
    task = _load_owned_task(db, user, item.task_id)
    if task.status != "in_progress":
        raise ValueError("任务不在进行中")
    if item.status not in _DRAFTABLE_ITEM_STATUSES:
        raise ValueError("该条目当前状态不可暂存")

    fields = dict(proposed_fields or {})
    allowed = set(_EDITABLE_FIELDS.get(item.table_name, []))
    for key in fields:
        if key not in allowed:
            raise AnnotationFieldValidationError(f"字段不可编辑: {key}")

    model = _TABLE_MAP.get(item.table_name)
    core = None if model is None else db.query(model).filter(model.id == item.record_id).first()
    if core is None:
        raise AnnotationNotFoundError("核心记录不存在")

    latest = _latest_submission(db, item.id)
    if latest is not None and latest.status == "draft":
        submission = latest
    else:
        submission = AnnotationSubmission(
            item_id=item.id,
            annotator_id=user.id,
            username=user.username,
            proposed_fields=fields,
            base_updated_at=core.updated_at,
            status="draft",
        )
        db.add(submission)
        db.flush()
    submission.proposed_fields = fields
    submission.base_updated_at = core.updated_at
    submission.annotator_id = user.id
    submission.username = user.username

    item.status = "drafted"
    action = "no_change" if not fields else "draft"
    _write_log(
        db,
        table_name=item.table_name,
        record_id=item.record_id,
        actor=user,
        action=action,
        new_fields=fields,
        submission_id=submission.id,
    )
    db.commit()

    return {
        "item_id": item.id,
        "task_id": task.id,
        "submission_id": submission.id,
        "action": action,
        "base_updated_at": submission.base_updated_at.isoformat()
        if submission.base_updated_at
        else None,
    }


def batch_submit(db: Session, user: User, task_id: int) -> dict[str, Any]:
    """整批提交：全部条目已暂存才放行；瞬时完成任务（复核解耦，T8 再审批）。

    C8 base 失效检测：比对各 draft 提交单的 base_updated_at 与核心记录当前
    updated_at，失配者列入 stale_base_item_ids —— 仅预警，绝不拦截提交。
    """
    task = _load_owned_task(db, user, task_id)
    if task.status != "in_progress":
        raise ValueError("任务不在进行中")

    items = (
        db.query(AnnotationTaskItem)
        .filter(AnnotationTaskItem.task_id == task_id)
        .order_by(AnnotationTaskItem.id)
        .all()
    )
    undrafted = [it for it in items if it.status != "drafted"]
    if items and undrafted:
        raise ValueError(f"还有 {len(undrafted)} 条未暂存")

    draft_submissions = {
        s.item_id: s
        for s in db.query(AnnotationSubmission)
        .filter(
            AnnotationSubmission.item_id.in_([it.id for it in items]),
            AnnotationSubmission.status == "draft",
        )
        .all()
    }

    stale_item_ids: list[int] = []
    for it in items:
        submission = draft_submissions.get(it.id)
        model = _TABLE_MAP.get(it.table_name)
        core = (
            None if model is None else db.query(model).filter(model.id == it.record_id).first()
        )
        current_updated_at = getattr(core, "updated_at", None) if core is not None else None
        if (
            submission is None
            or current_updated_at is None
            or submission.base_updated_at != current_updated_at
        ):
            stale_item_ids.append(it.id)

    now_utc = _utcnow()
    for submission in draft_submissions.values():
        submission.status = "pending"
    for it in items:
        it.status = "submitted"
        it.submitted_at = now_utc
    task.status = "completed"

    _write_log(
        db,
        table_name=items[0].table_name if items else "lit",
        record_id=0,
        actor=user,
        action="submit",
        new_fields={"task_id": task.id, "count": len(items)},
    )
    db.commit()

    return {
        "task_id": task.id,
        "completed": True,
        "count": len(items),
        "stale_base_item_ids": sorted(stale_item_ids),
    }


def _release_pool_item(db: Session, source_pool_item_id: int | None) -> None:
    """把条目占用的池位归还为 available（source 缺失或已被并发处理时静默跳过）。"""
    if source_pool_item_id is None:
        return
    pool_item = db.get(AnnotationPoolItem, source_pool_item_id)
    if pool_item is not None:
        pool_item.status = "available"


def run_lazy_sweep(db: Session, now: datetime | None = None) -> dict[str, int]:
    """惰性清扫（plan todo #7）：超期任务恢复 + 返工过期释放，随请求触发。

    (a) 截止恢复：status='in_progress' 且 deadline_at < now 的任务 ——
        pending 条目 -> recovered 并把池位归还 available；
        drafted 条目 -> 其 draft 提交单转 pending、条目转 submitted
        （等价 batch_submit 落库语义但不经它——后者强制全部已暂存）；
        收尾定态：任一条目 submitted/approved -> completed，否则 cancelled；
        每任务仅落一行 expire_recover 审计（record_id=0 池级约定）。
    (b) 返工释放：status='rejected' 且 rejected_at + REWORK_DAYS < now 的条目 ->
        recovered 并归还池位；逐条落一行 expire_recover 审计。
    幂等：两分支的筛选条件在处理后自然失配（终态不再命中），连跑第二次全零。
    返回计数器字典供测试断言；now 可注入以保证确定性。
    """
    now_utc = now if now is not None else _utcnow()
    recovered = 0
    resubmitted = 0
    completed_tasks = 0
    cancelled_tasks = 0

    expired_tasks = (
        db.query(AnnotationTask)
        .filter(AnnotationTask.status == "in_progress")
        .filter(AnnotationTask.deadline_at.isnot(None))
        .filter(AnnotationTask.deadline_at < now_utc)
        .order_by(AnnotationTask.id)
        .all()
    )
    for task in expired_tasks:
        items = (
            db.query(AnnotationTaskItem)
            .filter(AnnotationTaskItem.task_id == task.id)
            .order_by(AnnotationTaskItem.id)
            .all()
        )
        for item in items:
            if item.status == "pending":
                item.status = "recovered"
                recovered += 1
                _release_pool_item(db, item.source_pool_item_id)
            elif item.status == "drafted":
                # 等价 batch_submit 的落库动作，但只针对本任务的 drafted 条目，
                # 不复用该函数（其「全部条目必须已暂存」前置在这里不成立）。
                db.query(AnnotationSubmission).filter(
                    AnnotationSubmission.item_id == item.id,
                    AnnotationSubmission.status == "draft",
                ).update({AnnotationSubmission.status: "pending"}, synchronize_session=False)
                item.status = "submitted"
                item.submitted_at = now_utc
                resubmitted += 1

        has_output = any(it.status in ("submitted", "approved") for it in items)
        task.status = "completed" if has_output else "cancelled"
        if has_output:
            completed_tasks += 1
        else:
            cancelled_tasks += 1

        _write_log(
            db,
            table_name=items[0].table_name if items else "lit",
            record_id=0,
            actor=None,
            action="expire_recover",
            new_fields={"task_id": task.id, "recovered": recovered, "resubmitted": resubmitted},
        )

    rework_days = timedelta(days=get_annotation_config().REWORK_DAYS)
    released_rework = 0
    # 粗筛后 Python 侧精确比较：col + timedelta 的 SQL 算术在 SQLite 上不可靠
    rejected_candidates = (
        db.query(AnnotationTaskItem)
        .filter(
            AnnotationTaskItem.status == "rejected",
            AnnotationTaskItem.rejected_at.isnot(None),
            AnnotationTaskItem.rejected_at < now_utc,
        )
        .order_by(AnnotationTaskItem.id)
        .all()
    )
    for item in rejected_candidates:
        assert item.rejected_at is not None
        if not (item.rejected_at + rework_days < now_utc):
            continue
        item.status = "recovered"
        released_rework += 1
        _release_pool_item(db, item.source_pool_item_id)
        _write_log(
            db,
            table_name=item.table_name,
            record_id=item.record_id,
            actor=None,
            action="expire_recover",
            new_fields={"item_id": item.id, "reason": "rework_expired"},
        )

    db.commit()
    return {
        "expired_tasks": len(expired_tasks),
        "recovered": recovered,
        "resubmitted": resubmitted,
        "completed_tasks": completed_tasks,
        "cancelled_tasks": cancelled_tasks,
        "released_rework": released_rework,
    }


def get_my_rework(db: Session, user: User) -> dict[str, Any]:
    """当前标注员的待返工清单：本人未释放（仍为 rejected）的驳回条目。

    review_comment 取最新一条 rejected 提交单的复核意见；
    deadline_at = rejected_at + REWORK_DAYS，expired 与清扫判定同口径（严格小于）。
    """
    rows = (
        db.query(AnnotationTaskItem)
        .join(AnnotationTask, AnnotationTask.id == AnnotationTaskItem.task_id)
        .filter(
            AnnotationTask.claimed_by == user.id,
            AnnotationTaskItem.status == "rejected",
        )
        .order_by(AnnotationTaskItem.id.desc())
        .all()
    )
    rework_days = timedelta(days=get_annotation_config().REWORK_DAYS)
    now_utc = _utcnow()
    items: list[dict[str, Any]] = []
    for item in rows:
        latest_rejected = (
            db.query(AnnotationSubmission)
            .filter(
                AnnotationSubmission.item_id == item.id,
                AnnotationSubmission.status == "rejected",
            )
            .order_by(AnnotationSubmission.id.desc())
            .first()
        )
        deadline = item.rejected_at + rework_days if item.rejected_at else None
        items.append(
            {
                "item_id": item.id,
                "table_name": item.table_name,
                "record_id": item.record_id,
                "review_comment": latest_rejected.review_comment if latest_rejected else None,
                "rejected_at": item.rejected_at.isoformat() if item.rejected_at else None,
                "deadline_at": deadline.isoformat() if deadline else None,
                "expired": bool(deadline is not None and deadline < now_utc),
            }
        )
    return {"count": len(items), "items": items}


def get_my_task(db: Session, user: User) -> dict[str, Any]:
    """当前标注员的进行中任务概览（open/in_progress 取最新一个）；无则 task=null。"""
    task = (
        db.query(AnnotationTask)
        .filter(
            AnnotationTask.claimed_by == user.id,
            AnnotationTask.status.in_(_ACTIVE_TASK_STATUSES),
        )
        .order_by(AnnotationTask.id.desc())
        .first()
    )
    if task is None:
        return {"task": None}

    items = (
        db.query(AnnotationTaskItem)
        .filter(AnnotationTaskItem.task_id == task.id)
        .order_by(AnnotationTaskItem.id)
        .all()
    )
    table_name: str | None = items[0].table_name if items else None
    if table_name is None and task.pool_id is not None:
        pool = db.get(AnnotationPool, task.pool_id)
        table_name = pool.table_name if pool is not None else None

    counts = {"drafted": 0, "submitted": 0, "rejected": 0}
    for it in items:
        if it.status in counts:
            counts[it.status] += 1

    return {
        "task": {
            "task_id": task.id,
            "table_name": table_name,
            "status": task.status,
            "deadline_at": task.deadline_at.isoformat() if task.deadline_at else None,
            "total": len(items),
            **counts,
        }
    }


# ---------------------------------------------------------------------------
# 管理员复核（plan todo #8）：复核队列 + 逐条批准/驳回/过期处理
# ---------------------------------------------------------------------------


def _core_current_values(db: Session, table_name: str, record_id: int) -> tuple[dict[str, Any], bool]:
    """读核心记录全部可编辑字段现值；核心行缺失时返回 ({}, True) 交由调用方打标。"""
    model = _TABLE_MAP.get(table_name)
    core = None if model is None else db.query(model).filter(model.id == record_id).first()
    if core is None:
        return {}, True
    values = {field: getattr(core, field) for field in _EDITABLE_FIELDS.get(table_name, [])}
    return values, False


def review_queue(db: Session, status: str = "pending") -> list[dict[str, Any]]:
    """按任务分组的复核队列：只含 submission.status==status（默认 pending，可切 expired）。

    组内条目按 submission id 升序；submitted_at 取组内最早值；
    current_values 与 proposed_fields 并排展示供管理员对照基准漂移。
    """
    rows = (
        db.query(AnnotationSubmission, AnnotationTaskItem, AnnotationTask)
        .join(AnnotationTaskItem, AnnotationTaskItem.id == AnnotationSubmission.item_id)
        .join(AnnotationTask, AnnotationTask.id == AnnotationTaskItem.task_id)
        .filter(AnnotationSubmission.status == status)
        .order_by(AnnotationSubmission.id)
        .all()
    )
    groups: dict[int, dict[str, Any]] = {}
    for submission, item, task in rows:
        group = groups.get(task.id)
        if group is None:
            group = {
                "task_id": task.id,
                "annotator_username": submission.username,
                "table_name": item.table_name,
                "count": 0,
                "items": [],
                "_earliest_submitted_at": None,
            }
            groups[task.id] = group
        current_values, core_missing = _core_current_values(db, item.table_name, item.record_id)
        entry: dict[str, Any] = {
            "submission_id": submission.id,
            "item_id": item.id,
            "record_id": item.record_id,
            "current_values": current_values,
            "proposed_fields": submission.proposed_fields,
            "base_updated_at": submission.base_updated_at.isoformat()
            if submission.base_updated_at
            else None,
        }
        if core_missing:
            entry["core_missing"] = True
        group["items"].append(entry)
        group["count"] += 1
        submitted_at = item.submitted_at
        if submitted_at is not None and (
            group["_earliest_submitted_at"] is None or submitted_at < group["_earliest_submitted_at"]
        ):
            group["_earliest_submitted_at"] = submitted_at

    result: list[dict[str, Any]] = []
    for task_id in sorted(groups):
        group = groups[task_id]
        earliest = group.pop("_earliest_submitted_at")
        group["submitted_at"] = earliest.isoformat() if earliest else None
        result.append(group)
    return result


def _load_reviewable_submission(
    db: Session, submission_id: int
) -> tuple[AnnotationSubmission, AnnotationTaskItem]:
    """取提交单并校验处于待复核态；缺失 404、非 pending 由路由映射 409。"""
    submission = db.get(AnnotationSubmission, submission_id)
    if submission is None:
        raise AnnotationNotFoundError("提交单不存在")
    if submission.status != "pending":
        raise ValueError(f"该提交单状态为 {submission.status}，不可复核")
    item = db.get(AnnotationTaskItem, submission.item_id)
    if item is None:
        raise AnnotationNotFoundError("条目不存在")
    return submission, item


def approve_submission(db: Session, reviewer: User, submission_id: int) -> dict[str, Any]:
    """逐条批准：把 proposed_fields 经 update_record 落入核心表。

    - 空差异快速通道：仅落 approved 状态与审计，绝不触核心表；
    - 真实差异：复用 admin 直改唯一写入口 AdminQueryRepository.update_record
      （白名单、abstract 清洗、crawl_status 自动晋升同源；内部乐观锁 +
      commit），故每条目的核心写入天然独立成事务——单条 base 冲突转
      expired（条目进返工箱）时绝不牵连其他条目。
    返回 {"submission_id", "item_id", "record_id", "status"}，
    status ∈ {"approved", "expired"}；expired 不抛错，由响应体标记。
    """
    submission, item = _load_reviewable_submission(db, submission_id)
    now_utc = _utcnow()

    if not submission.proposed_fields:
        submission.status = "approved"
        submission.reviewed_at = now_utc
        submission.reviewer_id = reviewer.id
        item.status = "approved"
        _write_log(
            db,
            table_name=item.table_name,
            record_id=item.record_id,
            actor=reviewer,
            action="approve",
            old_fields={},
            new_fields={},
            submission_id=submission.id,
        )
        db.commit()
        return {
            "submission_id": submission.id,
            "item_id": item.id,
            "record_id": item.record_id,
            "status": "approved",
        }

    model = _TABLE_MAP.get(item.table_name)
    core = None if model is None else db.query(model).filter(model.id == item.record_id).first()
    if core is None:
        raise AnnotationNotFoundError("核心记录不存在")

    # 应用前快照：审计的 old_fields 必须是落库前的现值。
    old_fields = {field: getattr(core, field) for field in submission.proposed_fields}

    try:
        AdminQueryRepository(db).update_record(
            item.table_name,
            item.record_id,
            submission.proposed_fields,
            updated_at=submission.base_updated_at.isoformat(),
        )
    except StaleRecordError:
        # 基准冲突：提交单转 expired 归档，条目进返工箱等标注员重做。
        submission.status = "expired"
        submission.reviewed_at = now_utc
        submission.reviewer_id = reviewer.id
        item.status = "rejected"
        item.rejected_at = now_utc
        _write_log(
            db,
            table_name=item.table_name,
            record_id=item.record_id,
            actor=reviewer,
            action="expire",
            new_fields={"reason": "base_conflict"},
            submission_id=submission.id,
        )
        db.commit()
        return {
            "submission_id": submission.id,
            "item_id": item.id,
            "record_id": item.record_id,
            "status": "expired",
        }

    submission.status = "approved"
    submission.reviewed_at = now_utc
    submission.reviewer_id = reviewer.id
    item.status = "approved"
    _write_log(
        db,
        table_name=item.table_name,
        record_id=item.record_id,
        actor=reviewer,
        action="approve",
        old_fields=old_fields,
        new_fields=submission.proposed_fields,
        submission_id=submission.id,
    )
    db.commit()
    return {
        "submission_id": submission.id,
        "item_id": item.id,
        "record_id": item.record_id,
        "status": "approved",
    }


def reject_submission(db: Session, reviewer: User, submission_id: int, comment: str) -> dict[str, Any]:
    """逐条驳回：意见落提交单，条目带 rejected_at 进返工箱。"""
    if not (comment or "").strip():
        raise AnnotationFieldValidationError("驳回必须填写评论")

    submission, item = _load_reviewable_submission(db, submission_id)
    now_utc = _utcnow()
    submission.status = "rejected"
    submission.review_comment = comment
    submission.reviewed_at = now_utc
    submission.reviewer_id = reviewer.id
    item.status = "rejected"
    item.rejected_at = now_utc
    _write_log(
        db,
        table_name=item.table_name,
        record_id=item.record_id,
        actor=reviewer,
        action="reject",
        new_fields={"comment": comment},
        submission_id=submission.id,
    )
    db.commit()
    return {"submission_id": submission.id, "item_id": item.id, "status": "rejected"}


# ---------------------------------------------------------------------------
# 审计日志检索与一键回滚（plan todo #9）：history append-only，回滚只追加新行
# ---------------------------------------------------------------------------


def query_logs(
    db: Session,
    *,
    table_name: str | None = None,
    record_id: int | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页检索审计日志：过滤条件 AND 组合，created_at 区间含两端，按 id 倒序。

    纯只读；分页参数非法（page<1 或 page_size 越出 1..100）抛 ValueError，
    由路由映射 400。T8 的 approve/reject/expire 日志无需任何改造即天然可查。
    """
    if page < 1:
        raise ValueError("page 必须 >= 1")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size 必须在 1..100 之间")

    predicates = []
    if table_name:
        predicates.append(AnnotationLog.table_name == table_name)
    if record_id is not None:
        predicates.append(AnnotationLog.record_id == record_id)
    if actor_id is not None:
        predicates.append(AnnotationLog.actor_id == actor_id)
    if action:
        predicates.append(AnnotationLog.action == action)
    if date_from is not None:
        predicates.append(AnnotationLog.created_at >= date_from)
    if date_to is not None:
        predicates.append(AnnotationLog.created_at <= date_to)

    stmt = select(AnnotationLog)
    if predicates:
        stmt = stmt.where(*predicates)

    total = _count(db, stmt)
    rows = (
        db.execute(
            stmt.order_by(AnnotationLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    items = [
        {
            "id": log.id,
            "table_name": log.table_name,
            "record_id": log.record_id,
            "actor_id": log.actor_id,
            "username": log.username,
            "action": log.action,
            "old_fields": log.old_fields,
            "new_fields": log.new_fields,
            "submission_id": log.submission_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in rows
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def rollback_log(db: Session, reviewer: User, log_id: int) -> dict[str, Any]:
    """一键回滚：把源日志的 old_fields 经 update_record 反向写回核心表。

    - 历史追加不改：源日志原样保留；回滚动作另记一条 action='rollback' 的
      **新**日志（old=回滚前现值，new=被恢复旧值），绝不 delete/update 任何行；
    - 乐观锁与审批同源（approve_submission）：以读取时的核心行 updated_at 为
      基准传入 update_record，期间被人改过即 StaleRecordError ->
      ValueError（路由映射 409），核心表保持不动、不留任何审计行。
    """
    source = db.get(AnnotationLog, log_id)
    if source is None:
        raise AnnotationNotFoundError("日志不存在")

    restore_fields = dict(source.old_fields) if source.old_fields else {}
    if not restore_fields:
        raise AnnotationFieldValidationError("该日志不含可回滚的字段变更")

    model = _TABLE_MAP.get(source.table_name)
    core = (
        None if model is None else db.query(model).filter(model.id == source.record_id).first()
    )
    if core is None:
        raise AnnotationNotFoundError("核心记录不存在")

    # 应用前快照：新审计行的 old_fields 必须是回滚前的现值；
    # 锁基准取当前 updated_at（与审批同语义）。
    before_values = {field: getattr(core, field) for field in restore_fields}
    lock_token = core.updated_at.isoformat() if core.updated_at is not None else None

    try:
        AdminQueryRepository(db).update_record(
            source.table_name, source.record_id, restore_fields, lock_token
        )
    except StaleRecordError:
        raise ValueError("记录已被他人修改，无法回滚，请刷新后重试") from None

    _write_log(
        db,
        table_name=source.table_name,
        record_id=source.record_id,
        actor=reviewer,
        action="rollback",
        old_fields=before_values,
        new_fields=restore_fields,
        submission_id=source.submission_id,
    )
    db.commit()

    entry = (
        db.query(AnnotationLog)
        .filter(
            AnnotationLog.action == "rollback",
            AnnotationLog.table_name == source.table_name,
            AnnotationLog.record_id == source.record_id,
        )
        .order_by(AnnotationLog.id.desc())
        .first()
    )
    return {
        "log_id": entry.id if entry is not None else None,
        "record_id": source.record_id,
        "table_name": source.table_name,
        "restored_fields": sorted(restore_fields),
    }
