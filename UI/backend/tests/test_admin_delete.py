"""Regression: delete_lit 级联完整性 — 覆盖 MedCase / Guideline / Node+Edge 三种关联。

复现 PG 严格 FK 场景：若先删 CoreFile 父表再删子表，IntegrityError → 500。
修复后顺序：MedCase → GuidelineMetadata → Node/Edge → LitMetadata → CoreFile，
并且 file_uuid 相同的 GuidelineMetadata 必须一并清理。

沿用 tests/utils.py 与 test_annotation_*.py 约定：
- 之所以显式传 created_at/updated_at：lit/guideline/case/graph 表的 server_default 为 text("NOW()")，SQLite 无此函数，显式时间戳可规避。
- 仅覆盖 get_db 语义在此不需要；直接测 AdminService.delete_lit 事务完整性，S3 通过 monkeypatch 静默。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models.annotation  # noqa: F401  ensure Base chain registered (see tests/utils.py)
import app.models.conversation  # noqa: F401
import app.models.conversation_memory  # noqa: F401
import app.models.message  # noqa: F401
import app.models.search_history  # noqa: F401
import app.models.user  # noqa: F401

from app.models import Base, CoreFile, Edge, GraphBase, GuidelineMetadata, LitMetadata, MedCase, Node
from app.services.admin_service import AdminDeleteRecordNotFound, AdminService

TS = datetime(2026, 1, 15, 8, 0, 0, tzinfo=timezone.utc)


def _strip_now_defaults(metadata) -> None:
    for tbl in metadata.tables.values():
        for col in tbl.columns:
            try:
                sd = col.server_default
            except Exception:
                sd = None
            if sd is not None:
                try:
                    txt = str(sd.arg) if hasattr(sd, "arg") else str(sd)
                except Exception:
                    txt = ""
                if "NOW()" in txt:
                    col.server_default = None
            try:
                ou = col.onupdate
            except Exception:
                ou = None
            if ou is not None:
                try:
                    otxt = str(ou.arg) if hasattr(ou, "arg") else str(ou)
                except Exception:
                    otxt = ""
                if "NOW()" in otxt:
                    col.onupdate = None


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


def _make_guideline(**overrides):
    kwargs = dict(
        id=1,
        file_uuid="u1",
        original_name="a.pdf",
        storage_path="lit/u1/a.pdf",
        cleaned_title="T",
        title="T",
        authors=["张三"],
        keywords=["中医"],
        paper_type="指南",
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
    return GuidelineMetadata(**kwargs)


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    _strip_now_defaults(Base.metadata)
    _strip_now_defaults(GraphBase.metadata)
    Base.metadata.create_all(eng)
    GraphBase.metadata.create_all(eng)
    # 强制外键约束，贴近 PG 严格 FK 行为；若子表未清先删父表会直接抛 IntegrityError
    from sqlalchemy import event

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # 需在 pragma 生效后重建连接生效，复用同一内存库时新建 session 即可
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _seed_core_lit(session, **lit_overrides):
    session.add(
        CoreFile(
            file_uuid="u1",
            original_name="a.pdf",
            storage_path="lit/u1/a.pdf",
            upload_time=TS,
        )
    )
    session.add(_make_lit(**lit_overrides))
    session.commit()


def test_delete_lit_with_medcase_cascade(session, monkeypatch):
    _seed_core_lit(session)
    session.add(MedCase(id=10, file_uuid="u1", created_at=TS, updated_at=TS))
    session.add(MedCase(id=11, file_uuid="u1", created_at=TS, updated_at=TS))
    session.commit()
    monkeypatch.setattr(AdminService, "_remove_s3", lambda self, path: None)

    res = AdminService(session).delete_lit(1)

    assert res == {"deleted": True, "id": 1, "file_uuid": "u1"}
    assert session.get(LitMetadata, 1) is None
    assert session.get(CoreFile, "u1") is None
    assert session.query(MedCase).filter(MedCase.file_uuid == "u1").count() == 0
    assert session.get(MedCase, 10) is None
    assert session.get(MedCase, 11) is None


def test_delete_lit_with_guideline_cascade(session, monkeypatch):
    _seed_core_lit(session)
    session.add(_make_guideline(id=1, file_uuid="u1"))
    session.commit()
    monkeypatch.setattr(AdminService, "_remove_s3", lambda self, path: None)

    res = AdminService(session).delete_lit(1)

    assert res["file_uuid"] == "u1"
    assert session.get(LitMetadata, 1) is None
    assert session.get(GuidelineMetadata, 1) is None
    assert session.query(GuidelineMetadata).filter(GuidelineMetadata.file_uuid == "u1").count() == 0
    assert session.get(CoreFile, "u1") is None


def test_delete_lit_with_graph_node_edge_cascade(session, monkeypatch):
    _seed_core_lit(session)
    session.add(
        Node(
            id="pn-graph",
            node_type="paper",
            title="T",
            metric_value=2020,
            top_k_value=1.0,
            created_at=TS,
            updated_at=TS,
        )
    )
    session.add(
        Node(
            id="other-node",
            node_type="paper",
            title="OTHER",
            metric_value=2021,
            top_k_value=1.0,
            created_at=TS,
            updated_at=TS,
        )
    )
    session.add(
        Edge(
            id="e-graph-1",
            source_id="pn-graph",
            target_id="other-node",
            edge_type="paper-paper",
            similarity_score=0.99,
            created_at=TS,
            updated_at=TS,
        )
    )
    session.add(
        Edge(
            id="e-graph-2",
            source_id="other-node",
            target_id="pn-graph",
            edge_type="paper-paper",
            similarity_score=0.88,
            created_at=TS,
            updated_at=TS,
        )
    )
    session.commit()
    monkeypatch.setattr(AdminService, "_remove_s3", lambda self, path: None)

    AdminService(session).delete_lit(1)

    assert session.get(Node, "pn-graph") is None
    assert session.get(Edge, "e-graph-1") is None
    assert session.get(Edge, "e-graph-2") is None
    assert session.get(Node, "other-node") is not None
    assert session.get(LitMetadata, 1) is None
    assert session.get(CoreFile, "u1") is None


def test_delete_lit_with_all_associations_no_orphan(session, monkeypatch):
    _seed_core_lit(session)
    session.add(MedCase(id=20, file_uuid="u1", created_at=TS, updated_at=TS))
    session.add(_make_guideline(id=7, file_uuid="u1"))
    session.add(
        Node(
            id="pn-all",
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
            id="e-all-1",
            source_id="pn-all",
            target_id="pn-all",
            edge_type="paper-paper",
            similarity_score=1.0,
            created_at=TS,
            updated_at=TS,
        )
    )
    session.commit()
    monkeypatch.setattr(AdminService, "_remove_s3", lambda self, path: None)

    res = AdminService(session).delete_lit(1)

    assert res == {"deleted": True, "id": 1, "file_uuid": "u1"}
    assert session.get(LitMetadata, 1) is None
    assert session.get(CoreFile, "u1") is None
    assert session.query(MedCase).filter(MedCase.file_uuid == "u1").count() == 0
    assert session.query(GuidelineMetadata).filter(GuidelineMetadata.file_uuid == "u1").count() == 0
    assert session.get(Node, "pn-all") is None
    assert session.query(Edge).filter(Edge.id == "e-all-1").count() == 0
    # 核心表无孤儿：file_uuid=u1 的三张子表全空
    assert session.query(LitMetadata).filter(LitMetadata.file_uuid == "u1").count() == 0


def test_delete_lit_isolation_other_file_uuid_intact(session, monkeypatch):
    _seed_core_lit(session)
    session.add(
        CoreFile(
            file_uuid="u2",
            original_name="b.pdf",
            storage_path="lit/u2/b.pdf",
            upload_time=TS,
        )
    )
    session.add(_make_lit(id=2, file_uuid="u2", title="OTHER", cleaned_title="OTHER", storage_path="lit/u2/b.pdf"))
    session.add(MedCase(id=30, file_uuid="u2", created_at=TS, updated_at=TS))
    session.add(_make_guideline(id=9, file_uuid="u2"))
    session.add(MedCase(id=31, file_uuid="u1", created_at=TS, updated_at=TS))
    session.add(_make_guideline(id=10, file_uuid="u1"))
    session.commit()
    monkeypatch.setattr(AdminService, "_remove_s3", lambda self, path: None)

    AdminService(session).delete_lit(1)

    assert session.get(LitMetadata, 1) is None
    assert session.get(CoreFile, "u1") is None
    assert session.get(LitMetadata, 2) is not None
    assert session.get(CoreFile, "u2") is not None
    assert session.get(MedCase, 30) is not None
    assert session.get(GuidelineMetadata, 9) is not None
    assert session.get(MedCase, 31) is None
    assert session.get(GuidelineMetadata, 10) is None


def test_delete_lit_s3_still_invoked(session, monkeypatch):
    _seed_core_lit(session)
    session.commit()
    called: list[str] = []
    monkeypatch.setattr(AdminService, "_remove_s3", lambda self, path: called.append(path))

    AdminService(session).delete_lit(1)

    assert called == ["lit/u1/a.pdf"]


def test_delete_lit_not_found_raises(session):
    with pytest.raises(AdminDeleteRecordNotFound):
        AdminService(session).delete_lit(9999)
