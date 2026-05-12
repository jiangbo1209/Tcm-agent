from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.models.orm import PaperRecord
from app.models.schemas import PaperRecordCreate


class PaperRepository:
    """Database operations for paper_records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists_by_file_name(self, file_name: str) -> bool:
        stmt = select(PaperRecord.id).where(PaperRecord.file_name == file_name).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(self, data: PaperRecordCreate) -> PaperRecord:
        try:
            existing_stmt = select(PaperRecord).where(PaperRecord.file_name == data.file_name)
            existing_result = await self.session.execute(existing_stmt)
            record = existing_result.scalar_one_or_none()

            values = data.model_dump()
            if record is None:
                record = PaperRecord(**values)
                self.session.add(record)
            else:
                for key, value in values.items():
                    setattr(record, key, value)

            await self.session.commit()
            await self.session.refresh(record)
            return record
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseError(f"Failed to create paper record for {data.file_name}: {exc}") from exc

    async def count_by_status(self, status: str) -> int:
        stmt = select(func.count()).select_from(PaperRecord).where(PaperRecord.crawl_status == status)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
