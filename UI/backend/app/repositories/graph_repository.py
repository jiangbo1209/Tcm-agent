"""Database repository for graph and detail queries."""

from __future__ import annotations

from typing import Any

import mysql.connector
from mysql.connector import Error

from app.config import DatabaseConfig
from app.models.entities import PAPER_COLUMNS, RECORD_COLUMNS
from app.search.settings import SearchBackendMode, SearchConfig


def quote_ident(name: str) -> str:
    return f"`{name.replace('`', '``')}`"


class GraphRepository:
    PAPER_FULLTEXT_COLUMNS = ("title", "keywords", "abstract")
    RECORD_FULLTEXT_COLUMNS = ("论文名称", "中医证候诊断", "西医病名诊断")

    def __init__(self, db_config: DatabaseConfig, search_config: SearchConfig | None = None) -> None:
        self._db_config = db_config
        self._search_config = search_config or SearchConfig()
        self._fulltext_cache: dict[tuple[str, tuple[str, ...]], bool] = {}
        self._paper_column_cache: dict[str, bool] = {}

    def _connect(self):
        return mysql.connector.connect(
            host=self._db_config.host,
            port=self._db_config.port,
            user=self._db_config.user,
            password=self._db_config.password,
            database=self._db_config.database,
            charset="utf8mb4",
            use_unicode=True,
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
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(sql, (seed_id, seed_id, limit))
                return cursor.fetchall() or []

    def fetch_nodes_by_ids(self, node_ids: list[str]) -> list[dict[str, Any]]:
        if not node_ids:
            return []

        placeholders = ", ".join(["%s"] * len(node_ids))
        sql = (
            "SELECT id, node_type, title, metric_value, top_k_value "
            f"FROM nodes WHERE id IN ({placeholders})"
        )

        with self._connect() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(sql, tuple(node_ids))
                return cursor.fetchall() or []

    def fetch_node_by_id(self, node_id: str) -> dict[str, Any] | None:
        sql = (
            "SELECT id, node_type, title, metric_value, top_k_value "
            "FROM nodes WHERE id = %s LIMIT 1"
        )

        with self._connect() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(sql, (node_id,))
                row = cursor.fetchone()
                return row or None

    def fetch_paper_detail_by_title(self, title: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor(dictionary=True) as cursor:
                paper_columns = [
                    col
                    for col in PAPER_COLUMNS
                    if col != "file_key" or self._paper_has_column(cursor, "file_key")
                ]
                fields = ", ".join(quote_ident(col) for col in paper_columns)
                exact_sql = (
                    f"SELECT {fields} FROM paper "
                    "WHERE title = %s OR file_name = %s "
                    "ORDER BY CASE WHEN title = %s THEN 0 ELSE 1 END "
                    "LIMIT 1"
                )
                fuzzy_sql = (
                    f"SELECT {fields} FROM paper "
                    "WHERE title LIKE %s OR file_name LIKE %s "
                    "LIMIT 1"
                )

                cursor.execute(exact_sql, (title, title, title))
                row = cursor.fetchone()
                if row:
                    return row

                like_pattern = f"%{title}%"
                cursor.execute(fuzzy_sql, (like_pattern, like_pattern))
                return cursor.fetchone() or None

    def get_file_reference_by_node_id(self, node_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor(dictionary=True) as cursor:
                has_file_key = self._paper_has_column(cursor, "file_key")
                file_key_expr = "p.file_key" if has_file_key else "NULL"

                sql = (
                    "SELECT n.id AS node_id, n.node_type AS node_type, n.title AS node_title, "
                    "p.file_name AS file_name, "
                    f"{file_key_expr} AS file_key "
                    "FROM nodes n "
                    "LEFT JOIN paper p ON p.title = n.title "
                    "WHERE n.id = %s LIMIT 1"
                )
                cursor.execute(sql, (node_id,))
                row = cursor.fetchone()
                if not row:
                    return None

                return row

    def fetch_record_detail_by_title(self, title: str) -> dict[str, Any] | None:
        fields = ", ".join(quote_ident(col) for col in RECORD_COLUMNS)
        exact_sql = (
            f"SELECT {fields} FROM all_papers_records "
            f"WHERE {quote_ident('论文名称')} = %s "
            "LIMIT 1"
        )
        fuzzy_sql = (
            f"SELECT {fields} FROM all_papers_records "
            f"WHERE {quote_ident('论文名称')} LIKE %s "
            "LIMIT 1"
        )

        with self._connect() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(exact_sql, (title,))
                row = cursor.fetchone()
                if row:
                    return row

                like_pattern = f"%{title}%"
                cursor.execute(fuzzy_sql, (like_pattern,))
                return cursor.fetchone() or None

    def search_graph(self, keyword: str, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        with self._connect() as conn:
            with conn.cursor(dictionary=True) as cursor:
                backend = self._resolve_search_backend(cursor)

                if backend == SearchBackendMode.FULLTEXT:
                    try:
                        return self._search_with_fulltext(cursor, keyword, limit, offset)
                    except Error:
                        return self._search_with_like(cursor, keyword, limit, offset)

                return self._search_with_like(cursor, keyword, limit, offset)

    def get_search_index_status(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor(dictionary=True) as cursor:
                paper_indexed = self._fetch_fulltext_columns(cursor, "paper")
                record_indexed = self._fetch_fulltext_columns(cursor, "all_papers_records")

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
                            "name": "paper",
                            "required_columns": list(self.PAPER_FULLTEXT_COLUMNS),
                            "indexed_columns": sorted(paper_indexed),
                            "missing_columns": paper_missing,
                        },
                        {
                            "name": "all_papers_records",
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
        return self._has_fulltext_index(cursor, "paper", self.PAPER_FULLTEXT_COLUMNS) and self._has_fulltext_index(
            cursor, "all_papers_records", self.RECORD_FULLTEXT_COLUMNS
        )

    def _fetch_fulltext_columns(self, cursor, table: str) -> set[str]:
        sql = (
            "SELECT DISTINCT COLUMN_NAME FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_TYPE = 'FULLTEXT'"
        )
        cursor.execute(sql, (self._db_config.database, table))
        rows = cursor.fetchall() or []
        return {str(row.get("COLUMN_NAME") or "") for row in rows if row.get("COLUMN_NAME")}

    def _paper_has_column(self, cursor, column_name: str) -> bool:
        if column_name in self._paper_column_cache:
            return self._paper_column_cache[column_name]

        sql = (
            "SELECT 1 FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'paper' AND COLUMN_NAME = %s "
            "LIMIT 1"
        )
        cursor.execute(sql, (self._db_config.database, column_name))
        exists = cursor.fetchone() is not None
        self._paper_column_cache[column_name] = exists
        return exists

    def _has_fulltext_index(self, cursor, table: str, columns: tuple[str, ...]) -> bool:
        cache_key = (table, columns)
        if cache_key in self._fulltext_cache:
            return self._fulltext_cache[cache_key]

        placeholders = ", ".join(["%s"] * len(columns))
        sql = (
            "SELECT 1 FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "AND INDEX_TYPE = 'FULLTEXT' "
            f"AND COLUMN_NAME IN ({placeholders}) LIMIT 1"
        )
        cursor.execute(sql, (self._db_config.database, table, *columns))
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
        data_sql = (
            "SELECT * FROM ("
            "SELECT 'paper' AS source_type, "
            "n.id AS node_id, p.title AS title, p.authors AS authors, p.pub_year AS publish_year, "
            "p.keywords AS keywords, p.abstract AS abstract, "
            "NULL AS tcm_diagnosis, NULL AS western_diagnosis, "
            "MATCH(p.title, p.keywords, p.abstract) AGAINST (%s IN NATURAL LANGUAGE MODE) AS score "
            "FROM paper p "
            "LEFT JOIN nodes n ON n.title = p.title AND n.node_type = 'paper' "
            "WHERE MATCH(p.title, p.keywords, p.abstract) AGAINST (%s IN NATURAL LANGUAGE MODE) "
            "UNION ALL "
            "SELECT 'record' AS source_type, "
            "n.id AS node_id, r.`论文名称` AS title, NULL AS authors, NULL AS publish_year, "
            "NULL AS keywords, NULL AS abstract, "
            "r.`中医证候诊断` AS tcm_diagnosis, r.`西医病名诊断` AS western_diagnosis, "
            "MATCH(r.`论文名称`, r.`中医证候诊断`, r.`西医病名诊断`) AGAINST (%s IN NATURAL LANGUAGE MODE) AS score "
            "FROM all_papers_records r "
            "LEFT JOIN nodes n ON n.title = r.`论文名称` AND n.node_type = 'record' "
            "WHERE MATCH(r.`论文名称`, r.`中医证候诊断`, r.`西医病名诊断`) AGAINST (%s IN NATURAL LANGUAGE MODE) "
            ") AS combined "
            "ORDER BY score DESC, title ASC "
            "LIMIT %s OFFSET %s"
        )

        count_sql = (
            "SELECT COUNT(*) AS total FROM ("
            "SELECT 1 FROM paper p "
            "WHERE MATCH(p.title, p.keywords, p.abstract) AGAINST (%s IN NATURAL LANGUAGE MODE) "
            "UNION ALL "
            "SELECT 1 FROM all_papers_records r "
            "WHERE MATCH(r.`论文名称`, r.`中医证候诊断`, r.`西医病名诊断`) AGAINST (%s IN NATURAL LANGUAGE MODE) "
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
        data_sql = (
            "SELECT * FROM ("
            "SELECT 'paper' AS source_type, "
            "n.id AS node_id, p.title AS title, p.authors AS authors, p.pub_year AS publish_year, "
            "p.keywords AS keywords, p.abstract AS abstract, "
            "NULL AS tcm_diagnosis, NULL AS western_diagnosis, 0 AS score "
            "FROM paper p "
            "LEFT JOIN nodes n ON n.title = p.title AND n.node_type = 'paper' "
            "WHERE (p.title LIKE %s OR p.keywords LIKE %s OR p.abstract LIKE %s) "
            "UNION ALL "
            "SELECT 'record' AS source_type, "
            "n.id AS node_id, r.`论文名称` AS title, NULL AS authors, NULL AS publish_year, "
            "NULL AS keywords, NULL AS abstract, "
            "r.`中医证候诊断` AS tcm_diagnosis, r.`西医病名诊断` AS western_diagnosis, 0 AS score "
            "FROM all_papers_records r "
            "LEFT JOIN nodes n ON n.title = r.`论文名称` AND n.node_type = 'record' "
            "WHERE (r.`论文名称` LIKE %s OR r.`中医证候诊断` LIKE %s OR r.`西医病名诊断` LIKE %s) "
            ") AS combined "
            "ORDER BY score DESC, title ASC "
            "LIMIT %s OFFSET %s"
        )

        count_sql = (
            "SELECT COUNT(*) AS total FROM ("
            "SELECT 1 FROM paper p "
            "WHERE (p.title LIKE %s OR p.keywords LIKE %s OR p.abstract LIKE %s) "
            "UNION ALL "
            "SELECT 1 FROM all_papers_records r "
            "WHERE (r.`论文名称` LIKE %s OR r.`中医证候诊断` LIKE %s OR r.`西医病名诊断` LIKE %s) "
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
