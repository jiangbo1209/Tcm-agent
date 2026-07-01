from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.database import engine
from app.services.core_file_scanner import CoreFileScanner
from app.services.crawlers.base import BaseCrawler
from app.services.crawlers.nstl_crawler import NstlCrawler
from app.services.crawlers.wanfang_crawler import WanfangCrawler
from app.services.crawlers.yidu_crawler import YiduCrawler
from app.services.extraction_service import ExtractionService


CRAWLER_FACTORIES: dict[str, type[BaseCrawler]] = {
    "yidu": YiduCrawler,
    "nstl": NstlCrawler,
    "cnki": None,  # lazy import
    "wanfang": WanfangCrawler,
    "weipu": None,  # lazy import
}


async def main() -> None:
    setup_logging(settings)
    logger.info("Starting paper_info_crawler")
    logger.info("Settings loaded: output_dir={}", settings.OUTPUT_DIR)

    scanner = CoreFileScanner(settings)
    files = await scanner.scan()

    sites = [s.strip() for s in settings.CRAWLER_ORDER.split(",") if s.strip()]
    crawlers: dict[str, BaseCrawler] = {}
    for site in sites:
        factory = CRAWLER_FACTORIES.get(site)
        if factory is None and site == "cnki":
            from app.services.crawlers.cnki_crawler import CnkiCrawler

            crawlers[site] = CnkiCrawler(settings)
        elif factory is None and site == "weipu":
            from app.services.crawlers.weipu_crawler import WeipuCrawler

            crawlers[site] = WeipuCrawler()
        elif factory is not None:
            crawlers[site] = factory()
        else:
            logger.warning("Unknown site in CRAWLER_ORDER: {}", site)

    try:
        extraction_service = ExtractionService(
            yidu_crawler=crawlers.get("yidu"),
            nstl_crawler=crawlers.get("nstl"),
            cnki_crawler=crawlers.get("cnki"),
            wanfang_crawler=crawlers.get("wanfang"),
            weipu_crawler=crawlers.get("weipu"),
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
        for crawler in crawlers.values():
            try:
                await crawler.close()
            except Exception:
                pass
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
