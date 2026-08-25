"""R4T8 我的标注历史 RED-first： annotator 只读分页，查自己全部 submissions。

cover:
- 同一 annotator 三条(approved/rejected/draft) total=3, status/ title / id desc
- 另一 annotator 的提交不出现
- 分页 page_size=2 第二页拿到剩余
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.utils import auth_header, make_user

CORE_TS = datetime(2026, 1, 15, 8, 0, 0)


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

    app = FastAPI()
    app.include_router(annotation_router)
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


HISTORY_URL = "/api/annotation/my/history"


def _seed_case(db, idx: int) -> int:
    from app.models import MedCase

    # case has no title column -> will fallback to 病案#id
    case = MedCase(
        file_uuid=f"hist-case-{idx}",
        age="30",
        created_at=CORE_TS,
        updated_at=CORE_TS,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case.id


def _seed_lit(db, idx: int, title: str) -> int:
    from app.models import LitMetadata

    lit = LitMetadata(
        file_uuid=f"hist-lit-{idx}",
        original_name=f"lit{idx}.pdf",
        storage_path=f"lit/hist-lit-{idx}/lit{idx}.pdf",
        cleaned_title=title,
        title=title,
        authors=["张三"],
        keywords=["中医"],
        source_site="cnki",
        journal="中医杂志",
        pub_year="2024",
        matched_title=title,
        crawl_status="success",
        created_at=CORE_TS,
        updated_at=CORE_TS,
    )
    db.add(lit)
    db.commit()
    db.refresh(lit)
    return lit.id


def _seed_history_via_direct_insert(db, annotator, items_with_status):
    """items_with_status: list of (table_name, record_id, status)"""
    from app.models import AnnotationSubmission, AnnotationTask, AnnotationTaskItem

    ids = []
    for table_name, record_id, status in items_with_status:
        task = AnnotationTask(pool_id=None, claimed_by=annotator.id, status="completed")
        db.add(task)
        db.flush()
        item = AnnotationTaskItem(
            task_id=task.id,
            table_name=table_name,
            record_id=record_id,
            status="submitted" if status in ("approved", "rejected", "pending", "expired") else status,
        )
        db.add(item)
        db.flush()
        sub = AnnotationSubmission(
            item_id=item.id,
            annotator_id=annotator.id,
            username=annotator.username,
            proposed_fields={"title": f"pf-{record_id}"},
            base_updated_at=CORE_TS,
            status=status,
            reviewed_at=_naive_utcnow() if status in ("approved", "rejected") else None,
            review_comment="ok" if status == "approved" else ("bad" if status == "rejected" else None),
        )
        db.add(sub)
        db.flush()
        ids.append(sub.id)
    db.commit()
    return ids


def test_my_history_basic_and_isolation_and_order_and_title(client, db):
    # annotator A has lit (real title) + case (fallback) + lit-pending
    annotator = make_user(db, "hist-a", role="annotator")
    other = make_user(db, "hist-other", role="annotator")

    lit_id1 = _seed_lit(db, 101, "针灸治疗A")
    lit_id2 = _seed_lit(db, 102, "针灸治疗B")
    case_id = _seed_case(db, 201)

    # create 3 submissions for annotator: approved, rejected, draft across lit/case
    _seed_history_via_direct_insert(
        db,
        annotator,
        [
            ("lit", lit_id1, "approved"),
            ("case", case_id, "rejected"),
            ("lit", lit_id2, "draft"),
        ],
    )
    # other annotator one submission - should not appear
    _seed_history_via_direct_insert(db, other, [("lit", lit_id1, "approved")])

    resp = client.get(HISTORY_URL, headers=auth_header(annotator))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert len(data["items"]) == 3
    # id desc
    ids = [it["submission_id"] for it in data["items"]]
    assert ids == sorted(ids, reverse=True)
    # status set
    statuses = {it["status"] for it in data["items"]}
    assert statuses == {"approved", "rejected", "draft"}
    # title: lit真标题, case兜底 病案#{record_id}
    by_status = {it["status"]: it for it in data["items"]}
    assert by_status["approved"]["title"] == "针灸治疗A"
    assert by_status["draft"]["title"] == "针灸治疗B"
    assert by_status["rejected"]["title"] == f"病案#{case_id}"
    # fields per spec
    for it in data["items"]:
        assert "record_id" in it and "table_name" in it and "title" in it
        assert "submission_id" in it and "status" in it
        assert "proposed_fields" in it
        assert "submitted_at" in it  # may be null
        assert "reviewed_at" in it
        assert "review_comment" in it
    # other not leaked
    resp2 = client.get(HISTORY_URL, headers=auth_header(other))
    assert resp2.json()["total"] == 1

    # non-annotator 403
    normal = make_user(db, "hist-normal", role="normal")
    resp3 = client.get(HISTORY_URL, headers=auth_header(normal))
    assert resp3.status_code == 403


def test_my_history_pagination(client, db):
    annotator = make_user(db, "hist-page", role="annotator")
    lit_ids = [_seed_lit(db, 200 + i, f"分页标题{i}") for i in range(5)]
    _seed_history_via_direct_insert(
        db,
        annotator,
        [("lit", rid, "pending") for rid in lit_ids],
    )
    # page 1 size 2
    r1 = client.get(HISTORY_URL + "?page=1&page_size=2", headers=auth_header(annotator))
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] == 5
    assert len(d1["items"]) == 2
    r2 = client.get(HISTORY_URL + "?page=2&page_size=2", headers=auth_header(annotator))
    assert len(r2.json()["items"]) == 2
    r3 = client.get(HISTORY_URL + "?page=3&page_size=2", headers=auth_header(annotator))
    assert len(r3.json()["items"]) == 1
    # all ids covered without overlap via id desc order
    all_ids = d1["items"] + r2.json()["items"] + r3.json()["items"]
    sids = [it["submission_id"] for it in all_ids]
    assert len(set(sids)) == 5
    assert sids == sorted(sids, reverse=True)

    # validation: page_size >100 -> 422
    bad = client.get(HISTORY_URL + "?page_size=101", headers=auth_header(annotator))
    assert bad.status_code == 422


def test_my_history_gate_503(monkeypatch, db):
    # when disabled gate returns 503
    monkeypatch.setenv("ANNOTATION_ENABLED", "false")
    get_settings.cache_clear()
    from app.core.database import get_db
    from app.routers.annotation import router as annotation_router

    app = FastAPI()
    app.include_router(annotation_router)
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    annot = make_user(db, "hist-gate", role="annotator")
    r = c.get(HISTORY_URL, headers=auth_header(annot))
    assert r.status_code == 503
    get_settings.cache_clear()
