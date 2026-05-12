"""Tests for Yidu (e-read) crawler.

Run with reduced delays for faster testing:
    REQUEST_DELAY_MIN=0 REQUEST_DELAY_MAX=0 python -m pytest tests/test_yidu_crawler.py -x -v -s

Or as a standalone script:
    python tests/test_yidu_crawler.py
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.core.config import Settings
from app.services.crawlers.yidu_crawler import YiduCrawler


def _test_settings() -> Settings:
    """Return Settings with minimal delays for testing."""
    return Settings(
        REQUEST_DELAY_MIN=0,
        REQUEST_DELAY_MAX=0,
        CRAWLER_TIMEOUT=30,
        CRAWLER_MAX_RETRIES=1,
        YIDU_BASE_URL="https://yidu.calis.edu.cn",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_yidu_search_and_detail() -> None:
    """Search a known title via Yidu, then fetch details of the first result."""
    settings = _test_settings()
    crawler = YiduCrawler(settings)

    title = "杜小利治疗卵巢储备功能下降致不孕症验案1则"
    print(f"\n{'='*80}")
    print(f"搜索标题: {title}")
    print(f"{'='*80}\n")

    try:
        # --- Search ---
        results = await crawler.search(title)
        print(f"搜索结果数: {len(results)}")
        print(f"{'-'*80}")

        for i, r in enumerate(results, 1):
            print(f"\n  [{i}] 标题: {r.title}")
            print(f"      URL:  {r.detail_url}")
            print(f"      来源: {r.source_site}")
            if r.raw_data:
                print(f"      原始数据: {json.dumps(r.raw_data, ensure_ascii=False, indent=2)[:500]}")

        if not results:
            print("\n⚠ 未搜索到结果")
            return

        # --- Fetch detail of first result ---
        print(f"\n{'-'*80}")
        print(f"抓取第一条结果的详细信息...")
        print(f"{'-'*80}")

        metadata = await crawler.fetch_detail(results[0])
        print(f"\n  标题:    {metadata.title}")
        print(f"  作者:    {', '.join(metadata.authors) if metadata.authors else '无'}")
        print(f"  摘要:    {metadata.abstract[:200] if metadata.abstract else '无'}...")
        print(f"  关键词:  {', '.join(metadata.keywords) if metadata.keywords else '无'}")
        print(f"  类型:    {metadata.paper_type}")
        print(f"  来源:    {metadata.source_site}")
        print(f"  URL:     {metadata.source_url}")
        print(f"  期刊:    {metadata.journal}")
        print(f"  年份:    {metadata.pub_year}")
        print(f"\n{'='*80}")
        print("测试完成 ✓")
        print(f"{'='*80}")

    except Exception as e:
        print(f"\n❌ 错误: {type(e).__name__}: {e}")
        raise
    finally:
        await crawler.close()


# ── Standalone entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(test_yidu_search_and_detail())
