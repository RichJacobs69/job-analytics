-- Migration: Add hash column and unique constraint to raw_jobs table
-- Date: 2025-12-03
-- Purpose: Enable UPSERT deduplication for incremental pipeline writes

-- Step 1: Add hash column (TEXT, nullable initially)
ALTER TABLE raw_jobs ADD COLUMN IF NOT EXISTS hash TEXT;

-- Step 2: Populate hash for existing records
-- Generate hash from (company, title, 'unk') for existing data
UPDATE raw_jobs
SET hash = md5(
    lower(trim(COALESCE(company, 'unknown'))) || '|' ||
    lower(trim(COALESCE(title, 'unknown'))) || '|' ||
    'unk'
)
WHERE hash IS NULL;

-- Step 3: Add UNIQUE constraint
-- Drop existing constraint if it exists (idempotent)
ALTER TABLE raw_jobs DROP CONSTRAINT IF EXISTS raw_jobs_hash_unique;

-- Add new unique constraint
ALTER TABLE raw_jobs ADD CONSTRAINT raw_jobs_hash_unique UNIQUE (hash);

-- Step 4: Add index for performance
CREATE INDEX IF NOT EXISTS idx_raw_jobs_hash ON raw_jobs(hash);

-- Step 5: Make hash column NOT NULL (after all existing rows populated)
ALTER TABLE raw_jobs ALTER COLUMN hash SET NOT NULL;

-- Verification queries (run these after migration):
-- SELECT COUNT(*) FROM raw_jobs WHERE hash IS NULL;  -- Should be 0
-- SELECT hash, COUNT(*) FROM raw_jobs GROUP BY hash HAVING COUNT(*) > 1;  -- Should be empty
