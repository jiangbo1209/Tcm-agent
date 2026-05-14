from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.models.orm import CoreFile


class CoreFileRepository:
    """Database operations for source records in core_file."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_pending_metadata(self, limit: int = 0) -> list[CoreFile]:
        try:
            stmt = (
                select(CoreFile)
                .where(
                    CoreFile.status_metadata.is_(False),
                    func.lower(CoreFile.file_type) == "pdf",
                )
                .order_by(CoreFile.upload_time.asc(), CoreFile.file_uuid.asc())
            )
            if limit > 0:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to list pending core_file records: {exc}") from exc

    async def mark_metadata_found(self, file_uuid: str) -> None:
        try:
            stmt = update(CoreFile).where(CoreFile.file_uuid == file_uuid).values(status_metadata=True)
            await self.session.execute(stmt)
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to update core_file status for {file_uuid}: {exc}") from exc
