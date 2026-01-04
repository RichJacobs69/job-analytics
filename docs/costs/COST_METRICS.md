# Classification Cost Metrics

> **Last Updated:** 2025-12-04
> **Data Source:** Anthropic API Usage Dashboard
> **Note:** This is a point-in-time cost analysis from Dec 4, 2025. These metrics represent the cost per job for Haiku classification and remain valid regardless of dataset size. See `../../CLAUDE.md` for current job counts (Supabase source of truth, updated 2025-12-07).

## Summary

This directory contains API cost tracking data and analysis for the Claude 3.5 Haiku classification pipeline. The metrics below represent actual measured costs from production runs and are independent of the total job dataset size.

### Key Cost Metrics (Point-in-Time: 2025-12-04)

| Metric | Value |
|--------|-------|
| **Raw jobs inserted** | 1,654 |
| **Jobs classified (enriched)** | 961 |
| **Total API cost** | $9.38 |
| **Cost per raw insert** | $0.00567 |
| **Cost per classified job** | $0.00976 |
| **Classification rate** | 58.1% (961/1,654) |

### Token Usage (Point-in-Time: 2025-12-04)

| Metric | Value |
|--------|-------|
| **Input tokens** | 8,232,003 |
| **Output tokens** | 698,232 |
| **Total tokens** | 8,930,235 |
| **Avg tokens per classification** | ~9,293 |
| **Note** | These are actual measured values from Anthropic API; valid for predicting future Haiku classification costs |

### Pricing (Claude 3.5 Haiku)

| Token Type | Price per 1M tokens |
|------------|---------------------|
| Input (no cache) | $0.80 |
| Output | $4.00 |

---

## Cost Breakdown by Date

### December 4, 2025 (Point-in-Time Snapshot)

**Total Cost: $9.38**
- Input tokens (no cache): $6.59 (8.2M tokens)
- Output tokens: $2.79 (698K tokens)

**Pipeline Efficiency (Dec 4 measurement):**
- 58% of raw inserts were classified
- 42% filtered before classification (duplicates, agencies, quality filters)
- Agency detection saved significant API costs
- **Note:** This measurement was taken on 2025-12-04; current job counts have grown since then (see CLAUDE.md for latest dataset size)

### December 2, 2025

**Total Cost: $6.09**
- Input tokens: $4.03
- Output tokens: $2.06

---

## Files in This Directory

| File | Description |
|------|-------------|
| `claude_api_cost_2025_12_01_to_2025_12_04.csv` | Daily cost breakdown by token type |
| `claude_api_tokens_2025_12_04.csv` | Hourly token usage for Dec 4 |
| `COST_METRICS.md` | This analysis document |

---

## Cost Optimization Strategies

### Currently Implemented

1. **Duplicate Detection** - Skip classification for jobs already in database
   - Uses `source_job_id` for exact matching
   - Updates `last_seen` timestamp instead of re-classifying
   - Savings: ~$0.01 per skipped job

2. **Agency Filtering** - Hard filter agencies before classification
   - Pattern-based blacklist in `config/agency_blacklist.yaml`
   - Prevents wasting API calls on staffing agencies
   - Savings: ~$0.01 per filtered job

3. **Description Quality Filter** - Skip jobs with insufficient data
   - Minimum description length check
   - Prevents low-quality classifications

### Potential Future Optimizations

1. **Prompt Caching** - Cache repeated prompt sections
   - Claude supports prompt caching for repeated prefixes
   - Could reduce input costs by 50-90%
   - Requires: Restructuring prompts for cache-friendly format

2. **Batch Classification** - Group similar jobs
   - Combine multiple short descriptions in single request
   - Amortize system prompt across multiple jobs

3. **Title-Based Pre-filtering** - Skip obviously out-of-scope jobs
   - Use regex patterns before API call
   - Already partially implemented in Greenhouse scraper

---

## Monitoring & Tracking

### How to Check Current Costs

1. **Anthropic Dashboard**: https://console.anthropic.com/
2. **Pipeline Output**: Each run logs classification costs
3. **Database Query**: Count `classified_at` timestamps

### Cost Tracking in Code

The classifier returns cost data in `_cost_data`:
```python
{
    'input_tokens': 1234,
    'output_tokens': 89,
    'input_cost': 0.00099,
    'output_cost': 0.00036,
    'total_cost': 0.00135
}
```

---

## Historical Notes

- **Bug Fixed (2025-12-04)**: Pipeline was looking for `cost_usd` instead of `total_cost` in cost tracking
- **Model**: Using Claude 3.5 Haiku for cost efficiency (~10x cheaper than Sonnet)
- **Quality**: Haiku achieves ~93% accuracy on job classification tasks
































