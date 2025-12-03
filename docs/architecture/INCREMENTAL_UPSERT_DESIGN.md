# Incremental Upsert Architecture Design

**Date:** 2025-12-03
**Status:** IMPLEMENTED - Deployed 2025-12-03
**Problem Solved:** 3-hour pipeline runs with no database writes until the end = total data loss on failure

---

## Previous Architecture (Batch-Only) - REPLACED

```
1. Scrape ALL companies → List[UnifiedJob] (in-memory)
2. Merge ALL jobs → deduplicate in-memory
3. Classify ALL jobs → add classification data in-memory
4. Store ALL jobs → loop and insert to DB
```

**Problems:**
- ❌ 3+ hours of work held entirely in memory
- ❌ Single failure = lose everything
- ❌ Cannot resume from failure
- ❌ No progress visibility during run
- ❌ Cannot detect issues until completion

---

## Current Architecture (Incremental Writes) - ACTIVE

```
FOR EACH company:
    1. Scrape jobs → List[UnifiedJob]
    2. Write to raw_jobs (UPSERT by hash) ← IMMEDIATE PERSISTENCE
    3. Classify jobs → add classification
    4. Write to enriched_jobs (UPSERT by raw_job_id) ← IMMEDIATE PERSISTENCE
    5. Mark company as processed
```

**Benefits:**
- ✅ Data persisted every ~2-5 minutes per company
- ✅ Resume capability: skip already-processed companies
- ✅ Partial success: 80 companies done = 80 companies saved
- ✅ Progress visibility: query DB to see status
- ✅ Early error detection: see issues immediately

---

## Key Design Decisions

### 1. Database Schema Changes

**raw_jobs table:**
```sql
ALTER TABLE raw_jobs ADD CONSTRAINT raw_jobs_hash_unique UNIQUE (hash);
```

- **Purpose:** Enable UPSERT by hash (prevents duplicate insertions)
- **Impact:** Must handle conflict resolution (ON CONFLICT DO UPDATE)
- **Behavior:** If same job scraped twice, update existing row instead of error

**enriched_jobs table:**
- Already has unique constraint on raw_job_id
- No changes needed

### 2. Deduplication Strategy

**Current:** In-memory deduplication via UnifiedJobIngester
**Proposed:** Database-level deduplication via UPSERT

**Cross-Source Deduplication (Adzuna + Greenhouse):**
- Same job may appear from both sources
- **Rule:** UPSERT with source priority:
  - If raw_jobs has Adzuna version, Greenhouse version UPDATES it (better description)
  - `description_source` field tracks which source provided the description
  - `data_source` field tracks which source originally found the job

**Implementation:**
```python
# Pseudo-code for upsert
INSERT INTO raw_jobs (hash, source, title, company, raw_text, ...)
VALUES (...)
ON CONFLICT (hash) DO UPDATE SET
    raw_text = CASE
        WHEN EXCLUDED.source = 'greenhouse' THEN EXCLUDED.raw_text  -- Prefer Greenhouse text
        ELSE raw_jobs.raw_text  -- Keep existing
    END,
    scraped_at = EXCLUDED.scraped_at,
    source = raw_jobs.source  -- Keep original source
```

### 3. Resume Capability

**Track processed companies:**
- Option A: Query DB for companies with recent scraped_at timestamp
- Option B: Maintain separate `pipeline_runs` table to track progress
- Option C: Create `.checkpoint` file with completed companies

**Recommended:** Option A (query DB)
```python
# Get companies already processed in last 24 hours
processed_companies = supabase.table('raw_jobs') \
    .select('company') \
    .gte('scraped_at', datetime.now() - timedelta(days=1)) \
    .execute()

# Skip these companies
remaining_companies = [c for c in all_companies if c not in processed_companies]
```

### 4. Error Handling

**Per-company error handling:**
- If company fails: log error, continue to next company
- Do NOT abort entire pipeline
- Failed companies can be retried individually

**Retry strategy:**
- Immediate retry: 1 attempt
- If still fails: skip and continue
- Separately retry all failed companies at end

