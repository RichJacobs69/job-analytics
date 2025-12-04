-- Migration: Remove unique constraint on hash column in raw_jobs
-- 
-- Reason: The hash (company+title+city) can legitimately repeat when:
-- - Same role is posted again months later
-- - Same job appears via different aggregator URLs
--
-- We now rely solely on posting_url for deduplication.
-- The hash column is still stored for potential cross-source deduplication queries.

-- Try both possible constraint names to ensure it's dropped
ALTER TABLE raw_jobs DROP CONSTRAINT IF EXISTS raw_jobs_hash_key;
ALTER TABLE raw_jobs DROP CONSTRAINT IF EXISTS raw_jobs_hash_unique;

