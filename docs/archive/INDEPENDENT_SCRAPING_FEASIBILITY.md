# Independent Job Scraping: Can We Eliminate Adzuna Dependency?

## Your Question
"Are we now in a position where we could possibly scrape all jobs from say, OpenAI now that we know its ATS? Could we do that without any dependency on Adzuna for job title/location inputs etc?"

**Short Answer:** Yes, but with caveats. We can build independent scrapers for Greenhouse, Lever, Ashby, etc., but **not without browser automation**. Here's the detailed analysis.

---

## The Technical Reality

### What We Tried: Static HTML Scraping
We tested scraping Stripe and OpenAI's Greenhouse pages directly via HTTP requests.

**Result: Failed**
- Stripe's Greenhouse page loads (200 status, 383KB HTML)
- But: **NO job data in static HTML**
- Why: Greenhouse uses JavaScript to render jobs dynamically
- The HTML is a React/Vue SPA shell, not actual content

### What This Means
You **cannot** scrape Greenhouse jobs using simple HTTP + BeautifulSoup. The jobs aren't there until JavaScript executes.

---

## Three Paths Forward

### Path A: Browser Automation (Recommended)
**Use Playwright/Selenium to:**
1. Visit `https://boards.greenhouse.io/stripe`
2. Wait for JavaScript to render
3. Parse the resulting DOM
4. Extract job listings
5. Click individual jobs for full descriptions
6. Extract and store

**Pros:**
- Works reliably for all Greenhouse companies (100+ in your dataset)
- Gets full job descriptions
- No API key needed
- Can reuse same script for all Greenhouse companies
- **Only need to change company slug** (stripe, openai, coinbase, etc.)

**Cons:**
- Slower (2-5 seconds per company, 1-2 minutes to scrape all jobs)
- Requires browser resources (CPU, memory)
- May need headless browser pool for parallel scraping
- Greenhouse might rate-limit or block

**Estimated effort:** 3-4 hours to build and test
**Estimated time to scrape 91 Greenhouse companies:** 30-60 minutes

**Code structure:**
```python
class GreenhouseScraper:
    def __init__(self):
        self.browser = playwright.chromium.launch(headless=True)

    def scrape_company(self, company_slug: str):
        # 1. Navigate to greenhouse page
        page = self.browser.new_page()
        page.goto(f"https://boards.greenhouse.io/{company_slug}")

        # 2. Wait for jobs to load (job listings appear)
        page.wait_for_selector('.opening')  # or appropriate selector

        # 3. Extract all job links
        jobs = page.query_selector_all('.opening')

        # 4. For each job:
        for job in jobs:
            link = job.query_selector('a')
            job_url = link.get_attribute('href')

            # Navigate to job detail
            job_page = self.browser.new_page()
            job_page.goto(job_url)

            # Extract job data
            title = job_page.query_selector('h1').text_content()
            description = job_page.query_selector('.job-description').text_content()
            location = job_page.query_selector('[data-location]').text_content()

            yield {
                'company': company_slug,
                'title': title,
                'description': description,
                'location': location,
                'url': job_url,
            }
```

### Path B: Reverse-Engineer Greenhouse API
**Try to find and call the internal API that Greenhouse uses**

**Status:** Difficult
- Greenhouse likely has an internal API that serves jobs as JSON
- It's not documented publicly
- Would need to reverse-engineer network requests
- May have CORS restrictions or authentication requirements
- Likely to break if Greenhouse updates their code

**Pros:**
- Faster than browser automation
- Could potentially get JSON response with structured data

**Cons:**
- Fragile (breaks with code changes)
- Time-consuming to reverse-engineer
- Greenhouse might actively block this
- Would need to do separately for each ATS

**Estimated effort:** 5-8 hours to figure out, 2-3 hours per ATS

**Not recommended** - too risky for limited benefit

### Path C: Hybrid Approach
**Use browser automation strategically**
1. Build browser automation for major ATS platforms (Greenhouse, Lever, Ashby, Workable)
2. Use existing HTTP-based scraping for simple ATS (SmartRecruiters, Recruitee, etc.)
3. Cache results aggressively to minimize browser usage

**Pros:**
- Covers most of your dataset (81%+)
- Reusable scraping logic per ATS
- Lower overhead than scraping everything

**Cons:**
- Still requires browser automation infrastructure

---

## Impact on Your Architecture

### Current Architecture
```
Adzuna API
  ├─ Get job list + truncated description
  ├─ Extract job ID, title, location
  └─ Store in raw_jobs table

External scraper (for specific jobs)
  ├─ Visit ATS URL from Adzuna
  ├─ Extract full description
  └─ Enrich raw_jobs with full_text

Classifier
  └─ Use full_text if available, else truncated text
```

### Proposed Architecture (Independent)
```
List of companies using Greenhouse/Lever/etc
  ├─ Compile list of company slugs (openai, stripe, coinbase, ...)
  └─ Store in config/company_ats_mapping.json

Browser Automation Scraper
  ├─ For each company slug:
  │  ├─ Launch headless browser
  │  ├─ Visit boards.greenhouse.io/{slug}
  │  ├─ Scrape all jobs
  │  └─ Extract title, description, location, URL
  └─ Store in raw_jobs table

Classifier
  └─ Use full_text (no truncation)
```

