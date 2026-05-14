"""
endnote_parser.py
-----------------
解析 CNKI 导出的 EndNote 文本。形如：

    %0 Journal Article
    %A 任梦雪
    %A 隋娟
    %T 中成药联合枸橼酸氯米芬治疗排卵障碍性不孕症的网状Meta分析
    %J 时珍国医国药
    %D 2023
    %K 排卵障碍性不孕症;中成药;枸橼酸氯米芬
    %X 目的...结论...
    %@ 1008-0805

一条记录以 `%0` 开头，多条记录之间通常以空行分隔。每行 `%X <value>`，X 为单字母/数字。

字段映射（仅保留我们入库用的）：
    %0  类型（Journal Article / Thesis / Conference Proceedings / Newspaper Article）
    %T  title
    %A  author（重复，聚合到 authors，"; " 拼接）
    %J  secondary source → 期刊名 或 学位授予单位
    %D  date → pub_year（截取前 4 位）
    %K  keywords
    %X  abstract
    %9  学位类型（博士 / 硕士）——用来区分 phd / master
"""

from __future__ import annotations

import logging
import re
from typing import Any


log = logging.getLogger(__name__)


_RE_WS = re.compile(r"\s+")
# EndNote 的 tag 字符很杂：数字 / 字母 / @ / + / ? / > / ! 都见过。
# 只要行首是 % 跟一个非空白字符再加空格，就当一个 tag。
_RE_LINE = re.compile(r"^%(\S)\s+(.*)$")


def _clean(s: str) -> str:
    return _RE_WS.sub(" ", s).strip()


def _classify(
    type0: str, type9: str = "", dbname: str = ""
) -> str:
    """根据 %0、%9、dbname 三路信号判 paper_type。"""
    t0 = (type0 or "").strip().lower()
    t9 = (type9 or "").strip()
    db = (dbname or "").upper()

    # %0 直接能识别的类型
    if "journal" in t0:
        return "journal"
    if "conference" in t0 or "proceedings" in t0:
        return "conference"
    if "newspaper" in t0:
        return "newspaper"

    # %0 = Thesis 需要再细分博士 / 硕士
    if "thesis" in t0 or "dissertation" in t0:
        if "博士" in t9 or db.startswith("CDFD"):
            return "phd"
        if "硕士" in t9 or db.startswith("CMFD"):
            return "master"
        # 都没命中但确实是学位论文，回落 master（CNKI 绝大部分学位论文是硕士）
        return "master" if db.startswith("CMFD") or not db else "phd"

    # %0 没识别出来，走 dbname 兜底
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


def parse_endnote(text: str, *, dbname: str = "") -> dict[str, Any]:
    """
    解析一段 EndNote 文本，返回字段字典：
        title / authors / abstract / keywords / journal / pub_year / paper_type

    如果能解析出多条记录（很少见），只取第一条。
    """
    if not text:
        return {}

    # 字段收集器
    title: str = ""
    authors: list[str] = []
    journal: str = ""
    pub_year: str = ""
    keywords: str = ""
    abstract: str = ""
    type0: str = ""
    type9: str = ""

    # 允许值跨行（实际 CNKI 很少跨行，但摘要可能很长，<br> 已在 cnki_api 里替换成 \n，
    # 不过 EndNote 格式本身并不要求值单行——下一行如果不是 % 开头，就是续行）
    last_tag: str | None = None
    buf_lines: list[str] = []

    def _flush() -> None:
        nonlocal title, journal, pub_year, keywords, abstract, type0, type9, last_tag
        if last_tag is None:
            return
        value = _clean(" ".join(buf_lines))
        buf_lines.clear()
        if last_tag == "T":
            title = value
        elif last_tag == "A":
            if value:
                authors.append(value)
        elif last_tag == "J":
            journal = value
        elif last_tag == "D":
            m = re.search(r"\d{4}", value)
            pub_year = m.group(0) if m else value[:4]
        elif last_tag == "K":
            keywords = _normalize_keywords(value)
        elif last_tag == "X":
            abstract = value
        elif last_tag == "0":
            type0 = value
        elif last_tag == "9":
            type9 = value
        last_tag = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            _flush()
            continue
        m = _RE_LINE.match(line)
        if m:
            _flush()
            last_tag, val = m.group(1), m.group(2)
            buf_lines.append(val)
        else:
            # 续行：并到当前 tag 的 buffer
            if last_tag is not None:
                buf_lines.append(line)
    _flush()

    paper_type = _classify(type0, type9, dbname)

    return {
        "title": title or None,
        "authors": "; ".join(authors) if authors else None,
        "abstract": abstract or None,
        "keywords": keywords or None,
        "journal": journal or None,
        "pub_year": pub_year or None,
        "paper_type": paper_type,
    }


def _normalize_keywords(raw: str) -> str:
    """
    %K 的格式不固定：
        - "A;B;C"
        - "A; B; C"
        - "A,B,C"
        - "A B C"  （空格分隔，少见）
    统一成 `"A; B; C"`，去空值去重保序。
    """
    if not raw:
        return ""
    # 先按常见分隔符切
    parts = re.split(r"[;；,，]\s*", raw)
    if len(parts) == 1:
        # 只有一项，再试试空白切（但只在 2+ 段时切，避免单词被拆）
        space_parts = re.split(r"\s{2,}", raw)
        if len(space_parts) > 1:
            parts = space_parts
    seen: dict[str, None] = {}
    for p in parts:
        p = p.strip()
        if p:
            seen.setdefault(p, None)
    return "; ".join(seen)