### 5. Classification Strategy

**Current:** Batch classify after all scraping complete
**Proposed:** Classify immediately after each company scraped

**Why immediate classification?**
- Pro: Data fully enriched as it's scraped
- Pro: Can see classification errors early
- Pro: No orphaned raw_jobs without enriched_jobs
- Con: Slightly slower (no batch optimization)

**Decision:** Immediate classification per company (benefits > costs)

### 6. Progress Tracking

**Real-time visibility:**
```python
# Check status mid-run
SELECT
    COUNT(DISTINCT company) as companies_processed,
    COUNT(*) as total_jobs,
    MAX(scraped_at) as last_activity
FROM raw_jobs
WHERE scraped_at >= '2025-12-03 11:00:00'
```

**Log each company completion:**
```
[11:15] ✓ stripe: 10 jobs scraped, 8 classified, 8 stored
[11:17] ✓ monzo: 5 jobs scraped, 5 classified, 5 stored
[11:23] ✗ palantir: FAILED (timeout), will retry later
[11:25] ✓ anthropic: 15 jobs scraped, 14 classified, 14 stored
```

---

## Progress Logging Requirements

**REQUIREMENT:** Clear, real-time visibility into pipeline progress during execution.

### Pipeline Start Banner
```
╔══════════════════════════════════════════════════════════════╗
║          GREENHOUSE PIPELINE - INCREMENTAL MODE              ║
╚══════════════════════════════════════════════════════════════╝

Configuration:
  - Total companies: 109
  - Already processed (last 24h): 0
  - Remaining to process: 109
  - Sources: greenhouse
  - Mode: incremental (per-company writes)

Starting pipeline at 2025-12-03 15:30:00
═══════════════════════════════════════════════════════════════
```

### Per-Company Progress Log
```
[15:30:15] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[15:30:15] Company 1/109: stripe
[15:30:15] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[15:30:15]   → Scraping jobs from Greenhouse...
[15:30:22]   → Scraped: 45 jobs found
[15:30:22]   → Filtered: 35 by title, 5 by location (88.9% filter rate)
[15:30:22]   → Kept: 5 jobs for classification
[15:30:22]   → Writing raw jobs to database...
[15:30:23]   ✓ Raw jobs stored: 5 (0 duplicates skipped)
[15:30:23]   → Classifying jobs with Claude...
[15:30:28]   → Classified: 4/5 (1 agency filtered)
[15:30:28]   → Writing enriched jobs to database...
[15:30:29]   ✓ Enriched jobs stored: 4
[15:30:29] ✓ stripe COMPLETE: 4/5 jobs stored (1 filtered)
[15:30:29]
[15:30:29] ┌─────────────────────────────────────────────────┐
[15:30:29] │ PROGRESS: 1/109 companies (0.9%)               │
[15:30:29] │ TOTALS: 4 jobs stored | 41 jobs filtered      │
[15:30:29] │ ESTIMATED TIME REMAINING: ~180 minutes         │
[15:30:29] └─────────────────────────────────────────────────┘
[15:30:29]
```

### Running Totals (Every 10 Companies)
```
[15:45:00] ╔══════════════════════════════════════════════════╗
[15:45:00] ║           CHECKPOINT: 10/109 COMPANIES          ║
[15:45:00] ╚══════════════════════════════════════════════════╝
[15:45:00]
[15:45:00] Jobs Scraped:        423
[15:45:00] Jobs Filtered:       389 (92.0% filter rate)
[15:45:00] Jobs Kept:            34
[15:45:00] Jobs Classified:      30 (4 agencies filtered)
[15:45:00] Jobs Stored:          30
[15:45:00]
[15:45:00] Companies Completed:  10
[15:45:00] Companies Remaining:  99
[15:45:00] Companies Failed:     0
[15:45:00]
[15:45:00] Time Elapsed:        14m 45s
[15:45:00] Avg Time/Company:    1m 28s
[15:45:00] Est. Time Remaining: 145 minutes
[15:45:00]
[15:45:00] Cost So Far:         $0.12
[15:45:00] Est. Total Cost:     $1.31
[15:45:00] ════════════════════════════════════════════════════
```

