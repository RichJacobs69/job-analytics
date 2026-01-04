-- Migration 019: Rename employer_fill_stats.employer_name to canonical_name
-- Part of: Employer Metadata Architecture Cleanup
-- Date: 2026-01-04
-- Purpose: Align employer_fill_stats with employer_metadata naming convention
--
-- This migration:
-- 1. Renames employer_name -> canonical_name for consistency with employer_metadata
-- 2. Updates index name to match
-- 3. Updates table comments
--
-- The canonical_name column stores lowercase employer names, matching
-- employer_metadata.canonical_name for JOINs.
--
-- Risk Level: LOW
-- - Column rename only, no data changes
-- - Existing data is already lowercase
-- - API/pipeline code will be updated to use new column name

-- =============================================================================
-- STEP 1: Rename column
-- =============================================================================

ALTER TABLE employer_fill_stats
RENAME COLUMN employer_name TO canonical_name;

-- =============================================================================
-- STEP 2: Update index
-- =============================================================================

-- Drop old index
DROP INDEX IF EXISTS idx_employer_fill_stats_name;

-- Create new index with matching name
CREATE INDEX IF NOT EXISTS idx_employer_fill_stats_canonical
ON employer_fill_stats (canonical_name);

-- =============================================================================
-- STEP 3: Update comments
-- =============================================================================

COMMENT ON COLUMN employer_fill_stats.canonical_name IS 'Lowercase employer name, matches employer_metadata.canonical_name for JOINs';

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify column renamed
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'employer_fill_stats'
ORDER BY ordinal_position;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- ALTER TABLE employer_fill_stats RENAME COLUMN canonical_name TO employer_name;
-- DROP INDEX IF EXISTS idx_employer_fill_stats_canonical;
-- CREATE INDEX idx_employer_fill_stats_name ON employer_fill_stats (employer_name);
