"""format_list_field 五分支直接用例（None / 集合 / JSON 字符串 / 字符串透传 / str 回退）。"""

from app.core.formatting import format_list_field


def test_format_list_field_none_returns_none():
    assert format_list_field(None) is None


def test_format_list_field_list_joins_with_sep():
    assert format_list_field(["a", "b"], sep="、") == "a、b"


def test_format_list_field_json_string_parsed_and_joined():
    assert format_list_field('["x","y"]', sep=", ") == "x, y"


def test_format_list_field_plain_string_passthrough():
    assert format_list_field("plain text") == "plain text"


def test_format_list_field_other_type_falls_back_to_str():
    assert format_list_field(123) == "123"
