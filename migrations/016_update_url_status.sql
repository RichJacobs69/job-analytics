-- Migration 016: Update url_status column with expanded values and new default
-- Purpose: Support proper URL validation lifecycle with soft 404s and blocked detection
-- Date: 2026-01-01

-- ============================================
-- STEP 1: Drop old constraint
-- ============================================
ALTER TABLE enriched_jobs DROP CONSTRAINT IF EXISTS valid_url_status;

-- ============================================
-- STEP 2: Add new constraint with expanded values
-- ============================================
-- New statuses:
--   active: URL returns 200 with live job content
--   404: Hard 404 HTTP status
--   soft_404: Returns 200 but content indicates job is closed/gone
--   blocked: 403 bot detection (needs Playwright verification)
--   unverifiable: Tried everything, can't determine status (terminal)
--   error: Server error or network timeout
--   redirect: 3xx redirect (legacy, treated as unknown)
--   unknown: Not yet validated (legacy)

ALTER TABLE enriched_jobs
ADD CONSTRAINT valid_url_status
CHECK (url_status IN ('active', '404', 'soft_404', 'blocked', 'unverifiable', 'error', 'redirect', 'unknown'));

-- ============================================
-- STEP 3: Change default to 'active'
-- ============================================
-- Rationale: Freshly scraped jobs have working URLs
ALTER TABLE enriched_jobs ALTER COLUMN url_status SET DEFAULT 'active';

-- ============================================
-- STEP 4: Backfill existing data
-- ============================================
-- Set NULL/unknown to 'active' (assume working until proven otherwise)
UPDATE enriched_jobs
SET url_status = 'active'
WHERE url_status IS NULL OR url_status = 'unknown';

-- ============================================
-- VERIFICATION
-- ============================================
SELECT
    url_status,
    COUNT(*) as count
FROM enriched_jobs
GROUP BY url_status
ORDER BY count DESC;
