"""标注池创建与管理（plan todo #4）：preview 零写入 / 三类排除快照 / PATCH / 403。

Why not ``from main import app``：本机无 PostgreSQL，main.py 模块顶层迁移直连 PG
（见 tests/utils.py docstring）。故按既有约定把真实 annotation_admin 路由挂载到
裸 FastAPI 宿主，仅覆盖 get_db；require_admin 走真实依赖链（真实 JWT + DB 用户）。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.utils import auth_header, make_user

TS = datetime(2026, 1, 15, 8, 0, 0, tzinfo=timezone.utc)


# --- 基建 -----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _annotation_enabled(monkeypatch):
    """镜像 test_annotation_gate：环境变量直读根 Settings，清空其缓存放行真实总闸。"""
    monkeypatch.setenv("ANNOTATION_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db():
    from tests.utils import make_db

    with make_db() as session:
        yield session


@pytest.fixture()
def client(db):
    from app.core.database import get_db
    from app.routers.annotation_admin import router as annotation_admin_router

    app = FastAPI()
    app.include_router(annotation_admin_router)
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def admin(db):
    from tests.utils import make_user

    return make_user(db, "pool-admin", role="admin")


def _seed_lit(db, n=6):
    """Seed n lit records (ids autoincrement) and return their ids."""
    from app.models import LitMetadata

    ids = []
    for i in range(1, n + 1):
        row = LitMetadata(
            file_uuid=f"u{i}",
            original_name=f"a{i}.pdf",
            storage_path=f"lit/u{i}/a{i}.pdf",
            cleaned_title=f"针灸研究{i}",
            title=f"针灸治疗不孕症研究{i}",
            authors=["张三"],
            keywords=["中医"],
            source_site="cnki",
            journal="中医杂志",
            pub_year="2024",
            matched_title=f"针灸研究{i}",
            crawl_status="success",
            created_at=TS,
            updated_at=TS,
        )
        db.add(row)
    db.commit()
    ids = [r.id for r in db.query(LitMetadata).order_by(LitMetadata.id).all()]
    assert len(ids) == n
    return ids


def _occupy_in_other_active_pool(db, record_id):
    """排除类 (a)：记录已在另一个 active 池中。"""
    from app.models import AnnotationPool, AnnotationPoolItem

    pool = AnnotationPool(table_name="lit", filter_json={}, status="active")
    db.add(pool)
    db.flush()
    db.add(
        AnnotationPoolItem(
            pool_id=pool.id, table_name="lit", record_id=record_id, status="available"
        )
    )
    db.commit()


def _occupy_in_running_task(db, record_id):
    """排除类 (b)：记录挂在 open/in_progress 任务上。"""
    from app.models import AnnotationTask, AnnotationTaskItem

    task = AnnotationTask(status="in_progress")
    db.add(task)
    db.flush()
    db.add(
        AnnotationTaskItem(
            task_id=task.id, table_name="lit", record_id=record_id, status="pending"
        )
    )
    db.commit()


def _occupy_approved_ever(db, record_id):
    """排除类 (c)：记录曾有 approved 的 task_item（任务已完结也算占用）。"""
    from app.models import AnnotationTask, AnnotationTaskItem

    task = AnnotationTask(status="completed")
    db.add(task)
    db.flush()
    db.add(
        AnnotationTaskItem(
            task_id=task.id, table_name="lit", record_id=record_id, status="approved"
        )
    )
    db.commit()


def _table_counts(db):
    from app.models import AnnotationLog, AnnotationPool, AnnotationPoolItem

    def _count(model):
        return db.execute(sa.select(sa.func.count()).select_from(model)).scalar()

    return {
        "pools": _count(AnnotationPool),
        "pool_items": _count(AnnotationPoolItem),
        "logs": _count(AnnotationLog),
    }


PREVIEW_BODY = {"table_name": "lit", "q": "针灸"}


# --- (a) preview 只读且计数正确 -------------------------------------------


def test_preview_counts_and_writes_zero_rows(client, db, admin):
    ids = _seed_lit(db)
    _occupy_in_other_active_pool(db, ids[0])

    before = _table_counts(db)

    resp = client.post(
        "/api/annotation/admin/pools/preview",
        json=PREVIEW_BODY,
        headers=auth_header(admin),
    )

    assert resp.status_code == 200
    body = resp.json()
    # 6 条命中搜索词，其中 1 条已被 active 池占用 -> eligible 5
    assert body["total_matched"] == 6
    assert body["eligible"] == 5

    after = _table_counts(db)
    assert after == before == {"pools": 1, "pool_items": 1, "logs": 0}


def test_preview_applies_crawl_status_filter(client, db, admin):
    from app.models import LitMetadata

    ids = _seed_lit(db, n=2)
    # Core 层 update：绕开 ORM onupdate 的 text("NOW()")（SQLite 无此函数）
    db.execute(
        sa.update(LitMetadata)
        .where(LitMetadata.id == ids[0])
        .values(crawl_status="failed", updated_at=TS)
    )
    db.commit()

    resp = client.post(
        "/api/annotation/admin/pools/preview",
        json={"table_name": "lit", "crawl_status": "failed"},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200
    assert resp.json() == {"total_matched": 1, "eligible": 1}


# --- (b) create 仅快照 eligible 记录，shortfall 信息字段 -------------------


def test_create_snapshots_only_eligible_records(client, db, admin):
    ids = _seed_lit(db)  # [1..6]
    _occupy_in_other_active_pool(db, ids[0])      # 排除 (a)
    _occupy_in_running_task(db, ids[1])           # 排除 (b)
    _occupy_approved_ever(db, ids[2])             # 排除 (c)

    resp = client.post(
        "/api/annotation/admin/pools",
        json={**PREVIEW_BODY, "deadline_days": 7},
        headers=auth_header(admin),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["pool_id"] > 0
    assert body["total"] == 3
    assert body["deadline_days"] == 7
    assert body["status"] == "active"
    assert body["priority"] == 0
    # 3 条被排除 -> shortfall==3 作为信息字段随响应返回
    assert body["shortfall"] == 3

    from app.models import AnnotationPool, AnnotationPoolItem

    items = (
        db.query(AnnotationPoolItem)
        .filter(AnnotationPoolItem.pool_id == body["pool_id"])
        .order_by(AnnotationPoolItem.record_id)
        .all()
    )
    assert [it.record_id for it in items] == sorted(ids[3:])
    assert all(it.status == "available" for it in items)
    assert all(it.table_name == "lit" for it in items)

    pool = db.get(AnnotationPool, body["pool_id"])
    assert pool.status == "active"
    # filter_json 存档筛选字典（q/crawl_status/year_min/year_max），table_name 落在专列上
    assert pool.filter_json == {"q": "针灸", "crawl_status": None, "year_min": None, "year_max": None}
    assert pool.created_by == admin.id


def test_list_pools_reports_total_and_remaining(client, db, admin):
    ids = _seed_lit(db, n=4)
    _occupy_in_other_active_pool(db, ids[0])

    created = client.post(
        "/api/annotation/admin/pools",
        json={"table_name": "lit"},
        headers=auth_header(admin),
    ).json()
    assert created["total"] == 3

    resp = client.get("/api/annotation/admin/pools", headers=auth_header(admin))
    assert resp.status_code == 200
    pools = resp.json()
    # 种子里占用记录的 active 池也在列表中，按 id 取本测试创建的池
    entry = next(p for p in pools if p["id"] == created["pool_id"])
    assert entry["table_name"] == "lit"
    assert entry["status"] == "active"
    assert entry["priority"] == 0
    assert entry["deadline_days"] is None
    assert entry["total_items"] == 3
    assert entry["remaining_items"] == 3
    assert entry["created_at"]

    # available 减少 1 后 remaining_items 同步为 2
    from app.models import AnnotationPoolItem

    item = (
        db.query(AnnotationPoolItem)
        .filter(AnnotationPoolItem.pool_id == created["pool_id"])
        .first()
    )
    item.status = "assigned"
    db.commit()
    pools = client.get(
        "/api/annotation/admin/pools", headers=auth_header(admin)
    ).json()
    entry = next(p for p in pools if p["id"] == created["pool_id"])
    assert entry["remaining_items"] == 2
    assert entry["total_items"] == 3


# --- (c) PATCH priority / status -------------------------------------------


def test_patch_priority_then_pause_bogus_and_unknown(client, db, admin):
    ids = _seed_lit(db, n=1)
    created = client.post(
        "/api/annotation/admin/pools",
        json={"table_name": "lit", "q": "针灸"},
        headers=auth_header(admin),
    ).json()
    pool_id = created["pool_id"]

    resp = client.patch(
        f"/api/annotation/admin/pools/{pool_id}",
        json={"priority": 5},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["priority"] == 5

    resp = client.patch(
        f"/api/annotation/admin/pools/{pool_id}",
        json={"status": "paused"},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"

    resp = client.patch(
        f"/api/annotation/admin/pools/{pool_id}",
        json={"status": "bogus"},
        headers=auth_header(admin),
    )
    assert resp.status_code == 400

    resp = client.patch(
        "/api/annotation/admin/pools/99999",
        json={"priority": 1},
        headers=auth_header(admin),
    )
    assert resp.status_code == 404


# --- (d) 空候选集 -> 400 且零残留行 ----------------------------------------


def test_create_empty_candidates_rejected_without_rows(client, db, admin):
    _seed_lit(db, n=2)

    resp = client.post(
        "/api/annotation/admin/pools",
        json={"table_name": "lit", "q": "不存在的检索词zzz"},
        headers=auth_header(admin),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]
    assert _table_counts(db) == {"pools": 0, "pool_items": 0, "logs": 0}


def test_create_unknown_table_rejected(client, db, admin):
    _seed_lit(db, n=1)
    resp = client.post(
        "/api/annotation/admin/pools",
        json={"table_name": "hacker_table"},
        headers=auth_header(admin),
    )
    assert resp.status_code == 400
    assert _table_counts(db) == {"pools": 0, "pool_items": 0, "logs": 0}


# --- (e) 非 admin JWT -> 403（真实 require_admin 链） -----------------------


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/api/annotation/admin/pools/preview", {"table_name": "lit"}),
        ("post", "/api/annotation/admin/pools", {"table_name": "lit"}),
        ("get", "/api/annotation/admin/pools", None),
        ("patch", "/api/annotation/admin/pools/1", {"priority": 1}),
    ],
)
def test_non_admin_gets_403_on_every_endpoint(client, db, method, path, body):
    normal = make_user(db, "plain-user", role="normal")

    kwargs: dict = {"headers": auth_header(normal)}
    if body is not None:
        kwargs["json"] = body
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 403


def test_missing_token_gets_401(client, db):
    resp = client.post("/api/annotation/admin/pools", json={"table_name": "lit"})
    assert resp.status_code in (401, 403)


# --- (f) 审计日志 -----------------------------------------------------------


def test_create_writes_audit_log_with_username_snapshot(client, db, admin):
    ids = _seed_lit(db, n=3)
    created = client.post(
        "/api/annotation/admin/pools",
        json={"table_name": "lit", "q": "针灸"},
        headers=auth_header(admin),
    ).json()

    from app.models import AnnotationLog

    logs = db.query(AnnotationLog).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.action == "create_pool"
    assert log.actor_id == admin.id
    assert log.username == admin.username  # username 快照，用户删除后审计仍可读
    assert log.record_id == 0  # 池级事件约定 record_id=0
    assert log.table_name == "lit"
    assert log.new_fields == {"pool_id": created["pool_id"], "count": len(ids)}
    assert log.old_fields is None
