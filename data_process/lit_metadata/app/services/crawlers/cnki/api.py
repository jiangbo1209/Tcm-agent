"""
cnki_api.py
-----------
基于 aiohttp 的 CNKI POST API 客户端，复刻 jasminum 的通信方式。

为什么不再用 Playwright 整页渲染？
    1. 详情页要等 AJAX（#kcms-mobile-publication 懒加载）；
    2. 每个关键词都有可能弹滑块；
    3. 速度慢，20 条跑 5~10 分钟。

改用 jasminum 的两步式 POST：
    1) POST https://kns.cnki.net/kns8s/brief/grid
        form-url-encoded body，其中 QueryJson 字段是一段 JSON 字符串。
        返回一段 HTML 片段（表格），解析 <tr> 提取 exportID / dbname / filename / url / title。
    2) POST https://kns.cnki.net/dm8/API/GetExport
        form-url-encoded body: filename=<exportID>&uniplatform=NZKPT&displaymode=GBTREFER,elearning,EndNote
        返回 JSON，其中 data[].key=='EndNote' 的 value[0] 即 EndNote 文本。

两个端点都可能返回 HTTP 403，body 形如 {"message": "<captchaUrl>"}，
此时抛出 CaptchaRequired 异常由上层触发 cookie_bootstrap 重过验证。

Cookie 策略：
    - 内存里持有一份 dict[str, str]，按需随请求带上
    - 同时 dump 到 settings.debug_dir/cnki_cookies.json（带时间戳）
    - 5 分钟 TTL：过期视同不存在，需要重新过验证
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
from lxml import html as lxml_html
from yarl import URL


log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
COOKIE_TTL_SEC: int = 5 * 60  # 与 jasminum 保持一致

# jasminum 写死的跨库码
KUAKU_CODE: str = (
    "YSTT4HG0,LSTPFY1C,JUP3MUPD,MPMFIG1A,WQ0UVIAA,"
    "BLZOG7CK,PWFIRAGL,EMRPGLPA,NLBO1Z6R,NN3FJMUV"
)

PRODUCT_STR: str = (
    "YSTT4HG0,LSTPFY1C,RMJLXHZ3,JQIRZIYA,JUP3MUPD,"
    "1UR4K4HZ,BPBAFJ5S,R79MZMCB,MPMFIG1A,WQ0UVIAA,"
    "NB3BWEHK,XVLO76FD,HR1YT1Z9,BLZOG7CK,PWFIRAGL,"
    "EMRPGLPA,J708GVCE,ML4DRIDX,NLBO1Z6R,NN3FJMUV,"
)

# 引导页 URL，bootstrap 打开的就是它
HOME_REFERER: str = (
    "https://kns.cnki.net/kns8s/defaultresult/index"
    "?crossids=YSTT4HG0%2CLSTPFY1C%2CJUP3MUPD%2CMPMFIG1A%2CWQ0UVIAA"
    "%2CBLZOG7CK%2CPWFIRAGL%2CEMRPGLPA%2CNLBO1Z6R%2CNN3FJMUV"
    "&korder=SU&kw="
)

SEARCH_URL: str = "https://kns.cnki.net/kns8s/brief/grid"
EXPORT_URL: str = "https://kns.cnki.net/dm8/API/GetExport"

DEFAULT_UA: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# 异常
# --------------------------------------------------------------------------- #
class CaptchaRequired(Exception):
    """CNKI 返回 403 + captcha URL，需要重过验证。"""

    def __init__(self, captcha_url: str, raw_body: str = "") -> None:
        super().__init__(f"CNKI 需要重新验证: {captcha_url}")
        self.captcha_url = captcha_url
        self.raw_body = raw_body


class CnkiApiError(Exception):
    """其它非预期错误（JSON 解析失败 / 空结果等）。"""


# --------------------------------------------------------------------------- #
# 搜索结果模型
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class SearchResult:
    """一条搜索结果，字段来自 jasminum 的解析逻辑。"""
    export_id: str        # <td class="seq"><input value="...">，后续 GetExport 必用
    dbname: str           # 学位论文 CDFD/CMFD、期刊 CJFD、会议 CPFD、报纸 CCND 等
    filename: str         # 库内主键
    url: str              # 详情页链接（一般 /kcms2/article/abstract?v=...）
    title: str            # 论文标题
    authors: str = ""     # 原始 td.author，"A;B" 风格
    source: str = ""      # 期刊 / 学位授予单位，td.source
    date: str = ""        # 发表时间 / 出版时间字符串
    citation: str = ""    # 被引频次

    def guess_paper_type(self) -> str:
        """根据 dbname 推断类型，失败回落 unknown。后续 EndNote %0 解析可覆盖。"""
        db = (self.dbname or "").upper()
        if db.startswith("CJFD") or db.startswith("CJFQ") or db.startswith("CAPJ"):
            return "journal"
        if db.startswith("CDFD"):
            return "phd"
        if db.startswith("CMFD"):
            return "master"
        if db.startswith("CPFD") or db.startswith("IPFD") or db.startswith("CIPD"):
            return "conference"
        if db.startswith("CCND"):
            return "newspaper"
        return "unknown"


# --------------------------------------------------------------------------- #
# 工具：构造搜索表达式 / 表单
# --------------------------------------------------------------------------- #
def _build_search_expr(
    title: str, author: str | None = None, *, field: str = "TI"
) -> str:
    """
    复刻 jasminum.createSearchPostOptions 的 searchExp。
        - 含空格：`({field} %= '标题')`
        - 不含空格：`{field} %= '标题'`
        - 有 author：末尾 AND AU='作者'
    field 可选 TI（题名，默认）、SU（主题）、FT（全文）、KY（关键词）。
    """
    title = title.strip()
    field = field.upper()
    if " " in title:
        expr = f"({field} %= '{title}')"
    else:
        expr = f"{field} %= '{title}'"
    if author:
        expr = f"{expr} AND AU='{author.strip()}'"
    return expr


def _build_query_json(search_expr: str) -> dict[str, Any]:
    """大陆版 CNKI 的 QueryJson（内层对象）。"""
    return {
        "Platform": "",
        "Resource": "CROSSDB",
        "Classid": "WD0FTY92",
        "Products": "",
        "QNode": {
            "QGroup": [
                {
                    "Key": "Subject",
                    "Title": "",
                    "Logic": 0,
                    "Items": [
                        {
                            "Key": "Expert",
                            "Title": "",
                            "Logic": 0,
                            "Field": "EXPERT",
                            "Operator": 0,
                            "Value": search_expr,
                            "Value2": "",
                        }
                    ],
                    "ChildItems": [],
                },
                {
                    "Key": "ControlGroup",
                    "Title": "",
                    "Logic": 0,
                    "Items": [],
                    "ChildItems": [],
                },
            ]
        },
        "ExScope": "1",
        "SearchType": 4,
        "Rlang": "CHINESE",
        "KuaKuCode": KUAKU_CODE,
        "SearchFrom": 1,
    }


def _build_search_form(
    title: str, author: str | None = None, *, field: str = "TI"
) -> dict[str, str]:
    """
    构造最终 form 字段（值全为 str，含嵌套对象会被 JSON.stringify）。
    aiohttp 的 data=dict 会自动 urlencode，但嵌套对象不行，所以这里提前 stringify。
    """
    expr = _build_search_expr(title, author, field=field)
    expr_aside = expr.replace("'", "&#39;")  # jasminum 对 aside 做了 HTML 转义
    query_json = _build_query_json(expr)
    return {
        "boolSearch": "true",
        "QueryJson": json.dumps(query_json, ensure_ascii=False, separators=(",", ":")),
        "pageNum": "1",
        "pageSize": "20",
        "sortField": "",
        "sortType": "",
        "dstyle": "listmode",
        "productStr": PRODUCT_STR,
        "aside": f"({expr_aside})",
        "searchFrom": "资源范围：总库;++中英文扩展;++时间范围：更新时间：不限;++",
        "CurPage": "1",
    }


# --------------------------------------------------------------------------- #
# 工具：解析 grid 表格
# --------------------------------------------------------------------------- #
_RE_WS = re.compile(r"\s+")


def _clean(text: str | None) -> str:
    return _RE_WS.sub(" ", (text or "")).strip()


# --------------------------------------------------------------------------- #
# 工具：解析详情页 HTML（EndNote 缺字段时回落）
# --------------------------------------------------------------------------- #
def _text_no_sup(el: Any) -> str:
    """取 <a> 等元素的文本，去掉 <sup>/<em> 里的上标（CNKI 作者后缀 1,2,...）。"""
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        if child.tag in ("sup", "em"):
            if child.tail:
                parts.append(child.tail)
            continue
        parts.append(child.text_content())
        if child.tail:
            parts.append(child.tail)
    return _clean("".join(parts))


def _parse_detail_html(body: str) -> dict[str, Any]:
    """
    从详情页 HTML 抽 title / authors / keywords / abstract / pub_year。
    任一缺失返回 None。专门用来补 EndNote 没导出的字段。
    """
    if not body:
        return {}
    root = lxml_html.fromstring(body)

    # -- 标题：.wx-tit h1 （兼容旧版 .doc-title .text）--
    title = ""
    for xp in (
        ".//*[contains(@class,'doc-title')]//*[contains(@class,'text')]",
        ".//*[contains(@class,'wx-tit')]//h1",
        ".//*[contains(@class,'doc-top')]//h1",
    ):
        els = root.xpath(xp)
        if els:
            title = _clean(els[0].text_content())
            if title:
                break

    # -- 作者：h3[@id='authorpart'] 下的作者链接（排 /organ/ 机构链接）--
    authors: list[str] = []
    seen_a: set[str] = set()
    author_as = root.xpath(
        ".//h3[@id='authorpart']//a[contains(@href,'/author/')] "
        "| .//h3[contains(@class,'author')][not(@id) or @id='authorpart']"
        "//a[contains(@href,'/author/')]"
    )
    for a in author_as:
        name = _text_no_sup(a)
        # 再保险去掉尾部数字（万一 sup 丢了）
        name = re.sub(r"[\d,，；;]+$", "", name).strip()
        if name and name not in seen_a:
            seen_a.add(name)
            authors.append(name)

    # -- 关键词：p.keywords a / .keywords-text a --
    keywords: list[str] = []
    seen_kw: set[str] = set()
    kw_as = root.xpath(
        ".//p[contains(@class,'keywords')]//a "
        "| .//*[contains(@class,'keywords-text')]//a"
    )
    for a in kw_as:
        kw = _clean(a.text_content()).rstrip(";；,， ").strip()
        if kw and kw not in seen_kw:
            seen_kw.add(kw)
            keywords.append(kw)

    # -- 摘要：#ChDivSummary 优先，其次 .abstract-text --
    abstract = ""
    for xp in (
        ".//*[@id='ChDivSummary']",
        ".//*[contains(@class,'abstract-text')]",
    ):
        els = root.xpath(xp)
        if els:
            abstract = _clean(els[0].text_content())
            if abstract:
                break

    # -- 年份：input#article-year --
    pub_year = ""
    yr = root.xpath(".//input[@id='article-year']/@value")
    if yr:
        m = re.search(r"\d{4}", yr[0])
        pub_year = m.group(0) if m else ""

    return {
        "title": title or None,
        "authors": "; ".join(authors) if authors else None,
        "keywords": "; ".join(keywords) if keywords else None,
        "abstract": abstract or None,
        "pub_year": pub_year or None,
    }


# --------------------------------------------------------------------------- #
# 工具：搜索失败时降级简化标题
# --------------------------------------------------------------------------- #
_RE_PAREN = re.compile(r"[（(【\[][^）)】\]]*[）)】\]]")
_RE_TRAIL_VERSION = re.compile(r"[\s—\-]*(?:第[一二三四五六七八九十0-9]+版|\d{4}年版?|修订版|增订版)\s*$")


def simplify_query(title: str) -> str:
    """
    search() 返回空时的降级：
        - 去掉 (...)（...）【...】[...] 里的内容
        - 去掉尾部 "（2023年版）" / "第三版" / "修订版"
        - 压缩空白
    返回和原标题不同时才有意义。
    """
    t = _RE_PAREN.sub("", title)
    t = _RE_TRAIL_VERSION.sub("", t)
    t = _RE_WS.sub(" ", t).strip()
    return t


def _parse_search_html(body: str) -> list[SearchResult]:
    """
    jasminum 用 document.querySelectorAll('table.result-table-list > tbody > tr')。
    CNKI 返回的只是 <tbody> 片段，没有外层文档头；lxml.html 能吃得下。
    """
    if not body or "<tr" not in body:
        return []
    root = lxml_html.fromstring(body)
    rows = root.xpath(
        "//table[contains(@class,'result-table-list')]//tr "
        "| //tbody/tr "
        "| //tr[td[contains(@class,'seq')]]"
    )
    # 去重（有时三段 xpath 命中同一行）
    seen: set[int] = set()
    uniq_rows = []
    for r in rows:
        key = id(r)
        if key in seen:
            continue
        seen.add(key)
        uniq_rows.append(r)

    results: list[SearchResult] = []
    for row in uniq_rows:
        seq_input = row.xpath(".//td[contains(@class,'seq')]//input/@value")
        if not seq_input:
            # 表头或者空行
            continue
        export_id = _clean(seq_input[0])

        name_a = row.xpath(".//a[contains(@class,'fz14')]")
        if not name_a:
            continue
        a = name_a[0]
        url = _clean(a.get("href"))
        title = _clean(a.text_content())

        op_el = row.xpath(".//td[contains(@class,'operat')]//*[@data-dbname]")
        dbname = _clean(op_el[0].get("data-dbname")) if op_el else ""
        filename = _clean(op_el[0].get("data-filename")) if op_el else ""

        author_cell = row.xpath(".//td[contains(@class,'author')]")
        authors = _clean(author_cell[0].text_content()) if author_cell else ""

        source_cell = row.xpath(".//td[contains(@class,'source')]")
        source = _clean(source_cell[0].text_content()) if source_cell else ""

        date_cell = row.xpath(".//td[contains(@class,'date')]")
        date = _clean(date_cell[0].text_content()) if date_cell else ""

        quote_cell = row.xpath(".//td[contains(@class,'quote')]")
        citation = _clean(quote_cell[0].text_content()) if quote_cell else ""

        if not url.startswith("http"):
            url = "https://kns.cnki.net" + url

        results.append(
            SearchResult(
                export_id=export_id,
                dbname=dbname,
                filename=filename,
                url=url,
                title=title,
                authors=authors,
                source=source,
                date=date,
                citation=citation,
            )
        )
    return results


# --------------------------------------------------------------------------- #
# Cookie 持久化
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class CookieStore:
    """保存 {"ts": float, "cookies": {name: value}} 到 JSON。"""
    path: Path
    ttl_sec: int = COOKIE_TTL_SEC

    def load(self) -> dict[str, str] | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("cookie 文件解析失败：%s", e)
            return None
        ts = float(data.get("ts", 0))
        if time.time() - ts > self.ttl_sec:
            log.info("cookie 已过期（>%ds）", self.ttl_sec)
            return None
        cookies = data.get("cookies") or {}
        if not isinstance(cookies, dict) or len(cookies) < 2:
            return None
        return {str(k): str(v) for k, v in cookies.items()}

    def save(self, cookies: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": time.time(), "cookies": cookies}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# --------------------------------------------------------------------------- #
# 客户端本体
# --------------------------------------------------------------------------- #
class CnkiClient:
    """
    用法：
        async with CnkiClient(cookie_store, user_agent=...) as c:
            results = await c.search("标题")
            text = await c.get_export(results[0])
    """

    def __init__(
        self,
        cookie_store: CookieStore,
        *,
        user_agent: str = DEFAULT_UA,
        timeout_sec: float = 15.0,
    ) -> None:
        self.store = cookie_store
        self.user_agent = user_agent
        self.timeout = aiohttp.ClientTimeout(total=timeout_sec)
        self._session: aiohttp.ClientSession | None = None
        self._cookies: dict[str, str] = cookie_store.load() or {}

    # ---------- 生命周期 ----------
    async def __aenter__(self) -> "CnkiClient":
        # 用 cookies= 参数让 aiohttp 自动带 cookie jar
        self._session = aiohttp.ClientSession(
            timeout=self.timeout,
            cookies=self._cookies,
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    # ---------- cookie 读写 ----------
    @property
    def cookies(self) -> dict[str, str]:
        return dict(self._cookies)

    def update_cookies(self, cookies: dict[str, str]) -> None:
        """
        被 cookie_bootstrap 重过验证后回填新 cookie。
        同步方法，要求此时 session 已存在（即已进入 async with）。
        """
        self._cookies = dict(cookies)
        self.store.save(self._cookies)
        if self._session is not None:
            self._session.cookie_jar.update_cookies(
                cookies, response_url=URL("https://kns.cnki.net/")
            )

    def cookies_usable(self) -> bool:
        return len(self._cookies) >= 2 and self.store.load() is not None

    # ---------- 公开 API ----------
    async def search(
        self, title: str, author: str | None = None, *, field: str = "TI"
    ) -> list[SearchResult]:
        form = _build_search_form(title, author, field=field)
        headers = self._base_headers(referer=HOME_REFERER)
        status, body = await self._post(SEARCH_URL, form, headers)
        if status == 403:
            self._raise_captcha(body)
        if status != 200:
            raise CnkiApiError(f"/kns8s/brief/grid HTTP {status}: {body[:200]}")
        return _parse_search_html(body)

    async def get_export(self, result: SearchResult) -> str:
        """
        返回 EndNote 原始文本。data.key=='EndNote' 的 value[0] 里的 <br> 转换为 \\n。
        """
        headers = self._base_headers(referer=result.url)
        headers["Accept"] = "text/plain, */*; q=0.01"
        form = {
            "filename": result.export_id,
            "uniplatform": "NZKPT",
            "displaymode": "GBTREFER,elearning,EndNote",
        }
        status, body = await self._post(EXPORT_URL, form, headers)
        if status == 403:
            self._raise_captcha(body)
        if status != 200:
            raise CnkiApiError(f"/dm8/API/GetExport HTTP {status}: {body[:200]}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise CnkiApiError(f"GetExport 返回非 JSON：{body[:200]}") from e
        if payload.get("code") != 1:
            raise CnkiApiError(f"GetExport code!=1：{payload}")
        for entry in payload.get("data") or []:
            if entry.get("key") == "EndNote":
                values = entry.get("value") or []
                if values:
                    return values[0].replace("<br>", "\n")
        raise CnkiApiError("GetExport 响应中没有 EndNote 条目")

    async def fetch_detail(self, url: str) -> str:
        """GET 详情页 HTML。用 session 里的 cookie。"""
        if self._session is None:
            raise RuntimeError("CnkiClient 未进入 async with 上下文")
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,en-US;q=0.9,en;q=0.8",
            "Referer": HOME_REFERER,
        }
        async with self._session.get(url, headers=headers) as resp:
            text = await resp.text(encoding="utf-8", errors="replace")
            if resp.status == 403:
                self._raise_captcha(text)
            if resp.status != 200:
                raise CnkiApiError(f"GET {url} HTTP {resp.status}")
            return text

    # ---------- 内部 ----------
    def _base_headers(self, *, referer: str) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://kns.cnki.net",
            "Referer": referer,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
        }

    async def _post(
        self, url: str, form: dict[str, str], headers: dict[str, str]
    ) -> tuple[int, str]:
        if self._session is None:
            raise RuntimeError("CnkiClient 未进入 async with 上下文")
        # aiohttp 的 data=dict 会把每个 value URL-encode 并以 & 连接。
        # 我们已经把嵌套对象 JSON.stringify 了，直接传即可。
        async with self._session.post(url, data=form, headers=headers) as resp:
            text = await resp.text(encoding="utf-8", errors="replace")
            # 请求成功的话 response set-cookie 会自动进 jar，同步更新一份到 self._cookies
            if resp.status == 200:
                self._sync_cookies_from_jar()
            return resp.status, text

    def _sync_cookies_from_jar(self) -> None:
        """把 aiohttp 的 cookie_jar 拷贝到 self._cookies 并落盘。"""
        if self._session is None:
            return
        jar = self._session.cookie_jar
        cookies: dict[str, str] = {}
        for cookie in jar:
            cookies[cookie.key] = cookie.value
        if cookies and cookies != self._cookies:
            self._cookies = cookies
            self.store.save(self._cookies)

    def _raise_captcha(self, body: str) -> None:
        """
        403 场景：CNKI 在 body 中放 {"message": "<captchaUrl>"}。
        找不到就把整段 body 抛出，由上层决定怎么处理。
        """
        try:
            payload = json.loads(body)
            url = str(payload.get("message") or "")
        except Exception:
            url = ""
        if not url:
            # 有些场景 message 字段叫别的名字，兜底用正则抓一个 http URL
            m = re.search(r"https?://[^\s\"'<>]+", body)
            url = m.group(0) if m else ""
        if not url:
            raise CnkiApiError(f"403 且解析不出 captcha URL：{body[:200]}")
        raise CaptchaRequired(url, raw_body=body)
