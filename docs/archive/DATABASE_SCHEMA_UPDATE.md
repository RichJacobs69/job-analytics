# Database Schema Update: ATS Source Support

## Overview
This document describes the schema update needed to support multiple ATS (Applicant Tracking System) sources in addition to the Adzuna API.

## Current Status
- ❌ **BLOCKED**: Greenhouse jobs cannot be inserted into Supabase
- **Reason**: `raw_jobs.source` column only accepts 'adzuna' as valid value

## What Needs to Change
The `raw_jobs` table has a CHECK constraint (`valid_source`) that validates the source field. Currently it only allows:
- `adzuna` (existing)

We need to expand it to support all planned ATS systems:
- ✅ **adzuna** (API)
- ✅ **greenhouse** (implemented - web scraper)
- 🔜 **ashby** (planned scraper)
- 🔜 **lever** (planned scraper)
- 🔜 **workable** (planned scraper)
- 🔜 **smartrecruiters** (planned scraper)
- 🔜 **bamboohr** (planned scraper)
- 🔜 **recruitee** (planned scraper)
- 🔜 **comeet** (planned scraper)
- 🔜 **taleo** (planned scraper)
- 🔜 **workday** (planned scraper)
- 🔜 **custom** (manual/internal jobs)

Reference: `config/supported_ats.yaml`

## How to Apply the Update

### Method: Supabase SQL Editor (Recommended)

1. **Log into Supabase Dashboard**
   - Go to https://supabase.com
   - Select your project
   - Navigate to **SQL Editor** (left sidebar)

2. **Create New Query**
   - Click **New Query**
   - Name it: `Update: Add ATS Source Support`

3. **Paste the SQL**
   Copy and paste the entire SQL from `update_supabase_schema.sql`:

```sql
-- Step 1: Drop the existing constraint
ALTER TABLE raw_jobs DROP CONSTRAINT valid_source;

-- Step 2: Add new constraint with all supported sources
ALTER TABLE raw_jobs
ADD CONSTRAINT valid_source
CHECK (source IN (
  'adzuna',
  'greenhouse',
  'ashby',
  'lever',
  'workable',
  'smartrecruiters',
  'bamboohr',
  'recruitee',
  'comeet',
  'taleo',
  'workday',
  'custom',
  'linkedin_rss',
  'manual',
  'internal'
));
```

4. **Execute**
   - Click **Run** (blue button)
   - You should see: `"Executed successfully with 0 rows affected"`

5. **Verify**
   - Run this verification query:
   ```sql
   -- Check the constraint exists
   SELECT constraint_name, constraint_definition
   FROM information_schema.constraint_column_usage
   WHERE table_name='raw_jobs' AND column_name='source';
   ```
   - Should return one row with `valid_source` constraint

## After Update

Once the schema is updated, you can:

1. **Insert Greenhouse jobs** into `raw_jobs` table ✅
2. **Insert classified jobs** into `enriched_jobs` table ✅
3. **Prepare for future ATS integrations** (ashby, lever, workable, etc.)

## Testing the Update

Run the Greenhouse insertion test:
```bash
python test_insert_greenhouse.py
```

Expected output:
```
[STEP 1] Testing Supabase connection...
[OK] Connected to Supabase successfully

[STEP 2] Loading Greenhouse jobs...
[OK] Loaded 10 jobs from test_greenhouse_jobs.json

[STEP 3] Inserting Greenhouse jobs into database...

[Job 1] Account Executive - Enterprise...
  [OK] Raw job inserted (ID: xxxx)
  [OK] Job classified
    - Family: out_of_scope
    - Subfamily: None
    - Seniority: senior
  [OK] Enriched job inserted (ID: xxxx)

[Job 2] Account Executive - Startups, India...
  [OK] Raw job inserted (ID: xxxx)
  ...
```

## Timeline

| When | What |
|------|------|
| **Now** | ✅ Update Supabase schema with `update_supabase_schema.sql` |
| **After schema update** | ✅ Test Greenhouse insertion with `test_insert_greenhouse.py` |
| **Next phase** | 🔜 Build scrapers for other ATS systems (ashby, lever, workable, etc.) |

## Questions?

- **Where is the SQL file?** → `update_supabase_schema.sql` in the project root
- **Did it work?** → Check Supabase dashboard → SQL Editor → View recent queries and their status
- **What if it fails?** → Error message will appear in SQL Editor; check constraint name in error

## Related Documentation

- `config/supported_ats.yaml` - Complete list of ATS systems
- `docs/architecture/DUAL_PIPELINE.md` - Data source architecture
- `update_supabase_schema.sql` - The SQL to run
