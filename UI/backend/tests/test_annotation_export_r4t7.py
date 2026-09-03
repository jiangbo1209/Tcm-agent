"""RED-first for R4T7: workload CSV must contain record_id and title columns.

 lit row has real title, case row fallback is 病案#<id>.
 spec: header contains record_id + title after record_id, order date,username,table_name,record_id,title,item_status,review_outcome
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.utils import auth_header, make_user

CORE_TS = datetime(2026, 1, 15, 8, 0, 0)
EXPORT_URL = "/api/annotation/admin/export.csv"


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
    return make_user(db, "r4t7-admin", role="admin")


def _seed_lit(db, n=1, prefix="r4t7-lit"):
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
    return [
        r.id
        for r in db.query(LitMetadata)
        .filter(LitMetadata.file_uuid.like(f"{prefix}-%"))
        .order_by(LitMetadata.id)
        .all()
    ]


def _seed_case(db, n=1, prefix="r4t7-case"):
    from app.models import MedCase

    for i in range(1, n + 1):
        db.add(
            MedCase(
                file_uuid=f"{prefix}-u{i}",
                western_diagnosis="不孕",
                created_at=CORE_TS,
                updated_at=CORE_TS,
            )
        )
    db.commit()
    # filter by file_uuid prefix
    return [
        r.id
        for r in db.query(MedCase)
        .filter(MedCase.file_uuid.like(f"{prefix}-%"))
        .order_by(MedCase.id)
        .all()
    ]


def _seed_pool(db, record_ids, table_name="lit", priority=0):
    from app.models import AnnotationPool, AnnotationPoolItem

    pool = AnnotationPool(table_name=table_name, filter_json={}, status="active", priority=priority)
    db.add(pool)
    db.flush()
    db.add_all(
        [
            AnnotationPoolItem(pool_id=pool.id, table_name=table_name, record_id=rid, status="available")
            for rid in record_ids
        ]
    )
    db.commit()
    return pool


def _claim(client, annotator):
    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))
    assert resp.status_code == 200, resp.text
    return resp.json()["task_id"]


def test_export_csv_contains_record_id_and_title(client, db, admin):
    """RED: header must contain record_id and title; lit has real title, case fallback."""
    lit_ids = _seed_lit(db, 1, prefix="r4t7-a-lit")
    case_ids = _seed_case(db, 1, prefix="r4t7-a-case")
    from app.models import LitMetadata

    lit_title_val = db.query(LitMetadata).filter(LitMetadata.id == lit_ids[0]).one().title

    _seed_pool(db, lit_ids, table_name="lit", priority=5)
    _seed_pool(db, case_ids, table_name="case", priority=0)

    ann_a = make_user(db, "r4t7-ann-a", role="annotator")
    ann_b = make_user(db, "r4t7-ann-b", role="annotator")
    _claim(client, ann_a)
    _claim(client, ann_b)

    resp = client.get(EXPORT_URL, headers=auth_header(admin))
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert resp.headers["content-disposition"] == 'attachment; filename="workload.csv"'

    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    header = rows[0]
    # header must contain record_id and title, title immediately after record_id
    assert "record_id" in header, f"header missing record_id: {header}"
    assert "title" in header, f"header missing title: {header}"
    # order: ... table_name, record_id, title, item_status ...
    assert header == ["date", "username", "table_name", "record_id", "title", "item_status", "review_outcome"], f"header order wrong: {header}"

    # there should be 2 data rows
    data = rows[1:]
    assert len(data) == 2, f"expected 2 rows got {len(data)}: {data}"
    # build map by table_name
    by_table = {row[2]: row for row in data}
    # lit row
    lit_row = by_table["lit"]
    # columns: 0 date,1 username,2 table_name,3 record_id,4 title,5 item_status,6 review_outcome
    assert int(lit_row[3]) == lit_ids[0]
    assert lit_row[4] == lit_title_val, f"lit title mismatch got {lit_row[4]!r} expected {lit_title_val!r}"
    # case row fallback
    case_row = by_table["case"]
    assert int(case_row[3]) == case_ids[0]
    assert case_row[4] == f"病案#{case_ids[0]}", f"case fallback wrong got {case_row[4]!r}"
