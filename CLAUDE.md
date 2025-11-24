# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **📚 For documentation navigation and specification references, see [`docs/README.md`](docs/README.md)** - It provides a structured index of all specs (marketplace questions, taxonomy, architecture, etc.) and a recommended reading order for understanding the project.

## Project Overview

LLM-powered job market intelligence platform that fetches, classifies, and analyzes job postings using Claude AI. Ingests job data from Adzuna API, applies intelligent classification via Claude 3.5 Haiku, and stores enriched data in Supabase PostgreSQL.

**End Goal:** Answer 35 marketplace questions for job seekers and employers through an interactive Streamlit dashboard. Questions span market demand, skill trends, compensation benchmarks, work arrangements, and competitive hiring patterns across London, NYC, and Denver.

**Core Value Propositions:**
- **For job seekers:** "Which skills are in demand for my role?" "Where should I focus my job search?" "What salary can I expect?"
- **For employers:** "Which competitors are hiring most aggressively?" "What skills should we require?" "Are we competitive on comp/flexibility?"

**Current Status:**
- ✅ Epic 1: Data Ingestion Pipeline - Dual-source (Adzuna + Greenhouse) operational
- ✅ Epic 2: Job Classification & Enrichment - Claude LLM integration with agency filtering working
- ✅ Epic 3: Database & Data Layer - Schema and connections stable
- ⚠️ Epic 4: Pipeline Validation & Economics - E2E tested, needs formal validation run
- ⏳ Epic 5: Analytics Query Layer - Blocked (depends on Epic 4 validation)
- ⏳ Epic 6: Dashboard & Visualization - Blocked (depends on Epic 5)
- ⏳ Epic 7: Automation & Operational - Blocked (depends on Epic 4)

**See:** `docs/README.md` for documentation index, `docs/archive/` for implementation history, `greenhouse_validation_results.json` for ATS validation details

## Common Development Commands

```bash
# Initial setup (one-time)
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS/Linux
pip install -r requirements.txt

# Running the dual-source pipeline (Adzuna + Greenhouse)
python fetch_jobs.py [city] [max_jobs] --sources adzuna,greenhouse
# Examples:
# python fetch_jobs.py lon 100 --sources adzuna,greenhouse  # Dual pipeline
# python fetch_jobs.py nyc 50 --sources adzuna              # Adzuna only
# python fetch_jobs.py --sources greenhouse                # Greenhouse only

# Test the classifier module
python classifier.py

# Backfill agency flags on existing data
python backfill_agency_flags.py

# Validate pipeline health and economics
python validate_pipeline.py --cities lon,nyc --max-jobs 100
```

**Valid cities:** `lon` (London), `nyc` (New York), `den` (Denver)

**Environment setup:**
Create `.env` file in project root with:
```
ADZUNA_APP_ID=<your_adzuna_app_id>
ADZUNA_API_KEY=<your_adzuna_api_key>
ANTHROPIC_API_KEY=<your_anthropic_key>
SUPABASE_URL=<your_supabase_url>
SUPABASE_KEY=<your_supabase_key>
```

## Architecture & Data Pipeline

### Dual-Pipeline Architecture

**Two parallel data ingestion paths merge into single classification & analysis pipeline:**

```
PIPELINE A: Adzuna API                    PIPELINE B: Direct Web Scraping
(Mass market jobs)                        (Premium company deep-dive)

Adzuna Job API                            Greenhouse-hosted Career Pages
    ↓                                         ↓
fetch_adzuna_jobs.py                     greenhouse_scraper.py
├─ Fetch paginated results               ├─ Browser automation (Playwright)
├─ Format for processing                 ├─ Multi-company concurrent scraping
└─ Deduplication (MD5 hash)              ├─ Full job description extraction
    ↓                                     │  (9,000-15,000+ chars)
                                         ├─ All content sections captured:
                                         │  - Main description
                                         │  - Responsibilities
                                         │  - Work arrangements (hybrid/remote)
                                         │  - Pay & benefits
                                         │  - Requirements
                                         └─ Deduplication (MD5 hash)
                                             ↓

                    ┌─────────────────────┴─────────────────────┐
                    ↓                                             ↓
          UNIFIED JOB INGESTION LAYER
          (Merges both sources, handles overlap)
          ├─ Combines Adzuna + Greenhouse results
          ├─ Deduplicates by: (company + title + location) MD5
          └─ Tracks data source for each job
                    ↓
[Hard Filter - Agency Blocklist]
    ├─ Checks against config/agency_blacklist.yaml
    └─ Skips known recruitment firms (cost optimization)
    ↓
classifier.py (Claude 3.5 Haiku LLM)
    ├─ Builds structured prompt from taxonomy
    ├─ Extracts: function, level, skills, remote status
    └─ Returns JSON classification
    ↓
[Soft Detection - Agency Pattern Matching]
    ├─ Validates classifications
    └─ Flags suspected recruitment firms
    ↓
db_connection.py (Supabase PostgreSQL)
    ├─ raw_jobs table (original postings + source)
    └─ enriched_jobs table (classified results)
    ↓
analytics.py (Query & Aggregation Layer)
    ├─ Time series analysis (trends, growth rates)
    ├─ Geographic comparisons (city-level insights)
    ├─ Skill demand tracking & co-occurrence
    └─ Compensation benchmarking
    ↓
streamlit_app.py (User-Facing Dashboards)
    ├─ Interactive filters & exploration
    ├─ Pre-built views for marketplace questions
    └─ Export functionality (CSV, charts)
```

