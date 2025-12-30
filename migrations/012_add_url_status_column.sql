-- Migration 012: Add url_status column to enriched_jobs
-- Part of: EPIC-008 Curated Job Feed
-- Date: 2025-12-30
-- Purpose: Track posting URL health to filter dead links from job feed
--
-- This migration:
-- 1. Adds url_status column to enriched_jobs
-- 2. Adds url_checked_at timestamp for tracking when last validated
-- 3. Creates index for efficient filtering
--
-- The column is populated by pipeline/url_validator.py (nightly batch job)
-- which performs HTTP HEAD requests on posting URLs.
--
-- Jobs with url_status = '404' are excluded from the curated feed
-- to prevent poor UX (clicking through to dead pages).
--
-- Risk Level: LOW
-- - Additive change (new column, nullable)
-- - Non-destructive
-- - Existing data preserved (defaults to 'unknown')

-- =============================================================================
-- STEP 1: Add url_status column
-- =============================================================================

-- Status values:
-- 'active'   - URL returns 200 OK
-- '404'      - URL returns 404 Not Found (job likely closed/removed)
-- 'redirect' - URL redirects (may still be valid, needs investigation)
-- 'error'    - Network error, timeout, or other failure
-- 'unknown'  - Not yet checked (default for existing/new records)

ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS url_status TEXT DEFAULT 'unknown';

ALTER TABLE enriched_jobs
ADD CONSTRAINT valid_url_status
CHECK (url_status IN ('active', '404', 'redirect', 'error', 'unknown'));

COMMENT ON COLUMN enriched_jobs.url_status IS 'HTTP status of posting_url: active (200), 404, redirect, error, or unknown. Used to filter dead links from job feed.';

-- =============================================================================
-- STEP 2: Add url_checked_at timestamp
-- =============================================================================

ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS url_checked_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN enriched_jobs.url_checked_at IS 'Timestamp of last URL health check. NULL means never checked.';

-- =============================================================================
-- STEP 3: Create indexes
-- =============================================================================

-- Index for filtering active jobs in feed queries
CREATE INDEX IF NOT EXISTS idx_enriched_jobs_url_status
ON enriched_jobs (url_status);

-- Partial index for finding jobs needing URL check (efficiency for batch job)
CREATE INDEX IF NOT EXISTS idx_enriched_jobs_needs_url_check
ON enriched_jobs (url_checked_at)
WHERE url_status = 'unknown' OR url_checked_at IS NULL;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify columns exist
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'enriched_jobs'
  AND column_name IN ('url_status', 'url_checked_at')
ORDER BY column_name;

-- Verify constraint
SELECT constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_name = 'valid_url_status';

-- Check current state (all should be 'unknown' initially)
SELECT
    url_status,
    COUNT(*) AS count
FROM enriched_jobs
GROUP BY url_status
ORDER BY count DESC;

-- =============================================================================
-- EXAMPLE USAGE (for reference)
-- =============================================================================

-- Job feed query filters out 404s:
--
-- SELECT *
-- FROM enriched_jobs
-- WHERE data_source IN ('greenhouse', 'lever')
--   AND (url_status != '404' OR url_status IS NULL);

-- Find jobs needing URL check (batch job query):
--
-- SELECT id, posting_url
-- FROM enriched_jobs
-- JOIN raw_jobs ON enriched_jobs.raw_job_id = raw_jobs.id
-- WHERE enriched_jobs.data_source IN ('greenhouse', 'lever')
--   AND (enriched_jobs.url_checked_at IS NULL
--        OR enriched_jobs.url_checked_at < NOW() - INTERVAL '7 days');

-- Update after URL check:
--
-- UPDATE enriched_jobs
-- SET url_status = 'active', url_checked_at = NOW()
-- WHERE id = 123;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- ALTER TABLE enriched_jobs DROP CONSTRAINT IF EXISTS valid_url_status;
-- ALTER TABLE enriched_jobs DROP COLUMN IF EXISTS url_status;
-- ALTER TABLE enriched_jobs DROP COLUMN IF EXISTS url_checked_at;
-- DROP INDEX IF EXISTS idx_enriched_jobs_url_status;
-- DROP INDEX IF EXISTS idx_enriched_jobs_needs_url_check;
