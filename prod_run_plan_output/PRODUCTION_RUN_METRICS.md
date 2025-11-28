# Production Run Metrics Collection Plan

**Date to Run:** 2025-11-28 (Tomorrow)

## Objective
Run full Greenhouse pipeline on all 109 companies to measure actual performance metrics and validate time/cost projections.

## Metrics to Collect

### Per-Company Metrics
1. **Jobs found:** Total jobs on listings page
2. **Jobs after title filter:** Count passing Data/Product filter
3. **Jobs after location filter:** Count passing London/NYC/Denver filter
4. **Final jobs classified:** Jobs sent to LLM
5. **Time to load page:** Initial navigation time
6. **Time to extract listings:** Scraping all job titles/locations
7. **Time to fetch descriptions:** Per-job description fetch time
8. **Time to classify:** Per-job LLM classification time
9. **Time to store:** Database insertion time
10. **Total company time:** End-to-end for this company
11. **Pagination pages:** Number of pages scraped

### Aggregate Metrics
- **Total companies processed:** 109 (expected)
- **Total jobs found:** Sum across all companies
- **Combined filter rate:** (jobs_filtered / jobs_found) × 100
- **Average jobs per company:** Mean and median
- **Total pipeline time:** Start to finish
- **Classification cost:** Total $ spent on Haiku API calls
- **Jobs stored in database:** Final count

## Current Assumptions to Validate

| Metric | Assumption | Actual | Variance |
|--------|-----------|--------|----------|
| Jobs per company | 35 | ? | ? |
| Relevant jobs per company | 3 | ? | ? |
| Combined filter rate | 91% | ? | ? |
| Classification time | 4s | ? | ? |
| Total pipeline time | 65 min | ? | ? |
| Total classifications | 327 | ? | ? |
| Total cost | ~$1.11 | ? | ? |

## Command to Run

```bash
cd "C:\Cursor Projects\job-analytics"
python fetch_jobs.py --sources greenhouse --output-metrics production_run_metrics.json
```

## Logging Requirements

Scripts must log:
- Start/end timestamps for each stage
- Job counts at each filter stage
- Per-job timing for expensive operations
- API token usage and costs
- Database operation success/failure

## Post-Run Analysis

1. Compare actual vs projected metrics
2. Identify bottlenecks (which stage takes longest?)
3. Calculate actual cost per job
4. Determine if optimizations needed (company-level concurrency?)
5. Update CLAUDE.md with real production numbers

## Future Optimization Ideas (Deferred)

- **Company-level concurrency:** Run 2-3 companies in parallel → ~35-40 min (50% time savings)
- **Batch classification:** Queue descriptions and classify in batches
- **Faster model:** Test Haiku 3.0 vs 3.5 for speed gains
