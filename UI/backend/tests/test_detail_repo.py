import types
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, CoreFile, LitMetadata, MedCase
from app.repositories.detail_repo import DetailRepository


def _create_detail_tables(engine):
    Base.metadata.create_all(
        engine,
        tables=[CoreFile.__table__, LitMetadata.__table__, MedCase.__table__],
    )


def make_fake_lit_row():
    return types.SimpleNamespace(
        id=1,
        file_uuid="u1",
        original_name="a.pdf",
        storage_path="p",
        cleaned_title="t",
        title="T",
        authors=["A"],
        abstract=None,
        keywords=["k"],
        paper_type=None,
        source_site="s",
        source_url=None,
        journal="j",
        pub_year="2020",
        matched_title="mt",
        is_exact_match=True,
        crawl_status="success",
        error_message=None,
        created_at=None,
        updated_at=None,
    )


def make_fake_med_case():
    return types.SimpleNamespace(
        id=1,
        file_uuid="u1",
        age="30",
        bmi=None,
        menstruation=None,
        infertility=None,
        lifestyle=None,
        present_symptoms=None,
        medical_history=None,
        lab_tests=None,
        ultrasound=None,
        followup=None,
        western_diagnosis=None,
        tcm_diagnosis=None,
        treatment_principle=None,
        prescription=None,
        acupoints=None,
        assisted_reproduction=None,
        western_medicine=None,
        efficacy=None,
        adverse_reactions=None,
        commentary=None,
        created_at=None,
        updated_at=None,
    )


def test_lit_to_dict_maps_fields():
    record = DetailRepository._lit_to_dict(make_fake_lit_row())
    assert isinstance(record, dict)
    assert record["file_uuid"] == "u1"
    assert record["authors"] == ["A"]
    assert record["title"] == "T"


def test_record_to_dict_without_literature_title():
    row = (make_fake_med_case(), None)
    record = DetailRepository._record_to_dict(row)
    assert record["id"] == 1
    assert record["age"] == "30"
    assert record["bmi"] is None
    assert record["file_uuid"] == "u1"
    assert record["literature_title"] is None


def test_record_to_dict_with_literature_title():
    row = (make_fake_med_case(), "某文献")
    record = DetailRepository._record_to_dict(row)
    assert record["literature_title"] == "某文献"


def _seed_lit_metadata(session, **overrides):
    now = datetime.now()
    kwargs = dict(
        file_uuid="u1",
        original_name="a.pdf",
        storage_path="lit/u1/a.pdf",
        cleaned_title="某文献（清洗）",
        title="某文献",
        authors=["张三"],
        keywords=["中医"],
        source_site="cnki",
        matched_title="某文献",
        is_exact_match=True,
        crawl_status="success",
        created_at=now,
        updated_at=now,
    )
    kwargs.update(overrides)
    session.add(LitMetadata(**kwargs))
    session.commit()


def _seed_med_case(session, **overrides):
    now = datetime.now()
    kwargs = dict(
        file_uuid="u1",
        age="30",
        tcm_diagnosis="气虚血瘀",
        created_at=now,
        updated_at=now,
    )
    kwargs.update(overrides)
    session.add(MedCase(**kwargs))
    session.commit()


def test_fetch_paper_detail_by_file_uuid_hit(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    _create_detail_tables(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        _seed_lit_metadata(session)

    monkeypatch.setattr("app.core.database.SessionLocal", Session)

    repo = DetailRepository(types.SimpleNamespace(), types.SimpleNamespace())
    res = repo.fetch_paper_detail_by_file_uuid("u1")

    assert res is not None
    assert res["file_uuid"] == "u1"
    assert res["title"] == "某文献"


def test_fetch_paper_detail_by_title_hit(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    _create_detail_tables(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        _seed_lit_metadata(session)

    monkeypatch.setattr("app.core.database.SessionLocal", Session)

    repo = DetailRepository(types.SimpleNamespace(), types.SimpleNamespace())
    res = repo.fetch_paper_detail_by_title("某文献")

    assert res is not None
    assert res["title"] == "某文献"
    assert res["file_uuid"] == "u1"


def test_fetch_record_detail_by_file_uuid_hit(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    _create_detail_tables(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        _seed_lit_metadata(session)
        _seed_med_case(session)

    monkeypatch.setattr("app.core.database.SessionLocal", Session)

    repo = DetailRepository(types.SimpleNamespace(), types.SimpleNamespace())
    res = repo.fetch_record_detail_by_file_uuid("u1")

    assert res is not None
    assert res["file_uuid"] == "u1"
    assert res["literature_title"] == "某文献"
    assert res["tcm_diagnosis"] == "气虚血瘀"


def test_fetch_record_detail_by_title_exact_hit(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    _create_detail_tables(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        _seed_lit_metadata(session)
        _seed_med_case(session)

    monkeypatch.setattr("app.core.database.SessionLocal", Session)

    repo = DetailRepository(types.SimpleNamespace(), types.SimpleNamespace())
    res = repo.fetch_record_detail_by_title("某文献")

    assert res is not None
    assert res["tcm_diagnosis"] == "气虚血瘀"
    assert res["literature_title"] == "某文献"


def test_fetch_record_detail_by_title_ilike_fallback(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    _create_detail_tables(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        _seed_lit_metadata(
            session,
            file_uuid="u2",
            title="慢性盆腔炎临床研究",
        )
        _seed_med_case(session, file_uuid="u2")

    monkeypatch.setattr("app.core.database.SessionLocal", Session)

    repo = DetailRepository(types.SimpleNamespace(), types.SimpleNamespace())
    res = repo.fetch_record_detail_by_title("盆腔炎")

    assert res is not None
    assert res["literature_title"] == "慢性盆腔炎临床研究"
