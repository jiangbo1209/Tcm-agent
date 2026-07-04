"""Wanfang (万方) crawler — extracts metadata from search page or detail page."""
from __future__ import annotations

import asyncio
import json
import random
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

from loguru import logger
from playwright.async_api import Page, async_playwright

from app.core.config import settings
from app.models.schemas import PaperMetadata, SearchResult
from app.services.crawlers.base import BaseCrawler
from app.utils.text import clean_text, split_authors, split_keywords, strip_html

WANFANG_BASE_URL = "https://s.wanfangdata.com.cn"
COOKIE_TTL_SEC = 600


class _CookieStore:
    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath

    def load(self) -> dict[str, str] | None:
        if not self.filepath.exists():
            return None
        try:
            data = json.loads(self.filepath.read_text())
            if time.time() - data.get("ts", 0) > COOKIE_TTL_SEC:
                return None
            return data.get("cookies")
        except Exception:
            return None

    def save(self, cookies: dict[str, str]) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.write_text(json.dumps({"ts": time.time(), "cookies": cookies}))


_OVERLAY_JS = r"""
(hintText, siteLabel) => {
    const old = document.getElementById('__captcha_confirm_box__');
    if (old) old.remove();
    const box = document.createElement('div');
    box.id = '__captcha_confirm_box__';
    box.style.cssText = 'position:fixed;top:10px;right:10px;z-index:2147483647;padding:15px;background:white;border:3px solid red;border-radius:8px;box-shadow:0 4px 8px rgba(0,0,0,0.3);font-family:system-ui,Arial,sans-serif;color:black;max-width:280px';
    box.innerHTML = '<div style="font-weight:bold;font-size:14px;margin-bottom:6px">'+siteLabel+'</div><div style="font-size:12px;margin-bottom:10px;line-height:1.5">'+hintText+'</div><button id="__captcha_confirm_btn__" style="width:100%;padding:6px 8px;background:#4CAF50;color:white;border:none;border-radius:5px;font-weight:bold;cursor:pointer;font-size:13px">确认完成验证</button>';
    document.documentElement.appendChild(box);
    window.__captcha_confirmed__ = false;
    document.getElementById('__captcha_confirm_btn__').addEventListener('click', () => { window.__captcha_confirmed__ = true; box.style.borderColor='#2E7D32'; box.style.display='none'; });
}
"""


