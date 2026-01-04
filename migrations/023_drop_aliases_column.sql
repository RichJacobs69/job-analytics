-- Migration 023: Drop aliases column from employer_metadata
-- Date: 2026-01-04
-- Purpose: Remove unused aliases column to simplify schema
--
-- The aliases column was designed for fuzzy matching of employer name variations,
-- but with the FK constraint on enriched_jobs.employer_name, all employer names
-- are now normalized to lowercase canonical form. Aliases are not queried anywhere.
--
-- Risk Level: LOW
-- - Column is not used in any queries or application code
-- - Data loss is acceptable (aliases were just duplicates of canonical_name)

-- =============================================================================
-- STEP 1: Drop the aliases column
-- =============================================================================

ALTER TABLE employer_metadata DROP COLUMN IF EXISTS aliases;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Verify column is gone
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'employer_metadata'
ORDER BY ordinal_position;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- ALTER TABLE employer_metadata ADD COLUMN aliases TEXT[] DEFAULT '{}';
