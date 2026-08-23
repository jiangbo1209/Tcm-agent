"""Schema tests for the six annotation ORM tables.

Pure ORM-level checks (no HTTP): metadata registration, create_all on
in-memory SQLite, FK/unique-constraint shape, JSON variant columns,
server defaults, and a full FK-chain insert roundtrip.

Reuses ``tests.utils.make_db`` (StaticPool in-memory SQLite) instead of a
local engine fixture, per the shared test-infrastructure convention.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.models import (
    AnnotationLog,
    AnnotationPool,
    AnnotationPoolItem,
    AnnotationSubmission,
    AnnotationTask,
    AnnotationTaskItem,
    Base,
)
from tests.utils import make_db


@pytest.fixture()
def db():
    """In-memory SQLite session carrying the full registered schema."""
    with make_db() as session:
        yield session

NEED_TABLES = {
    "annotation_pools",
    "annotation_pool_items",
    "annotation_tasks",
    "annotation_task_items",
    "annotation_submissions",
    "annotation_logs",
}


def test_six_tables_registered_in_metadata():
    """AC: importing app.models registers all six annotation tables."""
    import app.models  # noqa: F401  (explicit for test readability)

    missing = NEED_TABLES - set(Base.metadata.tables)
    assert not missing, f"tables not registered via app.models import: {missing}"


def test_json_columns_use_portable_variant():
    """JSON cols must be JSON().with_variant(JSONB(), 'postgresql'), never bare JSONB."""
    from sqlalchemy import JSON
    from sqlalchemy.dialects import postgresql, sqlite
    from sqlalchemy.dialects.postgresql import JSONB

    json_columns = [
        AnnotationPool.__table__.c.filter_json,
        AnnotationSubmission.__table__.c.proposed_fields,
        AnnotationLog.__table__.c.old_fields,
        AnnotationLog.__table__.c.new_fields,
    ]
    for col in json_columns:
        assert isinstance(col.type, JSON), f"{col}: base type must be generic JSON"
        pg_impl = col.type.dialect_impl(postgresql.dialect())
        assert isinstance(pg_impl, JSONB), f"{col}: postgresql variant must be JSONB"
        sqlite_impl = col.type.dialect_impl(sqlite.dialect())
        assert not isinstance(sqlite_impl, JSONB), f"{col}: sqlite must stay plain JSON"


def test_foreign_key_ondelete_shapes():
    """Every FK carries the spec'd ondelete action."""
    fks = {
        ("annotation_pools", "created_by"): "SET NULL",
        ("annotation_pool_items", "pool_id"): "CASCADE",
        ("annotation_tasks", "pool_id"): "SET NULL",
        ("annotation_tasks", "claimed_by"): "SET NULL",
        ("annotation_task_items", "task_id"): "CASCADE",
        ("annotation_submissions", "item_id"): "CASCADE",
        ("annotation_submissions", "annotator_id"): "SET NULL",
        ("annotation_submissions", "reviewer_id"): "SET NULL",
        ("annotation_logs", "actor_id"): "SET NULL",
        ("annotation_logs", "submission_id"): "SET NULL",
    }
    for (table, col_name), expected in fks.items():
        col = Base.metadata.tables[table].columns[col_name]
        assert len(col.foreign_keys) == 1, f"{table}.{col_name} must have exactly one FK"
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete == expected, (
            f"{table}.{col_name}: expected ondelete={expected}, got {fk.ondelete}"
        )


def test_unique_constraints_present():
    pool_cols = [
        sorted(c.name for c in uc.columns)
        for uc in Base.metadata.tables["annotation_pool_items"].constraints
        if isinstance(uc, UniqueConstraint)
    ]
    task_cols = [
        sorted(c.name for c in uc.columns)
        for uc in Base.metadata.tables["annotation_task_items"].constraints
        if isinstance(uc, UniqueConstraint)
    ]
    assert ["pool_id", "record_id", "table_name"] in pool_cols
    assert ["record_id", "task_id"] in task_cols


