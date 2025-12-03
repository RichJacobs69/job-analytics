-- Migration 004: Allow 'remote' as valid city_code
-- Date: 2025-12-03
-- Purpose: Support remote jobs now that location filter accepts remote positions
--
-- Background: Updated greenhouse_location_patterns.yaml to accept remote jobs.
-- Need to allow 'remote' as a valid city_code for enriched_jobs table.

-- Step 1: Drop the existing constraint
ALTER TABLE enriched_jobs
DROP CONSTRAINT IF EXISTS valid_city;

-- Step 2: Recreate the constraint with 'remote' included
ALTER TABLE enriched_jobs
ADD CONSTRAINT valid_city CHECK (city_code IN ('lon', 'nyc', 'den', 'unk', 'remote'));

-- Update column comment
COMMENT ON COLUMN enriched_jobs.city_code IS 'City code: lon (London), nyc (New York), den (Denver), unk (Unknown), remote (Remote/WFH)';

-- Verification query (run manually):
-- SELECT city_code, COUNT(*) FROM enriched_jobs GROUP BY city_code;

