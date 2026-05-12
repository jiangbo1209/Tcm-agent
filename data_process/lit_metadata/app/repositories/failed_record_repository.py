from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.models.orm import FailedRecord
from app.models.schemas import FailedRecordCreate


class FailedRecordRepository:
    """Database operations for failed_records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists_by_file_name(self, file_name: str) -> bool:
        stmt = select(FailedRecord.id).where(FailedRecord.file_name == file_name).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(self, data: FailedRecordCreate) -> FailedRecord:
        try:
            record = FailedRecord(**data.model_dump())
            self.session.add(record)
            await self.session.commit()
            await self.session.refresh(record)
            return record
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseError(f"Failed to create failed record for {data.file_name}: {exc}") from exc

    async def list_all(self) -> list[FailedRecord]:
        stmt = select(FailedRecord).order_by(FailedRecord.created_at.asc(), FailedRecord.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
