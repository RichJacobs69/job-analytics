# CLAUDE.md Archive

> **Purpose:** Historical content archived from CLAUDE.md during cleanup (2025-12-22).
> Preserved for blog post reference about the job-analytics project journey.

---

## Implementation Roadmap: Dual Pipeline Integration (Completed)

> **Status:** Phases 1-4 [DONE] - See "Project Roadmap (Weeks 1-5)" section below for current progress

**Phase 1: ATS Validation** [DONE]
- Test 91 companies in config to confirm which still use Greenhouse
- Some companies may have migrated (e.g., Brex) - update mapping
- Output: Updated `config/greenhouse/company_ats_mapping.json` with company slugs

**Phase 2: Create Unified Job Ingester** [DONE]
- [DONE] File: `unified_job_ingester.py` implemented
- [DONE] Accepts jobs from multiple sources (Adzuna + Greenhouse)
- [DONE] Deduplicates: MD5 hash of (company + title + location)
- [DONE] Prioritizes Greenhouse descriptions (9,000+ chars vs 100-200)
- [DONE] Tracks source for each job (adzuna, greenhouse, hybrid)
- [DONE] Normalizes format for unified classifier pipeline

**Phase 3: Update Main Pipeline** [DONE]
- [DONE] Created: `fetch_jobs.py` dual-source orchestrator
- [DONE] Supports: `python fetch_jobs.py [city] [max_jobs] --sources adzuna,greenhouse`
- [DONE] Fetches from both Adzuna API and Greenhouse in parallel
- [DONE] Merges via unified_job_ingester.py
- [DONE] Passes merged jobs to classifier pipeline

**Phase 4: Run Greenhouse Scraper at Scale** [DONE] (2025-11-28, Ongoing)
- [DONE] Initial production run: 109 companies processed, 62 with active jobs
- [DONE] Scraper integrated into main pipeline and running continuously
- [DONE] Current dataset: 1,213 Greenhouse jobs successfully stored (as of 2025-12-07)
- [DONE] Ready: For analytics queries and compensation benchmarking

---

## Analytics Layer & Marketplace Questions (Original Planning)

**Core Purpose:** The entire pipeline exists to answer 35 marketplace questions for job seekers and employers (see `docs/marketplace_questions.yaml`).

### Analytics Architecture (Original Streamlit Plan)

```
enriched_jobs table (clean, classified data)
    |
analytics.py (aggregation, trends, filtering)
    |-- Time series queries (growth rates, trends)
    |-- Geographic comparisons (city-level insights)
    |-- Skill co-occurrence analysis
    +-- Compensation benchmarking
    |
streamlit_app.py (front-end visualization)
    |-- Interactive filters (role, city, time range)
    |-- Trend charts (Plotly)
    |-- Skill demand heatmaps
    +-- Salary distribution plots
```

> **Note:** This was replaced by Next.js dashboard at richjacobs.me/projects/hiring-market

### Key Analytics Modules (Original Plan)

**analytics.py** (Query Layer - to be built)
- Encapsulates common query patterns for marketplace questions
- Time-series aggregations (monthly/quarterly trends)
- Geographic segmentation (compare London vs NYC vs Denver)
- Skill extraction and co-occurrence matrices
- Compensation analysis (percentiles, distributions, by location)
- Role growth tracking (which subfamilies are hiring most)

**streamlit_app.py** (Visualization Layer - to be built)
- Non-technical user interface for exploring data
- Interactive filters: date range, city, job function, seniority
- Pre-built dashboards for common questions
- Export functionality (CSV, charts)
- Refresh cadence: daily (matches pipeline runs)

### Marketplace Questions Coverage

The platform answers **35 marketplace questions** across 7 categories. Here are examples mapped to implementation:

**1. Market Demand & Supply**
- *"Which job subfamilies are growing fastest in Product/Data in each city?"*
  - Query: Count jobs by subfamily, city, month -> calculate month-over-month growth rate
  - Visualization: Line chart showing trajectory by city

- *"Is demand for my skill increasing or decreasing vs last year?"*
  - Query: Count jobs mentioning skill X by month -> year-over-year comparison
  - Visualization: Trend line with YoY % change annotation

