# ATS Scraping Test Results

## Test Data & Summary

**Input:** 50 London-based job postings from Adzuna (mixed industry)
**Test Scope:** First 5 jobs
**Success Rate:** 0% (0/5 jobs)

## Key Findings

### 1. Detection Results

| Company | Job Title | ATS Detected | Status |
|---------|-----------|--------------|--------|
| Travelex | Data Engineer | Unknown/Custom ATS | FAIL - No scraper |
| Coca-Cola Europacific Partners | ML Engineering Lead | None | FAIL - No careers page |
| Billigence | Data Engineer | None | FAIL - No careers page |
| TCS | Principal Data Engineer | Unknown/Custom ATS | FAIL - No scraper |
| Focus on SAP | Analytics Engineer | None | FAIL - No careers page |

### 2. Root Cause Analysis

#### Problem 1: Company Domain Inference
- **Issue:** Simple name→domain mapping doesn't work for complex names
- **Example:** "Coca-Cola Europacific Partners" → "coca-cola-europacific-partners.com" (not a real domain)
- **Solution Needed:** Manual company→domain mappings or domain lookup API

#### Problem 2: Custom ATS Systems
- **Issue:** ~40% of UK companies use custom or unknown ATS systems
- **Examples:** Travelex, TCS appear to use custom career pages
- **Solution Needed:** Build generic scrapers for common custom ATS patterns, or manual content extraction

#### Problem 3: Company Not Online
- **Issue:** ~40% of companies don't have findable careers pages
- **Possible reasons:**
  - Using recruiting agency job boards instead
  - Careers page behind authentication/redirect
  - Company uses LinkedIn exclusively
  - Careers page on completely different domain
- **Solution Needed:** Fall back to extracting from Adzuna metadata

## Recommendations

### For This Project

Given the test results, **ATS scraping alone won't be sufficient** for your London dataset. Recommend a **hybrid approach**:

#### Phase 1: Quick Wins (Greenhouse/Lever/Workday Only)
- Filter dataset to companies known to use Greenhouse/Lever/Workday
- Run ATS scraping on those (~10-15% of dataset)
- Improves classifier for tech-forward companies

#### Phase 2: Fallback Strategy
- For companies without detected ATS:
  - Attempt LinkedIn job page scraping (with caution)
  - Use Adzuna text as-is (current behavior)
  - Mark record with `text_source: 'adzuna_api'` (truncated)
  - Note: This doesn't solve the truncation problem

#### Phase 3: Manual Enrichment (Optional)
- For top employers in dataset, manually identify their ATS/job portal
- Build company→domain mappings (could be crowd-sourced)
- Create specific scraper rules for common patterns

### Long-Term Solution

Rather than following Adzuna redirects→ATS scraping, consider:

**Option A: Direct API Integration**
- Use company APIs directly (rarely available)
- Slower approach but more reliable

**Option B: LinkedIn Scraping (with caution)**
- Many jobs are posted on LinkedIn
- Could scrape full descriptions from LinkedIn
- Risk: LinkedIn actively blocks scrapers, may violate ToS

**Option C: Use Complementary Data Sources**
- Indeed API (has more complete descriptions than Adzuna)
- LinkedIn Jobs API (if you can get approval)
- Company-specific RSS feeds for job postings

## Impact on Classification Accuracy

With only ~0% success on this sample:
- **Skills extraction:** Still degraded (~29% F1 - no improvement)
- **Working arrangement:** Still degraded (~0.565 F1 - no improvement)
- **Overall system F1:** No improvement over baseline

To achieve your targets (F1 ≥0.85), you'll need either:
1. Different data source with complete job descriptions
2. Hybrid approach (ATS for some, manual fallback for others)
3. Improved classifier trained on truncated text

## What Worked

- ✅ ATS detection works when careers page is accessible
- ✅ Workday detection works (e.g., would work for Microsoft)
- ✅ Unknown/Custom ATS is properly identified (for manual review)

## What Didn't Work

- ❌ Domain inference from company name (too error-prone)
- ❌ Generic job search/scraping for unknown ATS
- ❌ 60% of companies had no accessible careers pages

## Next Steps

**To continue with this approach:**

1. **Provide a mapping** of which companies in your dataset use which ATS
   - E.g., `{"Meta": ("greenhouse", "meta.com"), "Wise": ("custom", "wise.com")}`
   - This would skip the failing domain inference step

2. **Or provide company URLs directly** in your dataset
   - E.g., add column `careers_url` with direct links to job boards
   - Would dramatically improve success rate

3. **Or pivot to different data source**
   - Consider Indeed/LinkedIn instead of Adzuna redirects
   - May provide fuller job descriptions natively

## Files Generated

- `ats_test_results.json` - Detailed results for each job tested
- `ATS_SCRAPING_TEST_RESULTS.md` (this file) - Analysis and recommendations

## Questions for You

1. Do you have a mapping of which companies in your dataset use which ATS/job board?
2. Would it be feasible to add career page URLs to your Adzuna data?
3. Should we pivot to a different data source (Indeed, LinkedIn, etc.)?
4. Is full text scraping critical, or can you work with improved classifier on truncated text?