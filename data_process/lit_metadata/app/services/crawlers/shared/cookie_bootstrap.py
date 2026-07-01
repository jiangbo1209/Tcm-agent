"""
cookie_bootstrap.py
-------------------
Shared Playwright-based cookie bootstrapping for crawlers.

When a crawler triggers a captcha or access block, open a Chromium browser
window so the user can manually solve it. Cookies are extracted and saved
for reuse (with TTL).

All cookies are saved under OUTPUT_DIR/cookies/<site>_cookies.json.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, async_playwright

log = logging.getLogger(__name__)

COOKIE_TTL_SEC: int = 5 * 60

_OVERLAY_JS = r"""
(hintText, siteLabel) => {
    const old = document.getElementById('__captcha_confirm_box__');
    if (old) old.remove();
    const box = document.createElement('div');
    box.id = '__captcha_confirm_box__';
    box.style.cssText = [
        'position:fixed', 'top:10px', 'right:10px', 'z-index:2147483647',
        'padding:15px', 'background:white', 'border:3px solid red',
        'border-radius:8px', 'box-shadow:0 4px 8px rgba(0,0,0,0.3)',
        'font-family:system-ui,Arial,sans-serif', 'color:black',
        'max-width:280px'
    ].join(';');
    box.innerHTML = `
        <div style="font-weight:bold;font-size:14px;margin-bottom:6px">${siteLabel} 爬虫提示</div>
        <div style="font-size:12px;margin-bottom:10px;line-height:1.5">${hintText}</div>
        <button id="__captcha_confirm_btn__"
                style="width:100%;padding:6px 8px;background:#4CAF50;color:white;
                       border:none;border-radius:5px;font-weight:bold;cursor:pointer;
                       font-size:13px">
            确认完成验证
        </button>
    `;
    document.documentElement.appendChild(box);
    window.__captcha_confirmed__ = false;
    document.getElementById('__captcha_confirm_btn__').addEventListener('click', () => {
        window.__captcha_confirmed__ = true;
        box.style.borderColor = '#2E7D32';
        const btn = document.getElementById('__captcha_confirm_btn__');
        btn.textContent = '已确认，抽取 cookie 中…';
        btn.disabled = true;
    });
}
"""


class CookieStore:
    """Persist cookies to JSON file with TTL expiration."""

    def __init__(self, filepath: Path, ttl_sec: int = COOKIE_TTL_SEC) -> None:
        self.filepath = filepath
        self.ttl_sec = ttl_sec

    def load(self) -> dict[str, str] | None:
        if not self.filepath.exists():
            return None
        try:
            data = json.loads(self.filepath.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Cookie file parse failed: %s", exc)
            return None
        ts = float(data.get("ts", 0))
        if time.time() - ts > self.ttl_sec:
            log.info("Cookies expired (>%ds)", self.ttl_sec)
            return None
        cookies = data.get("cookies") or {}
        if not isinstance(cookies, dict) or len(cookies) < 2:
            return None
        return {str(k): str(v) for k, v in cookies.items()}

    def save(self, cookies: dict[str, str]) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": time.time(), "cookies": cookies}
        self.filepath.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _extract_cookies(context: BrowserContext, domains: list[str]) -> dict[str, str]:
    """Extract cookies whose domain matches any of the given patterns (substring match)."""
    raw = context.cookies()
    cookies: dict[str, str] = {}
    for c in raw:
        domain = (c.get("domain") or "").lstrip(".").lower()
        if any(pattern in domain for pattern in domains):
            cookies[c["name"]] = c["value"]
    return cookies


async def bootstrap_cookies(
    store: CookieStore,
    *,
    target_url: str,
    site_label: str,
    domains: list[str] | None = None,
    hint: str | None = None,
    headless: bool = False,
    timeout_ms: int = 0,
    channel: str | None = None,
) -> dict[str, str]:
    """
    Open a Playwright browser, let user solve captcha, extract cookies.

    Args:
        store:       CookieStore to persist cookies to disk.
        target_url:  URL the browser opens for captcha solving.
        site_label:  Label shown in the overlay (e.g. "CNKI", "万方").
        domains:     Domain patterns for cookie extraction (e.g. ["cnki", "wanfangdata", "calis"]).
        hint:        Custom hint text in the overlay.
        headless:    Whether to run headless (default False, user must see captcha).
        timeout_ms:  Max wait time (0 = unlimited).
        channel:     Browser channel (e.g. "chrome", "msedge").
    """
    hint_text = hint or "请在浏览器中完成验证码（滑块/点选），页面正常加载后点击右上角按钮。"
    domain_patterns = domains or []

    async with async_playwright() as p:
        launch_kwargs: dict[str, Any] = {"headless": headless}
        if channel:
            launch_kwargs["channel"] = channel
        browser = await p.chromium.launch(**launch_kwargs)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            log.info("%s cookie bootstrap: opening %s", site_label, target_url)
            await page.goto(target_url, wait_until="domcontentloaded")

            await page.evaluate(_OVERLAY_JS, hint_text, site_label)

            page.on(
                "load",
                lambda _f: asyncio.ensure_future(
                    page.evaluate(_OVERLAY_JS, hint_text, site_label)
                ),
            )

            log.info("Waiting for user to complete captcha on %s ... (headless=%s)", site_label, headless)
            await page.wait_for_function(
                "window.__captcha_confirmed__ === true",
                timeout=timeout_ms,
            )

            if domain_patterns:
                cookies = _extract_cookies(context, domain_patterns)
            else:
                raw = await context.cookies()
                cookies = {c["name"]: c["value"] for c in raw if c.get("name")}

            log.info("Extracted %d cookies for %s", len(cookies), site_label)
            if len(cookies) < 2:
                raise RuntimeError(
                    f"Too few cookies ({len(cookies)}) for {site_label}; page may not have loaded"
                )
            store.save(cookies)
            return cookies
        finally:
            await browser.close()


def resolve_cookie_path(output_dir: str, site: str) -> Path:
    """Return the standard cookie file path for a crawler site."""
    return Path(output_dir) / "cookies" / f"{site}_cookies.json"
