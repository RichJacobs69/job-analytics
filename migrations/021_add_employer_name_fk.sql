-- Migration 021: Add foreign key constraint on enriched_jobs.employer_name
-- Part of: Employer Metadata Architecture Cleanup
-- Date: 2026-01-04
-- Purpose: Enforce referential integrity between enriched_jobs and employer_metadata
--
-- IMPORTANT: This migration requires the auto-create logic in db_connection.py!
-- The insert_enriched_job() function calls ensure_employer_metadata() BEFORE inserting,
-- which auto-creates minimal employer entries for new companies. This allows:
-- - FK constraint enforces data integrity
-- - New companies can still be scraped (auto-created in employer_metadata first)
-- - Seed script later enriches with proper display_name from config files
--
-- Risk Level: LOW (with auto-create logic in place)
--
-- Rollback: ALTER TABLE enriched_jobs DROP CONSTRAINT fk_enriched_jobs_employer;

-- =============================================================================
-- STEP 1: Add foreign key constraint
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
-- STEP 2: Add index for FK performance (if not already indexed)
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_enriched_jobs_employer_name
ON enriched_jobs (employer_name);

-- =============================================================================
-- STEP 3: Add comment
-- =============================================================================

COMMENT ON CONSTRAINT fk_enriched_jobs_employer ON enriched_jobs IS
'Foreign key to employer_metadata. Ensures every job references a valid employer. New employers are auto-created by insert_enriched_job() via ensure_employer_metadata().';

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
