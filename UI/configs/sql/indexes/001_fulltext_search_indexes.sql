-- Reserved index migration for search scalability (10w+ records)
-- PostgreSQL 16+ (GIN / tsvector)

-- 1) Fulltext index for literature search.
CREATE INDEX IF NOT EXISTS idx_lit_metadata_search
  ON lit_metadata
  USING GIN (to_tsvector('simple',
    COALESCE(title, '') || ' ' ||
    COALESCE(keywords::text, '') || ' ' ||
    COALESCE(abstract, '')
  ));

-- 2) Fulltext index for case search.
CREATE INDEX IF NOT EXISTS idx_med_case_search
  ON med_case
  USING GIN (to_tsvector('simple',
    COALESCE(tcm_diagnosis, '') || ' ' ||
    COALESCE(western_diagnosis, '')
  ));

-- Optional: prefix index for title sorting or LIKE fallback acceleration.
-- CREATE INDEX IF NOT EXISTS idx_lit_metadata_title_prefix ON lit_metadata (title);
