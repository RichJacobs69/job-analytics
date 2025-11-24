# ATS Analysis: Strategic Report
**Based on analysis of 174 curated career page URLs**

## Executive Summary

Your dataset dramatically changes the story compared to the Adzuna sample. This is **real, representative data** and the news is **excellent**.

**Key Finding:** With strategic parser development, you can achieve **81% scraping coverage** across your career pages, compared to **0%** with the Adzuna sample.

### Bottom Line
- **Already scrapable:** 115 companies (66.1%) with your current infrastructure
- **Can be scrapable:** +26 companies (14.9%) with 2-3 new parsers
- **Difficult/requires automation:** 33 companies (19.0%) - custom pages and Workday

This fundamentally changes the ROI calculation for building new ATS parsers.

---

## Detailed ATS Distribution

| Platform | Count | % | Parser Status | Complexity | Impact |
|----------|-------|---|---|---|---|
| **Greenhouse** | 91 | 52.3% | [WORKING] | Easy | **HUGE - 52% coverage** |
| **Lever** | 11 | 6.3% | [WORKING] | Easy | **Large** |
| **Workable** | 8 | 4.6% | [WORKING] | Easy | **Medium** |
| **BambooHR** | 2 | 1.1% | [WORKING] | Medium | **Small** |
| **Recruitee** | 3 | 1.7% | [WORKING] | Medium | **Small** |
| **SUBTOTAL (Working)** | **115** | **66.1%** | | | |
| | | | | | |
| **Ashby** | 14 | 8.0% | [MISSING] | Medium | **High** |
| **SmartRecruiters** | 3 | 1.7% | [MISSING] | Hard | **Low** |
| **Comeet** | 5 | 2.9% | [MISSING] | Hard | **Medium** |
| **Taleo** | 4 | 2.3% | [MISSING] | Hard | **Low** |
| **SUBTOTAL (Can Build)** | **26** | **14.9%** | | | |
| | | | | | |
| **Custom Pages** | 26 | 14.9% | [HARD] | Very Hard | **Medium** |
| **Workday** | 7 | 4.0% | [HARD] | Very Hard | **Low** |
| **SUBTOTAL (Difficult)** | **33** | **19.0%** | | | |

---

## The Good News: Massive Improvement Opportunity

### Current State
You're already covering **115 companies (66.1%)** with Greenhouse, Lever, Workable, BambooHR, and Recruitee parsers.

These are the quality companies in your dataset:
- **Stripe, Coinbase, MongoDB, Etsy, Figma, GitHub, Instacart, DoorDash, Lyft, Twilio, HubSpot, Pinterest, Airbnb, Dropbox, etc.**

With just your current infrastructure, you have access to ~**60-70% of top-tier job descriptions**.

### Phase 1: Add Ashby Parser (1-2 days)
Ashby is a **modern, growing ATS platform** that's gaining adoption among tech companies and startups.

**14 companies using Ashby:**
- Notion, Vercel, Retool, Rippling, Webflow, OpenSea, Linear, Replit, Midjourney, Perplexity AI, Vanta, Mercury, Sourcegraph, Hex

**Why build it:**
- Ashby is **JavaScript-rendered SPA** but jobs are **in accessible DOM** (not hidden in lazy-load)
- Pattern: `jobs.ashbyhq.com/[company]` → fetch and parse job listings
- **Impact:** +14 companies (8.0% of total, brings you to **74.1%**)
- **Effort:** 2-4 hours (similar complexity to Lever)

**Code structure needed:**
```python
class AshbyScraper:
    """Scrape jobs from Ashby ATS"""

    def scrape_jobs(self, company_name: str) -> List[Job]:
        # 1. Load ashbyhq.com/company_name with requests or Playwright
        # 2. Wait for jobs to load (Ashby renders in browser, but API available)
        # 3. Parse job cards from DOM (or hit Ashby's API)
        # 4. Extract title, description, metadata
        # 5. Return structured job list
```

### Phase 2: Add SmartRecruiters Parser (1-2 days)
Only **3 companies** use SmartRecruiters but they're high-value: Spotify, Ubisoft, King.

**Why build it:**
- SmartRecruiters has **detectable patterns** in HTML
- Companies: Spotify, Ubisoft, King (gaming/entertainment giants)
- **Impact:** +3 companies (1.7%, brings you to **75.8%**)
- **Effort:** 2-3 hours (custom DOM parsing, not too complex)