### Pipeline Completion Summary
```
╔══════════════════════════════════════════════════════════════╗
║               PIPELINE COMPLETE - SUMMARY                    ║
╚══════════════════════════════════════════════════════════════╝

Duration: 2h 45m 33s
Completed at: 2025-12-03 18:15:33

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPANIES PROCESSED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Total:              109
  Successful:         105 (96.3%)
  Failed:             4 (3.7%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JOB COUNTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Jobs Scraped:       3,913
  Jobs Filtered:      3,706 (94.7%)
    - By Title:       2,234 (60.3%)
    - By Location:    1,472 (39.7%)
  Jobs Kept:          207
  Jobs Classified:    184 (23 filtered)
    - Agencies:       20
    - Other:          3
  Jobs Stored:        184

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ECONOMICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Classification Cost:     $0.71
  Cost per Job Stored:     $0.00386
  Cost Saved (filtering):  $14.38

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAILED COMPANIES (4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. palantir - Timeout after 3 retries
  2. datadog - SPA navigation failed
  3. whop - Page load timeout
  4. saucelabs - Infinite scroll detection failed

Retry these companies with:
  python fetch_jobs.py --sources greenhouse --companies palantir,datadog,whop,saucelabs

═══════════════════════════════════════════════════════════════
```

### Error Logging Format
```
[15:45:30] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[15:45:30] Company 15/109: palantir
[15:45:30] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[15:45:30]   → Scraping jobs from Greenhouse...
[15:45:45]   ✗ ERROR: Page load timeout (15s)
[15:45:45]   → Retrying (attempt 2/3)...
[15:46:00]   ✗ ERROR: Page load timeout (15s)
[15:46:00]   → Retrying (attempt 3/3)...
[15:46:15]   ✗ ERROR: Page load timeout (15s)
[15:46:15]   ✗ palantir FAILED after 3 attempts
[15:46:15]   → Will retry at end of pipeline
[15:46:15]
```

### Real-Time Stats Query (Available Mid-Run)
```python
# Users can query this while pipeline is running
python pipeline/utilities/check_pipeline_status.py --live

Output:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LIVE PIPELINE STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pipeline started: 2025-12-03 15:30:00 (45 minutes ago)
Last activity:    2025-12-03 16:15:00 (active)

Companies processed:  34/109 (31.2%)
Jobs stored (today):  120
Most recent company:  anthropic (16:14:55)

Estimated completion: 17:45 (90 minutes remaining)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Implementation Requirements

**Key Metrics to Track:**
1. **Per Company:**
   - Jobs scraped from website
   - Jobs filtered (by title + location)
   - Jobs kept for classification
   - Jobs classified successfully
   - Jobs stored in database
   - Agencies filtered
   - Time taken

2. **Running Totals:**
   - Total companies processed / remaining
   - Total jobs scraped / filtered / stored
   - Total cost spent / saved
   - Elapsed time / estimated remaining

3. **Failure Tracking:**
   - Companies that failed (with reasons)
   - Jobs that failed classification
   - Retry attempts

**Logging Levels:**
- INFO: Progress updates, company completion
- WARNING: Non-fatal issues (classification failures, agency detections)
- ERROR: Fatal company failures
- DEBUG: Detailed per-job information (when --verbose flag used)

**Output Destinations:**
- Console (pretty formatted with colors/unicode)
- Log file (plain text for parsing: `logs/pipeline_run_YYYYMMDD_HHMMSS.log`)
- Database (optional: `pipeline_runs` table for historical tracking)

---

## Implementation Phases

### Phase 1: Database Schema Updates
1. Add UNIQUE constraint on raw_jobs.hash
2. Update insert_raw_job() to use UPSERT logic
3. Test deduplication behavior on sample data

### Phase 2: Refactor Greenhouse Scraper
1. Modify scraper to yield jobs per-company (not return all at once)
2. Add callback: `on_company_complete(company, jobs)`
3. Callback writes to raw_jobs immediately

### Phase 3: Refactor Main Pipeline
1. Update fetch_jobs.py to process companies sequentially
2. For each company: scrape → write raw → classify → write enriched
3. Add progress logging per company

### Phase 4: Add Resume Capability
1. Query DB for recently processed companies
2. Skip those companies in current run
3. Add --force flag to re-scrape specific companies

### Phase 5: Validation & Rollout
1. Test on 5-10 companies first
2. Verify data quality matches old approach
3. Run full 109-company pipeline
4. Monitor for issues

---

## Code Changes Required

### 1. `db_connection.py`

**Add UPSERT logic:**
```python
def insert_raw_job_upsert(
    source: str,
    posting_url: str,
    title: str,
    company: str,
    raw_text: str,
    source_job_id: Optional[str] = None
) -> int:
    """
    Insert or update raw job using UPSERT.
    Returns raw_job_id (existing or new).
    """
    from pipeline.db_connection import generate_job_hash

    job_hash = generate_job_hash(company, title, "unk")  # City not available at raw stage

    # Use Supabase upsert
    result = supabase.table('raw_jobs').upsert({
        'hash': job_hash,
        'source': source,
        'posting_url': posting_url,
        'title': title,
        'company': company,
        'raw_text': raw_text,
        'source_job_id': source_job_id,
        'scraped_at': datetime.now().isoformat()
    }, on_conflict='hash').execute()

    return result.data[0]['id']
