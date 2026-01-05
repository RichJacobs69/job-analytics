-- Migration 026: Standardize headquarters location fields
-- Part of: Epic - Employer Metadata Enrichment
-- Date: 2026-01-05
-- Purpose: Add headquarters_state and enforce ISO standards for location aggregation
--
-- Standards:
--   headquarters_country: ISO 3166-1 alpha-2 (US, GB, ES)
--   headquarters_state: ISO 3166-2 subdivision (CA, NY, ENG)
--   headquarters_city: Normalized lowercase with underscores (new_york, san_francisco)

-- =============================================================================
-- Add headquarters_state column
-- =============================================================================

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS headquarters_state TEXT;

COMMENT ON COLUMN employer_metadata.headquarters_state IS 'ISO 3166-2 subdivision code (e.g., CA, NY, ENG, MD)';

-- Update comments on existing columns for clarity
COMMENT ON COLUMN employer_metadata.headquarters_city IS 'Normalized lowercase city name with underscores (e.g., new_york, san_francisco, london)';
COMMENT ON COLUMN employer_metadata.headquarters_country IS 'ISO 3166-1 alpha-2 country code (e.g., US, GB, ES)';

-- =============================================================================
-- Update the view to include headquarters_state
-- =============================================================================

DROP VIEW IF EXISTS jobs_with_employer_context;

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
    ej.employer_name AS employer_name_raw,
    COALESCE(em.display_name, ej.employer_name) AS employer_name,
    em.canonical_name AS employer_canonical,

    -- Employer metadata (source of truth)
    em.employer_size,
    ej.employer_department,
    em.working_arrangement_default AS employer_working_arrangement_default,
    em.working_arrangement_source AS employer_working_arrangement_source,

    -- Industry classification
    em.industry AS employer_industry,

    -- Company identity
    em.website AS employer_website,
    em.logo_url AS employer_logo_url,
    em.description AS employer_description,

    -- Organization info (with new state field)
    em.headquarters_city AS employer_headquarters_city,
    em.headquarters_state AS employer_headquarters_state,
    em.headquarters_country AS employer_headquarters_country,
    em.ownership_type AS employer_ownership_type,
    em.founding_year AS employer_founding_year,

    -- Enrichment tracking
    em.enrichment_source AS employer_enrichment_source,
    em.enrichment_date AS employer_enrichment_date,

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
-- VERIFICATION
-- =============================================================================

-- Check new column exists
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'employer_metadata'
  AND column_name LIKE 'headquarters_%'
ORDER BY column_name;
