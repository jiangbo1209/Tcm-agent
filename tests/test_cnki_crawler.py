from __future__ import annotations

from services.crawlers.cnki.api import (
    SearchResult as CnkiSearchResult,
    _parse_search_html,
    simplify_query,
)
from services.crawlers.cnki.endnote_parser import parse_endnote


def test_simplify_query_strips_parens() -> None:
    assert simplify_query("某某研究（2023年版）") == "某某研究"
    assert simplify_query("基于深度学习的研究 (第二版)") == "基于深度学习的研究"


def test_simplify_query_strips_trail_version() -> None:
    assert simplify_query("药典 第二版") == "药典"
    assert simplify_query("教材 2024年版") == "教材"


def test_simplify_query_no_change_returns_same() -> None:
    assert simplify_query("中药治疗") == "中药治疗"


def test_parse_endnote_journal_full_fields() -> None:
    text = (
        "%0 Journal Article\n"
        "%A 张三\n"
        "%A 李四\n"
        "%T 中药治疗多囊卵巢综合征的Meta分析\n"
        "%J 时珍国医国药\n"
        "%D 2023\n"
        "%K 多囊卵巢综合征;中药;Meta分析\n"
        "%X 目的探讨中药治疗。结论中药有效。\n"
    )
    parsed = parse_endnote(text, dbname="CJFD")
    assert parsed["title"] == "中药治疗多囊卵巢综合征的Meta分析"
    assert parsed["authors"] == "张三; 李四"
    assert parsed["journal"] == "时珍国医国药"
    assert parsed["pub_year"] == "2023"
    assert parsed["keywords"] == "多囊卵巢综合征; 中药; Meta分析"
    assert parsed["abstract"].startswith("目的探讨")
    assert parsed["paper_type"] == "journal"


def test_parse_endnote_thesis_phd_via_dbname() -> None:
    text = "%0 Thesis\n%T 博士论文标题\n%A 某博士\n"
    parsed = parse_endnote(text, dbname="CDFD")
    assert parsed["paper_type"] == "phd"


def test_parse_endnote_thesis_master_via_type9() -> None:
    text = "%0 Thesis\n%T 硕士论文标题\n%A 某硕士\n%9 硕士\n"
    parsed = parse_endnote(text, dbname="CMFD")
    assert parsed["paper_type"] == "master"


def test_parse_endnote_conference() -> None:
    text = "%0 Conference Proceedings\n%T 会议论文\n%A 作者甲\n"
    parsed = parse_endnote(text, dbname="CPFD")
    assert parsed["paper_type"] == "conference"


def test_parse_endnote_empty_returns_empty_dict() -> None:
    assert parse_endnote("") == {}


def test_cnki_search_result_guess_paper_type() -> None:
    assert CnkiSearchResult(
        export_id="x", dbname="CJFD2023", filename="f", url="u", title="t"
    ).guess_paper_type() == "journal"
    assert CnkiSearchResult(
        export_id="x", dbname="CDFD2023", filename="f", url="u", title="t"
    ).guess_paper_type() == "phd"
    assert CnkiSearchResult(
        export_id="x", dbname="CMFD2023", filename="f", url="u", title="t"
    ).guess_paper_type() == "master"
    assert CnkiSearchResult(
        export_id="x", dbname="CCND2023", filename="f", url="u", title="t"
    ).guess_paper_type() == "newspaper"
    assert CnkiSearchResult(
        export_id="x", dbname="UNKNOWN", filename="f", url="u", title="t"
    ).guess_paper_type() == "unknown"


def test_parse_search_html_empty_returns_empty_list() -> None:
    assert _parse_search_html("") == []
    assert _parse_search_html("<div>no tr</div>") == []
