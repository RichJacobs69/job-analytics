-- Migration 011: Create job_summaries table
-- Part of: EPIC-008 Curated Job Feed
-- Date: 2025-12-30
-- Purpose: Store AI-generated role summaries for expanded job cards
--
-- This migration:
-- 1. Creates job_summaries table
-- 2. Adds indexes for efficient lookups by job ID
--
-- The table is populated by pipeline/summary_generator.py (nightly batch job)
-- which generates 2-3 sentence summaries from job descriptions using Gemini.
--
-- Summaries are displayed in expanded job cards in the curated feed,
-- providing quick context without showing the full job description.
--
-- Design decision: Separate table (not column on enriched_jobs) because:
-- - Different refresh cadence (summaries only for new jobs)
-- - Cleaner separation of concerns
-- - Can track model version for regeneration if needed
--
-- Risk Level: LOW
-- - New table, no existing data affected
-- - Non-destructive

-- =============================================================================
-- STEP 1: Create job_summaries table
-- =============================================================================

CREATE TABLE IF NOT EXISTS job_summaries (
    id SERIAL PRIMARY KEY,

    -- Foreign key to enriched_jobs
    -- Using job_id (not raw_job_id) since summaries are for enriched/classified jobs
    enriched_job_id INTEGER NOT NULL UNIQUE,

    -- AI-generated summary (2-3 sentences)
    summary TEXT NOT NULL,

    -- Model tracking (for potential regeneration if model improves)
    model_name TEXT DEFAULT 'gemini-2.5-flash-lite',
    model_version TEXT,

    -- Tracking
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Foreign key constraint
    CONSTRAINT fk_job_summaries_enriched_job
        FOREIGN KEY (enriched_job_id)
        REFERENCES enriched_jobs(id)
        ON DELETE CASCADE
);

-- NOTE: Skills are NOT duplicated here - use enriched_jobs.skills instead

COMMENT ON TABLE job_summaries IS 'AI-generated role summaries for job feed expanded cards. Refreshed nightly for new jobs.';
COMMENT ON COLUMN job_summaries.summary IS '2-3 sentence summary of the role, generated from full job description by Gemini.';
COMMENT ON COLUMN job_summaries.model_name IS 'LLM model used to generate summary (for tracking/regeneration).';

-- =============================================================================
-- STEP 2: Create indexes
-- =============================================================================

-- Primary lookup is by enriched_job_id (for expanded card fetch)
CREATE INDEX IF NOT EXISTS idx_job_summaries_enriched_job_id
ON job_summaries (enriched_job_id);

-- Index for finding jobs without summaries (batch job efficiency)
CREATE INDEX IF NOT EXISTS idx_job_summaries_generated_at
ON job_summaries (generated_at);

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify table exists
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'job_summaries'
ORDER BY ordinal_position;

-- Verify foreign key
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.table_name = 'job_summaries' AND tc.constraint_type = 'FOREIGN KEY';

-- =============================================================================
-- EXAMPLE USAGE (for reference)
-- =============================================================================

-- Get job with summary for expanded card:
--
-- SELECT
--     ej.id,
--     ej.title_display,
--     ej.employer_name,
--     ej.skills,
--     js.summary,
--     js.key_skills
-- FROM enriched_jobs ej
-- LEFT JOIN job_summaries js ON ej.id = js.enriched_job_id
-- WHERE ej.id = 123;

-- Find jobs needing summaries (batch job query):
--
-- SELECT ej.id, ej.raw_job_id
-- FROM enriched_jobs ej
-- LEFT JOIN job_summaries js ON ej.id = js.enriched_job_id
-- WHERE js.id IS NULL
--   AND ej.data_source IN ('greenhouse', 'lever');

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- DROP TABLE IF EXISTS job_summaries;
