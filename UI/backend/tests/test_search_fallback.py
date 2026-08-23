"""Rollback-before-LIKE-fallback regression tests (plan security-p0p1-hardening W4-T12).

When the fulltext backend fails mid-transaction (e.g. aborted transaction in
PostgreSQL), the repository must roll the session back BEFORE issuing the
ILIKE fallback query, otherwise the fallback itself fails on an aborted
transaction.
"""

import contextlib
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.config import PostgresSettings, SearchSettings
from app.models.search_history import SearchBackendMode
from app.repositories.search_repo import SearchRepository


def _make_repo() -> SearchRepository:
    return SearchRepository(
        PostgresSettings(),
        SearchSettings(backend_mode=SearchBackendMode.FULLTEXT),
    )


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


def _search_like_rows():
    return [
        {"source_type": "paper", "node_id": 1, "title": "针灸治疗研究", "score": 0},
        {"source_type": "record", "node_id": 2, "title": "针灸病案记录", "score": 0},
    ]


def _facet_like_rows():
    return [
        {
            "source_type": "paper",
            "publish_year": "2020",
            "journal": "中医杂志",
            "paper_type": "journal",
            "keywords_text": '["针灸"]',
        }
    ]


def _tracking_execute(events, fail_first=False):
    """session.execute stand-in: records call order, optionally raises first."""
    counter = {"n": 0}

    def execute(clause, params=None):  # noqa: ANN001, ANN202 - test double
        counter["n"] += 1
        events.append(f"execute:{counter['n']}")
        if fail_first or counter["n"] == 1:
            raise SQLAlchemyError("current transaction is aborted")
        sql = str(clause)
        if "COUNT(*)" in sql:
            return _FakeResult([{"total": len(_search_like_rows())}])
        if "publish_year" in sql and "node_id" not in sql:
            return _FakeResult(_facet_like_rows())
        return _FakeResult(_search_like_rows())

    return execute


def _make_tracked_session(events, fail_first=False):
    session = MagicMock()
    session.execute.side_effect = _tracking_execute(events, fail_first=fail_first)
    session.rollback.side_effect = lambda: events.append("rollback")
    return session


def test_search_graph_rolls_back_before_like_fallback_when_fulltext_aborts():
    repo = _make_repo()
    events: list[str] = []
    session = _make_tracked_session(events)
    repo._get_session = lambda: contextlib.nullcontext(session)

    items, total = repo.search_graph("针灸", limit=10, offset=0)

    assert [row["title"] for row in items] == ["针灸治疗研究", "针灸病案记录"]
    assert total == 2
    assert "rollback" in events
    assert events.index("rollback") < events.index("execute:2")


def test_search_facets_rolls_back_before_like_fallback_when_fulltext_aborts():
    repo = _make_repo()
    events: list[str] = []
    session = _make_tracked_session(events)
    repo._get_session = lambda: contextlib.nullcontext(session)

    facets = repo.search_graph_facets("针灸")

    assert facets["source_types"][0]["value"] == "paper"
    assert facets["topics"][0] == {"value": "针灸", "label": "针灸", "count": 1}
    assert "rollback" in events
    assert events.index("rollback") < events.index("execute:2")


def test_search_graph_raises_when_like_fallback_also_fails():
    repo = _make_repo()
    session = _make_tracked_session([], fail_first=True)
    repo._get_session = lambda: contextlib.nullcontext(session)

    with pytest.raises(SQLAlchemyError):
        repo.search_graph("针灸", limit=10, offset=0)


def test_search_facets_raises_when_like_fallback_also_fails():
    repo = _make_repo()
    session = _make_tracked_session([], fail_first=True)
    repo._get_session = lambda: contextlib.nullcontext(session)

    with pytest.raises(SQLAlchemyError):
        repo.search_graph_facets("针灸")
