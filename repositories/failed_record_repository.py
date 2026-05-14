from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from models.orm import FailedRecord
from models.schemas import FailedRecordCreate


class FailedRecordRepository:
    """Database operations for failed_records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists_by_file_uuid(self, file_uuid: str) -> bool:
        stmt = select(FailedRecord.id).where(FailedRecord.file_uuid == file_uuid).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def upsert(self, data: FailedRecordCreate) -> FailedRecord:
        try:
            stmt = select(FailedRecord).where(FailedRecord.file_uuid == data.file_uuid)
            result = await self.session.execute(stmt)
            record = result.scalar_one_or_none()

            values = data.model_dump()
            if record is None:
                record = FailedRecord(**values)
                self.session.add(record)
            else:
                for key, value in values.items():
                    setattr(record, key, value)

            await self.session.commit()
            await self.session.refresh(record)
            return record
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseError(f"Failed to upsert failed record for {data.file_uuid}: {exc}") from exc

    async def list_all(self) -> list[FailedRecord]:
        stmt = select(FailedRecord).order_by(FailedRecord.created_at.asc(), FailedRecord.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
