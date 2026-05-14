from __future__ import annotations

from app.models.schemas import SearchResult
from app.services.title_matcher import ExactTitleMatcher


def test_exact_match_success() -> None:
    matcher = ExactTitleMatcher()
    assert matcher.is_exact_match("论文标题", "论文标题")


def test_trimmed_spaces_match_success() -> None:
    matcher = ExactTitleMatcher()
    assert matcher.is_exact_match(" 论文标题 ", "论文标题")


def test_continuous_spaces_match_success() -> None:
    matcher = ExactTitleMatcher()
    assert matcher.is_exact_match("基于  深度学习", "基于 深度学习")


def test_contains_relationship_fails() -> None:
    matcher = ExactTitleMatcher()
    assert not matcher.is_exact_match(
        "中药治疗痰湿型多囊卵巢综合征不孕疗效的Meta分析",
        "中药治疗痰湿型多囊卵巢综合征不孕疗效的Meta分析及机制探讨",
    )


def test_similar_title_fails() -> None:
    matcher = ExactTitleMatcher()
    assert not matcher.is_exact_match(
        "基于深度学习的医学图像分割研究",
        "基于深度学习的医学图像分割方法研究",
    )


def test_find_exact_match_returns_second_result() -> None:
    matcher = ExactTitleMatcher()
    results = [
        SearchResult(title="错误标题", detail_url="https://example.com/1", source_site="yidu"),
        SearchResult(title="论文标题", detail_url="https://example.com/2", source_site="yidu"),
    ]
    match = matcher.find_exact_match("论文标题", results)
    assert match is results[1]


def test_find_exact_match_returns_none() -> None:
    matcher = ExactTitleMatcher()
    results = [
        SearchResult(title="错误标题1", detail_url=None, source_site="yidu"),
        SearchResult(title="错误标题2", detail_url=None, source_site="yidu"),
    ]
    assert matcher.find_exact_match("论文标题", results) is None