**2. Skills Gap & Upskilling**
- *"Which tools/skills are most listed for Analytics Engineer roles in London?"*
  - Query: Extract skills from jobs where `job_subfamily='analytics_engineer'` AND `city_code='lon'`
  - Aggregation: Count frequency, rank by occurrence
  - Visualization: Bar chart of top 10-15 skills

- *"Which adjacent skills are most frequently co-mentioned with my core skill?"*
  - Query: Find jobs with skill X, extract all other skills, calculate co-occurrence matrix
  - Visualization: Network graph or ranked list

**3. Work Arrangement & Location**
- *"What % of Data Engineer postings in Denver are Onsite, Hybrid, or Remote?"*
  - Query: Count jobs by `working_arrangement` where `job_subfamily='data_engineer'` AND `city_code='den'`
  - Visualization: Pie chart or stacked bar

- *"Where are most AI Engineer roles that allow Remote work?"*
  - Query: Count jobs where `job_subfamily='ai_engineer'` AND `working_arrangement='remote'`, group by city
  - Visualization: Bar chart ranked by city

**4. Compensation & Transparency**
- *"What is the distribution of posted salary ranges for Data Scientist roles in NYC?"*
  - Query: Extract `compensation.base_salary_range` where `job_subfamily='data_scientist'` AND `city_code='nyc'`
  - Aggregation: Calculate percentiles (25th, 50th, 75th, 90th)
  - Visualization: Box plot or histogram

- *"Which salary ranges are most frequently advertised for Product Manager roles in NYC?"*
  - Query: Bin salary ranges, count frequency
  - Visualization: Histogram with modal range highlighted

**5. Competitive Positioning**
- *"Which competitors posted the most Platform PM roles in London last quarter?"*
  - Query: Count jobs by `employer.name` where `job_subfamily='platform_pm'` AND `city_code='lon'` AND `posted_date` in Q range
  - Visualization: Ranked bar chart of top 10 employers

- *"Which employers most frequently hire for my skill set in NYC?"*
  - Query: Match user's skills against job skills, rank employers by match frequency
  - Visualization: Ranked list with match percentage

**6. Title & Leveling Clarity**
- *"If I'm a Data Product Manager, which alternate titles describe similar work?"*
  - Query: Find jobs with similar skill profiles, extract `role.title_display`, cluster by similarity
  - Visualization: List of equivalent titles with example job URLs

**7. Role Scope & Realism**
- *"For Senior Data roles in Denver, what experience ranges are most listed?"*
  - Query: Extract `role.experience_range` where `seniority='senior'` AND `job_family='data'` AND `city_code='den'`
  - Aggregation: Bin ranges (0-2, 2-5, 5-7, 7-10, 10+), count frequency
  - Visualization: Bar chart showing distribution

### Example Query Patterns

**Time series aggregation:**
```sql
-- Growth rate by job subfamily, monthly
SELECT
  job_subfamily,
  DATE_TRUNC('month', posted_date) AS month,
  COUNT(*) AS job_count,
  LAG(COUNT(*)) OVER (PARTITION BY job_subfamily ORDER BY DATE_TRUNC('month', posted_date)) AS prev_month,
  (COUNT(*) - LAG(COUNT(*)) OVER (...)) / LAG(COUNT(*)) AS growth_rate
FROM enriched_jobs
WHERE city_code = 'lon'
  AND posted_date >= NOW() - INTERVAL '12 months'
GROUP BY job_subfamily, month
ORDER BY month DESC, growth_rate DESC;
```

**Skill co-occurrence:**
```sql
-- Which skills appear together with 'Python'?
WITH python_jobs AS (
  SELECT job_id, skills
  FROM enriched_jobs
  WHERE 'Python' = ANY(skills)
)
SELECT
  UNNEST(skills) AS co_occurring_skill,
  COUNT(*) AS frequency,
  COUNT(*) * 100.0 / (SELECT COUNT(*) FROM python_jobs) AS percentage
FROM python_jobs
WHERE UNNEST(skills) != 'Python'
GROUP BY co_occurring_skill
ORDER BY frequency DESC
LIMIT 20;
```

