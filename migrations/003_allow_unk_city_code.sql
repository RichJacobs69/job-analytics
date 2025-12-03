-- Migration 003: Allow 'unk' (unknown) as valid city_code
-- Date: 2025-12-03
-- Purpose: Support Greenhouse jobs where city cannot be determined from job listing
--
-- Problem: Greenhouse jobs are scraped without a pre-defined city. The classifier
-- tries to extract it from the description, but may fail. Currently defaults to
-- 'unk' which violates the valid_city constraint.
--
-- Solution: Add 'unk' to the allowed city_code values.

-- Step 1: Drop the existing constraint
ALTER TABLE enriched_jobs
DROP CONSTRAINT IF EXISTS valid_city;

-- Step 2: Recreate the constraint with 'unk' included
ALTER TABLE enriched_jobs
ADD CONSTRAINT valid_city CHECK (city_code IN ('lon', 'nyc', 'den', 'unk'));

-- Verification query (run manually to confirm):
-- SELECT city_code, COUNT(*) FROM enriched_jobs GROUP BY city_code;

COMMENT ON COLUMN enriched_jobs.city_code IS 'City code: lon (London), nyc (New York), den (Denver), unk (Unknown - typically Greenhouse remote/global jobs)';

