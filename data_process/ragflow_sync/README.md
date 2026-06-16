# RAGFlow Sync

Synchronize local TCM literature and case data into a RAGFlow dataset.

## What It Does

- Reads literature rows from `core_file` + `lit_metadata`.
- Downloads literature PDFs from MinIO.
- Reads case rows from `med_case` and renders each case as Markdown.
- Uploads documents to RAGFlow.
- Writes `meta_fields` to each RAGFlow document.
- Optionally triggers RAGFlow parsing.
- Stores sync state in `ragflow_sync_status` to avoid duplicate uploads.

## Environment

Add these values to the project `.env`:

```env
RAGFLOW_BASE_URL=http://127.0.0.1:9380
RAGFLOW_API_KEY=
RAGFLOW_DATASET_ID=
RAGFLOW_PARSE_AFTER_UPLOAD=true
RAGFLOW_DOMAIN=DOR infertility
```

The sync script also uses the existing PostgreSQL and MinIO settings:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
POSTGRES_DB=papers_records

MINIO_ENDPOINT=localhost:9000
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=
MINIO_BUCKET_NAME=tcm-documents
```

## Install

```bash
pip install -r data_process/ragflow_sync/requirements.txt
```

## Usage

Preview records without uploading:

```bash
python -m data_process.ragflow_sync --source all --limit 5 --dry-run
```

Sync literature PDFs:

```bash
python -m data_process.ragflow_sync --source literature --limit 20
```

Sync case Markdown documents:

```bash
python -m data_process.ragflow_sync --source case --limit 20
```

Upload without triggering RAGFlow parsing:

```bash
python -m data_process.ragflow_sync --source all --no-parse
```

Force re-upload even if a parsed sync status exists:

```bash
python -m data_process.ragflow_sync --source all --force
```

