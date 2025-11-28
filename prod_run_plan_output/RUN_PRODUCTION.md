# Production Run Command - 2025-11-28

## Quick Start

```bash
cd "C:\Cursor Projects\job-analytics"

# Run full Greenhouse pipeline (all 109 companies)
python fetch_jobs.py --sources greenhouse > greenhouse_production_run.log 2>&1
```

## What Will Happen

1. **Scrape 109 Greenhouse companies** from `config/company_ats_mapping.json`
2. **Apply filters:** Title (Data/Product) + Location (London/NYC/Denver)
3. **Fetch descriptions** only for jobs passing both filters
4. **Classify** with Claude Haiku (track costs)
5. **Store** to Supabase database

## Expected Duration

**Projected:** ~65 minutes (1 hour 5 min)

Based on:
- 109 companies
- ~35 jobs/company = 3,815 total jobs
- ~3 relevant jobs/company = 327 classifications
- Combined 91% filter rate

## Metrics to Collect

After run completes, analyze `greenhouse_production_run.log` for:

### Per-Company Metrics (example grep)
```bash
# Filter stats per company
grep "Filtering:" greenhouse_production_run.log

# Cost savings per company
grep "Cost savings" greenhouse_production_run.log
```

### Aggregate Metrics
```bash
# Total jobs scraped
grep "Successfully scraped" greenhouse_production_run.log | wc -l

# Total classifications
grep "Classified" greenhouse_production_run.log

# Total stored
grep "Successfully stored" greenhouse_production_run.log
```

### Timing Analysis
```bash
# First and last timestamps
head -1 greenhouse_production_run.log
tail -1 greenhouse_production_run.log

# Calculate duration from timestamps
```

## Key Questions to Answer

1. **Actual vs projected time:** Was it ~65 min?
2. **Filter effectiveness:** What was the real combined filter rate?
3. **Average jobs per company:** Actual distribution
4. **Classification time:** Average per job
5. **Total cost:** Actual $ spent on Haiku calls
6. **Bottlenecks:** Which stage took longest?

## Post-Run Analysis

Compare results to projections in `docs/PRODUCTION_RUN_METRICS.md`:

| Metric | Projected | Actual | Variance |
|--------|-----------|--------|----------|
| Total time | 65 min | ? | ? |
| Jobs scraped | 3,815 | ? | ? |
| Jobs classified | 327 | ? | ? |
| Filter rate | 91% | ? | ? |
| Total cost | ~$1.11 | ? | ? |

## If Something Goes Wrong

**Browser crashes:**
- Reduce `max_concurrent_pages` in greenhouse_scraper.py (currently 2)
- Add delays between companies

**API rate limits:**
- Anthropic has generous limits, unlikely to hit
- If hit, add sleep after each classification

**Database timeouts:**
- Check Supabase connection limits
- Batch inserts if needed

**Long runtime:**
- Pipeline will continue where it left off
- Can kill and restart - deduplication prevents re-processing

## Success Criteria

✅ All 109 companies processed
✅ >300 jobs classified and stored
✅ <2 hours total runtime
✅ <$2 total cost
✅ No fatal errors in logs
