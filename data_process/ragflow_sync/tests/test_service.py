from data_process.ragflow_sync.database import InMemorySyncRepository
from data_process.ragflow_sync.models import CaseSource, GuidelineSource, LiteratureSource
from data_process.ragflow_sync.service import RagflowSyncService


class FakeObjectStore:
    def __init__(self, objects=None):
        self.objects = objects or {"papers/u1.pdf": b"%PDF-1.4 test"}

    def get_object(self, object_name):
        return self.objects[object_name]


class FakeRagflowClient:
    def __init__(self):
        self.uploads = []
        self.metadata_updates = []
        self.parsed = []

    def upload_document(self, filename, content, content_type=None):
        doc_id = f"doc-{len(self.uploads) + 1}"
        self.uploads.append(
            {
                "document_id": doc_id,
                "filename": filename,
                "content": content,
                "content_type": content_type,
            }
        )
        return doc_id

    def update_document_metadata(self, document_id, meta_fields):
        self.metadata_updates.append((document_id, meta_fields))

    def parse_documents(self, document_ids):
        self.parsed.extend(document_ids)


def make_service(repository, ragflow=None, object_store=None):
    selected_client = ragflow or FakeRagflowClient()
    return RagflowSyncService(
        repository=repository,
        object_store=object_store or FakeObjectStore(),
        ragflow_clients={
            "literature": selected_client,
            "case": selected_client,
            "guideline": selected_client,
        },
        dataset_ids={
            "literature": "literature-dataset",
            "case": "case-dataset",
            "guideline": "guideline-dataset",
        },
        domain="DOR infertility",
        parse_after_upload=True,
    )


def test_sync_case_uploads_markdown_metadata_and_parses():
    repository = InMemorySyncRepository(
        cases=[
            CaseSource(
                file_uuid="c1",
                literature_title="DOR case",
                tcm_diagnosis="kidney deficiency and blood stasis",
            )
        ]
    )
    ragflow = FakeRagflowClient()
    service = make_service(repository, ragflow)

    results = service.sync("case")

    assert results[0].action == "parsed"
    assert results[0].stage == "parse"
    assert ragflow.uploads[0]["filename"].endswith(".md")
    assert b"kidney deficiency and blood stasis" in ragflow.uploads[0]["content"]
    assert ragflow.metadata_updates[0][1]["source_type"] == "case"
    assert ragflow.parsed == ["doc-1"]


def test_sync_literature_uploads_pdf_metadata_and_parses():
    repository = InMemorySyncRepository(
        literature=[
            LiteratureSource(
                file_uuid="u1",
                original_name="paper.pdf",
                storage_path="papers/u1.pdf",
                title="DOR paper",
            )
        ]
    )
    ragflow = FakeRagflowClient()
    service = make_service(repository, ragflow)

    results = service.sync("literature")

    assert results[0].action == "parsed"
    assert results[0].stage == "parse"
    assert ragflow.uploads[0]["content_type"] == "application/pdf"
    assert ragflow.metadata_updates[0][1]["source_type"] == "literature"
    assert ragflow.metadata_updates[0][1]["s3_path"] == "papers/u1.pdf"
    assert ragflow.parsed == ["doc-1"]


def test_sync_case_skips_unchanged_second_run():
    repository = InMemorySyncRepository(
        cases=[
            CaseSource(
                file_uuid="c1",
                literature_title="DOR case",
                tcm_diagnosis="kidney deficiency and blood stasis",
            )
        ]
    )
    ragflow = FakeRagflowClient()
    service = make_service(repository, ragflow)

    first = service.sync("case")
    second = service.sync("case")

    assert first[0].action == "parsed"
    assert second[0].action == "skipped"
    assert second[0].stage == "precheck"
    assert len(ragflow.uploads) == 1


def test_dry_run_does_not_touch_ragflow():
    repository = InMemorySyncRepository(
        literature=[
            LiteratureSource(
                file_uuid="u1",
                original_name="paper.pdf",
                storage_path="papers/u1.pdf",
            )
        ]
    )
    ragflow = FakeRagflowClient()
    service = make_service(repository, ragflow)

    results = service.sync("literature", dry_run=True)

    assert results[0].action == "skipped"
    assert results[0].stage == "dry_run"
    assert ragflow.uploads == []


def test_only_failed_filters_candidates():
    repository = InMemorySyncRepository(
        literature=[
            LiteratureSource(file_uuid="u1", original_name="paper1.pdf", storage_path="papers/u1.pdf"),
            LiteratureSource(file_uuid="u2", original_name="paper2.pdf", storage_path="papers/u1.pdf"),
        ]
    )
    repository.upsert_status(
        source_type="literature",
        file_uuid="u1",
        dataset_id="literature-dataset",
        document_id="doc-x",
        content_hash="hash-x",
        sync_status="failed",
        error_message="parse failed",
    )
    repository.upsert_status(
        source_type="literature",
        file_uuid="u2",
        dataset_id="literature-dataset",
        document_id="doc-y",
        content_hash="hash-y",
        sync_status="parsed",
    )

    ragflow = FakeRagflowClient()
    service = make_service(repository, ragflow)

    results = service.sync("literature", only_failed=True)

    assert len(results) == 1
    assert results[0].file_uuid == "u1"


def test_parse_failed_retry_reuses_existing_document():
    repository = InMemorySyncRepository(
        literature=[
            LiteratureSource(
                file_uuid="u1",
                original_name="paper.pdf",
                storage_path="papers/u1.pdf",
                title="DOR paper",
            )
        ]
    )
    repository.upsert_status(
        source_type="literature",
        file_uuid="u1",
        dataset_id="literature-dataset",
        document_id="existing-doc",
        content_hash=None,
        sync_status="failed",
        error_message="parse failed: previous parser error",
    )
    ragflow = FakeRagflowClient()
    service = make_service(repository, ragflow)

    results = service.sync("literature", only_failed=True)

    assert results[0].action == "parsed"
    assert results[0].document_id == "existing-doc"
    assert ragflow.uploads == []
    assert ragflow.metadata_updates == []
    assert ragflow.parsed == ["existing-doc"]


def test_empty_pdf_is_rejected_before_upload():
    repository = InMemorySyncRepository(
        literature=[
            LiteratureSource(
                file_uuid="u1",
                original_name="empty.pdf",
                storage_path="papers/empty.pdf",
                title="Empty PDF",
            )
        ]
    )
    ragflow = FakeRagflowClient()
    service = make_service(
        repository,
        ragflow,
        object_store=FakeObjectStore({"papers/empty.pdf": b""}),
    )

    results = service.sync("literature")

    assert results[0].action == "failed"
    assert results[0].stage == "upload"
    assert "S3 object is empty" in results[0].message
    assert ragflow.uploads == []


def test_sync_guideline_uploads_to_guideline_source():
    repository = InMemorySyncRepository(
        guidelines=[
            GuidelineSource(
                file_uuid="g1",
                original_name="guideline.pdf",
                storage_path="guidelines/g1.pdf",
                title="DOR guideline",
            )
        ]
    )
    ragflow = FakeRagflowClient()
    service = make_service(
        repository,
        ragflow,
        object_store=FakeObjectStore({"guidelines/g1.pdf": b"%PDF-1.4 guideline"}),
    )

    results = service.sync("guideline")

    assert results[0].action == "parsed"
    assert ragflow.uploads[0]["filename"].startswith("guideline_")
    assert ragflow.metadata_updates[0][1]["source_type"] == "guideline"
    assert ragflow.metadata_updates[0][1]["knowledge_role"] == "medical_guideline_validation"
