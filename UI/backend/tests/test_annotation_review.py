"""管理员复核（R3T4 扁平分页与批量）：review_queue flat pagination + batch approve/reject.

沿用 test_annotation_items 约定：裸 FastAPI + 真实依赖链（真实 JWT + DB 用户）。
pending 提交单经 claim + draft + submit 自然产生。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.utils import auth_header, make_user

CORE_TS = datetime(2026, 1, 15, 8, 0, 0)
NEWER_TS = datetime(2026, 8, 1, 8, 0, 0)
assert NEWER_TS > CORE_TS


def _naive_utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _annotation_enabled(monkeypatch):
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
    return make_user(db, "review-admin", role="admin")


QUEUE_URL = "/api/annotation/admin/review/queue"
BATCH_APPROVE_URL = "/api/annotation/admin/review/batch-approve"
BATCH_REJECT_URL = "/api/annotation/admin/review/batch-reject"


def _seed_core_lit(db, n: int, *, prefix: str = "t8") -> list[int]:
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


# --- (a) 扁平分页：page/page_size 翻页断言 total/items 顺序 ---------------------


def test_queue_flat_pagination_basic(client, db, admin):
    # seed > default page_size 条 => 用 5 条，分页 page_size=2
    annotator, task_id, items, subs = _submit_batch(
        db,
        client,
        n=5,
        fields=[{"title": f"稿{i}"} for i in range(5)],
        prefix="flat1",
    )
    # page 1
    resp = client.get(QUEUE_URL, params={"page": 1, "page_size": 2}, headers=auth_header(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    # order by submission.id asc
    ids_page1 = [it["submission_id"] for it in data["items"]]
    assert ids_page1 == sorted(ids_page1)
    assert ids_page1 == sorted([s.id for s in subs])[:2]

    # page 2
    resp2 = client.get(QUEUE_URL, params={"page": 2, "page_size": 2}, headers=auth_header(admin))
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 5
    assert data2["page"] == 2
    assert len(data2["items"]) == 2
    ids_page2 = [it["submission_id"] for it in data2["items"]]
    assert ids_page2 == sorted([s.id for s in subs])[2:4]
    # no overlap
    assert set(ids_page1).isdisjoint(set(ids_page2))

    # page 3 - remaining 1
    resp3 = client.get(QUEUE_URL, params={"page": 3, "page_size": 2}, headers=auth_header(admin))
    assert resp3.status_code == 200
    assert len(resp3.json()["items"]) == 1

    # 默认分页参数 (不传即 1/20)
    resp_default = client.get(QUEUE_URL, headers=auth_header(admin))
    assert resp_default.status_code == 200
    assert resp_default.json()["total"] == 5
    assert resp_default.json()["page"] == 1
    assert resp_default.json()["page_size"] == 20


def test_queue_flat_item_schema_and_current_values(client, db, admin):
    annotator, task_id, items, subs = _submit_batch(
        db, client, n=1, fields=[{"title": "扁平稿"}], prefix="flat2"
    )
    resp = client.get(QUEUE_URL, params={"page": 1, "page_size": 20}, headers=auth_header(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    entry = data["items"][0]
    # required fields per spec
    assert entry["submission_id"] == subs[0].id
    assert entry["item_id"] == items[0].id
    assert entry["record_id"] == items[0].record_id
    assert entry["annotator_username"] == annotator.username
    assert entry["table_name"] == "lit"
    assert "current_values" in entry
    assert entry["current_values"]["title"] == "针灸治疗不孕症研究1"
    assert entry["proposed_fields"] == {"title": "扁平稿"}
    assert "base_updated_at" in entry
    assert entry["base_updated_at"] is not None
    # core_missing absent when not missing
    assert "core_missing" not in entry or entry["core_missing"] is not True


def test_queue_flat_page_size_validation(client, db, admin):
    resp = client.get(QUEUE_URL, params={"page": 1, "page_size": 101}, headers=auth_header(admin))
    assert resp.status_code == 422
    resp2 = client.get(QUEUE_URL, params={"page": 0, "page_size": 20}, headers=auth_header(admin))
    assert resp2.status_code == 422
    # status 旧参数已废弃：传 status 应被忽略或422？现在路由已移除 status 参数，传多余参数应忽略或报错；
    # 约定不再支持 status，故只断言不走旧 tab 语义
    _submit_batch(db, client, n=1, fields=[{"title": "x"}], prefix="flat3")
    resp3 = client.get(QUEUE_URL, params={"page": 1, "page_size": 20}, headers=auth_header(admin))
    assert resp3.status_code == 200
    assert resp3.json()["total"] == 1


def test_queue_flags_missing_core_record_flat(db):
    from app.services import annotation_service

    record_ids = _seed_core_lit(db, 1, prefix="flat-missing")
    _seed_pool_with_records(db, record_ids)
    annotator = make_user(db, "flat-missing-ann", role="annotator")

    from app.models import AnnotationSubmission, AnnotationTask, AnnotationTaskItem

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
    from app.models import LitMetadata

    db.query(LitMetadata).filter(LitMetadata.id == record_ids[0]).delete()
    db.commit()

    data = annotation_service.review_queue(db, page=1, page_size=20)
    assert data["total"] == 1
    assert len(data["items"]) == 1
    entry = data["items"][0]
    assert entry["core_missing"] is True
    assert entry["current_values"] == {}


# --- (b) 单条批准仍可用（MUST NOT DO：不动单条语义） --------------------------


def test_approve_applies_proposed_fields_to_core(client, db, admin):
    _annotator, _task_id, items, subs = _submit_batch(
        db, client, n=2, fields=[{"title": "批准后标题", "journal": "新期刊"}, {}], prefix="t8a"
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
    assert core.title == "批准后标题"
    assert core.journal == "新期刊"

    db.refresh(target_sub)
    assert target_sub.status == "approved"
    db.refresh(target_item)
    assert target_item.status == "approved"

    log = _log_for(db, "approve", target_sub.id)
    assert log.old_fields["title"] == "针灸治疗不孕症研究1"
    assert log.new_fields["title"] == "批准后标题"


def test_approve_reuses_update_record_side_effects(client, db, admin):
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
            journal="",
            pub_year="",
            abstract=None,
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
    assert core.crawl_status == "success"
    assert core.error_message is None


def test_stale_base_expires_one_item_others_independent(client, db, admin):
    from app.models import AnnotationPoolItem, LitMetadata
    from app.services import annotation_service

    _annotator, _task_id, items, subs = _submit_batch(
        db, client, n=2, fields=[{"title": "冲突稿"}, {"title": "正常稿"}], prefix="t8b"
    )
    stale_item, stale_sub = items[0], subs[0]
    fresh_sub = subs[1]

    db.execute(
        sa.update(LitMetadata).where(LitMetadata.id == stale_item.record_id).values(updated_at=NEWER_TS)
    )
    db.commit()

    resp = _approve(client, admin, stale_sub.id)
    assert resp.status_code == 200
    assert resp.json()["status"] == "expired"

    db.refresh(stale_sub)
    assert stale_sub.status == "expired"
    db.refresh(stale_item)
    assert stale_item.status == "expired"
    assert stale_item.rejected_at is None

    # 源池条目复位 available
    pool_item = (
        db.query(AnnotationPoolItem)
        .filter(
            AnnotationPoolItem.table_name == stale_item.table_name,
            AnnotationPoolItem.record_id == stale_item.record_id,
            AnnotationPoolItem.status == "available",
        )
        .one_or_none()
    )
    assert pool_item is not None
    # 该记录在 preview_pool 中回候选：eligible=true （R3T5 决议C 回候选实证）
    preview = annotation_service.preview_pool(db, "lit", {}, include_annotated=False, page=1, page_size=100)
    matched = [it for it in preview["items"] if it["record_id"] == stale_item.record_id]
    assert len(matched) == 1
    assert matched[0]["eligible"] is True

    expire_log = _log_for(db, "expire", stale_sub.id)
    assert expire_log.new_fields == {"reason": "base_conflict"}

    other_resp = _approve(client, admin, fresh_sub.id)
    assert other_resp.status_code == 200
    assert other_resp.json()["status"] == "approved"


def test_reject_stores_comment_and_moves_item_to_rework(client, db, admin):
    annotator, task_id, items, subs = _submit_batch(db, client, n=1, fields=[{"title": "驳回稿"}], prefix="t8c")
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
    db.refresh(target_item)
    assert target_item.status == "rejected"

    from datetime import timedelta

    from app.config import get_annotation_config
    from app.models import AnnotationTask

    reopened = db.get(AnnotationTask, task_id)
    assert reopened.status == "in_progress"
    expected_deadline = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        days=get_annotation_config().rework_days
    )
    assert reopened.deadline_at is not None
    assert abs(reopened.deadline_at - expected_deadline) < timedelta(minutes=1)

    log = _log_for(db, "reject", target_sub.id)
    assert log.new_fields == {"comment": "标题不规范，请重写"}


def test_reject_without_comment_400(client, db, admin):
    _annotator, _task_id, _items, subs = _submit_batch(db, client, n=1, fields=[{}], prefix="t8d")
    resp = _reject(client, admin, subs[0].id, "")
    assert resp.status_code == 400
    assert "驳回必须填写评论" in resp.json()["detail"]


def test_empty_diff_approve_skips_core_write(client, db, admin):
    from app.models import LitMetadata

    _annotator, _task_id, items, subs = _submit_batch(db, client, n=1, fields=[{}], prefix="t8e")
    target_item, target_sub = items[0], subs[0]
    before = db.get(LitMetadata, target_item.record_id)
    before_title, before_updated = before.title, before.updated_at

    resp = _approve(client, admin, target_sub.id)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    after = db.get(LitMetadata, target_item.record_id)
    assert after.title == before_title
    assert after.updated_at == before_updated

    log = _log_for(db, "approve", target_sub.id)
    assert log.old_fields == {}
    assert log.new_fields == {}


def test_double_approve_conflicts(client, db, admin):
    _annotator, _task_id, _items, subs = _submit_batch(
        db, client, n=1, fields=[{"title": "只批一次"}], prefix="t8f"
    )
    assert _approve(client, admin, subs[0].id).status_code == 200

    resp = _approve(client, admin, subs[0].id)
    assert resp.status_code == 409
    assert "该提交单状态为 approved，不可复核" in resp.json()["detail"]

    reject_resp = _reject(client, admin, subs[0].id, "再驳一次试试")
    assert reject_resp.status_code == 409


def test_non_admin_forbidden_on_review_endpoints(client, db, admin):
    plain = make_user(db, "plain-t8", role="normal")

    queue_resp = client.get(QUEUE_URL, headers=auth_header(plain))
    assert queue_resp.status_code == 403

    approve_resp = _approve(client, plain, 1)
    assert approve_resp.status_code == 403

    reject_resp = _reject(client, plain, 1, "x")
    assert reject_resp.status_code == 403


# --- (c) 批量通过：混合 approved/expired/error，不中断 -------------------------


def test_batch_approve_mixed_approved_expired_error(client, db, admin):
    from app.models import LitMetadata

    annotator, task_id, items, subs = _submit_batch(
        db,
        client,
        n=3,
        fields=[{"title": "正常一"}, {"title": "冲突二"}, {"title": "正常三"}],
        prefix="batch1",
    )
    # 制造第二条 base 冲突
    db.execute(
        sa.update(LitMetadata).where(LitMetadata.id == items[1].record_id).values(updated_at=NEWER_TS)
    )
    db.commit()

    bad_id = 999999
    resp = client.post(
        BATCH_APPROVE_URL,
        json={"submission_ids": [subs[0].id, subs[1].id, bad_id]},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    results = body["results"]
    assert len(results) == 3
    # 顺序与去重保序
    assert [r["submission_id"] for r in results] == [subs[0].id, subs[1].id, bad_id]
    by_id = {r["submission_id"]: r for r in results}
    assert by_id[subs[0].id]["status"] == "approved"
    assert by_id[subs[1].id]["status"] == "expired"
    assert by_id[bad_id]["status"] == "error"
    assert "detail" in by_id[bad_id]

    # 汇总断言（兼容 summary 扁平两种形态）
    summary = body.get("summary") or body
    assert summary.get("approved", body.get("approved")) == 1
    assert summary.get("expired", body.get("expired")) == 1
    assert summary.get("error", body.get("error")) == 1

    # 副作用验证
    db.refresh(subs[0])
    assert subs[0].status == "approved"
    from app.models import LitMetadata as LM

    core0 = db.get(LM, items[0].record_id)
    assert core0.title == "正常一"

    db.refresh(subs[1])
    assert subs[1].status == "expired"
    db.refresh(items[1])
    assert items[1].status == "expired"
    assert items[1].rejected_at is None
    from app.models import AnnotationPoolItem as _API

    _pool_item = (
        db.query(_API)
        .filter(
            _API.table_name == items[1].table_name,
            _API.record_id == items[1].record_id,
            _API.status == "available",
        )
        .one_or_none()
    )
    assert _pool_item is not None
    from app.services import annotation_service as _svc

    _preview = _svc.preview_pool(db, "lit", {}, include_annotated=False, page=1, page_size=100)
    _matched = [it for it in _preview["items"] if it["record_id"] == items[1].record_id]
    assert len(_matched) == 1
    assert _matched[0]["eligible"] is True

    # 错误条不中断他条：正常三仍可单独批
    resp2 = client.post(
        BATCH_APPROVE_URL,
        json={"submission_ids": [subs[2].id]},
        headers=auth_header(admin),
    )
    assert resp2.status_code == 200
    assert resp2.json()["results"][0]["status"] == "approved"


def test_batch_approve_dedup_preserves_order(client, db, admin):
    _ann, _tid, items, subs = _submit_batch(
        db, client, n=2, fields=[{"title": "去重稿1"}, {"title": "去重稿2"}], prefix="batch2"
    )
    resp = client.post(
        BATCH_APPROVE_URL,
        json={"submission_ids": [subs[0].id, subs[0].id, subs[1].id, subs[0].id]},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    # 去重保序：应只有 2 条
    assert len(results) == 2
    assert [r["submission_id"] for r in results] == [subs[0].id, subs[1].id]
    assert all(r["status"] == "approved" for r in results)


def test_batch_approve_empty_list_400(client, db, admin):
    resp = client.post(BATCH_APPROVE_URL, json={"submission_ids": []}, headers=auth_header(admin))
    assert resp.status_code == 400


def test_batch_approve_non_admin_403(client, db, admin):
    plain = make_user(db, "plain-batch", role="normal")
    resp = client.post(BATCH_APPROVE_URL, json={"submission_ids": [1]}, headers=auth_header(plain))
    assert resp.status_code == 403


# --- (d) 批量驳回：全部 rejected + 空 comment 单条 error -------------------------


def test_batch_reject_all_rejected_and_empty_comment_error(client, db, admin):
    _ann, task_id, items, subs = _submit_batch(
        db,
        client,
        n=3,
        fields=[{"title": "驳回1"}, {"title": "驳回2"}, {"title": "驳回3"}],
        prefix="batch3",
    )
    resp = client.post(
        BATCH_REJECT_URL,
        json={
            "decisions": [
                {"submission_id": subs[0].id, "comment": "意见一"},
                {"submission_id": subs[1].id, "comment": ""},
                {"submission_id": subs[2].id, "comment": "意见三"},
            ]
        },
        headers=auth_header(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    results = body["results"]
    assert len(results) == 3
    by_id = {r["submission_id"]: r for r in results}
    assert by_id[subs[0].id]["status"] == "rejected"
    assert by_id[subs[2].id]["status"] == "rejected"
    assert by_id[subs[1].id]["status"] == "error"
    assert "驳回必须填写评论" in by_id[subs[1].id].get("detail", "")

    # 成功条进返工箱
    db.refresh(subs[0])
    assert subs[0].status == "rejected"
    db.refresh(items[0])
    assert items[0].status == "rejected"
    assert items[0].rejected_at is not None
    db.refresh(subs[2])
    assert subs[2].status == "rejected"
    # 空 comment 条保持 pending 未被驳回
    db.refresh(subs[1])
    assert subs[1].status == "pending"

    summary = body.get("summary") or body
    # 兼容两种汇总形态
    rejected_cnt = summary.get("rejected", body.get("rejected", 0))
    error_cnt = summary.get("error", body.get("error", 0))
    assert rejected_cnt == 2
    assert error_cnt == 1


def test_batch_reject_empty_list_400(client, db, admin):
    resp = client.post(BATCH_REJECT_URL, json={"decisions": []}, headers=auth_header(admin))
    assert resp.status_code == 400


def test_batch_reject_non_admin_403(client, db, admin):
    plain = make_user(db, "plain-batch-rej", role="normal")
    resp = client.post(
        BATCH_REJECT_URL,
        json={"decisions": [{"submission_id": 1, "comment": "x"}]},
        headers=auth_header(plain),
    )
    assert resp.status_code == 403


def test_batch_reject_error_does_not_interrupt_others(client, db, admin):
    _ann, _tid, items, subs = _submit_batch(
        db, client, n=2, fields=[{"title": "r1"}, {"title": "r2"}], prefix="batch4"
    )
    bad_id = 888888
    resp = client.post(
        BATCH_REJECT_URL,
        json={
            "decisions": [
                {"submission_id": subs[0].id, "comment": "ok"},
                {"submission_id": bad_id, "comment": "also"},
                {"submission_id": subs[1].id, "comment": "ok2"},
            ]
        },
        headers=auth_header(admin),
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 3
    by_id = {r["submission_id"]: r for r in results}
    assert by_id[subs[0].id]["status"] == "rejected"
    assert by_id[bad_id]["status"] == "error"
    assert by_id[subs[1].id]["status"] == "rejected"
