# Pipeline Log Review Guide

Quick reference for analyzing GitHub Actions logs to identify issues across all pipeline sources.

## Quick Grep Commands

```bash
# Download the log file first, then use these commands:

# === ALL SOURCES ===
# Title filtering issues
grep -E "Filtered by title:" log.txt | head -30

# Location filtering issues
grep -E "Filtered by location:" log.txt | head -30

# Classification errors
grep -E "ERROR|Exception|Failed|prompt is too long" log.txt

# Token limit errors
grep -E "prompt is too long|token" log.txt

# === GREENHOUSE-SPECIFIC ===
# Timing issues - find companies taking too long
grep -E "Successfully scraped.*jobs from" log.txt | head -20

# DNS/network failures
grep -E "net::ERR_|DNS|TimeoutError" log.txt

# Pagination issues
grep -E "infinite loop|Clicked page number|No more pagination" log.txt

# Companies with 0 jobs
grep -E "Successfully scraped 0 jobs" log.txt

# === LEVER-SPECIFIC ===
# API failures
grep -E "\[lever\].*error|\[lever\].*failed" log.txt

# === ADZUNA-SPECIFIC ===
# API rate limits
grep -E "429|rate limit|Too Many Requests" log.txt

# Truncated descriptions
grep -E "truncated|description.*short" log.txt
```

---

## Common Issues (All Sources)

### 1. Title Filtering Issues

**Applies to:** Greenhouse, Lever, Adzuna

**What to look for:**
- Legitimate roles being filtered (e.g., "Product Analyst", "Growth Analyst")
- High filter rates (>98%) for companies known to have relevant jobs

**Log pattern:**
```
[company] Filtered by title: 'Senior Product Analyst'
```

**Check against:**
- `docs/schema_taxonomy.yaml` - our job taxonomy
- `config/greenhouse/title_patterns.yaml` - Greenhouse patterns
- `config/lever/title_patterns.yaml` - Lever patterns

**Common misses:**
| Role | Should match? | Pattern needed |
|------|---------------|----------------|
| Product Analyst | Yes | `product analyst` |
| Growth Analyst | Yes | `growth analyst` |
| Research Scientist | Yes | `research scientist` |
| AI/ML Engineer | Yes | `ai/ml` |
| Analytics Director | Yes | `(analytics\|data).*director` |

---

### 2. Location Filtering Issues

**Applies to:** Greenhouse, Lever, Adzuna

**What to look for:**
- Valid locations being filtered as unknown
- Working arrangements in location field (Hybrid, In-Office)
- Location field containing job titles instead of locations

**Log patterns:**
```
# Location not recognized
[company] Filtered by location: 'Data Analyst' at 'United States'

# Working arrangement instead of location
[company] Filtered by location: 'Data Analyst' at 'Hybrid'

# Job title in location field (scraper bug)
[company] Filtered by location: 'Product Manager' at 'Product Manager, AI'
```

**Check against:**
- `config/location_mapping.yaml` - master location patterns
- `pipeline/location_extractor.py` - extraction logic

**Common issues:**
| Location string | Issue | Fix |
|-----------------|-------|-----|
| "Hybrid" / "In-Office" | Working arrangement, not location | Returns `unknown` (expected) |
| "United States" | Too broad, no city | Consider adding country-level matching |
| "Centennial, CO" | Missing suburb | Add to Denver metro patterns |
| "Alameda, CA" | Missing explicit pattern | Add `city, ca` variant |
| Title as location | Scraper DOM issue | Investigate board structure |

---

### 3. Classification/Enrichment Issues

**Applies to:** Greenhouse, Lever, Adzuna

**What to look for:**
- Jobs in `raw_jobs` but not in `enriched_jobs`
- API rate limiting (429 errors)
- Token limit errors
- Classification timeouts

**Log patterns:**
```
# Token limit error
prompt is too long: 205444 tokens > 200000 maximum

# Rate limiting
HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 429 Too Many Requests"

# Classification success
[14/29] Classified ($0.0044)
[14/29] SUCCESS: Stored (raw_id=21665, enriched_id=16963)
```

**Actions:**
| Issue | Fix |
|-------|-----|
| Token limit | Add description truncation in `classifier.py` |
| Rate limiting | Reduce batch size or add delays |
| Orphaned raw_jobs | Run `backfill_missing_enriched.py` |

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

## Greenhouse-Specific Issues

### 4. Timing Issues (Company Timeouts)

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
| Repeated "Clicked page number: {text}" with non-numeric text | Category nav mistaken for pagination | Check selector specificity |
| Same job count for 3+ iterations | Infinite loop (correctly detected) | Review board structure |

**Action:** If a company consistently times out, consider removing from `config/greenhouse/company_ats_mapping.json`.

---

### 5. Pagination/Infinite Loop Issues

**What to look for:**
- TimeoutError during navigation
- Infinite loop detection
- Page jumping to wrong URL

**Log patterns:**
```
# Timeout during page load
playwright._impl._errors.TimeoutError: Timeout 30000ms exceeded

# Infinite loop detected (SAFEGUARD working correctly)
[company] Detected infinite loop (same job count 50 for 3 iterations)

# Pagination clicked wrong element
[complyadvantage] Clicked page number: Fraud Detection
[complyadvantage] Clicked page number: ComplyLaunch
```

