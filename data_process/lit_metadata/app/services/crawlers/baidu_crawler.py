"""Baidu Academic (百度学术) crawler."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from loguru import logger

from app.models.schemas import PaperMetadata, SearchResult
from app.services.crawlers.base import BaseCrawler
from app.utils.text import clean_text, split_authors, split_keywords, strip_html

BAIDU_BASE_URL = "https://xueshu.baidu.com"


class BaiduCrawler(BaseCrawler):
    """HTTP crawler for Baidu Academic (百度学术)."""

    def __init__(self) -> None:
        super().__init__("baidu", BAIDU_BASE_URL)

    async def search(self, title: str) -> list[SearchResult]:
        url = f"{self.base_url}/s?wd={quote(title)}&pn=0"
        logger.debug("Searching baidu: title={}", title)
        html = await self._get_html(url, headers={
            "Referer": f"{self.base_url}/",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        return self._parse_search_html(html)

    def _parse_search_html(self, html: str) -> list[SearchResult]:
        results: list[SearchResult] = []

        # Split by result blocks
        blocks = re.split(r'<div[^>]*class="[^"]*result[^"]*"[^>]*>', html)
        if len(blocks) <= 1:
            blocks = re.split(r'<div[^>]*class="[^"]*sc_default_result[^"]*"[^>]*>', html)

        for block in blocks[1:]:
            title_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not title_match:
                title_match = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.DOTALL)
                if title_match:
                    href_match = re.search(r'href="([^"]*)"', block)
                    title = strip_html(title_match.group(1))
                    detail_url = href_match.group(1) if href_match else None
                    if title and len(title) > 2:
                        results.append(SearchResult(
                            title=title, detail_url=detail_url, source_site="baidu",
                        ))
                continue

            detail_url = title_match.group(1)
            title = strip_html(title_match.group(2))

            if not title or len(title) < 3:
                continue

            # Extract authors and other metadata from the block
            author_match = re.search(r'(?:作者|author)[：:\s]*<[^>]*>(.*?)</[^>]*>', block, re.DOTALL | re.IGNORECASE)
            authors = clean_text(strip_html(author_match.group(1))) if author_match else None

            abstract_match = re.search(r'(?:abstract|摘要)[^>]*>(.*?)</[^>]*>', block, re.DOTALL | re.IGNORECASE)
            abstract = clean_text(strip_html(abstract_match.group(1))) if abstract_match else None

            source_match = re.search(r'(?:source|来源|刊名)[^>]*>(.*?)</[^>]*>', block, re.DOTALL | re.IGNORECASE)
            source = clean_text(strip_html(source_match.group(1))) if source_match else None

            year_match = re.search(r'(?:year|年份|出版年)[^>]*>(.*?)</[^>]*>', block, re.DOTALL | re.IGNORECASE)
            pub_year = clean_text(strip_html(year_match.group(1))) if year_match else None

            if detail_url and not detail_url.startswith("http"):
                detail_url = f"{self.base_url}{detail_url}"

            raw_data = {}
            if authors:
                raw_data["authors"] = authors
            if abstract:
                raw_data["abstract"] = abstract
            if source:
                raw_data["source"] = source
            if pub_year:
                raw_data["pub_year"] = pub_year

            results.append(SearchResult(
                title=title,
                detail_url=detail_url,
                source_site="baidu",
                raw_data=raw_data if raw_data else None,
            ))

        logger.debug("Baidu search: {} results", len(results))
        return results

    async def fetch_detail(self, result: SearchResult) -> PaperMetadata:
        raw = result.raw_data or {}

        if raw.get("title") and raw.get("authors") and (raw.get("abstract") or raw.get("source")):
            return self._metadata_from_record(raw, result)

        if not result.detail_url:
            return self._metadata_from_record(raw, result)

        logger.debug("Baidu detail: {} -> {}", result.title, result.detail_url)
        try:
            html = await self._get_html(result.detail_url, headers={
                "Referer": f"{self.base_url}/",
            })
            detail = self._parse_detail_html(html)
            merged = {**raw, **detail}
            return self._metadata_from_record(merged, result)
        except Exception as exc:
            logger.warning("Baidu detail failed: {}", exc)
            return self._metadata_from_record(raw, result)

    def _parse_detail_html(self, html: str) -> dict[str, Any]:
        detail: dict[str, Any] = {}

        patterns = {
            "title": r'<h1[^>]*>(.*?)</h1>',
            "authors": r'(?:作者|Author)[：:]\s*<[^>]*>(.*?)</[^>]*>',
            "abstract": r'(?:摘要|Abstract)[：:]\s*<[^>]*>(.*?)</[^>]*>',
            "keywords": r'(?:关键词|Keywords?)[：:]\s*<[^>]*>(.*?)</[^>]*>',
            "journal": r'(?:期刊|刊名|Journal|来源)[：:]\s*<[^>]*>(.*?)</[^>]*>',
            "pub_year": r'(?:年份|出版年|Year)[：:]\s*<[^>]*>(.*?)</[^>]*>',
        }
        for field, pattern in patterns.items():
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                detail[field] = clean_text(strip_html(match.group(1)))

        return detail

    def _metadata_from_record(self, record: dict[str, Any], result: SearchResult) -> PaperMetadata:
        title = strip_html(str(record.get("title") or result.title or "")) or result.title

        authors_raw = record.get("authors") or record.get("author") or record.get("creator") or ""
        abstract = record.get("abstract") or record.get("Abstract") or record.get("abs")
        keywords_raw = record.get("keywords") or record.get("Keywords") or record.get("key") or ""
        journal = record.get("journal") or record.get("Journal") or record.get("source") or record.get("publisher")
        pub_year = record.get("year") or record.get("Year") or record.get("pub_year")

        metadata = PaperMetadata(
            title=title,
            authors=split_authors(str(authors_raw)) if isinstance(authors_raw, str) else [],
            abstract=clean_text(str(abstract)) if abstract else None,
            keywords=split_keywords(str(keywords_raw)) if isinstance(keywords_raw, str) else [],
            paper_type=self.infer_paper_type(json.dumps(record, ensure_ascii=False)),
            source_site="baidu",
            source_url=result.detail_url,
            raw_data=record,
            journal=clean_text(str(journal)) if journal else None,
            pub_year=clean_text(str(pub_year)) if pub_year else None,
        )
        logger.debug("Baidu metadata: title={} authors={}", metadata.title, len(metadata.authors))
        return metadata