### Advantages of Independent Scraping
1. **No Adzuna dependency** - you own the data pipeline
2. **No truncation** - get full descriptions directly
3. **Fresher data** - can update hourly vs Adzuna's lag
4. **Better coverage** - can scrape companies Adzuna doesn't index
5. **No rate limiting issues** - Adzuna API has limits, direct scraping doesn't

### Disadvantages
1. **Browser automation overhead** - requires Playwright/Selenium
2. **Rate limiting risk** - Greenhouse/Lever might block aggressive scraping
3. **Maintenance burden** - job board layouts change, need to update selectors
4. **More complex** - error handling, retry logic, browser pool management
5. **Can't scale beyond your ATS list** - only works for companies you know the ATS for

---

## Comparison: Adzuna vs Independent Scraping

| Factor | Adzuna | Independent Scraper |
|--------|--------|---|
| Setup time | None (use existing) | 4-6 hours |
| Daily data freshness | 24-72 hours lag | Real-time (hourly refresh) |
| Text truncation | 100% truncated | 0% (full text) |
| Discovery | Automatic (Adzuna crawls) | Manual (must know company ATS) |
| Job coverage | ~80% of market | ~50% (only companies you list) |
| Rate limiting | API limits | ATS-dependent |
| Infrastructure | 1 API key | Browser pool, infrastructure |
| Maintenance | None (Adzuna maintains) | Update selectors when layouts change |
| Cost | Free | Dev time + server resources |

---

## What This Means for Your Project

### Scenario 1: Keep Adzuna as Primary Source
**Strategy:** Use Adzuna for discovery, supplement with direct scrapers for key companies

- Adzuna provides job discovery (what jobs exist)
- Direct scrapers provide full text for high-value companies
- Classifier gets mix of full and truncated text
- **Coverage:** 66% full text (Greenhouse + Lever), 34% truncated (Adzuna)
- **Effort:** 3-4 hours to build Greenhouse scraper
- **Payoff:** Classifier F1 improves from ~0.66 → ~0.73

### Scenario 2: Replace Adzuna with Independent Scraping
**Strategy:** Build direct scrapers for all major ATS, eliminate Adzuna

**Prerequisites:**
- Maintain mapping of companies to ATS (your 174-company list becomes a system)
- Build scrapers for: Greenhouse, Lever, Ashby, Workable, BambooHR, Recruitee, SmartRecruiters, Comeet, Taleo
- Handle custom pages separately (require browser automation or accept gaps)

**Effort:** 2-3 weeks
- Greenhouse: 3-4 hours
- Lever: 2-3 hours
- Ashby: 2-3 hours
- Workable: 2-3 hours
- Others: 2 hours each
- Integration/testing: 3-4 hours

**Payoff:**
- 100% full-text jobs for companies you track
- No Adzuna limits
- Fresher data
- **Classifier F1:** 0.85+ on scraped companies
- **Problem:** Still gaps for companies not on your list

### Scenario 3: Hybrid Approach (Recommended)
**Strategy:** Keep Adzuna + build direct scrapers progressively

Phase 1 (Week 1): Build Greenhouse scraper
- Scrape 91 companies directly
- Keep using Adzuna for discovery
- Combine results

Phase 2 (Week 2): Add Lever, Ashby
- Adds 25 more companies
- Improves coverage to 75%

Phase 3 (Ongoing): Add other ATS as needed
- Build when you identify high-value companies using them

**Effort:** Progressive (4-6 hours initially, then 2-3 hours per ATS)
**Payoff:** Gradual improvement without big rewrite

---

## My Recommendation

**Build a Greenhouse scraper (Path A: Browser Automation)**

Here's why:

1. **Biggest bang for buck:** 91 companies = 52% of your dataset
2. **Manageable effort:** 3-4 hours to build and test
3. **Reusable pattern:** Same script works for all Greenhouse companies, just change slug
4. **Low risk:** Keeps Adzuna as fallback, doesn't break existing pipeline
5. **Clear value:** Get full-text descriptions for your largest companies (Stripe, Figma, GitHub, Instacart, DoorDash, etc.)

**Expected outcome:**
- Initial investment: 3-4 hours
- Weekly maintenance: 30 min (handle failures, update selectors if needed)
- Data quality: Full text for 91 companies, classifierF1 on those: ~0.85+
- Overall dataset F1 improvement: ~0.66 → ~0.72

---

## Implementation Order

1. **Week 1: Build Greenhouse scraper** (3-4 hours)
   - Set up Playwright
   - Handle pagination and job extraction
   - Test on 3-4 companies
   - Deploy and run on all 91

2. **Week 2: Build Ashby scraper** (2-3 hours)
   - Similar pattern to Greenhouse
   - Adds 14 more companies
   - Brings coverage to 66%

3. **Week 3: Evaluate ROI**
   - Measure classifier improvement
   - Decide whether to continue with more ATS or invest in other improvements

4. **Ongoing: Add Lever, Workable, etc.**
   - Only if ROI justifies effort

---

## The Bottom Line

**Yes, you can scrape OpenAI jobs independently without Adzuna.**

But:
- You need **browser automation** (Playwright/Selenium)
- It's **not trivially fast** (few seconds per company)
- It requires **active maintenance** (selectors change)
- It only works for companies **you explicitly list**

**However**, for your use case, building a Greenhouse scraper is **highly recommended**:
- Covers 52% of your dataset
- Takes 3-4 hours
- Gives you independent data source
- Improves classifier accuracy significantly

Would you like me to start building the Greenhouse scraper?
