from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from models.orm import LitMetadata
from models.schemas import LitMetadataCreate


class LitMetadataRepository:
    """Database operations for lit_metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists_by_file_uuid(self, file_uuid: str) -> bool:
        stmt = select(LitMetadata.id).where(LitMetadata.file_uuid == file_uuid).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_crawl_status_by_file_uuid(self, file_uuid: str) -> str | None:
        stmt = select(LitMetadata.crawl_status).where(LitMetadata.file_uuid == file_uuid).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, data: LitMetadataCreate) -> LitMetadata:
        try:
            existing_stmt = select(LitMetadata).where(LitMetadata.file_uuid == data.file_uuid)
            existing_result = await self.session.execute(existing_stmt)
            record = existing_result.scalar_one_or_none()

            values = data.model_dump()
            if record is None:
                record = LitMetadata(**values)
                self.session.add(record)
            else:
                for key, value in values.items():
                    setattr(record, key, value)

            await self.session.flush()
            return record
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to upsert lit_metadata for {data.file_uuid}: {exc}") from exc
