from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.models.orm import CoreFile, LitMetadata

SUPPORTED_DOCUMENT_TYPES = (0, 1, 2)


class CoreFileRepository:
    """Database operations for source records in core_file."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_pending_metadata(self, limit: int = 0) -> list[CoreFile]:
        try:
            existing_metadata = (
                select(LitMetadata.id)
                .where(LitMetadata.file_uuid == CoreFile.file_uuid)
                .exists()
            )
            stmt = (
                select(CoreFile)
                .where(
                    CoreFile.status_metadata.is_(False),
                    CoreFile.document_type.in_(SUPPORTED_DOCUMENT_TYPES),
                    func.lower(CoreFile.file_type) == "pdf",
                    ~existing_metadata,
                )
                .order_by(CoreFile.upload_time.asc(), CoreFile.file_uuid.asc())
            )
            if limit > 0:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to list pending core_file records: {exc}") from exc

    async def sync_existing_metadata_statuses(self) -> int:
        try:
            existing_metadata = (
                select(LitMetadata.id)
                .where(LitMetadata.file_uuid == CoreFile.file_uuid)
                .exists()
            )
            rows_stmt = select(CoreFile.file_uuid).where(
                CoreFile.status_metadata.is_(False),
                CoreFile.document_type.in_(SUPPORTED_DOCUMENT_TYPES),
                func.lower(CoreFile.file_type) == "pdf",
                existing_metadata,
            )
            result = await self.session.execute(rows_stmt)
            file_uuids = list(result.scalars().all())
            if not file_uuids:
                return 0

            await self.session.execute(
                update(CoreFile)
                .where(CoreFile.file_uuid.in_(file_uuids))
                .values(status_metadata=True)
            )
            return len(file_uuids)
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to sync existing lit_metadata statuses: {exc}") from exc

    async def mark_metadata_found(self, file_uuid: str) -> None:
        try:
            stmt = update(CoreFile).where(CoreFile.file_uuid == file_uuid).values(status_metadata=True)
            await self.session.execute(stmt)
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to update core_file status for {file_uuid}: {exc}") from exc