**Expected pagination logs:**
- `Clicked Load More` - infinite scroll boards
- `Clicked Next button` - paginated boards
- `Clicked page number: 2` (numeric) - numbered pagination

**Red flags:**
- Non-numeric page numbers (category names)
- Same job count across multiple iterations
- Navigation to job detail page instead of next listing page

---

### 6. DNS/Network Failures

**What to look for:**
- Companies with defunct Greenhouse boards
- Network connectivity issues

**Log pattern:**
```
[airbyte] net::ERR_NAME_NOT_RESOLVED at https://board.greenhouse.io/airbyte
[company] Failed to scrape on any URL
```

**Action:** Remove defunct companies from `config/greenhouse/company_ats_mapping.json`.

---

### 7. DOM Extraction Issues

**What to look for:**
- Job titles extracted as "View & Apply" or similar button text
- Location field showing job title text
- Custom careers pages (redirects from Greenhouse)

**Log patterns:**
```
# Button text as title (Skydio-style boards)
[skydio] Found 88 jobs with title 'View & Apply'

# Title appearing as location (custom careers page)
[figma] Filtered by location: 'Product Manager, AI' at 'Product Manager, AI'
```

**Actions:**
| Issue | Fix |
|-------|-----|
| Button text as title | Add parent element lookup for title |
| Title as location | Company uses custom page - consider removing |
| Redirect to custom page | Remove from Greenhouse, add to custom scraper |

---

### 8. URL Construction Issues

**What to look for:**
- Job URLs with wrong path structure
- "No description found" warnings for many jobs

**Log pattern:**
```
# Wrong URL structure
URL: https://job-boards.greenhouse.io/careers/jobs/4997715008
# Should be:
URL: https://job-boards.greenhouse.io/block/jobs/4997715008
```

**Check:** If a company has many "No description found" warnings, verify job URLs by visiting manually.

---

## Lever-Specific Issues

### 9. API Response Issues

**What to look for:**
- Empty responses from Lever API
- Malformed JSON responses
- Authentication failures

**Log patterns:**
```
[lever] Error fetching jobs for company: HTTPError 404
[lever] Invalid JSON response from API
```

**Actions:**
| Issue | Fix |
|-------|-----|
| 404 errors | Verify company slug in `config/lever/company_mapping.json` |
| Empty response | Company may have closed board |
| Auth failures | Check if company requires authentication |

---

## Adzuna-Specific Issues

### 10. API Rate Limits

**What to look for:**
- 429 Too Many Requests errors
- Throttling warnings

**Log pattern:**
```
HTTP 429 Too Many Requests
Rate limit exceeded, waiting 60 seconds...
```

**Action:** Reduce request frequency or implement exponential backoff.

---

### 11. Truncated Descriptions

**What to look for:**
- Job descriptions cut off mid-sentence
- Missing skills/requirements sections

**Note:** Adzuna API returns truncated descriptions by design. Full descriptions require visiting the original job posting URL.

---

## Summary Metrics by Source

### Greenhouse
| Metric | Healthy Range | Action if outside |
|--------|---------------|-------------------|
| Total runtime | 60-90 min per batch | Check for timeouts |
| Companies processed | ~70-90 per batch | Check for failures |
| Jobs enriched | Varies | Compare to previous runs |
| Filter rate | 90-96% | Too high = missing patterns |

### Lever
| Metric | Healthy Range | Action if outside |
|--------|---------------|-------------------|
| Total runtime | 10-20 min | Check API issues |
| Companies processed | ~60 | Check for failures |
| Filter rate | 85-95% | Review patterns |

### Adzuna
| Metric | Healthy Range | Action if outside |
|--------|---------------|-------------------|
| Total runtime | 5-15 min per city | Check rate limits |
| Jobs per city | 50-200 | Varies by market |
| Filter rate | 70-85% | Lower due to broader API results |

---

## Recent Fixes Reference

| Date | Source | Issue | Fix | Commit |
|------|--------|-------|-----|--------|
| 2025-12-23 | Greenhouse | Figma custom page (0% success) | Removed from scraper | `4532cf0` |
| 2025-12-23 | Greenhouse | Defunct: energysage, healthie, intern | Removed from mapping | `8464b95` |
| 2025-12-23 | Greenhouse | Defunct: sovrn | Removed from mapping | `71c4a4e` |
| 2025-12-23 | All | Token limit errors | Added 50K char truncation | `71c4a4e` |
| 2025-12-23 | Greenhouse | Skydio "View & Apply" titles | Added parent element lookup | (previous) |
| 2025-12-23 | Greenhouse | Defunct: messari, papaya, scytherobotics | Removed from mapping | (previous) |
| 2025-12-23 | Greenhouse | AI/ML pattern miss | Added `ai/ml` pattern | (previous) |
| 2025-12-23 | Greenhouse | Alameda, CA not matching | Added East Bay `, ca` patterns | (previous) |
| 2025-12-23 | Greenhouse | ComplyAdvantage 11min loop | Removed broad nav selector | `72a7689` |
| 2025-12-23 | Greenhouse | Block wrong URLs | Fixed path construction | `72a7689` |
| 2025-12-23 | All | Missing Product Analyst | Added to title patterns | `33abda3` |
