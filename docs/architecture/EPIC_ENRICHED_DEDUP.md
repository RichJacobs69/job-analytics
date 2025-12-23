# Epic: Enriched Jobs Pre-Classification Deduplication

**Status:** Planning
**Created:** 2025-12-23
**Priority:** Medium (Cost Optimization)

## Problem Statement

Currently, jobs are deduplicated at two points:
1. **raw_jobs**: By `(source, source_job_id)` - catches same posting from same source
2. **enriched_jobs**: By `job_hash` (company|title|city) - catches duplicates via upsert

The gap: When a job has a **new source_job_id** but **same content** (same company, title, city), we:
1. Pass raw_jobs check (new source_job_id)
2. Classify with Claude (~$0.004)
3. Upsert to enriched_jobs (updates existing record)

**Result:** Wasted classification cost on jobs we already have.

### Evidence (Waymo Example - 2025-12-23)

```
Jobs processed: 71
Truly new (201 Created): ~5
Updates to existing (200 OK): ~66
Wasted classification cost: ~$0.26
```

Common causes:
- Same job posted in multiple locations on the board
- Job reposted with new Greenhouse ID
- Duplicate listings (same title/company/city, different posting IDs)

## Proposed Solution

Add a pre-classification check against `enriched_jobs` table using `job_hash`.

### Current Flow
```
Scrape job
    |
    v
insert_raw_job_upsert(source_job_id)
    |-- Duplicate? --> Skip (was_duplicate=True)
    |
    v (NEW)
Hard agency filter
    |
    v
classify_job_with_claude()  <-- $0.004 COST
    |
    v
extract_locations()
    |
    v
insert_enriched_job(job_hash)  <-- May update existing!
```

### Proposed Flow
```
Scrape job
    |
    v
insert_raw_job_upsert(source_job_id)
    |-- Duplicate? --> Skip (was_duplicate=True)
    |
    v (NEW in raw_jobs)
extract_locations()  <-- MOVED UP
    |
    v
generate_job_hash(company, title, city_code)
    |
    v
check_enriched_exists(job_hash)  <-- NEW
    |-- Exists? --> Skip classification, log "DUPLICATE (enriched)"
    |
    v (NEW in enriched_jobs)
Hard agency filter
    |
    v
classify_job_with_claude()  <-- Only for truly new jobs
    |
    v
insert_enriched_job(job_hash)
```

## Implementation Plan

### Phase 1: Add enriched_jobs lookup function

**File:** `pipeline/db_connection.py`

Add new function:
```python
def check_enriched_job_exists(job_hash: str) -> Optional[int]:
    """
    Check if an enriched job with this hash already exists.

    Args:
        job_hash: MD5 hash of (employer_name|title|city_code)

    Returns:
        enriched_job_id if exists, None otherwise
    """
    result = supabase.table("enriched_jobs").select("id").eq("job_hash", job_hash).limit(1).execute()
    if result.data:
        return result.data[0]["id"]
    return None
```

**Estimated effort:** 15 minutes

### Phase 2: Create helper for early location extraction

**File:** `pipeline/fetch_jobs.py`

Add helper function to derive legacy city_code from raw location:
```python
def derive_city_code_from_location(raw_location: str) -> str:
    """
    Extract city code from raw location string for hash generation.

    Used for enriched_jobs pre-check before classification.
    """
    if not raw_location or raw_location == 'Unspecified':
        return 'unk'

    extracted = extract_locations(raw_location)
    if extracted and extracted[0].get('type') == 'city':
        city_name = extracted[0].get('city', '')
        city_to_code = {
            'london': 'lon',
            'new_york': 'nyc',
            'denver': 'den',
            'san_francisco': 'sfo',
            'singapore': 'sgp'
        }
        return city_to_code.get(city_name, 'unk')
    elif extracted and extracted[0].get('type') == 'remote':
        return 'remote'
    return 'unk'
```

**Estimated effort:** 20 minutes

### Phase 3: Update Greenhouse pipeline

**File:** `pipeline/fetch_jobs.py` - `process_greenhouse_incremental()`

