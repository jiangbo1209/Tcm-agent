from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import Settings, settings
from app.core.exceptions import (
    CaptchaDetectedError,
    CrawlerError,
    DetailPageParseError,
)
from app.models.schemas import PaperMetadata, SearchResult
from app.services.crawlers.base import BaseCrawler
from app.services.crawlers.cnki.api import (
    CaptchaRequired,
    CnkiApiError,
    CnkiClient,
    CookieStore,
    SearchResult as CnkiSearchResult,
    _parse_detail_html,
    simplify_query,
)
from app.services.crawlers.cnki.cookie_bootstrap import bootstrap_cookies
from app.services.crawlers.cnki.endnote_parser import parse_endnote
from app.utils.text import split_authors, split_keywords


def _reconstruct_cnki_result(raw_data: dict[str, Any] | None) -> CnkiSearchResult:
    if not raw_data:
        raise CrawlerError("cnki: missing raw_data on SearchResult")
    return CnkiSearchResult(
        export_id=raw_data.get("export_id", ""),
        dbname=raw_data.get("dbname", ""),
        filename=raw_data.get("filename", ""),
        url=raw_data.get("url", ""),
        title=raw_data.get("title", ""),
        authors=raw_data.get("authors", ""),
        source=raw_data.get("source", ""),
        date=raw_data.get("date", ""),
        citation=raw_data.get("citation", ""),
    )


class CnkiCrawler(BaseCrawler):
    """CNKI crawler using POST API with manual cookie bootstrap on captcha."""

    def __init__(self, app_settings: Settings = settings) -> None:
        super().__init__("cnki", app_settings.CNKI_BASE_URL, app_settings)
        debug_dir = Path(app_settings.OUTPUT_DIR) / "cnki_debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        self._cookie_store = CookieStore(
            debug_dir / "cnki_cookies.json",
            ttl_sec=app_settings.CNKI_COOKIE_TTL_SEC,
        )
        self._client: CnkiClient | None = None
        self._cookie_lock = asyncio.Lock()
        self._client_lock = asyncio.Lock()

    async def _ensure_client(self) -> None:
        async with self._client_lock:
            if self._client is not None:
                return
            client = CnkiClient(
                self._cookie_store,
                timeout_sec=self.settings.CRAWLER_TIMEOUT,
            )
            await client.__aenter__()
            self._client = client
        if not self._client.cookies_usable():
            await self._bootstrap()

    async def _bootstrap(self, *, captcha_url: str | None = None) -> None:
        async with self._cookie_lock:
            assert self._client is not None
            if captcha_url is None and self._client.cookies_usable():
                return
            hint = (
                "请完成滑块/点选验证，页面正常加载后点击右上角按钮。"
                if captcha_url
                else "请等待知网首页正常加载，然后点击右上角按钮继续。"
            )
            cookies = await bootstrap_cookies(
                self._cookie_store,
                url=captcha_url,
                hint=hint,
                headless=self.settings.CNKI_HEADLESS_BOOTSTRAP,
                channel=self.settings.CNKI_BROWSER_CHANNEL or None,
            )
            self._client.update_cookies(cookies)

    async def _search_with_fallback(self, title: str) -> list[CnkiSearchResult]:
        assert self._client is not None
        results = await self._client.search(title)
        if results:
            return results

        simple = simplify_query(title)
        if simple and simple != title:
            logger.info("cnki fallback (strip parens): {!r}", simple)
            await asyncio.sleep(0.6)
            results = await self._client.search(simple)
            if results:
                return results

        logger.info("cnki fallback (SU subject search): {!r}", title)
        await asyncio.sleep(0.6)
        return await self._client.search(title, field="SU")

    async def search(self, title: str) -> list[SearchResult]:
        await self._ensure_client()
        await self._sleep_before_request()
        logger.info("Searching cnki: title={}", title)
        try:
            raw_results = await self._search_with_fallback(title)
        except CaptchaRequired as exc:
            logger.warning("cnki captcha required, bootstrapping: {}", exc.captcha_url)
            await self._bootstrap(captcha_url=exc.captcha_url)
            try:
                raw_results = await self._search_with_fallback(title)
            except CaptchaRequired as exc2:
                raise CaptchaDetectedError(
                    f"cnki still requires captcha after bootstrap: {exc2.captcha_url}"
                ) from exc2

        logger.info("Cnki search result count: title={}, count={}", title, len(raw_results))
        return [
            SearchResult(
                title=r.title,
                detail_url=r.url,
                source_site="cnki",
                raw_data={
                    "export_id": r.export_id,
                    "dbname": r.dbname,
                    "filename": r.filename,
                    "url": r.url,
                    "title": r.title,
                    "authors": r.authors,
                    "source": r.source,
                    "date": r.date,
                    "citation": r.citation,
                },
            )
            for r in raw_results
        ]

    async def fetch_detail(self, result: SearchResult) -> PaperMetadata:
        await self._ensure_client()
        assert self._client is not None
        cnki_result = _reconstruct_cnki_result(result.raw_data)

        parsed: dict[str, Any] = {}
        try:
            endnote_text = await self._client.get_export(cnki_result)
            parsed = parse_endnote(endnote_text, dbname=cnki_result.dbname)
        except CaptchaRequired as exc:
            logger.warning("cnki captcha on export, bootstrapping: {}", exc.captcha_url)
            await self._bootstrap(captcha_url=exc.captcha_url)
            try:
                endnote_text = await self._client.get_export(cnki_result)
                parsed = parse_endnote(endnote_text, dbname=cnki_result.dbname)
            except (CnkiApiError, CaptchaRequired) as exc2:
                logger.info("cnki export still failed after bootstrap: {}", exc2)
        except CnkiApiError as exc:
            logger.info("cnki export failed, falling back to detail page: {}", exc)

        needs_detail = not (
            parsed.get("title")
            and parsed.get("authors")
            and parsed.get("abstract")
            and parsed.get("keywords")
        )
        if needs_detail:
            try:
                html = await self._client.fetch_detail(cnki_result.url)
                detail = _parse_detail_html(html)
                for key, value in detail.items():
                    if not parsed.get(key) and value:
                        parsed[key] = value
            except CaptchaRequired as exc:
                raise CaptchaDetectedError(
                    f"cnki detail page captcha: {exc.captcha_url}"
                ) from exc
            except CnkiApiError as exc:
                logger.warning("cnki detail page failed: {}", exc)

        title = parsed.get("title") or cnki_result.title
        if not title:
            raise DetailPageParseError(
                f"cnki returned no usable title for {cnki_result.url}"
            )

        return PaperMetadata(
            title=title,
            authors=split_authors(parsed.get("authors")),
            abstract=parsed.get("abstract"),
            keywords=split_keywords(parsed.get("keywords")),
            paper_type=parsed.get("paper_type") or cnki_result.guess_paper_type(),
            source_site="cnki",
            source_url=cnki_result.url,
            journal=parsed.get("journal") or cnki_result.source or None,
            pub_year=parsed.get("pub_year"),
            raw_data=parsed,
        )

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            finally:
                self._client = None
        await super().close()
