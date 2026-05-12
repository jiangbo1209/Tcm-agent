from __future__ import annotations

from app.models.schemas import DatasetFile, FailedRecordCreate, PaperMetadata, SearchResult


def test_dataset_file_schema() -> None:
    data = DatasetFile(file_name="a.pdf", file_path="/tmp/a.pdf", suffix=".pdf")
    assert data.file_name == "a.pdf"


def test_search_result_schema() -> None:
    data = SearchResult(
        title="论文标题",
        detail_url="https://example.com/detail",
        source_site="yidu",
        raw_data={"rank": 1},
    )
    assert data.raw_data == {"rank": 1}


def test_paper_metadata_schema() -> None:
    data = PaperMetadata(
        title="论文标题",
        authors=["张三", "李四"],
        abstract="摘要",
        keywords=["关键词1", "关键词2"],
        paper_type="journal",
        source_site="nstl",
        source_url="https://example.com/detail",
    )
    assert data.authors == ["张三", "李四"]
    assert data.keywords == ["关键词1", "关键词2"]


def test_failed_record_create_schema() -> None:
    data = FailedRecordCreate(
        file_name="a.pdf",
        file_path="/tmp/a.pdf",
        cleaned_title="论文标题",
        attempted_sites=["yidu", "nstl"],
        failure_reason="title_not_exact_match",
        error_message="no exact title",
        suggested_action="manual_check",
    )
    assert data.attempted_sites == ["yidu", "nstl"]