### Data Source Characteristics

| Aspect | Adzuna API | Greenhouse Scraper |
|--------|------------|-------------------|
| **Coverage** | 1,500+ jobs/month (general market) | 91 premium companies (curated) |
| **Description Length** | 100-200 chars (truncated) | 9,000-15,000+ chars (complete) |
| **Content Sections** | Basic summary only | Full job posting: responsibilities, benefits, work arrangements |
| **Update Frequency** | Continuous daily | On-demand by company |
| **Cost** | API calls (bulk) | Browser automation (moderate) |
| **Quality/Depth** | Wide but shallow | Narrow but deep |
| **Best For** | Market trends, volume analysis | Premium company deep-dive, compensation benchmarking |

### Greenhouse Scraper Status

**✅ GREENHOUSE SCRAPING IMPLEMENTED:**
- **Full descriptions captured:** 9,000-15,000+ chars per job (vs. 4,000 from main description alone)
- **Complete sections included:** Main responsibilities, Hybrid work arrangements, Pay & benefits, In-office expectations, Remote work policies
- **Tested:** 66 Stripe jobs successfully extracted with all content sections
- **Coverage:** 91 Greenhouse companies pre-configured for rapid expansion

**Example improvement:**
- Backend Engineer, Data job: Captures complete job posting including:
  - [OK] Hybrid work at Stripe
  - [OK] Pay and benefits
  - [OK] In-office expectations
  - [OK] Working remotely policies
  - [OK] Responsibilities

**✅ Phase 2 Integration Complete:**
1. ✅ ATS mapping validated for 91 companies → 24 verified with active Greenhouse (captured 1,045 jobs)
2. ✅ Greenhouse scraper integrated into `fetch_jobs.py` main pipeline orchestrator
3. ✅ Deduplication logic implemented in `unified_job_ingester.py` (Adzuna + Greenhouse merge)

### Implementation Roadmap: Dual Pipeline Integration

> **Status:** Phases 1-4 ✅ COMPLETE - See "Project Roadmap (Weeks 1-5)" section below for current progress

**Phase 1: ATS Validation** ✅ (COMPLETE)
- Test 91 companies in config to confirm which still use Greenhouse
- Some companies may have migrated (e.g., Brex) - update mapping
- Output: Updated `config/company_ats_mapping.json` with verified status

**Phase 2: Create Unified Job Ingester** ✅ (COMPLETE)
- ✅ File: `unified_job_ingester.py` implemented
- ✅ Accepts jobs from multiple sources (Adzuna + Greenhouse)
- ✅ Deduplicates: MD5 hash of (company + title + location)
- ✅ Prioritizes Greenhouse descriptions (9,000+ chars vs 100-200)
- ✅ Tracks source for each job (adzuna, greenhouse, hybrid)
- ✅ Normalizes format for unified classifier pipeline

**Phase 3: Update Main Pipeline** ✅ (COMPLETE)
- ✅ Created: `fetch_jobs.py` dual-source orchestrator
- ✅ Supports: `python fetch_jobs.py [city] [max_jobs] --sources adzuna,greenhouse`
- ✅ Fetches from both Adzuna API and Greenhouse in parallel
- ✅ Merges via unified_job_ingester.py
- ✅ Passes merged jobs to classifier pipeline

**Phase 4: Run Greenhouse Scraper at Scale** ✅ (COMPLETE)
- ✅ Validated: 24 of 91 companies actively use Greenhouse
- ✅ Extracted: 1,045 jobs from verified companies
- ✅ Tested: Full descriptions processed through classifier
- ✅ Ready: For analytics queries and compensation benchmarking

### Key Implementation Notes

