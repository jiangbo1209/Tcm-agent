"""Database access for RAGFlow synchronization."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Engine, create_engine, text

from .config import RagflowSyncSettings
from .models import CaseSource, LiteratureSource, SourceType, SyncStatus


def connect_database(settings: RagflowSyncSettings) -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


class RagflowSyncRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ensure_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS ragflow_sync_status (
            id SERIAL PRIMARY KEY,
            source_type VARCHAR(32) NOT NULL,
            file_uuid VARCHAR(64) NOT NULL,
            dataset_id VARCHAR(128) NOT NULL,
            ragflow_document_id VARCHAR(128),
            content_hash VARCHAR(128),
            sync_status VARCHAR(32) NOT NULL,
            error_message TEXT,
            synced_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (source_type, file_uuid, dataset_id)
        )
        """
        with self._engine.begin() as conn:
            conn.execute(text(ddl))

    def fetch_literature(self, limit: int | None = None) -> list[LiteratureSource]:
        sql = """
        SELECT
            cf.file_uuid,
            cf.original_name,
            COALESCE(cf.storage_path, lm.storage_path) AS storage_path,
            lm.title,
            lm.authors,
            lm.abstract,
            lm.keywords,
            lm.paper_type,
            lm.source_site,
            lm.source_url,
            lm.journal,
            lm.pub_year,
            lm.matched_title,
            lm.crawl_status
        FROM core_file cf
        JOIN lit_metadata lm ON lm.file_uuid = cf.file_uuid
        WHERE lower(COALESCE(cf.file_type, 'pdf')) = 'pdf'
          AND cf.status_metadata = TRUE
          AND COALESCE(cf.storage_path, lm.storage_path, '') <> ''
        ORDER BY lm.updated_at DESC NULLS LAST, lm.id DESC
        """
        params: dict[str, int] = {}
        if limit:
            sql += " LIMIT :limit"
            params["limit"] = limit

        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [LiteratureSource(**dict(row)) for row in rows]

    def fetch_cases(self, limit: int | None = None) -> list[CaseSource]:
        sql = """
        SELECT
            mc.file_uuid,
            lm.title AS literature_title,
            cf.original_name,
            mc.age,
            mc.bmi,
            mc.menstruation,
            mc.infertility,
            mc.lifestyle,
            mc.present_symptoms,
            mc.medical_history,
            mc.lab_tests,
            mc.ultrasound,
            mc.followup,
            mc.western_diagnosis,
            mc.tcm_diagnosis,
            mc.treatment_principle,
            mc.prescription,
            mc.acupoints,
            mc.assisted_reproduction,
            mc.western_medicine,
            mc.efficacy,
            mc.adverse_reactions,
            mc.commentary
        FROM med_case mc
        LEFT JOIN lit_metadata lm ON lm.file_uuid = mc.file_uuid
        LEFT JOIN core_file cf ON cf.file_uuid = mc.file_uuid
        WHERE cf.file_uuid IS NULL OR cf.status_case = TRUE
        ORDER BY mc.updated_at DESC NULLS LAST, mc.id DESC
        """
        params: dict[str, int] = {}
        if limit:
            sql += " LIMIT :limit"
            params["limit"] = limit

        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [CaseSource(**dict(row)) for row in rows]

    def get_status(self, source_type: SourceType, file_uuid: str, dataset_id: str) -> SyncStatus | None:
        sql = """
        SELECT
            source_type,
            file_uuid,
            dataset_id,
            ragflow_document_id AS document_id,
            content_hash,
            sync_status,
            error_message,
            synced_at
        FROM ragflow_sync_status
        WHERE source_type = :source_type
          AND file_uuid = :file_uuid
          AND dataset_id = :dataset_id
        LIMIT 1
        """
        with self._engine.connect() as conn:
            row = conn.execute(
                text(sql),
                {"source_type": source_type, "file_uuid": file_uuid, "dataset_id": dataset_id},
            ).mappings().first()
        return SyncStatus(**dict(row)) if row else None

    def upsert_status(
        self,
        *,
        source_type: SourceType,
        file_uuid: str,
        dataset_id: str,
        document_id: str | None,
        content_hash: str | None,
        sync_status: str,
        error_message: str | None = None,
    ) -> None:
        sql = """
        INSERT INTO ragflow_sync_status (
            source_type,
            file_uuid,
            dataset_id,
            ragflow_document_id,
            content_hash,
            sync_status,
            error_message,
            synced_at,
            updated_at
        )
        VALUES (
            :source_type,
            :file_uuid,
            :dataset_id,
            :document_id,
            :content_hash,
            :sync_status,
            :error_message,
            NOW(),
            NOW()
        )
        ON CONFLICT (source_type, file_uuid, dataset_id) DO UPDATE SET
            ragflow_document_id = EXCLUDED.ragflow_document_id,
            content_hash = EXCLUDED.content_hash,
            sync_status = EXCLUDED.sync_status,
            error_message = EXCLUDED.error_message,
            synced_at = EXCLUDED.synced_at,
            updated_at = NOW()
        """
        with self._engine.begin() as conn:
            conn.execute(
                text(sql),
                {
                    "source_type": source_type,
                    "file_uuid": file_uuid,
                    "dataset_id": dataset_id,
                    "document_id": document_id,
                    "content_hash": content_hash,
                    "sync_status": sync_status,
                    "error_message": error_message,
                },
            )

    def close(self) -> None:
        self._engine.dispose()


class InMemorySyncRepository:
    """Tiny test/dry-run repository with the same surface as the SQL repository."""

    def __init__(
        self,
        literature: Iterable[LiteratureSource] = (),
        cases: Iterable[CaseSource] = (),
    ) -> None:
        self.literature = list(literature)
        self.cases = list(cases)
        self.statuses: dict[tuple[str, str, str], SyncStatus] = {}

    def ensure_schema(self) -> None:
        return None

    def fetch_literature(self, limit: int | None = None) -> list[LiteratureSource]:
        return self.literature[:limit] if limit else list(self.literature)

    def fetch_cases(self, limit: int | None = None) -> list[CaseSource]:
        return self.cases[:limit] if limit else list(self.cases)

    def get_status(self, source_type: SourceType, file_uuid: str, dataset_id: str) -> SyncStatus | None:
        return self.statuses.get((source_type, file_uuid, dataset_id))

    def upsert_status(
        self,
        *,
        source_type: SourceType,
        file_uuid: str,
        dataset_id: str,
        document_id: str | None,
        content_hash: str | None,
        sync_status: str,
        error_message: str | None = None,
    ) -> None:
        self.statuses[(source_type, file_uuid, dataset_id)] = SyncStatus(
            source_type=source_type,
            file_uuid=file_uuid,
            dataset_id=dataset_id,
            document_id=document_id,
            content_hash=content_hash,
            sync_status=sync_status,
            error_message=error_message,
        )

    def close(self) -> None:
        return None

