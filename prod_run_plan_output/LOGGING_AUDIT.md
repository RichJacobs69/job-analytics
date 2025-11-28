# Production Logging Audit

**Status:** Reviewed 2025-11-27
**For:** Production run planned 2025-11-28

## Current Logging Coverage

### ✅ GOOD - Already Logged

| Metric | Location | Example |
|--------|----------|---------|
| **Filter stats** | `greenhouse_scraper.py:418-424` | Total scraped, kept, filtered by title/location |
| **Cost savings** | `fetch_jobs.py:145` | `${filtered * 0.00388:.2f}` |
| **Classification count** | `fetch_jobs.py:226` | Jobs classified and agencies filtered |
| **Storage count** | `fetch_jobs.py:335` | Successfully stored jobs |
| **Token usage** | `classifier.py:207-212` | Input/output tokens + costs per job |
| **Job counts** | Throughout | Jobs found, filtered, merged, stored |

### ❌ MISSING - Need to Add

| Metric | Why Needed | Where to Add |
|--------|------------|--------------|
| **Total pipeline time** | End-to-end duration | `fetch_jobs.py:main()` - add start/end timestamps |
| **Per-company time** | Identify slow companies | `greenhouse_scraper.py:scrape_company()` - wrap in timer |
| **Classification time** | Actual LLM call duration | `classifier.py:classify_job()` - time API call |
| **Per-stage timing** | Identify bottlenecks | All major functions |
| **Aggregate costs** | Total $ spent | `fetch_jobs.py` - sum all `_cost_data` |

## Recommended Logging Additions

### 1. Add timing wrapper to fetch_jobs.py

```python
import time

def main():
    start_time = time.time()

    # ... existing code ...

    elapsed = time.time() - start_time
    logger.info(f"Total pipeline time: {elapsed/60:.1f} minutes ({elapsed:.0f} seconds)")
```

### 2. Add per-company timing to greenhouse_scraper.py

```python
async def scrape_company(self, company_slug: str, ...):
    import time
    start_time = time.time()

    # ... existing scraping code ...

    elapsed = time.time() - start_time
    logger.info(f"[{company_slug}] Company scrape time: {elapsed:.1f}s")

    stats['scrape_time_seconds'] = round(elapsed, 1)
    return {'jobs': jobs, 'stats': stats}
```

### 3. Add classification timing to classifier.py

```python
def classify_job(job: UnifiedJob) -> Optional[Dict]:
    import time
    start_time = time.time()

    # ... API call ...

    elapsed = time.time() - start_time
    logger.debug(f"Classification took {elapsed:.2f}s for {job.title}")

    if cost_data:
        cost_data['classification_time_seconds'] = round(elapsed, 2)
```

### 4. Add cost aggregation to fetch_jobs.py

```python
# After classification loop
total_cost = sum(job.get('_cost_data', {}).get('total_cost', 0) for job in classified)
total_input_tokens = sum(job.get('_cost_data', {}).get('input_tokens', 0) for job in classified)
total_output_tokens = sum(job.get('_cost_data', {}).get('output_tokens', 0) for job in classified)

logger.info(f"Classification costs: ${total_cost:.4f}")
logger.info(f"Tokens used: {total_input_tokens:,} input + {total_output_tokens:,} output")
```

## What We Can Already Measure

From existing logs, we can extract:
- ✅ Jobs per company (from filter stats)
- ✅ Filter effectiveness (title/location)
- ✅ Cost savings from filtering
- ✅ Classification success rate
- ✅ Storage success rate
- ⚠️ Approximate timing (from log timestamps)

## What Needs Code Changes

To get precise timing metrics, we need to add:
1. **Timer wrappers** around major operations
2. **Aggregation logic** for costs across all jobs
3. **Metrics export** to JSON file for analysis

## Decision

**Option A:** Run tomorrow with existing logging
- ✅ Can measure most metrics from logs
- ❌ No precise per-stage timing
- ⏱️ Can infer timing from log timestamps

**Option B:** Add timing logging first (30 min work)
- ✅ Precise timing data
- ✅ JSON metrics export
- ⏱️ Delays production run by ~30 min

**Recommendation:** Option A - existing logging is sufficient. We can calculate timing from log timestamps, and the key metrics (counts, filter rates, costs) are already tracked.
