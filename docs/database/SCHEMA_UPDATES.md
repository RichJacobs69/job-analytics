# Database Schema Updates

**Last Updated:** January 4, 2026
**Status:** All migrations complete and verified

This document tracks all database schema changes for the job-analytics platform.

---

## Table of Contents

1. [Migration 1: Source Tracking (enriched_jobs)](#migration-1-source-tracking-enriched_jobs)
2. [Migration 2: Title and Company Fields (raw_jobs)](#migration-2-title-and-company-fields-raw_jobs)
3. [Migrations 014-015: URL Validation Timestamps](#migrations-014-015-url-validation-timestamps)
4. [Migration 016: URL Status Expansion](#migration-016-url-status-expansion)
5. [Migrations 017-022: Employer Metadata System](#migrations-017-022-employer-metadata-system)
6. [Current Schema Reference](#current-schema-reference)

---

## Migration 1: Source Tracking (enriched_jobs)

**Date:** November 21, 2025
**Purpose:** Add source tracking columns for Adzuna + Greenhouse dual pipeline
**Status:** ✅ Complete

### Summary

The dual pipeline requires tracking which data source provided each job and which source provided the description used for classification. The existing schema already has `source` and `full_text` columns in `raw_jobs`, but we need to add source tracking to `enriched_jobs` for analytics and debugging.

### Changes Applied

#### New Columns in `enriched_jobs` Table

- **`data_source`** (VARCHAR 50) - Primary data source: 'adzuna', 'greenhouse', or 'hybrid'
- **`description_source`** (VARCHAR 50) - Which source provided the description: 'adzuna' or 'greenhouse'
- **`deduplicated`** (BOOLEAN) - Whether this job was deduplicated from multiple sources
- **`original_url_secondary`** (VARCHAR 2048) - Secondary URL if merged from another source
- **`merged_from_source`** (VARCHAR 50) - If deduplicated, which source was merged with this one

#### New Indexes

- `idx_enriched_jobs_data_source` - For filtering/grouping by source
- `idx_enriched_jobs_deduplicated` - For finding merged jobs
- `idx_enriched_jobs_description_source` - For quality analysis by source

### Benefits

- ✅ Track deduplication rate between Adzuna and Greenhouse
- ✅ Measure classification quality by description source
- ✅ Enable source-specific analytics
- ✅ Support cost-benefit analysis of each pipeline

---

## Migration 2: Title and Company Fields (raw_jobs)

**Date:** December 2, 2025
**Purpose:** Preserve original source metadata before classification
**Status:** ✅ Complete and verified

### Summary

The `raw_jobs` table was missing key source metadata:
- **Title**: Original job title from source (lost after classification)
- **Company**: Original company name from source (lost after classification)

This enhancement preserves the original title and company from Adzuna API responses, enabling:
- Direct analysis of raw_jobs without joining enriched_jobs
- Fallback data when classification fails
- Better audit trail for data lineage
- Comparison of source titles vs classified titles

### Changes Applied

#### New Columns in `raw_jobs` Table

```sql
ALTER TABLE raw_jobs
ADD COLUMN IF NOT EXISTS title TEXT;

ALTER TABLE raw_jobs
ADD COLUMN IF NOT EXISTS company TEXT;

COMMENT ON COLUMN raw_jobs.title IS 'Original job title from source (before classification)';
COMMENT ON COLUMN raw_jobs.company IS 'Original company name from source (before classification)';
```

#### New Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_raw_jobs_title ON raw_jobs(title);
CREATE INDEX IF NOT EXISTS idx_raw_jobs_company ON raw_jobs(company);
```

### Code Changes

**Modified:** `pipeline/db_connection.py` (insert_raw_job function)
- Added optional `title` and `company` parameters
- Null-safe handling with conditional insertion

**Modified:** `pipeline/fetch_jobs.py` (store_jobs function)
- Now passes title and company from UnifiedJob to insert_raw_job()

### Verification

**Test completed:** December 2, 2025
- Fetched 11 Adzuna jobs from London
- ✅ 6/7 jobs successfully stored with title and company populated
- ✅ 1 duplicate URL rejected (expected behavior)
- ✅ Fields automatically populated from Adzuna API responses

### Benefits

- ✅ Preserve source title and company without classification
- ✅ Fallback data when classification fails
- ✅ Better audit trail (what did Adzuna say vs what did Claude classify?)
- ✅ Query raw_jobs directly (no join to enriched_jobs needed)
- ✅ Analyze company name variations across sources
- ✅ Track data lineage

### Backward Compatibility

✅ **Fully backward compatible**
- Existing code continues to work (parameters are optional)
- Existing data is unchanged (new columns are nullable)
- New jobs will populate title and company
- Old jobs will have NULL values (can be backfilled if needed)

---

## Migrations 014-015: URL Validation Timestamps

**Date:** December 31, 2025
**Purpose:** Add timestamp columns for URL validation tracking
**Status:** Complete

### Summary

Added `url_checked_at` and `updated_at` columns to support URL validation lifecycle for the curated job feed.

### Changes Applied

```sql
-- Migration 014: Add url_checked_at
ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS url_checked_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_enriched_jobs_url_checked_at
ON enriched_jobs(url_checked_at);

-- Migration 015: Add updated_at with auto-update trigger
ALTER TABLE enriched_jobs
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_enriched_jobs_updated_at
    BEFORE UPDATE ON enriched_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### Benefits

- Track when each job URL was last validated
- Support 3-day recheck window (avoid redundant validation)
- Auto-update timestamp on any record change

---

## Migration 016: URL Status Expansion

**Date:** January 1, 2026
**Purpose:** Expand url_status constraint for soft 404 detection and set default to 'active'
**Status:** Complete

### Summary

Expanded the `url_status` constraint to support soft 404 detection (pages that return HTTP 200 but show "job closed" content) and Playwright fallback for bot-protected sites. Changed default from 'unknown' to 'active' since freshly scraped jobs have working URLs.

### Changes Applied

```sql
-- Drop old constraint
ALTER TABLE enriched_jobs DROP CONSTRAINT IF EXISTS valid_url_status;

-- Add new constraint with expanded values
ALTER TABLE enriched_jobs
ADD CONSTRAINT valid_url_status
CHECK (url_status IN ('active', '404', 'soft_404', 'blocked', 'unverifiable', 'error', 'redirect', 'unknown'));

-- Change default to 'active' (freshly scraped = working URL)
ALTER TABLE enriched_jobs ALTER COLUMN url_status SET DEFAULT 'active';

-- Backfill: Set NULL/unknown to 'active' for existing jobs
UPDATE enriched_jobs
SET url_status = 'active'
WHERE url_status IS NULL OR url_status = 'unknown';
```

### URL Status Values

| Status | Meaning | Terminal? |
|--------|---------|-----------|
| `active` | Job page loads correctly | No (recheck after 3 days) |
| `404` | HTTP 404 response | Yes (never recheck) |
| `soft_404` | HTTP 200 but content says "job closed/filled" | Yes (never recheck) |
| `blocked` | HTTP 403 (bot protection) | No (retry with Playwright) |
| `unverifiable` | Playwright also blocked (Cloudflare/CAPTCHA) | No (keep in feed) |
| `error` | Network timeout or other error | No (retry next run) |

### Code Changes

**Modified:** `pipeline/db_connection.py`
- Added `url_status: str = 'active'` parameter to `insert_enriched_job()`
- New jobs now default to 'active' status

**Modified:** `pipeline/url_validator.py`
- Added soft 404 pattern detection (13 patterns)
- Added bot protection detection (10 patterns)
- Added Playwright fallback for blocked URLs
- Added oldest-first ordering for validation priority
- Skip 404/soft_404 jobs (terminal states)

**Modified:** `pipeline/employer_stats.py`
- Include soft_404 in fill time calculations (closed = 404 OR soft_404)

### Validation Results (2026-01-01)

Initial full validation of 2,548 ATS jobs:

| Status | Count | % |
|--------|-------|---|
| active | 2,985 | 79.7% |
| 404 | 171 | 4.6% |
| soft_404 | 280 | 7.5% |
| unverifiable | 121 | 3.2% |
| error | 190 | 5.1% |

**451 dead links identified (12.1%)** - excluded from job feed.

---

## Migrations 017-022: Employer Metadata System

**Date:** January 3-4, 2026
**Purpose:** Create employer metadata infrastructure with FK constraint for referential integrity
**Status:** Complete

### Summary

This series of migrations creates a centralized employer metadata system that:
1. Stores canonical employer information (display names, sizes, working arrangements)
2. Enforces referential integrity via FK constraint on enriched_jobs.employer_name
3. Provides a view layer for API queries with proper display names

### Migration 017: Add HTTP 410 Status

**File:** `migrations/017_add_410_url_status.sql`

Added HTTP 410 (Gone) as a terminal URL status for permanently removed job postings.

```sql
ALTER TABLE enriched_jobs DROP CONSTRAINT IF EXISTS valid_url_status;
ALTER TABLE enriched_jobs ADD CONSTRAINT valid_url_status
CHECK (url_status IN ('active', '404', '410', 'soft_404', 'blocked', 'unverifiable', 'error', 'redirect', 'unknown'));
```

### Migration 018: Create employer_metadata Table

**File:** `migrations/018_create_employer_metadata.sql`

Created the `employer_metadata` table as the single source of truth for employer information.

```sql
CREATE TABLE employer_metadata (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,      -- Lowercase normalized (PK for JOINs)
    display_name TEXT NOT NULL,               -- Proper casing for UI
    employer_size TEXT CHECK (employer_size IN ('startup', 'scaleup', 'enterprise')),
    working_arrangement_default TEXT CHECK (
        working_arrangement_default IN ('hybrid', 'remote', 'onsite', 'flexible')
    ),
    working_arrangement_source TEXT CHECK (
        working_arrangement_source IN ('manual', 'inferred', 'scraped')
    ),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Note: `aliases` column was removed in migration 023 (unused with FK constraint approach).

### Migration 019: Rename employer_fill_stats Column

**File:** `migrations/019_rename_employer_fill_stats_column.sql`

Renamed `employer_name` to `canonical_name` in `employer_fill_stats` for consistency.

### Migration 020: Create jobs_with_employer_context View

**File:** `migrations/020_create_jobs_with_employer_context_view.sql`

Created view that JOINs enriched_jobs with employer_metadata and employer_fill_stats.

```sql
CREATE VIEW jobs_with_employer_context AS
SELECT
    ej.*,
    ej.employer_name AS employer_name_raw,
    COALESCE(em.display_name, ej.employer_name) AS employer_name,
    em.canonical_name AS employer_canonical,
    COALESCE(em.employer_size, ej.employer_size) AS employer_size,
    em.working_arrangement_default,
    efs.median_days_to_fill AS employer_median_days_to_fill,
    (CURRENT_DATE - ej.posted_date) AS days_open,
    -- fill_time_ratio computed field
FROM enriched_jobs ej
LEFT JOIN employer_metadata em ON ej.employer_name = em.canonical_name
LEFT JOIN employer_fill_stats efs ON ej.employer_name = efs.canonical_name;
```

### Migration 021: Add FK Constraint on employer_name

**File:** `migrations/021_add_employer_name_fk.sql`

Added foreign key constraint to enforce referential integrity.

**Prerequisites applied before migration:**
- Deleted 1,995 agency jobs (is_agency=true or blacklisted employers)
- Added 4,131 employers to employer_metadata (from Adzuna data)
- Normalized all employer_name values to lowercase

```sql
ALTER TABLE enriched_jobs
ADD CONSTRAINT fk_enriched_jobs_employer
FOREIGN KEY (employer_name)
REFERENCES employer_metadata (canonical_name)
ON UPDATE CASCADE
ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_enriched_jobs_employer_name
ON enriched_jobs (employer_name);
```

**Impact:**
- enriched_jobs.employer_name is now **always lowercase canonical**
- Every job must reference a valid employer in employer_metadata
- Cannot delete employers with existing jobs (RESTRICT)
- Employer name changes cascade to jobs (CASCADE)

### Migration 022: Simplify View JOINs

**File:** `migrations/022_simplify_view_joins.sql`

Updated view to use direct JOINs (removed LOWER() calls since employer_name is now canonical).

```sql
-- Before (migration 020):
LEFT JOIN employer_metadata em ON LOWER(ej.employer_name) = em.canonical_name

-- After (migration 022):
LEFT JOIN employer_metadata em ON ej.employer_name = em.canonical_name
```

### Data Migration Summary

| Action | Count |
|--------|-------|
| Agency jobs deleted | 1,995 |
| Employers added to metadata | 4,131 |
| employer_name values normalized | 3,293 |
| Total employers in metadata | 5,586 |
| FK coverage | 100% |

### Code Changes

**Modified:** `pipeline/db_connection.py`
- `insert_enriched_job()` now normalizes employer_name to lowercase
- Added `ensure_employer_metadata()` function
- Added `get_employer_metadata()` with caching
- Added `get_working_arrangement_fallback()` function

**Modified:** `pipeline/fetch_jobs.py`
- Calls `ensure_employer_metadata()` after job inserts
- Working arrangement fallback at 5 ATS processor locations

### Benefits

- Single source of truth for employer information
- Proper display names (e.g., "Figma" not "figma")
- Working arrangement fallback for jobs classified as 'unknown'
- Referential integrity prevents orphan jobs
- Simplified JOINs improve query performance

---

## Current Schema Reference

### `raw_jobs` Table

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | bigint | NO | Primary key |
| source | text | NO | 'adzuna', 'greenhouse', etc |
| posting_url | text | NO | Unique constraint |
| raw_text | text | NO | Full job description |
| source_job_id | text | YES | External ID |
| **title** | **text** | **YES** | **Original job title (NEW)** |
| **company** | **text** | **YES** | **Original company (NEW)** |
| metadata | jsonb | YES | Additional metadata |
| full_text | text | YES | Greenhouse full description |
| text_source | text | YES | Where full_text came from |
| scraped_at | timestamp | NO | When job was scraped |
| created_at | timestamp | NO | When record was created |
| updated_at | timestamp | NO | Last update |

**Indexes:**
- `idx_raw_jobs_posting_url` (UNIQUE)
- `idx_raw_jobs_source`
- `idx_raw_jobs_scraped_at`
- `idx_raw_jobs_title` **(NEW)**
- `idx_raw_jobs_company` **(NEW)**

### `enriched_jobs` Table

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | bigint | NO | Primary key |
| raw_job_id | bigint | NO | Foreign key to raw_jobs |
| job_hash | text | NO | Deduplication hash (UNIQUE) |
| employer_name | text | NO | Canonical employer name (lowercase, FK to employer_metadata) |
| title_display | text | NO | Original job title from posting |
| job_family | text | NO | 'product', 'data', 'out_of_scope' |
| job_subfamily | text | YES | Specific role type |
| seniority | text | YES | Junior, Mid-Level, Senior, Staff+ |
| city_code | text | NO | 'lon', 'nyc', 'den' |
| working_arrangement | text | NO | onsite, hybrid, remote, flexible |
| **data_source** | **text** | **YES** | **'adzuna', 'greenhouse', 'hybrid' (NEW)** |
| **description_source** | **text** | **YES** | **Which source provided description (NEW)** |
| **deduplicated** | **boolean** | **YES** | **Whether job was merged from multiple sources (NEW)** |
| **original_url_secondary** | **text** | **YES** | **Secondary URL if merged (NEW)** |
| **merged_from_source** | **text** | **YES** | **Which source was merged in** |
| **url_status** | **text** | **NO** | **URL validation status (default: 'active')** |
| **url_checked_at** | **timestamp** | **YES** | **When URL was last validated** |
| **updated_at** | **timestamp** | **YES** | **Auto-updated on any change** |
| ... | ... | ... | (plus compensation, skills, dates, etc.) |

**Indexes:**
- `idx_enriched_jobs_job_hash` (UNIQUE)
- `idx_enriched_jobs_city_code`
- `idx_enriched_jobs_job_family`
- `idx_enriched_jobs_data_source`
- `idx_enriched_jobs_deduplicated`
- `idx_enriched_jobs_description_source`
- `idx_enriched_jobs_url_checked_at`

---

## Example Usage

### Storing a Job with Full Metadata

```python
from pipeline.db_connection import insert_raw_job, insert_enriched_job
from datetime import date

# Step 1: Insert raw job with original title and company
raw_job_id = insert_raw_job(
    source="adzuna",
    posting_url="https://www.adzuna.com/jobs/details/...",
    title="Senior Data Engineer",          # Original Adzuna title
    company="Stripe",                      # Original Adzuna company
    raw_text="Job description...",
    source_job_id="12345678"
)

# Step 2: Insert enriched job with classification and source tracking
enriched_job_id = insert_enriched_job(
    raw_job_id=raw_job_id,
    employer_name="Stripe",                # Classified company name
    title_display="Senior Data Engineer",   # Classified title
    job_family="data",
    job_subfamily="data_engineer",
    seniority="senior",
    city_code="lon",
    working_arrangement="hybrid",
    position_type="full_time",
    posted_date=date.today(),
    last_seen_date=date.today(),
    # Source tracking (Migration 1)
    data_source="adzuna",
    description_source="adzuna",
    deduplicated=False
)
```

### Querying with New Fields

```sql
-- Get original source metadata for a job
SELECT
    r.title AS adzuna_title,
    r.company AS adzuna_company,
    e.title_display AS classified_title,
    e.employer_name AS classified_company,
    e.data_source,
    e.description_source
FROM enriched_jobs e
JOIN raw_jobs r ON e.raw_job_id = r.id
WHERE e.city_code = 'lon'
LIMIT 10;

-- Find jobs where source title differs from classified title
SELECT
    r.title AS original_title,
    e.title_display AS classified_title,
    r.company AS original_company,
    e.employer_name AS classified_company
FROM enriched_jobs e
JOIN raw_jobs r ON e.raw_job_id = r.id
WHERE r.title IS NOT NULL
  AND r.title != e.title_display
LIMIT 20;

-- Analyze deduplication rate by source
SELECT
    data_source,
    COUNT(*) AS total_jobs,
    SUM(CASE WHEN deduplicated THEN 1 ELSE 0 END) AS deduplicated_jobs,
    ROUND(100.0 * SUM(CASE WHEN deduplicated THEN 1 ELSE 0 END) / COUNT(*), 2) AS dedup_rate_percent
FROM enriched_jobs
GROUP BY data_source;
```

---

## Migration Scripts

### Migration 1: Source Tracking

**File:** `migrations/001_add_source_tracking.sql`
**Applied:** November 21, 2025
**Status:** Complete

### Migration 2: Raw Jobs Metadata

**Generator Script:** `pipeline/utilities/migrate_raw_jobs_schema.py`
**Wrapper:** `wrapper/migrate_raw_jobs_schema.py`
**Applied:** December 2, 2025
**Status:** Complete and verified

**Documentation:** See `docs/archive/session_2025-12-02_backfill/SCHEMA_ENHANCEMENT_SUMMARY.md` for detailed implementation notes.

---

## Rollback Procedures

### Rollback Migration 1 (Source Tracking)

```sql
-- Drop indexes
DROP INDEX IF EXISTS idx_enriched_jobs_data_source;
DROP INDEX IF EXISTS idx_enriched_jobs_deduplicated;
DROP INDEX IF EXISTS idx_enriched_jobs_description_source;

-- Drop columns
ALTER TABLE enriched_jobs
DROP COLUMN IF EXISTS data_source,
DROP COLUMN IF EXISTS description_source,
DROP COLUMN IF EXISTS deduplicated,
DROP COLUMN IF EXISTS original_url_secondary,
DROP COLUMN IF EXISTS merged_from_source;
```

### Rollback Migration 2 (Raw Jobs Metadata)

```sql
-- Drop indexes
DROP INDEX IF EXISTS idx_raw_jobs_title;
DROP INDEX IF EXISTS idx_raw_jobs_company;

-- Drop columns
ALTER TABLE raw_jobs
DROP COLUMN IF EXISTS title,
DROP COLUMN IF EXISTS company;
```

**Note:** Rollbacks will lose any data stored in these columns. Only use in emergencies.

---

## Next Planned Migrations

No migrations currently planned. Future schema changes will be documented here.

### Migration History

| Migration | Date | Purpose |
|-----------|------|---------|
| 001 | Nov 21, 2025 | Source tracking columns |
| 002 | Dec 2, 2025 | Raw jobs title/company fields |
| 010-013 | Dec 27-31, 2025 | Job feed infrastructure (employer_fill_stats, summary, url_status) |
| 014-015 | Dec 31, 2025 | URL validation timestamps |
| 016 | Jan 1, 2026 | URL status expansion (soft_404, default 'active') |
| 017 | Jan 3, 2026 | Add HTTP 410 status for permanently removed jobs |
| 018 | Jan 4, 2026 | Create employer_metadata table |
| 019 | Jan 4, 2026 | Rename employer_fill_stats.employer_name to canonical_name |
| 020 | Jan 4, 2026 | Create jobs_with_employer_context view |
| 021 | Jan 4, 2026 | FK constraint on enriched_jobs.employer_name |
| 022 | Jan 4, 2026 | Simplify view JOINs (remove LOWER()) |
| 023 | Jan 4, 2026 | Drop unused aliases column from employer_metadata |

---

## References

- **Code:** `pipeline/db_connection.py` - Database interface implementation
- **Specs:** `docs/schema_taxonomy.yaml` - Job classification taxonomy
- **Architecture:** `docs/system_architecture.yaml` - System design document
- **Implementation Notes:** `docs/archive/session_2025-12-02_backfill/SCHEMA_ENHANCEMENT_SUMMARY.md`
