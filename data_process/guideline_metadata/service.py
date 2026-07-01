"""Synchronize guideline rows from lit_metadata into guideline_metadata."""

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data_process.lit_metadata.app.models.orm import Base
from data_process.pdf_upload.config import get_postgres_config

from .repository import GuidelineMetadataRepository
from .schemas import GuidelineSyncItem, GuidelineSyncSummary

LOGGER = logging.getLogger("guideline_metadata")


class GuidelineMetadataSyncService:
    def __init__(self) -> None:
        pg_config = get_postgres_config()
        self._engine = create_async_engine(
            pg_config.dsn,
            echo=False,
            pool_size=5,
            json_serializer=lambda value: json.dumps(value, ensure_ascii=False),
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def ensure_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def sync_pending(self, limit: int = 0) -> GuidelineSyncSummary:
        summary = GuidelineSyncSummary()

        async with self._session_factory() as session:
            repository = GuidelineMetadataRepository(session)
            pending = await repository.list_pending(limit=limit)
            summary.total = len(pending)

            if not pending:
                LOGGER.info("No pending guideline metadata to sync")
                return summary

            LOGGER.info("Found %d pending guideline metadata rows", len(pending))

            for core_file, lit_metadata in pending:
                item = GuidelineSyncItem(
                    file_uuid=core_file.file_uuid,
                    original_name=core_file.original_name,
                    success=False,
                )
                try:
                    await repository.upsert_from_lit_metadata(core_file, lit_metadata)
                    await session.commit()
                    item.success = True
                    summary.synced += 1
                    LOGGER.info("Synced guideline metadata: %s", core_file.original_name)
                except Exception as exc:
                    await session.rollback()
                    item.error = str(exc)
                    summary.failed += 1
                    LOGGER.exception(
                        "Failed to sync guideline metadata: %s",
                        core_file.original_name,
                    )

                summary.results.append(item)

        return summary

    async def dispose(self) -> None:
        await self._engine.dispose()