def test_source_pool_item_id_is_plain_integer_no_fk():
    """source_pool_item_id is deliberately a loose reference (no FK)."""
    col = Base.metadata.tables["annotation_task_items"].columns["source_pool_item_id"]
    assert col.foreign_keys == set()
    assert col.nullable is True


def _seed_chain(db):
    """Insert one full FK chain: user -> pool -> item -> task -> item -> submission -> log."""
    from app.models.user import User

    user = User(
        username="annotator1",
        email="a1@test.local",
        hashed_password="x",
        role="professional",
    )
    db.add(user)
    db.flush()

    pool = AnnotationPool(table_name="lit_metadata", filter_json={"source_site": "cnki"})
    db.add(pool)
    db.flush()

    item = AnnotationPoolItem(pool_id=pool.id, table_name="lit_metadata", record_id=101)
    db.add(item)
    db.flush()

    task = AnnotationTask(pool_id=pool.id, claimed_by=user.id)
    db.add(task)
    db.flush()

    titem = AnnotationTaskItem(
        task_id=task.id,
        table_name="lit_metadata",
        record_id=101,
        source_pool_item_id=item.id,
    )
    db.add(titem)
    db.flush()

    sub = AnnotationSubmission(
        item_id=titem.id,
        annotator_id=user.id,
        username=user.username,
        proposed_fields={"title": "新标题"},
        base_updated_at=datetime(2026, 8, 23, 12, 0, 0),
    )
    db.add(sub)
    db.flush()

    log = AnnotationLog(
        table_name="lit_metadata",
        record_id=101,
        actor_id=user.id,
        username=user.username,
        action="submit",
        old_fields={"title": "旧标题"},
        new_fields={"title": "新标题"},
        submission_id=sub.id,
    )
    db.add(log)
    db.commit()
    return user, pool, item, task, titem, sub, log


def test_full_chain_roundtrip_with_defaults(db):
    user, pool, item, task, titem, sub, log = _seed_chain(db)

    # Python-side column defaults applied by the ORM.
    assert pool.status == "active"
    assert pool.priority == 0
    assert item.status == "available"
    assert task.status == "open"
    assert titem.status == "pending"
    assert sub.status == "draft"

    # Server-side timestamps materialized after flush.
    for obj in (pool, item, task, titem, sub, log):
        assert obj.created_at is not None

    # Snapshot username columns persisted.
    assert sub.username == "annotator1"
    assert log.username == "annotator1"

    # JSON payloads round-trip intact.
    assert pool.filter_json == {"source_site": "cnki"}
    assert sub.proposed_fields == {"title": "新标题"}
    assert log.old_fields == {"title": "旧标题"}
    assert log.new_fields == {"title": "新标题"}

    # Reload through a fresh query to prove persistence.
    got = db.query(AnnotationPool).filter_by(table_name="lit_metadata").one()
    assert got.id == pool.id


def test_updated_at_onupdate_fires(db):
    past = datetime(2020, 1, 1)
    pool = AnnotationPool(
        table_name="case_metadata",
        filter_json={},
        created_at=past,
        updated_at=past,
    )
    db.add(pool)
    db.commit()
    assert pool.updated_at == past

    pool.status = "closed"
    db.commit()
    db.refresh(pool)
    assert pool.updated_at > past, "onupdate=func.now() must bump updated_at"


def test_pool_item_duplicate_rejected_by_unique_constraint(db):
    pool = AnnotationPool(table_name="lit_metadata", filter_json={})
    db.add(pool)
    db.flush()
    db.add(AnnotationPoolItem(pool_id=pool.id, table_name="lit_metadata", record_id=7))
    db.commit()

    db.add(AnnotationPoolItem(pool_id=pool.id, table_name="lit_metadata", record_id=7))
    with pytest.raises(IntegrityError):
        db.commit()


def test_task_item_duplicate_same_record_rejected(db):
    task = AnnotationTask()
    db.add(task)
    db.flush()
    db.add(AnnotationTaskItem(task_id=task.id, table_name="med_case", record_id=3))
    db.commit()

    db.add(AnnotationTaskItem(task_id=task.id, table_name="med_case", record_id=3))
    with pytest.raises(IntegrityError):
        db.commit()
