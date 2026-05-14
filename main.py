from __future__ import annotations

import asyncio
import sys

from loguru import logger

from core.config import settings
from core.exceptions import ConfigError, DatabaseError
from core.logging import setup_logging
from database import engine, init_db
from models.schemas import ProcessingSummary
from services.core_file_scanner import CoreFileScanner
from services.crawlers.cnki_crawler import CnkiCrawler
from services.crawlers.nstl_crawler import NstlCrawler
from services.crawlers.yidu_crawler import YiduCrawler
from services.export_service import ExportService
from services.extraction_service import ExtractionService


def _merge_summary(total: ProcessingSummary, batch: ProcessingSummary) -> None:
    total.total_files += batch.total_files
    total.success_count += batch.success_count
    total.partial_count += batch.partial_count
    total.failed_count += batch.failed_count
    total.skipped_count += batch.skipped_count


def _next_batch_limit(processed_count: int) -> int | None:
    if settings.CORE_FILE_PENDING_LIMIT <= 0:
        return settings.CORE_FILE_BATCH_SIZE

    remaining = settings.CORE_FILE_PENDING_LIMIT - processed_count
    if remaining <= 0:
        return None
    return min(settings.CORE_FILE_BATCH_SIZE, remaining)


def _validate_runtime_settings() -> None:
    if settings.database_url_uses_placeholder_password:
        raise ConfigError(
            "DATABASE_URL in .env still contains the example password placeholder. "
            "Replace <url-encoded-password> with the real PostgreSQL password. "
            "If the password contains @, write it as %40. "
            f"Current target: {settings.redacted_database_url}"
        )


async def main() -> None:
    setup_logging(settings)
    logger.info("Starting paper_info_crawler")
    logger.info(
        "Settings loaded: output_dir={}",
        settings.OUTPUT_DIR,
    )

    _validate_runtime_settings()

    await init_db()
    logger.info("Database initialized")

    scanner = CoreFileScanner(settings)

    yidu_crawler = YiduCrawler(settings)
    nstl_crawler = NstlCrawler(settings) if settings.ENABLE_NSTL else None
    cnki_crawler = CnkiCrawler(settings) if settings.ENABLE_CNKI else None

    try:
        extraction_service = ExtractionService(
            yidu_crawler=yidu_crawler,
            nstl_crawler=nstl_crawler,
            cnki_crawler=cnki_crawler,
            app_settings=settings,
        )
        summary = ProcessingSummary()
        batch_index = 0
        processed_count = 0

        while True:
            batch_limit = _next_batch_limit(processed_count)
            if batch_limit is None:
                break

            files = await scanner.scan(limit=batch_limit)
            if not files:
                break

            batch_index += 1
            logger.info(
                "Processing batch: batch_index={}, batch_size={}, batch_limit={}",
                batch_index,
                len(files),
                batch_limit,
            )
            batch_summary = await extraction_service.process_all(files)
            _merge_summary(summary, batch_summary)
            processed_count += len(files)

            if batch_summary.skipped_count == len(files):
                logger.warning("Stopping batch loop because every file in the batch was skipped")
                break
            if len(files) < batch_limit:
                break

        if settings.EXPORT_FAILED_CSV:
            export_service = ExportService(settings)
            failed_export_path = await export_service.export_failed_to_csv()
            summary.failed_export_path = failed_export_path

        logger.info("Final summary: {}", summary.model_dump())
        print("Paper info crawler finished.")
        print(f"Total files: {summary.total_files}")
        print(f"Success: {summary.success_count}")
        print(f"Partial: {summary.partial_count}")
        print(f"Failed: {summary.failed_count}")
        print(f"Skipped: {summary.skipped_count}")
        print(f"Failed CSV: {summary.failed_export_path}")
    finally:
        await yidu_crawler.close()
        if nstl_crawler is not None:
            await nstl_crawler.close()
        if cnki_crawler is not None:
            await cnki_crawler.close()
        await engine.dispose()


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        asyncio.run(main())
    except (ConfigError, DatabaseError) as exc:
        logger.error("{}", exc)
        raise SystemExit(2) from exc