**Geographic comparison:**
```sql
-- Compare working arrangements across cities for Data Engineers
SELECT
  city_code,
  working_arrangement,
  COUNT(*) AS count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY city_code) AS percentage
FROM enriched_jobs
WHERE job_subfamily = 'data_engineer'
  AND posted_date >= NOW() - INTERVAL '3 months'
GROUP BY city_code, working_arrangement
ORDER BY city_code, percentage DESC;
```

### Front-End User Experience (Original Streamlit Plan)

**Streamlit Dashboard Sections:**

1. **Market Overview**
   - Total jobs by city (last 30 days)
   - Trending roles (biggest % growth)
   - Remote vs onsite split by city

2. **Role Explorer**
   - Filter: Job subfamily, city, seniority, working arrangement
   - Output: Job count, salary range (if available), top skills
   - Time series: Trend over last 6-12 months

3. **Skills Demand**
   - Search: Enter a skill (e.g., "PyTorch")
   - Output: Jobs mentioning it (count, %), trend chart, co-occurring skills
   - Comparison: Compare 2-3 skills side-by-side

4. **Compensation Benchmarks** (NYC/Denver focus)
   - Filter: Role, seniority, city
   - Output: Salary distribution (percentiles), sample job links
   - Note: Limited to transparent markets (NYC, Denver > London)

5. **Employer Activity**
   - Filter: City, role, time period
   - Output: Top hiring employers, posting frequency
   - Use case: Target applications to most active companies

### Analytics Development Priorities (Original Plan)

**Phase 1 (after Epic 4 validation):**
1. Build `analytics.py` with core query functions
2. Create basic Streamlit app with 2-3 dashboards
3. Validate insights against manual spot-checks
4. Deploy to Streamlit Cloud (free tier)

**Phase 2 (Polish & Expand):**
1. Add more sophisticated visualizations (Plotly, network graphs)
2. Implement caching for expensive queries
3. Add export functionality (CSV, PDF reports)
4. Gather user feedback, iterate on dashboards

**Success criteria:**
- Non-technical users can answer marketplace questions without SQL
- Insights load in <5s (caching, indexing)
- Median 2-3 "new useful insights" per user session (pilot testing)

### Why Clean Data Matters for Analytics

**Example impact of truncation on insights:**

*Question:* "What % of ML Engineer jobs are remote?"

| Data Quality | Result | Confidence |
|---|---|---|
| Adzuna only (truncated text) | 45% remote | Low - F1=0.565 means ~43% misclassified |
| Dual pipeline (Greenhouse full text) | 32% remote | High - F1>=0.85 means <15% misclassified |

**Without accurate classification:** Users get misleading insights, make wrong career decisions, platform has no value.

**With accurate classification:** Users trust the data, discover real trends, platform becomes indispensable.

This is why the Greenhouse integration is critical - it's not just about data quality, it's about **making the entire analytics layer usable**.

---

## Completed Epics (Historical Details)

### Epic 1: Data Ingestion Pipeline [DONE]
**Goal:** Fetch jobs from multiple sources and merge with deduplication

**Components:**
- `scrapers/adzuna/fetch_adzuna_jobs.py` - Paginated API client for Adzuna Jobs API
- `scrapers/greenhouse/greenhouse_scraper.py` - Browser automation scraper for Greenhouse career pages (24 companies verified)
- `unified_job_ingester.py` - Merge & deduplication logic (MD5 hashing by company + title + location)
- `fetch_jobs.py` - Main orchestrator supporting `--sources adzuna,greenhouse` flag

**Status:** Operational - dual pipeline running, 1,045 Greenhouse jobs + continuous Adzuna intake

**Key Achievement:** Full job descriptions (9,000-15,000+ chars) now captured from premium companies vs 100-200 char truncation from Adzuna alone

