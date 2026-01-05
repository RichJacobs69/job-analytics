-- Migration 027: Add 'productivity' to employer_industry enum
-- Part of: Taxonomy v1.7.0
-- Date: 2026-01-05
-- Purpose: Add productivity category for work management/collaboration tools
--
-- Companies affected: Calendly, Asana, Notion, Airtable, ClickUp, Smartsheet, Lucid Software

-- =============================================================================
-- Update the check constraint to include 'productivity'
-- =============================================================================

-- Drop the existing constraint
ALTER TABLE employer_metadata
DROP CONSTRAINT IF EXISTS employer_metadata_industry_check;

-- Add updated constraint with 'productivity' (20 categories total)
ALTER TABLE employer_metadata
ADD CONSTRAINT employer_metadata_industry_check
CHECK (industry IN (
    'fintech',
    'financial_services',
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
    'productivity',
    'hardware',
    'other'
));

-- =============================================================================
-- Reclassify productivity companies
-- =============================================================================

UPDATE employer_metadata
SET industry = 'productivity', enrichment_source = 'manual'
WHERE canonical_name IN (
    'calendly',
    'asana',
    'notion',
    'airtable',
    'clickup',
    'smartsheet',
    'lucidsoftware'
);

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Check reclassified companies
SELECT canonical_name, industry, enrichment_source
FROM employer_metadata
WHERE industry = 'productivity';

-- Check industry distribution
SELECT industry, COUNT(*) as count
FROM employer_metadata
WHERE enrichment_source IN ('scraped', 'manual')
GROUP BY industry
ORDER BY count DESC;
