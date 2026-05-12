-- Migration: 001_core_file
-- Creates the CORE_FILE table for PDF upload tracking
-- Compatible with PostgreSQL 16 + pgvector

CREATE TABLE IF NOT EXISTS core_file (
    file_uuid       VARCHAR(36)    NOT NULL PRIMARY KEY,
    original_name   VARCHAR(512)   NOT NULL,
    storage_path    VARCHAR(1024)  NOT NULL,
    file_type       VARCHAR(32)    NOT NULL DEFAULT 'pdf',
    upload_time     TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    status_metadata BOOLEAN        NOT NULL DEFAULT FALSE,
    status_case     BOOLEAN        NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE  core_file                IS 'File core table mapping uploaded documents to MinIO storage';
COMMENT ON COLUMN core_file.file_uuid       IS 'Primary key, auto-generated UUID4';
COMMENT ON COLUMN core_file.original_name   IS 'Original filename from upload';
COMMENT ON COLUMN core_file.storage_path    IS 'Object path within MinIO bucket';
COMMENT ON COLUMN core_file.file_type       IS 'File extension/MIME classification';
COMMENT ON COLUMN core_file.upload_time     IS 'Timestamp of upload';
COMMENT ON COLUMN core_file.status_metadata IS 'Whether literature metadata extraction is complete';
COMMENT ON COLUMN core_file.status_case     IS 'Whether case data extraction is complete';

-- Partial indexes: optimized for downstream polling of unprocessed records
CREATE INDEX IF NOT EXISTS idx_core_file_status_meta ON core_file (status_metadata) WHERE status_metadata = FALSE;
CREATE INDEX IF NOT EXISTS idx_core_file_status_case  ON core_file (status_case)     WHERE status_case = FALSE;
CREATE INDEX IF NOT EXISTS idx_core_file_upload_time  ON core_file (upload_time DESC);
