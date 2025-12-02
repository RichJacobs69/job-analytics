# Database Schema Updates

**Last Updated:** December 2, 2025
**Status:** All migrations complete and verified

This document tracks all database schema changes for the job-analytics platform.

---

## Table of Contents

1. [Migration 1: Source Tracking (enriched_jobs)](#migration-1-source-tracking-enriched_jobs)
2. [Migration 2: Title and Company Fields (raw_jobs)](#migration-2-title-and-company-fields-raw_jobs)
3. [Current Schema Reference](#current-schema-reference)

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
| employer_name | text | NO | Classified company name |
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
| **merged_from_source** | **text** | **YES** | **Which source was merged in (NEW)** |
| ... | ... | ... | (plus compensation, skills, dates, etc.) |

**Indexes:**
- `idx_enriched_jobs_job_hash` (UNIQUE)
- `idx_enriched_jobs_city_code`
- `idx_enriched_jobs_job_family`
- `idx_enriched_jobs_data_source` **(NEW)**
- `idx_enriched_jobs_deduplicated` **(NEW)**
- `idx_enriched_jobs_description_source` **(NEW)**

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

---

## References

- **Code:** `pipeline/db_connection.py` - Database interface implementation
- **Specs:** `docs/schema_taxonomy.yaml` - Job classification taxonomy
- **Architecture:** `docs/system_architecture.yaml` - System design document
- **Implementation Notes:** `docs/archive/session_2025-12-02_backfill/SCHEMA_ENHANCEMENT_SUMMARY.md`
