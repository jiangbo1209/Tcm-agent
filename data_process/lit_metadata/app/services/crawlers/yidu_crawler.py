from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.core.config import Settings, settings
from app.core.exceptions import DetailPageParseError
from app.models.schemas import PaperMetadata, SearchResult
from app.services.crawlers.base import BaseCrawler
from app.utils.text import clean_text, split_authors, split_keywords, strip_html


class YiduCrawler(BaseCrawler):
    """HTTP API crawler for e-read academic resource discovery."""

    def __init__(self, app_settings: Settings = settings) -> None:
        super().__init__("yidu", app_settings.YIDU_BASE_URL, app_settings)

    def build_search_url(self, title: str) -> str:
        return f"{self.base_url}/prod-api/yidu/resource/query"

    async def search(self, title: str) -> list[SearchResult]:
        url = self.build_search_url(title)
        payload = self._build_search_payload(title)
        logger.info("Searching yidu API: title={}, url={}", title, url)
        data = await self._request_json(
            "POST",
            url,
            json=payload,
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "Referer": f"{self.base_url}/searchList/index",
            },
        )
        results = self.parse_search_results(data)
        logger.info("Yidu API search result count: title={}, count={}", title, len(results))
        return results

    def _build_search_payload(self, title: str) -> dict[str, Any]:
        condition = {
            "title": {
                "type": "title",
                "label": title,
                "value": title,
                "title": "\u9898\u540d",
                "andor": "0",
                "relation": "0",
                "category": "0",
            }
        }
        return {
            "offset": 1,
            "limit": 10,
            "sort": None,
            "exp": [
                {
                    "field": "title",
                    "value": title,
                    "label": title,
                    "relation": "0",
                    "op": "0",
                    "resource": "0",
                    "typeNew": "0-2",
                }
            ],
            "facet": [],
            "searchJson": json.dumps(
                {
                    "condition": condition,
                    "secondCondition": [],
                    "searchType": "simple",
                },
                ensure_ascii=False,
            ),
            "refresh": "",
        }

    def parse_search_results(self, data: dict[str, Any]) -> list[SearchResult]:
        if str(data.get("code")) != "200":
            raise CrawlerError(f"Yidu search API failed: code={data.get('code')} msg={data.get('msg')}")

        content = data.get("data", {}).get("content", []) or []
        results: list[SearchResult] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            title = strip_html(item.get("string_title"))
            if not title:
                continue
            ukey = item.get("ukey")
            detail_url = f"{self.base_url}/searchDetail/{ukey}" if ukey else None
            results.append(
                SearchResult(
                    title=title,
                    detail_url=detail_url,
                    source_site="yidu",
                    raw_data=item,
                )
            )
        return results

    async def fetch_detail(self, result: SearchResult) -> PaperMetadata:
        raw = result.raw_data or {}
        ukey = raw.get("ukey")
        schema_code = raw.get("schemacode")
        if not ukey or not schema_code:
            logger.warning("Yidu result misses ukey/schemacode, using search-list metadata: {}", result.title)
            return self._metadata_from_record(raw, result)

        url = f"{self.base_url}/prod-api/yidu/resource/getInfo"
        logger.info("Fetching yidu API detail: title={}, ukey={}, type={}", result.title, ukey, schema_code)
        data = await self._request_json(
            "GET",
            url,
            params={"ukey": ukey, "type": schema_code},
            headers={"Referer": result.detail_url or f"{self.base_url}/searchDetail/{ukey}"},
        )

        if str(data.get("code")) != "200":
            raise DetailPageParseError(f"Yidu detail API failed: code={data.get('code')} msg={data.get('msg')}")

        records = data.get("data", {}).get("concat", []) or []
        if not records:
            raise DetailPageParseError(f"Yidu detail API returned no detail records: {result.title}")
        record = records[0]
        if not isinstance(record, dict):
            raise DetailPageParseError(f"Yidu detail API returned invalid detail record: {result.title}")
        merged = {**raw, **record}
        return self._metadata_from_record(merged, result)

    def _metadata_from_record(self, record: dict[str, Any], result: SearchResult) -> PaperMetadata:
        title = strip_html(record.get("string_title")) or result.title
        authors_text = clean_text(record.get("string_creator") or record.get("string_creatorsearch"))
        abstract = clean_text(record.get("string_abstract"))
        keywords_text = clean_text(record.get("string_Key") or record.get("string_keyword"))
        explicit_type = self._type_text(record)
        journal = clean_text(record.get("string_journal_title"))
        pub_year = clean_text(record.get("string_publishyear"))

        metadata = PaperMetadata(
            title=title,
            authors=split_authors(authors_text),
            abstract=abstract,
            keywords=split_keywords(keywords_text),
            paper_type=self.infer_paper_type(json.dumps(record, ensure_ascii=False), explicit_type),
            source_site="yidu",
            source_url=result.detail_url,
            journal=journal,
            pub_year=pub_year,
            raw_data=record,
        )
        logger.info(
            "Parsed yidu metadata: title={}, authors={}, keywords={}, paper_type={}",
            metadata.title,
            len(metadata.authors),
            len(metadata.keywords),
            metadata.paper_type,
        )
        return metadata

    @staticmethod
    def _type_text(record: dict[str, Any]) -> str:
        values: list[str] = []
        raw_types = record.get("multivalued_type") or []
        if isinstance(raw_types, list):
            values.extend(str(item) for item in raw_types)
        elif raw_types:
            values.append(str(raw_types))
        if record.get("schemacode"):
            values.append(str(record["schemacode"]))
        return " ".join(values)
