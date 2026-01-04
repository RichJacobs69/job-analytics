-- Migration 024: Drop employer_size from enriched_jobs
-- Part of: Employer Metadata Architecture Cleanup
-- Date: 2026-01-04
-- Purpose: Remove duplicate employer_size column - employer_metadata is source of truth
--
-- Background:
-- - enriched_jobs.employer_size was populated by classifier (unreliable, inconsistent)
-- - employer_metadata.employer_size is the curated source of truth
-- - jobs_with_employer_context view now uses only employer_metadata.employer_size
--
-- Risk Level: LOW
-- - Column data is unreliable anyway (classifier guesses from job text)
-- - View already prefers employer_metadata via COALESCE
-- - No frontend code directly queries enriched_jobs.employer_size
--
-- Rollback: See bottom of file

-- =============================================================================
-- STEP 1: Update the view to remove COALESCE (use only employer_metadata)
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
    ej.employer_name AS employer_name_raw,
    COALESCE(em.display_name, ej.employer_name) AS employer_name,
    em.canonical_name AS employer_canonical,

    -- Employer metadata (single source of truth)
    em.employer_size,  -- Now only from employer_metadata
    ej.employer_department,
    em.working_arrangement_default AS employer_working_arrangement_default,
    em.working_arrangement_source AS employer_working_arrangement_source,

    -- Employer fill stats
    efs.median_days_to_fill AS employer_median_days_to_fill,
    efs.sample_size AS employer_fill_sample_size,

    -- Computed fields for job feed
    (CURRENT_DATE - ej.posted_date) AS days_open,
    CASE
        WHEN efs.median_days_to_fill IS NOT NULL AND efs.median_days_to_fill > 0
        THEN (CURRENT_DATE - ej.posted_date)::numeric / efs.median_days_to_fill
        ELSE NULL
    END AS fill_time_ratio

FROM enriched_jobs ej
LEFT JOIN employer_metadata em
    ON ej.employer_name = em.canonical_name
LEFT JOIN employer_fill_stats efs
    ON ej.employer_name = efs.canonical_name;

-- =============================================================================
-- STEP 2: Drop the column from enriched_jobs
-- =============================================================================

ALTER TABLE enriched_jobs DROP COLUMN IF EXISTS employer_size;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Verify column is gone
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'enriched_jobs' AND column_name = 'employer_size';
-- Should return 0 rows

-- Verify view still works
SELECT id, employer_name, employer_size
FROM jobs_with_employer_context
WHERE employer_size IS NOT NULL
LIMIT 5;

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- To rollback, re-add the column and restore old view:
--
-- ALTER TABLE enriched_jobs
-- ADD COLUMN employer_size TEXT CHECK (employer_size IN ('startup', 'scaleup', 'enterprise'));
--
-- Then re-run migration 020 to restore COALESCE logic in view.
