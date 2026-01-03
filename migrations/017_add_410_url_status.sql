-- Migration 017: Add 410 to url_status constraint
-- Purpose: Support HTTP 410 Gone status (permanently removed jobs)
-- Date: 2026-01-03

-- ============================================
-- STEP 1: Drop old constraint
-- ============================================
ALTER TABLE enriched_jobs DROP CONSTRAINT IF EXISTS valid_url_status;

-- ============================================
-- STEP 2: Add updated constraint with 410
-- ============================================
-- Statuses:
--   active: URL returns 200 with live job content
--   404: Hard 404 HTTP status
--   410: HTTP 410 Gone (permanently removed)
--   soft_404: Returns 200 but content indicates job is closed/gone
--   blocked: 403/202 bot detection or async page (needs Playwright)
--   unverifiable: Tried everything, can't determine status (terminal)
--   error: Server error or network timeout
--   redirect: 3xx redirect (legacy, treated as unknown)
--   unknown: Not yet validated (legacy)

ALTER TABLE enriched_jobs
ADD CONSTRAINT valid_url_status
CHECK (url_status IN ('active', '404', '410', 'soft_404', 'blocked', 'unverifiable', 'error', 'redirect', 'unknown'));

-- ============================================
-- VERIFICATION
-- ============================================
SELECT constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_name = 'valid_url_status';
