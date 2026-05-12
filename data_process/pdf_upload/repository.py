"""Async CRUD repository for CoreFile."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CoreFile


class CoreFileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, core_file: CoreFile) -> CoreFile:
        self._session.add(core_file)
        await self._session.flush()
        await self._session.refresh(core_file)
        return core_file

    async def get_by_uuid(self, file_uuid: str) -> CoreFile | None:
        stmt = select(CoreFile).where(CoreFile.file_uuid == file_uuid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_files(
        self, *, page: int = 1, size: int = 20
    ) -> tuple[Sequence[CoreFile], int]:
        count_stmt = select(func.count()).select_from(CoreFile)
        total = (await self._session.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * size
        data_stmt = (
            select(CoreFile)
            .order_by(CoreFile.upload_time.desc())
            .offset(offset)
            .limit(size)
        )
        result = await self._session.execute(data_stmt)
        items = result.scalars().all()
        return items, total

    async def exists_by_original_name(self, original_name: str) -> bool:
        stmt = select(func.count()).select_from(CoreFile).where(
            CoreFile.original_name == original_name
        )
        count = (await self._session.execute(stmt)).scalar() or 0
        return count > 0

    async def delete_by_uuid(self, file_uuid: str) -> bool:
        stmt = delete(CoreFile).where(CoreFile.file_uuid == file_uuid)
        result = await self._session.execute(stmt)
        return result.rowcount > 0  # type: ignore[attr-defined]

    async def delete_by_uuids(self, file_uuids: list[str]) -> dict[str, CoreFile]:
        """Delete multiple files and return deleted file info.

        Returns a map of uuid -> CoreFile for records that existed.
        """
        if not file_uuids:
            return {}

        # Fetch first for response details
        stmt = select(CoreFile).where(CoreFile.file_uuid.in_(file_uuids))
        result = await self._session.execute(stmt)
        files = result.scalars().all()
        files_map = {f.file_uuid: f for f in files}

        # Delete in one statement
        delete_stmt = delete(CoreFile).where(CoreFile.file_uuid.in_(file_uuids))
        await self._session.execute(delete_stmt)

        return files_map
