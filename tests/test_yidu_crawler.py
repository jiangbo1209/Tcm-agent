from __future__ import annotations

import pytest

from models.schemas import SearchResult
from services.crawlers.yidu_crawler import YiduCrawler


@pytest.mark.asyncio
async def test_yidu_metadata_maps_journal_and_publish_year() -> None:
    crawler = YiduCrawler()
    try:
        metadata = crawler._metadata_from_record(
            {
                "string_title": "title",
                "string_creator": "author",
                "string_abstract": "abstract",
                "string_Key": "keyword",
                "schemacode": "JNArt",
                "string_journal_title": "Journal A",
                "string_publishyear": "2020",
            },
            SearchResult(
                title="title",
                detail_url="https://example.com/detail",
                source_site="yidu",
                raw_data={},
            ),
        )
    finally:
        await crawler.close()

    assert metadata.journal == "Journal A"
    assert metadata.pub_year == "2020"
