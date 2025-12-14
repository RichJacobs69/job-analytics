-- Migration 007: Allow 'unknown' as valid working_arrangement
-- Date: 2025-12-14
-- Purpose: Support Adzuna jobs where working arrangement cannot be determined from truncated text
--
-- Background: Adzuna API provides truncated job descriptions. Working arrangement info
-- is often cut off, so we defaulted to 'onsite'. This is inaccurate for ~99% of cases.
-- Adding 'unknown' allows honest classification when we can't determine the arrangement.
--
-- Affected: ~5,800 Adzuna jobs will be updated to 'unknown' after running backfill

-- Step 1: Drop the existing constraint
ALTER TABLE enriched_jobs
DROP CONSTRAINT IF EXISTS valid_working_arrangement;

-- Step 2: Recreate the constraint with 'unknown' included
ALTER TABLE enriched_jobs
ADD CONSTRAINT valid_working_arrangement CHECK (working_arrangement IN ('onsite', 'hybrid', 'remote', 'flexible', 'unknown'));

-- Update column comment
COMMENT ON COLUMN enriched_jobs.working_arrangement IS 'Working arrangement: onsite, hybrid, remote, flexible, or unknown (when cannot be determined from available data)';

-- Verification query (run manually after migration):
-- SELECT working_arrangement, COUNT(*) FROM enriched_jobs GROUP BY working_arrangement;

