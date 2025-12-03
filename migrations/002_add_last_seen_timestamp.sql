-- Migration 002: Add last_seen timestamp to raw_jobs
-- Purpose: Track when jobs were last scraped (vs first discovered)
-- Date: 2025-12-03
-- Status: Pending execution

-- Step 1: Add last_seen column (default to scraped_at for existing records)
ALTER TABLE raw_jobs
ADD COLUMN last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Step 2: For existing records, set last_seen = scraped_at (one-time backfill)
UPDATE raw_jobs
SET last_seen = scraped_at
WHERE last_seen IS NULL;

-- Step 3: Make last_seen NOT NULL now that all records have values
ALTER TABLE raw_jobs
ALTER COLUMN last_seen SET NOT NULL;

-- Step 4: Add index for resume capability queries
CREATE INDEX idx_raw_jobs_source_last_seen
ON raw_jobs(source, last_seen);

-- Step 5: Add comment for documentation
COMMENT ON COLUMN raw_jobs.scraped_at IS 'First seen timestamp - when job was first discovered (immutable)';
COMMENT ON COLUMN raw_jobs.last_seen IS 'Last seen timestamp - when job was last scraped/verified (updated on every encounter)';

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- 1. Check column exists and has values
SELECT
    COUNT(*) as total_records,
    COUNT(last_seen) as records_with_last_seen,
    COUNT(*) - COUNT(last_seen) as null_last_seen
FROM raw_jobs;
-- Expected: null_last_seen = 0

-- 2. Verify index was created
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'raw_jobs'
AND indexname = 'idx_raw_jobs_source_last_seen';
-- Expected: 1 row returned

-- 3. Sample data check
SELECT id, source, scraped_at, last_seen, scraped_at = last_seen as timestamps_match
FROM raw_jobs
LIMIT 10;
-- Expected: timestamps_match = true for all existing records

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================

-- To rollback this migration:
-- DROP INDEX idx_raw_jobs_source_last_seen;
-- ALTER TABLE raw_jobs DROP COLUMN last_seen;
