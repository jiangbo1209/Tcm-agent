from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.database import engine, init_db
from app.services.core_file_scanner import CoreFileScanner
from app.services.crawlers.cnki_crawler import CnkiCrawler
from app.services.crawlers.nstl_crawler import NstlCrawler
from app.services.crawlers.yidu_crawler import YiduCrawler
from app.services.dataset_scanner import DatasetScanner
from app.services.export_service import ExportService
from app.services.extraction_service import ExtractionService


async def main() -> None:
    setup_logging(settings)
    logger.info("Starting paper_info_crawler")
    logger.info(
        "Settings loaded: input_source={}, dataset_dir={}, output_dir={}",
        settings.INPUT_SOURCE,
        settings.DATASET_DIR,
        settings.OUTPUT_DIR,
    )

    await init_db()
    logger.info("Database initialized")

    if settings.INPUT_SOURCE == "core_file":
        scanner = CoreFileScanner(settings)
        files = await scanner.scan()
    else:
        scanner = DatasetScanner(settings)
        files = scanner.scan()

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
        summary = await extraction_service.process_all(files)

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
    asyncio.run(main())
