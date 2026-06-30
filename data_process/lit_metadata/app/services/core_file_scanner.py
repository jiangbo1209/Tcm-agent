from __future__ import annotations

from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, settings
from app.database import AsyncSessionLocal
from app.models.orm import CoreFile
from app.models.schemas import DatasetFile
from app.repositories.core_file_repository import CoreFileRepository


class CoreFileScanner:
    """Load pending PDF inputs from the core_file table."""

    def __init__(
        self,
        app_settings: Settings = settings,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    ) -> None:
        self.settings = app_settings
        self.session_factory = session_factory

    async def scan(self) -> list[DatasetFile]:
        async with self.session_factory() as session:
            repo = CoreFileRepository(session)
            synced_count = await repo.sync_existing_metadata_statuses()
            if synced_count:
                await session.commit()
                logger.info("Synced existing lit_metadata statuses: count={}", synced_count)
            records = await repo.list_pending_metadata(self.settings.CORE_FILE_PENDING_LIMIT)

        files = [self._to_dataset_file(record) for record in records]
        logger.info("Core file scan finished: pending_pdf_count={}", len(files))
        return files

    @staticmethod
    def _to_dataset_file(record: CoreFile) -> DatasetFile:
        suffix = Path(record.original_name).suffix.lower()
        if not suffix:
            suffix = f".{record.file_type.lower().lstrip('.')}"

        return DatasetFile(
            file_uuid=record.file_uuid,
            file_name=record.original_name,
            file_path=record.storage_path,
            suffix=suffix,
        )
