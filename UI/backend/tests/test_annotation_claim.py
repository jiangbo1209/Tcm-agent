"""任务领取与代派（plan todo #5）：原子随机抽取 / 单任务约束 / 逐用户代派。

沿用 test_annotation_pools 约定：本机无 PostgreSQL，main.py 顶层迁移直连 PG，
故把真实 annotation + annotation_admin 路由挂载到裸 FastAPI 宿主，仅覆盖
get_db；require_annotator/require_admin 走真实依赖链（真实 JWT + DB 用户）。

抽取的并发安全在 sqlite 上以「rowcount 对账 + 重试一次」路径覆盖：
test_claim_retry_after_contention 用带毒的候选列表制造首次对账失败，
断言重试路径真的被执行（而非静默成功）；PG FOR UPDATE SKIP LOCKED
路径由 skipif 保护的 8 线程并发测试覆盖（无 PG 时本地跳过）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.utils import auth_header, make_user

OLD_TS = datetime(2026, 1, 1, 8, 0, 0)
NEW_TS = datetime(2026, 6, 1, 8, 0, 0)


def _naive_utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- 基建 -----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _annotation_enabled(monkeypatch):
    """镜像 test_annotation_pools：环境变量直读根 Settings，清空其缓存放行真实总闸。"""
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
    from tests.utils import make_user

    return make_user(db, "claim-admin", role="admin")


def _annotator(db, name: str, is_active: bool = True):
    from tests.utils import make_user

    return make_user(db, name, role="annotator", is_active=is_active)


def _seed_pool(
    db,
    *,
    n: int,
    priority: int = 0,
    status: str = "active",
    created_at: datetime = OLD_TS,
    deadline_days: int | None = None,
):
    """直插 pool + n 条 available pool_item（task_items 不做 FK 校验，无需 lit 行）。"""
    from app.models import AnnotationPool, AnnotationPoolItem

    pool = AnnotationPool(
        table_name="lit",
        filter_json={},
        status=status,
        priority=priority,
        deadline_days=deadline_days,
        created_at=created_at,
    )
    db.add(pool)
    db.flush()
    db.add_all(
        [
            AnnotationPoolItem(
                pool_id=pool.id,
                table_name="lit",
                record_id=i,
                status="available",
            )
            for i in range(1, n + 1)
        ]
    )
    db.commit()
    return pool


def _pool_item_rows(db, pool_id: int, status: str | None = None):
    from app.models import AnnotationPoolItem

    q = db.query(AnnotationPoolItem).filter(AnnotationPoolItem.pool_id == pool_id)
    if status is not None:
        q = q.filter(AnnotationPoolItem.status == status)
    return q.all()


# --- (a) 抽取规模 min(20, available)，被抽中项全部置为 assigned ------------


def test_claim_draws_at_most_20(client, db):
    annotator = _annotator(db, "drawer-1")
    pool = _seed_pool(db, n=25)

    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 20
    assert body["table_name"] == "lit"

    from app.models import AnnotationTask, AnnotationTaskItem

    task = db.get(AnnotationTask, body["task_id"])
    assert task.status == "in_progress"
    assert task.claimed_by == annotator.id
    assert task.pool_id == pool.id
    items = db.query(AnnotationTaskItem).filter(AnnotationTaskItem.task_id == task.id).all()
    assert len(items) == 20
    assert all(it.status == "pending" for it in items)

    drawn_ids = {it.source_pool_item_id for it in items}
    assigned = _pool_item_rows(db, pool.id, status="assigned")
    assert len(assigned) == 20
    assert {it.id for it in assigned} == drawn_ids
    assert len(_pool_item_rows(db, pool.id, status="available")) == 5


def test_non_annotator_cannot_claim(client, db):
    normal = make_user(db, "plain-claimer", role="normal")
    _seed_pool(db, n=3)
    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(normal))
    assert resp.status_code == 403


# --- (b) 池选择顺序：priority DESC 优先，其次 created_at DESC --------------


def test_claim_prefers_higher_priority_pool(client, db):
    annotator = _annotator(db, "picker-1")
    low_old = _seed_pool(db, n=5, priority=0, created_at=OLD_TS)
    high_new = _seed_pool(db, n=5, priority=10, created_at=NEW_TS)

    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))

    assert resp.status_code == 200
    from app.models import AnnotationTask

    task = db.get(AnnotationTask, resp.json()["task_id"])
    assert task.pool_id == high_new.id
    assert task.pool_id != low_old.id
    # 低优先池原封不动
    assert len(_pool_item_rows(db, low_old.id, status="available")) == 5


def test_claim_falls_back_to_newer_pool_when_same_priority(client, db):
    annotator = _annotator(db, "picker-2")
    older = _seed_pool(db, n=5, priority=0, created_at=OLD_TS)
    newer = _seed_pool(db, n=5, priority=0, created_at=NEW_TS)

    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))

    assert resp.status_code == 200
    from app.models import AnnotationTask

    task = db.get(AnnotationTask, resp.json()["task_id"])
    assert task.pool_id == newer.id
    assert task.pool_id != older.id


# --- (c) 同一标注员二次领取 -> 409 已有进行中的任务 -------------------------


def test_second_claim_conflicts(client, db):
    annotator = _annotator(db, "double-claimer")
    _seed_pool(db, n=10)

    first = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))
    assert first.status_code == 200

    second = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))
    assert second.status_code == 409
    assert "已有进行中的任务" in second.json()["detail"]


def test_max_pending_rework_gate(monkeypatch, client, db):
    monkeypatch.setenv("ANNOTATION_MAX_PENDING_REWORK", "1")
    get_settings.cache_clear()

    annotator = _annotator(db, "reworker")
    pool = _seed_pool(db, n=10)

    from app.models import AnnotationTask, AnnotationTaskItem

    old_task = AnnotationTask(
        pool_id=pool.id,
        claimed_by=annotator.id,
        status="completed",
    )
    db.add(old_task)
    db.flush()
    db.add(
        AnnotationTaskItem(
            task_id=old_task.id,
            table_name="lit",
            record_id=10001,
            status="rejected",
        )
    )
    db.commit()

    resp = client.post(
        "/api/annotation/tasks/claim", json={}, headers=auth_header(annotator)
    )
    assert resp.status_code == 409
    assert "待返工条目过多" in resp.json()["detail"]


# --- (d) 代派：两个标注员各得独立任务，条目互不重叠 ------------------------


def test_assign_two_annotators_disjoint_items(client, db):
    admin = make_user(db, "assigner", role="admin")
    u1 = _annotator(db, "assignee-1")
    u2 = _annotator(db, "assignee-2")
    pool = _seed_pool(db, n=40)

    resp = client.post(
        "/api/annotation/admin/tasks/assign",
        json={"pool_id": pool.id, "user_ids": [u1.id, u2.id]},
        headers=auth_header(admin),
    )

    assert resp.status_code == 200
    results = resp.json()["results"]
    assert [r["ok"] for r in results] == [True, True]
    assert results[0]["task_id"] != results[1]["task_id"]

    from app.models import AnnotationTask, AnnotationTaskItem

    def _item_records(task_id: int) -> set[int]:
        rows = (
            db.query(AnnotationTaskItem)
            .filter(AnnotationTaskItem.task_id == task_id)
            .all()
        )
        assert len(rows) == 20
        assert all(r.status == "pending" for r in rows)
        return {r.record_id for r in rows}

    set1 = _item_records(results[0]["task_id"])
    set2 = _item_records(results[1]["task_id"])
    assert not (set1 & set2), "两个任务的条目必须互不重叠"

    tasks = db.query(AnnotationTask).order_by(AnnotationTask.id).all()
    by_user = {t.claimed_by: t for t in tasks}
    assert set(by_user) == {u1.id, u2.id}
    assert all(t.status == "in_progress" for t in tasks)
    assert all(t.deadline_at is not None and t.claimed_at is not None for t in tasks)

    assert len(_pool_item_rows(db, pool.id, status="available")) == 0
    assert len(_pool_item_rows(db, pool.id, status="assigned")) == 40


# --- (e) 代派坏用户：逐条目报错，其余用户不受影响 --------------------------


def test_assign_bad_users_get_per_item_errors(client, db):
    admin = make_user(db, "assigner-2", role="admin")
    good = _annotator(db, "good-annotator")
    wrong_role = make_user(db, "not-annotator", role="normal")
    inactive = _annotator(db, "sleepy-annotator", is_active=False)
    pool = _seed_pool(db, n=25)

    resp = client.post(
        "/api/annotation/admin/tasks/assign",
        json={
            "pool_id": pool.id,
            "user_ids": [99999, wrong_role.id, inactive.id, good.id],
        },
        headers=auth_header(admin),
    )

    assert resp.status_code == 200
    results = resp.json()["results"]
    by_user = {r["user_id"]: r for r in results}
    assert len(results) == 4

    assert by_user[99999] == {"user_id": 99999, "ok": False, "error": "用户不存在"}
    assert by_user[wrong_role.id]["ok"] is False
    assert "标注员" in by_user[wrong_role.id]["error"]
    assert by_user[inactive.id]["ok"] is False
    assert "禁用" in by_user[inactive.id]["error"]

    good_result = by_user[good.id]
    assert good_result["ok"] is True
    assert good_result["count"] == 20

    from app.models import AnnotationTask

    tasks = db.query(AnnotationTask).all()
    assert len(tasks) == 1
    assert tasks[0].claimed_by == good.id
    # 坏用户失败后好用户仍能抽满：25 可用 - 20 抽中 = 5
    assert len(_pool_item_rows(db, pool.id, status="available")) == 5


def test_assign_requires_admin(client, db):
    annotator = _annotator(db, "sneaky")
    pool = _seed_pool(db, n=5)
    resp = client.post(
        "/api/annotation/admin/tasks/assign",
        json={"pool_id": pool.id, "user_ids": [annotator.id]},
        headers=auth_header(annotator),
    )
    assert resp.status_code == 403


def test_assign_unknown_or_inactive_pool_rejected_globally(client, db):
    admin = make_user(db, "assigner-3", role="admin")
    annotator = _annotator(db, "waiter")

    resp_missing = client.post(
        "/api/annotation/admin/tasks/assign",
        json={"pool_id": 424242, "user_ids": [annotator.id]},
        headers=auth_header(admin),
    )
    assert resp_missing.status_code == 404

    paused = _seed_pool(db, n=5, status="paused")
    resp_paused = client.post(
        "/api/annotation/admin/tasks/assign",
        json={"pool_id": paused.id, "user_ids": [annotator.id]},
        headers=auth_header(admin),
    )
    assert resp_paused.status_code == 400

    from app.models import AnnotationTask

    assert db.query(AnnotationTask).count() == 0


# --- (f) deadline 覆盖：pool.deadline_days=3 -> deadline_at ≈ now+3d -------


def test_deadline_follows_pool_override(client, db):
    annotator = _annotator(db, "deadline-checker")
    _seed_pool(db, n=1, deadline_days=3)

    before = _naive_utcnow()
    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))
    after = _naive_utcnow()

    assert resp.status_code == 200
    parsed = datetime.fromisoformat(resp.json()["deadline_at"])
    lower = before + timedelta(days=3) - timedelta(minutes=2)
    upper = after + timedelta(days=3) + timedelta(minutes=2)
    assert lower <= parsed <= upper


def test_default_deadline_from_config(client, db):
    annotator = _annotator(db, "default-deadline")
    _seed_pool(db, n=1, deadline_days=None)

    before = _naive_utcnow()
    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))

    assert resp.status_code == 200
    parsed = datetime.fromisoformat(resp.json()["deadline_at"])
    assert before + timedelta(days=7) - timedelta(minutes=2) <= parsed


# --- (g-sqlite) rowcount 对账重试路径真实执行（防 misleading_success）------


def test_claim_retry_after_contention(client, db, monkeypatch):
    """首抽候选里混入一条已被占用的记录 -> rowcount 短缺 -> 回滚重试成功。"""
    from app.services import annotation_service

    annotator = _annotator(db, "contender")
    pool = _seed_pool(db, n=60)
    stolen = _pool_item_rows(db, pool.id)[0]
    stolen.status = "assigned"
    db.commit()
    assert len(_pool_item_rows(db, pool.id, status="available")) == 59

    original = annotation_service._random_candidate_ids
    calls = {"n": 0}

    def poisoned_first_draw(session, target_pool_id, n):
        calls["n"] += 1
        if calls["n"] == 1:
            return [stolen.id] + list(original(session, target_pool_id, n - 1))
        return list(original(session, target_pool_id, n))

    monkeypatch.setattr(annotation_service, "_random_candidate_ids", poisoned_first_draw)

    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))

    assert calls["n"] == 2, "rowcount 对账失败后必须恰好重试一次"
    assert resp.status_code == 200

    from app.models import AnnotationTaskItem

    task_id = resp.json()["task_id"]
    items = db.query(AnnotationTaskItem).filter(AnnotationTaskItem.task_id == task_id).all()
    assert len(items) == 20
    assert all(it.source_pool_item_id != stolen.id for it in items)
    assert len(_pool_item_rows(db, pool.id, status="available")) == 39


def test_claim_gives_up_after_two_poisoned_attempts(client, db, monkeypatch):
    """两次对账都短缺 -> 409 任务池已被抢占，且不残留任何任务行。"""
    from app.services import annotation_service

    annotator = _annotator(db, "unlucky")
    pool = _seed_pool(db, n=60)
    pre_assigned = _pool_item_rows(db, pool.id)[0]
    pre_assigned.status = "assigned"
    db.commit()

    original = annotation_service._random_candidate_ids
    calls = {"n": 0}

    def always_poisoned(session, target_pool_id, n):
        calls["n"] += 1
        return [pre_assigned.id] + list(original(session, target_pool_id, n - 1))

    monkeypatch.setattr(annotation_service, "_random_candidate_ids", always_poisoned)

    from app.models import AnnotationLog, AnnotationTask

    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))

    assert calls["n"] == 2
    assert resp.status_code == 409
    assert "任务池已被抢占" in resp.json()["detail"]
    assert db.query(AnnotationTask).count() == 0
    assert db.query(AnnotationLog).count() == 0
    # 回滚彻底：59 available 一条不少
    assert len(_pool_item_rows(db, pool.id, status="available")) == 59


# --- (g-pg) SKIP LOCKED 并发：8 线程同时 claim，恰 1 成功 7×409 ------------


def _pg_reachable() -> bool:
    import socket

    from app.config import get_database_config

    cfg = get_database_config()
    try:
        with socket.create_connection((cfg.host, cfg.port), timeout=2):
            return True
    except OSError:
        return False


requires_pg = pytest.mark.skipif(not _pg_reachable(), reason="PostgreSQL 不可用")


@requires_pg
def test_pg_concurrent_claims_exactly_one_winner():
    import concurrent.futures

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.models.conversation  # noqa: F401
    import app.models.message  # noqa: F401
    from app.auth.service import create_access_token
    from app.config import get_database_config
    from app.core.database import get_db
    from app.models import Base, AnnotationPool, AnnotationPoolItem
    from app.models.user import User
    from app.routers.annotation import router as annotation_router

    engine = create_engine(
        get_database_config().dsn, connect_args={"connect_timeout": 3}
    )
    # 只 create（幂等）不 drop：目标可能是共享 PG，销毁性清理不可接受；
    # 本测试产生的少量行留在测试库中由 CI 环境自行回收。
    Base.metadata.create_all(engine)
    try:
        SessionLocal = sessionmaker(bind=engine)

        seed = SessionLocal()
        pool = AnnotationPool(table_name="lit", filter_json={}, status="active", priority=0)
        seed.add(pool)
        seed.flush()
        seed.add_all(
            [
                AnnotationPoolItem(pool_id=pool.id, table_name="lit", record_id=i, status="available")
                for i in range(1, 21)
            ]
        )
        users = []
        for i in range(8):
            u = User(
                username=f"pg-racer-{_naive_utcnow().timestamp()}-{i}",
                email=f"pg-racer-{i}@race.local",
                hashed_password="x",
                role="annotator",
                is_active=True,
            )
            seed.add(u)
            users.append(u)
        seed.commit()
        tokens = {
            u.id: create_access_token(data={"sub": str(u.id), "role": u.role})
            for u in users
        }
        user_ids = [u.id for u in users]
        pool_id = pool.id
        seed.close()

        app = FastAPI()
        app.include_router(annotation_router)

        def _override():
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = _override

        def race(user_id: int) -> int:
            with TestClient(app) as thread_client:
                resp = thread_client.post(
                    "/api/annotation/tasks/claim",
                    json={},
                    headers={"Authorization": f"Bearer {tokens[user_id]}"},
                )
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool_exec:
            futures = [pool_exec.submit(race, uid) for uid in user_ids]
            codes = [f.result(timeout=60) for f in futures]

        assert codes.count(200) == 1, f"应恰有 1 个赢家，实际 {codes}"
        assert codes.count(409) == 7, f"其余应为 409，实际 {codes}"

        check = SessionLocal()
        try:
            remaining = (
                check.query(AnnotationPoolItem)
                .filter(
                    AnnotationPoolItem.pool_id == pool_id,
                    AnnotationPoolItem.status == "available",
                )
                .count()
            )
            assert remaining == 0
        finally:
            check.close()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
