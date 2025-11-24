# Schema Updates for Dual Pipeline

**Status:** Ready for migration
**Date:** November 21, 2025
**Purpose:** Add source tracking columns for Adzuna + Greenhouse dual pipeline

---

## Summary

The dual pipeline requires tracking which data source provided each job and which source provided the description used for classification. The existing schema already has `source` and `full_text` columns in `raw_jobs`, but we need to add source tracking to `enriched_jobs` for analytics and debugging.

---

## Changes Required

### 1. Add Columns to `enriched_jobs` Table

**New columns:**
- `data_source` (VARCHAR 50) - Primary data source: 'adzuna', 'greenhouse', or 'hybrid'
- `description_source` (VARCHAR 50) - Which source provided the description: 'adzuna' or 'greenhouse'
- `deduplicated` (BOOLEAN) - Whether this job was deduplicated from multiple sources
- `original_url_secondary` (VARCHAR 2048) - Secondary URL if merged from another source
- `merged_from_source` (VARCHAR 50) - If deduplicated, which source was merged with this one

### 2. Add Indexes for Performance

**New indexes:**
- `idx_enriched_jobs_data_source` - For filtering/grouping by source
- `idx_enriched_jobs_deduplicated` - For finding merged jobs
- `idx_enriched_jobs_description_source` - For quality analysis by source

---

## Migration Steps

### Step 1: Run SQL Migration

Execute the migration file in your Supabase SQL editor:

```bash
# File: migrations/001_add_source_tracking.sql
```

**Or manually in Supabase:**

1. Go to Supabase Dashboard → SQL Editor
2. Create new query
3. Copy and paste content from `migrations/001_add_source_tracking.sql`
4. Click "Run" button
5. Verify success (no errors)

### Step 2: Update Python Code

The `db_connection.py` file has already been updated with:
- New parameters in `insert_enriched_job()` function
- Defaults for backward compatibility (data_source defaults to 'adzuna')

**No further code changes needed** - the database code is ready to use.

### Step 3: Verify Migration

```bash
# Connect to Supabase and verify columns exist
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'enriched_jobs'
AND column_name IN ('data_source', 'description_source', 'deduplicated');
```

---

## Schema Details

### Column Descriptions

#### `data_source` (VARCHAR 50)
- **Purpose:** Track primary data source for the job
- **Values:**
  - 'adzuna' - Job came from Adzuna API only
  - 'greenhouse' - Job came from Greenhouse scraper only
  - 'hybrid' - Job merged from both sources
- **Default:** 'adzuna'
- **Used for:** Analytics, filtering, understanding data coverage

#### `description_source` (VARCHAR 50)
- **Purpose:** Track which source provided the description used for classification
- **Values:**
  - 'adzuna' - Using Adzuna's truncated description (~100-200 chars)
  - 'greenhouse' - Using Greenhouse's full description (~9,000-15,000 chars)
- **Default:** 'adzuna'
- **Used for:** Quality metrics, classification confidence scoring
- **Impact:** Jobs with 'greenhouse' descriptions are expected to have better classification accuracy

#### `deduplicated` (BOOLEAN)
- **Purpose:** Flag indicating if this job was merged from multiple sources
- **Values:**
  - FALSE (default) - Job from single source only
  - TRUE - Job found in both Adzuna and Greenhouse, merged as one
- **Used for:** Understanding deduplication rate, finding merged jobs
- **Example query:** "How many Greenhouse jobs also appeared on Adzuna?"

#### `original_url_secondary` (VARCHAR 2048)
- **Purpose:** Store secondary URL if job was merged from another source
- **Example:** If Adzuna job was merged with Greenhouse job:
  - `url` = Greenhouse URL (primary)
  - `original_url_secondary` = Adzuna URL
- **Used for:** Traceability, comparing job postings from both sources
- **Nullable:** Yes (NULL if not deduplicated)

#### `merged_from_source` (VARCHAR 50)
- **Purpose:** Track which source was merged into this job
- **Values:**
  - NULL (default) - Not a merged job
  - 'adzuna' - Adzuna job was merged into this (Greenhouse primary)
  - 'greenhouse' - Greenhouse job was merged into this (Adzuna primary, rare)
- **Used for:** Understanding merge direction and source priority decisions

---

## Example Usage in Code

### Storing a Greenhouse Job

