-- Migration 025c: Add financial_services to industry enum
-- Date: 2026-01-04
-- Purpose: Distinguish traditional banks (JPMorgan) from fintech disruptors (Stripe)

-- Drop and recreate the CHECK constraint to add new value
ALTER TABLE employer_metadata
DROP CONSTRAINT IF EXISTS employer_metadata_industry_check;

ALTER TABLE employer_metadata
ADD CONSTRAINT employer_metadata_industry_check CHECK (industry IN (
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
    'hardware',
    'other'
));
