-- Migration 013: Add summary column to enriched_jobs
-- Part of: EPIC-008 Curated Job Feed (Inline Summary Generation)
-- Date: 2025-12-31
-- Purpose: Store AI-generated role summaries inline with job data
--
-- This migration:
-- 1. Adds summary column to enriched_jobs table
-- 2. Adds summary_model column to track which model generated the summary
--
-- Background:
-- Previously, summaries were stored in a separate job_summaries table and
-- generated via a daily batch job. This caused data consistency issues
-- (jobs without summaries) and GHA runaway (39-min batch trying to catch up).
--
-- New approach: Summaries are generated inline during classification.
-- The classifier.py prompt now includes summary generation, so new jobs
-- always have summaries from the start.
--
-- The job_summaries table is retained for backward compatibility but
-- may be deprecated after data is migrated.
--
-- Risk Level: LOW
-- - Additive change (new nullable columns)
-- - No existing data affected
-- - Non-destructive

-- =============================================================================
-- STEP 1: Add summary column
-- =============================================================================

ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS summary TEXT;

COMMENT ON COLUMN enriched_jobs.summary IS 'AI-generated 2-3 sentence role summary (from classifier, inline generation)';

-- =============================================================================
-- STEP 2: Add summary_model column (for tracking/regeneration)
-- =============================================================================

ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS summary_model TEXT DEFAULT 'gemini-2.5-flash-lite';

COMMENT ON COLUMN enriched_jobs.summary_model IS 'LLM model used to generate summary (for tracking/regeneration)';

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify columns exist
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'enriched_jobs'
  AND column_name IN ('summary', 'summary_model')
ORDER BY column_name;

-- =============================================================================
-- OPTIONAL: Migrate existing summaries from job_summaries table
-- =============================================================================

-- Run this after verifying the column was added successfully:
--
-- UPDATE enriched_jobs ej
-- SET
--     summary = js.summary,
--     summary_model = js.model_name
-- FROM job_summaries js
-- WHERE ej.id = js.enriched_job_id
--   AND ej.summary IS NULL;
--
-- Verify migration:
-- SELECT COUNT(*) FROM enriched_jobs WHERE summary IS NOT NULL;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- ALTER TABLE enriched_jobs DROP COLUMN IF EXISTS summary;
-- ALTER TABLE enriched_jobs DROP COLUMN IF EXISTS summary_model;