### Phase 3: Add Comeet Parser (2-3 days, optional)
**5 companies** using Comeet: Riskified, Taboola, Similarweb, Fiverr, Via Transportation

**Why it's lower priority:**
- Smaller companies than Ashby/SmartRecruiters
- Comeet is more complex (JavaScript-heavy, API-based)
- **Impact:** +5 companies (2.9%, brings you to **78.7%**)
- **Effort:** 3-4 hours (may need browser automation or reverse-engineer API)

### Phase 4: Add Taleo Parser (2-3 days, optional)
**4 companies** (mostly public sector): TfL, Metropolitan Police, UCL, UAL

**Why lower priority:**
- Mostly government/university jobs (lower match for typical job seeker)
- Taleo is legacy, complex, outdated
- **Impact:** +4 companies (2.3%, brings you to **81.0%**)
- **Effort:** 3-4 hours (Taleo is notoriously difficult)

---

## The Hard Part: Custom Pages & Workday (19% of dataset)

### Custom Career Pages (26 companies)
Companies like **Microsoft, Amazon, Apple, Google, Meta, Netflix, Tesla, Bloomberg, etc.** build their own job boards.

**Examples:**
- Microsoft: careers.microsoft.com (custom page)
- Amazon: amazon.jobs (custom)
- Google: careers.google.com (custom)
- Meta: metacareers.com (custom)
- Netflix: jobs.netflix.com (custom)
- etc.

**Why they're hard:**
- No standardized API or HTML structure
- Heavy JavaScript rendering (React/Vue SPAs)
- Custom pagination, job card layouts, filtering
- Would require **browser automation** or **reverse-engineer each company's API**

**ROI Analysis:**
- These are 26 separate implementations
- Each would take 1-2 hours to reverse-engineer
- Building parsers for all 26 would take 26-52 hours
- **Not worth it** - better to use browser automation approach

**Recommendation:** For custom pages, consider:
1. **Selective browser automation** - only for high-value companies (FAANG, Meta, Netflix, etc.)
2. **Accept Adzuna text** - for the remaining custom pages, use what you have
3. **Hybrid approach** - scrape Ashby/SmartRecruiters/Comeet, use Adzuna for custom pages

### Workday (7 companies)
**Companies:** Bloomberg, Deliveroo, Snowflake, Nike, Salesforce, Walmart, Target

**Why it's hard:**
- **Workday is an enterprise ERP system**, not a recruiting platform
- Job data is embedded in Workday's proprietary UI
- Heavy JavaScript, complex pagination, tokens/session handling
- Would require **reverse-engineering Workday's internal API** or **browser automation**

