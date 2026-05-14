from __future__ import annotations

from collections.abc import AsyncIterator

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from core.exceptions import DatabaseError
from models.orm import Base, FailedRecord, LitMetadata


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    tables = [FailedRecord.__table__, LitMetadata.__table__]

    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
            await conn.execute(text("ALTER TABLE failed_records ADD COLUMN IF NOT EXISTS file_uuid VARCHAR"))
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_failed_records_file_uuid "
                    "ON failed_records(file_uuid) "
                    "WHERE file_uuid IS NOT NULL"
                )
            )
            await _check_metadata_state(conn)
            if settings.REPAIR_METADATA_STATE:
                await _flag_partial_metadata_as_failed(conn)
                await _reset_orphan_completed_core_files(conn)
    except SQLAlchemyError as exc:
        raise DatabaseError(_format_database_error(exc)) from exc
    except Exception as exc:
        raise DatabaseError(_format_database_error(exc)) from exc


async def _check_metadata_state(conn: AsyncConnection) -> None:
    partial_count = await conn.scalar(
        text("SELECT count(*) FROM lit_metadata WHERE crawl_status = 'partial'")
    )
    orphan_completed_count = await conn.scalar(
        text(
            """
            SELECT count(*)
            FROM core_file AS cf
            WHERE cf.status_metadata = true
              AND lower(cf.file_type) = 'pdf'
              AND NOT EXISTS (
                  SELECT 1
                  FROM lit_metadata AS lm
                  WHERE lm.file_uuid = cf.file_uuid
              )
            """
        )
    )

    if partial_count:
        logger.warning(
            "Found partial lit_metadata rows: count={}. "
            "They are not repaired automatically because REPAIR_METADATA_STATE=false.",
            partial_count,
        )
    if orphan_completed_count:
        logger.warning(
            "Found completed core_file PDF rows without lit_metadata: count={}. "
            "They are not repaired automatically because REPAIR_METADATA_STATE=false.",
            orphan_completed_count,
        )


async def _flag_partial_metadata_as_failed(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO failed_records (
                file_uuid,
                file_name,
                file_path,
                cleaned_title,
                attempted_sites,
                failure_reason,
                error_message,
                suggested_action
            )
            SELECT
                lm.file_uuid,
                lm.original_name,
                lm.storage_path,
                lm.cleaned_title,
                json_build_array(lm.source_site),
                'missing_metadata_fields',
                COALESCE(lm.error_message, 'Missing metadata fields'),
                'complete_metadata'
            FROM lit_metadata AS lm
            WHERE lm.crawl_status = 'partial'
              AND NOT EXISTS (
                  SELECT 1
                  FROM failed_records AS fr
                  WHERE fr.file_uuid = lm.file_uuid
              )
            """
        )
    )
    await conn.execute(
        text(
            """
            UPDATE failed_records AS fr
            SET
                file_name = lm.original_name,
                file_path = lm.storage_path,
                cleaned_title = lm.cleaned_title,
                attempted_sites = json_build_array(lm.source_site),
                failure_reason = 'missing_metadata_fields',
                error_message = COALESCE(lm.error_message, 'Missing metadata fields'),
                suggested_action = 'complete_metadata',
                updated_at = now()
            FROM lit_metadata AS lm
            WHERE lm.crawl_status = 'partial'
              AND fr.file_uuid = lm.file_uuid
            """
        )
    )
    await conn.execute(
        text(
            """
            UPDATE core_file AS cf
            SET status_metadata = false
            FROM lit_metadata AS lm
            WHERE lm.crawl_status = 'partial'
              AND cf.file_uuid = lm.file_uuid
            """
        )
    )


async def _reset_orphan_completed_core_files(conn: AsyncConnection) -> None:
    result = await conn.execute(
        text(
            """
            UPDATE core_file AS cf
            SET status_metadata = false
            WHERE cf.status_metadata = true
              AND lower(cf.file_type) = 'pdf'
              AND NOT EXISTS (
                  SELECT 1
                  FROM lit_metadata AS lm
                  WHERE lm.file_uuid = cf.file_uuid
              )
            """
        )
    )
    if result.rowcount:
        logger.warning(
            "Reset orphan completed core_file rows without lit_metadata: count={}",
            result.rowcount,
        )


def _format_database_error(exc: Exception) -> str:
    target = settings.redacted_database_url
    if _exception_chain_contains(exc, "InvalidPasswordError"):
        return (
            "Database authentication failed. Check DATABASE_URL in .env, replace the "
            "placeholder with the real PostgreSQL password, and URL-encode special "
            f"characters such as @ as %40. Target: {target}"
        )
    return f"Failed to initialize database at {target}: {exc}"


def _exception_chain_contains(exc: BaseException, class_name: str) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if current.__class__.__name__ == class_name:
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
