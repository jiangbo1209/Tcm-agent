-- Migration: add literature file_key
-- Safe to run multiple times on MySQL 5.7+

SET @ddl_add_file_key := (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE paper ADD COLUMN file_key VARCHAR(512) NULL COMMENT ''MinIO object key'' AFTER file_name',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'paper'
    AND COLUMN_NAME = 'file_key'
);

PREPARE stmt_add_file_key FROM @ddl_add_file_key;
EXECUTE stmt_add_file_key;
DEALLOCATE PREPARE stmt_add_file_key;
