from __future__ import annotations

import pytest

from models.schemas import SearchResult
from services.crawlers.nstl_crawler import NstlCrawler


@pytest.mark.asyncio
async def test_nstl_metadata_maps_journal_and_publish_year() -> None:
    crawler = NstlCrawler()
    try:
        metadata = crawler._metadata_from_record(
            {
                "tit": ["title"],
                "hasAut": [[{"f": "nam", "v": ["author"]}]],
                "abs": ["abstract"],
                "key": ["keyword"],
                "type": "JournalPaper",
                "hasSo": [[{"f": "id", "v": "sxzy"}, {"f": "tit", "v": ["Journal A"]}]],
                "yea": ["2025"],
            },
            SearchResult(
                title="title",
                detail_url="https://example.com/detail",
                source_site="nstl",
                raw_data={},
            ),
        )
    finally:
        await crawler.close()

    assert metadata.journal == "Journal A"
    assert metadata.pub_year == "2025"
