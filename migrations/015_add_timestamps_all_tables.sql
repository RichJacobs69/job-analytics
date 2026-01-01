-- Migration 015: Add created_at and updated_at to raw_jobs and employer_fill_stats
-- Purpose: Consistent timestamp tracking across all tables
-- Date: 2026-01-01

-- ============================================
-- RAW_JOBS TABLE
-- ============================================
-- Note: raw_jobs already has scraped_at which serves as created_at

-- Add updated_at column
ALTER TABLE raw_jobs
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Backfill: set updated_at = scraped_at initially
UPDATE raw_jobs
SET updated_at = scraped_at
WHERE updated_at IS NULL;

-- Attach trigger (reuses function from migration 014)
DROP TRIGGER IF EXISTS set_updated_at ON raw_jobs;

CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON raw_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Index for recently updated queries
CREATE INDEX IF NOT EXISTS idx_raw_jobs_updated_at
ON raw_jobs(updated_at DESC);

-- ============================================
-- EMPLOYER_FILL_STATS TABLE
-- ============================================

-- Add created_at column
ALTER TABLE employer_fill_stats
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

-- Add updated_at column
ALTER TABLE employer_fill_stats
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Backfill: set both to now for existing rows (no better approximation)
UPDATE employer_fill_stats
SET created_at = NOW(), updated_at = NOW()
WHERE created_at IS NULL;

-- Attach trigger
DROP TRIGGER IF EXISTS set_updated_at ON employer_fill_stats;

CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON employer_fill_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VERIFICATION
-- ============================================

SELECT 'raw_jobs' as table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'raw_jobs'
AND column_name IN ('scraped_at', 'updated_at')
UNION ALL
SELECT 'employer_fill_stats' as table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'employer_fill_stats'
AND column_name IN ('created_at', 'updated_at')
ORDER BY table_name, column_name;
