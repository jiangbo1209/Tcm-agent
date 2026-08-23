"""管理员复核（plan todo #8）：review_queue / approve / reject / expired 处理。

沿用 test_annotation_items 约定：本机无 PostgreSQL，main.py 顶层迁移直连 PG，
故把真实 annotation 路由与 annotation_admin 路由同时挂载到裸 FastAPI 宿主，
仅覆盖 get_db；require_annotator / require_admin 走真实依赖链（真实 JWT + DB 用户）。
pending 提交单经 claim + draft + submit 自然产生，绝不手工插 pending 行。

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
    return make_user(db, "review-admin", role="admin")


QUEUE_URL = "/api/annotation/admin/review/queue"


def _seed_core_lit(db, n: int, *, prefix: str = "t8") -> list[int]:
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


def _draft(client, annotator, item_id: int, proposed_fields: dict):
    return client.put(
        f"/api/annotation/items/{item_id}/draft",
        json={"proposed_fields": proposed_fields},
        headers=auth_header(annotator),
    )


def _submit_all(client, annotator, task_id: int):
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


def _submit_batch(db, client, *, n: int, fields: list[dict], prefix: str = "t8"):
    """建池 -> 领取 -> 逐条暂存 -> 整批提交，返回 (annotator, task_id, items, submissions)。"""
    record_ids = _seed_core_lit(db, n, prefix=prefix)
    _seed_pool_with_records(db, record_ids)
    annotator = make_user(db, f"{prefix}-annotator", role="annotator")
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)
    for it, f in zip(items, fields):
        assert _draft(client, annotator, it.id, f).status_code == 200
    _submit_all(client, annotator, task_id)
    return annotator, task_id, items, _pending_submissions(db, items)


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


def _log_for(db, action: str, submission_id: int):
    from app.models import AnnotationLog

    log = (
        db.query(AnnotationLog)
        .filter(AnnotationLog.action == action, AnnotationLog.submission_id == submission_id)
        .one()
    )
    return log


# --- (a) 队列分组：同一任务的 3 条提交单聚成一组 -----------------------------


def test_queue_groups_by_task_with_current_values(client, db, admin):
    annotator, task_id, items, subs = _submit_batch(
        db, client, n=3, fields=[{"title": "批量稿一"}, {}, {"title": "批量稿三"}]
    )

    resp = client.get(QUEUE_URL, params={"status": "pending"}, headers=auth_header(admin))
    assert resp.status_code == 200
    groups = resp.json()
    assert len(groups) == 1, "同一任务的三条提交单必须聚合为一个组"

    group = groups[0]
    assert group["task_id"] == task_id
    assert group["annotator_username"] == annotator.username
    assert group["table_name"] == "lit"
    assert group["submitted_at"] is not None
    assert group["count"] == 3

    entry_subs = [it["submission_id"] for it in group["items"]]
    assert entry_subs == sorted(s.id for s in subs), "组内条目按 submission id 升序"
    by_sid = {s.id: s for s in subs}
    no_change = next(it for it in group["items"] if by_sid[it["submission_id"]].proposed_fields == {})
    assert no_change["proposed_fields"] == {}
    assert no_change["current_values"]["title"].startswith("针灸治疗不孕症研究"), (
        "current_values 必须反映核心记录现值"
    )
    real = next(it for it in group["items"] if it["submission_id"] == subs[0].id)
    assert real["current_values"]["title"] == "针灸治疗不孕症研究1"
    for it in group["items"]:
        assert "core_missing" not in it


# --- (b) 批准 happy path：核心表真实更新 + 审计对照 ---------------------------


def test_approve_applies_proposed_fields_to_core(client, db, admin):
    _annotator, _task_id, items, subs = _submit_batch(
        db, client, n=2, fields=[{"title": "批准后标题", "journal": "新期刊"}, {}]
    )
    target_item, target_sub = items[0], subs[0]

    resp = _approve(client, admin, target_sub.id)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "submission_id": target_sub.id,
        "item_id": target_item.id,
        "record_id": target_item.record_id,
        "status": "approved",
    }

    from app.models import LitMetadata

    core = db.get(LitMetadata, target_item.record_id)
    assert core.title == "批准后标题", "批准必须把 proposed_fields 落到核心表"
    assert core.journal == "新期刊"

    db.refresh(target_sub)
    assert target_sub.status == "approved"
    assert target_sub.reviewer_id == admin.id
    assert target_sub.reviewed_at is not None
    db.refresh(target_item)
    assert target_item.status == "approved"

    log = _log_for(db, "approve", target_sub.id)
    assert log.old_fields != log.new_fields
    assert log.old_fields["title"] == "针灸治疗不孕症研究1"
    assert log.new_fields["title"] == "批准后标题"
    assert log.actor_id == admin.id


# --- (c) 复用 update_record 的旁证：crawl_status 自动晋升 --------------------


def test_approve_reuses_update_record_side_effects(client, db, admin):
    """partial + 缺必填字段 -> 补齐后批准 -> crawl_status 晋升 success。

    只有真正走 AdminQueryRepository.update_record 才会有该副作用，
    绕过它手写 UPDATE 无法通过此测试。
    """
    from app.models import LitMetadata

    db.add(
        LitMetadata(
            file_uuid="t8-partial",
            original_name="p.pdf",
            storage_path="lit/t8/p.pdf",
            cleaned_title="部分抓取",
            title="针灸机制研究",
            authors=["李四"],
            keywords=["针灸"],
            source_site="cnki",
            journal="",  # 必填缺失
            pub_year="",  # 必填缺失
            abstract=None,  # 必填缺失
            matched_title="部分抓取",
            crawl_status="partial",
            error_message="字段抓取不全",
            created_at=CORE_TS,
            updated_at=CORE_TS,
        )
    )
    db.commit()
    record_id = db.query(LitMetadata).filter_by(file_uuid="t8-partial").one().id
    _seed_pool_with_records(db, [record_id])
    annotator = make_user(db, "t8-partial-ann", role="annotator")
    task_id = _claim_task(client, annotator)
    item = _task_items(db, task_id)[0]
    complete_fields = {
        "abstract": "补全的摘要文本",
        "paper_type": "期刊论文",
        "journal": "中医杂志",
        "pub_year": "2024",
    }
    assert _draft(client, annotator, item.id, complete_fields).status_code == 200
    _submit_all(client, annotator, task_id)
    (sub,) = _pending_submissions(db, [item])

    resp = _approve(client, admin, sub.id)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    core = db.get(LitMetadata, record_id)
    assert core.crawl_status == "success", "update_record 的自动晋升副作用必须出现"
    assert core.error_message is None


# --- (d) base 冲突 -> 单条过期，其余条目独立可用 ------------------------------


def test_stale_base_expires_one_item_others_independent(client, db, admin):
    from app.models import LitMetadata

    _annotator, _task_id, items, subs = _submit_batch(
        db, client, n=2, fields=[{"title": "冲突稿"}, {"title": "正常稿"}]
    )
    stale_item, stale_sub = items[0], subs[0]
    fresh_sub = subs[1]

    # Core 层直改：sa.update 绕开 ORM onupdate，把基准推到更新的时间戳
    db.execute(
        sa.update(LitMetadata)
        .where(LitMetadata.id == stale_item.record_id)
        .values(updated_at=NEWER_TS)
    )
    db.commit()

    resp = _approve(client, admin, stale_sub.id)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "expired", "乐观锁冲突必须转 expired 而不是报错"
    assert body["submission_id"] == stale_sub.id

    db.refresh(stale_sub)
    assert stale_sub.status == "expired"
    assert stale_sub.reviewed_at is not None
    assert stale_sub.reviewer_id == admin.id
    db.refresh(stale_item)
    assert stale_item.status == "rejected"
    assert stale_item.rejected_at is not None, "过期条目必须进返工箱"

    expire_log = _log_for(db, "expire", stale_sub.id)
    assert expire_log.new_fields == {"reason": "base_conflict"}

    # 其余条目不受牵连：仍可正常批准
    other_resp = _approve(client, admin, fresh_sub.id)
    assert other_resp.status_code == 200
    assert other_resp.json()["status"] == "approved"
    db.refresh(fresh_sub)
    assert fresh_sub.status == "approved"

    core = db.get(LitMetadata, items[1].record_id)
    assert core.title == "正常稿"


# --- (e) 驳回：意见落库 + 条目进返工箱 + 审计 --------------------------------


def test_reject_stores_comment_and_moves_item_to_rework(client, db, admin):
    _annotator, _task_id, items, subs = _submit_batch(db, client, n=1, fields=[{"title": "驳回稿"}])
    target_item, target_sub = items[0], subs[0]

    resp = _reject(client, admin, target_sub.id, "标题不规范，请重写")
    assert resp.status_code == 200
    assert resp.json() == {
        "submission_id": target_sub.id,
        "item_id": target_item.id,
        "status": "rejected",
    }

    db.refresh(target_sub)
    assert target_sub.status == "rejected"
    assert target_sub.review_comment == "标题不规范，请重写"
    assert target_sub.reviewer_id == admin.id
    assert target_sub.reviewed_at is not None
    db.refresh(target_item)
    assert target_item.status == "rejected"
    assert target_item.rejected_at is not None

    log = _log_for(db, "reject", target_sub.id)
    assert log.new_fields == {"comment": "标题不规范，请重写"}
    assert log.actor_id == admin.id


# --- (f) 空评论驳回 -> 400 ----------------------------------------------------


def test_reject_without_comment_400(client, db, admin):
    _annotator, _task_id, _items, subs = _submit_batch(db, client, n=1, fields=[{}])

    resp = _reject(client, admin, subs[0].id, "")

    assert resp.status_code == 400
    assert "驳回必须填写评论" in resp.json()["detail"]


# --- (g) 空 diff 快速通道：不触碰核心表 ---------------------------------------


def test_empty_diff_approve_skips_core_write(client, db, admin):
    from app.models import LitMetadata

    _annotator, _task_id, items, subs = _submit_batch(db, client, n=1, fields=[{}])
    target_item, target_sub = items[0], subs[0]
    before = db.get(LitMetadata, target_item.record_id)
    before_title, before_updated = before.title, before.updated_at

    resp = _approve(client, admin, target_sub.id)

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    after = db.get(LitMetadata, target_item.record_id)
    assert after.title == before_title
    assert after.updated_at == before_updated, "空 diff 批准绝不允许碰核心表（含 updated_at）"

    db.refresh(target_sub)
    assert target_sub.status == "approved"
    assert target_sub.reviewer_id == admin.id
    db.refresh(target_item)
    assert target_item.status == "approved"

    log = _log_for(db, "approve", target_sub.id)
    assert log.old_fields == {}
    assert log.new_fields == {}


# --- (h) 重复复核守卫 -> 409 --------------------------------------------------


def test_double_approve_conflicts(client, db, admin):
    _annotator, _task_id, _items, subs = _submit_batch(
        db, client, n=1, fields=[{"title": "只批一次"}]
    )
    assert _approve(client, admin, subs[0].id).status_code == 200

    resp = _approve(client, admin, subs[0].id)

    assert resp.status_code == 409
    assert "该提交单状态为 approved，不可复核" in resp.json()["detail"]

    reject_resp = _reject(client, admin, subs[0].id, "再驳一次试试")
    assert reject_resp.status_code == 409


# --- (i) 非管理员一律 403 -----------------------------------------------------


def test_non_admin_forbidden_on_review_endpoints(client, db, admin):
    plain = make_user(db, "plain-t8", role="normal")

    queue_resp = client.get(QUEUE_URL, headers=auth_header(plain))
    assert queue_resp.status_code == 403

    approve_resp = _approve(client, plain, 1)
    assert approve_resp.status_code == 403

    reject_resp = _reject(client, plain, 1, "x")
    assert reject_resp.status_code == 403


# --- (j) 过期队列：status=expired 列出冲突提交单 ------------------------------


def test_expired_queue_lists_expired_submission(client, db, admin):
    from app.models import LitMetadata

    _annotator, _task_id, items, subs = _submit_batch(
        db, client, n=2, fields=[{"title": "过期稿"}, {"title": "待审稿"}], prefix="t8j"
    )
    stale_sub = subs[0]
    db.execute(
        sa.update(LitMetadata)
        .where(LitMetadata.id == items[0].record_id)
        .values(updated_at=NEWER_TS)
    )
    db.commit()
    assert _approve(client, admin, stale_sub.id).json()["status"] == "expired"

    pending_groups = client.get(
        QUEUE_URL, params={"status": "pending"}, headers=auth_header(admin)
    ).json()
    pending_sids = [it["submission_id"] for g in pending_groups for it in g["items"]]
    assert stale_sub.id not in pending_sids, "已过期的提交单不得再出现在 pending 队列"

    expired_groups = client.get(
        QUEUE_URL, params={"status": "expired"}, headers=auth_header(admin)
    ).json()
    expired_sids = [it["submission_id"] for g in expired_groups for it in g["items"]]
    assert expired_sids == [stale_sub.id]


# --- (k) 服务层补充：核心记录被删的条目带 core_missing 标记 -------------------


def test_queue_flags_missing_core_record(db):
    from app.services import annotation_service

    record_ids = _seed_core_lit(db, 1)
    _seed_pool_with_records(db, record_ids)
    annotator = make_user(db, "t8-k-ann", role="annotator")

    # 手工构造一条 pending 提交单（核心行随后删除，无法走 HTTP 全流程）
    from app.models import (
        AnnotationSubmission,
        AnnotationTask,
        AnnotationTaskItem,
    )

    task = AnnotationTask(pool_id=None, claimed_by=annotator.id, status="completed")
    db.add(task)
    db.flush()
    item = AnnotationTaskItem(
        task_id=task.id,
        table_name="lit",
        record_id=record_ids[0],
        status="submitted",
        submitted_at=_naive_utcnow(),
    )
    db.add(item)
    db.flush()
    db.add(
        AnnotationSubmission(
            item_id=item.id,
            annotator_id=annotator.id,
            username=annotator.username,
            proposed_fields={"title": "孤儿稿"},
            base_updated_at=CORE_TS,
            status="pending",
        )
    )
    # 删除核心记录后再查询
    from app.models import LitMetadata

    db.query(LitMetadata).filter(LitMetadata.id == record_ids[0]).delete()
    db.commit()

    groups = annotation_service.review_queue(db, status="pending")
    assert len(groups) == 1
    (entry,) = groups[0]["items"]
    assert entry["core_missing"] is True
    assert entry["current_values"] == {}
