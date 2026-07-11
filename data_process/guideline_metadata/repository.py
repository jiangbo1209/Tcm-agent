"""Database operations for guideline metadata synchronization."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from UI.backend.app.models import (
    CoreFile,
    GuidelineMetadata,
    LitMetadata,
)

GUIDELINE_DOCUMENT_TYPE = 2


class GuidelineMetadataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_pending(self, limit: int = 0) -> list[tuple[CoreFile, LitMetadata]]:
        stmt = (
            select(CoreFile, LitMetadata)
            .join(LitMetadata, LitMetadata.file_uuid == CoreFile.file_uuid)
            .where(
                CoreFile.document_type == GUIDELINE_DOCUMENT_TYPE,
                CoreFile.status_metadata.is_(True),
                CoreFile.status_guidelinemeta.is_(False),
                func.lower(CoreFile.file_type) == "pdf",
            )
            .order_by(CoreFile.upload_time.asc(), CoreFile.file_uuid.asc())
        )
        if limit > 0:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.all())

    async def upsert_from_lit_metadata(
        self,
        core_file: CoreFile,
        lit_metadata: LitMetadata,
    ) -> None:
        existing_stmt = select(GuidelineMetadata).where(
            GuidelineMetadata.file_uuid == core_file.file_uuid
        )
        existing_result = await self.session.execute(existing_stmt)
        record = existing_result.scalar_one_or_none()

        values = {
            "file_uuid": core_file.file_uuid,
            "original_name": core_file.original_name,
            "storage_path": core_file.storage_path or lit_metadata.storage_path,
            "cleaned_title": lit_metadata.cleaned_title,
            "title": lit_metadata.title,
            "authors": lit_metadata.authors,
            "abstract": lit_metadata.abstract,
            "keywords": lit_metadata.keywords,
            "paper_type": lit_metadata.paper_type,
            "source_site": lit_metadata.source_site,
            "source_url": lit_metadata.source_url,
            "journal": lit_metadata.journal,
            "pub_year": lit_metadata.pub_year,
            "matched_title": lit_metadata.matched_title,
            "is_exact_match": lit_metadata.is_exact_match,
            "crawl_status": lit_metadata.crawl_status,
            "error_message": lit_metadata.error_message,
        }

        if record is None:
            self.session.add(GuidelineMetadata(**values))
        else:
            for key, value in values.items():
                setattr(record, key, value)

        await self.session.execute(
            update(CoreFile)
            .where(CoreFile.file_uuid == core_file.file_uuid)
            .values(status_guidelinemeta=True)
        )
        await self.session.flush()
