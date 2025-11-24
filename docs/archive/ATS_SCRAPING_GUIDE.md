# ATS Scraping System - Complete Guide

## Overview

This system automatically detects which Applicant Tracking System (ATS) a company uses and scrapes full job descriptions from their careers pages. This solves the Adzuna text truncation problem by enriching job records with complete descriptions from the original source.

## Architecture

```
Adzuna Job Metadata (employer, title, location)
    ↓
ATSDetector (Auto-detection)
    ├─ Infer company domain from employer name
    ├─ Find company careers page
    └─ Identify ATS by URL patterns
    ↓
ATSScraper (Job Search & Scraping)
    ├─ Search ATS job board for matching job
    ├─ Scrape full job description
    └─ Extract and clean text
    ↓
Supabase
    ├─ Store full_text in raw_jobs table
    ├─ Set text_source = 'ats_scrape'
    └─ Use for improved classification
```

## Supported ATS Platforms

### 1. **Greenhouse** (Most Popular for Tech)
- **Used by:** Stripe, GitHub, GitLab, Shopify, Figma, etc.
- **Domain pattern:** `*.greenhouse.io` or `boards.greenhouse.io`
- **Job board URL:** `https://[company].greenhouse.io/jobs`
- **Status:** ✅ Scraper implemented

### 2. **Lever** (Popular for Startups)
- **Used by:** Notion, Figma, Airbnb, Instacart, etc.
- **Domain pattern:** `*.lever.co` or `jobs.lever.co`
- **Job board URL:** `https://[company].lever.co/jobs`
- **Status:** ✅ Scraper implemented

### 3. **Workday** (Enterprise)
- **Used by:** Google, Facebook, Microsoft, Apple, Amazon, etc.
- **Domain pattern:** `*.myworkdayjobs.com`
- **Job board URL:** `https://[company].myworkdayjobs.com/[company]`
- **Status:** ✅ Scraper implemented

## Key Components

### 1. `ats_scraper.py` - Core Module

#### `ATSDetector` Class
```python
detector = ATSDetector()

# Auto-detect ATS for a company
ats_name, careers_url = detector.detect_ats_for_company(
    employer_name="Stripe",
    company_domain="stripe.com"  # optional
)
# Returns: ("Greenhouse", "https://stripe.greenhouse.io/jobs")
```

**How it works:**
1. Infers company domain from name (e.g., "Stripe" → "stripe.com")
2. Tries common careers page patterns:
   - `https://[domain]/careers`
   - `https://careers.[domain]`
   - `https://jobs.[domain]`
3. Detects ATS by checking URL against domain patterns
4. Caches results to avoid redundant lookups

#### ATS Scraper Classes
Each ATS has its own scraper class:
- `GreenhouseScraper`
- `LeverScraper`
- `WorkdayScraper`

**Common interface:**
```python
scraper = get_scraper_for_ats('greenhouse')

# Search for job
job_url = scraper.search_jobs(
    employer_name="Stripe",
    job_title="Senior Data Engineer",
    location="San Francisco"
)

# Scrape full description
full_text = scraper.scrape_job(job_url)
```

#### Main E2E Function
```python
result = scrape_full_job_text(
    employer_name="Stripe",
    job_title="Senior Data Engineer",
    location="San Francisco"
)

# Returns:
# {
#     'full_text': '...',
#     'ats_type': 'greenhouse',
#     'ats_name': 'Greenhouse',
#     'job_url': 'https://...',
#     'scrape_source': 'ats_scrape'
# }
```

### 2. `test_ats_scraping.py` - Test Harness

Allows testing with sample Adzuna data:

```bash
# Test with CSV data
python test_ats_scraping.py --data sample_jobs.csv

# Test with JSON data
python test_ats_scraping.py --data sample_jobs.json

# Test and save to Supabase
python test_ats_scraping.py --data sample_jobs.csv --save-to-db

# Limit to N jobs
python test_ats_scraping.py --data sample_jobs.csv --limit 5

# Custom output file
python test_ats_scraping.py --data sample_jobs.csv --output results.json
```

**Input format (CSV):**
```
employer_name,title,location,id
Stripe,Senior Data Engineer,San Francisco,12345
GitHub,Product Manager,Remote,12346
```

**Input format (JSON):**
```json
[
  {
    "employer_name": "Stripe",
    "title": "Senior Data Engineer",
    "location": "San Francisco",
    "id": 12345
  }
]
```

**Output (JSON):**
```json
[
  {
    "employer": "Stripe",
    "title": "Senior Data Engineer",
    "location": "San Francisco",
    "raw_job_id": "12345",
    "status": "success",
    "ats_detected": "Greenhouse",
    "ats_type": "greenhouse",
    "job_found": true,
    "job_url": "https://stripe.greenhouse.io/jobs/...",
    "text_length": 3847,
    "full_text": "..."
  }
]
```

### 3. Updated `db_connection.py` Functions

New functions for storing scraped content:

```python
# Store full text from ATS scraping
success = update_raw_job_full_text(
    raw_job_id=12345,
    full_text="Full job description here...",
    text_source='ats_scrape'
)

# Retrieve job record
job = get_raw_job_by_id(12345)
```

**Database schema expectations:**
- `raw_jobs` table has columns:
  - `full_text` (TEXT)
  - `text_source` (VARCHAR) - values: 'adzuna_api', 'ats_scrape', etc.