- **Deduplication:** Same job may appear on both Adzuna (truncated) + Greenhouse (full). Prefer Greenhouse description if duplicate.
- **Source tracking:** Raw table should include `source` field ('adzuna' or 'greenhouse') to enable source-specific analytics later
- **Concurrent scraping:** `greenhouse_scraper.py` already supports multi-company scraping. Can run all 91 companies in ~2-3 hours with `max_concurrent_pages=2`
- **Cost optimization:** Keep Adzuna for volume (1,500/month) + Greenhouse for depth (high-value companies). No need to scrape everything.

### Directory Structure

```
job-analytics/
├── .env                        # Secrets (API keys, DB credentials)
├── .env.example                # Template for .env
├── .gitignore                  # Git exclusions
├── requirements.txt            # Python dependencies
├── CLAUDE.md                   # This file: development guide
├── greenhouse_validation_results.json  # Validated companies (24 verified, 90 tested)
├── greenhouse_validation_results.csv   # Validation export
│
├── [Core Pipeline Python Files]
├── classifier.py               # Claude LLM integration & classification
├── db_connection.py            # Supabase client and DB helpers
├── agency_detection.py         # Hard/soft agency filtering
├── backfill_agency_flags.py    # Retroactive agency flag updates
├── fetch_jobs.py               # Main pipeline orchestrator (dual-source)
├── unified_job_ingester.py     # Merge Adzuna + Greenhouse results with dedup
├── validate_greenhouse_batched.py  # ATS company validation (COMPLETE)
│
├── config/
│   ├── agency_blacklist.yaml       # Known recruitment agencies (hard filter)
│   └── company_ats_mapping.json    # Company → ATS platform mapping (verified status)
│
├── docs/                       # Documentation (see docs/README.md for index)
│   ├── README.md               # Documentation index & reading guide (START HERE)
│   ├── system_architecture.yaml # Complete system design & responsibilities
│   ├── schema_taxonomy.yaml      # Job classification taxonomy & rules
│   ├── product_brief.yaml        # Product requirements, KPIs, scope
│   ├── blacklisting_process.md   # Agency detection methodology
│   ├── pipline_flow              # ASCII/visual pipeline diagram
│   ├── marketplace_questions.yaml # User research questionnaire
│   ├── architecture/             # Architecture deep-dives
│   ├── database/                 # Schema migrations & updates
│   ├── testing/                  # Test documentation
│   └── archive/                  # Historical docs & legacy code
│
├── scrapers/
│   ├── adzuna/
│   │   ├── fetch_adzuna_jobs.py  # Adzuna API pipeline
│   │   └── sample_adzuna_jobs.csv # Sample data
│   └── greenhouse/
│       ├── greenhouse_scraper.py # Greenhouse web scraper (browser automation)
│       └── README.md
│
├── tests/                       # Test suite (6 active tests)
│   ├── test_greenhouse_scraper_simple.py
│   ├── test_end_to_end.py
│   ├── test_two_companies.py
│   └── [archived tests in docs/archive/tests/]
│
├── output/                      # Generated outputs (gitignored)
│   ├── stripe_job_page.html     # Test cache
│   ├── ats_analysis_results.json
│   └── ...other generated files
│
└── __pycache__/                # Python bytecode (auto-generated)
```

### Core Module Responsibilities

**fetch_jobs.py** (Main Dual-Pipeline Orchestrator)
- Coordinates both Adzuna API and Greenhouse scraper in parallel
- Orchestrates full pipeline: fetch → merge → classify → store
- Supports flexible source selection (adzuna, greenhouse, or both)
- Calls unified_job_ingester for deduplication and merging
- Entry point: `python fetch_jobs.py [city] [max_jobs] --sources adzuna,greenhouse`
- See `scrapers/adzuna/fetch_adzuna_jobs.py` and `scrapers/greenhouse/greenhouse_scraper.py` for source implementations

**scrapers/adzuna/fetch_adzuna_jobs.py** (Adzuna API Client)
- Fetches paginated job results from Adzuna Jobs API
- Formats raw data for processing
- Generates MD5 hash of (employer + title + city) for deduplication
- Handles API rate limiting and pagination
- Returns structured job objects for ingestion pipeline

