# Pipeline Log Review Guide

Quick reference for analyzing GitHub Actions logs to identify issues in the Greenhouse scraper pipeline.

## Quick Grep Commands

```bash
# Download the log file first, then use these commands:

# Timing issues - find companies taking too long
grep -E "Successfully scraped.*jobs from" log.txt | head -20

# DNS/network failures
grep -E "net::ERR_|DNS|timeout|Timeout" log.txt

# Pagination issues
grep -E "infinite loop|Clicked page number|No more pagination" log.txt

# Companies with 0 jobs
grep -E "Successfully scraped 0 jobs" log.txt

# Filtering summary
grep -E "\[.*\] Filtering:" log.txt

# Errors and warnings
grep -E "ERROR|WARNING|Exception|Failed" log.txt
```

---

## Issue Categories

### 1. Timing Issues (Company Timeouts)

**What to look for:**
- Companies taking >5 minutes for <50 jobs
- Large gap between "Loading" and "Successfully scraped" timestamps

**Log pattern:**
```
11:06:57 - [complyadvantage] Attempt 1/1: Loading https://...
11:18:32 - [complyadvantage] Successfully scraped 0 jobs
```
*11+ minutes for 0 jobs = problem*

**Common causes:**
| Symptom | Cause | Fix |
|---------|-------|-----|
| Clicking category buttons | Pagination selector too broad | Add link text validation |
| Repeated "Clicked page number: {text}" with non-numeric text | Category nav mistaken for pagination | Check `nav[role="navigation"]` selector |
| Same job count for 3+ iterations | Infinite loop (correctly detected) | Review board structure |

**Action:** If a company consistently times out, consider removing from `company_ats_mapping.json` or adding company-specific handling.

---

### 2. Title Filtering Issues

**What to look for:**
- Legitimate roles being filtered (e.g., "Product Analyst", "Growth Analyst")
- High filter rates (>98%) for companies known to have relevant jobs

**Log pattern:**
```
[pandadoc] Filtered by title: 'Senior Product Analyst'
[pandadoc] Filtered by title: 'Senior Product Analyst'
```

**Check against:**
- `docs/schema_taxonomy.yaml` - our job taxonomy
- `config/greenhouse/title_patterns.yaml` - filter patterns

**Common misses:**
| Role | Should match? | Pattern needed |
|------|---------------|----------------|
| Product Analyst | Yes | `product analyst` |
| Growth Analyst | Yes | `growth analyst` |
| Research Scientist | Yes | `research scientist` |
| Data Science Manager | Yes | `data science (engineer\|manager\|lead)` |

---

### 3. Location Filtering Issues

**What to look for:**
- Valid locations being filtered as unknown
- Working arrangements in location field (Hybrid, In-Office)
- Location field containing job titles instead of locations

**Log patterns:**
```
# Location not recognized
[databricks] Filtered by location: 'AI Engineer' at 'United States'

# Working arrangement instead of location
[cloudflare] Filtered by location: 'Data Analyst' at 'Hybrid'

# Job title in location field (board misconfiguration)
[duolingo] Filtered by location: 'Product Manager' at 'Product Manager, Learning'
```

**Check against:**
- `config/location_mapping.yaml` - location patterns
- `pipeline/location_extractor.py` - extraction logic

**Common issues:**
| Location string | Issue | Fix |
|-----------------|-------|-----|
| "Hybrid" / "In-Office" | Working arrangement, not location | Returns `unknown` (expected) |
| "United States" | Too broad, no city | Consider adding country-level matching |
| "Centennial, CO" | Missing suburb | Add to Denver metro patterns |
| "NYC; Remote, US" | Multi-location | Check both parts extracted |

---

### 4. Companies with 0 Jobs

**What to look for:**
- DNS resolution failures
- 100% filter rate
- No job listings found

**Log patterns:**
```
# DNS failure - company defunct
[airbyte] net::ERR_NAME_NOT_RESOLVED at https://board.greenhouse.io/airbyte

# All jobs filtered
[company] Filtering: 50 total, 0 kept, 50 filtered (100.0%)

# No listings found (board structure changed)
[company] No job listings found with any selector
```

**Action by cause:**
| Cause | Action |
|-------|--------|
| DNS failure | Remove from `company_ats_mapping.json` |
| 100% title filter | Review title patterns, may need additions |
| 100% location filter | Review location patterns |
| No listings found | Board structure changed, needs selector update |

---

### 5. Playwright/Pagination Issues

**What to look for:**
- TimeoutError during navigation
- Infinite loop detection
- Page jumping to wrong URL

**Log patterns:**
```
# Timeout during page load
playwright._impl._errors.TimeoutError: Timeout 30000ms exceeded

# Infinite loop detected (this is the SAFEGUARD working)
[company] Detected infinite loop (same job count 50 for 3 iterations)

# Pagination clicked wrong element
[complyadvantage] Clicked page number: Fraud Detection
[complyadvantage] Clicked page number: ComplyLaunch
```

**Pagination should log:**
- `Clicked Load More` - for infinite scroll boards
- `Clicked Next button` - for paginated boards
- `Clicked page number: 2` (numeric) - for numbered pagination

**Red flags:**
- Non-numeric page numbers (category names)
- Same job count across multiple iterations
- Navigation to job detail page instead of next listing page

---

### 6. URL Construction Issues

**What to look for:**
- Job URLs with wrong path structure
- "No description found" warnings for many jobs

**Log pattern:**
```
# Wrong URL structure (Block-specific issue)
URL: https://job-boards.greenhouse.io/careers/jobs/4997715008
# Should be:
URL: https://job-boards.greenhouse.io/block/jobs/4997715008
```

**Check:** If a company has many "No description found" warnings, verify the job URLs are correct by visiting one manually.

---

### 7. Classification/Enrichment Issues

**What to look for:**
- Jobs in `raw_jobs` but not in `enriched_jobs`
- API rate limiting (429 errors)
- Classification timeouts

**Log patterns:**
```
# Rate limiting
HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 429 Too Many Requests"

# Classification success
[14/29] Classified ($0.0044)
[14/29] SUCCESS: Stored (raw_id=21665, enriched_id=16963)
```

**Verify with SQL:**
```sql
-- Check for orphaned raw_jobs (not in enriched)
SELECT r.id, r.title, r.company
FROM raw_jobs r
LEFT JOIN enriched_jobs e ON e.raw_job_id = r.id
WHERE r.scraped_at > NOW() - INTERVAL '1 day'
  AND e.id IS NULL;
```

---

## Summary Metrics to Check

At the end of each batch run, verify:

| Metric | Healthy Range | Action if outside |
|--------|---------------|-------------------|
| Total runtime | 60-90 min | Check for timeouts |
| Companies processed | ~90 per batch | Check for failures |
| Jobs enriched | Varies | Compare to previous runs |
| Filter rate | 90-96% | Too high = missing patterns |
| Duplicates | Varies | Expected for repeat runs |

---

## Recent Fixes Reference

| Date | Issue | Fix | Commit |
|------|-------|-----|--------|
| 2025-12-23 | ComplyAdvantage 11min loop | Removed broad nav selector, added link text validation | `72a7689` |
| 2025-12-23 | Block wrong URLs | Replace `/careers/jobs/` with `/{slug}/jobs/` | `72a7689` |
| 2025-12-23 | Multi-location extraction | Coverage-based early return check | `3766c2b` |
| 2025-12-23 | Missing Product Analyst | Added to title patterns | `33abda3` |
| 2025-12-23 | Defunct companies | Removed airbyte, ambient, caramedicalltd | `72a7689` |
