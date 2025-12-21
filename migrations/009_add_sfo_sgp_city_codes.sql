-- Migration 009: Add 'sfo' (San Francisco) and 'sgp' (Singapore) as valid city_codes
-- Date: 2025-12-21
-- Purpose: Support Global Location Expansion - adding San Francisco and Singapore markets
--
-- Background: As part of the Global Location Expansion Epic, we're adding support for
-- San Francisco (sfo) and Singapore (sgp) markets. These need to be valid city_code values.
--
-- Note: city_code is DEPRECATED in favor of the locations JSONB column (migration 008).
-- This migration maintains backward compatibility during the transition period.

-- Step 1: Drop the existing constraint
ALTER TABLE enriched_jobs
DROP CONSTRAINT IF EXISTS valid_city;

-- Step 2: Recreate the constraint with 'sfo' and 'sgp' included
ALTER TABLE enriched_jobs
ADD CONSTRAINT valid_city CHECK (city_code IN ('lon', 'nyc', 'den', 'sfo', 'sgp', 'unk', 'remote'));

-- Update column comment
COMMENT ON COLUMN enriched_jobs.city_code IS 'DEPRECATED: Use locations JSONB instead. City code: lon (London), nyc (New York), den (Denver), sfo (San Francisco), sgp (Singapore), unk (Unknown), remote (Remote/WFH)';

-- Verification query (run manually):
-- SELECT city_code, COUNT(*) FROM enriched_jobs GROUP BY city_code;