**Recent Fix (2025-11-24):** Adzuna integration fully operational after resolving 3 bugs:
1. Import path correction (`scrapers.adzuna.fetch_adzuna_jobs`)
2. Async/await mismatch fix (function is synchronous)
3. Dict-to-UnifiedJob conversion added (transforms API dicts to dataclass objects)
- E2E pipeline verified working with both sources
- See `docs/archive/FIXES_APPLIED_2025-11-24.md` for details

---

### Epic 2: Job Classification & Enrichment [DONE]
**Goal:** Extract structured insights from job postings using Claude LLM

**Components:**
- `classifier.py` - LLM integration (Claude 3.5 Haiku) with structured JSON output
- `agency_detection.py` - Two-tier filtering (hard blacklist + soft pattern matching)
- `docs/schema_taxonomy.yaml` - Centralized classification rules
- `backfill_agency_flags.py` - Retroactive updates for historical data

**Extracts:**
- Job function (Data Analyst, Data Engineer, AI Engineer, Product Manager, etc.)
- Seniority level (Junior, Mid-Level, Senior, Staff+)
- Technical skills (Python, SQL, PyTorch, dbt, etc.)
- Working arrangement (Onsite, Hybrid, Remote)
- Compensation (when available in posting)

**Status:** Operational - 93% accuracy on complete text, **actual measured cost $0.00388/job** with Haiku (validated 2025-11-25)
- **Token usage (Greenhouse full-text jobs):** ~4,156 input tokens/job, ~233 output tokens/job
- **Cost tracking:** Implemented in classifier.py using actual Anthropic API token counts
- **Monthly estimate:** 1,500 jobs/month x $0.00388 = ~$5.82/month (well under budget)

**Known Issue:** Agency spam filtering catches 10-15% pre-LLM (hard) + 5-10% post-LLM (soft), but ~21.6% still leaks through - ongoing refinement needed

---

### Epic 3: Database & Data Layer [DONE]
**Goal:** Persist raw and enriched job data in queryable form

**Components:**
- `db_connection.py` - Supabase PostgreSQL client with connection pooling
- Schema: `raw_jobs` (original postings with source tracking + title/company metadata) + `enriched_jobs` (classified results with source tracking)
- Helper functions: deduplication hashing, batch inserts, error handling

**Status:** Stable - schema tested with 1,000+ jobs, queries performant

**Recent Enhancement (2025-12-02):** Added `title` and `company` columns to raw_jobs table to preserve original source metadata before classification. Enables direct analysis of raw_jobs without joins and provides fallback data when classification fails. See `docs/database/SCHEMA_UPDATES.md` for details.

---

### Epic 4: Pipeline Validation & Economics [DONE]
**Goal:** Validate that the dual pipeline is viable before investing in analytics layer

**Status:** DONE (validated 2025-11-25)

**Validation Results:**
- [DONE] Dual-source integration working (Adzuna + Greenhouse)
- [DONE] Deduplication logic operational (0 duplicates in test batches)
- [DONE] Classification: 93% accuracy on Greenhouse full text
- [DONE] Storage: 100% success rate with proper source tracking
- [DONE] Agency filtering: Working (blocks 10-15% pre-LLM, flags 5-10% post-LLM)
- [DONE] Unit economics: **$0.00388/job actual measured cost** (well under $0.005 target)
- [DONE] Token usage tracking: Implemented in classifier.py using Anthropic API metrics
- [DONE] Pipeline reliability: <5% failure rate achieved

**Actual Cost Metrics (Measured 2025-11-25):**
- **Input tokens:** ~4,156 tokens/job (Greenhouse full-text, 11K+ chars)
- **Output tokens:** ~233 tokens/job
- **Cost per classification:** $0.00388/job
- **Cost per unique merged job:** $0.00340/job (accounting for deduplication)
- **Monthly estimate:** 1,500 jobs/month = ~$5.10/month
- **Budget headroom:** $15-20/month supports 4,400-5,900 jobs/month

**Key Achievement:** Cost tracking now embedded in production pipeline via `classifier.py`, not just validation

