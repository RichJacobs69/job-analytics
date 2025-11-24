# Greenhouse Scraper: Comprehensive Testing Guide

## Overview

This document consolidates all testing information for the Greenhouse scraper into one comprehensive guide.

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [The 8 Validation Checks](#the-8-validation-checks)
3. [Quality Scoring](#quality-scoring)
4. [Running Tests](#running-tests)
5. [Interpreting Results](#interpreting-results)
6. [Failure Scenarios](#failure-scenarios)
7. [Integration with CI/CD](#integration-with-cicd)

---

## Quick Start

```bash
# Run validation tests
python test_greenhouse_validation.py

# Expected output:
# ✓ PASS - Jobs Count: Captured 66 jobs
# ✓ PASS - Null Descriptions: All have descriptions
# ✓ PASS - Description Length: 54/66 substantial
# ✓ PASS - Content Sections: 62/66 with full content
# ✓ PASS - URL Integrity: All URLs valid
# ✓ PASS - Deduplication: No duplicates detected
# ✓ PASS - Sample Job: All fields present
# Quality Score: 92.5/100 → PRODUCTION READY
```

---

## The 8 Validation Checks

### 1. Jobs Count Check
**Purpose:** Verify scraper found jobs on listing page

**What it checks:**
- Total number of jobs extracted > 0
- Number >= 5 (indicates real results, not noise)
- Warns if suspiciously low (< 5 jobs)

**Fails if:**
- 0 jobs found (selector broken)
- Extremely low count suggests page changed

**Example:**
```
PASS: Captured 66 jobs
WARNING: Only 2 jobs found (expected 5+)
FAIL: No jobs extracted
```

**Action if fails:**
- Company may not use Greenhouse anymore (like Brex)
- CSS selectors may need updating
- Greenhouse domain may have changed

---

### 2. Null/Empty Descriptions Check
**Purpose:** Ensure every job has a description (critical data quality)

**What it checks:**
- No jobs with None or empty descriptions
- No descriptions that are just whitespace
- Reports any jobs with missing content

**Fails if:**
- Any job has empty description
- Indicates extraction failed for some jobs

**Example:**
```
PASS: All 66 jobs have descriptions
FAIL: 3 jobs with no description
  - Senior Engineer (url: ...)
  - Product Manager (url: ...)
  - Data Analyst (url: ...)
```

**Action if fails:**
- Description extraction failed (timeout, selector, etc.)
- Some job pages may have different structure
- May need selector debugging

---

### 3. Description Length Check
**Purpose:** Verify descriptions are complete, not truncated

**What it checks:**
- Minimum, maximum, average description length
- Distribution by size ranges:
  - Very short (<500): Likely truncated
  - Short (500-2k): Moderate content
  - Medium (2-5k): Good content
  - Long (5-10k): Very comprehensive
  - Very long (10k+): Complete posting

**Fails if:**
- Average < 1,500 chars (multi-section extraction broken)
- 30%+ of jobs are very short (<500 chars)

**Example:**
```
PASS: 54/66 substantial descriptions (2000+ chars)
  Min: 1,203 chars
  Max: 5,701 chars
  Avg: 4,018 chars

Distribution:
  Very Short (<500): 0
  Short (500-2k): 12
  Medium (2-5k): 48
  Long (5-10k): 6
  Very Long (10k+): 0

Quality: PASS - 90% substantial
```

**Threshold:**
- PASS: >= 90% have 2000+ chars
- WARNING: 75-90% substantial
- FAIL: < 75% substantial

**Action if fails:**
- Multi-section extraction not working
- Check if section elements exist on page
- May need to update section keywords

---

### 4. Content Sections Check
**Purpose:** Verify full job posting sections captured

**What it checks:**
- Presence of key content sections:
  - Responsibilities (role overview)
  - Benefits (compensation, perks)
  - Work Arrangement (hybrid, remote)
  - Requirements (skills, experience)

**Fails if:**
- Most jobs only have main description
- Key sections are missing

**Example:**
```
PASS: 62/66 jobs with full content sections

Sample jobs missing content:
  - Junior Dev: 2 sections (missing: benefits, requirements)
  - Sales Rep: 1 section (missing: benefits, work_arr, requirements)
```

**Threshold:**
- PASS: >= 85% have 3+ sections
- WARNING: 70-85%
- FAIL: < 70%

**Action if fails:**
- Company may use different section labels
- Add new keywords to keyword list
- Check job detail page HTML manually

---

### 5. URL Integrity Check
**Purpose:** Validate all URLs are correct and unique

**What it checks:**
- URLs start with http:// or https://
- URLs contain /jobs/ path (Greenhouse standard)
- No duplicate URLs (same job multiple times)
- No malformed links

**Fails if:**
- Malformed URLs found
- Duplicate jobs detected
- Invalid link structure

**Example:**
```
PASS: All 66 URLs valid
  Total: 66
  Valid: 66
  Malformed: 0
  Duplicates: 0
```

**Failure example:**
```
FAIL: URL problems
  Total: 66
  Valid: 64
  Malformed: 1
    - "ftp://invalid..."
  Duplicates: 1
    - "/jobs/123" appears 2x
```

**Action if fails:**
- Pagination issue (same jobs twice)
- Page structure changed
- Load More button not handled correctly

---

### 6. Deduplication Check
**Purpose:** Detect duplicate jobs

**What it checks:**
- Creates MD5 hash of (company|title|location)
- Identifies any jobs with identical hashes
- Reports which jobs are duplicates

**Fails if:**
- Any duplicate jobs found
- Indicates pagination problem

**Example:**
```
PASS: No duplicates detected

FAIL: 3 duplicates found
  - Senior Engineer, London
    First: /jobs/123
    Dup: /jobs/456
```

**Action if fails:**
- Pagination/Load More not handled
- Fix loop logic in _extract_all_jobs()

---

### 7. Sample Job Validation
**Purpose:** Verify data structure integrity

**What it checks:**
- All required fields present:
  - company (e.g., "stripe")
  - title (e.g., "Backend Engineer")
  - location (e.g., "London")
  - url (full job URL)
  - job_id (extracted from URL)
  - description (full job text)

**Fails if:**
- Any fields missing
- Data not properly structured

**Example:**
```
PASS: All 6 fields present

Sample: "Backend Engineer, Data"
  company: stripe ✓
  title: Backend Engineer, Data ✓
  location: San Francisco ✓
  url: https://... ✓
  job_id: 6865161 ✓
  description: 4,126 chars ✓
```

---

### 8. Data Quality Score
**Purpose:** Composite quality metric (0-100)

**Formula:**
```
Score =
  (description_coverage × 0.30) +
  (rich_content_percentage × 0.30) +
  (field_completeness × 0.25) +
  (avg_length_normalized × 0.15)
```

**Interpretation:**
```
90-100: ✓ Excellent → Production ready
80-90:  ~ Good → Acceptable with review
70-80:  ! Fair → Investigate warnings
<70:    ✗ Poor → Fix required
```

**Example:**
```
Quality Score: 92.5/100 ✓ EXCELLENT

Metrics:
  - Description Coverage: 100%
  - Rich Content (2000+): 92%
  - Field Completeness: 99.8%
  - Avg Description: 4,018 chars
```

---

## Quality Scoring

### Score Thresholds

| Score | Status | Action |
|-------|--------|--------|
| 90-100 | ✓ Excellent | Deploy to production |
| 80-90 | ~ Good | Acceptable, monitor warnings |
| 70-80 | ! Fair | Investigate & fix |
| <70 | ✗ Poor | Critical issues, do not deploy |

### Metrics Breakdown

1. **Description Coverage (30% weight)**
   - % of jobs with descriptions
   - Target: 100%

2. **Rich Content (30% weight)**
   - % of jobs with 2000+ characters
   - Target: 90%+

3. **Field Completeness (25% weight)**
   - % of required fields present per job
   - Target: 99%+

4. **Avg Description Length (15% weight)**
   - Average char count across all jobs
   - Normalized: (avg_length / 10000) × 100
   - Target: 3000-5000 chars

---

## Running Tests

### Prerequisites
```bash
pip install playwright
playwright install chromium
```

### Basic Test
```bash
cd /path/to/job-analytics
python test_greenhouse_validation.py
```

### Customize Test Companies
Edit `test_greenhouse_validation.py`:
```python
async def main():
    # Change this list:
    test_companies = ['stripe', 'figma']  # → Add more companies

    validator = GreenhouseValidationTest()
    report = await validator.run_all_tests(test_companies)
```

### Save Report for Later Comparison
Reports automatically save as:
```
greenhouse_validation_report_YYYYMMDD_HHMMSS.json
```

Compare reports:
```bash
# Side-by-side comparison
diff report_20250114.json report_20250121.json
```

---

## Interpreting Results

### All Checks Pass ✓
```
✓ PASS - Jobs Count
✓ PASS - Null Descriptions
✓ PASS - Description Length
✓ PASS - Content Sections
✓ PASS - URL Integrity
✓ PASS - Deduplication
✓ PASS - Sample Job
Quality Score: 92.5/100 EXCELLENT
```

**Action:** Ready for production/expansion

### Some Checks Fail ✗

#### Scenario 1: Zero jobs found
**Cause:**
- Selectors don't match page
- Company migrated off Greenhouse
- Domain changed

**Debug:**
1. Visit page in browser: `job-boards.greenhouse.io/{company}`
2. Inspect job element with DevTools
3. Check if selectors match
4. Update selectors if needed

#### Scenario 2: Low description length
```
Description Length:
  avg_chars: 1,203 (should be 3,000+)
```

**Cause:**
- Multi-section extraction not working
- Only main description captured
- Section iteration broken

**Debug:**
1. Check if `<section>` elements exist on page
2. Verify section keywords match page content
3. Check section header text in browser

#### Scenario 3: Missing content sections
```
Content Sections: FAIL
  jobs_with_full_content: 30 out of 66
```

**Cause:**
- Section keywords outdated
- Company uses different labels
- New sections added

**Debug:**
1. Open job detail page in browser
2. Check section headers
3. Update `section_keywords` list if needed

#### Scenario 4: Duplicate jobs detected
```
Deduplication: FAIL
  duplicate_count: 3
```

**Cause:**
- Load More button processed twice
- Pagination not handled

**Debug:**
1. Check `_extract_all_jobs()` logic
2. Verify Load More button click works once
3. Check for duplicate detection

---

## Failure Analysis Decision Tree

```
Run test
    ↓
All 8 checks pass?
├─ YES → Quality >= 80?
│   ├─ YES → ✓ PRODUCTION READY
│   └─ NO  → Review warnings
│
└─ NO (failures exist)
    ├─ Jobs count = 0?
    │  → Company may not use Greenhouse
    │  → Try both domains
    │  → Manual inspection needed
    │
    ├─ Null descriptions?
    │  → Description extraction failed
    │  → Check selectors, timeouts
    │  → Debug specific jobs
    │
    ├─ Low description length?
    │  → Multi-section not working
    │  → Check section elements
    │  → Verify section keywords
    │
    ├─ Missing content sections?
    │  → Company uses different labels
    │  → Update keywords
    │  → Or add new sections
    │
    ├─ URL issues?
    │  → Page structure changed
    │  → Update selectors
    │  → Verify job links
    │
    └─ Duplicates found?
       → Pagination not working
       → Fix Load More logic
       → Check while loop condition
```

---

## Integration with CI/CD

### Example: GitHub Actions
```yaml
name: Test Greenhouse Scraper
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: pip install playwright && playwright install chromium
      - name: Run validation tests
        run: python test_greenhouse_validation.py
      - name: Check quality score
        run: |
          python -c "
          import json, glob
          report = json.load(open(sorted(glob.glob('greenhouse_validation_report_*.json'))[-1]))
          if any(r['data_quality']['quality_score'] < 80 for r in report['test_results'].values()):
              print('ALERT: Quality below 80!')
              exit(1)
          "
```

---

## When to Run Tests

| Scenario | When |
|----------|------|
| Code change to scraper | Before committing |
| Before expanding to new company | Before adding to scraper |
| Quarterly monitoring | Monthly/quarterly sweep |
| After fixing a bug | Before deployment |
| Before production deployment | Always |

---

## Summary

The 8-check validation framework ensures:
- ✓ All jobs are captured (completeness)
- ✓ Full descriptions extracted (no truncation)
- ✓ No data quality issues (nulls, duplicates)
- ✓ Rich content captured (all sections)
- ✓ Production-ready quality (score >= 80)

Use before expanding to new companies or deploying changes.
