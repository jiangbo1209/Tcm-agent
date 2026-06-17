from data_process.ragflow_sync.document_builder import (
    build_case_markdown,
    case_metadata,
    content_hash,
    literature_filename,
    literature_metadata,
    normalize_list,
)
from data_process.ragflow_sync.models import CaseSource, LiteratureSource


def test_normalize_list_handles_json_strings():
    assert normalize_list('["DOR", "不孕"]') == "DOR, 不孕"
    assert normalize_list(["A", "B"]) == "A, B"
    assert normalize_list("") is None


def test_literature_metadata_is_compact_and_keeps_domain():
    source = LiteratureSource(
        file_uuid="u1",
        original_name="paper.pdf",
        storage_path="papers/u1.pdf",
        title="DOR不孕研究",
        authors=["张三", "李四"],
        keywords=["DOR", "不孕"],
        pub_year="2024",
    )

    metadata = literature_metadata(source, "DOR infertility")

    assert metadata["source_type"] == "literature"
    assert metadata["domain"] == "DOR infertility"
    assert metadata["file_uuid"] == "u1"
    assert metadata["authors"] == "张三, 李四"
    assert metadata["keywords"] == "DOR, 不孕"
    assert metadata["graph_node_type"] == "paper"
    assert "journal" not in metadata
    assert literature_filename(source).endswith(".pdf")


def test_case_markdown_and_metadata_include_medical_fields():
    source = CaseSource(
        file_uuid="c1",
        literature_title="DOR病案分析",
        age="35岁",
        western_diagnosis="卵巢储备功能下降",
        tcm_diagnosis="肾虚血瘀",
        treatment_principle="补肾活血",
        prescription="左归丸加减",
        efficacy="AMH改善",
    )

    markdown = build_case_markdown(source)
    metadata = case_metadata(source, "DOR infertility")

    assert "# 病案：DOR病案分析" in markdown
    assert "- 西医病名诊断: 卵巢储备功能下降" in markdown
    assert "- 中医证候诊断: 肾虚血瘀" in markdown
    assert metadata["source_type"] == "case"
    assert metadata["tcm_diagnosis"] == "肾虚血瘀"
    assert metadata["graph_node_type"] == "record"


def test_content_hash_changes_with_metadata():
    base = content_hash("hello", {"a": "1"})
    changed = content_hash("hello", {"a": "2"})
    assert base != changed

