# Schema Enhancement: Add Title and Company to raw_jobs (2025-12-02)

## Problem Identified

The `raw_jobs` table was missing key source metadata:
- **Title**: Original job title from source (lost after classification)
- **Company**: Original company name from source (lost after classification)

This meant:
- Can't analyze raw jobs without joining enriched_jobs
- No fallback data if classification fails
- Poor audit trail for data lineage
- Need joins to enriched_jobs for basic queries

## Solution

Added `title` and `company` as first-class fields in the `raw_jobs` table.

### Code Changes

#### 1. Updated `pipeline/db_connection.py`

**Function:** `insert_raw_job()`

Added two new optional parameters:
```python
def insert_raw_job(
    source: str,
    posting_url: str,
    raw_text: str,
    source_job_id: Optional[str] = None,
    title: Optional[str] = None,          # NEW
    company: Optional[str] = None,        # NEW
    metadata: Optional[Dict] = None,
    full_text: Optional[str] = None,
    text_source: Optional[str] = None
) -> int:
```

Benefits:
- ✅ Backward compatible (optional parameters)
- ✅ Null-safe (handle missing values gracefully)
- ✅ Clear intent (parameters describe data)
- ✅ No breaking changes (existing code still works)

#### 2. Updated `pipeline/fetch_jobs.py`

**Location:** Line 295-302 (raw job insertion)

Added title and company to the insert call:
```python
raw_job_id = insert_raw_job(
    source=source,
    posting_url=url,
    title=title,            # NEW
    company=company,        # NEW
    raw_text=description,
    source_job_id=job_id
)
```

Now captures:
- ✅ Original job title from Adzuna
- ✅ Original company name from Adzuna
- ✅ All other raw metadata

### Database Schema Migration

#### Script: `pipeline/utilities/migrate_raw_jobs_schema.py`

**Purpose:** Generate SQL migration script for Supabase

**What it does:**
1. Displays migration SQL script
2. Provides step-by-step instructions
3. Explains the changes and benefits
4. Provides rollback instructions

**Usage:**
```bash
python wrapper/migrate_raw_jobs_schema.py
```

**Output:**
```sql
ALTER TABLE raw_jobs
ADD COLUMN IF NOT EXISTS title TEXT;

ALTER TABLE raw_jobs
ADD COLUMN IF NOT EXISTS company TEXT;

CREATE INDEX IF NOT EXISTS idx_raw_jobs_title ON raw_jobs(title);
CREATE INDEX IF NOT EXISTS idx_raw_jobs_company ON raw_jobs(company);
```

#### How to Apply the Migration

**Option 1: Supabase Dashboard (Easy)**
1. Go to https://app.supabase.com
2. Select your project
3. Click "SQL Editor"
4. Click "New Query"
5. Copy SQL from `python wrapper/migrate_raw_jobs_schema.py`
6. Click "Run"

**Option 2: Supabase CLI**
```bash
supabase db push
```

**Option 3: Direct SQL**
Paste the SQL into your preferred Supabase SQL client

### Schema After Migration

```sql
Table: raw_jobs

Column            | Type          | Nullable | Notes
------------------+---------------+----------+---------------------------
id                | bigint        | NO       | Primary key
source            | text          | NO       | 'adzuna', 'greenhouse', etc
posting_url       | text          | NO       | Unique constraint
raw_text          | text          | NO       | Full job description
source_job_id     | text          | YES      | External ID
title             | text          | YES      | Original job title (NEW)
company           | text          | YES      | Original company (NEW)
metadata          | jsonb         | YES      | Additional metadata
full_text         | text          | YES      | Greenhouse full description
text_source       | text          | YES      | Where full_text came from
scraped_at        | timestamp     | NO       | When job was scraped
created_at        | timestamp     | NO       | When record was created
updated_at        | timestamp     | NO       | Last update

Indexes:
  idx_raw_jobs_posting_url (UNIQUE)
  idx_raw_jobs_source
  idx_raw_jobs_scraped_at
  idx_raw_jobs_title (NEW)
  idx_raw_jobs_company (NEW)
```

## Benefits

### Immediate
- ✅ Preserve source title and company without classification
- ✅ Fallback data when classification fails
- ✅ Better audit trail (what did Adzuna say vs what did Claude classify?)

### Analytics
- ✅ Query raw_jobs directly (no join to enriched_jobs)
- ✅ Compare title variations across sources
- ✅ Analyze company name variations
- ✅ Track data lineage

### Performance
- ✅ Indexes on title and company for fast queries
- ✅ Reduce need for table joins
- ✅ Support for WHERE clauses on title/company

## Backward Compatibility

✅ **Fully backward compatible**

- Existing code continues to work (parameters are optional)
- Existing data is unchanged (new columns are nullable)
- New jobs will populate title and company
- Old jobs will have NULL values (can be backfilled if needed)

## Migration Impact

### On Adzuna Jobs (fetch_jobs.py)
- ✅ Will now store original Adzuna title
- ✅ Will now store original Adzuna company
- ✅ No other changes

### On Greenhouse Jobs
- ⚠️ Will store NULL (Greenhouse jobs don't use insert_raw_job)
- ℹ️ Could be added in future if needed

### On Existing Data
- ✅ No changes to existing rows
- ✅ New rows will populate fields
- ℹ️ Can backfill historical data if desired

## Rollback Instructions

If you need to remove the columns:

```sql
ALTER TABLE raw_jobs DROP COLUMN IF EXISTS title;
ALTER TABLE raw_jobs DROP COLUMN IF EXISTS company;
```

This is fully reversible with no data loss (since columns start empty).

## Next Steps

1. **Run migration script:**
   ```bash
   python wrapper/migrate_raw_jobs_schema.py
   ```

2. **Apply SQL to Supabase:**
   - Copy the SQL output
   - Paste into Supabase SQL Editor
   - Click "Run"

3. **Verify schema:**
   - Open Supabase Dashboard
   - Check raw_jobs table
   - Confirm title and company columns exist

4. **Test the pipeline:**
   ```bash
   python wrapper/fetch_jobs.py lon 10 --sources adzuna
   ```

5. **Verify data:**
   - Check Supabase raw_jobs table
   - Confirm title and company are populated

## Files Modified

```
pipeline/db_connection.py
  └─ insert_raw_job() - Added title and company parameters

pipeline/fetch_jobs.py
  └─ store_jobs() - Pass title and company to insert_raw_job

pipeline/utilities/migrate_raw_jobs_schema.py (NEW)
  └─ Migration script with SQL and instructions

wrapper/migrate_raw_jobs_schema.py (NEW)
  └─ Wrapper to call migration script
```

## Testing the Changes

After applying the migration:

```bash
# Fetch a small batch of Adzuna jobs
python wrapper/fetch_jobs.py lon 5 --sources adzuna --skip-classification

# Check the database
# In Supabase Dashboard:
#   1. Go to Table Editor
#   2. Select raw_jobs
#   3. Verify title and company columns are populated
```

## Questions & Troubleshooting

**Q: What if title or company is None?**
A: They're stored as NULL in the database. That's expected for sources without those fields.

**Q: Will this slow down inserts?**
A: No. Adding optional columns doesn't impact insert performance, and the indexes only speed up queries.

**Q: Can I populate historical data?**
A: Yes, with a backfill script. The data is in the job descriptions, but would require re-parsing.

**Q: What about Greenhouse jobs?**
A: They currently use a different insert path. Could be added in future if needed.

---

**Status:** Ready to migrate
**Applied:** Not yet (awaiting user action)
**Rollback:** Yes (fully reversible)

