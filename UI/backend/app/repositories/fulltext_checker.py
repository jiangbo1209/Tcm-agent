"""Fulltext search index detection and backend selection."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.search_history import SearchBackendMode


class FulltextCheckerMixin:
    def get_search_index_status(self) -> dict[str, Any]:
        with self._get_session() as session:
            paper_indexed = self._fetch_fulltext_columns(
                session, self.PAPER_SEARCH_INDEX, self.PAPER_FULLTEXT_COLUMNS
            )
            record_indexed = self._fetch_fulltext_columns(
                session, self.RECORD_SEARCH_INDEX, self.RECORD_FULLTEXT_COLUMNS
            )

            paper_missing = [c for c in self.PAPER_FULLTEXT_COLUMNS if c not in paper_indexed]
            record_missing = [c for c in self.RECORD_FULLTEXT_COLUMNS if c not in record_indexed]
            fulltext_ready = not paper_missing and not record_missing
            effective_backend = self._resolve_search_backend(session).value

            recommendations: list[str] = []
            if not fulltext_ready:
                recommendations.append("Create fulltext indexes on lit_metadata and case_metadata tables")
            if self._search_config.backend_mode == SearchBackendMode.LIKE:
                recommendations.append("SEARCH_BACKEND_MODE=like is enabled; switch to auto/fulltext after index rollout")

            return {
                "configured_backend": self._search_config.backend_mode.value,
                "effective_backend": effective_backend,
                "fulltext_ready": fulltext_ready,
                "tables": [
                    {
                        "name": "lit_metadata",
                        "required_columns": list(self.PAPER_FULLTEXT_COLUMNS),
                        "indexed_columns": sorted(paper_indexed),
                        "missing_columns": paper_missing,
                    },
                    {
                        "name": "case_metadata",
                        "required_columns": list(self.RECORD_FULLTEXT_COLUMNS),
                        "indexed_columns": sorted(record_indexed),
                        "missing_columns": record_missing,
                    },
                ],
                "suggested_scripts": [],
                "recommendations": recommendations,
            }

    def _resolve_search_backend(self, session: Session) -> SearchBackendMode:
        mode = self._search_config.backend_mode
        if mode == SearchBackendMode.LIKE:
            return SearchBackendMode.LIKE
        if mode == SearchBackendMode.FULLTEXT:
            return SearchBackendMode.FULLTEXT
        return SearchBackendMode.FULLTEXT if self._supports_fulltext(session) else SearchBackendMode.LIKE

    def _supports_fulltext(self, session: Session) -> bool:
        return self._has_fulltext_index(session, self.PAPER_SEARCH_INDEX) and self._has_fulltext_index(
            session, self.RECORD_SEARCH_INDEX
        )

    def _fetch_fulltext_columns(
        self, session: Session, index_name: str, columns: tuple[str, ...]
    ) -> set[str]:
        if self._has_fulltext_index(session, index_name):
            return set(columns)
        return set()

    def _has_fulltext_index(self, session: Session, index_name: str) -> bool:
        if index_name in self._fulltext_cache:
            return self._fulltext_cache[index_name]

        result = session.execute(
            text("SELECT 1 FROM pg_indexes WHERE schemaname = current_schema() AND indexname = :name LIMIT 1"),
            {"name": index_name},
        ).fetchone()
        supported = result is not None
        self._fulltext_cache[index_name] = supported
        return supported
