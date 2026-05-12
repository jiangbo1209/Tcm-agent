from __future__ import annotations

import abc
import asyncio
import json
import random
from typing import Any

import httpx
from loguru import logger

from app.core.config import Settings, settings
from app.core.exceptions import (
    AccessLimitedError,
    CaptchaDetectedError,
    CrawlerError,
    LoginRequiredError,
    NetworkCrawlerError,
    TimeoutCrawlerError,
)
from app.models.schemas import PaperMetadata, SearchResult
from app.utils.retry import is_retryable_status


class BaseCrawler(abc.ABC):
    """Common async crawler contract and shared HTTP helpers."""

    def __init__(self, source_site: str, base_url: str, app_settings: Settings = settings) -> None:
        self.source_site = source_site
        self.base_url = base_url.rstrip("/")
        self.settings = app_settings
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.CRAWLER_TIMEOUT),
            follow_redirects=True,
            headers={
                "User-Agent": self.settings.USER_AGENT,
                "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )

    @abc.abstractmethod
    async def search(self, title: str) -> list[SearchResult]:
        """Search by cleaned title and return raw candidate results."""

    @abc.abstractmethod
    async def fetch_detail(self, result: SearchResult) -> PaperMetadata:
        """Fetch and parse a matched detail page."""

    async def close(self) -> None:
        await self.client.aclose()

    async def _sleep_before_request(self) -> None:
        delay = random.uniform(self.settings.REQUEST_DELAY_MIN, self.settings.REQUEST_DELAY_MAX)
        await asyncio.sleep(delay)

    async def _get_html(self, url: str, params: dict[str, Any] | None = None) -> str:
        return await self._request("GET", url, params=params)

    async def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        text = await self._request(method, url, **kwargs)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CrawlerError(f"{self.source_site} returned non-JSON response: {url}") from exc

        code = str(data.get("code", ""))
        if code == "401":
            raise LoginRequiredError(f"{self.source_site} API login required")
        if code == "403":
            raise AccessLimitedError(f"{self.source_site} API access limited")
        if code == "429":
            raise AccessLimitedError(f"{self.source_site} API rate limited")
        if code == "504":
            raise CaptchaDetectedError(f"{self.source_site} API captcha verification required")
        return data

    async def _request(self, method: str, url: str, **kwargs: Any) -> str:
        max_attempts = self.settings.CRAWLER_MAX_RETRIES + 1
        last_error: CrawlerError | None = None

        for attempt in range(1, max_attempts + 1):
            await self._sleep_before_request()
            try:
                response = await self.client.request(method, url, **kwargs)
            except httpx.TimeoutException as exc:
                last_error = TimeoutCrawlerError(f"{self.source_site} request timed out: {url}")
                if attempt < max_attempts:
                    logger.warning(
                        "{} timeout, retrying {}/{}: {}",
                        self.source_site,
                        attempt,
                        self.settings.CRAWLER_MAX_RETRIES,
                        url,
                    )
                    continue
                raise last_error from exc
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.NetworkError) as exc:
                last_error = NetworkCrawlerError(f"{self.source_site} network error: {url} ({exc})")
                if attempt < max_attempts:
                    logger.warning(
                        "{} network error, retrying {}/{}: {}",
                        self.source_site,
                        attempt,
                        self.settings.CRAWLER_MAX_RETRIES,
                        url,
                    )
                    continue
                raise last_error from exc

            if response.status_code in {403, 429}:
                raise AccessLimitedError(f"{self.source_site} access limited: HTTP {response.status_code}")

            if is_retryable_status(response.status_code):
                last_error = NetworkCrawlerError(
                    f"{self.source_site} server error: HTTP {response.status_code} {url}"
                )
                if attempt < max_attempts:
                    logger.warning(
                        "{} server error HTTP {}, retrying {}/{}: {}",
                        self.source_site,
                        response.status_code,
                        attempt,
                        self.settings.CRAWLER_MAX_RETRIES,
                        url,
                    )
                    continue
                raise last_error

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise NetworkCrawlerError(
                    f"{self.source_site} HTTP error: {response.status_code} {url}"
                ) from exc

            text = response.text
            self.detect_access_issue(text)
            return text

        raise last_error or NetworkCrawlerError(f"{self.source_site} request failed: {url}")

    def detect_access_issue(self, text: str) -> None:
        """Detect access blocks without treating normal navigation login links as failures."""

        captcha_keywords = (
            "\u9a8c\u8bc1\u7801",
            "\u8bf7\u8f93\u5165\u9a8c\u8bc1\u7801",
            "\u5b89\u5168\u9a8c\u8bc1",
            "captcha",
        )
        login_keywords = (
            "\u8bf7\u767b\u5f55",
            "\u672a\u767b\u5f55",
            "\u767b\u5f55\u5df2\u8fc7\u671f",
            "login required",
            "unauthorized",
        )
        access_keywords = (
            "\u8bbf\u95ee\u53d7\u9650",
            "\u8bbf\u95ee\u8fc7\u4e8e\u9891\u7e41",
            "Forbidden",
            "Too Many Requests",
        )
        lowered = text.lower()

        if any(keyword.lower() in lowered for keyword in captcha_keywords):
            raise CaptchaDetectedError(f"{self.source_site} captcha or security verification detected")
        if any(keyword.lower() in lowered for keyword in access_keywords):
            raise AccessLimitedError(f"{self.source_site} access limited page detected")
        if any(keyword.lower() in lowered for keyword in login_keywords):
            raise LoginRequiredError(f"{self.source_site} login required page detected")

    @staticmethod
    def first_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, list):
            if not value:
                return None
            return BaseCrawler.first_value(value[0])
        if isinstance(value, dict):
            for key in ("v", "name", "title", "tit", "nam", "zh"):
                if key in value:
                    return BaseCrawler.first_value(value[key])
            return None
        return str(value)

    @staticmethod
    def infer_paper_type(page_text: str, explicit_type: str | None = None) -> str:
        source = f"{explicit_type or ''} {page_text}"
        if any(keyword in source for keyword in ("\u5b66\u4f4d", "\u535a\u58eb", "\u7855\u58eb", "DegreePaper")):
            return "thesis"
        if any(keyword in source for keyword in ("\u4f1a\u8bae", "ProceedingsPaper")):
            return "conference"
        if any(keyword in source for keyword in ("\u671f\u520a", "\u520a\u540d", "JournalPaper", "JNArt")):
            return "journal"
        return "unknown"
