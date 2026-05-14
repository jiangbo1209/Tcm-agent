"""Chinese key → English column mapping and Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Chinese key names from LLM output → English column names in med_case table
FIELD_MAP: dict[str, str] = {
    "年齡": "age",
    "BMI": "bmi",
    "月经情况": "menstruation",
    "不孕情况": "infertility",
    "生活习惯": "lifestyle",
    "刻下症": "present_symptoms",
    "既往病史": "medical_history",
    "生化检查": "lab_tests",
    "超声检查": "ultrasound",
    "复诊情况": "followup",
    "西医病名诊断": "western_diagnosis",
    "中医证候诊断": "tcm_diagnosis",
    "治法": "treatment_principle",
    "方剂": "prescription",
    "针刺选穴": "acupoints",
    "辅助生殖技术": "assisted_reproduction",
    "西药": "western_medicine",
    "疔效评价": "efficacy",
    "不良反应": "adverse_reactions",
    "按语/评价说明": "commentary",
}


def map_chinese_to_english(record: dict) -> dict:
    """Convert LLM output (Chinese keys) to DB column names (English)."""
    mapped = {}
    for cn_key, value in record.items():
        en_key = FIELD_MAP.get(cn_key)
        if en_key:
            mapped[en_key] = value
    return mapped


class ExtractionResult(BaseModel):
    """Result of a single PDF extraction."""
    file_uuid: str
    original_name: str
    success: bool
    error: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    extra_fields: list[str] = Field(default_factory=list)


class ExtractionSummary(BaseModel):
    """Summary of a batch extraction run."""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[ExtractionResult] = Field(default_factory=list)
