-- Migration 014: Add created_at and updated_at columns with auto-update trigger
-- Purpose: Track when rows are created and last modified
-- Date: 2026-01-01

-- Step 1a: Add created_at column (immutable, set once on INSERT)
ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

-- Backfill existing rows: use posted_date as best approximation
UPDATE enriched_jobs
SET created_at = posted_date
WHERE created_at IS NULL;

-- Step 1b: Add updated_at column (auto-updates on every UPDATE)
ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Backfill existing rows: set updated_at = created_at initially
UPDATE enriched_jobs
SET updated_at = created_at
WHERE updated_at IS NULL;

-- Step 2: Create trigger function to auto-update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 3: Attach trigger to enriched_jobs table
DROP TRIGGER IF EXISTS set_updated_at ON enriched_jobs;

CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON enriched_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Step 4: Add index for queries filtering by recently updated
CREATE INDEX IF NOT EXISTS idx_enriched_jobs_updated_at
ON enriched_jobs(updated_at DESC);

-- Verification
SELECT
    column_name,
    data_type,
    column_default
FROM information_schema.columns
WHERE table_name = 'enriched_jobs'
AND column_name IN ('created_at', 'updated_at')
ORDER BY column_name;
