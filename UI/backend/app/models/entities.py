"""Database table models and column lists for the UI backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class CoreFile:
    file_uuid: str
    original_name: str
    storage_path: str
    file_type: str = "pdf"
    upload_time: datetime | None = None
    status_metadata: bool = False
    status_case: bool = False


@dataclass(slots=True)
class LitMetadata:
    file_uuid: str
    original_name: str
    storage_path: str
    cleaned_title: str
    title: str
    source_site: str
    matched_title: str
    crawl_status: str
    id: int | None = None
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None
    keywords: list[str] = field(default_factory=list)
    paper_type: str | None = None
    source_url: str | None = None
    journal: str | None = None
    pub_year: str | None = None
    is_exact_match: bool = True
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class MedCase:
    file_uuid: str
    id: int | None = None
    age: str | None = None
    bmi: str | None = None
    menstruation: str | None = None
    infertility: str | None = None
    lifestyle: str | None = None
    present_symptoms: str | None = None
    medical_history: str | None = None
    lab_tests: str | None = None
    ultrasound: str | None = None
    followup: str | None = None
    western_diagnosis: str | None = None
    tcm_diagnosis: str | None = None
    treatment_principle: str | None = None
    prescription: str | None = None
    acupoints: str | None = None
    assisted_reproduction: str | None = None
    western_medicine: str | None = None
    efficacy: str | None = None
    adverse_reactions: str | None = None
    commentary: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Node:
    id: str
    node_type: str
    title: str
    metric_value: int | None = None
    top_k_value: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Edge:
    id: str
    source_id: str
    target_id: str
    edge_type: str
    similarity_score: float | None = None
    raw_score: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


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
