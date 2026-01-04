-- Migration 022: Simplify view JOINs after employer_name normalization
-- Part of: Employer Metadata Architecture Cleanup
-- Date: 2026-01-04
-- Purpose: Update jobs_with_employer_context view to use direct JOINs (no LOWER())
--
-- Prerequisites:
-- - Migration 021 must be applied (FK constraint on employer_name)
-- - All employer_name values are already lowercase
--
-- This migration simplifies the view by removing LOWER() calls in JOINs,
-- improving query performance since employer_name is now guaranteed to be canonical.
--
-- Risk Level: LOW
-- - Just updating a view
-- - Non-destructive

-- =============================================================================
-- STEP 1: Drop existing view (column order changed)
-- =============================================================================

DROP VIEW IF EXISTS jobs_with_employer_context;

-- =============================================================================
-- STEP 2: Recreate view with simplified JOINs
-- =============================================================================

CREATE VIEW jobs_with_employer_context AS
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
    ej.employer_name AS employer_name_raw,  -- Now canonical (lowercase)
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
    (CURRENT_DATE - ej.posted_date) AS days_open,
    CASE
        WHEN efs.median_days_to_fill IS NOT NULL AND efs.median_days_to_fill > 0
        THEN (CURRENT_DATE - ej.posted_date)::numeric / efs.median_days_to_fill
        ELSE NULL
    END AS fill_time_ratio

FROM enriched_jobs ej
-- Direct JOIN: employer_name is now always lowercase (canonical)
LEFT JOIN employer_metadata em
    ON ej.employer_name = em.canonical_name
LEFT JOIN employer_fill_stats efs
    ON ej.employer_name = efs.canonical_name;

-- =============================================================================
-- STEP 3: Update comment
-- =============================================================================

COMMENT ON VIEW jobs_with_employer_context IS
'Unified view of jobs with employer display_name from employer_metadata and fill stats. employer_name is canonical (lowercase) with FK to employer_metadata.';

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Verify view works
SELECT COUNT(*) FROM jobs_with_employer_context;

-- Check JOIN coverage
SELECT
    COUNT(*) as total_jobs,
    COUNT(employer_canonical) as jobs_with_metadata,
    COUNT(employer_median_days_to_fill) as jobs_with_fill_stats
FROM jobs_with_employer_context;

-- =============================================================================
-- ROLLBACK (restore LOWER() version if needed)
-- =============================================================================

-- Re-run migration 020 to restore original view
