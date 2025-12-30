-- Migration 010: Create employer_fill_stats table
-- Part of: EPIC-008 Curated Job Feed
-- Date: 2025-12-30
-- Purpose: Store median fill time per employer for "Still Hiring" group logic
--
-- This migration:
-- 1. Creates employer_fill_stats table
-- 2. Adds indexes for efficient lookups by employer name
--
-- The table is populated by pipeline/employer_stats.py (nightly batch job)
-- which computes median fill times from closed roles in enriched_jobs.
--
-- "Still Hiring" group shows jobs open >1.5x the employer's median fill time.
--
-- Risk Level: LOW
-- - New table, no existing data affected
-- - Non-destructive

-- =============================================================================
-- STEP 1: Create employer_fill_stats table
-- =============================================================================

CREATE TABLE IF NOT EXISTS employer_fill_stats (
    id SERIAL PRIMARY KEY,

    -- Employer identifier (matches enriched_jobs.employer_name)
    employer_name TEXT NOT NULL UNIQUE,

    -- Median days from posted_date to last_seen_date for closed roles
    -- "Closed" = last_seen_date < CURRENT_DATE - 7 days
    median_days_to_fill NUMERIC(5,1),

    -- Sample size used to compute median (minimum 3 for meaningful stats)
    sample_size INTEGER NOT NULL DEFAULT 0,

    -- Tracking
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_sample_size CHECK (sample_size >= 0),
    CONSTRAINT valid_median CHECK (median_days_to_fill IS NULL OR median_days_to_fill >= 0)
);

COMMENT ON TABLE employer_fill_stats IS 'Derived table: median fill times per employer for "Still Hiring" job feed group. Refreshed nightly.';
COMMENT ON COLUMN employer_fill_stats.median_days_to_fill IS 'Median days from posted_date to last_seen_date for roles presumed closed (last_seen > 7 days ago)';
COMMENT ON COLUMN employer_fill_stats.sample_size IS 'Number of closed roles used to compute median. Minimum 3 for meaningful stats.';

-- =============================================================================
-- STEP 2: Create indexes
-- =============================================================================

-- Primary lookup is by employer_name (already has UNIQUE constraint)
-- Add index for efficient joins with enriched_jobs
CREATE INDEX IF NOT EXISTS idx_employer_fill_stats_name
ON employer_fill_stats (employer_name);

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify table exists
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'employer_fill_stats'
ORDER BY ordinal_position;

-- =============================================================================
-- EXAMPLE USAGE (for reference)
-- =============================================================================

-- Join with enriched_jobs to find "Still Hiring" candidates:
--
-- SELECT
--     ej.id,
--     ej.title_display,
--     ej.employer_name,
--     DATE_PART('day', CURRENT_DATE - ej.posted_date) AS days_open,
--     efs.median_days_to_fill,
--     DATE_PART('day', CURRENT_DATE - ej.posted_date) / NULLIF(efs.median_days_to_fill, 0) AS ratio
-- FROM enriched_jobs ej
-- LEFT JOIN employer_fill_stats efs ON ej.employer_name = efs.employer_name
-- WHERE efs.sample_size >= 3
--   AND DATE_PART('day', CURRENT_DATE - ej.posted_date) / NULLIF(efs.median_days_to_fill, 0) > 1.5;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- DROP TABLE IF EXISTS employer_fill_stats;
