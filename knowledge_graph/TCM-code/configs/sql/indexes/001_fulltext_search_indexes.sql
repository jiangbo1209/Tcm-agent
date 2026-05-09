-- Reserved index migration for search scalability (10w+ records)
-- Apply manually after backup.

-- 1) Fulltext index for literature search.
ALTER TABLE paper
  ADD FULLTEXT INDEX ft_paper_search (title, keywords, abstract);

-- 2) Fulltext index for case search.
ALTER TABLE all_papers_records
  ADD FULLTEXT INDEX ft_record_search (`论文名称`, `中医证候诊断`, `西医病名诊断`);

-- Optional: prefix index for title sorting or LIKE fallback acceleration.
-- ALTER TABLE paper ADD INDEX idx_paper_title_prefix (title(191));
-- ALTER TABLE all_papers_records ADD INDEX idx_record_title_prefix (`论文名称`(191));