**Production Data Collection (Cumulative as of 2025-12-07):**
- [DONE] **Adzuna Pipeline:** Ongoing continuous collection from all 3 cities (London, NYC, Denver)
  - **Current total:** 4,963 raw jobs -> 4,676 enriched jobs
  - **All 11 role types covered:** Data Scientist, Data Engineer, ML Engineer, Analytics Engineer, Data Analyst, AI Engineer, Data Architect, Product Manager, Technical PM, Growth PM, AI PM
  - **Storage:** All jobs successfully stored in Supabase (raw_jobs + enriched_jobs tables)
- [DONE] **Greenhouse Pipeline:** Ongoing scraping from configured companies
  - **Current total:** 1,213 Greenhouse raw jobs -> 953 enriched jobs
  - **Storage:** All jobs successfully stored with proper source tracking
  - **Combined dataset:** 4,676 Adzuna + 953 Greenhouse = 5,629 total enriched jobs ready for analytics

**Validation Artifacts:**
- `validation_actual_costs.json` - 7-job test with real API costs
- `validation_e2e_success.json` - E2E pipeline test results
- `validation_e2e_final.json` - Final E2E validation

**Decision:** Pipeline validated as economically viable. Sufficient dataset collected. Ready to proceed to Epic 5 (Analytics Query Layer).

---

### Epic 5: Analytics Query Layer [DONE]
**Goal:** Programmatically answer marketplace questions from enriched job data

**Status:** DONE (2025-12-16)

**Implementation Approach:**
- **Architecture:** Next.js API routes (TypeScript) instead of Python `analytics.py`
- **Location:** `portfolio-site/app/api/hiring-market/` directory
- **Query Layer:** Supabase JS client with server-side filtering
- **Deployed:** Live at `richjacobs.me/projects/hiring-market`

**Completed Components:**
- [DONE] `/api/hiring-market/role-demand` - Role demand by city/subfamily
- [DONE] `/api/hiring-market/top-skills` - 3-level skill hierarchy (domain -> family -> skill)
- [DONE] `/api/hiring-market/working-arrangement` - Remote/Hybrid/Onsite split
- [DONE] `/api/hiring-market/top-companies` - Employer hiring activity
- [DONE] `/api/hiring-market/experience-distribution` - Seniority level distribution
- [DONE] `/api/hiring-market/count` - Job count with filters
- [DONE] `/api/hiring-market/last-updated` - Pipeline freshness indicator

**Query Patterns Implemented:**
- Time series filtering (7/30/90 days, all time)
- Geographic segmentation (London/NYC/Denver)
- Skill demand tracking with hierarchical grouping
- Work arrangement distribution by role
- Employer activity ranking

**Success Criteria Met:**
- [DONE] 5 marketplace questions answered programmatically
- [DONE] Query latency <5s with caching optimizations
- [DONE] Server-side filtering reduces bandwidth
- [DONE] Type-safe contracts between API and frontend
- [DONE] Unit tests completed
- [DONE] E2E tests completed

**See:** `docs/epic5_analytics_layer_planning.md` for detailed implementation phases

**Depends On:** Epic 4 [DONE]
**Unblocks:** Epic 6 [DONE]

---

### Epic 6: Dashboard & Visualization [DONE]
**Goal:** Non-technical users can explore insights without SQL

**Status:** DONE (2025-12-16)

**Implementation Approach:**
- **Architecture:** Next.js dashboard (React 19) instead of Streamlit
- **Location:** `portfolio-site/app/projects/hiring-market/` directory
- **Charts:** Chart.js + sunburst-chart for interactive visualizations
- **Design:** Matches richjacobs.me design system (Geist fonts, lime/emerald accents)
- **Deployed:** Live at `richjacobs.me/projects/hiring-market`

**Completed Components:**
- [DONE] Global filter system (date range, city, job family)
- [DONE] Custom dropdowns with smooth animations
- [DONE] Real-time job count display
- [DONE] Five interactive visualizations:
  1. **Role Demand Chart** - Bar chart with gradient coloring by volume
  2. **Skills Demand Chart** - 3-level sunburst (domain -> family -> skill)
  3. **Working Arrangement Chart** - Stacked bar chart (Remote/Hybrid/Onsite)
  4. **Top Companies Chart** - Ranked bar chart by hiring activity
  5. **Experience Distribution Chart** - Seniority level distribution

