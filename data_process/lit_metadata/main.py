from __future__ import annotations

import asyncio

from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.database import engine
from app.services.core_file_scanner import CoreFileScanner
from app.services.crawlers.nstl_crawler import NstlCrawler
from app.services.crawlers.yidu_crawler import YiduCrawler
from app.services.extraction_service import ExtractionService


async def main() -> None:
    setup_logging(settings)
    logger.info("Starting paper_info_crawler")
    logger.info(
        "Settings loaded: output_dir={}",
        settings.OUTPUT_DIR,
    )

    scanner = CoreFileScanner(settings)
    files = await scanner.scan()

    yidu_crawler = YiduCrawler(settings)
    nstl_crawler = NstlCrawler(settings) if settings.ENABLE_NSTL else None
    cnki_crawler = None
    if settings.ENABLE_CNKI:
        from app.services.crawlers.cnki_crawler import CnkiCrawler

        cnki_crawler = CnkiCrawler(settings)

    try:
        extraction_service = ExtractionService(
            yidu_crawler=yidu_crawler,
            nstl_crawler=nstl_crawler,
            cnki_crawler=cnki_crawler,
            app_settings=settings,
        )
        summary = await extraction_service.process_all(files)

        logger.info("Final summary: {}", summary.model_dump())
        print("Paper info crawler finished.")
        print(f"Total files: {summary.total_files}")
        print(f"Success: {summary.success_count}")
        print(f"Partial: {summary.partial_count}")
        print(f"Failed: {summary.failed_count}")
        print(f"Skipped: {summary.skipped_count}")
    finally:
        await yidu_crawler.close()
        if nstl_crawler is not None:
            await nstl_crawler.close()
        if cnki_crawler is not None:
            await cnki_crawler.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
