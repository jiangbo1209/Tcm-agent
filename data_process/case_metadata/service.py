"""Core service: download PDF from object storage, extract case data via LLM, insert into DB."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from UI.backend.app.config import PostgresSettings
from UI.backend.app.models import Base, CoreFile, MedCase
from UI.backend.app.storage import S3Client, get_s3_config

from .llm_client import (
    build_final_prompt,
    build_payload,
    call_gemini_stream,
    extract_json_object,
    jsonschema_to_gemini_schema,
    load_json_file,
    normalize_record,
    validate_record,
    MAX_RETRIES,
    RETRY_DELAY,
)
from .schemas import ExtractionResult, ExtractionSummary, map_chinese_to_english

LOGGER = logging.getLogger("case_metadata")

_MODULE_DIR = Path(__file__).resolve().parent
_PROMPT_PATH = _MODULE_DIR / "prompt.md"
_SCHEMA_PATH = _MODULE_DIR / "schema.json"
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "case_metadata"


def _setup_file_logger() -> logging.Handler:
    """Add a file handler that appends every extraction result to a log file."""
    logger = logging.getLogger("case_metadata")
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            return handler

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOG_DIR / f"extraction_{datetime.now().strftime('%Y%m%d')}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)
    return fh


class CaseExtractionService:
    def __init__(self) -> None:
        pg_config = PostgresSettings()
        self._engine = create_async_engine(pg_config.async_dsn, echo=False, pool_size=5)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self._s3 = S3Client(get_s3_config())

        # Load prompt + schema (once at init)
        self._prompt_md = _PROMPT_PATH.read_text(encoding="utf-8")
        self._local_schema = load_json_file(_SCHEMA_PATH)
        self._field_names = list(self._local_schema.get("properties", {}).keys())
        self._final_prompt = build_final_prompt(self._prompt_md, self._field_names)
        self._gemini_schema = jsonschema_to_gemini_schema(self._local_schema)

        # Enable file logging
        _setup_file_logger()

    async def ensure_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ux_case_metadata_file_uuid ON case_metadata (file_uuid)"
                )
            )

    async def process_pending_cases(self, limit: int | None = None) -> ExtractionSummary:
        summary = ExtractionSummary()

        async with self._session_factory() as session:

            synced_existing = await self._sync_existing_case_statuses(session)
            for core_file in synced_existing:
                summary.results.append(
                    ExtractionResult(
                        file_uuid=core_file.file_uuid,
                        original_name=core_file.original_name,
                        success=True,
                        skipped=True,
                    )
                )
            summary.skipped += len(synced_existing)

            # Query pending records
            existing_case = select(MedCase.id).where(MedCase.file_uuid == CoreFile.file_uuid).exists()
            stmt = (
                select(CoreFile)
                .where(
                    CoreFile.document_type == 1,
                    func.lower(CoreFile.file_type) == "pdf",
                    CoreFile.status_case == False,  # noqa: E712
                    ~existing_case,
                )
                .order_by(CoreFile.upload_time.asc())
            )
            if limit is not None:
                stmt = stmt.limit(max(0, limit))
            result = await session.execute(stmt)
            pending = result.scalars().all()

            summary.total = len(pending) + summary.skipped
            if not pending:
                LOGGER.info("No pending cases to process")
                return summary

            LOGGER.info(
                "Found %d pending cases%s",
                len(pending),
                f" (limit={limit})" if limit is not None else "",
            )

            for core_file in pending:
                try:
                    extraction = await self._process_one(
                        session,
                        core_file.file_uuid,
                        core_file.storage_path,
                        core_file.original_name,
                    )
                except Exception as exc:
                    await session.rollback()
                    LOGGER.exception("Unexpected failure for %s", core_file.original_name)
                    extraction = ExtractionResult(
                        file_uuid=core_file.file_uuid,
                        original_name=core_file.original_name,
                        success=False,
                        error=f"Unexpected error: {exc}",
                    )
                summary.results.append(extraction)

                if extraction.success:
                    if extraction.skipped:
                        summary.skipped += 1
                    else:
                        summary.success += 1
                else:
                    summary.failed += 1

        return summary

    async def _sync_existing_case_statuses(self, session: AsyncSession) -> list:

        existing_case = select(MedCase.id).where(MedCase.file_uuid == CoreFile.file_uuid).exists()
        stmt = (
            select(CoreFile)
            .where(
                CoreFile.document_type == 1,
                func.lower(CoreFile.file_type) == "pdf",
                CoreFile.status_case == False,  # noqa: E712
                existing_case,
            )
            .order_by(CoreFile.upload_time.asc())
        )
        result = await session.execute(stmt)
        stale_rows = result.scalars().all()
        if not stale_rows:
            return []

        await session.execute(
            update(CoreFile)
            .where(CoreFile.file_uuid.in_([row.file_uuid for row in stale_rows]))
            .values(status_case=True)
        )
        await session.commit()
        LOGGER.info("Skipped %d cases already present in case_metadata", len(stale_rows))
        return stale_rows

    async def _process_one(self, session: AsyncSession, file_uuid: str, storage_path: str, original_name: str) -> ExtractionResult:
        extraction = ExtractionResult(file_uuid=file_uuid, original_name=original_name, success=False)
        t_start = time.monotonic()

        if await self._case_metadata_exists(session, file_uuid):
            await self._mark_case_processed(session, file_uuid)
            extraction.success = True
            extraction.skipped = True
            elapsed = time.monotonic() - t_start
            LOGGER.info("RESULT | SKIP | %s | reason=already_extracted | elapsed=%.1fs", original_name, elapsed)
            return extraction

        # 1. Download PDF from object storage (Tencent COS)
        try:
            pdf_bytes = self._s3.get_object(storage_path)
        except Exception as exc:
            elapsed = time.monotonic() - t_start
            LOGGER.exception("Failed to download %s from COS", storage_path)
            extraction.error = f"COS download failed: {exc}"
            LOGGER.info(
                "RESULT | FAIL | %s | phase=download | elapsed=%.1fs | error=%s",
                original_name, elapsed, exc,
            )
            return extraction

        LOGGER.info("Downloaded %s (%d bytes)", original_name, len(pdf_bytes))

        # 2. Call LLM with retries
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                payload = build_payload(self._final_prompt, pdf_bytes, self._gemini_schema)
                raw_text = call_gemini_stream(payload)
                break
            except Exception as exc:
                LOGGER.warning("Attempt %d/%d failed for %s: %s", attempt, MAX_RETRIES, original_name, exc)
                if attempt >= MAX_RETRIES:
                    elapsed = time.monotonic() - t_start
                    extraction.error = f"LLM call failed after {MAX_RETRIES} retries: {exc}"
                    LOGGER.info(
                        "RESULT | FAIL | %s | phase=llm | elapsed=%.1fs | retries=%d | error=%s",
                        original_name, elapsed, MAX_RETRIES, exc,
                    )
                    return extraction
                import asyncio
                await asyncio.sleep(RETRY_DELAY)

        # 3. Parse JSON
        try:
            parsed = extract_json_object(raw_text)
        except ValueError as exc:
            elapsed = time.monotonic() - t_start
            extraction.error = f"JSON parse failed: {exc}"
            LOGGER.info(
                "RESULT | FAIL | %s | phase=parse | elapsed=%.1fs | error=%s",
                original_name, elapsed, exc,
            )
            return extraction

        # 4. Normalize + validate
        normalized, missing_fields, extra_fields = normalize_record(parsed, self._field_names)
        extraction.missing_fields = missing_fields
        extraction.extra_fields = extra_fields

        try:
            validate_record(normalized, self._local_schema)
        except ValueError as exc:
            LOGGER.warning("Schema validation warning for %s: %s", original_name, exc)

        # 5. Map Chinese keys → English columns
        mapped = map_chinese_to_english(normalized)
        mapped["file_uuid"] = file_uuid

        # 6. Insert into case_metadata
        med_case = MedCase(**mapped)
        session.add(med_case)

        # 7. Update CORE_FILE.status_case = true
        await session.execute(
            update(CoreFile).where(CoreFile.file_uuid == file_uuid).values(status_case=True)
        )

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await self._mark_case_processed(session, file_uuid)
            extraction.success = True
            extraction.skipped = True
            elapsed = time.monotonic() - t_start
            LOGGER.info("RESULT | SKIP | %s | reason=duplicate_insert | elapsed=%.1fs", original_name, elapsed)
            return extraction
        except SQLAlchemyError as exc:
            await session.rollback()
            extraction.error = f"Database commit failed: {exc}"
            elapsed = time.monotonic() - t_start
            LOGGER.exception("RESULT | FAIL | %s | phase=commit | elapsed=%.1fs", original_name, elapsed)
            return extraction

        extraction.success = True
        elapsed = time.monotonic() - t_start
        LOGGER.info(
            "RESULT | OK | %s | elapsed=%.1fs | missing=%d%s",
            original_name, elapsed, len(missing_fields),
            f" [{','.join(missing_fields[:5])}]" if missing_fields else "",
        )
        return extraction

    async def _case_metadata_exists(self, session: AsyncSession, file_uuid: str) -> bool:
        stmt = select(MedCase.id).where(MedCase.file_uuid == file_uuid).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _mark_case_processed(self, session: AsyncSession, file_uuid: str) -> None:

        await session.execute(
            update(CoreFile)
            .where(
                CoreFile.file_uuid == file_uuid,
                CoreFile.document_type == 1,
            )
            .values(status_case=True)
        )
        await session.commit()

    async def dispose(self) -> None:
        await self._engine.dispose()
