"""Build document payloads and metadata for RAGFlow."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .models import CaseSource, GuidelineSource, LiteratureSource


def normalize_list(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(items) if items else None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return raw
            return normalize_list(parsed)
        return raw
    return str(value)


def compact_metadata(data: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, bool):
            result[key] = "true" if value else "false"
        else:
            text = str(value).strip()
            if text:
                result[key] = text
    return result


def safe_filename(name: str, suffix: str) -> str:
    base = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name).strip(" ._")
    if not base:
        base = "document"
    if not base.lower().endswith(suffix.lower()):
        base = f"{base}{suffix}"
    return base


def literature_filename(source: LiteratureSource) -> str:
    title = source.title or source.matched_title or source.original_name or source.file_uuid
    return safe_filename(title, ".pdf")


def guideline_filename(source: GuidelineSource) -> str:
    title = source.title or source.matched_title or source.original_name or source.file_uuid
    return safe_filename(f"guideline_{title}", ".pdf")


def case_filename(source: CaseSource) -> str:
    title = source.literature_title or source.original_name or source.file_uuid
    return safe_filename(f"case_{title}", ".md")


def literature_metadata(source: LiteratureSource, domain: str) -> dict[str, str]:
    return compact_metadata(
        {
            "source_type": "literature",
            "domain": domain,
            "file_uuid": source.file_uuid,
            "title": source.title,
            "authors": normalize_list(source.authors),
            "keywords": normalize_list(source.keywords),
            "journal": source.journal,
            "pub_year": source.pub_year,
            "paper_type": source.paper_type,
            "source_site": source.source_site,
            "source_url": source.source_url,
            "minio_path": source.storage_path,
            "graph_node_type": "paper",
            "crawl_status": source.crawl_status,
        }
    )


def guideline_metadata(source: GuidelineSource, domain: str) -> dict[str, str]:
    return compact_metadata(
        {
            "source_type": "guideline",
            "domain": domain,
            "file_uuid": source.file_uuid,
            "title": source.title,
            "authors": normalize_list(source.authors),
            "keywords": normalize_list(source.keywords),
            "journal": source.journal,
            "pub_year": source.pub_year,
            "paper_type": source.paper_type,
            "source_site": source.source_site,
            "source_url": source.source_url,
            "minio_path": source.storage_path,
            "knowledge_role": "medical_guideline_validation",
            "crawl_status": source.crawl_status,
        }
    )


def case_metadata(source: CaseSource, domain: str) -> dict[str, str]:
    return compact_metadata(
        {
            "source_type": "case",
            "domain": domain,
            "file_uuid": source.file_uuid,
            "literature_title": source.literature_title,
            "age": source.age,
            "bmi": source.bmi,
            "western_diagnosis": source.western_diagnosis,
            "tcm_diagnosis": source.tcm_diagnosis,
            "treatment_principle": source.treatment_principle,
            "prescription": source.prescription,
            "efficacy": source.efficacy,
            "graph_node_type": "record",
        }
    )


def build_case_markdown(source: CaseSource) -> str:
    title = source.literature_title or source.original_name or source.file_uuid
    sections = [
        ("基本信息", [("年龄", source.age), ("BMI", source.bmi)]),
        (
            "病史与表现",
            [
                ("月经情况", source.menstruation),
                ("不孕情况", source.infertility),
                ("生活习惯", source.lifestyle),
                ("刻下症", source.present_symptoms),
                ("既往病史", source.medical_history),
            ],
        ),
        ("检查", [("生化检查", source.lab_tests), ("超声检查", source.ultrasound), ("复诊情况", source.followup)]),
        (
            "诊断与治疗",
            [
                ("西医病名诊断", source.western_diagnosis),
                ("中医证候诊断", source.tcm_diagnosis),
                ("治法", source.treatment_principle),
                ("方剂", source.prescription),
                ("针刺选穴", source.acupoints),
                ("辅助生殖技术", source.assisted_reproduction),
                ("西药", source.western_medicine),
            ],
        ),
        ("疗效与评价", [("疗效评价", source.efficacy), ("不良反应", source.adverse_reactions), ("按语/评价说明", source.commentary)]),
    ]

    lines = [f"# 病案：{title}", "", f"- file_uuid: {source.file_uuid}", ""]
    for heading, fields in sections:
        visible = [(label, value) for label, value in fields if value]
        if not visible:
            continue
        lines.append(f"## {heading}")
        for label, value in visible:
            lines.append(f"- {label}: {value}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def content_hash(content: bytes | str, metadata: dict[str, str] | None = None) -> str:
    hasher = hashlib.sha256()
    if isinstance(content, str):
        hasher.update(content.encode("utf-8"))
    else:
        hasher.update(content)
    if metadata:
        encoded = json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode("utf-8")
        hasher.update(encoded)
    return hasher.hexdigest()

