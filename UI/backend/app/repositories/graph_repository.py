"""Database repository for graph and detail queries using SQLAlchemy ORM."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import String, case, func, or_, text
from sqlalchemy.orm import Session

from app.config import DatabaseConfig, SearchConfig
from app.models.graph import CoreFile, Edge, LitMetadata, MedCase, Node
from app.search.settings import SearchBackendMode


class GraphRepository:
    PAPER_FULLTEXT_COLUMNS = ("title", "keywords", "abstract")
    RECORD_FULLTEXT_COLUMNS = ("tcm_diagnosis", "western_diagnosis")
    PAPER_SEARCH_INDEX = "idx_lit_metadata_search"
    RECORD_SEARCH_INDEX = "idx_med_case_search"

    def __init__(self, db_config: DatabaseConfig, search_config: SearchConfig | None = None) -> None:
        self._db_config = db_config
        self._search_config = search_config or SearchConfig()
        self._fulltext_cache: dict[str, bool] = {}

    def _get_session(self) -> Session:
        from app.database_pg import PgSession
        return PgSession()

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

    def search_graph(self, keyword: str, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        with self._get_session() as session:
            backend = self._resolve_search_backend(session)

            if backend == SearchBackendMode.FULLTEXT:
                try:
                    return self._search_with_fulltext(session, keyword, limit, offset)
                except Exception:
                    return self._search_with_like(session, keyword, limit, offset)

            return self._search_with_like(session, keyword, limit, offset)

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
                recommendations.append("Create fulltext indexes on lit_metadata and med_case tables")
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
                        "name": "med_case",
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
        self, session: Session, keyword: str, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        paper_title = func.coalesce(
            LitMetadata.title, LitMetadata.matched_title,
            LitMetadata.cleaned_title, LitMetadata.original_name,
            LitMetadata.file_uuid.cast(String),
        )
        record_title = func.coalesce(
            LitMetadata.title, LitMetadata.matched_title,
            LitMetadata.cleaned_title, LitMetadata.original_name,
            MedCase.file_uuid.cast(String),
        )

        paper_vector = func.to_tsvector(
            "simple",
            func.coalesce(LitMetadata.title, "") + " " +
            func.coalesce(LitMetadata.keywords.cast(String), "") + " " +
            func.coalesce(LitMetadata.abstract, ""),
        )
        record_vector = func.to_tsvector(
            "simple",
            func.coalesce(MedCase.tcm_diagnosis, "") + " " +
            func.coalesce(MedCase.western_diagnosis, ""),
        )
        ts_query = func.plainto_tsquery("simple", keyword)

        sql = text("""
            SELECT source_type, node_id, title, authors, publish_year,
                   keywords, abstract, tcm_diagnosis, western_diagnosis, score
            FROM (
                SELECT 'paper' AS source_type,
                    n.id AS node_id,
                    COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) AS title,
                    lm_p.authors AS authors,
                    lm_p.pub_year AS publish_year,
                    lm_p.keywords AS keywords,
                    lm_p.abstract AS abstract,
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
                    COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) AS title,
                    NULL AS authors, NULL AS publish_year,
                    NULL AS keywords, NULL AS abstract,
                    mc.tcm_diagnosis AS tcm_diagnosis, mc.western_diagnosis AS western_diagnosis,
                    ts_rank_cd(
                        to_tsvector('simple', COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '')),
                        plainto_tsquery('simple', :keyword)
                    ) AS score
                FROM med_case mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                LEFT JOIN nodes n ON n.title = COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) AND n.node_type = 'record'
                WHERE to_tsvector('simple', COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '')) @@ plainto_tsquery('simple', :keyword)
            ) AS combined
            ORDER BY score DESC, title ASC
            LIMIT :limit OFFSET :offset
        """)

        count_sql = text("""
            SELECT COUNT(*) AS total FROM (
                SELECT 1 FROM lit_metadata lm_p
                WHERE to_tsvector('simple', COALESCE(lm_p.title, '') || ' ' || COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, '')) @@ plainto_tsquery('simple', :keyword)
                UNION ALL
                SELECT 1 FROM med_case mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                WHERE to_tsvector('simple', COALESCE(mc.tcm_diagnosis, '') || ' ' || COALESCE(mc.western_diagnosis, '')) @@ plainto_tsquery('simple', :keyword)
            ) AS combined
        """)

        items = session.execute(sql, {"keyword": keyword, "limit": limit, "offset": offset}).mappings().all()
        total_row = session.execute(count_sql, {"keyword": keyword}).mappings().first()
        total = int(total_row["total"]) if total_row else 0

        return [dict(r) for r in items], total

    def _search_with_like(
        self, session: Session, keyword: str, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        like_pattern = f"%{keyword}%"

        sql = text("""
            SELECT source_type, node_id, title, authors, publish_year,
                   keywords, abstract, tcm_diagnosis, western_diagnosis, score
            FROM (
                SELECT 'paper' AS source_type,
                    n.id AS node_id,
                    COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) AS title,
                    lm_p.authors AS authors,
                    lm_p.pub_year AS publish_year,
                    lm_p.keywords AS keywords,
                    lm_p.abstract AS abstract,
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
                    COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) AS title,
                    NULL AS authors, NULL AS publish_year,
                    NULL AS keywords, NULL AS abstract,
                    mc.tcm_diagnosis AS tcm_diagnosis, mc.western_diagnosis AS western_diagnosis,
                    0 AS score
                FROM med_case mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                LEFT JOIN nodes n ON n.title = COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) AND n.node_type = 'record'
                WHERE (COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) ILIKE :like
                       OR mc.tcm_diagnosis ILIKE :like
                       OR mc.western_diagnosis ILIKE :like)
            ) AS combined
            ORDER BY score DESC, title ASC
            LIMIT :limit OFFSET :offset
        """)

        count_sql = text("""
            SELECT COUNT(*) AS total FROM (
                SELECT 1 FROM lit_metadata lm_p
                WHERE (COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name) ILIKE :like
                       OR lm_p.keywords::text ILIKE :like
                       OR lm_p.abstract ILIKE :like)
                UNION ALL
                SELECT 1 FROM med_case mc
                LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid
                WHERE (COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name) ILIKE :like
                       OR mc.tcm_diagnosis ILIKE :like
                       OR mc.western_diagnosis ILIKE :like)
            ) AS combined
        """)

        params = {"like": like_pattern, "limit": limit, "offset": offset}
        items = session.execute(sql, params).mappings().all()

        count_params = {"like": like_pattern}
        total_row = session.execute(count_sql, count_params).mappings().first()
        total = int(total_row["total"]) if total_row else 0

        return [dict(r) for r in items], total

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
