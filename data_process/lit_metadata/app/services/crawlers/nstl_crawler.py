from __future__ import annotations

import json
import uuid
from typing import Any
from urllib.parse import quote_plus

from loguru import logger

from app.core.config import Settings, settings
from app.core.exceptions import CrawlerError, DetailPageParseError
from app.models.schemas import PaperMetadata, SearchResult
from app.services.crawlers.base import BaseCrawler
from app.utils.text import clean_text, split_authors, split_keywords, strip_html


class NstlCrawler(BaseCrawler):
    """HTTP API crawler for NSTL National Science and Technology Library."""

    PAPER_LIST_PATH = "/api/service/nstl/web/execute?target=nstl4.search4&function=paper/pc/list/pl"
    PAPER_DETAIL_PATH = "/api/service/nstl/web/execute?target=nstl4.search4&function=paper/pc/details"

    def __init__(self, app_settings: Settings = settings) -> None:
        super().__init__("nstl", app_settings.NSTL_BASE_URL, app_settings)

    def build_search_url(self, title: str) -> str:
        return f"{self.base_url}{self.PAPER_LIST_PATH}"

    async def search(self, title: str) -> list[SearchResult]:
        url = self.build_search_url(title)
        logger.info("Searching nstl API: title={}, url={}", title, url)
        data = await self._request_json(
            "POST",
            url,
            data=self._build_search_form(title),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": f"{self.base_url}/search.html",
            },
        )
        results = self.parse_search_results(data)
        logger.info("NSTL API search result count: title={}, count={}", title, len(results))
        return results

    def _build_search_form(self, title: str) -> dict[str, str]:
        query = {
            "c": 10,
            "st": "0",
            "f": [],
            "p": "",
            "q": [{"k": "tit_s_q", "v": title, "a": 1, "o": "AND"}],
            "op": "AND",
            "s": ["nstl", "haveAbsAuK:desc", "yea:desc", "score"],
            "t": ["JournalPaper", "ProceedingsPaper", "DegreePaper"],
        }
        return {
            "query": json.dumps(query, ensure_ascii=False),
            "webDisplayId": "11",
            "sl": "1",
            "searchWordId": uuid.uuid4().hex,
            "searchId": uuid.uuid4().hex,
            "facetRelation": "[]",
            "pageSize": "10",
            "pageNumber": "1",
        }

    def parse_search_results(self, data: dict[str, Any]) -> list[SearchResult]:
        if str(data.get("code")) != "0":
            raise CrawlerError(f"NSTL search API failed: code={data.get('code')} msg={data.get('msg')}")

        results: list[SearchResult] = []
        for item in data.get("data", []) or []:
            record = self._flatten_record(item)
            title = strip_html(self.first_value(record.get("tit")))
            paper_id = self.first_value(record.get("id"))
            if not title:
                continue
            detail_url = f"{self.base_url}/paper_detail.html?id={paper_id}" if paper_id else None
            results.append(
                SearchResult(
                    title=title,
                    detail_url=detail_url,
                    source_site="nstl",
                    raw_data=record,
                )
            )
        return results

    async def fetch_detail(self, result: SearchResult) -> PaperMetadata:
        raw = result.raw_data or {}
        paper_id = self.first_value(raw.get("id"))
        if not paper_id:
            raise DetailPageParseError(f"NSTL result has no paper id: {result.title}")

        url = (
            f"{self.base_url}{self.PAPER_DETAIL_PATH}"
            f"&ids={quote_plus(paper_id)}&type=Detail&webDisplayId=1001"
        )
        logger.info("Fetching nstl API detail: title={}, id={}", result.title, paper_id)
        data = await self._request_json(
            "GET",
            url,
            headers={"Referer": result.detail_url or f"{self.base_url}/paper_detail.html?id={paper_id}"},
        )
        if str(data.get("code")) != "0":
            raise DetailPageParseError(f"NSTL detail API failed: code={data.get('code')} msg={data.get('msg')}")

        detail_data = data.get("data", {})
        item = detail_data.get(paper_id) if isinstance(detail_data, dict) else None
        if not item:
            raise DetailPageParseError(f"NSTL detail API returned no record: {result.title}")

        detail = self._flatten_record(item)
        merged = {**raw, **detail}
        return self._metadata_from_record(merged, result)

    def _metadata_from_record(self, record: dict[str, Any], result: SearchResult) -> PaperMetadata:
        title = strip_html(self.first_value(record.get("tit"))) or result.title
        authors = self._extract_authors(record.get("hasAut"))
        abstract = self._join_values(record.get("abs"))
        keywords = self._extract_keywords(record.get("key"))
        explicit_type = self.first_value(record.get("type"))
        page_text = json.dumps(record, ensure_ascii=False)

        metadata = PaperMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            keywords=keywords,
            paper_type=self.infer_paper_type(page_text, explicit_type),
            source_site="nstl",
            source_url=result.detail_url,
            raw_data=record,
        )
        logger.info(
            "Parsed nstl metadata: title={}, authors={}, keywords={}, paper_type={}",
            metadata.title,
            len(metadata.authors),
            len(metadata.keywords),
            metadata.paper_type,
        )
        return metadata

    def _flatten_record(self, item: Any) -> dict[str, Any]:
        record: dict[str, Any] = {}
        if isinstance(item, dict):
            return item
        if not isinstance(item, list):
            return record
        for field in item:
            if isinstance(field, dict) and "f" in field:
                record[str(field["f"])] = field.get("v")
        return record

    def _join_values(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, list):
            parts = [strip_html(self.first_value(item)) for item in value]
            return clean_text("".join(part for part in parts if part))
        return strip_html(str(value))

    def _extract_keywords(self, value: Any) -> list[str]:
        if isinstance(value, list):
            keywords = [strip_html(self.first_value(item)) for item in value]
            return [keyword for keyword in keywords if keyword]
        return split_keywords(strip_html(str(value)) if value else None)

    def _extract_authors(self, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return split_authors(value)
        authors: list[str] = []
        if isinstance(value, list):
            for author_item in value:
                name = self._extract_author_name(author_item)
                if name:
                    authors.append(name)
        return authors

    def _extract_author_name(self, value: Any) -> str | None:
        if isinstance(value, list):
            fields = self._flatten_record(value)
            return clean_text(self.first_value(fields.get("nam")) or self.first_value(fields.get("nam_s")))
        if isinstance(value, dict):
            return clean_text(self.first_value(value.get("nam")) or self.first_value(value.get("nam_s")))
        return clean_text(str(value))
