"""
yidu_bootstrap.py
------------------
当 yidu 触发验证码时，用 Playwright 打开浏览器让用户手动完成验证，
抽取 cookie 并保存复用。
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

log = logging.getLogger(__name__)

_OVERLAY_JS = r"""
(hintText) => {
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
        <div style="font-weight:bold;font-size:14px;margin-bottom:6px">yidu 爬虫提示</div>
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
        box.style.display = 'none';
    });
}
"""


class YiduCookieStore:
    def __init__(self, filepath: Path, ttl_sec: int = 600) -> None:
        self.filepath = filepath
        self.ttl_sec = ttl_sec

    def load(self) -> dict[str, str] | None:
        if not self.filepath.exists():
            return None
        try:
            data = json.loads(self.filepath.read_text())
            age = asyncio.get_event_loop().time() - data.get("saved_at", 0)
            if age > self.ttl_sec:
                log.info("yidu cookie 已过期（>%ds）", self.ttl_sec)
                return None
            return data.get("cookies", {})
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, cookies: dict[str, str]) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.write_text(json.dumps({
            "cookies": cookies,
            "saved_at": asyncio.get_event_loop().time(),
        }, ensure_ascii=False))


async def bootstrap_yidu(
    store: YiduCookieStore,
    url: str | None = None,
    timeout_ms: int = 0,
) -> dict[str, str]:
    target_url = url or "https://yidu.calis.edu.cn/searchList/index"
    hint_text = "请在浏览器中完成验证码（滑块/点选），页面正常加载后点击右上角按钮。"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            log.info("yidu 引导：打开 %s", target_url)
            await page.goto(target_url, wait_until="domcontentloaded")

            await page.evaluate(_OVERLAY_JS, hint_text)

            log.info("等待用户完成验证码并点击确认…")
            await page.wait_for_function(
                "window.__captcha_confirmed__ === true",
                timeout=timeout_ms,
            )

            raw = await context.cookies()
            cookies = _extract_yidu_cookies(raw)
            log.info("抽到 %d 条 yidu cookie", len(cookies))
            store.save(cookies)
            return cookies
        finally:
            await browser.close()


def _extract_yidu_cookies(raw: list[dict[str, Any]]) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for c in raw:
        domain = (c.get("domain") or "").lower()
        if "calis" not in domain and "yidu" not in domain:
            continue
        cookies[c["name"]] = c["value"]
    return cookies