```

### 2. `fetch_jobs.py`

**Refactor to per-company processing:**
```python
async def process_company_incremental(company_slug: str) -> Dict:
    """
    Scrape, classify, and store a single company's jobs immediately.
    Returns stats about the company.
    """
    # 1. Scrape
    scraper = GreenhouseScraper(headless=True)
    await scraper.init()
    result = await scraper.scrape_company(company_slug)
    jobs = result['jobs']

    # 2. Write raw jobs (UPSERT)
    raw_job_ids = []
    for job in jobs:
        raw_id = insert_raw_job_upsert(
            source='greenhouse',
            posting_url=job.url,
            title=job.title,
            company=job.company,
            raw_text=job.description,
            source_job_id=job.job_id
        )
        raw_job_ids.append(raw_id)

    # 3. Classify
    classified_jobs = await classify_jobs(jobs)

    # 4. Write enriched jobs
    stored_count = 0
    for job in classified_jobs:
        if job.classification:
            insert_enriched_job(...)  # Existing function
            stored_count += 1

    logger.info(f"✓ {company_slug}: {len(jobs)} scraped, {stored_count} stored")

    return {
        'company': company_slug,
        'scraped': len(jobs),
        'stored': stored_count,
        'failed': len(jobs) - stored_count
    }

async def main_incremental():
    """Main pipeline with incremental processing"""
    companies = load_companies()

    # Skip already processed (optional)
    processed = get_recently_processed_companies(hours=24)
    remaining = [c for c in companies if c not in processed]

    logger.info(f"Processing {len(remaining)} companies ({len(processed)} already done)")

    results = []
    for company in remaining:
        try:
            result = await process_company_incremental(company)
            results.append(result)
        except Exception as e:
            logger.error(f"✗ {company}: FAILED - {str(e)}")
            results.append({'company': company, 'error': str(e)})

    # Summary
    total_scraped = sum(r.get('scraped', 0) for r in results)
    total_stored = sum(r.get('stored', 0) for r in results)
    logger.info(f"Pipeline complete: {total_stored}/{total_scraped} jobs stored")
```

### 3. `greenhouse_scraper.py`

**Add per-company yield (optional optimization):**
```python
async def scrape_all_incremental(
    self,
    companies: List[str],
    on_company_complete=None
) -> Dict:
    """
    Scrape companies and call callback after each one.
    Allows for incremental processing.
    """
    results = {}
    for company in companies:
        result = await self.scrape_company(company)
        results[company] = result

        # Callback for incremental processing
        if on_company_complete:
            on_company_complete(company, result)

    return results
