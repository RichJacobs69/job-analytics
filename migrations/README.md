# Database Migrations

This directory contains SQL migration scripts for schema changes.

## How to Run Migrations

**STEP 0: Data Cleanup (Required First)**

Before running any migrations, clean up NULL records:
```bash
python migrations/000_backfill_raw_jobs_metadata.py
```

This backfills company/title from enriched_jobs and deletes orphaned records.

**STEP 1: Deduplicate (Required Second)**

Remove duplicate jobs (same job scraped on multiple dates):
```bash
python migrations/001a_deduplicate_raw_jobs.py
```

Keeps most recent version of each job, deletes older duplicates.

**STEP 2: Run SQL Migration**

**Option 1: Supabase SQL Editor (Recommended)**
1. Go to your Supabase Dashboard: https://app.supabase.com
2. Navigate to: SQL Editor
3. Copy contents of migration file (e.g., `001_add_raw_jobs_hash.sql`)
4. Paste into SQL editor
5. Click "Run" to execute
6. Verify success with verification queries at bottom of migration file

**Option 2: Python Verification Script**
After running the SQL migration manually, verify it worked:
```bash
python migrations/verify_001_hash_migration.py
```

## Migration History

| # | File | Date | Description | Status |
|---|------|------|-------------|--------|
| 001 | `001_add_raw_jobs_hash.sql` | 2025-12-03 | Add hash column + unique constraint to raw_jobs | ⏳ Pending |
| 002 | `002_add_last_seen_timestamp.sql` | 2025-12-03 | Add last_seen column for resume capability | ⏳ Pending |
| 003 | `003_allow_unk_city_code.sql` | 2025-12-03 | Allow 'unk' as valid city_code | ✅ Done |
| 004 | `004_allow_remote_city_code.sql` | 2025-12-03 | Allow 'remote' as valid city_code | ✅ Done |
| 005 | `005_remove_hash_unique_constraint.sql` | 2025-12-03 | Remove hash unique constraint | ✅ Done |
| 006 | `006_unique_source_job_id.sql` | 2025-12-03 | Add unique constraint on source_job_id | ✅ Done |
| 007 | `007_allow_unknown_working_arrangement.sql` | 2025-12-14 | Allow 'unknown' as valid working_arrangement | ⏳ Pending |
| 008 | `008_add_locations_jsonb.sql` | 2025-12-18 | Add locations JSONB column for global expansion | ⏳ Pending |

## Current Migration: 001_add_raw_jobs_hash.sql

**Purpose:** Enable UPSERT-based deduplication for incremental pipeline writes

**Changes:**
- Adds `hash` column to `raw_jobs` table (TEXT, NOT NULL)
- Populates hash for existing records using MD5(company|title|unk)
- Adds UNIQUE constraint: `raw_jobs_hash_unique`
- Adds index for query performance: `idx_raw_jobs_hash`

**Risk Level:** LOW
- Non-destructive (only adds column + constraint)
- Existing data preserved
- Backwards compatible (old code continues to work)

**Rollback:**
```sql
-- If needed, rollback with:
ALTER TABLE raw_jobs DROP CONSTRAINT raw_jobs_hash_unique;
DROP INDEX idx_raw_jobs_hash;
ALTER TABLE raw_jobs DROP COLUMN hash;
```

---

## Migration 002: Add last_seen Timestamp

**Purpose:** Enable proper resume capability by tracking when jobs were last scraped

**Problem Solved:**
- Without `last_seen`, resume capability breaks after first window expires
- `scraped_at` only tracks first discovery, not recent processing
- Pipeline would wastefully re-scrape companies already processed

**Changes:**
- Adds `last_seen` column to `raw_jobs` table (TIMESTAMP WITH TIME ZONE, NOT NULL)
- Backfills existing records: `last_seen = scraped_at`
- Adds index: `idx_raw_jobs_source_last_seen` for resume queries
- Adds comments documenting the two timestamps

**Semantics:**
- `scraped_at`: When job was **first discovered** (immutable after insert)
- `last_seen`: When job was **last scraped/verified** (updated on every encounter)

**Risk Level:** LOW
- Non-destructive (only adds column + index)
- Existing data preserved
- Backwards compatible

**Rollback:**
```sql
DROP INDEX idx_raw_jobs_source_last_seen;
ALTER TABLE raw_jobs DROP COLUMN last_seen;
```

**Code Changes Required:**
- ✅ `insert_raw_job_upsert()` now updates `last_seen` on every call
- ✅ `get_recently_processed_companies()` queries `last_seen` instead of `scraped_at`

---

## Next Steps After Running Migrations

**For Migration 001:**
1. ✅ Run migration SQL in Supabase Dashboard
2. ✅ Run verification script: `python migrations/verify_001_hash_migration.py`
3. ✅ Test upsert function: `python -m tests.test_db_upsert`
4. ✅ Update code to use `insert_raw_job_upsert()` instead of `insert_raw_job()`

**For Migration 002:**
1. ⏳ Run migration SQL in Supabase Dashboard
2. ⏳ Verify column exists and has values (see verification queries in SQL file)
3. ⏳ Test resume capability: `python tests/test_resume_capability.py`