## Workflow: Enriching Adzuna Data

### Step 1: Prepare Sample Data

Create `sample_jobs.csv` with Adzuna records:
```csv
employer_name,title,location,id
Stripe,Data Engineer,San Francisco,101
GitHub,Backend Engineer,Remote,102
Figma,Product Manager,New York,103
Google,Software Engineer,Mountain View,104
```

### Step 2: Run ATS Scraping Test

```bash
python test_ats_scraping.py \
  --data sample_jobs.csv \
  --limit 5 \
  --output scraping_results.json
```

### Step 3: Review Results

Check `scraping_results.json`:
- **Success rate** - % of jobs where full text was scraped
- **ATS distribution** - which ATS systems were found
- **Failures** - which jobs couldn't be scraped and why

### Step 4: Save to Supabase

Once satisfied with results, save to database:

```bash
python test_ats_scraping.py \
  --data sample_jobs.csv \
  --save-to-db
```

This updates the `raw_jobs` table with:
- `full_text`: Complete job description
- `text_source`: 'ats_scrape'

### Step 5: Improve Classifier

Re-run classifier on enriched jobs:
```python
from classifier import classify_job

# Get enriched job from DB
job = get_raw_job_by_id(12345)

# Use full_text instead of truncated raw_text
classification = classify_job(
    description_text=job['full_text'],  # Full text from ATS
    employer_name=job['employer_name']
)
```

## Limitations & Known Issues

### Current Limitations

1. **Domain inference**: Works for standard domain patterns (name.com)
   - Issue: "GitHub" → "github.com" ✓, but "GitHub Inc" might not work
   - Fix: Manual domain mappings for non-standard cases

2. **Job matching**: Uses fuzzy matching on job title
   - Issue: May find wrong job if company has many similar titles
   - Fix: Could add location and posting date to matching logic

3. **HTML parsing**: Assumes standard HTML structure
   - Issue: Some companies customize their ATS heavily
   - Fix: May need site-specific CSS selectors

4. **Rate limiting**: 2-second delay between jobs
   - Issue: Slow for large batches
   - Fix: Could parallelize with request throttling

### Edge Cases

- ❌ **Private careers pages** - Requires authentication
- ❌ **Custom ATS** - Won't detect if not Greenhouse/Lever/Workday
- ⚠️ **Ajax-loaded jobs** - May need Selenium/Playwright for dynamic content
- ⚠️ **Geolocation-specific** - Some pages show different jobs by location

## Future Improvements

### Phase 2: Expand ATS Support
- [ ] SmartRecruiters (enterprise)
- [ ] Workable (SMB)
- [ ] Bamboo HR (SMB)
- [ ] Taleo (enterprise legacy)

### Phase 3: Better Job Matching
- [ ] Use posting date to match jobs
- [ ] Use salary ranges if available
- [ ] Implement fuzzy matching with Levenshtein distance

### Phase 4: Handling Edge Cases
- [ ] Detect and handle authentication walls
- [ ] Support for dynamic content (JavaScript-rendered)
- [ ] Fallback to Google search if standard URLs fail

### Phase 5: Optimization
- [ ] Parallel scraping with async requests
- [ ] Cache frequently accessed company pages
- [ ] Smart retry logic for failed jobs

## Testing & Validation

### Quick Test
```python
from ats_scraper import scrape_full_job_text

result = scrape_full_job_text(
    employer_name="Stripe",
    job_title="Data Engineer",
    location="San Francisco"
)

if result:
    print(f"✓ Found on {result['ats_name']}")
    print(f"✓ Scraped {len(result['full_text'])} chars")
else:
    print("✗ Scraping failed")
```

### Batch Test with Metrics
```bash
# Run test and generate report
python test_ats_scraping.py \
  --data sample_jobs.csv \
  --output results.json

# Check success rate
python -c "
import json
with open('results.json') as f:
    results = json.load(f)
    success = sum(1 for r in results if r['status'] == 'success')
    print(f'Success rate: {success}/{len(results)} = {success/len(results)*100:.1f}%')
"
```

## Integration with Classifier

Once full text is stored, update `classifier.py` to prefer full text:

```python
def classify_job(raw_job_id: int) -> Dict:
    """Classify job using full text if available, else fallback to truncated"""

    job = get_raw_job_by_id(raw_job_id)

    # Prefer full_text from ATS scraping
    description = job['full_text'] or job['raw_text']

    # Run existing classification pipeline
    return classify_text(description, job['employer_name'])
```

## Requirements

- `beautifulsoup4` - HTML parsing
- `requests` - HTTP requests
- `supabase-py` - Database client

Install with:
```bash
pip install beautifulsoup4 requests supabase-py
```

## Summary

This system provides:
- ✅ Automatic ATS detection
- ✅ Full job description scraping
- ✅ Supabase integration for storage
- ✅ Test harness for validation
- ✅ Support for 3 major ATS platforms (Greenhouse, Lever, Workday)

When combined with the existing classifier, it should dramatically improve classification accuracy by providing complete job descriptions instead of Adzuna's truncated text.

**Expected improvements:**
- Skills F1: 0.29 → 0.85+
- Working arrangement F1: 0.565 → 0.85+
- Overall system F1: >0.85
