from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.exceptions import CaptchaDetectedError, CrawlerError, DetailPageParseError
from app.models.schemas import PaperMetadata, SearchResult
from app.services.crawlers.base import BaseCrawler
from app.services.crawlers.shared.cookie_bootstrap import (
    CookieStore,
    bootstrap_cookies,
    resolve_cookie_path,
)
from app.utils.text import clean_text, split_authors, split_keywords, strip_html

WANFANG_BASE_URL = "https://c.wanfangdata.com.cn"


class WanfangCrawler(BaseCrawler):
    """HTTP API crawler for Wanfang Data (万方数据) with Playwright cookie bootstrap."""

    SEARCH_PATH = "/search/searchList"

    def __init__(self) -> None:
        super().__init__("wanfang", WANFANG_BASE_URL)
        cookie_path = resolve_cookie_path(settings.OUTPUT_DIR, "wanfang")
        self._cookie_store = CookieStore(cookie_path)
        self._cookie_lock = asyncio.Lock()
        self._load_cookies()

    def _load_cookies(self) -> None:
        cookies = self._cookie_store.load()
        if cookies:
            self.client.cookies.update(cookies)
            logger.info("Loaded {} wanfang cookies from cache", len(cookies))

    async def handle_captcha(self) -> bool:
        async with self._cookie_lock:
            try:
                cookies = await bootstrap_cookies(
                    self._cookie_store,
                    target_url=f"{self.base_url}/",
                    site_label="万方",
                    domains=["wanfangdata"],
                    hint="请在浏览器中完成验证码，页面正常加载后点击右上角按钮。",
                )
                self.client.cookies.update(cookies)
                return True
            except Exception as exc:
                logger.warning("wanfang captcha bootstrap failed: {}", exc)
                return False

    def build_search_url(self) -> str:
        return f"{self.base_url}{self.SEARCH_PATH}"

    async def search(self, title: str) -> list[SearchResult]:
        url = self.build_search_url()
        logger.debug("Searching wanfang API: title={}, url={}", title, url)

        try:
            text = await self._request(
                "POST",
                url,
                data=self._build_search_form(title),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Referer": f"{self.base_url}/",
                },
            )
        except CaptchaDetectedError:
            await self.handle_captcha()
            text = await self._request(
                "POST",
                url,
                data=self._build_search_form(title),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Referer": f"{self.base_url}/",
                },
            )

        results = self.parse_search_results(text)
        logger.debug("Wanfang API search result count: title={}, count={}", title, len(results))
        return results

    def _build_search_form(self, title: str) -> dict[str, str]:
        return {
            "searchType": "all",
            "searchWord": title,
            "page": "1",
            "pageSize": "10",
        }

    def parse_search_results(self, text: str) -> list[SearchResult]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CrawlerError("Wanfang search returned non-JSON response") from exc

        if not isinstance(data, dict):
            raise CrawlerError("Wanfang search returned unexpected response format")

        records = data.get("data", {}).get("records", []) or []
        if not records and data.get("data", {}).get("recordList"):
            records = data["data"]["recordList"]

        results: list[SearchResult] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            title_value = item.get("title") or item.get("Title") or item.get("tit")
            title_clean = strip_html(str(title_value)) if title_value else None
            if not title_clean:
                continue
            detail_url = item.get("url") or item.get("detail_url")
            if detail_url and not detail_url.startswith("http"):
                detail_url = f"{self.base_url}{detail_url}"
            results.append(
                SearchResult(
                    title=title_clean,
                    detail_url=detail_url,
                    source_site="wanfang",
                    raw_data=item,
                )
            )
        return results

    async def fetch_detail(self, result: SearchResult) -> PaperMetadata:
        raw = result.raw_data or {}
        if self._has_detail_metadata(raw):
            return self._metadata_from_record(raw, result)

        detail_url = result.detail_url
        if not detail_url:
            logger.warning("Wanfang result has no detail_url, using search-list metadata: {}", result.title)
            return self._metadata_from_record(raw, result)

        logger.debug("Fetching wanfang detail page: title={}, url={}", result.title, detail_url)
        try:
            html = await self._get_html(detail_url)
            detail = self._parse_detail_page(html)
            merged = {**raw, **detail}
            return self._metadata_from_record(merged, result)
        except CaptchaDetectedError:
            await self.handle_captcha()
            html = await self._get_html(detail_url)
            detail = self._parse_detail_page(html)
            merged = {**raw, **detail}
            return self._metadata_from_record(merged, result)
        except Exception as exc:
            logger.warning("Wanfang detail page failed, using search-list metadata: {}", exc)
            return self._metadata_from_record(raw, result)

    @staticmethod
    def _has_detail_metadata(record: dict[str, Any]) -> bool:
        authors = record.get("authors") or record.get("Authors") or record.get("creator")
        abstract = record.get("abstract") or record.get("Abstract") or record.get("abs")
        keywords = record.get("keywords") or record.get("Keywords") or record.get("key")
        return bool(authors or abstract or keywords)

    def _parse_detail_page(self, html: str) -> dict[str, Any]:
        import re

        detail: dict[str, Any] = {}

        title_match = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if title_match:
            detail["title"] = strip_html(title_match.group(1))

        abstract_match = re.search(
            r'(?:abstract|Abstract|摘要).*?<div[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE
        )
        if not abstract_match:
            abstract_match = re.search(
                r'(?:abstract|Abstract|摘要).*?<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE
            )
        if abstract_match:
            detail["abstract"] = clean_text(strip_html(abstract_match.group(1)))

        author_match = re.search(
            r'(?:author|Author|作者).*?<[^>]*>(.*?)</[^>]*>', html, re.DOTALL | re.IGNORECASE
        )
        if author_match:
            detail["authors"] = clean_text(strip_html(author_match.group(1)))

        keyword_match = re.search(
            r'(?:keyword|Keyword|关键词).*?<[^>]*>(.*?)</[^>]*>', html, re.DOTALL | re.IGNORECASE
        )
        if keyword_match:
            detail["keywords"] = clean_text(strip_html(keyword_match.group(1)))

        journal_match = re.search(
            r'(?:journal|Journal|期刊|刊名).*?<[^>]*>(.*?)</[^>]*>', html, re.DOTALL | re.IGNORECASE
        )
        if journal_match:
            detail["journal"] = clean_text(strip_html(journal_match.group(1)))

        year_match = re.search(
            r'(?:year|Year|年份|出版年).*?<[^>]*>(.*?)</[^>]*>', html, re.DOTALL | re.IGNORECASE
        )
        if year_match:
            detail["pub_year"] = clean_text(strip_html(year_match.group(1)))

        return detail

    def _metadata_from_record(self, record: dict[str, Any], result: SearchResult) -> PaperMetadata:
        title = (
            strip_html(str(record.get("title") or record.get("Title") or ""))
            or result.title
        )
        authors_text = (
            record.get("authors")
            or record.get("Authors")
            or record.get("creator")
            or record.get("string_creator")
            or ""
        )
        abstract = record.get("abstract") or record.get("Abstract") or record.get("abs") or record.get("string_abstract")
        keywords_text = (
            record.get("keywords")
            or record.get("Keywords")
            or record.get("key")
            or record.get("string_keyword")
            or ""
        )
        explicit_type = self._type_from_record(record)
        journal = record.get("journal") or record.get("Journal") or record.get("string_journal") or record.get("source")
        pub_year = record.get("year") or record.get("Year") or record.get("pub_year") or record.get("string_publishyear")

        metadata = PaperMetadata(
            title=title,
            authors=split_authors(
                str(authors_text) if not isinstance(authors_text, (list, type(None))) else None
            ),
            abstract=clean_text(str(abstract)) if abstract else None,
            keywords=split_keywords(
                str(keywords_text) if not isinstance(keywords_text, (list, type(None))) else None
            ),
            paper_type=self.infer_paper_type(json.dumps(record, ensure_ascii=False), explicit_type),
            source_site="wanfang",
            source_url=result.detail_url,
            raw_data=record,
            journal=clean_text(str(journal)) if journal else None,
            pub_year=clean_text(str(pub_year)) if pub_year else None,
        )
        if isinstance(authors_text, list):
            metadata.authors = [
                clean_text(str(a)) for a in authors_text if clean_text(str(a))
            ]

        logger.debug(
            "Parsed wanfang metadata: title={}, authors={}, keywords={}, paper_type={}",
            metadata.title,
            len(metadata.authors),
            len(metadata.keywords),
            metadata.paper_type,
        )
        return metadata

    @staticmethod
    def _type_from_record(record: dict[str, Any]) -> str | None:
        for key in ("type", "Type", "paper_type", "resource_type", "article_type"):
            value = record.get(key)
            if value:
                return str(value)
        return None
