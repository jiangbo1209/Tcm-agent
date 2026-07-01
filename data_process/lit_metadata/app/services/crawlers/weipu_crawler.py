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

WEIPU_BASE_URL = "https://qikan.cqvip.com"


class WeipuCrawler(BaseCrawler):
    """HTTP API crawler for Weipu (维普中文期刊) with Playwright cookie bootstrap."""

    SEARCH_PATH = "/Qikan/Search/SearchResult"

    def __init__(self) -> None:
        super().__init__("weipu", WEIPU_BASE_URL)
        cookie_path = resolve_cookie_path(settings.OUTPUT_DIR, "weipu")
        self._cookie_store = CookieStore(cookie_path)
        self._cookie_lock = asyncio.Lock()
        self._load_cookies()

    def _load_cookies(self) -> None:
        cookies = self._cookie_store.load()
        if cookies:
            self.client.cookies.update(cookies)
            logger.info("Loaded {} weipu cookies from cache", len(cookies))

    async def handle_captcha(self) -> bool:
        async with self._cookie_lock:
            try:
                cookies = await bootstrap_cookies(
                    self._cookie_store,
                    target_url=f"{self.base_url}/Qikan/Search/Index",
                    site_label="维普",
                    domains=["cqvip"],
                    hint="请在浏览器中完成验证码（滑块/点选），页面正常加载后点击右上角按钮。",
                )
                self.client.cookies.update(cookies)
                return True
            except Exception as exc:
                logger.warning("weipu captcha bootstrap failed: {}", exc)
                return False

    def build_search_url(self) -> str:
        return f"{self.base_url}{self.SEARCH_PATH}"

    async def search(self, title: str) -> list[SearchResult]:
        url = self.build_search_url()
        logger.debug("Searching weipu API: title={}, url={}", title, url)

        try:
            text = await self._request(
                "POST",
                url,
                data=self._build_search_form(title),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Referer": f"{self.base_url}/Qikan/Search/Index",
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
                    "Referer": f"{self.base_url}/Qikan/Search/Index",
                },
            )

        results = self.parse_search_results(text)
        logger.debug("Weipu API search result count: title={}, count={}", title, len(results))
        return results

    def _build_search_form(self, title: str) -> dict[str, str]:
        return {
            "searchParamModel": json.dumps(
                {
                    "ObjectType": 1,
                    "SearchKeyWord": title,
                    "SearchKeyType": "T",
                    "SearchDateType": 0,
                    "SearchDateValue": "",
                    "SortField": "relevant",
                    "SortType": "desc",
                },
                ensure_ascii=False,
            ),
            "page": "1",
            "pageSize": "10",
        }

    def parse_search_results(self, text: str) -> list[SearchResult]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return self._parse_search_html(text)

        if not isinstance(data, dict):
            raise CrawlerError("Weipu search returned unexpected response format")

        records = data.get("data", {}).get("list", []) or []
        if not records:
            records = data.get("data", {}).get("records", []) or []
        if not records:
            records = data.get("list", []) or data.get("records", []) or []

        results: list[SearchResult] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            title_value = item.get("title") or item.get("Title") or item.get("BT")
            title_clean = strip_html(str(title_value)) if title_value else None
            if not title_clean:
                continue
            article_id = item.get("articleId") or item.get("ArticleId") or item.get("id") or item.get("ID")
            detail_url = None
            if article_id:
                detail_url = f"{self.base_url}/Qikan/Article/Detail?id={article_id}"
            results.append(
                SearchResult(
                    title=title_clean,
                    detail_url=detail_url,
                    source_site="weipu",
                    raw_data=item,
                )
            )
        return results

    def _parse_search_html(self, html: str) -> list[SearchResult]:
        import re

        results: list[SearchResult] = []
        items = re.split(r'<div[^>]*class="[^"]*result[^"]*item', html)
        for block in items[1:]:
            title_match = re.search(r'<a[^>]*>(.*?)</a>', block, re.DOTALL)
            if not title_match:
                continue
            title_clean = strip_html(title_match.group(1))
            if not title_clean:
                continue
            url_match = re.search(r'href="([^"]*)"', block)
            detail_url = None
            if url_match:
                href = url_match.group(1)
                detail_url = href if href.startswith("http") else f"{self.base_url}{href}"
            results.append(
                SearchResult(
                    title=title_clean,
                    detail_url=detail_url,
                    source_site="weipu",
                )
            )
        return results

    async def fetch_detail(self, result: SearchResult) -> PaperMetadata:
        raw = result.raw_data or {}

        if self._has_detail_metadata(raw):
            return self._metadata_from_record(raw, result)

        detail_url = result.detail_url
        if not detail_url:
            logger.warning("Weipu result has no detail_url, using search-list metadata: {}", result.title)
            return self._metadata_from_record(raw, result)

        logger.debug("Fetching weipu detail page: title={}, url={}", result.title, detail_url)
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
            logger.warning("Weipu detail page failed, using search-list metadata: {}", exc)
            return self._metadata_from_record(raw, result)

    @staticmethod
    def _has_detail_metadata(record: dict[str, Any]) -> bool:
        authors = record.get("authors") or record.get("Authors") or record.get("author") or record.get("ZZ")
        abstract = record.get("abstract") or record.get("Abstract") or record.get("ZY") or record.get("abs")
        keywords = record.get("keywords") or record.get("Keywords") or record.get("GJC") or record.get("key")
        return bool(authors or abstract or keywords)

    def _parse_detail_page(self, html: str) -> dict[str, Any]:
        import re

        detail: dict[str, Any] = {}

        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if not title_match:
            title_match = re.search(r'<h2[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h2>', html, re.DOTALL)
        if title_match:
            detail["title"] = strip_html(title_match.group(1))

        abstract_match = re.search(
            r'(?:abstract|Abstract|摘要|文摘).*?<(?:div|p)[^>]*>(.*?)</(?:div|p)>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if abstract_match:
            detail["abstract"] = clean_text(strip_html(abstract_match.group(1)))

        author_match = re.search(
            r'(?:author|Author|作者).*?<(?:div|p|span)[^>]*>(.*?)</(?:div|p|span)>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if author_match:
            detail["authors"] = clean_text(strip_html(author_match.group(1)))

        keyword_match = re.search(
            r'(?:keyword|Keyword|关键词).*?<(?:div|p|span)[^>]*>(.*?)</(?:div|p|span)>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if keyword_match:
            detail["keywords"] = clean_text(strip_html(keyword_match.group(1)))

        journal_match = re.search(
            r'(?:journal|Journal|期刊|刊名).*?<(?:div|p|span)[^>]*>(.*?)</(?:div|p|span)>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if journal_match:
            detail["journal"] = clean_text(strip_html(journal_match.group(1)))

        year_match = re.search(
            r'(?:year|Year|年份|出版年).*?<(?:div|p|span)[^>]*>(.*?)</(?:div|p|span)>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if year_match:
            detail["pub_year"] = clean_text(strip_html(year_match.group(1)))

        return detail

    def _metadata_from_record(self, record: dict[str, Any], result: SearchResult) -> PaperMetadata:
        title = (
            strip_html(str(record.get("title") or record.get("Title") or record.get("BT") or ""))
            or result.title
        )
        authors_raw = (
            record.get("authors")
            or record.get("Authors")
            or record.get("author")
            or record.get("ZZ")
            or ""
        )
        abstract = (
            record.get("abstract")
            or record.get("Abstract")
            or record.get("ZY")
            or record.get("abs")
            or record.get("string_abstract")
        )
        keywords_raw = (
            record.get("keywords")
            or record.get("Keywords")
            or record.get("GJC")
            or record.get("key")
            or record.get("string_keyword")
            or ""
        )
        explicit_type = self._type_from_record(record)
        journal = (
            record.get("journal")
            or record.get("Journal")
            or record.get("source")
            or record.get("KM")
            or record.get("string_journal")
        )
        pub_year = (
            record.get("year")
            or record.get("Year")
            or record.get("pub_year")
            or record.get("NF")
            or record.get("string_publishyear")
        )

        metadata = PaperMetadata(
            title=title,
            authors=(
                split_authors(str(authors_raw))
                if not isinstance(authors_raw, (list, type(None)))
                else []
            ),
            abstract=clean_text(str(abstract)) if abstract else None,
            keywords=(
                split_keywords(str(keywords_raw))
                if not isinstance(keywords_raw, (list, type(None)))
                else []
            ),
            paper_type=self.infer_paper_type(json.dumps(record, ensure_ascii=False), explicit_type),
            source_site="weipu",
            source_url=result.detail_url,
            raw_data=record,
            journal=clean_text(str(journal)) if journal else None,
            pub_year=clean_text(str(pub_year)) if pub_year else None,
        )
        if isinstance(authors_raw, list):
            metadata.authors = [clean_text(str(a)) for a in authors_raw if clean_text(str(a))]
        if isinstance(keywords_raw, list):
            metadata.keywords = [clean_text(str(k)) for k in keywords_raw if clean_text(str(k))]

        logger.debug(
            "Parsed weipu metadata: title={}, authors={}, keywords={}, paper_type={}",
            metadata.title,
            len(metadata.authors),
            len(metadata.keywords),
            metadata.paper_type,
        )
        return metadata

    @staticmethod
    def _type_from_record(record: dict[str, Any]) -> str | None:
        for key in ("type", "Type", "paper_type", "resource_type", "LX", "article_type"):
            value = record.get(key)
            if value:
                return str(value)
        return None
