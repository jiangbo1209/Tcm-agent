"""惰性清扫与标注员自助查询（plan todo #7）：run_lazy_sweep / my/rework / my/task。

沿用 test_annotation_items 约定：本机无 PostgreSQL，把真实 annotation 路由挂载到
裸 FastAPI 宿主，仅覆盖 get_db；require_annotator 走真实依赖链（JWT + DB 用户）。

清扫类断言一律直接调用服务函数并注入 now（确定性）；路由级 lazy_sweep_dep
只做冒烟验证（用例 h 用行为证据证明依赖确实执行过）。

DISCOVERED WORK：前端 T13/T14 已在消费 GET /my/task（原计划遗漏该端点），
此处一并补齐，响应形状对齐 AnnotationWorkbench.vue 的 ``res.data.task`` 契约。

核心记录 lit_metadata 的 server_default 是 text("NOW()")，SQLite 无此函数，
播种一律显式给 updated_at（见 test_annotation_pools / test_annotation_items 先例）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_annotation_config
from app.services import annotation_service
from tests.utils import auth_header, make_user

CORE_TS = datetime(2026, 1, 15, 8, 0, 0)

ZERO_COUNTERS = {
    "expired_tasks": 0,
    "recovered": 0,
    "resubmitted": 0,
    "completed_tasks": 0,
    "cancelled_tasks": 0,
    "released_rework": 0,
}


def _naive_utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- 基建 -----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _annotation_enabled(monkeypatch):
    """镜像 test_annotation_claim：清空 lru_cache 后改写缓存实例放行真实总闸。"""
    monkeypatch.delenv("ANNOTATION_ENABLED", raising=False)
    get_annotation_config.cache_clear()
    get_annotation_config().ENABLED = True
    yield
    get_annotation_config.cache_clear()


@pytest.fixture()
def db():
    from tests.utils import make_db

    with make_db() as session:
        yield session


@pytest.fixture()
def client(db):
    from app.core.database import get_db
    from app.routers.annotation import router as annotation_router

    app = FastAPI()
    app.include_router(annotation_router)
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _annotator(db, name: str):
    return make_user(db, name, role="annotator")


def _seed_core_lit(db, n: int) -> list[int]:
    """播种 n 条核心 lit 记录（显式时间戳规避 SQLite NOW() 缺失）。"""
    from app.models import LitMetadata

    for i in range(1, n + 1):
        db.add(
            LitMetadata(
                file_uuid=f"t7-u{i}",
                original_name=f"a{i}.pdf",
                storage_path=f"lit/t7-u{i}/a{i}.pdf",
                cleaned_title=f"针灸研究{i}",
                title=f"针灸治疗不孕症研究{i}",
                authors=["张三"],
                keywords=["中医"],
                source_site="cnki",
                journal="中医杂志",
                pub_year="2024",
                matched_title=f"针灸研究{i}",
                crawl_status="success",
                created_at=CORE_TS,
                updated_at=CORE_TS,
            )
        )
    db.commit()
    ids = [r.id for r in db.query(LitMetadata).order_by(LitMetadata.id).all()]
    assert len(ids) == n
    return ids


def _seed_pool_with_records(db, record_ids: list[int]):
    from app.models import AnnotationPool, AnnotationPoolItem

    pool = AnnotationPool(table_name="lit", filter_json={}, status="active", priority=0)
    db.add(pool)
    db.flush()
    db.add_all(
        [
            AnnotationPoolItem(
                pool_id=pool.id,
                table_name="lit",
                record_id=record_id,
                status="available",
            )
            for record_id in record_ids
        ]
    )
    db.commit()
    return pool


def _claim_task(client, annotator) -> int:
    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))
    assert resp.status_code == 200
    return resp.json()["task_id"]


def _task_items(db, task_id: int):
    from app.models import AnnotationTaskItem

    return (
        db.query(AnnotationTaskItem)
        .filter(AnnotationTaskItem.task_id == task_id)
        .order_by(AnnotationTaskItem.id)
        .all()
    )


def _pool_item_by_source(db, item):
    from app.models import AnnotationPoolItem

    return db.get(AnnotationPoolItem, item.source_pool_item_id)


def _draft(client, annotator, item_id: int, proposed_fields: dict):
    return client.put(
        f"/api/annotation/items/{item_id}/draft",
        json={"proposed_fields": proposed_fields},
        headers=auth_header(annotator),
    )


def _submissions_for(db, item_id: int):
    from app.models import AnnotationSubmission

    return (
        db.query(AnnotationSubmission)
        .filter(AnnotationSubmission.item_id == item_id)
        .order_by(AnnotationSubmission.id)
        .all()
    )


def _force_reject(db, item, annotator, comment: str, rejected_at: datetime) -> None:
    """模拟 T8 驳回现场：item rejected + 一条带复核意见的 rejected submission。"""
    from app.models import AnnotationSubmission

    item.status = "rejected"
    item.rejected_at = rejected_at
    db.add(
        AnnotationSubmission(
            item_id=item.id,
            annotator_id=annotator.id,
            username=annotator.username,
            proposed_fields={"title": "被驳回的旧稿"},
            base_updated_at=CORE_TS,
            status="rejected",
            review_comment=comment,
        )
    )
    db.commit()


def _expire_logs(db):
    from app.models import AnnotationLog

    return (
        db.query(AnnotationLog)
        .filter(AnnotationLog.action == "expire_recover")
        .order_by(AnnotationLog.id)
        .all()
    )


# --- (a) 纯 pending 超期：条目 recovered、池位回收、任务 cancelled ----------


def test_pure_pending_expiry(client, db):
    from app.models import AnnotationTask

    annotator = _annotator(db, "sw-pure")
    _seed_pool_with_records(db, _seed_core_lit(db, 3))
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)
    assert len(items) == 3

    base = _naive_utcnow()
    result = annotation_service.run_lazy_sweep(db, now=base + timedelta(days=8))

    assert result["recovered"] == 3
    assert result["cancelled_tasks"] == 1
    assert result["expired_tasks"] == 1

    for it in items:
        db.refresh(it)
        assert it.status == "recovered"
        assert _pool_item_by_source(db, it).status == "available", "池位必须回收为可抽取"

    assert db.get(AnnotationTask, task_id).status == "cancelled"

    logs = _expire_logs(db)
    assert len(logs) == 1, "每个超期任务只落一行审计日志"
    log = logs[0]
    assert log.record_id == 0
    assert log.username == "system"
    assert log.table_name == "lit"
    assert log.new_fields == {"task_id": task_id, "recovered": 3, "resubmitted": 0}


# --- (b) 部分产出超期：drafted 转 submitted 进复核，pending 回收，任务完成 ----


def test_partial_output_expiry(client, db):
    from app.models import AnnotationSubmission, AnnotationTask

    annotator = _annotator(db, "sw-mix")
    _seed_pool_with_records(db, _seed_core_lit(db, 3))
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)

    assert _draft(client, annotator, items[0].id, {"title": "草稿一"}).status_code == 200
    assert _draft(client, annotator, items[1].id, {}).status_code == 200

    base = _naive_utcnow()
    sweep_now = base + timedelta(days=8)
    result = annotation_service.run_lazy_sweep(db, now=sweep_now)

    assert result["recovered"] == 1
    assert result["resubmitted"] == 2
    assert result["completed_tasks"] == 1
    assert result["cancelled_tasks"] == 0

    # drafted 对：submission draft -> pending，条目 -> submitted（带提交时刻）
    for it in items[:2]:
        db.refresh(it)
        assert it.status == "submitted"
        assert it.submitted_at == sweep_now
        subs = _submissions_for(db, it.id)
        assert len(subs) == 1
        assert subs[0].status == "pending"

    # pending 条目：recovered + 池位回收；drafted 对的池位保持占用
    db.refresh(items[2])
    assert items[2].status == "recovered"
    assert _pool_item_by_source(db, items[2]).status == "available"
    for it in items[:2]:
        assert _pool_item_by_source(db, it).status == "assigned", "已进复核的记录不得回流池中"

    assert db.get(AnnotationTask, task_id).status == "completed"

    logs = _expire_logs(db)
    assert len(logs) == 1
    assert logs[0].new_fields == {"task_id": task_id, "recovered": 1, "resubmitted": 2}

    assert db.query(AnnotationSubmission).filter_by(status="draft").count() == 0


# --- (c) 未超期：零变更 ------------------------------------------------------


def test_not_expired_no_mutations(client, db):
    from app.models import AnnotationTask

    annotator = _annotator(db, "sw-fresh")
    _seed_pool_with_records(db, _seed_core_lit(db, 2))
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)

    base = _naive_utcnow()
    result = annotation_service.run_lazy_sweep(db, now=base + timedelta(days=6))

    assert result == ZERO_COUNTERS, "未到期时所有计数器必须为 0"
    assert db.get(AnnotationTask, task_id).status == "in_progress"
    for it in items:
        db.refresh(it)
        assert it.status == "pending"
        assert _pool_item_by_source(db, it).status == "assigned"
    assert _expire_logs(db) == []


# --- (d) 幂等：同一 now 连跑两次，第二次全零 --------------------------------


def test_sweep_idempotent_second_run_zero(client, db):
    from app.models import AnnotationTask

    annotator = _annotator(db, "sw-idem")
    _seed_pool_with_records(db, _seed_core_lit(db, 2))
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)

    base = _naive_utcnow()
    sweep_now = base + timedelta(days=8)
    first = annotation_service.run_lazy_sweep(db, now=sweep_now)
    assert first["recovered"] == 2, "首跑必须有真实变更作为幂等对照基线"

    second = annotation_service.run_lazy_sweep(db, now=sweep_now)
    assert second == ZERO_COUNTERS, "第二跑计数器必须全零"

    # 状态在两跑之间保持稳定（counter diff 之外的状态级复核）
    assert db.get(AnnotationTask, task_id).status == "cancelled"
    for it in items:
        db.refresh(it)
        assert it.status == "recovered"
        assert _pool_item_by_source(db, it).status == "available"
    assert len(_expire_logs(db)) == 1, "不得重复落日志"


# --- (e) 返工过期释放：过窗 rejected 释放回池，未过窗不动 --------------------


def test_rework_release_on_expiry(client, db):
    from app.models import AnnotationTaskItem

    annotator = _annotator(db, "sw-rework")
    _seed_pool_with_records(db, _seed_core_lit(db, 3))
    _claim_task(client, annotator)
    items = _task_items(db, _active_task_id(db, annotator))

    base = _naive_utcnow()
    _force_reject(db, items[0], annotator, "术语不统一", rejected_at=base - timedelta(days=6))
    _force_reject(db, items[1], annotator, "摘要漏关键信息", rejected_at=base - timedelta(days=1))

    result = annotation_service.run_lazy_sweep(db, now=base)

    assert result["released_rework"] == 1
    assert result["expired_tasks"] == 0, "任务未超期，(a) 分支不得触发"

    db.refresh(items[0])
    assert items[0].status == "recovered"
    assert _pool_item_by_source(db, items[0]).status == "available"

    db.refresh(items[1])
    assert items[1].status == "rejected", "未过返工窗口的驳回条目不得被触碰"

    logs = [log for log in _expire_logs(db) if (log.new_fields or {}).get("reason")]
    assert len(logs) == 1
    assert logs[0].new_fields == {"item_id": items[0].id, "reason": "rework_expired"}
    assert logs[0].table_name == "lit"

    assert db.get(AnnotationTaskItem, items[2].id).status == "pending"


def _active_task_id(db, annotator) -> int:
    from app.models import AnnotationTask

    task = (
        db.query(AnnotationTask)
        .filter(AnnotationTask.claimed_by == annotator.id)
        .order_by(AnnotationTask.id.desc())
        .first()
    )
    assert task is not None
    return task.id


# --- (f) GET /my/rework：只含本人未释放驳回条目 ------------------------------


def test_my_rework_lists_own_unreleased_only(client, db):
    base = _naive_utcnow()
    alice = _annotator(db, "sw-alice")
    bob = _annotator(db, "sw-bob")

    record_ids = _seed_core_lit(db, 6)
    # 单次领取会抽走 min(50, available) 条 —— 每人一个独立小池，保证两人各得一条目
    _seed_pool_with_records(db, record_ids[:3])
    _seed_pool_with_records(db, record_ids[3:])
    task_a = _claim_task(client, alice)
    task_b = _claim_task(client, bob)
    items_a = _task_items(db, task_a)
    items_b = _task_items(db, task_b)

    rejected_at = base - timedelta(days=1)
    _force_reject(db, items_a[0], alice, "标题不规范", rejected_at=rejected_at)
    _force_reject(db, items_b[0], bob, "bob 的驳回", rejected_at=rejected_at)

    resp = client.get("/api/annotation/my/rework", headers=auth_header(alice))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1, "他人驳回条目不得出现"
    entry = body["items"][0]
    assert set(entry.keys()) == {
        "item_id",
        "table_name",
        "record_id",
        "review_comment",
        "rejected_at",
        "deadline_at",
        "expired",
    }
    assert entry["item_id"] == items_a[0].id
    assert entry["table_name"] == "lit"
    assert entry["record_id"] == items_a[0].record_id
    assert entry["review_comment"] == "标题不规范"
    assert entry["rejected_at"] == rejected_at.isoformat()
    assert entry["deadline_at"] == (rejected_at + timedelta(days=5)).isoformat()
    assert entry["expired"] is False

    # 无驳回的用户得到空清单
    carol = make_user(db, "sw-carol", role="annotator")
    empty = client.get("/api/annotation/my/rework", headers=auth_header(carol))
    assert empty.status_code == 200
    assert empty.json() == {"count": 0, "items": []}


def test_my_rework_expired_flag_true_before_sweep(db):
    """直连服务（不经路由 -> 不触发清扫）：过窗条目标记 expired=True。"""
    from app.models import AnnotationPoolItem, AnnotationTask, AnnotationTaskItem

    base = _naive_utcnow()
    alice = _annotator(db, "sw-dave")
    _seed_pool_with_records(db, _seed_core_lit(db, 1))

    # 直接种一条挂在任务上的过窗驳回（绕过领取，聚焦标志位本身）
    pool_item = db.query(AnnotationPoolItem).first()
    task = AnnotationTask(status="in_progress", claimed_by=alice.id)
    db.add(task)
    db.flush()
    item = AnnotationTaskItem(
        task_id=task.id,
        table_name=pool_item.table_name,
        record_id=pool_item.record_id,
        source_pool_item_id=pool_item.id,
        status="rejected",
        rejected_at=base - timedelta(days=9),
    )
    db.add(item)
    db.commit()

    result = annotation_service.get_my_rework(db, alice)
    assert result["count"] == 1
    entry = result["items"][0]
    assert entry["item_id"] == item.id
    assert entry["review_comment"] is None, "缺 rejected submission 时意见应为 None"
    assert entry["expired"] is True
    assert entry["deadline_at"] == (base - timedelta(days=9) + timedelta(days=5)).isoformat()


# --- (g) GET /my/task：活动任务完整形状 / 无任务 null ------------------------


def test_my_task_active_shape_and_null(client, db):
    from app.models import AnnotationTask

    annotator = _annotator(db, "sw-task")
    _seed_pool_with_records(db, _seed_core_lit(db, 3))
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)

    assert _draft(client, annotator, items[0].id, {"title": "x"}).status_code == 200
    items[1].status = "submitted"
    items[1].submitted_at = _naive_utcnow()
    items[2].status = "rejected"
    items[2].rejected_at = _naive_utcnow()
    db.commit()

    resp = client.get("/api/annotation/my/task", headers=auth_header(annotator))
    assert resp.status_code == 200
    task = resp.json()["task"]
    assert task is not None
    assert set(task.keys()) == {
        "task_id",
        "table_name",
        "status",
        "deadline_at",
        "total",
        "count",
        "drafted",
        "submitted",
        "rejected",
    }
    assert task["count"] == task["total"] == 3
    assert task["task_id"] == task_id
    assert task["table_name"] == "lit"
    assert task["status"] == "in_progress"
    assert task["deadline_at"] == db.get(AnnotationTask, task_id).deadline_at.isoformat()
    assert task["total"] == 3
    assert task["drafted"] == 1
    assert task["submitted"] == 1
    assert task["rejected"] == 1

    # 无活动任务的标注员 -> {"task": null}
    outsider = make_user(db, "sw-outsider", role="annotator")
    resp2 = client.get("/api/annotation/my/task", headers=auth_header(outsider))
    assert resp2.status_code == 200
    assert resp2.json() == {"task": None}


# --- (h) 路由级 sweep 依赖冒烟：GET /health 触发清扫且不出错 -----------------


def test_health_triggers_lazy_sweep_dependency(client, db):
    from app.models import AnnotationTask

    annotator = _annotator(db, "sw-dep")
    _seed_pool_with_records(db, _seed_core_lit(db, 1))
    task_id = _claim_task(client, annotator)

    # 把截止时间改到过去：下一次任意请求（/health）经 lazy_sweep_dep 必须恢复它
    task = db.get(AnnotationTask, task_id)
    task.deadline_at = _naive_utcnow() - timedelta(days=1)
    db.commit()

    resp = client.get("/api/annotation/health")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True}

    db.expire_all()
    assert db.get(AnnotationTask, task_id).status == "cancelled", (
        "路由级依赖必须已在请求处理前执行过一次真实清扫"
    )
