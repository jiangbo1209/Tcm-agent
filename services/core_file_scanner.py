from __future__ import annotations

from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings, settings
from database import AsyncSessionLocal
from models.orm import CoreFile
from models.schemas import PendingFile
from repositories.core_file_repository import CoreFileRepository


class CoreFileScanner:
    """Load pending PDF inputs from the core_file table."""

    def __init__(
        self,
        app_settings: Settings = settings,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    ) -> None:
        self.settings = app_settings
        self.session_factory = session_factory

    async def scan(self, limit: int | None = None) -> list[PendingFile]:
        scan_limit = self.settings.CORE_FILE_BATCH_SIZE if limit is None else limit
        async with self.session_factory() as session:
            repo = CoreFileRepository(session)
            records = await repo.list_pending_metadata(
                scan_limit,
                skip_failed_records=self.settings.SKIP_FAILED_RECORDS,
            )

        files = [self._to_pending_file(record) for record in records]
        logger.info("Core file scan finished: pending_pdf_count={}", len(files))
        return files

    @staticmethod
    def _to_pending_file(record: CoreFile) -> PendingFile:
        suffix = Path(record.original_name).suffix.lower()
        if not suffix:
            suffix = f".{record.file_type.lower().lstrip('.')}"

        return PendingFile(
            file_uuid=record.file_uuid,
            file_name=record.original_name,
            file_path=record.storage_path,
            suffix=suffix,
        )
