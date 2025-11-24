-- Migration: Add source tracking columns for dual pipeline
-- Date: 2025-11-21
-- Purpose: Track data source for dual Adzuna + Greenhouse pipeline

-- Add columns to enriched_jobs table to track data sources
-- These columns help understand which data sources were used for each job

ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS data_source VARCHAR(50) DEFAULT 'adzuna' COMMENT 'Primary data source: adzuna, greenhouse, or hybrid',
ADD COLUMN IF NOT EXISTS description_source VARCHAR(50) DEFAULT 'adzuna' COMMENT 'Which source provided the description used: adzuna, greenhouse',
ADD COLUMN IF NOT EXISTS deduplicated BOOLEAN DEFAULT FALSE COMMENT 'Whether this job was deduplicated from multiple sources',
ADD COLUMN IF NOT EXISTS original_url_secondary VARCHAR(2048) DEFAULT NULL COMMENT 'Secondary URL if merged from another source',
ADD COLUMN IF NOT EXISTS merged_from_source VARCHAR(50) DEFAULT NULL COMMENT 'If deduplicated, which source was merged with this one';

-- Add index on data_source for filtering queries
CREATE INDEX IF NOT EXISTS idx_enriched_jobs_data_source ON enriched_jobs(data_source);

-- Add index on deduplicated for finding merged jobs
CREATE INDEX IF NOT EXISTS idx_enriched_jobs_deduplicated ON enriched_jobs(deduplicated);

-- Add index on description_source for quality analysis
CREATE INDEX IF NOT EXISTS idx_enriched_jobs_description_source ON enriched_jobs(description_source);

-- Comment on table to explain new tracking
COMMENT ON TABLE enriched_jobs IS 'Classified/enriched job data with source tracking for dual Adzuna+Greenhouse pipeline';