```

---

## Migration Plan

**How to transition from old to new architecture:**

1. **No migration needed for existing data** - schema changes are additive
2. **Run new pipeline in parallel** - validate results match old pipeline
3. **Switch over** - deprecate old batch pipeline once validated
4. **Keep old code** - maintain for 1-2 weeks as fallback

**Validation criteria:**
- Same number of jobs stored (±5% acceptable due to timing)
- Same classification quality
- Faster failure recovery
- Better observability

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| More DB calls = slower | Medium | Acceptable trade-off for resilience |
| Complex error handling | Medium | Per-company try/catch with detailed logging |
| Deduplication edge cases | Low | Extensive testing on known duplicates |
| Resume logic bugs | Medium | Option to force re-scrape with --force flag |
| Data inconsistency | High | Transaction wrappers around raw+enriched writes |

---

## Success Metrics

**After implementation, we should see:**
- ✅ Pipeline failures lose <10 minutes of work (not 3 hours)
- ✅ Can check progress mid-run via DB queries
- ✅ Failed companies can be retried individually
- ✅ Database has partial results even if pipeline killed

**Acceptance test:**
- Run pipeline, kill it after 30 minutes, verify data is in DB
- Resume from checkpoint, verify no duplicates
- Compare results to old batch pipeline on same dataset

---

## Design Decisions (Finalized)

1. **✅ Batch classify per-company**
   - Decision: Classify immediately after each company scraped
   - Reasoning: Simplicity > optimization, early error detection valuable

2. **✅ Adzuna stays as batch**
   - Decision: Keep Adzuna as-is (batch process at end)
   - Reasoning: Already performant, no changes needed
   - Only Greenhouse uses incremental per-company writes

3. **✅ NO transactions - embrace partial success**
   - Decision: Do NOT wrap raw + enriched inserts in transactions
   - Reasoning:
     - Partial success is valuable (raw data saved even if classification fails)
     - Can build backfill utility to re-classify orphaned raw_jobs
     - Simpler implementation (no transaction complexity)
     - Supabase Python client has limited transaction support
   - Trade-off: Accept some orphaned raw_jobs as "classification failure markers"

4. **✅ Logging to both file AND console**
   - Decision: Write to both timestamped log file + pretty console output
   - Console: Rich formatting with unicode boxes, colors, progress bars
   - Log file: Plain text for parsing/searching
   - Database tracking: Optional future enhancement (pipeline_runs table)

---

## Next Steps

1. ✅ Kill current pipeline (DONE - 2025-12-03)
2. ✅ Document design (DONE - this file)
3. ✅ Discuss design with user (DONE - approved)
4. ✅ Add shell ID tracking instructions to CLAUDE.md (DONE)
5. ✅ Finalize design decisions (DONE - see above)
6. ⏳ **NEXT:** Implement Phase 1 (database schema changes)
   - Add UNIQUE constraint on raw_jobs.hash
   - Create insert_raw_job_upsert() function
   - Test deduplication
7. ⏳ Implement Phase 2 (refactor Greenhouse scraper)
   - Per-company processing with callbacks
8. ⏳ Implement Phase 3 (refactor main pipeline + progress logging)
   - Rich console output with unicode boxes
   - Timestamped log files
   - Running totals and estimates
9. ⏳ Implement Phase 4 (resume capability)
10. ⏳ Test on 5 companies
11. ⏳ Full rollout on 109 companies

---

**Note:** This is a significant architectural change. We should implement incrementally and validate at each phase before proceeding.

**Implementation Timeline:**
- Phase 1 (schema): ~30 minutes
- Phase 2 (scraper refactor): ~1 hour
- Phase 3 (pipeline + logging): ~2 hours
- Phase 4 (resume): ~30 minutes
- Testing & validation: ~1 hour
- **Total estimated effort: ~5 hours**
