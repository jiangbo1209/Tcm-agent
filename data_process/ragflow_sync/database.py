"""Database access for RAGFlow synchronization."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Engine, and_, create_engine, exists, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from data_process.case_metadata.models import MedCase
from data_process.lit_metadata.app.models.orm import GuidelineMetadata, LitMetadata
from data_process.pdf_upload.models import CoreFile

from .config import RagflowSyncSettings
from .models import CaseSource, GuidelineSource, LiteratureSource, SourceType, SyncStatus
from .orm import RagflowSyncStatus


def connect_database(settings: RagflowSyncSettings) -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


class RagflowSyncRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    def ensure_schema(self) -> None:
        RagflowSyncStatus.__table__.create(bind=self._engine, checkfirst=True)

    def fetch_literature(
        self,
        limit: int | None = None,
        *,
        only_failed: bool = False,
        dataset_id: str | None = None,
    ) -> list[LiteratureSource]:
        with self._session_factory() as session:
            stmt = (
                select(CoreFile, LitMetadata)
                .join(LitMetadata, LitMetadata.file_uuid == CoreFile.file_uuid)
                .where(func.lower(func.coalesce(CoreFile.file_type, "pdf")) == "pdf")
                .where(CoreFile.document_type == 0)
                .where(CoreFile.status_metadata.is_(True))
                .where(func.coalesce(CoreFile.storage_path, LitMetadata.storage_path, "") != "")
                .order_by(LitMetadata.updated_at.desc().nulls_last(), LitMetadata.id.desc())
            )
            if only_failed:
                if not dataset_id:
                    raise ValueError("dataset_id is required when only_failed=True")
                stmt = stmt.where(
                    exists().where(
                        RagflowSyncStatus.source_type == "literature",
                        RagflowSyncStatus.file_uuid == CoreFile.file_uuid,
                        RagflowSyncStatus.dataset_id == dataset_id,
                        RagflowSyncStatus.sync_status == "failed",
                    )
                )
            if limit:
                stmt = stmt.limit(limit)

            rows = session.execute(stmt).all()

        return [self._map_literature(core_file, lit_metadata) for core_file, lit_metadata in rows]

    def fetch_cases(
        self,
        limit: int | None = None,
        *,
        only_failed: bool = False,
        dataset_id: str | None = None,
    ) -> list[CaseSource]:
        with self._session_factory() as session:
            stmt = (
                select(MedCase, LitMetadata, CoreFile)
                .outerjoin(LitMetadata, LitMetadata.file_uuid == MedCase.file_uuid)
                .outerjoin(CoreFile, CoreFile.file_uuid == MedCase.file_uuid)
                .where(or_(CoreFile.file_uuid.is_(None), CoreFile.status_case.is_(True)))
                .where(or_(CoreFile.file_uuid.is_(None), CoreFile.document_type == 1))
                .order_by(MedCase.updated_at.desc().nulls_last(), MedCase.id.desc())
            )
            if only_failed:
                if not dataset_id:
                    raise ValueError("dataset_id is required when only_failed=True")
                stmt = stmt.where(
                    exists().where(
                        RagflowSyncStatus.source_type == "case",
                        RagflowSyncStatus.file_uuid == MedCase.file_uuid,
                        RagflowSyncStatus.dataset_id == dataset_id,
                        RagflowSyncStatus.sync_status == "failed",
                    )
                )
            if limit:
                stmt = stmt.limit(limit)

            rows = session.execute(stmt).all()

        return [self._map_case(med_case, lit_metadata, core_file) for med_case, lit_metadata, core_file in rows]

    def fetch_guidelines(
        self,
        limit: int | None = None,
        *,
        only_failed: bool = False,
        dataset_id: str | None = None,
    ) -> list[GuidelineSource]:
        with self._session_factory() as session:
            stmt = (
                select(CoreFile, GuidelineMetadata)
                .join(GuidelineMetadata, GuidelineMetadata.file_uuid == CoreFile.file_uuid)
                .where(func.lower(func.coalesce(CoreFile.file_type, "pdf")) == "pdf")
                .where(CoreFile.document_type == 2)
                .where(CoreFile.status_guidelinemeta.is_(True))
                .where(func.coalesce(CoreFile.storage_path, GuidelineMetadata.storage_path, "") != "")
                .order_by(GuidelineMetadata.updated_at.desc().nulls_last(), GuidelineMetadata.id.desc())
            )
            if only_failed:
                if not dataset_id:
                    raise ValueError("dataset_id is required when only_failed=True")
                stmt = stmt.where(
                    exists().where(
                        RagflowSyncStatus.source_type == "guideline",
                        RagflowSyncStatus.file_uuid == CoreFile.file_uuid,
                        RagflowSyncStatus.dataset_id == dataset_id,
                        RagflowSyncStatus.sync_status == "failed",
                    )
                )
            if limit:
                stmt = stmt.limit(limit)

            rows = session.execute(stmt).all()

        return [self._map_guideline(core_file, guideline_metadata) for core_file, guideline_metadata in rows]

    def get_status(self, source_type: SourceType, file_uuid: str, dataset_id: str) -> SyncStatus | None:
        with self._session_factory() as session:
            row = self._get_status_row(session, source_type, file_uuid, dataset_id)
            return self._map_status(row) if row else None

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
        with self._session_factory() as session:
            row = self._get_status_row(session, source_type, file_uuid, dataset_id)
            if row is None:
                row = RagflowSyncStatus(
                    source_type=source_type,
                    file_uuid=file_uuid,
                    dataset_id=dataset_id,
                )
                session.add(row)

            row.ragflow_document_id = document_id
            row.content_hash = content_hash
            row.sync_status = sync_status
            row.error_message = error_message
            row.synced_at = func.now()
            row.updated_at = func.now()
            session.commit()

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _get_status_row(
        session: Session,
        source_type: SourceType,
        file_uuid: str,
        dataset_id: str,
    ) -> RagflowSyncStatus | None:
        stmt = select(RagflowSyncStatus).where(
            and_(
                RagflowSyncStatus.source_type == source_type,
                RagflowSyncStatus.file_uuid == file_uuid,
                RagflowSyncStatus.dataset_id == dataset_id,
            )
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _map_literature(core_file: CoreFile, lit_metadata: LitMetadata) -> LiteratureSource:
        return LiteratureSource(
            file_uuid=core_file.file_uuid,
            original_name=core_file.original_name,
            storage_path=core_file.storage_path or lit_metadata.storage_path,
            title=lit_metadata.title,
            authors=lit_metadata.authors,
            abstract=lit_metadata.abstract,
            keywords=lit_metadata.keywords,
            paper_type=lit_metadata.paper_type,
            source_site=lit_metadata.source_site,
            source_url=lit_metadata.source_url,
            journal=lit_metadata.journal,
            pub_year=lit_metadata.pub_year,
            matched_title=lit_metadata.matched_title,
            crawl_status=lit_metadata.crawl_status,
        )

    @staticmethod
    def _map_guideline(core_file: CoreFile, guideline_metadata: GuidelineMetadata) -> GuidelineSource:
        return GuidelineSource(
            file_uuid=core_file.file_uuid,
            original_name=core_file.original_name,
            storage_path=core_file.storage_path or guideline_metadata.storage_path,
            title=guideline_metadata.title,
            authors=guideline_metadata.authors,
            abstract=guideline_metadata.abstract,
            keywords=guideline_metadata.keywords,
            paper_type=guideline_metadata.paper_type,
            source_site=guideline_metadata.source_site,
            source_url=guideline_metadata.source_url,
            journal=guideline_metadata.journal,
            pub_year=guideline_metadata.pub_year,
            matched_title=guideline_metadata.matched_title,
            crawl_status=guideline_metadata.crawl_status,
        )

    @staticmethod
    def _map_case(med_case: MedCase, lit_metadata: LitMetadata | None, core_file: CoreFile | None) -> CaseSource:
        return CaseSource(
            file_uuid=med_case.file_uuid,
            literature_title=lit_metadata.title if lit_metadata else None,
            original_name=core_file.original_name if core_file else None,
            age=med_case.age,
            bmi=med_case.bmi,
            menstruation=med_case.menstruation,
            infertility=med_case.infertility,
            lifestyle=med_case.lifestyle,
            present_symptoms=med_case.present_symptoms,
            medical_history=med_case.medical_history,
            lab_tests=med_case.lab_tests,
            ultrasound=med_case.ultrasound,
            followup=med_case.followup,
            western_diagnosis=med_case.western_diagnosis,
            tcm_diagnosis=med_case.tcm_diagnosis,
            treatment_principle=med_case.treatment_principle,
            prescription=med_case.prescription,
            acupoints=med_case.acupoints,
            assisted_reproduction=med_case.assisted_reproduction,
            western_medicine=med_case.western_medicine,
            efficacy=med_case.efficacy,
            adverse_reactions=med_case.adverse_reactions,
            commentary=med_case.commentary,
        )

    @staticmethod
    def _map_status(row: RagflowSyncStatus) -> SyncStatus:
        return SyncStatus(
            source_type=row.source_type,  # type: ignore[arg-type]
            file_uuid=row.file_uuid,
            dataset_id=row.dataset_id,
            document_id=row.ragflow_document_id,
            content_hash=row.content_hash,
            sync_status=row.sync_status,
            error_message=row.error_message,
            synced_at=row.synced_at,
        )


class InMemorySyncRepository:
    """Tiny test/dry-run repository with the same surface as the SQL repository."""

    def __init__(
        self,
        literature: Iterable[LiteratureSource] = (),
        cases: Iterable[CaseSource] = (),
        guidelines: Iterable[GuidelineSource] = (),
    ) -> None:
        self.literature = list(literature)
        self.cases = list(cases)
        self.guidelines = list(guidelines)
        self.statuses: dict[tuple[str, str, str], SyncStatus] = {}

    def ensure_schema(self) -> None:
        return None

    def fetch_literature(
        self,
        limit: int | None = None,
        *,
        only_failed: bool = False,
        dataset_id: str | None = None,
    ) -> list[LiteratureSource]:
        items = list(self.literature)
        if only_failed:
            items = [
                item
                for item in items
                if dataset_id
                and self.statuses.get(("literature", item.file_uuid, dataset_id)) is not None
                and self.statuses[("literature", item.file_uuid, dataset_id)].sync_status == "failed"
            ]
        return items[:limit] if limit else items

    def fetch_cases(
        self,
        limit: int | None = None,
        *,
        only_failed: bool = False,
        dataset_id: str | None = None,
    ) -> list[CaseSource]:
        items = list(self.cases)
        if only_failed:
            items = [
                item
                for item in items
                if dataset_id
                and self.statuses.get(("case", item.file_uuid, dataset_id)) is not None
                and self.statuses[("case", item.file_uuid, dataset_id)].sync_status == "failed"
            ]
        return items[:limit] if limit else items

    def fetch_guidelines(
        self,
        limit: int | None = None,
        *,
        only_failed: bool = False,
        dataset_id: str | None = None,
    ) -> list[GuidelineSource]:
        items = list(self.guidelines)
        if only_failed:
            items = [
                item
                for item in items
                if dataset_id
                and self.statuses.get(("guideline", item.file_uuid, dataset_id)) is not None
                and self.statuses[("guideline", item.file_uuid, dataset_id)].sync_status == "failed"
            ]
        return items[:limit] if limit else items

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
