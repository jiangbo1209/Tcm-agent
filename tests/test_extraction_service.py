from __future__ import annotations

from models.schemas import PaperMetadata
from services.extraction_service import FAILURE_ACTIONS, ExtractionService


def test_missing_metadata_message_reports_abstract() -> None:
    metadata = PaperMetadata(
        title="title",
        authors=["author"],
        abstract=None,
        keywords=["keyword"],
        paper_type="journal",
        source_site="nstl",
        source_url="https://example.com",
    )

    assert ExtractionService._missing_metadata_message(metadata) == "Missing metadata fields: abstract"


def test_complete_metadata_has_no_missing_message() -> None:
    metadata = PaperMetadata(
        title="title",
        authors=["author"],
        abstract="abstract",
        keywords=["keyword"],
        paper_type="journal",
        source_site="nstl",
        source_url="https://example.com",
    )

    assert ExtractionService._missing_metadata_message(metadata) is None


def test_missing_metadata_failure_is_preserved_over_later_no_result() -> None:
    reason, message = ExtractionService._choose_failure(
        "missing_metadata_fields",
        "Missing metadata fields: abstract",
        "no_result",
        "cnki returned no search results",
    )

    assert reason == "missing_metadata_fields"
    assert message == "Missing metadata fields: abstract"
    assert FAILURE_ACTIONS[reason] == "complete_metadata"
