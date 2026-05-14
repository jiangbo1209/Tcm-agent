"""
cookie_bootstrap.py
-------------------
首次 / 过期后用 Playwright 打开 CNKI，人工完成滑块验证后抽取 cookie。

UX 复刻 jasminum：
    1. headless=False 启动 chromium
    2. goto 给定 URL（默认是 HOME_REFERER）
    3. 在页面右上角注入一个红框 + "确认完成验证" 绿色按钮
    4. 用户滑完滑块、看到页面正常加载后点按钮
    5. 脚本检测到标记位翻转，抽出 context.cookies() 并保存到 CookieStore

为什么不自动滑？
    - OpenCV 缺口识别对 CNKI 的图样识别率低
    - CNKI 滑块会检测鼠标轨迹的"人味"，一旦失败会直接拉黑
    - 首次人工过一次，5 分钟 TTL 内的所有请求都能复用，代价可接受
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from playwright.async_api import async_playwright, BrowserContext

from .api import CookieStore, HOME_REFERER


log = logging.getLogger(__name__)


# 页面上的红框 + 按钮；window.__captcha_confirmed__ 作为握手标记
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
        <div style="font-weight:bold;font-size:14px;margin-bottom:6px">CNKI 爬虫提示</div>
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


async def _collect_cookies(context: BrowserContext) -> dict[str, str]:
    """把 Playwright BrowserContext 的所有 cookie 合成 name->value 字典。"""
    raw = await context.cookies()
    # 只保留 CNKI 相关域：cnki.net / kns.cnki.net / www.cnki.net
    cookies: dict[str, str] = {}
    for c in raw:
        domain = (c.get("domain") or "").lstrip(".")
        if "cnki" not in domain:
            continue
        cookies[c["name"]] = c["value"]
    return cookies


def _fire_and_forget(coro: Any) -> None:
    """把 awaitable 丢进 loop 里跑，不关心结果；用于 Playwright 事件回调。"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    task = loop.create_task(coro)
    # 防止 loop 关闭时报 "Task was destroyed but it is pending"
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)


async def bootstrap_cookies(
    store: CookieStore,
    *,
    url: str | None = None,
    hint: str | None = None,
    headless: bool = False,
    timeout_ms: int = 0,
    channel: str | None = None,
) -> dict[str, str]:
    """
    打开 url，等待用户点击"确认完成验证"按钮，返回 cookie 字典并落盘。

    参数：
        store       : CookieStore，用来落盘
        url         : 默认 HOME_REFERER；403 重过时传 respJson["message"]
        hint        : 浮层里显示的提示文案
        headless    : 默认 False；用户必须能看见页面才能滑滑块
        timeout_ms  : 0 表示无限等待（默认就这样，调试时可设 300_000）

    抛 TimeoutError 说明用户没及时确认。
    """
    target_url = url or HOME_REFERER
    hint_text = hint or "请等待知网页面正常加载（如需滑块，请完成），然后点击下方按钮。"

    async with async_playwright() as p:
        launch_kwargs: dict[str, Any] = {"headless": headless}
        if channel:
            launch_kwargs["channel"] = channel
        browser = await p.chromium.launch(**launch_kwargs)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            log.info("cookie 引导：打开 %s", target_url)
            await page.goto(target_url, wait_until="domcontentloaded")

            # 首次注入
            await page.evaluate(_OVERLAY_JS, hint_text)

            # 跳转后浮层会被新 DOM 覆盖，load 事件里重注一次
            page.on(
                "load",
                lambda _f: _fire_and_forget(page.evaluate(_OVERLAY_JS, hint_text)),
            )

            log.info("等待用户点击'确认完成验证'按钮…（headless=%s）", headless)
            await page.wait_for_function(
                "window.__captcha_confirmed__ === true",
                timeout=timeout_ms,
            )

            cookies = await _collect_cookies(context)
            log.info("抽到 %d 条 CNKI cookie", len(cookies))
            if len(cookies) < 2:
                raise RuntimeError(
                    f"cookie 太少（{len(cookies)} 条），可能页面没加载完就被点了"
                )
            store.save(cookies)
            return cookies
        finally:
            await browser.close()


def _fire_and_forget(coro: Any) -> None:
    """把 awaitable 丢进 loop 里跑，不关心结果；用于 Playwright 事件回调。"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    task = loop.create_task(coro)
    # 防止 loop 关闭时报 "Task was destroyed but it is pending"
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)


