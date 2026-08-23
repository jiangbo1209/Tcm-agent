from app.core.formatting import parse_listish
from app.repositories.search_repo import SearchRepository


def test_split_listish_facet_accepts_plain_list():
    assert parse_listish(["a", "b"]) == ["a", "b"]


def test_split_listish_facet_parses_json_string():
    assert parse_listish('["x","y"]') == ["x", "y"]


def test_split_listish_facet_splits_cjk_separators():
    assert parse_listish("a、b，c") == ["a", "b", "c"]


def test_split_listish_facet_none_returns_empty_list():
    assert parse_listish(None) == []


def test_normalize_filter_values_dedupes():
    assert SearchRepository._normalize_filter_values(["a", "a", "b"]) == ["a", "b"]


def test_normalize_paper_type_journal():
    assert SearchRepository._normalize_paper_type("journal") == "期刊论文"


def test_normalize_paper_type_master():
    assert SearchRepository._normalize_paper_type("master") == "学位论文"


def test_normalize_paper_type_none_is_none():
    assert SearchRepository._normalize_paper_type(None) is None
