-- Migration 020: Create jobs_with_employer_context view
-- Part of: Employer Metadata Architecture Cleanup (Phase 3)
-- Date: 2026-01-04
-- Purpose: Provide unified view of jobs with employer display_name and fill stats
--
-- This view:
-- 1. JOINs enriched_jobs with employer_metadata to get display_name
-- 2. JOINs with employer_fill_stats to get median_days_to_fill
-- 3. Provides a clean interface for the Job Feed API
--
-- The API can query this view instead of enriched_jobs directly,
-- getting proper employer display names without additional JOIN logic.
--
-- Risk Level: LOW
-- - New view, no existing data affected
-- - Non-destructive
-- - API can migrate gradually

-- =============================================================================
-- STEP 1: Create the view
-- =============================================================================

CREATE OR REPLACE VIEW jobs_with_employer_context AS
SELECT
    -- Job fields
    ej.id,
    ej.raw_job_id,
    ej.job_hash,
    ej.title_display,
    ej.title_canonical,
    ej.job_family,
    ej.job_subfamily,
    ej.track,
    ej.seniority,
    ej.position_type,
    ej.experience_range,
    ej.city_code,
    ej.working_arrangement,
    ej.currency,
    ej.salary_min,
    ej.salary_max,
    ej.equity_eligible,
    ej.skills,
    ej.posted_date,
    ej.last_seen_date,
    ej.classified_at,
    ej.is_agency,
    ej.agency_confidence,
    ej.data_source,
    ej.description_source,
    ej.deduplicated,
    ej.original_url_secondary,
    ej.merged_from_source,
    ej.locations,
    ej.url_status,
    ej.url_checked_at,
    ej.summary,
    ej.summary_model,
    ej.updated_at,
    ej.created_at,

    -- Employer name fields
    ej.employer_name AS employer_name_raw,  -- Original from source (for debugging)
    COALESCE(em.display_name, ej.employer_name) AS employer_name,  -- Prefer display_name
    em.canonical_name AS employer_canonical,

    -- Employer metadata
    COALESCE(em.employer_size, ej.employer_size) AS employer_size,  -- Prefer metadata
    ej.employer_department,
    em.working_arrangement_default AS employer_working_arrangement_default,
    em.working_arrangement_source AS employer_working_arrangement_source,

    -- Employer fill stats
    efs.median_days_to_fill AS employer_median_days_to_fill,
    efs.sample_size AS employer_fill_sample_size,

    -- Computed fields for job feed
    -- Date subtraction returns integer (days) in PostgreSQL
    (CURRENT_DATE - ej.posted_date) AS days_open,
    CASE
        WHEN efs.median_days_to_fill IS NOT NULL AND efs.median_days_to_fill > 0
        THEN (CURRENT_DATE - ej.posted_date)::numeric / efs.median_days_to_fill
        ELSE NULL
    END AS fill_time_ratio

FROM enriched_jobs ej
LEFT JOIN employer_metadata em
    ON LOWER(ej.employer_name) = em.canonical_name
LEFT JOIN employer_fill_stats efs
    ON LOWER(ej.employer_name) = efs.canonical_name;

-- =============================================================================
-- STEP 2: Add comment
-- =============================================================================

COMMENT ON VIEW jobs_with_employer_context IS
'Unified view of jobs with employer display_name from employer_metadata and fill stats from employer_fill_stats. Use this view for the Job Feed API to get proper employer names.';

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify view exists and returns data
SELECT
    id,
    title_display,
    employer_name_raw,
    employer_name,
    employer_canonical,
    employer_size,
    employer_median_days_to_fill,
    days_open,
    fill_time_ratio
FROM jobs_with_employer_context
WHERE employer_canonical IS NOT NULL
LIMIT 10;

-- Check display_name improvements
SELECT
    employer_name_raw,
    employer_name,
    COUNT(*) as job_count
FROM jobs_with_employer_context
WHERE employer_name_raw != employer_name
GROUP BY employer_name_raw, employer_name
ORDER BY job_count DESC
LIMIT 20;

-- =============================================================================
-- EXAMPLE USAGE (for API)
-- =============================================================================

-- Job Feed query (replaces direct enriched_jobs query):
--
-- SELECT
--     id,
--     title_display,
--     employer_name,           -- Now properly cased (e.g., "Figma" not "figma")
--     employer_size,
--     city_code,
--     working_arrangement,
--     salary_min,
--     salary_max,
--     currency,
--     posted_date,
--     days_open,
--     employer_median_days_to_fill,
--     fill_time_ratio,
--     summary,
--     skills
-- FROM jobs_with_employer_context
-- WHERE data_source IN ('greenhouse', 'lever', 'ashby')
--   AND url_status IS DISTINCT FROM '404'
--   AND url_status IS DISTINCT FROM '410'
--   AND job_family = 'data'
-- ORDER BY posted_date DESC
-- LIMIT 50;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- DROP VIEW IF EXISTS jobs_with_employer_context;
