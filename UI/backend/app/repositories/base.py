"""Shared utilities and base class for graph repository sub-modules."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import String, func
from sqlalchemy.orm import Session

from app.config import PostgresSettings, SearchSettings
from app.models import LitMetadata


class GraphRepositoryBase:
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