```python
from db_connection import insert_enriched_job
from datetime import date

insert_enriched_job(
    raw_job_id=123,
    employer_name="Stripe",
    title_display="Backend Engineer, Data",
    job_family="data",
    city_code="lon",
    working_arrangement="hybrid",
    position_type="full_time",
    posted_date=date.today(),
    last_seen_date=date.today(),
    job_subfamily="data_engineer",
    seniority="senior",
    # New parameters for dual pipeline
    data_source="greenhouse",
    description_source="greenhouse",
    deduplicated=False,
    original_url_secondary=None,
    merged_from_source=None
)
```

### Storing a Deduplicated Job

```python
# Job found in both Adzuna and Greenhouse - we chose Greenhouse
insert_enriched_job(
    raw_job_id=456,
    employer_name="Figma",
    title_display="Product Manager",
    job_family="product",
    city_code="nyc",
    working_arrangement="remote",
    position_type="full_time",
    posted_date=date.today(),
    last_seen_date=date.today(),
    # New parameters for dual pipeline
    data_source="hybrid",  # From both sources
    description_source="greenhouse",  # Used Greenhouse's better description
    deduplicated=True,  # This was a merge
    original_url_secondary="https://www.adzuna.com/...",  # Original Adzuna URL
    merged_from_source="adzuna"  # We merged Adzuna into this
)
```

### Querying by Source in Analytics

```sql
-- How many jobs came from each source?
SELECT data_source, COUNT(*) as job_count
FROM enriched_jobs
GROUP BY data_source;

-- How many jobs were deduplicated?
SELECT COUNT(*) as deduplicated_count
FROM enriched_jobs
WHERE deduplicated = TRUE;

-- How many jobs have full Greenhouse descriptions?
SELECT COUNT(*) as greenhouse_desc_count
FROM enriched_jobs
WHERE description_source = 'greenhouse';

-- Classification quality by description source
SELECT
    description_source,
    COUNT(*) as total_jobs,
    ROUND(AVG(CASE WHEN is_agency = FALSE THEN 1 ELSE 0 END), 2) as non_agency_rate
FROM enriched_jobs
GROUP BY description_source;
```

---

## Backward Compatibility

✓ **Fully backward compatible**

- All new columns are nullable (default values provided)
- Existing code without source parameters still works
- Jobs stored without source info will default to 'adzuna' source
- No breaking changes to existing functionality

---

## Testing the Migration

### Quick Verification

After running the migration, verify in Supabase SQL Editor:

```sql
-- Check columns exist
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'enriched_jobs'
AND column_name LIKE '%source%' OR column_name = 'deduplicated';

-- Should see 5 new columns:
-- - data_source
-- - description_source
-- - deduplicated
-- - original_url_secondary
-- - merged_from_source

-- Check indexes exist
SELECT indexname
FROM pg_indexes
WHERE tablename = 'enriched_jobs'
AND indexname LIKE 'idx_enriched_jobs_%source%'
OR indexname = 'idx_enriched_jobs_deduplicated';
```

### Test Insertion

After migration, test inserting a job with source tracking:

```python
from db_connection import insert_enriched_job
from datetime import date

# Test insertion with new fields
result = insert_enriched_job(
    raw_job_id=999,
    employer_name="Test Company",
    title_display="Test Job",
    job_family="data",
    city_code="lon",
    working_arrangement="hybrid",
    position_type="full_time",
    posted_date=date.today(),
    last_seen_date=date.today(),
    data_source="greenhouse",
    description_source="greenhouse",
    deduplicated=False
)
print(f"Job inserted with ID: {result}")
```

---

## Rollback Plan (If Needed)

If you need to revert the migration:

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

**Note:** This would lose any source tracking data already stored. Only use in emergencies.

---

## Implementation Timeline

1. **Before Phase 4:** Run migration (5 minutes)
2. **During Phase 4:** Greenhouse scraping stores jobs with source tracking
3. **Post-Phase 4:** Analytics can filter by source and measure deduplication

---

## Analytics Benefits

With source tracking, you can now:

✓ **Measure deduplication rate:** "Of X Adzuna jobs, Y% also appeared on Greenhouse"
✓ **Understand coverage:** "60% of final dataset came from Greenhouse, 40% from Adzuna"
✓ **Quality analysis:** "Jobs with Greenhouse descriptions have 85%+ F1 score vs 60% for Adzuna"
✓ **Source-specific insights:** "Analyze trends separately by data source"
✓ **Cost optimization:** "Track cost-benefit of Greenhouse vs Adzuna scraping"

---

**Migration Status:** READY
**Backward Compatible:** YES
**Implementation Time:** < 5 minutes
**No code changes required:** Uses updated db_connection.py
