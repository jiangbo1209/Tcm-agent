from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    CoreFile,
    Edge,
    GraphBase,
    LitMetadata,
    MedCase,
    Node,
)
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories.admin_repo import AdminQueryRepository, StaleRecordError
from app.services.admin_service import AdminService

TS = datetime(2026, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
STALE_TS = "2025-06-01T00:00:00+00:00"


def _make_lit(**overrides):
    kwargs = dict(
        id=1,
        file_uuid="u1",
        original_name="a.pdf",
        storage_path="lit/u1/a.pdf",
        cleaned_title="T",
        title="T",
        authors=["张三"],
        keywords=["中医"],
        paper_type="期刊论文",
        source_site="cnki",
        journal="中医杂志",
        pub_year="2026",
        matched_title="T",
        is_exact_match=True,
        crawl_status="success",
        created_at=TS,
        updated_at=TS,
    )
    kwargs.update(overrides)
    return LitMetadata(**kwargs)


@pytest.fixture()
def engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    GraphBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(engine):
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _seed_cascade_rows(session):
    session.add(
        CoreFile(
            file_uuid="u1",
            original_name="a.pdf",
            storage_path="lit/u1/a.pdf",
            upload_time=TS,
        )
    )
    session.add(_make_lit())
    session.add(MedCase(id=1, file_uuid="u1", created_at=TS, updated_at=TS))
    session.add(
        Node(
            id="pn",
            node_type="paper",
            title="T",
            metric_value=2020,
            top_k_value=1.0,
            created_at=TS,
            updated_at=TS,
        )
    )
    session.add(
        Edge(
            id="e1",
            source_id="pn",
            target_id="other",
            edge_type="paper-paper",
            similarity_score=1.0,
            created_at=TS,
            updated_at=TS,
        )
    )
    session.commit()


def test_delete_lit_cascade(session, monkeypatch):
    _seed_cascade_rows(session)
    monkeypatch.setattr(AdminService, "_remove_s3", lambda self, path: None)

    svc = AdminService(session)
    res = svc.delete_lit(1)

    assert res == {"deleted": True, "id": 1, "file_uuid": "u1"}
    assert session.get(LitMetadata, 1) is None
    assert session.get(CoreFile, "u1") is None
    assert session.get(MedCase, 1) is None
    assert session.get(Node, "pn") is None
    assert session.get(Edge, "e1") is None


def test_update_record_stale_conflict(session):
    session.add(_make_lit())
    session.commit()

    repo = AdminQueryRepository(session)
    with pytest.raises(StaleRecordError):
        repo.update_record("lit", 1, {"title": "新标题"}, updated_at=STALE_TS)

    session.expire_all()
    assert session.get(LitMetadata, 1).title == "T"


@pytest.mark.skip(reason="需 PG 起后端")
def test_admin_http_regression():
    """真实 GET /api/admin/* 回归需 PostgreSQL 后端，占位跳过。"""
