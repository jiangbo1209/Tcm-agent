from __future__ import annotations

import pytest

from app.services.filename_cleaner import FilenameCleaner


@pytest.fixture()
def cleaner() -> FilenameCleaner:
    return FilenameCleaner()


def test_remove_pdf_suffix(cleaner: FilenameCleaner) -> None:
    assert cleaner.clean("论文标题.pdf") == "论文标题"


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("001_论文标题.pdf", "论文标题"),
        ("001-论文标题.pdf", "论文标题"),
        ("001.论文标题.pdf", "论文标题"),
        ("001 论文标题.pdf", "论文标题"),
        ("1. 论文标题.pdf", "论文标题"),
        ("1、论文标题.pdf", "论文标题"),
    ],
)
def test_remove_number_prefix(cleaner: FilenameCleaner, file_name: str, expected: str) -> None:
    assert cleaner.clean(file_name) == expected


def test_remove_square_bracket_number(cleaner: FilenameCleaner) -> None:
    assert cleaner.clean("[1]论文标题.pdf") == "论文标题"
    assert cleaner.clean("【1】论文标题.pdf") == "论文标题"


def test_remove_chinese_parentheses_number(cleaner: FilenameCleaner) -> None:
    assert cleaner.clean("（1）论文标题.pdf") == "论文标题"
    assert cleaner.clean("(1)论文标题.pdf") == "论文标题"


def test_remove_download_marker(cleaner: FilenameCleaner) -> None:
    assert cleaner.clean("论文标题_下载.pdf") == "论文标题"
    assert cleaner.clean("论文标题-CNKI.pdf") == "论文标题"


def test_remove_copy_marker(cleaner: FilenameCleaner) -> None:
    assert cleaner.clean("论文标题（副本）.pdf") == "论文标题"


def test_remove_outer_book_title_marks(cleaner: FilenameCleaner) -> None:
    assert cleaner.clean("《论文标题》.pdf") == "论文标题"
    assert cleaner.clean("<论文标题>.pdf") == "论文标题"


def test_keep_valid_punctuation(cleaner: FilenameCleaner) -> None:
    title = "基于AI的医学图像分割：方法、挑战与展望"
    assert cleaner.clean(f"{title}.pdf") == title


def test_keep_subtitle(cleaner: FilenameCleaner) -> None:
    title = "中医药治疗不孕症研究——基于真实世界数据"
    assert cleaner.clean(f"{title}.pdf") == title


def test_empty_after_clean_raises(cleaner: FilenameCleaner) -> None:
    with pytest.raises(ValueError):
        cleaner.clean("001_下载.pdf")


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("中西医结合治疗输卵管功能障碍性不孕的Meta分析_黄金华.pdf", "中西医结合治疗输卵管功能障碍性不孕的Meta分析"),
        ("输卵管积水相关不孕症诊治中国专家共识（2023年版）_张颐.pdf", "输卵管积水相关不孕症诊治中国专家共识（2023年版）"),
        ("清心滋肾汤对PCOS不孕症患者情绪调节及辅助生殖助孕结局的临床观察_独文晨.pdf", "清心滋肾汤对PCOS不孕症患者情绪调节及辅助生殖助孕结局的临床观察"),
    ],
)
def test_remove_trailing_chinese_author(cleaner: FilenameCleaner, file_name: str, expected: str) -> None:
    assert cleaner.clean(file_name) == expected


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("卵巢储备功能减退不孕中医药联合辅助生殖临床诊疗专家共识 (1).pdf", "卵巢储备功能减退不孕中医药联合辅助生殖临床诊疗专家共识"),
        ("论文标题(2).pdf", "论文标题"),
        ("论文标题（3）.pdf", "论文标题"),
    ],
)
def test_remove_trailing_duplicate_marker(cleaner: FilenameCleaner, file_name: str, expected: str) -> None:
    assert cleaner.clean(file_name) == expected


def test_remove_compound_trailing_artifacts(cleaner: FilenameCleaner) -> None:
    assert cleaner.clean("论文标题_作者 (1).pdf") == "论文标题"


def test_keep_non_chinese_underscore_suffix(cleaner: FilenameCleaner) -> None:
    """Don't strip _v1 / _final / _补充材料 etc. — only pure 2-4 Chinese-char suffixes."""
    assert cleaner.clean("论文标题_v1.pdf") == "论文标题_v1"
    assert cleaner.clean("论文标题_附录1.pdf") == "论文标题_附录1"
