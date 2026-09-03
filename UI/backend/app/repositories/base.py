"""Shared utilities and injectable base class for repository sub-modules."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import PostgresSettings, SearchSettings


class BaseRepository:
    PAPER_FULLTEXT_COLUMNS = ("title", "keywords", "abstract")
    RECORD_FULLTEXT_COLUMNS = ("tcm_diagnosis", "western_diagnosis")
    PAPER_SEARCH_INDEX = "idx_lit_metadata_search"
    RECORD_SEARCH_INDEX = "idx_case_metadata_search"

    def __init__(self, db_config: PostgresSettings, search_config: SearchSettings | None = None) -> None:
        self._db_config = db_config
        self._search_config = search_config or SearchSettings()
        self._fulltext_cache: dict[str, bool] = {}

    def _get_session(self) -> Session:
        from app.core.database import SessionLocal
        return SessionLocal()

    @staticmethod
    def _clean_facet_value(value: Any) -> str | None:
        if value is None:
            return None
        text_value = str(value).strip()
        return text_value or None

    @staticmethod
    def _year_sort_key(value: str) -> tuple[int, str]:
        text_value = str(value).strip()
        if len(text_value) >= 4 and text_value[:4].isdigit():
            return (int(text_value[:4]), text_value)
        return (9999, text_value)

    @staticmethod
    def _normalize_paper_type(value: str | None) -> str | None:
        if not value:
            return None
        v = value.strip().lower()
        if v in ("journal", "期刊论文", "newspaper"):
            return "期刊论文"
        if v in ("master", "phd", "硕士论文", "博士论文"):
            return "学位论文"
        return None

    @staticmethod
    def _normalize_filter_values(values: Any) -> list[str]:
        if not values:
            return []
        if not isinstance(values, list):
            values = [values]
        seen = set()
        normalized = []
        for value in values:
            text_value = str(value).strip()
            if text_value and text_value not in seen:
                seen.add(text_value)
                normalized.append(text_value)
        return normalized[:20]
