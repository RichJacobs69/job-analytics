-- Migration 006: Add unique constraint on (source, source_job_id)
--
-- Problem: Adzuna URLs contain session tracking parameters that change,
-- causing the same job to be inserted multiple times with different URLs.
--
-- Example: source_job_id 5505183028 appears 3 times with different URLs:
--   - https://...?se=DlP3dfrQ8BG5neMjo083IQ...
--   - https://...?se=xD976TzR8BGQZI3bOe79Tw...
--   - https://...?se=tsYMjZXP8BG3W4V_Z2HFAQ...
--
-- Solution: Use (source, source_job_id) as the unique constraint instead of posting_url.
-- This correctly identifies duplicates based on the actual job ID from the source.

-- Step 1: Remove old constraints
ALTER TABLE raw_jobs DROP CONSTRAINT IF EXISTS raw_jobs_posting_url_key;
ALTER TABLE raw_jobs DROP CONSTRAINT IF EXISTS raw_jobs_hash_unique;
ALTER TABLE raw_jobs DROP CONSTRAINT IF EXISTS raw_jobs_hash_key;

-- Step 2: Clean up existing duplicates (keep the most recent)
-- This deletes older duplicates, keeping only the row with the highest ID for each (source, source_job_id)
DELETE FROM raw_jobs a
USING raw_jobs b
WHERE a.source = b.source
  AND a.source_job_id = b.source_job_id
  AND a.source_job_id IS NOT NULL
  AND a.id < b.id;

-- Step 3: Add unique constraint on (source, source_job_id)
-- Only applies when source_job_id is NOT NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_jobs_source_job_id_unique 
ON raw_jobs (source, source_job_id) 
WHERE source_job_id IS NOT NULL;

-- Step 4: Keep posting_url index for lookups (but not unique)
DROP INDEX IF EXISTS idx_raw_jobs_posting_url;
CREATE INDEX IF NOT EXISTS idx_raw_jobs_posting_url ON raw_jobs (posting_url);

-- Verify: Check for any remaining duplicates
-- SELECT source, source_job_id, COUNT(*) 
-- FROM raw_jobs 
-- WHERE source_job_id IS NOT NULL 
-- GROUP BY source, source_job_id 
-- HAVING COUNT(*) > 1;