class WanfangCrawler(BaseCrawler):
    def __init__(self, page_pool_size: int | None = None) -> None:
        super().__init__("wanfang", WANFANG_BASE_URL)
        cookie_path = Path(settings.OUTPUT_DIR) / "cookies" / "wanfang_cookies.json"
        self._cookie_store = _CookieStore(cookie_path)
        self._cookie_lock = asyncio.Lock()
        self._bootstrap_lock = asyncio.Lock()
        self._last_bootstrap = 0.0
        self._load_cookies()

        self._page_pool_size = page_pool_size or max(1, settings.CRAWLER_CONCURRENCY)
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page_pool: asyncio.Queue[Page] = asyncio.Queue()
        self._browser_init_lock = asyncio.Lock()
        self._browser_initialized = False

    def _load_cookies(self) -> None:
        cookies = self._cookie_store.load()
        if cookies:
            self.client.cookies.update(cookies)

    async def handle_captcha(self) -> bool:
        try:
            await self._bootstrap_via_playwright()
            return True
        except Exception as exc:
            logger.warning("wanfang bootstrap failed: {}", exc)
            return False

    async def _bootstrap_via_playwright(self) -> None:
        async with self._bootstrap_lock:
            if time.time() - self._last_bootstrap < 10:
                return
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                try:
                    page = await browser.new_page()
                    await page.goto(f"{self.base_url}/paper?q=test&p=1", wait_until="networkidle", timeout=30000)
                    await page.evaluate(_OVERLAY_JS, "请在浏览器中完成万方验证码，搜索页面正常加载后点击按钮。", "万方")
                    await page.wait_for_function("window.__captcha_confirmed__ === true", timeout=0)
                    raw = await page.context.cookies()
                    cookies = {c["name"]: c["value"] for c in raw if "wanfangdata" in (c.get("domain") or "").lower()}
                    self._cookie_store.save(cookies)
                    self.client.cookies.update(cookies)
                    self._last_bootstrap = time.time()
                finally:
                    try:
                        await browser.close()
                    except Exception:
                        pass

    async def _ensure_browser(self) -> None:
        if self._browser_initialized:
            return
        async with self._browser_init_lock:
            if self._browser_initialized:
                return
            logger.info("Wanfang: starting persistent browser (pool size={})", self._page_pool_size)
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=False)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=settings.USER_AGENT,
            )
            cached = self._cookie_store.load()
            if cached:
                await self._context.add_cookies([
                    {"name": k, "value": v, "domain": ".wanfangdata.com.cn", "path": "/"}
                    for k, v in cached.items()
                ])
            for _ in range(self._page_pool_size):
                page = await self._context.new_page()
                self._page_pool.put_nowait(page)
            self._browser_initialized = True

    async def _acquire_page(self) -> Page:
        await self._ensure_browser()
        return await self._page_pool.get()

    async def _release_page(self, page: Page) -> None:
        try:
            # Reset page to blank to free resources and avoid state leaks
            await page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
        except Exception:
            # If the page is broken, recreate it
            try:
                await page.close()
            except Exception:
                pass
            try:
                new_page = await self._context.new_page()
                self._page_pool.put_nowait(new_page)
                return
            except Exception:
                pass
        self._page_pool.put_nowait(page)

    async def search(self, title: str) -> list[SearchResult]:
        url = f"{self.base_url}/paper?q={quote(title)}&p=1"
        # Wanfang search results are rendered by JS; go straight to Playwright.
        return await self._playwright_search(title, url)

    async def _playwright_search(self, title: str, url: str) -> list[SearchResult]:
        page = await self._acquire_page()
        try:
            # Small stagger to avoid hammering Wanfang with simultaneous navigations
            await asyncio.sleep(random.uniform(0.3, 0.8))
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            # Wait for actual search result cards to render
            try:
                await page.wait_for_selector(".normal-list, .thesis-list, .conference-list", timeout=8000)
            except Exception:
                pass

            page_title = await page.title()
            logger.debug("Wanfang page: title={}", page_title)

            # Try DOM extraction first
            results = await self._extract_from_dom(page, title)
            if results:
                logger.info("Wanfang: found {} results via DOM", len(results))
                return results

            # Fallback: try page HTML for gRPC data
            html = await page.content()
            results = self._extract_from_grpc(html)
            if results:
                logger.info("Wanfang: found {} results via gRPC in HTML", len(results))
                return results

            logger.info("Wanfang: no results for '{}' (page: {} chars)", title, len(html))
            return []
        except Exception as exc:
            logger.warning("Wanfang Playwright error: {}", exc)
            return []
        finally:
            await self._release_page(page)

    async def _extract_from_dom(self, page, title_for_log: str) -> list[SearchResult]:
        results: list[SearchResult] = []

        # Wanfang renders results as .normal-list cards (not <a> tags).
        item_selectors = [
            ".normal-list", ".thesis-list", ".conference-list",
        ]
        items: list[Any] = []
        for sel in item_selectors:
            try:
                items = await page.query_selector_all(sel)
                if items:
                    logger.debug("Wanfang selector '{}' found {} items", sel, len(items))
                    break
            except Exception:
                continue

        logger.info("Wanfang page: {} result cards for '{}'", len(items), title_for_log)

        for item in items[:20]:
            try:
                title_el = await item.query_selector(".title-area .title, .title")
                if not title_el:
                    continue
                title_text = strip_html(await title_el.inner_text())
                if not title_text or len(title_text) < 3:
                    continue

                id_el = await item.query_selector(".title-id-hidden")
                raw_id = (await id_el.inner_text()).strip() if id_el else ""
                detail_url: str | None = None
                if raw_id:
                    # raw_id looks like "periodical_mysj201810068" or "thesis_xxx"
                    parts = raw_id.split("_", 1)
                    if len(parts) == 2 and parts[1]:
                        dtype, doc_id = parts
                        detail_url = f"https://d.wanfangdata.com.cn/{dtype}/{doc_id}"

                # Authors (skip year/issue entries that share the same class)
                authors: list[str] = []
                author_els = await item.query_selector_all(".author-area .authors")
                for ae in author_els:
                    txt = strip_html(await ae.inner_text()).strip()
                    if txt and not re.search(r"\d{4}年\d+期", txt):
                        authors.append(txt)

                # Journal / source
                journal_el = await item.query_selector(".author-area .periodical-title")
                journal = strip_html(await journal_el.inner_text()) if journal_el else ""

                # Year/issue
                year_text = ""
                for ae in author_els:
                    txt = strip_html(await ae.inner_text()).strip()
                    m = re.search(r"(\d{4})年(\d+)期", txt)
                    if m:
                        year_text = m.group(1)
                        break

                # Paper type
                type_el = await item.query_selector(".author-area .essay-type")
                paper_type = strip_html(await type_el.inner_text()) if type_el else ""

                # Abstract
                abs_el = await item.query_selector(".abstract-area")
                abstract = ""
                if abs_el:
                    abstract = strip_html(await abs_el.inner_text())
                    if abstract.startswith("摘要："):
                        abstract = abstract[3:].strip()

                # Keywords
                kw_els = await item.query_selector_all(".keywords-area .keywords-list")
                keywords = [strip_html(await k.inner_text()).strip() for k in kw_els]
                keywords = [k for k in keywords if k]

                results.append(SearchResult(
                    title=title_text,
                    detail_url=detail_url,
                    source_site="wanfang",
                    raw_data={
                        "title": title_text,
                        "authors": ", ".join(authors),
                        "abstract": abstract,
                        "keywords": ", ".join(keywords),
                        "journal": journal,
                        "pub_year": year_text,
                        "paper_type": paper_type,
                    },
                ))
            except Exception:
                continue
        return results

    def _extract_from_grpc(self, text: str) -> list[SearchResult]:
        if "resourcesList" not in text:
            return []
        match = re.search(r'(\{.*"resourcesList".*\})', text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        resources = data.get("resourcesList")
        if not isinstance(resources, list):
            return []

        results: list[SearchResult] = []
        for item in resources:
            if not isinstance(item, dict):
                continue
            item_type = (item.get("type") or "").lower()
            inner = item.get(item_type, item)

            title = strip_html(str(inner.get("title") or inner.get("tit") or item.get("title") or ""))
            if not title:
                continue

            uid = item.get("uid") or inner.get("uid") or ""
            detail_url = inner.get("url") or item.get("url")
            if not detail_url and uid:
                detail_url = f"https://d.wanfangdata.com.cn/periodical/{uid}"

            raw_data = {
                "title": title,
                "authors": str(inner.get("authors") or inner.get("creator") or ""),
                "abstract": str(inner.get("abstract") or ""),
                "keywords": str(inner.get("keywords") or inner.get("key") or ""),
                "journal": str(inner.get("journal") or inner.get("source") or ""),
                "pub_year": str(inner.get("year") or inner.get("pub_year") or ""),
                "paper_type": str(inner.get("type") or ""),
            }
            results.append(SearchResult(
                title=title, detail_url=detail_url, source_site="wanfang", raw_data=raw_data,
            ))
        return results

    async def fetch_detail(self, result: SearchResult) -> PaperMetadata:
        raw = result.raw_data or {}

        # If any key metadata is missing from search results, visit detail page
        if (
            not raw.get("authors")
            or not raw.get("abstract")
            or not raw.get("keywords")
            or not raw.get("journal")
            or not raw.get("pub_year")
        ) and result.detail_url:
            page = await self._acquire_page()
            try:
                await page.goto(result.detail_url, wait_until="domcontentloaded", timeout=20000)
                try:
                    await page.wait_for_selector("h1, .title, .article-title", timeout=5000)
                except Exception:
                    pass
                html = await page.content()
                detail = self._parse_detail_html(html)
                raw = {**raw, **detail}
            except Exception as exc:
                logger.warning("Wanfang detail page failed: {}", exc)
            finally:
                await self._release_page(page)

        return PaperMetadata(
            title=strip_html(str(raw.get("title") or result.title)) or result.title,
            authors=split_authors(raw.get("authors") or ""),
            abstract=clean_text(raw.get("abstract") or "") or None,
            keywords=split_keywords(raw.get("keywords") or ""),
            paper_type=raw.get("paper_type"),
            source_site="wanfang",
            source_url=result.detail_url,
            raw_data=raw,
            journal=clean_text(raw.get("journal") or "") or None,
            pub_year=clean_text(raw.get("pub_year") or "") or None,
        )

    def _parse_detail_html(self, html: str) -> dict[str, str]:
        detail: dict[str, str] = {}
        patterns = {
            "title": r'<h1[^>]*>(.*?)</h1>',
            "authors": r'(?:作者|Author)[：:]\s*<[^>]*>(.*?)</[^>]*>',
            "abstract": r'(?:摘要|Abstract)[：:]\s*<[^>]*>(.*?)</[^>]*>',
            "keywords": r'(?:关键词|Keywords?)[：:]\s*<[^>]*>(.*?)</[^>]*>',
            "journal": r'(?:期刊|刊名|Journal|来源|母体文献)[：:]\s*<[^>]*>(.*?)</[^>]*>',
            "pub_year": r'(?:年份|出版年|Year|发表时间)[：:]\s*<[^>]*>(.*?)</[^>]*>',
            "paper_type": r'(?:文献类型|资源类型|Type)[：:]\s*<[^>]*>(.*?)</[^>]*>',
        }
        for field, pattern in patterns.items():
            m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if m:
                detail[field] = clean_text(strip_html(m.group(1))) or ""
        return detail

    async def close(self) -> None:
        # Close all pooled pages
        if self._browser_initialized:
            try:
                while not self._page_pool.empty():
                    page = self._page_pool.get_nowait()
                    try:
                        await page.close()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if self._context:
                    await self._context.close()
            except Exception:
                pass
            try:
                if self._browser:
                    await self._browser.close()
            except Exception:
                pass
            try:
                if self._playwright:
                    await self._playwright.stop()
            except Exception:
                pass
            self._browser_initialized = False
        await super().close()