**ROI Analysis:**
- Workday integration is complex and fragile (breaks with updates)
- Only 7 companies, mostly not job-seeker-focused (they're enterprise platforms)
- **Not recommended** - better to use browser automation if needed

---

## Recommendation: Three-Tier Strategy

### Tier 1: BUILD IMMEDIATELY (1-2 days)
**Ashby Parser**
- 14 companies
- Medium complexity, high ROI
- Takes you from **66.1% → 74.1%**

**Estimated effort:** 2-4 hours
**Code template:** Similar to Lever, just different HTML selectors

### Tier 2: BUILD NEXT (1-2 days, optional)
**SmartRecruiters Parser**
- 3 companies (but high-value)
- Takes you to **75.8%**

**Estimated effort:** 2-3 hours

### Tier 3: BUILD IF TIME (2-3 days, optional)
**Comeet Parser**
- 5 companies
- Takes you to **78.7%**

**Estimated effort:** 3-4 hours

### Tier 4: ACCEPT AS-IS (Don't build)
**Custom Pages (26 companies) & Workday (7 companies)**
- Together only 19.0% of dataset
- Require browser automation infrastructure
- Not worth the engineering effort for this ROI

---

## Impact on Classifier Accuracy

### Scenario A: Current state (Greenhouse + Lever only)
- **Coverage:** 115 companies (66.1%)
- **Text source:** Full text from ATS scrapers
- **Skills F1:** ~0.85+ on scraped subset
- **Working arrangement F1:** ~0.85+ on scraped subset
- **Remaining 58.9%:** Still getting truncated Adzuna text, F1 ≈ 0.29

**Overall dataset F1:** (0.85 × 0.66) + (0.29 × 0.34) = **~0.66** (good improvement)

### Scenario B: After building Ashby parser
- **Coverage:** 129 companies (74.1%)
- **Skills F1:** ~0.85+ on scraped subset
- **Remaining 25.9%:** Truncated Adzuna text, F1 ≈ 0.29

**Overall dataset F1:** (0.85 × 0.74) + (0.29 × 0.26) = **~0.71** (solid)

### Scenario C: After building Ashby + SmartRecruiters + Comeet
- **Coverage:** 144 companies (82.8%)
- **Overall dataset F1:** (0.85 × 0.83) + (0.29 × 0.17) = **~0.75** (strong)

### Scenario D: Browser automation for custom pages
- **Coverage:** 170+ companies (97%+)
- **Overall dataset F1:** **~0.83+** (excellent)
- **Cost:** 1-2 weeks engineering + infrastructure

---

## Quick Wins Analysis

### What You Should Do This Week
**1. Build Ashby Parser (1-2 days)**

This is your biggest quick win:
- Simple enough that you can do it in a day
- Adds 14 companies (8% of dataset)
- Uses similar patterns to Lever (you already know how to scrape it)
- Takes you from 66% → 74% coverage

**Implementation roadmap:**
1. Fetch `https://jobs.ashbyhq.com/[company]`
2. Parse job listings from DOM (they're not lazy-loaded)
3. Extract title, description, metadata
4. Store with `text_source: 'ashby'`

**Effort estimate:** 2-4 hours (similar to Lever)

### What You Could Do Next
**2. SmartRecruiters Parser (1-2 days, optional)**

- Only 3 companies but high-value (Spotify, Ubisoft, King)
- Similar complexity to Ashby
- Takes you from 74% → 76%

**3. Comeet Parser (2-3 days, optional)**

- 5 companies
- More complex (may need light browser automation)
- Takes you from 76% → 79%

### What You Should NOT Do
**Build custom page parsers** for the 26 companies with their own job boards

- Requires 26+ separate implementations
- Not worth the time for 14.9% coverage
- Better to improve classifier on truncated text instead
- Or use browser automation for key companies only

---

## Comparison to Your Adzuna Sample

| Metric | Adzuna Sample (50 jobs) | Your Career Pages (174 companies) |
|--------|---|---|
| Greenhouse coverage | 0% | 52.3% |
| Lever coverage | 0% | 6.3% |
| Total easy scraping | 0% | 66.1% |
| With new parsers | 0% | 81.0% |
| Custom pages | 52% | 14.9% |
| No findable page | 48% | 0% |

**The lesson:** The Adzuna sample is heavily skewed toward SMEs and custom job boards. Your curated career page list is **far more representative** of major tech/established companies that use standardized ATS platforms.

---

## Final Recommendation

### Option A: Low-Effort, High-Impact
**Build Ashby parser only**
- **Time:** 2-4 hours
- **Coverage improvement:** 66% → 74%
- **Dataset F1 improvement:** ~0.66 → ~0.71
- **ROI:** Excellent

### Option B: Balanced Approach
**Build Ashby + SmartRecruiters**
- **Time:** 4-6 hours
- **Coverage improvement:** 66% → 76%
- **Dataset F1 improvement:** ~0.66 → ~0.72
- **ROI:** Excellent

### Option C: Maximum Coverage (Not Recommended)
**Build Ashby + SmartRecruiters + Comeet + Taleo + Browser Automation**
- **Time:** 2-3 weeks
- **Coverage improvement:** 66% → 97%+
- **Dataset F1 improvement:** ~0.66 → ~0.83+
- **ROI:** Good, but expensive

---

## Next Steps

1. **Decide:** Will you build Ashby parser? (Highly recommended - big win for minimal effort)
2. **Decide:** Will you build SmartRecruiters? (Optional but worthwhile)
3. **Decide:** Will you try Comeet/Taleo? (Lower priority)
4. **I'll build:** Custom scraper code for whichever you choose
5. **Test:** Run on 5-10 companies to validate
6. **Deploy:** Integrate into pipeline

Which option appeals to you most?