**Features Implemented:**
- [DONE] Interactive filters with URL-ready architecture
- [DONE] Chart.js visualizations with custom styling
- [DONE] Smooth loading states with skeleton loaders
- [DONE] Frontend caching for instant role switching
- [DONE] Last updated timestamp with relative time
- [DONE] Data source indicators for quality transparency
- [DONE] Share functionality with Web Share API + clipboard fallback
- [DONE] Responsive design (desktop-focused for portfolio demos)
- [DONE] Error handling and empty states

**Success Criteria Met:**
- [DONE] 5 marketplace questions answered with visualizations
- [DONE] Consistent with richjacobs.me design system
- [DONE] Loads in <3s with caching
- [DONE] Professional polish suitable for portfolio
- [DONE] Added to main site's projects page
- [DONE] GitHub repo documentation available
- [DONE] Browser tested (Chrome, Firefox, Safari)
- [DONE] Unit tests completed
- [DONE] E2E tests completed

**See:** `docs/epic5_analytics_layer_planning.md` for detailed implementation phases

**Depends On:** Epic 5 [DONE] (implemented together)
**Unblocks:** Epic 7 (automation to keep dashboard fresh)

---

## Epic 4 Completion Summary

**Status:** COMPLETE (2025-11-26)

Epic 4 validated the dual-source pipeline is economically viable and technically sound, then executed production data collection.

**Validation Approach (2025-11-25):**
- Small-scale testing (7-10 jobs) proved pipeline mechanics
- Actual cost tracking implemented in production code (`classifier.py`)
- Measured real token usage from Anthropic API instead of estimates

**Economic Viability:**
- **Target:** <=$0.005/job -> **Actual:** $0.00388/job (23% under target)
- **Monthly budget:** $15-20 -> **Actual usage:** ~$5.10 for 1,500 jobs (66-74% under budget)
- **Headroom:** Can process 4,400-5,900 jobs/month sustainably

**Technical Validation:**
- Dual-source integration working (Adzuna + Greenhouse)
- Deduplication preventing duplicate classifications
- Classification accuracy 93% on full-text jobs
- Storage 100% success rate
- Agency filtering blocking 10-15% of jobs pre-LLM

**Production Data Collection:**
- **Adzuna (2025-11-26):** 1,279 raw jobs -> 1,044 enriched jobs (all 3 cities, 11 role types)
- **Greenhouse (2025-11-28):** 109 companies, 3,913 scraped, 207 kept (94.7% filter), 184 stored
- **Combined dataset:** 1,228 total enriched jobs (1,044 + 184)

**Key Innovation:**
Cost tracking now embedded in production pipeline, not just validation scripts. Every classification returns actual token counts and costs for ongoing observability.

**Decision:** Pipeline validated. Dataset collected. Ready to proceed to Epic 5 (Analytics Query Layer).

---

## Web Scraping Integration (Completed)

**Goal:** Get full job text instead of truncated Adzuna descriptions

**Implemented in:**
1. `greenhouse_scraper.py` (browser automation with Playwright)
   - Accepts company list from `config/greenhouse/company_ats_mapping.json`
   - Handles page navigation, infinite scroll, dynamic content
   - Extracts full job descriptions (9,000-15,000+ chars)
   - Handles timeouts, rate limiting, headless browser errors

2. `unified_job_ingester.py` (data merge & deduplication)
   - Accepts jobs from Adzuna API and Greenhouse scraper
   - Deduplicates by MD5 hash of (company + title + location)
   - Prioritizes Greenhouse text when duplicates found
   - Tracks data source for analytics

3. `fetch_jobs.py` (orchestrator)
   - Calls scraper and Adzuna API in parallel
   - Passes merged jobs to classification pipeline
   - Supports --sources flag for flexible pipeline configuration

4. Testing & Validation
   - 6 active test suites covering scraper, ingestion, and E2E flows
   - Production run (2025-11-28): 109 companies processed, 3,913 jobs scraped, 184 stored
   - Validated 94.7% filter rate from combined title + location filtering
   - Tested classification on full Greenhouse text
   - Confirmed deduplication prevents duplicate processing

