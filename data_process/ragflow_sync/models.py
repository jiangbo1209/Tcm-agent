"""Data models used by the RAGFlow synchronization pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

SourceType = Literal["literature", "case"]


@dataclass(slots=True)
class LiteratureSource:
    file_uuid: str
    original_name: str
    storage_path: str
    title: str | None = None
    authors: Any = None
    abstract: str | None = None
    keywords: Any = None
    paper_type: str | None = None
    source_site: str | None = None
    source_url: str | None = None
    journal: str | None = None
    pub_year: str | None = None
    matched_title: str | None = None
    crawl_status: str | None = None


@dataclass(slots=True)
class CaseSource:
    file_uuid: str
    literature_title: str | None = None
    original_name: str | None = None
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


@dataclass(slots=True)
class SyncStatus:
    source_type: SourceType
    file_uuid: str
    dataset_id: str
    document_id: str | None
    content_hash: str | None
    sync_status: str
    error_message: str | None = None
    synced_at: datetime | None = None


@dataclass(slots=True)
class SyncResult:
    source_type: SourceType
    file_uuid: str
    action: str
    document_id: str | None = None
    message: str | None = None

