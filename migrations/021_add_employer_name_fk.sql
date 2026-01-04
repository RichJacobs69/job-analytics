-- Migration 021: Add foreign key constraint on enriched_jobs.employer_name
-- Part of: Employer Metadata Architecture Cleanup
-- Date: 2026-01-04
-- Purpose: Enforce referential integrity between enriched_jobs and employer_metadata
--
-- Prerequisites (must be done before running this migration):
-- 1. All employer_name values in enriched_jobs must be lowercase (normalized)
-- 2. All employers must exist in employer_metadata.canonical_name
-- 3. Agency jobs (is_agency=true or blacklisted employers) should be deleted
--
-- This migration adds a FK constraint so that:
-- - Every job must reference a valid employer in employer_metadata
-- - No orphan jobs can exist without employer metadata
-- - Deletes from employer_metadata are restricted (cannot delete if jobs exist)
--
-- Risk Level: MEDIUM
-- - Constraint will fail if any employer_name doesn't exist in employer_metadata
-- - Run verification queries before applying
--
-- Rollback: DROP CONSTRAINT fk_enriched_jobs_employer

-- =============================================================================
-- STEP 0: Verification queries (run these first!)
-- =============================================================================

-- Check if any employer_name values are not lowercase
-- Expected: 0 rows
-- SELECT DISTINCT employer_name
-- FROM enriched_jobs
-- WHERE employer_name != LOWER(TRIM(employer_name))
-- LIMIT 10;

-- Check if any employers are missing from employer_metadata
-- Expected: 0 rows
-- SELECT DISTINCT LOWER(TRIM(employer_name)) as canonical
-- FROM enriched_jobs ej
-- WHERE NOT EXISTS (
--     SELECT 1 FROM employer_metadata em
--     WHERE em.canonical_name = LOWER(TRIM(ej.employer_name))
-- )
-- LIMIT 10;

-- =============================================================================
-- STEP 1: Rename column to employer_canonical for clarity (optional but recommended)
-- =============================================================================
-- Note: Keeping as employer_name for now to minimize breaking changes.
-- The view jobs_with_employer_context exposes employer_canonical for JOINs.

-- =============================================================================
-- STEP 2: Add foreign key constraint
-- =============================================================================

ALTER TABLE enriched_jobs
ADD CONSTRAINT fk_enriched_jobs_employer
FOREIGN KEY (employer_name)
REFERENCES employer_metadata (canonical_name)
ON UPDATE CASCADE
ON DELETE RESTRICT;

-- ON UPDATE CASCADE: If canonical_name changes, update enriched_jobs automatically
-- ON DELETE RESTRICT: Prevent deleting employers that have jobs (must delete jobs first)

-- =============================================================================
-- STEP 3: Add index for FK performance (if not already indexed)
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_enriched_jobs_employer_name
ON enriched_jobs (employer_name);

-- =============================================================================
-- STEP 4: Add comment
-- =============================================================================

COMMENT ON CONSTRAINT fk_enriched_jobs_employer ON enriched_jobs IS
'Foreign key to employer_metadata. Ensures every job references a valid employer. employer_name must be lowercase (canonical).';

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Verify constraint exists
SELECT
    tc.constraint_name,
    tc.constraint_type,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_name = 'fk_enriched_jobs_employer';

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- ALTER TABLE enriched_jobs DROP CONSTRAINT fk_enriched_jobs_employer;
-- DROP INDEX IF EXISTS idx_enriched_jobs_employer_name;