Changes at lines ~450-470:
```python
# After raw_jobs insert, before classification:

# Step 2: Pre-check enriched_jobs by hash (NEW)
city_code = derive_city_code_from_location(job.location)
job_hash = generate_job_hash(job.company, job.title, city_code)
existing_enriched_id = check_enriched_job_exists(job_hash)

if existing_enriched_id:
    stats['jobs_enriched_duplicate'] += 1
    company_jobs_enriched_dup += 1
    logger.info(f"  [{i}/{len(jobs)}] DUPLICATE (enriched): {job.title[:50]}... (skipped)")
    continue

# Step 3: Hard filter - check if agency before classification
# ... existing code ...
```

**Estimated effort:** 30 minutes

### Phase 4: Update Lever pipeline

**File:** `pipeline/fetch_jobs.py` - `process_lever_incremental()`

Same pattern as Greenhouse, at lines ~1115-1125.

**Estimated effort:** 20 minutes

### Phase 5: Update Adzuna pipeline

**File:** `pipeline/fetch_jobs.py` - `process_adzuna_incremental()`

Same pattern, at lines ~820-830.

**Estimated effort:** 20 minutes

### Phase 6: Update statistics and logging

Add new stats tracking:
- `jobs_enriched_duplicate`: Count of jobs skipped due to enriched pre-check
- `cost_saved_enriched_dedup`: Estimated cost saved (~$0.00388 * count)

Update pipeline summary output to show:
```
Company Summary:
  - New jobs written: 71
  - Duplicates skipped (raw): 0
  - Duplicates skipped (enriched): 66  <-- NEW
  - Agencies blocked: 0
  - Jobs classified: 5
  - Cost saved (enriched dedup): $0.26  <-- NEW
```

**Estimated effort:** 30 minutes

### Phase 7: Testing

1. **Unit test:** `check_enriched_job_exists()` function
2. **Unit test:** `derive_city_code_from_location()` function
3. **Integration test:** Run Greenhouse scraper on company with known duplicates (Waymo)
4. **Verify:** Duplicates logged correctly, classifications skipped

**Estimated effort:** 45 minutes

## Files Modified

| File | Changes |
|------|---------|
| `pipeline/db_connection.py` | Add `check_enriched_job_exists()` |
| `pipeline/fetch_jobs.py` | Add `derive_city_code_from_location()`, update 3 pipeline functions |
| `tests/test_deduplication.py` | New test file for dedup logic |

## Metrics

### Before (Waymo example)
- Jobs classified: 71
- Truly new: 5
- Classification cost: $0.28

### After (projected)
- Jobs classified: 5
- Duplicates skipped: 66
- Classification cost: $0.02
- Cost saved: $0.26 (93% reduction for this company)

### Expected Impact (pipeline-wide)
- Estimated 10-20% of jobs are enriched duplicates across all companies
- Savings: ~$0.05-0.10 per batch run
- Adds ~2-3ms latency per job (DB query)

## Rollout Plan

1. Implement in feature branch
2. Test locally with single company (Waymo)
3. Run full Greenhouse batch, compare stats to previous run
4. Monitor for any edge cases (hash collisions, false positives)
5. Merge to master

## Future Considerations

1. **Deprecate city_code entirely:** Once locations JSONB is fully adopted, update hash to use locations instead
2. **Cross-source deduplication:** Same job from Adzuna and Greenhouse should dedupe
3. **Hash migration:** Consider rehashing existing enriched_jobs if hash algorithm changes

## Dependencies

- `pipeline/location_extractor.py` - Already exists, no changes needed
- `pipeline/db_connection.py` - `generate_job_hash()` already exists

## Risks

| Risk | Mitigation |
|------|------------|
| Hash collision (different jobs, same hash) | Low probability with MD5; monitor for unexpected dedup |
| Location extraction errors causing wrong hash | Use 'unk' as fallback; same behavior as current |
| Performance impact from extra DB query | Single indexed query, ~2-3ms; net positive from saved API calls |

## Sign-off

- [ ] Implementation complete
- [ ] Tests passing
- [ ] Deployed to production
- [ ] Metrics validated
