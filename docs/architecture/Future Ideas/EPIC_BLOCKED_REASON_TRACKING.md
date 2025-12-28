# Epic: Blocked Reason Tracking for Raw Jobs

**Status:** Planning
**Created:** 2025-12-24
**Priority:** Medium (Pipeline Clarity / Backfill Efficiency)

## Problem Statement

Currently, jobs are written to `raw_jobs` before filtering decisions are made. When a job is blocked (e.g., agency hard filter), it remains in `raw_jobs` without a corresponding `enriched_jobs` record, and there's no indication of WHY it was blocked.

This causes issues:

1. **Backfill inefficiency:** The `backfill_missing_enriched.py` script finds all raw_jobs without enriched counterparts and attempts to process them - including intentionally blocked jobs
2. **No audit trail:** Cannot determine why a job wasn't enriched
3. **Misleading metrics:** "Missing" jobs count includes both failures AND intentional blocks

### Evidence (2025-12-24 Adzuna Run)

```
Backfill dry-run output:
  Found 504 total raw jobs (last hour)
  115 raw_jobs are missing from enriched_jobs

Actual breakdown:
  - ~6 classification failures (429 rate limit)
  - ~65 agency hard filter blocks (intentional)
  - ~44 unclear (likely more agencies)

Backfill would waste API calls on 65+ agency jobs that should never be enriched.
```

### Current Flow (Problem)

```
1. Upsert to raw_jobs         [Job written]
2. Check duplicate            [Skip if duplicate]
3. Check agency hard filter   [Skip if agency - NO RECORD OF WHY]
4. Classify with Claude
5. Write to enriched_jobs
```

Result: raw_job exists, no enriched_job, no indication it was intentionally blocked.

## Proposed Solution

Add a `blocked_reason` column to `raw_jobs` to track why a job wasn't enriched.

### Schema Change

```sql
ALTER TABLE raw_jobs ADD COLUMN blocked_reason TEXT NULL;

-- Optional index for filtering
CREATE INDEX idx_raw_jobs_blocked_reason ON raw_jobs(blocked_reason) WHERE blocked_reason IS NOT NULL;
```

### Blocked Reason Values

| Value | Meaning | Backfill Action |
|-------|---------|-----------------|
| `NULL` | Not blocked (has enriched OR needs retry) | Process if no enriched record |
| `agency_hard_filter` | Blocked by agency blacklist | Skip - intentional |
| `description_too_short` | Description < 50 chars (future) | Skip - cannot classify |
| `out_of_scope` | Classified as out_of_scope (future) | Skip - not relevant |

### New Flow

```
1. Upsert to raw_jobs         [Job written]
2. Check duplicate            [Skip if duplicate]
3. Check agency hard filter   [UPDATE blocked_reason='agency_hard_filter', skip]
4. Classify with Claude
5. Write to enriched_jobs
```

## Implementation Plan

### Phase 1: Schema Migration

**Database:** Supabase

```sql
-- Add column
ALTER TABLE raw_jobs ADD COLUMN blocked_reason TEXT NULL;

-- Add index for efficient filtering
CREATE INDEX idx_raw_jobs_blocked_reason ON raw_jobs(blocked_reason);
```

**Estimated effort:** 10 minutes

### Phase 2: Add helper function

**File:** `pipeline/db_connection.py`

```python
def update_raw_job_blocked_reason(raw_job_id: int, reason: str) -> None:
    """
    Update the blocked_reason for a raw_job.

    Args:
        raw_job_id: ID of the raw_job to update
        reason: Block reason (e.g., 'agency_hard_filter')
    """
    supabase.table("raw_jobs").update({
        "blocked_reason": reason
    }).eq("id", raw_job_id).execute()
```

**Estimated effort:** 15 minutes

### Phase 3: Update Greenhouse pipeline

**File:** `pipeline/fetch_jobs.py` - `process_greenhouse_incremental()` (~line 459-462)

```python
# Current:
if is_agency_job(job.company):
    stats['jobs_agency_filtered'] += 1
    logger.info(f"  [{i}/{len(jobs)}] AGENCY (hard filter): Skipped")
    continue

# New:
if is_agency_job(job.company):
    stats['jobs_agency_filtered'] += 1
    update_raw_job_blocked_reason(raw_job_id, 'agency_hard_filter')
    logger.info(f"  [{i}/{len(jobs)}] AGENCY (hard filter): Skipped")
    continue
```

**Estimated effort:** 15 minutes

### Phase 4: Update Adzuna pipeline

**File:** `pipeline/fetch_jobs.py` - `process_adzuna_incremental()` (~line 822-825)

Same pattern as Greenhouse.

**Estimated effort:** 10 minutes

### Phase 5: Update Lever pipeline

