from sqlalchemy import create_engine

from data_process.ragflow_sync.database import RagflowSyncRepository


def test_repository_status_uses_orm_model_roundtrip():
    engine = create_engine("sqlite:///:memory:")
    repository = RagflowSyncRepository(engine)

    repository.ensure_schema()
    repository.upsert_status(
        source_type="case",
        file_uuid="case-1",
        dataset_id="case-dataset",
        document_id="doc-1",
        content_hash="hash-1",
        sync_status="parsed",
    )

    status = repository.get_status("case", "case-1", "case-dataset")

    assert status is not None
    assert status.document_id == "doc-1"
    assert status.content_hash == "hash-1"
    assert status.sync_status == "parsed"
