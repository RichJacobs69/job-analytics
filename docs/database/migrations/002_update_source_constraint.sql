-- ============================================
-- Supabase Schema Update: Support Multiple ATS Systems
-- ============================================
-- Purpose: Add support for all planned ATS system sources
--
-- Based on: config/supported_ats.yaml
-- Supported ATS Systems:
--   - adzuna (existing API source)
--   - greenhouse (implemented)
--   - ashby, lever, workable, smartrecruiters, bamboohr, recruitee, comeet, taleo, workday (planned)
--   - custom (for manual/internal jobs)
-- ============================================

-- Step 1: Drop the existing valid_source constraint
ALTER TABLE raw_jobs DROP CONSTRAINT valid_source;

-- Step 2: Add new constraint with all supported sources
ALTER TABLE raw_jobs
ADD CONSTRAINT valid_source
CHECK (source IN (
  'adzuna',           -- Job board API (existing)
  'greenhouse',       -- ATS - implemented
  'ashby',            -- ATS - planned
  'lever',            -- ATS - planned
  'workable',         -- ATS - planned
  'smartrecruiters',  -- ATS - planned
  'bamboohr',         -- ATS - planned
  'recruitee',        -- ATS - planned
  'comeet',           -- ATS - planned
  'taleo',            -- ATS - planned
  'workday',          -- ATS - planned
  'custom',           -- Manual/internal jobs
  'linkedin_rss',     -- Future: LinkedIn RSS feed
  'manual',           -- Manual posting (deprecated - use 'custom')
  'internal'          -- Internal testing (deprecated - use 'custom')
));

-- ============================================
-- Verification
-- ============================================
-- To verify the constraint was updated, run:
-- SELECT constraint_name, constraint_definition
-- FROM information_schema.table_constraints
-- WHERE table_name='raw_jobs';
--
-- Or check the table structure:
-- SELECT column_name, column_default, is_nullable
-- FROM information_schema.columns
-- WHERE table_name='raw_jobs' AND column_name='source';