**File:** `pipeline/fetch_jobs.py` - `process_lever_incremental()` (~line 1125-1129)

Same pattern as Greenhouse.

**Estimated effort:** 10 minutes

### Phase 6: Update backfill script

**File:** `pipeline/utilities/backfill_missing_enriched.py`

Update `find_missing_enriched_jobs()` to exclude blocked jobs:

```python
# Current (line 113):
missing_jobs = [job for job in raw_jobs if job['id'] not in enriched_raw_ids]

# New:
missing_jobs = [
    job for job in raw_jobs
    if job['id'] not in enriched_raw_ids
    and job.get('blocked_reason') is None
]

# Update logging
logger.info(f"  {len(missing_jobs)} raw_jobs are missing from enriched_jobs (excluding blocked)")
blocked_count = len([j for j in raw_jobs if j.get('blocked_reason')])
if blocked_count:
    logger.info(f"  {blocked_count} raw_jobs intentionally blocked (skipped)")
```

**Estimated effort:** 20 minutes

### Phase 7: One-time backfill of existing data

**File:** `pipeline/utilities/backfill_blocked_reason.py` (new script)

```python
"""
One-time migration: Set blocked_reason for existing raw_jobs.

Finds raw_jobs without enriched counterpart and checks if they're agencies.
"""
from pipeline.db_connection import supabase
from pipeline.agency_detection import is_agency_job

def backfill_blocked_reasons():
    # Find raw_jobs without enriched records
    # Check if company matches agency blacklist
    # Update blocked_reason for matches
    pass

if __name__ == "__main__":
    backfill_blocked_reasons()
```

**Estimated effort:** 45 minutes

### Phase 8: Testing

1. **Unit test:** `update_raw_job_blocked_reason()` function
2. **Integration test:** Run pipeline, verify blocked_reason set for agency jobs
3. **Backfill test:** Run backfill, verify blocked jobs skipped
4. **Query test:** Verify analytics queries work

**Estimated effort:** 30 minutes

## Files Modified

| File | Changes |
|------|---------|
| `pipeline/db_connection.py` | Add `update_raw_job_blocked_reason()` |
| `pipeline/fetch_jobs.py` | Update 3 pipeline functions to set blocked_reason |
| `pipeline/utilities/backfill_missing_enriched.py` | Filter out blocked jobs |
| `pipeline/utilities/backfill_blocked_reason.py` | New one-time migration script |

## Metrics

### Before (2025-12-24 example)

```
Backfill finds: 115 "missing" jobs
Actually need processing: ~6
Wasted API calls if run: 109
```

### After

```
Backfill finds: 6 missing jobs (blocked excluded)
All 6 need processing: Yes
Wasted API calls: 0
```

### Analytics Queries Enabled

```sql
-- Block reason distribution
SELECT blocked_reason, COUNT(*)
FROM raw_jobs
WHERE blocked_reason IS NOT NULL
GROUP BY blocked_reason;

-- Agency block rate by source
SELECT source, COUNT(*)
FROM raw_jobs
WHERE blocked_reason = 'agency_hard_filter'
GROUP BY source;

-- Jobs needing backfill (truly missing)
SELECT COUNT(*)
FROM raw_jobs r
LEFT JOIN enriched_jobs e ON r.id = e.raw_job_id
WHERE e.id IS NULL AND r.blocked_reason IS NULL;
```

## Rollout Plan

1. Apply schema migration to Supabase
2. Deploy code changes to all 3 pipelines
3. Run one-time backfill for existing raw_jobs
4. Verify backfill script correctly filters blocked jobs
5. Monitor pipeline logs for blocked_reason updates

## Future Considerations

1. **Additional block reasons:**
   - `description_too_short` - Skip jobs with minimal description
   - `out_of_scope` - Jobs classified as out_of_scope (optional)
   - `duplicate_cross_source` - Same job from different sources (ties into EPIC_ENRICHED_DEDUP)

2. **Dashboard integration:**
   - Show blocked job counts in pipeline summary
   - Alert on unusual block rates

3. **Retention policy:**
   - Consider purging old blocked raw_jobs after N days
   - Or archive to separate table

## Dependencies

- `pipeline/agency_detection.py` - `is_agency_job()` already exists
- Supabase schema access for migration

## Risks

| Risk | Mitigation |
|------|------------|
| Extra DB write per blocked job | Single UPDATE, minimal overhead (~2ms) |
| Backfill migration misses some jobs | Run multiple times, verify counts |
| New block reasons not handled | Default to NULL, backfill picks up |

## Sign-off

- [ ] Schema migration applied
- [ ] Code changes deployed
- [ ] Existing data backfilled
- [ ] Backfill script verified
- [ ] Documentation updated
