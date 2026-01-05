-- Migration 028: Add careers_url to employer_metadata
-- Date: 2026-01-05
-- Purpose: Store company careers page URL separately from website domain
--
-- Example: Stripe has website "stripe.com" but careers_url "https://stripe.com/jobs"

-- =============================================================================
-- Step 1: Add column to employer_metadata
-- =============================================================================

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS careers_url TEXT;

COMMENT ON COLUMN employer_metadata.careers_url IS 'Direct URL to company careers/jobs page (e.g., https://stripe.com/jobs)';

-- =============================================================================
-- Step 2: Recreate view to expose careers_url
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
    em.careers_url AS employer_careers_url,  -- NEW: Direct careers page URL
    em.logo_url AS employer_logo_url,
    em.description AS employer_description,

    -- Organization info
    em.headquarters_city AS employer_headquarters_city,
    em.headquarters_country AS employer_headquarters_country,
    em.ownership_type AS employer_ownership_type,
    em.founding_year AS employer_founding_year,
    em.parent_company AS employer_parent_company,

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
-- Verification
-- =============================================================================

SELECT column_name
FROM information_schema.columns
WHERE table_name = 'employer_metadata'
  AND column_name = 'careers_url';

SELECT column_name
FROM information_schema.columns
WHERE table_name = 'jobs_with_employer_context'
  AND column_name = 'employer_careers_url';
