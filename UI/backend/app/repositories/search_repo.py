"""Search and facet queries (fulltext + ILIKE backends)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.models.search_history import SearchBackendMode


class SearchRepoMixin:
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
        filters = filters or {}

        def _compute_facets(exclude_topics: bool = False) -> list[dict[str, Any]]:
            facet_filters = {
                k: v for k, v in filters.items()
                if not (exclude_topics and k == "topics")
            }
            with self._get_session() as session:
                backend = self._resolve_search_backend(session)
                if backend == SearchBackendMode.FULLTEXT:
                    try:
                        return self._search_facet_rows_with_fulltext(session, keyword, source_type, facet_filters)
                    except Exception:
                        return self._search_facet_rows_with_like(session, keyword, source_type, facet_filters)
                return self._search_facet_rows_with_like(session, keyword, source_type, facet_filters)

        rows_with_topics = _compute_facets(exclude_topics=False)
        rows_for_topics = _compute_facets(exclude_topics=True) if filters.get("topics") else rows_with_topics

        from collections import Counter
        counters: dict[str, Counter[str]] = {
            "source_types": Counter(),
            "topics": Counter(),
            "years": Counter(),
            "journals": Counter(),
            "paper_types": Counter(),
        }

        for row in rows_with_topics:
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

        for row in rows_for_topics:
            for topic in self._split_listish_facet(row.get("keywords_text")):
                counters["topics"][topic] += 1

        facets: dict[str, list[dict[str, int | str]]] = {
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

    def _search_with_fulltext(
        self,
        session,
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
        session,
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
        session,
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
        session,
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
