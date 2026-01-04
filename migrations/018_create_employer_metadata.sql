-- Migration 018: Create employer_metadata table
-- Part of: EPIC-008 Curated Job Feed / Employer Metadata System
-- Date: 2026-01-04
-- Purpose: Centralized employer metadata with working_arrangement fallback
--
-- This migration:
-- 1. Creates employer_metadata table with canonical name handling
-- 2. Adds working_arrangement_default for fallback when classifier returns 'unknown'
-- 3. Stores employer_size (canonical, not per-job varying)
-- 4. Tracks name aliases for display purposes
--
-- The table is populated by pipeline/utilities/seed_employer_metadata.py
-- which seeds from existing enriched_jobs data.
--
-- working_arrangement_default values are set manually (or via future career page scraping)
--
-- Risk Level: LOW
-- - New table, no existing data affected
-- - Non-destructive

-- =============================================================================
-- STEP 1: Create employer_metadata table
-- =============================================================================

CREATE TABLE IF NOT EXISTS employer_metadata (
    id SERIAL PRIMARY KEY,

    -- Canonical identifier (lowercase, normalized - primary lookup key)
    canonical_name TEXT NOT NULL UNIQUE,

    -- Name variations seen in job postings (for display/reporting)
    aliases TEXT[] DEFAULT '{}',

    -- Display name (most common casing, pretty version for UI)
    display_name TEXT NOT NULL,

    -- Employer size (canonical, not per-job varying)
    employer_size TEXT CHECK (employer_size IN ('startup', 'scaleup', 'enterprise')),

    -- Working arrangement fallback (used when classifier returns 'unknown')
    -- Priority: classifier > is_remote flag > this fallback > 'unknown'
    working_arrangement_default TEXT CHECK (
        working_arrangement_default IN ('hybrid', 'remote', 'onsite', 'flexible')
    ),

    -- Source of working_arrangement_default value
    -- 'manual' = human-verified, 'inferred' = algorithmic, 'scraped' = from career page
    working_arrangement_source TEXT CHECK (
        working_arrangement_source IN ('manual', 'inferred', 'scraped')
    ),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE employer_metadata IS 'Centralized employer metadata. Provides canonical employer info and working_arrangement fallback when classifier returns unknown.';
COMMENT ON COLUMN employer_metadata.canonical_name IS 'Lowercase normalized employer name (primary lookup key)';
COMMENT ON COLUMN employer_metadata.aliases IS 'Name variations seen in job postings (for display/reporting, not lookup)';
COMMENT ON COLUMN employer_metadata.display_name IS 'Most common casing variant, used for UI display';
COMMENT ON COLUMN employer_metadata.employer_size IS 'Canonical employer size (startup/scaleup/enterprise), not per-job varying';
COMMENT ON COLUMN employer_metadata.working_arrangement_default IS 'Fallback working arrangement when classifier returns unknown. Priority: classifier > is_remote > this > unknown';
COMMENT ON COLUMN employer_metadata.working_arrangement_source IS 'How working_arrangement_default was determined: manual (human), inferred (algorithm), scraped (career page)';

-- =============================================================================
-- STEP 2: Create indexes
-- =============================================================================

-- Primary lookup is by canonical_name (already has UNIQUE constraint)
CREATE INDEX IF NOT EXISTS idx_employer_metadata_canonical_name
ON employer_metadata (canonical_name);

-- Index for filtering by employer_size
CREATE INDEX IF NOT EXISTS idx_employer_metadata_size
ON employer_metadata (employer_size);

-- =============================================================================
-- STEP 3: Add auto-update trigger for updated_at
-- =============================================================================

-- Uses existing update_updated_at_column() function from migration 014
-- If running standalone, the function should already exist

DROP TRIGGER IF EXISTS set_updated_at ON employer_metadata;

CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON employer_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify table exists
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'employer_metadata'
ORDER BY ordinal_position;

-- =============================================================================
-- EXAMPLE USAGE (for reference)
-- =============================================================================

-- Lookup employer metadata by name (case-insensitive):
--
-- SELECT * FROM employer_metadata
-- WHERE canonical_name = lower('Harvey AI');

-- Join with enriched_jobs for employer context:
--
-- SELECT
--     ej.title_display,
--     ej.employer_name,
--     em.display_name,
--     em.employer_size,
--     em.working_arrangement_default
-- FROM enriched_jobs ej
-- LEFT JOIN employer_metadata em
--     ON lower(ej.employer_name) = em.canonical_name
-- WHERE ej.city_code = 'lon';

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- DROP TRIGGER IF EXISTS set_updated_at ON employer_metadata;
-- DROP TABLE IF EXISTS employer_metadata;
