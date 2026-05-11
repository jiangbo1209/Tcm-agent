"""Core domain constants and simple model utilities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Literature:
    file_name: str
    title: str
    authors: str | None = None
    abstract: str | None = None
    keywords: str | None = None
    journal: str | None = None
    pub_year: int | None = None
    paper_type: str | None = None
    file_key: str | None = None


PAPER_COLUMNS = [
    "file_name",
    "file_key",
    "title",
    "authors",
    "abstract",
    "keywords",
    "journal",
    "pub_year",
    "paper_type",
    "created_at",
    "updated_at",
]

RECORD_COLUMNS = [
    "论文名称",
    "年齡",
    "BMI",
    "月经情况",
    "不孕情况",
    "生活习惯",
    "刻下症",
    "既往病史",
    "生化检查",
    "超声检查",
    "复诊情况",
    "西医病名诊断",
    "中医证候诊断",
    "治法",
    "方剂",
    "针刺选穴",
    "辅助生殖技术",
    "西药",
    "疔效评价",
    "不良反应",
    "按语/评价说明",
]