---

## Original Tech Stack Planning

- **Language:** Python 3.x
- **LLM:** Anthropic Claude 3.5 Haiku (via anthropic SDK)
- **Database:** Supabase (PostgreSQL client)
- **External APIs:** Adzuna Jobs API (job source)
- **Configuration:** PyYAML (taxonomy and blacklist)
- **HTTP:** Requests, httpx (API calls)
- **Secrets:** python-dotenv (environment variables)
- **Web Scraping:** Playwright (browser automation for Greenhouse scraper)
- **Analytics/Visualization (planned - Epic 5+):**
  - Streamlit (interactive dashboards) -> **REPLACED BY Next.js**
  - Plotly (charts, time series) -> **REPLACED BY Chart.js**
  - Pandas (data manipulation, aggregation)

---

## Historical Dependencies

```
python-dotenv==1.0.0       # Environment variable management
anthropic==0.25.0          # Claude API client
supabase==2.5.0            # PostgreSQL database client
pyyaml==6.0.1              # YAML parsing (taxonomy, config)
requests==2.31.0           # HTTP client for Adzuna API (updated to 2.32.4)
httpx>=0.24.0              # Alternative HTTP client
playwright>=1.40.0         # Browser automation for Greenhouse scraper

# Originally planned for analytics/visualization (Epic 5+):
# streamlit>=1.28.0        # Interactive dashboards -> NOT USED
# plotly>=5.17.0           # Interactive charts -> NOT USED
# pandas>=2.1.0            # Data manipulation -> USED
```

---

## Classification Quality Impact Analysis

### How Classification Quality Impacts Analytics

**High classification accuracy -> Trustworthy insights:**

| Classification | Impact on Analytics | Example |
|---|---|---|
| Job subfamily (F1 >=0.85) | Enables role-specific trend analysis | "ML Engineer demand grew 40% in London Q4" |
| Skills extraction (F1 >=0.80) | Powers skill demand tracking, upskilling recommendations | "PyTorch mentioned in 67% of AI Engineer jobs" |
| Working arrangement (F1 >=0.85) | Supports remote work trend analysis | "Remote Data roles dropped from 45% -> 32% in NYC" |
| Seniority (F1 >=0.85) | Enables career progression insights | "Senior -> Staff+ roles require 8-10 years experience" |
| Compensation (when available) | Salary benchmarking by role/location | "Median Data Scientist salary in NYC: $140-160K" |

**Current limitation:** Truncated text from Adzuna degrades skills and work arrangement F1 scores, reducing confidence in those analytics. Greenhouse full text (now integrated) significantly improves these metrics.

---

## Current State Snapshot (as of 2025-12-07)

### [WORKING] Positive Items
- **Dual-source pipeline operational:** Adzuna API + Greenhouse scraper both functioning
- Unified job ingestion with deduplication (MD5 hashing) reliable and tested
- Agency hard filtering prevents 10-15% of wasted API calls
- Classification achieves 93% accuracy on complete job descriptions (test cases)
- Database schema stable and queries performant
- Greenhouse scraper captures full job text (9,000-15,000+ chars)
- Greenhouse production run complete: 109 companies processed, 62 with active jobs, 184 jobs stored (2025-11-28)

### [NEEDS ATTENTION] Active Issues
1. **Skills/Work Arrangement Classification:** Limited by Adzuna's truncated text
   - For Adzuna-only jobs: Skills extraction ~29%, Work arrangement F1=0.565
   - For Greenhouse jobs: Both improve significantly with full text
   - **Mitigation:** Use `fetch_jobs.py --sources adzuna,greenhouse` for better data quality

2. **Agency Spam:** ~21.6% of Adzuna dataset from recruitment agencies despite filtering
   - Ongoing blacklist refinement needed
   - Greenhouse data has less agency spam (better quality sources)
   - May need more sophisticated detection patterns beyond hard blacklist

---

*Archive created: 2025-12-22*
*Original file: CLAUDE.md (~64KB, 1,110 lines)*
