"""Database repository for graph and detail queries."""

from __future__ import annotations

from typing import Any

try:
    import psycopg2
    from psycopg2 import Error
    from psycopg2.extras import RealDictCursor
except Exception:  # pragma: no cover
    psycopg2 = None
    Error = Exception
    RealDictCursor = None

from app.config import DatabaseConfig
from app.search.settings import SearchBackendMode, SearchConfig


class GraphRepository:
    PAPER_FULLTEXT_COLUMNS = ("title", "keywords", "abstract")
    RECORD_FULLTEXT_COLUMNS = ("tcm_diagnosis", "western_diagnosis")
    PAPER_SEARCH_INDEX = "idx_lit_metadata_search"
    RECORD_SEARCH_INDEX = "idx_med_case_search"

    def __init__(self, db_config: DatabaseConfig, search_config: SearchConfig | None = None) -> None:
        self._db_config = db_config
        self._search_config = search_config or SearchConfig()
        self._fulltext_cache: dict[str, bool] = {}

    @staticmethod
    def _lit_match_condition(title_expr: str) -> str:
        return (
            f"(lm.title = {title_expr} OR "
            f"lm.matched_title = {title_expr} OR "
            f"lm.cleaned_title = {title_expr} OR "
            f"lm.original_name = {title_expr})"
        )

    def _completion_rank_sql(self, title_expr: str) -> str:
        return (
            "CASE WHEN EXISTS ("
            "SELECT 1 FROM lit_metadata lm "
            "JOIN core_file cf ON cf.file_uuid = lm.file_uuid "
            f"WHERE {self._lit_match_condition(title_expr)} "
            "AND cf.status_metadata = TRUE AND cf.status_case = TRUE"
            ") THEN 1 ELSE 0 END"
        )

    def _connect(self):
        if psycopg2 is None:
            raise RuntimeError("Missing dependency: psycopg2-binary")
        return psycopg2.connect(
            host=self._db_config.host,
            port=self._db_config.port,
            user=self._db_config.user,
            password=self._db_config.password,
            dbname=self._db_config.database,
        )

    def fetch_edges_by_seed(self, seed_id: str, limit: int) -> list[dict[str, Any]]:
        sql = (
            "SELECT id, source_id, target_id, edge_type, similarity_score, raw_score "
            "FROM edges "
            "WHERE source_id = %s OR target_id = %s "
            "ORDER BY similarity_score DESC "
            "LIMIT %s"
        )

        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, (seed_id, seed_id, limit))
                return cursor.fetchall() or []

    def fetch_nodes_by_ids(self, node_ids: list[str]) -> list[dict[str, Any]]:
        if not node_ids:
            return []

        placeholders = ", ".join(["%s"] * len(node_ids))
        completion_rank = self._completion_rank_sql("n.title")
        sql = (
            "SELECT id, node_type, title, metric_value, top_k_value "
            f"FROM nodes n WHERE id IN ({placeholders}) "
            f"ORDER BY {completion_rank} DESC, n.id ASC"
        )

        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, tuple(node_ids))
                return cursor.fetchall() or []

    def fetch_node_by_id(self, node_id: str) -> dict[str, Any] | None:
        sql = (
            "SELECT id, node_type, title, metric_value, top_k_value "
            "FROM nodes WHERE id = %s LIMIT 1"
        )

        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, (node_id,))
                row = cursor.fetchone()
                return row or None

    def fetch_paper_detail_by_title(self, title: str) -> dict[str, Any] | None:
        columns = (
            "id",
            "file_uuid",
            "original_name",
            "storage_path",
            "cleaned_title",
            "title",
            "authors",
            "abstract",
            "keywords",
            "paper_type",
            "source_site",
            "source_url",
            "journal",
            "pub_year",
            "matched_title",
            "is_exact_match",
            "crawl_status",
            "error_message",
            "created_at",
            "updated_at",
        )
        fields = ", ".join(f"lm.{col}" for col in columns)
        match_sql = "(lm.title = %s OR lm.matched_title = %s OR lm.cleaned_title = %s OR lm.original_name = %s)"
        order_sql = (
            "CASE "
            "WHEN lm.title = %s THEN 0 "
            "WHEN lm.matched_title = %s THEN 1 "
            "WHEN lm.cleaned_title = %s THEN 2 "
            "WHEN lm.original_name = %s THEN 3 "
            "ELSE 4 END"
        )

        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                exact_sql = (
                    f"SELECT {fields} FROM lit_metadata lm "
                    f"WHERE {match_sql} "
                    f"ORDER BY {order_sql}, lm.updated_at DESC "
                    "LIMIT 1"
                )
                fuzzy_sql = (
                    f"SELECT {fields} FROM lit_metadata lm "
                    "WHERE (lm.title LIKE %s OR lm.matched_title LIKE %s OR lm.cleaned_title LIKE %s "
                    "OR lm.original_name LIKE %s) "
                    "ORDER BY lm.updated_at DESC "
                    "LIMIT 1"
                )

                cursor.execute(
                    exact_sql,
                    (
                        title,
                        title,
                        title,
                        title,
                        title,
                        title,
                        title,
                        title,
                    ),
                )
                row = cursor.fetchone()
                if row:
                    return row

                like_pattern = f"%{title}%"
                cursor.execute(
                    fuzzy_sql,
                    (like_pattern, like_pattern, like_pattern, like_pattern),
                )
                return cursor.fetchone() or None

    def get_file_reference_by_node_id(self, node_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                sql = (
                    "SELECT n.id AS node_id, n.node_type AS node_type, n.title AS node_title, "
                    "cf.original_name AS file_name, "
                    "cf.storage_path AS file_key "
                    "FROM nodes n "
                    "LEFT JOIN lit_metadata lm ON lm.id = ("
                    "SELECT lm2.id FROM lit_metadata lm2 "
                    "WHERE (lm2.title = n.title OR lm2.matched_title = n.title "
                    "OR lm2.cleaned_title = n.title OR lm2.original_name = n.title) "
                    "ORDER BY "
                    "CASE WHEN lm2.title = n.title THEN 0 "
                    "WHEN lm2.matched_title = n.title THEN 1 "
                    "WHEN lm2.cleaned_title = n.title THEN 2 "
                    "WHEN lm2.original_name = n.title THEN 3 ELSE 4 END, "
                    "lm2.updated_at DESC "
                    "LIMIT 1"
                    ") "
                    "LEFT JOIN core_file cf ON cf.file_uuid = lm.file_uuid "
                    "WHERE n.id = %s LIMIT 1"
                )
                cursor.execute(sql, (node_id,))
                row = cursor.fetchone()
                if not row:
                    return None

                return row

    def fetch_record_detail_by_title(self, title: str) -> dict[str, Any] | None:
        fields = (
            "mc.id AS id, mc.file_uuid AS file_uuid, mc.age AS age, mc.bmi AS bmi, "
            "mc.menstruation AS menstruation, mc.infertility AS infertility, "
            "mc.lifestyle AS lifestyle, mc.present_symptoms AS present_symptoms, "
            "mc.medical_history AS medical_history, mc.lab_tests AS lab_tests, "
            "mc.ultrasound AS ultrasound, mc.followup AS followup, "
            "mc.western_diagnosis AS western_diagnosis, mc.tcm_diagnosis AS tcm_diagnosis, "
            "mc.treatment_principle AS treatment_principle, mc.prescription AS prescription, "
            "mc.acupoints AS acupoints, mc.assisted_reproduction AS assisted_reproduction, "
            "mc.western_medicine AS western_medicine, mc.efficacy AS efficacy, "
            "mc.adverse_reactions AS adverse_reactions, mc.commentary AS commentary, "
            "mc.created_at AS created_at, mc.updated_at AS updated_at, "
            "lm.title AS literature_title"
        )
        match_sql = "(lm.title = %s OR lm.matched_title = %s OR lm.cleaned_title = %s OR lm.original_name = %s)"
        order_sql = (
            "CASE "
            "WHEN lm.title = %s THEN 0 "
            "WHEN lm.matched_title = %s THEN 1 "
            "WHEN lm.cleaned_title = %s THEN 2 "
            "WHEN lm.original_name = %s THEN 3 "
            "ELSE 4 END"
        )
        exact_sql = (
            f"SELECT {fields} "
            "FROM lit_metadata lm "
            "JOIN med_case mc ON mc.file_uuid = lm.file_uuid "
            f"WHERE {match_sql} "
            f"ORDER BY {order_sql}, mc.updated_at DESC "
            "LIMIT 1"
        )
        fuzzy_sql = (
            f"SELECT {fields} "
            "FROM lit_metadata lm "
            "JOIN med_case mc ON mc.file_uuid = lm.file_uuid "
            "WHERE (lm.title LIKE %s OR lm.matched_title LIKE %s OR lm.cleaned_title LIKE %s "
            "OR lm.original_name LIKE %s) "
            "ORDER BY mc.updated_at DESC "
            "LIMIT 1"
        )

        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    exact_sql,
                    (
                        title,
                        title,
                        title,
                        title,
                        title,
                        title,
                        title,
                        title,
                    ),
                )
                row = cursor.fetchone()
                if row:
                    return row

                like_pattern = f"%{title}%"
                cursor.execute(
                    fuzzy_sql,
                    (like_pattern, like_pattern, like_pattern, like_pattern),
                )
                return cursor.fetchone() or None

    def search_graph(self, keyword: str, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                backend = self._resolve_search_backend(cursor)

                if backend == SearchBackendMode.FULLTEXT:
                    try:
                        return self._search_with_fulltext(cursor, keyword, limit, offset)
                    except Error:
                        return self._search_with_like(cursor, keyword, limit, offset)

                return self._search_with_like(cursor, keyword, limit, offset)

    def get_search_index_status(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                paper_indexed = self._fetch_fulltext_columns(
                    cursor,
                    self.PAPER_SEARCH_INDEX,
                    self.PAPER_FULLTEXT_COLUMNS,
                )
                record_indexed = self._fetch_fulltext_columns(
                    cursor,
                    self.RECORD_SEARCH_INDEX,
                    self.RECORD_FULLTEXT_COLUMNS,
                )

                paper_missing = [col for col in self.PAPER_FULLTEXT_COLUMNS if col not in paper_indexed]
                record_missing = [col for col in self.RECORD_FULLTEXT_COLUMNS if col not in record_indexed]
                fulltext_ready = not paper_missing and not record_missing
                effective_backend = self._resolve_search_backend(cursor).value

                recommendations: list[str] = []
                if not fulltext_ready:
                    recommendations.append("Apply configs/sql/indexes/001_fulltext_search_indexes.sql")
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
                    "suggested_scripts": [
                        "configs/sql/indexes/001_fulltext_search_indexes.sql",
                        "configs/sql/indexes/README.md",
                    ],
                    "recommendations": recommendations,
                }

    def _resolve_search_backend(self, cursor) -> SearchBackendMode:
        mode = self._search_config.backend_mode
        if mode == SearchBackendMode.LIKE:
            return SearchBackendMode.LIKE
        if mode == SearchBackendMode.FULLTEXT:
            return SearchBackendMode.FULLTEXT
        return SearchBackendMode.FULLTEXT if self._supports_fulltext(cursor) else SearchBackendMode.LIKE

    def _supports_fulltext(self, cursor) -> bool:
        return self._has_fulltext_index(cursor, self.PAPER_SEARCH_INDEX) and self._has_fulltext_index(
            cursor, self.RECORD_SEARCH_INDEX
        )

    def _fetch_fulltext_columns(
        self,
        cursor,
        index_name: str,
        columns: tuple[str, ...],
    ) -> set[str]:
        if self._has_fulltext_index(cursor, index_name):
            return set(columns)
        return set()

    def _has_fulltext_index(self, cursor, index_name: str) -> bool:
        cache_key = index_name
        if cache_key in self._fulltext_cache:
            return self._fulltext_cache[cache_key]

        sql = (
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = current_schema() AND indexname = %s LIMIT 1"
        )
        cursor.execute(sql, (index_name,))
        supported = cursor.fetchone() is not None
        self._fulltext_cache[cache_key] = supported
        return supported

    def _search_with_fulltext(
        self,
        cursor,
        keyword: str,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        paper_title_expr = "COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name)"
        record_title_expr = "COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name)"
        paper_vector = (
            "to_tsvector('simple', COALESCE(lm_p.title, '') || ' ' || "
            "COALESCE(lm_p.keywords::text, '') || ' ' || COALESCE(lm_p.abstract, ''))"
        )
        record_vector = (
            "to_tsvector('simple', COALESCE(mc.tcm_diagnosis, '') || ' ' || "
            "COALESCE(mc.western_diagnosis, ''))"
        )
        paper_query = "plainto_tsquery('simple', %s)"
        record_query = "plainto_tsquery('simple', %s)"
        paper_completion = self._completion_rank_sql(paper_title_expr)
        record_completion = self._completion_rank_sql(record_title_expr)

        data_sql = (
            "SELECT source_type, node_id, title, authors, publish_year, "
            "keywords, abstract, tcm_diagnosis, western_diagnosis, score "
            "FROM ("
            "SELECT 'paper' AS source_type, "
            f"n.id AS node_id, {paper_title_expr} AS title, lm_p.authors AS authors, "
            "lm_p.pub_year AS publish_year, lm_p.keywords AS keywords, lm_p.abstract AS abstract, "
            "NULL AS tcm_diagnosis, NULL AS western_diagnosis, "
            f"{paper_completion} AS completed_rank, "
            f"ts_rank_cd({paper_vector}, {paper_query}) AS score "
            "FROM lit_metadata lm_p "
            f"LEFT JOIN nodes n ON n.title = {paper_title_expr} AND n.node_type = 'paper' "
            f"WHERE {paper_vector} @@ {paper_query} "
            "UNION ALL "
            "SELECT 'record' AS source_type, "
            f"n.id AS node_id, {record_title_expr} AS title, NULL AS authors, NULL AS publish_year, "
            "NULL AS keywords, NULL AS abstract, "
            "mc.tcm_diagnosis AS tcm_diagnosis, mc.western_diagnosis AS western_diagnosis, "
            f"{record_completion} AS completed_rank, "
            f"ts_rank_cd({record_vector}, {record_query}) AS score "
            "FROM med_case mc "
            "LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid "
            f"LEFT JOIN nodes n ON n.title = {record_title_expr} AND n.node_type = 'record' "
            f"WHERE {record_vector} @@ {record_query} "
            ") AS combined "
            "ORDER BY completed_rank DESC, score DESC, title ASC "
            "LIMIT %s OFFSET %s"
        )

        count_sql = (
            "SELECT COUNT(*) AS total FROM ("
            "SELECT 1 FROM lit_metadata lm_p "
            f"WHERE {paper_vector} @@ {paper_query} "
            "UNION ALL "
            "SELECT 1 FROM med_case mc "
            "LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid "
            f"WHERE {record_vector} @@ {record_query} "
            ") AS combined"
        )

        cursor.execute(data_sql, (keyword, keyword, keyword, keyword, limit, offset))
        items = cursor.fetchall() or []

        cursor.execute(count_sql, (keyword, keyword))
        total_row = cursor.fetchone()
        total = int(total_row["total"]) if total_row else 0

        return items, total

    def _search_with_like(
        self,
        cursor,
        keyword: str,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        like_pattern = f"%{keyword}%"
        paper_title_expr = "COALESCE(lm_p.title, lm_p.matched_title, lm_p.cleaned_title, lm_p.original_name)"
        record_title_expr = "COALESCE(lm_r.title, lm_r.matched_title, lm_r.cleaned_title, lm_r.original_name)"
        paper_completion = self._completion_rank_sql(paper_title_expr)
        record_completion = self._completion_rank_sql(record_title_expr)
        data_sql = (
            "SELECT source_type, node_id, title, authors, publish_year, "
            "keywords, abstract, tcm_diagnosis, western_diagnosis, score "
            "FROM ("
            "SELECT 'paper' AS source_type, "
            f"n.id AS node_id, {paper_title_expr} AS title, lm_p.authors AS authors, "
            "lm_p.pub_year AS publish_year, lm_p.keywords AS keywords, lm_p.abstract AS abstract, "
            "NULL AS tcm_diagnosis, NULL AS western_diagnosis, "
            f"{paper_completion} AS completed_rank, "
            "0 AS score "
            "FROM lit_metadata lm_p "
            f"LEFT JOIN nodes n ON n.title = {paper_title_expr} AND n.node_type = 'paper' "
            f"WHERE ({paper_title_expr} ILIKE %s OR lm_p.keywords::text ILIKE %s OR lm_p.abstract ILIKE %s) "
            "UNION ALL "
            "SELECT 'record' AS source_type, "
            f"n.id AS node_id, {record_title_expr} AS title, NULL AS authors, NULL AS publish_year, "
            "NULL AS keywords, NULL AS abstract, "
            "mc.tcm_diagnosis AS tcm_diagnosis, mc.western_diagnosis AS western_diagnosis, "
            f"{record_completion} AS completed_rank, "
            "0 AS score "
            "FROM med_case mc "
            "LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid "
            f"LEFT JOIN nodes n ON n.title = {record_title_expr} AND n.node_type = 'record' "
            f"WHERE ({record_title_expr} ILIKE %s OR mc.tcm_diagnosis ILIKE %s OR mc.western_diagnosis ILIKE %s) "
            ") AS combined "
            "ORDER BY completed_rank DESC, score DESC, title ASC "
            "LIMIT %s OFFSET %s"
        )

        count_sql = (
            "SELECT COUNT(*) AS total FROM ("
            "SELECT 1 FROM lit_metadata lm_p "
            f"WHERE ({paper_title_expr} ILIKE %s OR lm_p.keywords::text ILIKE %s OR lm_p.abstract ILIKE %s) "
            "UNION ALL "
            "SELECT 1 FROM med_case mc "
            "LEFT JOIN lit_metadata lm_r ON lm_r.file_uuid = mc.file_uuid "
            f"WHERE ({record_title_expr} ILIKE %s OR mc.tcm_diagnosis ILIKE %s OR mc.western_diagnosis ILIKE %s) "
            ") AS combined"
        )

        cursor.execute(
            data_sql,
            (
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
                limit,
                offset,
            ),
        )
        items = cursor.fetchall() or []

        cursor.execute(
            count_sql,
            (
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
            ),
        )
        total_row = cursor.fetchone()
        total = int(total_row["total"]) if total_row else 0

        return items, total
