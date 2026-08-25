"""R4T2 RED-first 后端隔离测试：驳回→重做→重提交后复核队列可见性."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.utils import auth_header, make_user

CORE_TS = datetime(2026, 1, 15, 8, 0, 0)


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


def _seed_core_lit(db, n: int, *, prefix: str = "r4t2") -> list[int]:
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
    return [r.id for r in db.query(LitMetadata).order_by(LitMetadata.id).all()]


def _seed_pool(db, record_ids: list[int]):
    from app.models import AnnotationPool, AnnotationPoolItem

    pool = AnnotationPool(table_name="lit", filter_json={}, status="active", priority=0)
    db.add(pool)
    db.flush()
    db.add_all(
        [
            AnnotationPoolItem(pool_id=pool.id, table_name="lit", record_id=rid, status="available")
            for rid in record_ids
        ]
    )
    db.commit()
    return pool


def _claim(client, annotator) -> int:
    r = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))
    assert r.status_code == 200, r.text
    return r.json()["task_id"]


def _items(db, task_id: int):
    from app.models import AnnotationTaskItem

    return db.query(AnnotationTaskItem).filter(AnnotationTaskItem.task_id == task_id).order_by(AnnotationTaskItem.id).all()


def _draft(client, annotator, item_id: int, fields: dict):
    return client.put(f"/api/annotation/items/{item_id}/draft", json={"proposed_fields": fields}, headers=auth_header(annotator))


def test_rework_resubmit_reappears_in_review_queue(client, db):
    """领2条→draft→整批提交→驳回1条→重做被驳条目→再提交→复核队列含新pending且旧rejected不出现."""
    from app.models import AnnotationSubmission, AnnotationTask, AnnotationTaskItem
    from app.services import annotation_service

    record_ids = _seed_core_lit(db, 2, prefix="r4t2-rework")
    _seed_pool(db, record_ids)
    annotator = make_user(db, "r4t2-annot1", role="annotator")
    admin = make_user(db, "r4t2-admin1", role="admin")

    task_id = _claim(client, annotator)
    items = _items(db, task_id)
    assert len(items) == 2
    item_a, item_b = items[0], items[1]

    # 全部 draft 并整批提交 -> 2 pending
    assert _draft(client, annotator, item_a.id, {"title": "稿A"}).status_code == 200
    assert _draft(client, annotator, item_b.id, {"title": "稿B"}).status_code == 200
    r = client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))
    assert r.status_code == 200, r.text
    assert db.get(AnnotationTask, task_id).status == "completed"

    # 捕获2条 pending 提交单
    subs_a = db.query(AnnotationSubmission).filter(AnnotationSubmission.item_id == item_a.id).order_by(AnnotationSubmission.id).all()
    subs_b = db.query(AnnotationSubmission).filter(AnnotationSubmission.item_id == item_b.id).order_by(AnnotationSubmission.id).all()
    assert len(subs_a) == 1 and subs_a[0].status == "pending"
    assert len(subs_b) == 1 and subs_b[0].status == "pending"
    pending_a_id_old = subs_a[0].id
    pending_b_id = subs_b[0].id

    # queue 初始 2 pending
    q0 = annotation_service.review_queue(db, page=1, page_size=20)
    assert q0["total"] == 2
    assert {x["submission_id"] for x in q0["items"]} == {pending_a_id_old, pending_b_id}

    # admin 驳回 item_a
    from app.services.annotation_service import reject_submission

    rej = reject_submission(db, admin, pending_a_id_old, "标题不规范")
    assert rej["status"] == "rejected"
    db.refresh(item_a)
    assert item_a.status == "rejected"
    db.refresh(db.get(AnnotationTask, task_id))
    assert db.get(AnnotationTask, task_id).status == "in_progress"

    # 驳回后 queue 仅剩 item_b 的 pending
    q1 = annotation_service.review_queue(db, page=1, page_size=20)
    assert q1["total"] == 1, f"驳回后应剩1条 pending, got {q1}"
    assert q1["items"][0]["submission_id"] == pending_b_id
    assert pending_a_id_old not in {x["submission_id"] for x in q1["items"]}

    # 标注员重做被驳条目：item_draft 应新建行，旧 rejected 保留
    dr = _draft(client, annotator, item_a.id, {"title": "稿A-返工"})
    assert dr.status_code == 200, dr.text
    new_sub_id = dr.json()["submission_id"]
    assert new_sub_id != pending_a_id_old, "rejected→新建行，id 不应复用"

    all_subs_a = db.query(AnnotationSubmission).filter(AnnotationSubmission.item_id == item_a.id).order_by(AnnotationSubmission.id).all()
    assert len(all_subs_a) == 2
    assert all_subs_a[0].id == pending_a_id_old and all_subs_a[0].status == "rejected"
    assert all_subs_a[1].id == new_sub_id and all_subs_a[1].status == "draft"
    db.refresh(item_a)
    assert item_a.status == "drafted"

    # queue 仍只有 item_b 的 pending（draft 尚未进队列）
    q2 = annotation_service.review_queue(db, page=1, page_size=20)
    assert q2["total"] == 1
    assert q2["items"][0]["submission_id"] == pending_b_id

    # 再次整批提交
    r2 = client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))
    assert r2.status_code == 200, r2.text
    assert r2.json()["completed"] is True
    assert db.get(AnnotationTask, task_id).status == "completed"
    db.refresh(item_a)
    assert item_a.status == "submitted"
    db.refresh(db.get(AnnotationSubmission, new_sub_id))
    assert db.get(AnnotationSubmission, new_sub_id).status == "pending"

    # 最终断言：queue 含新 pending，且旧 rejected 不出现；并保持另一条 pending
    q3 = annotation_service.review_queue(db, page=1, page_size=20)
    ids = {x["submission_id"] for x in q3["items"]}
    assert new_sub_id in ids, f"重提交后新 pending {new_sub_id} 应在队列, got {ids}"
    assert pending_a_id_old not in ids, f"旧 rejected {pending_a_id_old} 不应出现在 pending 队列"
    # 另一条未驳回的 pending 仍在（服务层语义：drafted/submitted 原样保留）
    assert pending_b_id in ids, "未驳回条目的 pending 应仍在队列"
    assert q3["total"] == 2, f"最终应有 2 pending (重做1条+未驳1条), got {q3['total']}"

    # via HTTP 也应可见
    http_q = client.get("/api/annotation/admin/review/queue", params={"page": 1, "page_size": 20}, headers=auth_header(admin))
    assert http_q.status_code == 200
    http_ids = {x["submission_id"] for x in http_q.json()["items"]}
    assert new_sub_id in http_ids
    assert pending_a_id_old not in http_ids
