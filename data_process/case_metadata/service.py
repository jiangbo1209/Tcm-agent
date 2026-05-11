"""Core service: download PDF from MinIO, extract case data via LLM, insert into DB."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_process.pdf_upload.config import get_minio_config, get_postgres_config
from data_process.pdf_upload.minio_client import MinioClient
from data_process.pdf_upload.models import Base

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
from .models import MedCase
from .schemas import ExtractionResult, ExtractionSummary, map_chinese_to_english

LOGGER = logging.getLogger("case_metadata")

_MODULE_DIR = Path(__file__).resolve().parent
_PROMPT_PATH = _MODULE_DIR / "prompt.md"
_SCHEMA_PATH = _MODULE_DIR / "schema.json"
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "case_metadata"


def _setup_file_logger() -> logging.Handler:
    """Add a file handler that appends every extraction result to a log file."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOG_DIR / f"extraction_{datetime.now().strftime('%Y%m%d')}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.getLogger("case_metadata").addHandler(fh)
    return fh


class CaseExtractionService:
    def __init__(self) -> None:
        pg_config = get_postgres_config()
        self._engine = create_async_engine(pg_config.dsn, echo=False, pool_size=5)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self._minio = MinioClient(get_minio_config())

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

    async def process_pending_cases(self) -> ExtractionSummary:
        summary = ExtractionSummary()

        async with self._session_factory() as session:
            # Query pending records
            from data_process.pdf_upload.models import CoreFile
            stmt = select(CoreFile).where(CoreFile.status_case == False)  # noqa: E712
            result = await session.execute(stmt)
            pending = result.scalars().all()

            summary.total = len(pending)
            if not pending:
                LOGGER.info("No pending cases to process")
                return summary

            LOGGER.info("Found %d pending cases", len(pending))

            for core_file in pending:
                extraction = await self._process_one(session, core_file.file_uuid, core_file.storage_path, core_file.original_name)
                summary.results.append(extraction)

                if extraction.success:
                    summary.success += 1
                else:
                    summary.failed += 1

        return summary

    async def _process_one(self, session: AsyncSession, file_uuid: str, storage_path: str, original_name: str) -> ExtractionResult:
        extraction = ExtractionResult(file_uuid=file_uuid, original_name=original_name, success=False)
        t_start = time.monotonic()

        # 1. Download PDF from MinIO
        try:
            pdf_bytes = self._minio.get_object(storage_path)
        except Exception as exc:
            elapsed = time.monotonic() - t_start
            LOGGER.exception("Failed to download %s from MinIO", storage_path)
            extraction.error = f"MinIO download failed: {exc}"
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

        # 6. Insert into MED_CASE
        med_case = MedCase(**mapped)
        session.add(med_case)

        # 7. Update CORE_FILE.status_case = true
        from data_process.pdf_upload.models import CoreFile
        await session.execute(
            update(CoreFile).where(CoreFile.file_uuid == file_uuid).values(status_case=True)
        )

        await session.commit()
        extraction.success = True
        elapsed = time.monotonic() - t_start
        LOGGER.info(
            "RESULT | OK | %s | elapsed=%.1fs | missing=%d%s",
            original_name, elapsed, len(missing_fields),
            f" [{','.join(missing_fields[:5])}]" if missing_fields else "",
        )
        return extraction

    async def dispose(self) -> None:
        await self._engine.dispose()
