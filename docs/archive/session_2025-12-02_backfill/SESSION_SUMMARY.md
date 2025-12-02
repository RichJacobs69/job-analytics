# Session Summary: Backfill Missing Enriched Jobs (2025-12-02)

## Problem Statement

User reported discrepancy between raw_jobs (409 rows) and enriched_jobs (79 rows) from a recent pipeline run. Investigation needed to determine if this was due to duplicates, bugs, or expected filtering behavior.

## Root Cause Analysis

### Key Findings

1. **Null job_family Bug** (PRIMARY ISSUE)
   - Claude API sometimes returns `job_family: null` instead of omitting the field
   - Code used `.get('job_family', 'out_of_scope')` which doesn't handle null values
   - Caused HTTP 400 Bad Request errors when inserting into enriched_jobs
   - **Fix:** Changed to `.get('job_family') or 'out_of_scope'` in fetch_jobs.py line 315

2. **UPSERT Behavior** (EXPECTED)
   - enriched_jobs table uses UPSERT on job_hash (company+title+city MD5)
   - Multiple raw_jobs with same hash update single enriched_job record
   - HTTP 200 OK responses instead of 201 Created indicate updates
   - This is intentional deduplication behavior

3. **Duplicate posting_url** (EXPECTED)
   - HTTP 409 Conflict errors on raw_jobs.posting_url unique constraint
   - Happens when same job URL scraped multiple times
   - Expected behavior - prevents duplicate raw entries

### Breakdown of 409 Raw Jobs

- **79 successfully inserted to enriched_jobs** (19.3%)
- **~118 failed due to null job_family bug** (28.8%)
- **~212 were UPSERT updates or duplicates** (51.9%)

## Solution Implemented

### 1. Bug Fix in fetch_jobs.py

**File:** `fetch_jobs.py`
**Line:** 315
**Change:**
```python
# BEFORE (broken):
job_family=role.get('job_family', 'out_of_scope'),

# AFTER (fixed):
job_family=role.get('job_family') or 'out_of_scope',
```

### 2. Backfill Script Created

**File:** `backfill_missing_enriched.py`

**Features:**
- Finds raw_jobs missing from enriched_jobs (with pagination for large datasets)
- Re-classifies through Claude API
- City inference from posting URLs (handles invalid 'unk' city codes)
- Null-safe employer name handling
- Graceful error handling for edge cases

**Results:**
- 118 missing jobs identified
- 93 successfully recovered (78.8% success rate)
- 25 failed due to missing employer/title info or invalid data
- Cost: $0.47 for re-classification

## Files Created (Archived)

All diagnostic files from this session have been archived in `docs/archive/session_2025-12-02_backfill/`:

1. **analyze_job_discrepancy.py** - Initial diagnostic script to analyze discrepancy
2. **detailed_job_analysis.py** - Detailed analysis with UPSERT detection
3. **check_schema.py** - Quick schema inspection utility
4. **monitor_progress.ps1** - PowerShell monitoring script (not integrated with Python pipeline)
5. **test_doubleverify_fix.py** - One-off test for company-specific fix

## Files Retained (Maintained Utilities)

Kept in root directory for ongoing use:

1. **backfill_missing_enriched.py** - Useful for future recovery scenarios (similar to backfill_agency_flags.py)
2. **analyze_db_results.py** - Comprehensive database analysis tool
3. **check_pipeline_status.py** - Quick status checks with pagination

## Lessons Learned

1. **Null-safety in Python:**
   - `.get(key, default)` doesn't catch null values from dictionaries
   - Use `.get(key) or default` for true null-safety

2. **Database constraints matter:**
   - NOT NULL constraints catch bugs at insert time
   - CHECK constraints (valid_city) prevent invalid data
   - Unique constraints (posting_url) prevent duplicates

3. **UPSERT vs INSERT:**
   - HTTP 200 OK = UPSERT updated existing record
   - HTTP 201 Created = new record inserted
   - HTTP 409 Conflict = unique constraint violation
   - HTTP 400 Bad Request = constraint violation (NULL, CHECK, etc.)

4. **Pagination is critical:**
   - Supabase limits queries to 1,000 records
   - Always implement pagination for complete data analysis
   - Use `range(offset, offset + page_size - 1)` pattern

## Validation

- ✅ Bug fix deployed to fetch_jobs.py
- ✅ 93 jobs recovered through backfill
- ✅ Future runs will use null-safe code
- ✅ Diagnostic scripts archived for reference
- ✅ Repository cleaned up and organized

## Status

**COMPLETE** - Issue resolved, backfill successful, repository tidied.
