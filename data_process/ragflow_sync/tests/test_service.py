from data_process.ragflow_sync.database import InMemorySyncRepository
from data_process.ragflow_sync.models import CaseSource, LiteratureSource
from data_process.ragflow_sync.service import RagflowSyncService


class FakeObjectStore:
    def __init__(self):
        self.objects = {"papers/u1.pdf": b"%PDF-1.4 test"}

    def get_object(self, object_name):
        return self.objects[object_name]


class FakeRagflowClient:
    def __init__(self):
        self.uploads = []
        self.metadata_updates = []
        self.parsed = []

    def upload_document(self, filename, content, content_type):
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


def make_service(repository, ragflow=None):
    return RagflowSyncService(
        repository=repository,
        object_store=FakeObjectStore(),
        ragflow_client=ragflow or FakeRagflowClient(),
        dataset_id="dataset-1",
        domain="DOR infertility",
        parse_after_upload=True,
    )


def test_sync_case_uploads_markdown_metadata_and_parses():
    repository = InMemorySyncRepository(
        cases=[
            CaseSource(
                file_uuid="c1",
                literature_title="DOR病案",
                tcm_diagnosis="肾虚血瘀",
            )
        ]
    )
    ragflow = FakeRagflowClient()
    service = make_service(repository, ragflow)

    results = service.sync("case")

    assert results[0].action == "parsed"
    assert ragflow.uploads[0]["filename"].endswith(".md")
    assert "肾虚血瘀".encode("utf-8") in ragflow.uploads[0]["content"]
    assert ragflow.metadata_updates[0][1]["source_type"] == "case"
    assert ragflow.parsed == ["doc-1"]


def test_sync_literature_uploads_pdf_metadata_and_parses():
    repository = InMemorySyncRepository(
        literature=[
            LiteratureSource(
                file_uuid="u1",
                original_name="paper.pdf",
                storage_path="papers/u1.pdf",
                title="DOR文献",
            )
        ]
    )
    ragflow = FakeRagflowClient()
    service = make_service(repository, ragflow)

    results = service.sync("literature")

    assert results[0].action == "parsed"
    assert ragflow.uploads[0]["content_type"] == "application/pdf"
    assert ragflow.metadata_updates[0][1]["source_type"] == "literature"
    assert ragflow.metadata_updates[0][1]["minio_path"] == "papers/u1.pdf"
    assert ragflow.parsed == ["doc-1"]


def test_sync_case_skips_unchanged_second_run():
    repository = InMemorySyncRepository(
        cases=[
            CaseSource(
                file_uuid="c1",
                literature_title="DOR病案",
                tcm_diagnosis="肾虚血瘀",
            )
        ]
    )
    ragflow = FakeRagflowClient()
    service = make_service(repository, ragflow)

    first = service.sync("case")
    second = service.sync("case")

    assert first[0].action == "parsed"
    assert second[0].action == "skipped"
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

    assert results[0].action == "would_upload"
    assert ragflow.uploads == []

