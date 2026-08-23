"""逐条暂存与整批提交（plan todo #6）：item_draft / batch_submit。

沿用 test_annotation_claim 约定：本机无 PostgreSQL，main.py 顶层迁移直连 PG，
故把真实 annotation 路由挂载到裸 FastAPI 宿主，仅覆盖 get_db；
require_annotator 走真实依赖链（真实 JWT + DB 用户）。

核心记录（lit_metadata）的 server_default 是 text("NOW()")，SQLite 无此函数，
播种与 Core 层直改一律显式给 updated_at（见 test_annotation_pools 先例）。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_annotation_config
from tests.utils import auth_header, make_user

CORE_TS = datetime(2026, 1, 15, 8, 0, 0)
NEWER_TS = datetime(2026, 8, 1, 8, 0, 0)
assert NEWER_TS > CORE_TS


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
    from tests.utils import make_user

    return make_user(db, name, role="annotator")


def _seed_core_lit(db, n: int) -> list[int]:
    """播种 n 条核心 lit 记录（显式时间戳规避 SQLite NOW() 缺失）。"""
    from app.models import LitMetadata

    for i in range(1, n + 1):
        db.add(
            LitMetadata(
                file_uuid=f"t6-u{i}",
                original_name=f"a{i}.pdf",
                storage_path=f"lit/t6-u{i}/a{i}.pdf",
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
    """直插 pool + 与核心记录一一对应的 available pool_item。"""
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


@pytest.fixture()
def claimed(db, client):
    """3 条核心记录 + 建池 + 领取 → (annotator, task_id, items)。"""
    record_ids = _seed_core_lit(db, n=3)
    _seed_pool_with_records(db, record_ids)
    annotator = _annotator(db, "drafter")
    task_id = _claim_task(client, annotator)
    return annotator, task_id, _task_items(db, task_id)


# --- (a) 正常编辑暂存：submission(draft) + base_updated_at 快照 + 日志 ------


def test_happy_draft_creates_submission_with_base_snapshot(client, db, claimed):
    annotator, _task_id, items = claimed
    item1 = items[0]

    resp = _draft(client, annotator, item1.id, {"title": "新标题"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["item_id"] == item1.id
    assert body["action"] == "draft"

    subs = _submissions_for(db, item1.id)
    assert len(subs) == 1
    sub = subs[0]
    assert sub.status == "draft"
    assert sub.proposed_fields == {"title": "新标题"}
    assert sub.base_updated_at == CORE_TS, "base_updated_at 必须等于核心记录当前 updated_at"
    assert sub.annotator_id == annotator.id
    assert sub.username == annotator.username

    db.refresh(item1)
    assert item1.status == "drafted"

    from app.models import AnnotationLog

    log = (
        db.query(AnnotationLog)
        .filter(AnnotationLog.action == "draft", AnnotationLog.record_id == item1.record_id)
        .one()
    )
    assert log.new_fields == {"title": "新标题"}
    assert log.submission_id == sub.id
    assert log.actor_id == annotator.id
    assert log.table_name == "lit"


# --- (b) 空 dict = 标记无需修改：日志 action=no_change ----------------------


def test_no_change_draft_logs_no_change(client, db, claimed):
    annotator, _task_id, items = claimed
    item2 = items[1]

    resp = _draft(client, annotator, item2.id, {})
    assert resp.status_code == 200
    assert resp.json()["action"] == "no_change"

    from app.models import AnnotationLog

    sub = _submissions_for(db, item2.id)[0]
    assert sub.status == "draft"
    assert sub.proposed_fields == {}
    log = (
        db.query(AnnotationLog)
        .filter(AnnotationLog.action == "no_change", AnnotationLog.record_id == item2.record_id)
        .one()
    )
    assert log.new_fields == {}


# --- (c) 覆盖暂存：同一 submission 行原位更新，不产生新行 -------------------


def test_redraft_overwrites_same_submission_row(client, db, claimed):
    annotator, _task_id, items = claimed
    item1 = items[0]

    first = _draft(client, annotator, item1.id, {"title": "第一版"})
    assert first.status_code == 200
    first_sub_id = first.json()["submission_id"]

    second = _draft(client, annotator, item1.id, {"title": "第二版", "journal": "另一期刊"})
    assert second.status_code == 200
    assert second.json()["submission_id"] == first_sub_id, "覆盖暂存必须复用同一 submission 行"

    subs = _submissions_for(db, item1.id)
    assert len(subs) == 1, "不得重复建行"
    sub = subs[0]
    assert sub.id == first_sub_id
    assert sub.proposed_fields == {"title": "第二版", "journal": "另一期刊"}
    assert sub.status == "draft"


# --- (d) 非法字段名 -> 400 字段不可编辑 -------------------------------------


def test_invalid_field_rejected_400(client, db, claimed):
    annotator, _task_id, items = claimed

    resp = _draft(client, annotator, items[0].id, {"not_a_real_column": "x"})

    assert resp.status_code == 400
    assert "字段不可编辑" in resp.json()["detail"]
    assert _submissions_for(db, items[0].id) == []
    assert items[0].status == "pending"


# --- (e) 整批提交 happy path：任务 completed、条目 submitted、可立即再领 ----


def test_batch_submit_completes_task_and_flips_rows(client, db, claimed):
    annotator, task_id, items = claimed
    _seed_pool_with_records(db, [r * 1000 for r in range(9001, 9006)])  # 再领用池

    for it in items:
        fields = {} if it is items[1] else {"title": f"标题-{it.id}"}
        assert _draft(client, annotator, it.id, fields).status_code == 200

    resp = client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "task_id": task_id,
        "completed": True,
        "count": 3,
        "stale_base_item_ids": [],
    }

    from app.models import AnnotationSubmission, AnnotationTask

    task = db.get(AnnotationTask, task_id)
    assert task.status == "completed"

    for it in items:
        db.refresh(it)
        assert it.status == "submitted"
        assert it.submitted_at is not None
        sub = _submissions_for(db, it.id)[0]
        assert sub.status == "pending"

    assert db.query(AnnotationSubmission).filter_by(status="draft").count() == 0

    from app.models import AnnotationLog

    log = db.query(AnnotationLog).filter(AnnotationLog.action == "submit").one()
    assert log.record_id == 0
    assert log.new_fields == {"task_id": task_id, "count": 3}

    relog = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))
    assert relog.status_code == 200, "提交完成后同一标注员必须能立刻再领取"


# --- (f) C8 base 失效检测：仅预警不拦截 -------------------------------------


def test_stale_base_detected_but_submit_still_succeeds(client, db, claimed):
    from app.models import AnnotationTask, LitMetadata

    annotator, task_id, items = claimed
    for it in items:
        assert _draft(client, annotator, it.id, {"title": "x"}).status_code == 200

    stale_target = items[0]
    # Core 层直改：sa.update 绕开 ORM onupdate，并显式给出更新的 updated_at
    db.execute(
        sa.update(LitMetadata)
        .where(LitMetadata.id == stale_target.record_id)
        .values(updated_at=NEWER_TS)
    )
    db.commit()

    resp = client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed"] is True
    assert body["count"] == 3
    assert body["stale_base_item_ids"] == [stale_target.id]

    sub = _submissions_for(db, stale_target.id)[0]
    assert sub.base_updated_at == CORE_TS, "快照保持播种时的旧值"
    core_now = db.get(LitMetadata, stale_target.record_id)
    assert core_now.updated_at == NEWER_TS
    assert NEWER_TS > CORE_TS

    assert db.get(AnnotationTask, task_id).status == "completed"


# --- (g) 部分暂存就提交 -> 409 还有 N 条未暂存 -------------------------------


def test_partial_staging_submit_conflicts(client, db, claimed):
    annotator, task_id, items = claimed
    assert _draft(client, annotator, items[0].id, {"title": "a"}).status_code == 200
    assert _draft(client, annotator, items[1].id, {}).status_code == 200

    resp = client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))

    assert resp.status_code == 409
    assert "还有 1 条未暂存" in resp.json()["detail"]

    from app.models import AnnotationSubmission, AnnotationTask

    assert db.get(AnnotationTask, task_id).status == "in_progress"
    assert db.query(AnnotationSubmission).filter_by(status="pending").count() == 0


# --- (h) 越权：他人任务条目 403 ---------------------------------------------


def test_other_annotators_item_and_task_forbidden(client, db, claimed):
    owner, task_id, items = claimed
    intruder = _annotator(db, "intruder")

    draft_resp = _draft(client, intruder, items[0].id, {"title": "偷改"})
    assert draft_resp.status_code == 403
    assert "只能操作自己任务中的条目" in draft_resp.json()["detail"]

    submit_resp = client.post(
        f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(intruder)
    )
    assert submit_resp.status_code == 403

    assert _submissions_for(db, items[0].id) == []


# --- (i) 返工重做：rejected 条目重新暂存生成新 submission，历史保留 ----------


def test_rework_rejected_item_creates_new_submission_then_submit(client, db, claimed):
    from app.models import AnnotationSubmission, AnnotationTask, AnnotationTaskItem

    annotator, task_id, items = claimed
    item1 = items[0]

    # 模拟 T8 驳回后的现场：item rejected + 一条 rejected submission
    item1.status = "rejected"
    item1.rejected_at = _naive_utcnow()
    old_sub = AnnotationSubmission(
        item_id=item1.id,
        annotator_id=annotator.id,
        username=annotator.username,
        proposed_fields={"title": "被驳回的旧稿"},
        base_updated_at=CORE_TS,
        status="rejected",
        review_comment="标题不规范",
    )
    db.add(old_sub)
    db.commit()
    old_sub_id = old_sub.id

    resp = _draft(client, annotator, item1.id, {"title": "返工新稿"})
    assert resp.status_code == 200
    new_sub_id = resp.json()["submission_id"]
    assert new_sub_id != old_sub_id, "驳回后重新暂存必须新建 submission"

    subs = _submissions_for(db, item1.id)
    assert [s.id for s in subs] == sorted([old_sub_id, new_sub_id])
    old = db.get(AnnotationSubmission, old_sub_id)
    assert old.status == "rejected", "历史驳回记录必须原样保留"
    assert old.proposed_fields == {"title": "被驳回的旧稿"}
    fresh = db.get(AnnotationSubmission, new_sub_id)
    assert fresh.status == "draft"
    assert fresh.proposed_fields == {"title": "返工新稿"}

    db.refresh(item1)
    assert item1.status == "drafted"

    for it in items[1:]:
        assert _draft(client, annotator, it.id, {}).status_code == 200
    submit = client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))
    assert submit.status_code == 200
    assert submit.json()["count"] == 3
    assert db.get(AnnotationTask, task_id).status == "completed"


# --- (j) 未知条目 / 未知任务 -> 404 ------------------------------------------


def test_unknown_item_and_task_404(client, db, claimed):
    annotator, _task_id, _items = claimed

    resp_item = _draft(client, annotator, 987654, {"title": "x"})
    assert resp_item.status_code == 404
    assert "条目不存在" in resp_item.json()["detail"]

    resp_task = client.post(
        "/api/annotation/tasks/987654/submit", headers=auth_header(annotator)
    )
    assert resp_task.status_code == 404


# --- 补充：终态守卫（submitted/completed 后再操作 -> 409）--------------------


def test_operations_blocked_after_completion(client, db, claimed):
    annotator, task_id, items = claimed
    for it in items:
        assert _draft(client, annotator, it.id, {}).status_code == 200
    assert (
        client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))
    ).status_code == 200

    redraft = _draft(client, annotator, items[0].id, {"title": "迟到的修改"})
    assert redraft.status_code == 409
    assert "任务不在进行中" in redraft.json()["detail"]

    resubmit = client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))
    assert resubmit.status_code == 409
    assert "任务不在进行中" in resubmit.json()["detail"]


def test_non_annotator_cannot_draft_or_submit(client, db, claimed):
    owner, task_id, items = claimed
    plain = make_user(db, "plain-t6", role="normal")

    assert _draft(client, plain, items[0].id, {"title": "x"}).status_code == 403
    assert (
        client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(plain)).status_code
        == 403
    )


def test_draft_on_submitted_item_conflicts(client, db, claimed):
    annotator, _task_id, items = claimed
    for it in items:
        assert _draft(client, annotator, it.id, {}).status_code == 200
    # 手动把条目推进到 submitted（模拟已进入复核），此时不允许再暂存
    for it in items:
        it.status = "submitted"
        it.submitted_at = _naive_utcnow()
    db.commit()

    resp = _draft(client, annotator, items[0].id, {"title": "x"})
    assert resp.status_code == 409
    assert "该条目当前状态不可暂存" in resp.json()["detail"]
