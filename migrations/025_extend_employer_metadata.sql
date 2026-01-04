-- Migration 025: Extend employer_metadata with enrichment fields
-- Part of: Epic - Employer Metadata Enrichment
-- Date: 2026-01-04
-- Purpose: Add industry classification, company identity, and enrichment tracking fields
--
-- Related Docs:
--   - docs/architecture/Future Ideas/EPIC_EMPLOYER_ENRICHMENT.md
--   - docs/schema_taxonomy.yaml (enums.employer_industry)
--
-- Risk Level: LOW
--   - All new columns are nullable
--   - No changes to existing data
--   - View update is additive

-- =============================================================================
-- STEP 1: Add identity fields
-- =============================================================================

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS website TEXT;

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS logo_url TEXT;

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS description TEXT;

-- =============================================================================
-- STEP 2: Add industry classification fields
-- =============================================================================

-- 18 domain-focused categories (see docs/schema_taxonomy.yaml)
-- Design decision: No "b2b_saas" - it's a business model, not an industry
ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS industry TEXT CHECK (industry IN (
    'fintech',
    'healthtech',
    'ecommerce',
    'ai_ml',
    'consumer',
    'mobility',
    'proptech',
    'edtech',
    'climate',
    'crypto',
    'devtools',
    'data_infra',
    'cybersecurity',
    'hr_tech',
    'martech',
    'professional_services',
    'hardware',
    'other'
));

-- =============================================================================
-- STEP 3: Add organization fields
-- =============================================================================

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS headquarters_city TEXT;

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS headquarters_country TEXT;

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS ownership_type TEXT CHECK (ownership_type IN (
    'private',
    'public',
    'subsidiary',
    'acquired'
));

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS parent_company TEXT;

ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS founding_year INTEGER;

-- =============================================================================
-- STEP 4: Add enrichment tracking fields
-- =============================================================================

-- Track where enrichment data came from
ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS enrichment_source TEXT CHECK (enrichment_source IN (
    'manual',
    'inferred',
    'scraped'
));

-- Track when data was last enriched (for freshness)
ALTER TABLE employer_metadata
ADD COLUMN IF NOT EXISTS enrichment_date DATE;

-- =============================================================================
-- STEP 5: Create index for industry filtering
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_employer_metadata_industry
ON employer_metadata (industry);

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Check new columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'employer_metadata'
  AND column_name IN ('industry', 'website', 'headquarters_city', 'enrichment_source')
ORDER BY column_name;
-- Should return 4 rows

-- =============================================================================
-- ROLLBACK (if needed)
-- =============================================================================

-- DROP INDEX IF EXISTS idx_employer_metadata_industry;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS website;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS logo_url;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS description;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS industry;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS headquarters_city;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS headquarters_country;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS ownership_type;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS parent_company;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS founding_year;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS enrichment_source;
-- ALTER TABLE employer_metadata DROP COLUMN IF EXISTS enrichment_date;

