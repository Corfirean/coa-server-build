-- Older repacks created this key column without a default. The release schema
-- expects DEFAULT 0. Change only that known definition, without changing rows,
-- keys, column types or unrelated custom defaults. Safe to run repeatedly.
SET @coa_fix_display_default = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'creature_display_preset'
      AND COLUMN_NAME = 'display_id' AND COLUMN_TYPE = 'int unsigned'
      AND IS_NULLABLE = 'NO' AND COLUMN_DEFAULT IS NULL
);
SET @coa_fix_display_sql = IF(@coa_fix_display_default = 1,
    'ALTER TABLE `creature_display_preset` ALTER COLUMN `display_id` SET DEFAULT 0',
    'SELECT 1');
PREPARE coa_fix_display_stmt FROM @coa_fix_display_sql;
EXECUTE coa_fix_display_stmt;
DEALLOCATE PREPARE coa_fix_display_stmt;
