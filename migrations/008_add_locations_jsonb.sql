-- Migration 008: Add locations JSONB column to enriched_jobs
-- Part of: Global Location Expansion Epic - Phase 1
-- Date: 2025-12-18
-- Purpose: Replace city_code enum with flexible locations JSONB array
--
-- This migration:
-- 1. Adds locations JSONB column (nullable initially for gradual migration)
-- 2. Creates GIN index for efficient JSONB queries
-- 3. Keeps city_code column for backward compatibility during transition
--
-- Risk Level: LOW
-- - Non-destructive (only adds column + index)
-- - Existing data preserved
-- - city_code remains functional until migration complete

-- =============================================================================
-- STEP 1: Add locations column
-- =============================================================================

ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS locations JSONB;

COMMENT ON COLUMN enriched_jobs.locations IS 'Array of location objects. Each object has type (city/country/region/remote), country_code, city, region, scope. Replaces city_code.';

-- =============================================================================
-- STEP 2: Create GIN index for efficient JSONB queries
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_enriched_jobs_locations
ON enriched_jobs USING GIN (locations);

-- =============================================================================
-- STEP 3: Set default for new records (empty array)
-- =============================================================================

ALTER TABLE enriched_jobs
ALTER COLUMN locations SET DEFAULT '[]'::jsonb;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify column exists
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'enriched_jobs' AND column_name = 'locations';

-- Verify index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'enriched_jobs' AND indexname = 'idx_enriched_jobs_locations';

-- Check current state (all should be NULL before backfill)
SELECT
    COUNT(*) AS total_jobs,
    COUNT(locations) AS jobs_with_locations,
    COUNT(*) - COUNT(locations) AS jobs_without_locations
FROM enriched_jobs;

-- =============================================================================
-- EXAMPLE QUERIES (for reference after backfill)
-- =============================================================================

-- Filter by specific city
-- SELECT * FROM enriched_jobs
-- WHERE locations @> '[{"city": "london"}]';

-- Filter by country
-- SELECT * FROM enriched_jobs
-- WHERE locations @> '[{"country_code": "US"}]';

-- Filter by remote scope
-- SELECT * FROM enriched_jobs
-- WHERE locations @> '[{"type": "remote", "scope": "global"}]';

-- Count jobs by city
-- SELECT
--     elem->>'city' AS city,
--     COUNT(*) AS job_count
-- FROM enriched_jobs, jsonb_array_elements(locations) AS elem
-- WHERE elem->>'type' = 'city'
-- GROUP BY elem->>'city'
-- ORDER BY job_count DESC;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- DROP INDEX IF EXISTS idx_enriched_jobs_locations;
-- ALTER TABLE enriched_jobs DROP COLUMN IF EXISTS locations;