**unified_job_ingester.py** (Merge & Deduplication)
- Combines job results from Adzuna API and Greenhouse scraper
- Deduplicates by MD5 hash of (company + title + location)
- Intelligently prefers Greenhouse descriptions (9,000+ chars vs Adzuna's 100-200)
- Tracks data source for each job for analytics segmentation
- Handles data format normalization across sources
- Returns merged job list for classification

**classifier.py** (LLM Integration)
- Reads taxonomy from `docs/schema_taxonomy.yaml`
- Builds structured classification prompts
- Calls Claude 3.5 Haiku API for inference
- Extracts structured JSON: function, level, skills, remote status, compensation
- Handles API errors and response parsing
- Contains standalone test mode: `python classifier.py`
- Cost optimized: uses cheaper Haiku model, not Opus/Sonnet
- **Current accuracy:** 93% on manual test cases with clear job descriptions, but degrades significantly on truncated text

**db_connection.py** (Data Layer)
- Initializes Supabase PostgreSQL client
- Helper functions: `generate_job_hash()` for deduplication
- Insert functions: `insert_raw_job()`, `insert_enriched_job()`
- Connection pooling and retry logic
- Error handling with graceful degradation

**agency_detection.py** (Cost Optimization)
- Hard filtering: checks against `config/agency_blacklist.yaml` BEFORE Claude calls
  - Instant, free operation - avoids expensive LLM processing
  - Currently blocks ~10-15% of jobs pre-classification
- Soft detection: pattern matching on classification results
  - Catches variations of known agencies using regex/keyword matching
  - Flags additional ~5-10% post-classification
- **Known issue:** ~21.6% of dataset is agency spam despite filtering - ongoing refinement needed
- Returns boolean flag indicating if job is from recruitment firm

**backfill_agency_flags.py** (Maintenance)
- Retroactively updates agency flags on historical records
- Used when agency blacklist is updated or soft detection rules change
- Processes `enriched_jobs` table in batches

### Classification Taxonomy

Defined in `docs/schema_taxonomy.yaml` - all rules centralized, code-independent.

**Job Functions:**
- Data roles: Product Analytics, Data Analyst, Analytics Engineer, Data Engineer, ML Engineer, Data Scientist, Research Scientist (ML/AI), AI Engineer, Data Architect
- Product roles: Core PM, Growth PM, Platform PM, Technical PM, AI/ML PM

**Seniority Levels:**
- Junior, Mid-Level, Senior, Staff+

**Track:**
- IC (Individual Contributor)
- Management

**Skills Extraction:**
- Technical competencies automatically identified from job descriptions
- Organized into families: Programming, Analytics/Stats, Classical ML, Deep Learning, LLM/GenAI, Big Data, Pipelines/Orchestration, Data Modeling, Warehouses/Lakes, MLOps, Cloud, Streaming, Visualization, Deployment, Infrastructure as Code, CI/CD, Monitoring/Observability
- **Current limitation:** Skills extraction only ~29% successful due to text truncation (improved to 85%+ with full text)

**Remote Status:**
- Onsite, Hybrid, Remote
- **Current limitation:** F1 score of 0.565 due to truncated text cutting off work arrangement details (target: ≥0.85)

**Compensation:**
- Extracted when available in job description
- Higher availability in NYC/Denver (pay transparency laws) vs London (~30%)

**Success Metrics:**
- Function/level classification F1 score target: ≥0.85 (currently 0.93 on clear text)
- Skills extraction F1 score target: ≥0.80 (currently 0.29 due to truncation)
- Working arrangement F1 score target: ≥0.85 (currently 0.565 due to truncation)
- These guide prompt engineering and taxonomy refinement

### Target Scope

**Locations:** London, New York City, Denver

**Job Titles:** Data Analyst, Data Engineer, Analytics Engineer, Data Scientist, ML Engineer, AI Engineer, Data Architect, Technical Product Manager, Product Manager, Product Owner, Growth PM, AI PM

**Success KPIs:**
- Data coverage: 5,000-7,500 unique postings per week (all 3 locations combined)
- Freshness: ≥90% of jobs ingested within 72 hours of posting
- Pipeline reliability: ≥95% successful daily runs
- Query latency: <5s (stretch goal: <2s)

## Analytics Layer & Marketplace Questions

**Core Purpose:** The entire pipeline exists to answer 35 marketplace questions for job seekers and employers (see `docs/marketplace_questions.yaml`).

### Analytics Architecture

```
enriched_jobs table (clean, classified data)
    ↓
analytics.py (aggregation, trends, filtering)
    ├─ Time series queries (growth rates, trends)
    ├─ Geographic comparisons (city-level insights)
    ├─ Skill co-occurrence analysis
    └─ Compensation benchmarking
    ↓
streamlit_app.py (front-end visualization)
    ├─ Interactive filters (role, city, time range)
    ├─ Trend charts (Plotly)
    ├─ Skill demand heatmaps
    └─ Salary distribution plots
```

### Key Analytics Modules

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
  - Query: Count jobs by subfamily, city, month → calculate month-over-month growth rate
  - Visualization: Line chart showing trajectory by city
  
- *"Is demand for my skill increasing or decreasing vs last year?"*
  - Query: Count jobs mentioning skill X by month → year-over-year comparison
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

### How Classification Quality Impacts Analytics

**High classification accuracy → Trustworthy insights:**

| Classification | Impact on Analytics | Example |
|---|---|---|
| Job subfamily (F1 ≥0.85) | Enables role-specific trend analysis | "ML Engineer demand grew 40% in London Q4" |
| Skills extraction (F1 ≥0.80) | Powers skill demand tracking, upskilling recommendations | "PyTorch mentioned in 67% of AI Engineer jobs" |
| Working arrangement (F1 ≥0.85) | Supports remote work trend analysis | "Remote Data roles dropped from 45% → 32% in NYC" |
| Seniority (F1 ≥0.85) | Enables career progression insights | "Senior → Staff+ roles require 8-10 years experience" |
| Compensation (when available) | Salary benchmarking by role/location | "Median Data Scientist salary in NYC: $140-160K" |

**Current limitation:** Truncated text from Adzuna degrades skills and work arrangement F1 scores, reducing confidence in those analytics. Greenhouse full text (now integrated) significantly improves these metrics.

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

### Front-End User Experience

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

### Analytics Development Priorities

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
| Dual pipeline (Greenhouse full text) | 32% remote | High - F1≥0.85 means <15% misclassified |

**Without accurate classification:** Users get misleading insights, make wrong career decisions, platform has no value.

**With accurate classification:** Users trust the data, discover real trends, platform becomes indispensable.

This is why the Greenhouse integration is critical - it's not just about data quality, it's about **making the entire analytics layer usable**.

## Planned Epics

The project is organized into discrete epics that can be addressed in any order or in parallel. These are not time-dependent milestones but rather distinct work packages.

### Epic 1: Data Ingestion Pipeline ✅ COMPLETE
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

### Epic 2: Job Classification & Enrichment ✅ COMPLETE
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

**Status:** Operational - 93% accuracy on complete text, **verified cost $0.00168/job** with Haiku (validated 2025-11-24)

**Known Issue:** Agency spam filtering catches 10-15% pre-LLM (hard) + 5-10% post-LLM (soft), but ~21.6% still leaks through - ongoing refinement needed

---

### Epic 3: Database & Data Layer ✅ COMPLETE
**Goal:** Persist raw and enriched job data in queryable form

**Components:**
- `db_connection.py` - Supabase PostgreSQL client with connection pooling
- Schema: `raw_jobs` (original postings with source tracking) + `enriched_jobs` (classified results)
- Helper functions: deduplication hashing, batch inserts, error handling

**Status:** Stable - schema tested with 1,000+ jobs, queries performant

---

### Epic 4: Pipeline Validation & Economics ⚠️ NEEDS FORMAL VALIDATION
**Goal:** Validate that the dual pipeline is viable before investing in analytics layer

**Current Status:** E2E testing completed successfully (Nov 24, 2025), formal validation run pending

**E2E Testing Confirmed (Nov 24):**
- ✅ Dual-source integration working (Adzuna + Greenhouse)
- ✅ Deduplication logic operational (0 duplicates in test batch)
- ✅ Classification: 93% accuracy on Greenhouse full text
- ✅ Storage: 100% success rate with proper source tracking
- ✅ Agency filtering: 60% filtered (6 out of 10 - expected behavior)
- ✅ Unit economics: $0.00168/job verified

**Next Step: Formal Validation Run**

Run comprehensive validation to generate official metrics for Epic 4 completion:

```bash
python validate_pipeline.py --cities lon,nyc --max-jobs 100 --output-file validation_metrics.json
# Runtime: ~30-45 min | Cost: ~$0.20-0.30 (100-150 classifications)
```

**Validation Criteria:**
- ✅ Unit economics ≤$0.005/job (already verified: $0.00168/job)
- ⏳ Deduplication >90% accurate (tested in E2E, needs formal metrics)
- ⏳ Skills extraction >70% with Greenhouse full text (needs validation)
- ⏳ Pipeline reliability <5% failure rate (needs scale testing)

**After Validation Passes:**
1. Mark Epic 4 as ✅ COMPLETE
2. Expand job scraping to build richer dataset:
   - Run full Greenhouse scraping across all 24 verified companies
   - Fetch larger Adzuna batches across all 3 cities (lon, nyc, den)
   - Target: 500-1,000 jobs to provide robust dataset for analytics development
3. Create `docs/PIPELINE_VALIDATION_REPORT.md` with findings
4. Proceed to Epic 5 (Analytics Query Layer)

**Outputs:**
- `validation_metrics.json` - Structured metrics and sample classifications
- `docs/PIPELINE_VALIDATION_REPORT.md` (manual) - Executive summary and go/no-go decision

**Depends On:** Nothing (ready to run now)
**Unblocks:** Epic 5, 6, 7 (all downstream work)

---

### Epic 5: Analytics Query Layer ⏳ PLANNED (blocked by Epic 4)
**Goal:** Programmatically answer 35 marketplace questions from enriched job data

**Components:**
- `analytics.py` - Query functions for common patterns:
  - Time series aggregation (monthly/quarterly trends, growth rates)
  - Geographic comparisons (London vs NYC vs Denver)
  - Skill demand tracking and co-occurrence analysis
  - Compensation distribution (percentiles, by location)
  - Role growth tracking (which subfamilies are hiring)

**SQL Patterns** (examples in CLAUDE.md)
- Role growth rate by city, month-over-month
- Skill co-occurrence (which skills appear together)
- Work arrangement distribution by role and location
- Salary range distribution by role/seniority/city

**Success Criteria:**
- Can programmatically answer questions like "Which skills are growing fastest for Data Engineers in NYC?"
- Query latency <5s for common aggregations
- Results validated against manual spot-checks

**Depends On:** Epic 4 (validation must pass)
**Unblocks:** Epic 6 (dashboard depends on query functions)

---

### Epic 6: Dashboard & Visualization ⏳ PLANNED (blocked by Epic 5)
**Goal:** Non-technical users can explore insights without SQL

**Components:**
- `streamlit_app.py` - Interactive dashboards with:
  - Market Overview (job volume by city, trending roles, remote split)
  - Role Explorer (filter by function/city/seniority, see top skills & trends)
  - Skills Demand (search skill, see trend & co-occurring skills)
  - Compensation Benchmarks (NYC/Denver focus, due to pay transparency laws)
  - Employer Activity (top hiring companies by role/city)

**Features:**
- Interactive filters (date range, city, job function, seniority, working arrangement)
- Charts and visualizations (Plotly)
- Export functionality (CSV, charts)
- Daily refresh (matches pipeline cadence)

**Success Criteria:**
- Users discover 2-3 new insights per session
- Dashboard loads in <5s
- Users can answer marketplace questions without SQL knowledge

**Depends On:** Epic 5 (analytics queries)
**Unblocks:** Epic 7 (automation to keep dashboard fresh)

---

### Epic 7: Automation & Operational Excellence ⏳ PLANNED (blocked by Epic 4)
**Goal:** Run pipeline reliably at scale with minimal manual intervention

**Components:**
- GitHub Actions for daily pipeline execution
- Caching layer (Redis or in-memory) for expensive queries
- Monitoring and alerting for pipeline failures
- Pre-built reports (weekly market summary, skill trends)
- Error handling and graceful degradation
- No emojis in any code to avoid issues with win unicode

**Success Criteria:**
- Daily pipeline runs execute without manual intervention
- ≥95% successful run rate
- Query results cached for <5s response time
- 1-2 users actively checking dashboard weekly

**Depends On:** Epic 4 (validation) + Epic 6 (dashboard exists)

---

## Why Epic 4 Blocks Everything

Building analytics (Epic 5), dashboards (Epic 6), or automation (Epic 7) without formal validation means:
- Dashboards showing incorrect insights if cost model breaks at scale
- Time wasted building features that won't work if deduplication fails
- Bad data discovery affecting all downstream decisions

**Current Status (Nov 24, 2025):** E2E testing completed successfully - pipeline works end-to-end. Next step is running formal validation (`validate_pipeline.py`) to generate official metrics and complete Epic 4.

**The formal validation run is small (30-45 min, ~$0.20-0.30) but critical for project viability.** After validation passes, we'll expand job scraping to build a richer dataset (500-1,000 jobs) ready for analytics development.

## Current State & Known Limitations

### ✅ Working Well
- **Dual-source pipeline operational:** Adzuna API + Greenhouse scraper both functioning
- Unified job ingestion with deduplication (MD5 hashing) reliable and tested
- Agency hard filtering prevents 10-15% of wasted API calls
- Classification achieves 93% accuracy on complete job descriptions (test cases)
- Database schema stable and queries performant
- Greenhouse scraper captures full job text (9,000-15,000+ chars)
- ATS validation complete: 24 verified companies with Greenhouse

### 🚨 Active Issues
1. **Skills/Work Arrangement Classification:** Limited by Adzuna's truncated text
   - For Adzuna-only jobs: Skills extraction ~29%, Work arrangement F1=0.565
   - For Greenhouse jobs: Both improve significantly with full text
   - **Mitigation:** Use `fetch_jobs.py --sources adzuna,greenhouse` for better data quality

2. **Agency Spam:** ~21.6% of Adzuna dataset from recruitment agencies despite filtering
   - Ongoing blacklist refinement needed
   - Greenhouse data has less agency spam (better quality sources)
   - May need more sophisticated detection patterns beyond hard blacklist

### 📋 Immediate Next Steps
**Epic 4: Formal Validation Run** (ready to execute)
- **Status:** E2E testing completed successfully (Nov 24) - pipeline works end-to-end
- **Action:** Run `python validate_pipeline.py --cities lon,nyc --max-jobs 100` to generate official metrics
- **Purpose:** Validate unit economics, deduplication efficiency, and classification quality at scale
- **After validation passes:** Expand job scraping to build 500-1,000 job dataset for analytics development
- **See:** Epic 4 section in "Planned Epics" for full details

## Key Development Workflows

### Adding a New Job Classification Category

1. **Update taxonomy:** Edit `docs/schema_taxonomy.yaml`
   - Add new function type, level, or extraction rule
   - Define how to identify it from job descriptions

2. **Update classifier prompt:** Modify `classifier.py`
   - Rebuild prompt to include new categories
   - Ensure prompt builds valid JSON schema

3. **Test classification:** Run `python classifier.py`
   - Test mode validates prompt and LLM response parsing
   - Check for hallucinations or incorrect extractions

4. **Monitor cost impact:** Haiku is cheap, but longer/more complex prompts may increase per-job cost
   - Test on sample of 10-20 jobs before rolling out

### Extending Agency Detection

**Hard filtering (before LLM calls):**
1. Add agency name to `config/agency_blacklist.yaml`
2. Re-run pipeline: `python fetch_adzuna_jobs.py [city] [max_jobs]`
3. New blacklist entries apply immediately to new jobs

**Soft detection (pattern matching):**
1. Update soft detection logic in `agency_detection.py`
2. Add regex patterns or keyword matching for agency variations
3. Run `python backfill_agency_flags.py` to retroactively flag existing jobs

### Web Scraping Integration ✅ COMPLETE

**Goal:** Get full job text instead of truncated Adzuna descriptions

**Implemented in:**
1. ✅ `greenhouse_scraper.py` (browser automation with Playwright)
   - Accepts company list from `config/company_ats_mapping.json`
   - Handles page navigation, infinite scroll, dynamic content
   - Extracts full job descriptions (9,000-15,000+ chars)
   - Handles timeouts, rate limiting, headless browser errors

2. ✅ `unified_job_ingester.py` (data merge & deduplication)
   - Accepts jobs from Adzuna API and Greenhouse scraper
   - Deduplicates by MD5 hash of (company + title + location)
   - Prioritizes Greenhouse text when duplicates found
   - Tracks data source for analytics

3. ✅ `fetch_jobs.py` (orchestrator)
   - Calls scraper and Adzuna API in parallel
   - Passes merged jobs to classification pipeline
   - Supports --sources flag for flexible pipeline configuration

4. ✅ Testing & Validation
   - 6 active test suites covering scraper, ingestion, and E2E flows
   - Successfully extracted 1,045 jobs from 24 Greenhouse companies
   - Tested classification on full Greenhouse text
   - Confirmed deduplication prevents duplicate processing

### Adding a New Data Source Location

1. Update `fetch_adzuna_jobs.py` with new city code and Adzuna parameters
2. Update `docs/schema_taxonomy.yaml` with location scope
3. Update `docs/product_brief.yaml` with new location in success metrics
4. Run pipeline: `python fetch_adzuna_jobs.py [new_city] [max_jobs]`
5. Monitor first run for data quality and classification accuracy

## Important Implementation Details

### Cost Optimization

- **Hard filtering before LLM:** Only valid jobs reach Claude, avoiding wasted API calls on known recruiters
- **Cheap model selection:** Claude 3.5 Haiku used instead of Opus/Sonnet - much lower cost per classification
- **Batch deduplication:** MD5 hash prevents re-classifying duplicate jobs
- **Actual cost per job:** $0.00168/job for classifications (Haiku pricing) - **VERIFIED 2025-11-24**
- **Cost per unique merged job:** $0.00112/job (accounting for deduplication)
- **Example cost:** 100 jobs × $0.00112 = $0.11 total
- **Monthly estimate:** 1,500 jobs/month = ~$1.68 (vs previous incorrect estimate of $6+/month)
- **Budget:** $15-20/month → can process 13,000+ jobs/month sustainably

### Deduplication Strategy

- **Key:** MD5 hash of (employer name + job title + city)
- **Logic:** Same job posted in same city from same employer = duplicate
- **Prevents:** Duplicate classifications, double-counting in analytics
- **Checked before:** Hard filtering and LLM calls (save costs)

### Two-Tier Agency Detection

**Hard filter (immediate, free):**
- Checks raw employer name against blacklist
- If match found, skip LLM processing entirely
- Saves cost on known recruiting firms
- Currently blocks ~10-15% of jobs

**Soft detection (post-LLM):**
- Runs on classification results
- Uses pattern matching on extracted company name
- Catches variations: "ABC Recruiting", "ABC Staffing", etc.
- Flags additional ~5-10% post-classification
- Updates agency flag for retroactive analysis

**Known gap:** Still ~21.6% agency spam getting through - needs ongoing refinement

### Error Handling

- Retries on Adzuna API rate limiting (exponential backoff)
- Graceful degradation if classification fails (marks as low confidence)
- Database connection pooling with automatic reconnection
- Validates JSON schema of LLM responses

## Tech Stack

- **Language:** Python 3.x
- **LLM:** Anthropic Claude 3.5 Haiku (via anthropic SDK)
- **Database:** Supabase (PostgreSQL client)
- **External APIs:** Adzuna Jobs API (job source)
- **Configuration:** PyYAML (taxonomy and blacklist)
- **HTTP:** Requests, httpx (API calls)
- **Secrets:** python-dotenv (environment variables)
- **Web Scraping:** Playwright (browser automation for Greenhouse scraper)
- **Analytics/Visualization (planned - Epic 5+):**
  - Streamlit (interactive dashboards)
  - Plotly (charts, time series)
  - Pandas (data manipulation, aggregation)

## Dependencies

```
python-dotenv==1.0.0       # Environment variable management
anthropic==0.25.0          # Claude API client
supabase==2.5.0            # PostgreSQL database client
pyyaml==6.0.1              # YAML parsing (taxonomy, config)
requests==2.31.0           # HTTP client for Adzuna API
httpx>=0.24.0              # Alternative HTTP client
playwright>=1.40.0         # Browser automation for Greenhouse scraper

# To be added for analytics/visualization (Epic 5+):
# streamlit>=1.28.0        # Interactive dashboards
# plotly>=5.17.0           # Interactive charts
# pandas>=2.1.0            # Data manipulation
```

## Environment Variables

Required in `.env`:
```
ADZUNA_APP_ID=<your_app_id>       # Adzuna API authentication
ADZUNA_API_KEY=<your_api_key>     # Adzuna API authentication
ANTHROPIC_API_KEY=<your_key>      # Claude API access
SUPABASE_URL=<database_url>       # PostgreSQL connection
SUPABASE_KEY=<database_key>       # PostgreSQL authentication
```

Never commit `.env` file - use `.env.example` as template for contributors.

## Documentation Files

Refer to these YAML/Markdown files for detailed specifications:

- **system_architecture.yaml** - Read this first for complete system overview, all module interactions, and responsibilities
- **schema_taxonomy.yaml** - Job classification rules; update this to change what gets extracted
- **product_brief.yaml** - Product requirements, business context, success metrics, and target scope
- **blacklisting_process.md** - Detailed explanation of agency detection methodology
- **marketplace_questions.yaml** - Key business questions the platform must answer for job seekers and employers
- **agency_blacklist.yaml** - The actual list of agencies to hard-filter (maintain actively)

## Quick Start for New Contributors

1. Clone repo and set up environment:
   ```bash
   git clone <repo_url>
   cd job-analytics
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. Create `.env` from `.env.example` and add your API keys

3. Read documentation in this order:
   - This file (CLAUDE.md) - overview and common tasks
   - docs/system_architecture.yaml - detailed system design
   - docs/schema_taxonomy.yaml - classification rules

4. Test classifier on sample data:
   ```bash
   python classifier.py
   ```

5. Fetch small batch of jobs:
   ```bash
   python fetch_adzuna_jobs.py lon 10
   ```

6. Check database for results (Supabase dashboard)

## Troubleshooting

**Classification returning garbage/hallucinations:**
- Check if job description is truncated (current known issue)
- Verify taxonomy YAML is properly formatted
- Test prompt in Claude web interface first
- Check Haiku response for JSON parsing errors

**Agency detection not working:**
- Verify `config/agency_blacklist.yaml` exists and is formatted correctly
- Run `python backfill_agency_flags.py` to update historical data
- Check soft detection patterns in `agency_detection.py`

**Database connection failures:**
- Verify `.env` has correct Supabase credentials
- Check Supabase dashboard for connection limits
- Look for connection pooling issues in logs

**High API costs:**
- Check if hard filtering is working (should block 10-15% of jobs)
- Verify deduplication is preventing re-classification
- Consider if taxonomy is too complex (longer prompts = higher cost)

**Low classification accuracy:**
- **Most common cause:** Text truncation from Adzuna (mitigated by Greenhouse scraper - use `--sources adzuna,greenhouse`)
- Validate taxonomy against actual job descriptions
- Check if job is from unusual industry/company type
- Review edge cases and update taxonomy rules
