"""Database repository for graph and detail queries using SQLAlchemy ORM."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import String, case, func, or_, text
from sqlalchemy.orm import Session

from app.config import PostgresSettings, SearchSettings
from app.models import CoreFile, Edge, LitMetadata, MedCase, Node
from app.models.search_history import SearchBackendMode


class GraphRepository:
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

    def _title_coalesce(self, model):
        return func.coalesce(
            model.title,
            model.matched_title if hasattr(model, "matched_title") else model.title,
            model.cleaned_title if hasattr(model, "cleaned_title") else model.title,
            model.original_name if hasattr(model, "original_name") else model.title,
            model.file_uuid.cast(String) if hasattr(model, "file_uuid") else model.title,
        )

    def fetch_edges_by_seed(self, seed_id: str, limit: int) -> list[dict[str, Any]]:
        with self._get_session() as session:
            rows = (
                session.query(Edge)
                .filter(or_(Edge.source_id == seed_id, Edge.target_id == seed_id))
                .order_by(Edge.similarity_score.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "edge_type": r.edge_type,
                    "similarity_score": float(r.similarity_score) if r.similarity_score is not None else None,
                    "raw_score": float(r.raw_score) if r.raw_score is not None else None,
                }
                for r in rows
            ]

    def fetch_nodes_by_ids(self, node_ids: list[str]) -> list[dict[str, Any]]:
        if not node_ids:
            return []

        with self._get_session() as session:
            rows = (
                session.query(Node)
                .filter(Node.id.in_(node_ids))
                .all()
            )
            return [
                {
                    "id": r.id,
                    "node_type": r.node_type,
                    "title": r.title,
                    "metric_value": r.metric_value,
                    "top_k_value": float(r.top_k_value) if r.top_k_value is not None else None,
                }
                for r in rows
            ]

    def fetch_node_by_id(self, node_id: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            node = session.query(Node).filter(Node.id == node_id).first()
            if not node:
                return None
            return {
                "id": node.id,
                "node_type": node.node_type,
                "title": node.title,
                "metric_value": node.metric_value,
                "top_k_value": float(node.top_k_value) if node.top_k_value is not None else None,
            }

    def fetch_paper_detail_by_title(self, title: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            title_expr = func.coalesce(
                LitMetadata.title,
                LitMetadata.matched_title,
                LitMetadata.cleaned_title,
                LitMetadata.original_name,
            )

            order_case = case(
                (LitMetadata.title == title, 0),
                (LitMetadata.matched_title == title, 1),
                (LitMetadata.cleaned_title == title, 2),
                (LitMetadata.original_name == title, 3),
                else_=4,
            )

            row = (
                session.query(LitMetadata)
                .filter(
                    or_(
                        LitMetadata.title == title,
                        LitMetadata.matched_title == title,
                        LitMetadata.cleaned_title == title,
                        LitMetadata.original_name == title,
                    )
                )
                .order_by(order_case, LitMetadata.updated_at.desc())
                .first()
            )
            if row:
                return self._lit_to_dict(row)

            like_pattern = f"%{title}%"
            row = (
                session.query(LitMetadata)
                .filter(
                    or_(
                        LitMetadata.title.ilike(like_pattern),
                        LitMetadata.matched_title.ilike(like_pattern),
                        LitMetadata.cleaned_title.ilike(like_pattern),
                        LitMetadata.original_name.ilike(like_pattern),
                    )
                )
                .order_by(LitMetadata.updated_at.desc())
                .first()
            )
            return self._lit_to_dict(row) if row else None

    def get_file_reference_by_node_id(self, node_id: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            node = session.query(Node).filter(Node.id == node_id).first()
            if not node:
                return None

            title = node.title
            order_case = case(
                (LitMetadata.title == title, 0),
                (LitMetadata.matched_title == title, 1),
                (LitMetadata.cleaned_title == title, 2),
                (LitMetadata.original_name == title, 3),
                else_=4,
            )

            lm = (
                session.query(LitMetadata)
                .filter(
                    or_(
                        LitMetadata.title == title,
                        LitMetadata.matched_title == title,
                        LitMetadata.cleaned_title == title,
                        LitMetadata.original_name == title,
                    )
                )
                .order_by(order_case, LitMetadata.updated_at.desc())
                .first()
            )

            file_name = None
            file_key = None
            if lm:
                cf = session.query(CoreFile).filter(CoreFile.file_uuid == lm.file_uuid).first()
                if cf:
                    file_name = cf.original_name
                    file_key = cf.storage_path

            return {
                "node_id": node.id,
                "node_type": node.node_type,
                "node_title": node.title,
                "file_name": file_name,
                "file_key": file_key,
            }

    def get_file_reference_by_file_uuid(self, file_uuid: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            cf = session.query(CoreFile).filter(CoreFile.file_uuid == file_uuid).first()
            if not cf:
                return None
            node_type = "paper"
            return {
                "node_id": file_uuid,
                "node_type": node_type,
                "node_title": cf.original_name,
                "file_name": cf.original_name,
                "file_key": cf.storage_path,
            }

    def fetch_record_detail_by_title(self, title: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            order_case = case(
                (LitMetadata.title == title, 0),
                (LitMetadata.matched_title == title, 1),
                (LitMetadata.cleaned_title == title, 2),
                (LitMetadata.original_name == title, 3),
                else_=4,
            )

            row = (
                session.query(MedCase, LitMetadata.title.label("literature_title"))
                .join(LitMetadata, MedCase.file_uuid == LitMetadata.file_uuid)
                .filter(
                    or_(
                        LitMetadata.title == title,
                        LitMetadata.matched_title == title,
                        LitMetadata.cleaned_title == title,
                        LitMetadata.original_name == title,
                    )
                )
                .order_by(order_case, MedCase.updated_at.desc())
                .first()
            )
            if row:
                return self._record_to_dict(row)

            like_pattern = f"%{title}%"
            row = (
                session.query(MedCase, LitMetadata.title.label("literature_title"))
                .join(LitMetadata, MedCase.file_uuid == LitMetadata.file_uuid)
                .filter(
                    or_(
                        LitMetadata.title.ilike(like_pattern),
                        LitMetadata.matched_title.ilike(like_pattern),
                        LitMetadata.cleaned_title.ilike(like_pattern),
                        LitMetadata.original_name.ilike(like_pattern),
                    )
                )
                .order_by(MedCase.updated_at.desc())
                .first()
            )
            return self._record_to_dict(row) if row else None

    def fetch_paper_detail_by_file_uuid(self, file_uuid: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            row = session.query(LitMetadata).filter(LitMetadata.file_uuid == file_uuid).first()
            return self._lit_to_dict(row) if row else None

    def fetch_record_detail_by_file_uuid(self, file_uuid: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            row = (
                session.query(MedCase, LitMetadata.title.label("literature_title"))
                .join(LitMetadata, MedCase.file_uuid == LitMetadata.file_uuid)
                .filter(MedCase.file_uuid == file_uuid)
                .first()
            )
            if row:
                return self._record_to_dict(row)
            mc = session.query(MedCase).filter(MedCase.file_uuid == file_uuid).first()
            if mc:
                return self._record_to_dict((mc, None))
            return None

    def search_graph(
        self,
        keyword: str,
        limit: int,
        offset: int,
        source_type: str | None = None,
        filters: dict[str, list[str]] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._get_session() as session:
            backend = self._resolve_search_backend(session)

            if backend == SearchBackendMode.FULLTEXT:
                try:
                    return self._search_with_fulltext(session, keyword, limit, offset, source_type, filters)
                except Exception:
                    return self._search_with_like(session, keyword, limit, offset, source_type, filters)

            return self._search_with_like(session, keyword, limit, offset, source_type, filters)

    def search_graph_facets(
        self,
        keyword: str,
        source_type: str | None = None,
        filters: dict[str, list[str]] | None = None,
    ) -> dict[str, list[dict[str, int | str]]]:
        with self._get_session() as session:
            backend = self._resolve_search_backend(session)

            if backend == SearchBackendMode.FULLTEXT:
                try:
                    rows = self._search_facet_rows_with_fulltext(session, keyword, source_type, filters)
                except Exception:
                    rows = self._search_facet_rows_with_like(session, keyword, source_type, filters)
            else:
                rows = self._search_facet_rows_with_like(session, keyword, source_type, filters)

        counters = {
            "source_types": Counter(),
            "topics": Counter(),
            "years": Counter(),
            "journals": Counter(),
            "paper_types": Counter(),
        }

        for row in rows:
            source = self._clean_facet_value(row.get("source_type"))
            year = self._clean_facet_value(row.get("publish_year"))
            journal = self._clean_facet_value(row.get("journal"))
            paper_type_raw = self._clean_facet_value(row.get("paper_type"))
            if source:
                counters["source_types"][source] += 1
            if year:
                counters["years"][year] += 1
            if journal:
                counters["journals"][journal] += 1
            paper_type_label = self._normalize_paper_type(paper_type_raw)
            if paper_type_label:
                counters["paper_types"][paper_type_label] += 1

            for topic in self._split_listish_facet(row.get("keywords_text")):
                counters["topics"][topic] += 1

        facets = {
            key: [
                {"value": value, "label": value, "count": count}
                for value, count in counter.most_common(12)
            ]
            for key, counter in counters.items()
            if key != "years"
        }
        facets["years"] = [
            {"value": value, "label": value, "count": counters["years"][value]}
            for value in sorted(counters["years"], key=self._year_sort_key)
        ]
        return facets

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

    @classmethod
    def _split_listish_facet(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in (cls._clean_facet_value(v) for v in value) if item]

        raw = str(value).strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [item for item in (cls._clean_facet_value(v) for v in parsed) if item]

        cleaned = raw.strip("[](){}")
        parts = cleaned.replace("；", ";").replace("，", ",").replace("、", ",").replace(";", ",").split(",")
        return [item for item in (cls._clean_facet_value(part.strip(" '\"")) for part in parts) if item]

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

    def _build_search_filter_sql(
        self,
        source_type: str | None,
        filters: dict[str, list[str]] | None,
    ) -> tuple[str, dict[str, Any]]:
        clauses = []
        params: dict[str, Any] = {}
        filters = filters or {}

        if source_type:
            clauses.append("source_type = :source_type")
            params["source_type"] = source_type

        exact_filters = {
            "source_types": "source_type",
            "years": "publish_year",
            "journals": "journal",
        }
        for key, column in exact_filters.items():
            values = self._normalize_filter_values(filters.get(key))
            if not values:
                continue
            placeholders = []
            for index, value in enumerate(values):
                param_name = f"{key}_{index}"
                params[param_name] = value
                placeholders.append(f":{param_name}")
            clauses.append(f"{column} IN ({', '.join(placeholders)})")

        paper_type_values = self._normalize_filter_values(filters.get("paper_types"))
        if paper_type_values:
            expanded_db_values = []
            for val in paper_type_values:
                if val == "期刊论文":
                    expanded_db_values.extend(["journal", "期刊论文"])
                elif val == "学位论文":
                    expanded_db_values.extend(["master", "phd", "硕士论文", "博士论文"])
            if expanded_db_values:
                placeholders = []
                for idx, v in enumerate(expanded_db_values):
                    pname = f"pt_{idx}"
                    params[pname] = v
                    placeholders.append(f":{pname}")
                clauses.append(f"paper_type IN ({', '.join(placeholders)})")

        contains_filters = {
            "topics": "topic_text",
        }
        for key, column in contains_filters.items():
            values = self._normalize_filter_values(filters.get(key))
            if not values:
                continue
            subclauses = []
            for index, value in enumerate(values):
                param_name = f"{key}_{index}"
                params[param_name] = f"%{value}%"
                subclauses.append(f"COALESCE({column}, '') ILIKE :{param_name}")
            clauses.append(f"({' OR '.join(subclauses)})")

        if not clauses:
            return "", params
        return "WHERE " + " AND ".join(clauses), params

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

    def _search_with_fulltext(
        self,
        session: Session,
        keyword: str,
        limit: int,
        offset: int,
        source_type: str | None = None,
        filters: dict[str, list[str]] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filter_sql, filter_params = self._build_search_filter_sql(source_type, filters)

        sql = text(f"""
            SELECT source_type, node_id, file_uuid, title, authors, publish_year,
                   keywords, abstract, journal, paper_type, tcm_diagnosis, western_diagnosis, score
            FROM (
                SELECT 'paper' AS source_type,
                    n.id AS node_id,
                    lm_p.file_uuid AS file_uuid,
                    COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) AS title,
                    lm_p.authors AS authors,
                    lm_p.pub_year AS publish_year,
                    lm_p.keywords AS keywords,
                    lm_p.abstract AS abstract,
                    lm_p.journal AS journal,
                    lm_p.paper_type AS paper_type,
                    lm_p.keywords::text AS keywords_text,
                    COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '') AS topic_text,
                    NULL AS tcm_diagnosis, NULL AS western_diagnosis,
                    ts_rank_cd(
                        to_tsvector('simple', COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '')),
                        plainto_tsquery('simple', :keyword)
                    ) AS score
                FROM lit_metadata lm_p
                LEFT JOIN nodes n ON n.title = COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) AND n.node_type = 'paper'
                WHERE to_tsvector('simple', COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '')) @@ plainto_tsquery('simple', :keyword)
                UNION ALL
                SELECT 'record' AS source_type,
                    n.id AS node_id,
                    COALESCE(mc.file_uuid, lm_r.file_uuid) AS file_uuid,
                    COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) AS title,
                    NULL AS authors, lm_r.pub_year AS publish_year,
                    NULL AS keywords, NULL AS abstract,
                    lm_r.journal AS journal,
                    lm_r.paper_type AS paper_type,
                    lm_r.keywords::text AS keywords_text,
                    COALESCE(lm_r.title, '') || ' ' || COALESCE(lm_r.keywords::text, '') || ' ' || COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '') AS topic_text,
                    mc.tcm_diagnosis AS tcm_diagnosis, mc.western_diagnosis AS western_diagnosis,
                    ts_rank_cd(
                        to_tsvector('simple', COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '')),
                        plainto_tsquery('simple', :keyword)
                    ) AS score
                FROM case_metadata mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                LEFT JOIN nodes n ON n.title = COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) AND n.node_type = 'record'
                WHERE to_tsvector('simple', COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '')) @@ plainto_tsquery('simple', :keyword)
            ) AS combined
            {filter_sql}
            ORDER BY score DESC, title ASC
            LIMIT :limit OFFSET :offset
        """)

        count_sql = text(f"""
            SELECT COUNT(*) AS total FROM (
                SELECT 'paper' AS source_type,
                    lm_p.pub_year AS publish_year,
                    lm_p.journal AS journal,
                    lm_p.paper_type AS paper_type,
                    lm_p.keywords::text AS keywords_text,
                    COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '') AS topic_text
                FROM lit_metadata lm_p
                WHERE to_tsvector('simple', COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '')) @@ plainto_tsquery('simple', :keyword)
                UNION ALL
                SELECT 'record' AS source_type,
                    lm_r.pub_year AS publish_year,
                    lm_r.journal AS journal,
                    lm_r.paper_type AS paper_type,
                    lm_r.keywords::text AS keywords_text,
                    COALESCE(lm_r.title, '') || ' ' || COALESCE(lm_r.keywords::text, '') || ' ' || COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '') AS topic_text
                FROM case_metadata mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                WHERE to_tsvector('simple', COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '')) @@ plainto_tsquery('simple', :keyword)
            ) AS combined
            {filter_sql}
        """)

        params = {"keyword": keyword, "limit": limit, "offset": offset, **filter_params}
        items = session.execute(sql, params).mappings().all()
        total_row = session.execute(count_sql, {"keyword": keyword, **filter_params}).mappings().first()
        total = int(total_row["total"]) if total_row else 0

        return [dict(r) for r in items], total

    def _search_with_like(
        self,
        session: Session,
        keyword: str,
        limit: int,
        offset: int,
        source_type: str | None = None,
        filters: dict[str, list[str]] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        like_pattern = f"%{keyword}%"
        filter_sql, filter_params = self._build_search_filter_sql(source_type, filters)

        sql = text(f"""
            SELECT source_type, node_id, file_uuid, title, authors, publish_year,
                   keywords, abstract, journal, paper_type, tcm_diagnosis, western_diagnosis, score
            FROM (
                SELECT 'paper' AS source_type,
                    n.id AS node_id,
                    lm_p.file_uuid AS file_uuid,
                    COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) AS title,
                    lm_p.authors AS authors,
                    lm_p.pub_year AS publish_year,
                    lm_p.keywords AS keywords,
                    lm_p.abstract AS abstract,
                    lm_p.journal AS journal,
                    lm_p.paper_type AS paper_type,
                    lm_p.keywords::text AS keywords_text,
                    COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '') AS topic_text,
                    NULL AS tcm_diagnosis, NULL AS western_diagnosis,
                    0 AS score
                FROM lit_metadata lm_p
                LEFT JOIN nodes n ON n.title = COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) AND n.node_type = 'paper'
                WHERE (COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) ILIKE :like
                       OR lm_p.keywords::text ILIKE :like
                       OR lm_p.abstract ILIKE :like)
                UNION ALL
                SELECT 'record' AS source_type,
                    n.id AS node_id,
                    COALESCE(mc.file_uuid, lm_r.file_uuid) AS file_uuid,
                    COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) AS title,
                    NULL AS authors, lm_r.pub_year AS publish_year,
                    NULL AS keywords, NULL AS abstract,
                    lm_r.journal AS journal,
                    lm_r.paper_type AS paper_type,
                    lm_r.keywords::text AS keywords_text,
                    COALESCE(lm_r.title, '') || ' ' || COALESCE(lm_r.keywords::text, '') || ' ' || COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '') AS topic_text,
                    mc.tcm_diagnosis AS tcm_diagnosis, mc.western_diagnosis AS western_diagnosis,
                    0 AS score
                FROM case_metadata mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                LEFT JOIN nodes n ON n.title = COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) AND n.node_type = 'record'
                WHERE (COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) ILIKE :like
                       OR mc.tcm_diagnosis ILIKE :like
                       OR mc.western_diagnosis ILIKE :like)
            ) AS combined
            {filter_sql}
            ORDER BY score DESC, title ASC
            LIMIT :limit OFFSET :offset
        """)

        count_sql = text(f"""
            SELECT COUNT(*) AS total FROM (
                SELECT 'paper' AS source_type,
                    lm_p.pub_year AS publish_year,
                    lm_p.journal AS journal,
                    lm_p.paper_type AS paper_type,
                    lm_p.keywords::text AS keywords_text,
                    COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '') AS topic_text
                FROM lit_metadata lm_p
                WHERE (COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) ILIKE :like
                       OR lm_p.keywords::text ILIKE :like
                       OR lm_p.abstract ILIKE :like)
                UNION ALL
                SELECT 'record' AS source_type,
                    lm_r.pub_year AS publish_year,
                    lm_r.journal AS journal,
                    lm_r.paper_type AS paper_type,
                    lm_r.keywords::text AS keywords_text,
                    COALESCE(lm_r.title, '') || ' ' || COALESCE(lm_r.keywords::text, '') || ' ' || COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '') AS topic_text
                FROM case_metadata mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                WHERE (COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) ILIKE :like
                       OR mc.tcm_diagnosis ILIKE :like
                       OR mc.western_diagnosis ILIKE :like)
            ) AS combined
            {filter_sql}
        """)

        params = {"like": like_pattern, "limit": limit, "offset": offset, **filter_params}
        items = session.execute(sql, params).mappings().all()

        count_params = {"like": like_pattern, **filter_params}
        total_row = session.execute(count_sql, count_params).mappings().first()
        total = int(total_row["total"]) if total_row else 0

        return [dict(r) for r in items], total

    def _search_facet_rows_with_fulltext(
        self,
        session: Session,
        keyword: str,
        source_type: str | None = None,
        filters: dict[str, list[str]] | None = None,
    ) -> list[dict[str, Any]]:
        filter_sql, filter_params = self._build_search_filter_sql(source_type, filters)
        sql = text(f"""
            SELECT source_type, publish_year, journal, paper_type, keywords_text
            FROM (
                SELECT 'paper' AS source_type,
                    lm_p.pub_year AS publish_year,
                    lm_p.journal AS journal,
                    lm_p.paper_type AS paper_type,
                    lm_p.keywords::text AS keywords_text,
                    COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '') AS topic_text
                FROM lit_metadata lm_p
                WHERE to_tsvector('simple', COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '')) @@ plainto_tsquery('simple', :keyword)
                UNION ALL
                SELECT 'record' AS source_type,
                    lm_r.pub_year AS publish_year,
                    lm_r.journal AS journal,
                    lm_r.paper_type AS paper_type,
                    lm_r.keywords::text AS keywords_text,
                    COALESCE(lm_r.title, '') || ' ' || COALESCE(lm_r.keywords::text, '') || ' ' || COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '') AS topic_text
                FROM case_metadata mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                WHERE to_tsvector('simple', COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '')) @@ plainto_tsquery('simple', :keyword)
            ) AS combined
            {filter_sql}
        """)
        rows = session.execute(sql, {"keyword": keyword, **filter_params}).mappings().all()
        return [dict(row) for row in rows]

    def _search_facet_rows_with_like(
        self,
        session: Session,
        keyword: str,
        source_type: str | None = None,
        filters: dict[str, list[str]] | None = None,
    ) -> list[dict[str, Any]]:
        like_pattern = f"%{keyword}%"
        filter_sql, filter_params = self._build_search_filter_sql(source_type, filters)
        sql = text(f"""
            SELECT source_type, publish_year, journal, paper_type, keywords_text
            FROM (
                SELECT 'paper' AS source_type,
                    lm_p.pub_year AS publish_year,
                    lm_p.journal AS journal,
                    lm_p.paper_type AS paper_type,
                    lm_p.keywords::text AS keywords_text,
                    COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '') AS topic_text
                FROM lit_metadata lm_p
                WHERE (COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) ILIKE :like
                       OR lm_p.keywords::text ILIKE :like
                       OR lm_p.abstract ILIKE :like)
                UNION ALL
                SELECT 'record' AS source_type,
                    lm_r.pub_year AS publish_year,
                    lm_r.journal AS journal,
                    lm_r.paper_type AS paper_type,
                    lm_r.keywords::text AS keywords_text,
                    COALESCE(lm_r.title, '') || ' ' || COALESCE(lm_r.keywords::text, '') || ' ' || COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '') AS topic_text
                FROM case_metadata mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                WHERE (COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) ILIKE :like
                       OR mc.tcm_diagnosis ILIKE :like
                       OR mc.western_diagnosis ILIKE :like)
            ) AS combined
            {filter_sql}
        """)
        rows = session.execute(sql, {"like": like_pattern, **filter_params}).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    def _lit_to_dict(row: LitMetadata) -> dict[str, Any]:
        return {
            "id": row.id,
            "file_uuid": row.file_uuid,
            "original_name": row.original_name,
            "storage_path": row.storage_path,
            "cleaned_title": row.cleaned_title,
            "title": row.title,
            "authors": row.authors,
            "abstract": row.abstract,
            "keywords": row.keywords,
            "paper_type": row.paper_type,
            "source_site": row.source_site,
            "source_url": row.source_url,
            "journal": row.journal,
            "pub_year": row.pub_year,
            "matched_title": row.matched_title,
            "is_exact_match": row.is_exact_match,
            "crawl_status": row.crawl_status,
            "error_message": row.error_message,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _record_to_dict(row) -> dict[str, Any]:
        mc = row[0]
        return {
            "id": mc.id,
            "file_uuid": mc.file_uuid,
            "age": mc.age,
            "bmi": mc.bmi,
            "menstruation": mc.menstruation,
            "infertility": mc.infertility,
            "lifestyle": mc.lifestyle,
            "present_symptoms": mc.present_symptoms,
            "medical_history": mc.medical_history,
            "lab_tests": mc.lab_tests,
            "ultrasound": mc.ultrasound,
            "followup": mc.followup,
            "western_diagnosis": mc.western_diagnosis,
            "tcm_diagnosis": mc.tcm_diagnosis,
            "treatment_principle": mc.treatment_principle,
            "prescription": mc.prescription,
            "acupoints": mc.acupoints,
            "assisted_reproduction": mc.assisted_reproduction,
            "western_medicine": mc.western_medicine,
            "efficacy": mc.efficacy,
            "adverse_reactions": mc.adverse_reactions,
            "commentary": mc.commentary,
            "created_at": mc.created_at,
            "updated_at": mc.updated_at,
            "literature_title": row[1] if len(row) > 1 else None,
        }
