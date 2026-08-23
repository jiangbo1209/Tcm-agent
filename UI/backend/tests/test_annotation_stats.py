"""管理端仪表盘聚合与工作量 CSV 导出（plan todo #10）。

沿用 test_annotation_review 约定：本机无 PostgreSQL，main.py 顶层迁移直连 PG，
故把真实 annotation 路由与 annotation_admin 路由同时挂载到裸 FastAPI 宿主，
仅覆盖 get_db；require_annotator / require_admin 走真实依赖链（真实 JWT + DB 用户）。
数据一律经 claim -> draft -> submit -> approve/reject 全流程自然产生。

核心记录（lit_metadata）的 server_default 是 text("NOW()")，SQLite 无此函数，
播种时显式给 created_at/updated_at（test_annotation_pools 先例）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_annotation_config
from tests.utils import auth_header, make_user

CORE_TS = datetime(2026, 1, 15, 8, 0, 0)

CSV_HEADER = "date,username,table_name,record_id,item_status,review_outcome"
STATS_URL = "/api/annotation/admin/stats"
EXPORT_URL = "/api/annotation/admin/export.csv"


def _naive_utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- 基建 -----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _annotation_enabled(monkeypatch):
    """镜像 test_annotation_items：清空 lru_cache 后改写缓存实例放行真实总闸。"""
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
    from app.routers.annotation_admin import router as annotation_admin_router

    app = FastAPI()
    app.include_router(annotation_router)
    app.include_router(annotation_admin_router)
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def admin(db):
    return make_user(db, "t10-admin", role="admin")


# --- 播种辅助（claim→draft→submit→approve/reject 全流程） --------------------


def _seed_core_lit(db, n: int, *, prefix: str = "t10") -> list[int]:
    """播种 n 条核心 lit 记录（显式时间戳规避 SQLite NOW() 缺失）。"""
    from app.models import LitMetadata

    for i in range(1, n + 1):
        db.add(
            LitMetadata(
                file_uuid=f"{prefix}-u{i}",
                original_name=f"a{i}.pdf",
                storage_path=f"lit/{prefix}-u{i}/a{i}.pdf",
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
    # 只返回本批（按唯一前缀）的 id：同一测试多次播种时互不污染
    return [
        r.id
        for r in db.query(LitMetadata)
        .filter(LitMetadata.file_uuid.like(f"{prefix}-%"))
        .order_by(LitMetadata.id)
        .all()
    ]


def _seed_pool_with_records(
    db, record_ids: list[int], *, priority: int = 0, table_name: str = "lit"
):
    from app.models import AnnotationPool, AnnotationPoolItem

    pool = AnnotationPool(
        table_name=table_name, filter_json={}, status="active", priority=priority
    )
    db.add(pool)
    db.flush()
    db.add_all(
        [
            AnnotationPoolItem(
                pool_id=pool.id,
                table_name=table_name,
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


def _draft(client, annotator, item_id: int, proposed_fields: dict | None = None):
    return client.put(
        f"/api/annotation/items/{item_id}/draft",
        json={"proposed_fields": proposed_fields or {}},
        headers=auth_header(annotator),
    )


def _submit_all(client, annotator, task_id: int) -> dict:
    resp = client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))
    assert resp.status_code == 200
    return resp.json()


def _pending_submissions(db, items):
    """按条目顺序取各自的唯一 pending 提交单（claim+draft+submit 的自然产物）。"""
    from app.models import AnnotationSubmission

    subs = []
    for it in items:
        sub = (
            db.query(AnnotationSubmission)
            .filter(AnnotationSubmission.item_id == it.id, AnnotationSubmission.status == "pending")
            .one()
        )
        subs.append(sub)
    return subs


def _approve(client, admin, submission_id: int):
    return client.post(
        f"/api/annotation/admin/review/{submission_id}/approve", headers=auth_header(admin)
    )


def _reject(client, admin, submission_id: int, comment: str):
    return client.post(
        f"/api/annotation/admin/review/{submission_id}/reject",
        json={"comment": comment},
        headers=auth_header(admin),
    )


def _run_batch(
    client,
    db,
    admin,
    *,
    n: int,
    prefix: str,
    outcomes: list[str],
) -> tuple:
    """建池(n 条) -> annotator 领取 -> 全部暂存 -> 提交 -> 按 outcomes 审批。

    outcomes 按条目顺序取 "approved" / "rejected"；返回 (annotator, task_id, items)。
    """
    record_ids = _seed_core_lit(db, n, prefix=prefix)
    _seed_pool_with_records(db, record_ids)
    annotator = make_user(db, f"{prefix}-ann", role="annotator")
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)
    assert len(items) == n
    for it in items:
        assert _draft(client, annotator, it.id).status_code == 200
    _submit_all(client, annotator, task_id)
    subs = _pending_submissions(db, items)
    for sub, outcome in zip(subs, outcomes):
        if outcome == "approved":
            assert _approve(client, admin, sub.id).json()["status"] == "approved"
        else:
            assert _reject(client, admin, sub.id, f"重做{sub.id}").status_code == 200
    db.expire_all()
    return annotator, task_id, items


def _get_stats(client, admin) -> dict:
    resp = client.get(STATS_URL, headers=auth_header(admin))
    assert resp.status_code == 200
    return resp.json()


# --- (a) pools 段：与播种池一致，含余量，priority 降序 ------------------------


def test_stats_pools_match_seeds_with_remaining_counts(client, db, admin):
    high_records = _seed_core_lit(db, 3, prefix="t10a-hi")
    low_records = _seed_core_lit(db, 2, prefix="t10a-lo")
    pool_high = _seed_pool_with_records(db, high_records, priority=5)
    pool_low = _seed_pool_with_records(db, low_records, priority=0)

    annotator = make_user(db, "t10a-ann", role="annotator")
    # resolve_pool 取优先级最高的 active 池 -> 高优先级池被抽干
    _claim_task(client, annotator)

    body = _get_stats(client, admin)

    assert set(body.keys()) == {"pools", "coverage", "users"}
    pools = body["pools"]
    assert set(pools[0].keys()) == {
        "id",
        "table_name",
        "status",
        "priority",
        "total_items",
        "remaining_items",
    }
    assert [p["id"] for p in pools] == [pool_high.id, pool_low.id], "按 priority 降序"
    assert pools[0] == {
        "id": pool_high.id,
        "table_name": "lit",
        "status": "active",
        "priority": 5,
        "total_items": 3,
        "remaining_items": 0,
    }
    assert pools[1] == {
        "id": pool_low.id,
        "table_name": "lit",
        "status": "active",
        "priority": 0,
        "total_items": 2,
        "remaining_items": 2,
    }


# --- (b) coverage：DISTINCT 批准记录数 / 核心表全表计数，空表 0 安全 ----------


def test_coverage_counts_approved_distinct_records(client, db, admin):
    all_records = _seed_core_lit(db, 4, prefix="t10b")
    # 池只装前 2 条；后 2 条保持无标注。批准后 annotated=2 / total=4
    _seed_pool_with_records(db, all_records[:2])
    annotator = make_user(db, "t10b-ann", role="annotator")
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)
    assert len(items) == 2
    assert {it.record_id for it in items} == set(all_records[:2])
    for it in items:
        assert _draft(client, annotator, it.id).status_code == 200
    _submit_all(client, annotator, task_id)
    for sub in _pending_submissions(db, items):
        assert _approve(client, admin, sub.id).json()["status"] == "approved"

    db.expire_all()
    assert {it.status for it in items} == {"approved"}, "前置：两条种子条目均被批准"

    coverage = _get_stats(client, admin)["coverage"]

    assert coverage == {
        "lit": {"annotated": 2, "total": 4},
        "case": {"annotated": 0, "total": 0},
        "guideline": {"annotated": 0, "total": 0},
    }, "lit 表 4 条记录中恰有 2 条存在 approved 条目；case/guideline 空表 0 安全"


# --- (c) users 段：聚合口径 + 零工作量标注员可见 ------------------------------


def test_users_section_aggregates_and_includes_zero_work_annotator(client, db, admin):
    ann_a, task_id_a, _items = _run_batch(
        client,
        db,
        admin,
        n=3,
        prefix="t10c",
        outcomes=["approved", "approved", "rejected"],
    )
    zero_b = make_user(db, "t10c-zero", role="annotator")

    users = _get_stats(client, admin)["users"]

    assert [u["username"] for u in users] == [ann_a.username, zero_b.username], (
        "只含 role='annotator'（admin 不出现），零工作量标注员也在列"
    )

    (row_a, row_b) = users
    assert row_a["user_id"] == ann_a.id
    assert row_a["completed"] == 2
    assert row_a["rejected_rate"] == 0.33, "1/(1+2) 保留两位"
    assert row_a["pending_rework"] == 1
    # F-02：已完成任务的条目被驳回 -> 任务重开，标注员占用活跃槽位直至返工完成
    assert row_a["in_progress"] == 1

    assert row_b == {
        "user_id": zero_b.id,
        "username": zero_b.username,
        "completed": 0,
        "rejected_rate": 0.0,
        "pending_rework": 0,
        "in_progress": 0,
    }

    # 返工完成（redraft + 重提）后任务再次 completed，
    # MAX_PENDING_REWORK=0 不限制返工过用户再领取新任务
    from app.models import AnnotationSubmission, AnnotationTaskItem

    rejected_item = (
        db.query(AnnotationTaskItem)
        .filter(
            AnnotationTaskItem.task_id == task_id_a,
            AnnotationTaskItem.status == "rejected",
        )
        .one()
    )
    redraft = client.put(
        f"/api/annotation/items/{rejected_item.id}/draft",
        json={"proposed_fields": {}},
        headers=auth_header(ann_a),
    )
    assert redraft.status_code == 200
    resubmit = client.post(
        f"/api/annotation/tasks/{task_id_a}/submit", headers=auth_header(ann_a)
    )
    assert resubmit.status_code == 200

    fresh_record = _seed_core_lit(db, 1, prefix="t10c-extra")
    _seed_pool_with_records(db, fresh_record, priority=9)
    assert _claim_task(client, ann_a), "MAX_PENDING_REWORK=0 不限制返工中用户再领取"

    row_a = next(u for u in _get_stats(client, admin)["users"] if u["user_id"] == ann_a.id)
    assert row_a["in_progress"] == 1
    assert row_a["completed"] == 2, "已完成数不受新任务影响"


# --- (d) CSV 导出 happy path：表头精确、行内容、created_at+id 排序 -------------


def test_export_csv_rows_content_and_ordering(client, db, admin):
    ann, _task_id, items = _run_batch(
        client,
        db,
        admin,
        n=3,
        prefix="t10d",
        outcomes=["approved", "rejected", "approved"],
    )

    resp = client.get(EXPORT_URL, headers=auth_header(admin))

    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert resp.headers["content-disposition"] == 'attachment; filename="workload.csv"'

    lines = resp.text.splitlines()
    assert lines[0] == CSV_HEADER, "表头必须逐字符一致"
    rows = [line.split(",") for line in lines[1:]]
    assert len(rows) == 3

    expected_items = sorted(items, key=lambda it: (it.created_at, it.id))
    from app.models import AnnotationSubmission

    latest_sub_status = {}
    for it in items:
        subs = (
            db.query(AnnotationSubmission)
            .filter(AnnotationSubmission.item_id == it.id)
            .order_by(AnnotationSubmission.id)
            .all()
        )
        latest_sub_status[it.id] = subs[-1].status

    for row, it in zip(rows, expected_items):
        date_str, username, table_name, record_id, item_status, review_outcome = row
        assert date_str == it.created_at.date().isoformat()
        assert username == ann.username
        assert table_name == "lit"
        assert int(record_id) == it.record_id
        assert item_status == it.status
        assert review_outcome == latest_sub_status[it.id]
    assert [int(r[3]) for r in rows] == [it.record_id for it in expected_items], (
        "按 created_at 升序再 id 升序"
    )
    statuses = {it.status for it in items}
    assert statuses == {"approved", "rejected"}, "前置：种子确有批准与驳回两种终态"


# --- (e) CSV 过滤：user_id / pool_id / 组合 ----------------------------------


def test_export_csv_filters_user_and_pool(client, db, admin):
    hi_records = _seed_core_lit(db, 2, prefix="t10e-hi")
    lo_records = _seed_core_lit(db, 2, prefix="t10e-lo")
    pool_hi = _seed_pool_with_records(db, hi_records, priority=5)
    pool_lo = _seed_pool_with_records(db, lo_records, priority=0)

    ann_a = make_user(db, "t10e-a", role="annotator")
    ann_b = make_user(db, "t10e-b", role="annotator")
    # 高优先级池先被 A 领走，B 落到低优先级池
    task_a = _claim_task(client, ann_a)
    task_b = _claim_task(client, ann_b)
    for ann, task_id in ((ann_a, task_a), (ann_b, task_b)):
        for it in _task_items(db, task_id):
            assert _draft(client, ann, it.id).status_code == 200
        _submit_all(client, ann, task_id)
    db.expire_all()

    def _export_rows(params: dict | None = None) -> list[list[str]]:
        resp = client.get(EXPORT_URL, params=params or {}, headers=auth_header(admin))
        assert resp.status_code == 200
        lines = resp.text.splitlines()
        assert lines[0] == CSV_HEADER
        return [line.split(",") for line in lines[1:]]

    unfiltered = _export_rows()
    assert len(unfiltered) == 4, "两个任务各 2 条"

    by_user = _export_rows({"user_id": ann_a.id})
    assert {r[1] for r in by_user} == {ann_a.username}, "user_id 过滤只剩该标注员"
    assert {int(r[3]) for r in by_user} == set(hi_records)

    by_pool = _export_rows({"pool_id": pool_lo.id})
    assert {int(r[3]) for r in by_pool} == set(lo_records), "pool_id 过滤只剩该池条目"

    combined = _export_rows({"user_id": ann_b.id, "pool_id": pool_lo.id})
    assert {int(r[3]) for r in combined} == set(lo_records)
    assert {r[1] for r in combined} == {ann_b.username}, "组合过滤取交集"

    cross = _export_rows({"user_id": ann_a.id, "pool_id": pool_lo.id})
    assert cross == [], "A 的条目不在低优先级池 -> 空"

    bad_date = client.get(
        EXPORT_URL, params={"date_from": "not-a-date"}, headers=auth_header(admin)
    )
    assert bad_date.status_code == 400, "非法 ISO 日期 -> 400（与审计日志检索同口径）"


# --- (f) 空数据集导出：仅表头的合法 CSV --------------------------------------


def test_export_csv_empty_dataset_is_header_only(client, db, admin):
    resp = client.get(EXPORT_URL, headers=auth_header(admin))

    assert resp.status_code == 200
    assert resp.text.splitlines() == [CSV_HEADER]


# --- (g) 非管理员一律 403 ----------------------------------------------------


def test_non_admin_forbidden_on_stats_and_export(client, db, admin):
    plain = make_user(db, "t10g-plain", role="normal")

    stats_resp = client.get(STATS_URL, headers=auth_header(plain))
    export_resp = client.get(EXPORT_URL, headers=auth_header(plain))

    assert stats_resp.status_code == 403
    assert export_resp.status_code == 403


# --- (h) 端点先跑惰性清扫：过期任务在统计前被回收 ----------------------------


def test_stats_runs_lazy_sweep_before_aggregating(client, db, admin):
    from app.models import AnnotationPoolItem, AnnotationTask

    record = _seed_core_lit(db, 1, prefix="t10h")
    pool = _seed_pool_with_records(db, record)
    ann = make_user(db, "t10h-ann", role="annotator")
    task_id = _claim_task(client, ann)

    past = _naive_utcnow() - timedelta(days=30)
    db.execute(sa.update(AnnotationTask).where(AnnotationTask.id == task_id).values(deadline_at=past))
    db.commit()

    body = _get_stats(client, admin)

    row = next(u for u in body["users"] if u["user_id"] == ann.id)
    assert row["in_progress"] == 0, "统计前超期任务必须已被惰性清扫回收"

    task = db.get(AnnotationTask, task_id)
    assert task.status == "cancelled", "全 pending 的过期任务清扫后定态为 cancelled"

    remaining = (
        db.query(AnnotationPoolItem)
        .filter(
            AnnotationPoolItem.pool_id == pool.id,
            AnnotationPoolItem.status == "available",
        )
        .count()
    )
    assert remaining == 1, "池位已归还 available"
