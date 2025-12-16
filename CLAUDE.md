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
- ✅ Epic 4: Pipeline Validation & Economics - COMPLETE (validated 2025-11-25)
- ✅ Epic 5: Analytics Query Layer - COMPLETE (Next.js API routes implementation, 2025-12-16)
- ✅ Epic 6: Dashboard & Visualization - COMPLETE (richjacobs.me/projects/hiring-market, 2025-12-16)
- ⏳ Epic 7: Automation & Operational - Ready to start

**Current Dataset (Supabase - Source of Truth, updated 2025-12-07):**
- **Raw jobs:** 6,178 total (Adzuna: 4,963 | Greenhouse: 1,213 | Manual: 2)
- **Enriched jobs:** 5,629 total (Adzuna: 4,676 | Greenhouse: 953)
- **Companies scraped:** 302 Greenhouse companies configured (in `config/company_ats_mapping.json`)
- **Geographic distribution:** London: 2,187 (38.9%) | NYC: 1,980 (35.2%) | Denver: 888 (15.8%) | Remote: 269 (4.8%) | Unknown: 305 (5.4%)
- **Filtering rate:** 8.9% filtered, 91.1% kept
- **Note:** Cumulative dataset from continuous scraping; numbers grow with each pipeline run

**See:** `docs/README.md` for documentation index, `docs/archive/` for implementation history, `greenhouse_validation_results.json` for ATS validation details

## Common Development Commands

```bash
# Initial setup (one-time)
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS/Linux
pip install -r requirements.txt

# Running the dual-source pipeline (Adzuna + Greenhouse)
python wrapper/fetch_jobs.py [city] [max_jobs] --sources adzuna,greenhouse
# Examples:
# python wrapper/fetch_jobs.py lon 100 --sources adzuna,greenhouse  # Dual pipeline
# python wrapper/fetch_jobs.py nyc 50 --sources adzuna              # Adzuna only
# python wrapper/fetch_jobs.py --sources greenhouse                # Greenhouse only

# Running multiple cities in parallel (SIMPLIFIED - single command!):
python wrapper/run_all_cities.py
# or with custom parameters:
python wrapper/run_all_cities.py --max-jobs 100 --sources adzuna,greenhouse

# See prod_run_plan_output/PARALLEL_EXECUTION_GUIDE.md for more examples

# Check pipeline status (how many jobs have been classified):
python wrapper/check_pipeline_status.py

# Test the classifier module
python pipeline/classifier.py

# Backfill agency flags on existing data
python wrapper/backfill_agency_flags.py

# Validate pipeline health and economics
python validate_pipeline.py --cities lon,nyc --max-jobs 100

# Running tests (title filter feature)
# Fast tests (recommended - runs in ~1 second)
pytest tests/test_greenhouse_title_filter_unit.py tests/test_greenhouse_scraper_filtered.py tests/test_e2e_greenhouse_filtered.py -v -m "not integration"

# Live validation on real company (runs in ~60 seconds)
python tests/test_monzo_filtering.py

# See tests/README_TITLE_FILTER_TESTS.md for full testing guide
```

**Valid cities:** `lon` (London), `nyc` (New York), `den` (Denver)

## 🚨 CRITICAL: Long-Running Command Protocol

**WHEN EXECUTING LONG-RUNNING COMMANDS (>5 minutes), ALWAYS:**

1. **Use `run_in_background: true`** parameter in Bash tool
2. **IMMEDIATELY capture and save the shell ID** returned
3. **Store shell ID in a variable or comment** for later reference
4. **Use `BashOutput` tool with the shell ID** to check progress periodically
5. **Create a TodoWrite entry** to track the long-running task

**Example:**
```python
# CORRECT - Running long pipeline with shell ID tracking
bash_result = Bash(
    command="python fetch_jobs.py --sources greenhouse",
    run_in_background=True,
    description="Run full Greenhouse scraper on all companies"
)
# SAVE THE SHELL ID: shell_id = bash_result.shell_id (example)
# Then use: BashOutput(bash_id=shell_id) to check progress
```

**Why this matters:**
- Without shell ID, we cannot monitor progress
- Terminal buffers clear, losing all output history
- No way to check status after conversation compaction
- Hours of work can be lost with no visibility

**If a long-running job is started without shell ID:**
- ❌ Cannot check progress
- ❌ Cannot determine if stuck or still running
- ❌ Must kill and restart to regain control

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
| **Coverage** | 1,500+ jobs/month (general market) | 109 premium companies (curated) |
| **Description Length** | 100-200 chars (truncated) | 9,000-15,000+ chars (complete) |
| **Content Sections** | Basic summary only | Full job posting: responsibilities, benefits, work arrangements |
| **Update Frequency** | Continuous daily | On-demand by company |
| **Cost** | API calls (bulk) | Browser automation (moderate) |
| **Quality/Depth** | Wide but shallow | Narrow but deep |
| **Best For** | Market trends, volume analysis | Premium company deep-dive, compensation benchmarking |

### Greenhouse Scraper Status

**✅ GREENHOUSE SCRAPING IMPLEMENTED:**
- **Company coverage:** 302 Greenhouse companies configured in `config/company_ats_mapping.json`
- **Full descriptions captured:** 9,000-15,000+ chars per job (vs. 4,000 from main description alone)
- **Complete sections included:** Main responsibilities, Hybrid work arrangements, Pay & benefits, In-office expectations, Remote work policies
- **Current jobs collected:** 1,213 Greenhouse jobs across configured companies in dataset (as of 2025-12-07)
- **Title filtering:** Pre-classification filtering reduces LLM costs by 60-70% (implemented 2025-11-26)
- **Location filtering:** Combined with title filtering achieves 94.7% filter rate in production
- **Pagination support:** Multi-page navigation (Load More, Next buttons, page numbers)

**Example improvement:**
- Backend Engineer, Data job: Captures complete job posting including:
  - [OK] Hybrid work at Stripe
  - [OK] Pay and benefits
  - [OK] In-office expectations
  - [OK] Working remotely policies
  - [OK] Responsibilities

**Title Filtering & Cost Optimization:**
- **Purpose:** Filter jobs by title BEFORE expensive description fetching and LLM classification
- **Configuration:** 20 regex patterns in `config/greenhouse_title_patterns.yaml`
- **Target roles:** Data Analyst, Data Engineer, Data Scientist, ML Engineer, AI Engineer, Product Manager, etc.
- **Filter rate:** 60-70% of jobs filtered out (Sales, Marketing, HR, Legal, etc.)
- **Cost savings:** $0.00388/job × filtered jobs (e.g., 70 jobs filtered = $0.27 saved)
- **Validation:** Tested on Stripe (97.1% filter rate), Monzo (87.9% filter rate)
- **Usage:** Enabled by default, disable with `GreenhouseScraper(filter_titles=False)`
- **Test suite:** 39 automated tests (unit, integration, E2E) - all passing in <1 second
- **See:** `docs/testing/greenhouse_title_filter_implementation.md` for full details
- **See:** `tests/README_TITLE_FILTER_TESTS.md` for test suite usage guide

**Location Filtering & Additional Cost Optimization:**
- **Purpose:** Filter jobs by location AFTER title filter, BEFORE expensive description fetching
- **Configuration:** Target city patterns in `config/greenhouse_location_patterns.yaml`
- **Target locations:** London, New York City, Denver (with variations and aliases)
- **Filter rate:** 89% of title-filtered jobs filtered out (jobs outside target cities)
- **Combined savings:** Title (60-70%) + Location (89% of remaining) = 96% total reduction
- **Validation:** Tested on Figma (127 jobs → 15 after title filter → 1 after location filter = 99.2% filtered)
- **Cost savings example:** Figma test saved $0.49 by avoiding 126 description fetches
- **Usage:** Enabled by default, disable with `GreenhouseScraper(filter_locations=False)`
- **Filter pipeline:** Extract title + location → Title filter → Location filter → Fetch description
- **See:** `tests/test_figma_location_filter.py` for validation

**✅ Phase 2 Integration Complete:**
1. ✅ ATS mapping validated for 109 companies → 62 verified with active jobs in production run (2025-11-28)
2. ✅ Greenhouse scraper integrated into `fetch_jobs.py` main pipeline orchestrator
3. ✅ Deduplication logic implemented in `unified_job_ingester.py` (Adzuna + Greenhouse merge)
4. ✅ Production validation: 3,913 jobs scraped, 94.7% filter rate, 184 jobs stored to database

### Implementation Roadmap: Dual Pipeline Integration

> **Status:** Phases 1-4 ✅ COMPLETE - See "Project Roadmap (Weeks 1-5)" section below for current progress

**Phase 1: ATS Validation** ✅ (COMPLETE)
- Test 91 companies in config to confirm which still use Greenhouse
- Some companies may have migrated (e.g., Brex) - update mapping
- Output: Updated `config/company_ats_mapping.json` with company slugs

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

**Phase 4: Run Greenhouse Scraper at Scale** ✅ (COMPLETE 2025-11-28, Ongoing)
- ✅ Initial production run: 109 companies processed, 62 with active jobs
- ✅ Scraper integrated into main pipeline and running continuously
- ✅ Current dataset: 1,213 Greenhouse jobs successfully stored (as of 2025-12-07)
- ✅ Ready: For analytics queries and compensation benchmarking

### Key Implementation Notes

- **Deduplication:** Same job may appear on both Adzuna (truncated) + Greenhouse (full). Prefer Greenhouse description if duplicate.
- **Source tracking:** Raw table should include `source` field ('adzuna' or 'greenhouse') to enable source-specific analytics later
- **Concurrent scraping:** `greenhouse_scraper.py` already supports multi-company scraping. Production run processed all 109 companies in ~58 minutes
- **Cost optimization:** Combined title + location filtering achieves 94.7% filter rate, dramatically reducing LLM classification costs. Keep Adzuna for volume (1,500/month) + Greenhouse for depth (high-value companies).

### Directory Structure

See **[`REPOSITORY_STRUCTURE.md`](REPOSITORY_STRUCTURE.md)** for the detailed, up-to-date directory organization.

Quick overview:
```
job-analytics/
├── wrapper/                       # User-facing entry points (thin wrappers)
│   ├── fetch_jobs.py
│   ├── run_all_cities.py
│   ├── check_pipeline_status.py
│   └── ... other utilities
│
├── pipeline/                      # Core production code
│   ├── fetch_jobs.py              # (implementation)
│   ├── classifier.py              # (implementation)
│   ├── db_connection.py           # (implementation)
│   ├── unified_job_ingester.py    # (implementation)
│   ├── agency_detection.py        # (implementation)
│   └── utilities/                 # Maintenance scripts
│       ├── check_pipeline_status.py
│       ├── analyze_db_results.py
│       └── ... backfill utilities
│
├── config/                        # Configuration files
├── docs/                          # Documentation (see docs/README.md)
├── scrapers/                      # External data sources
├── tests/                         # Test suite
└── output/                        # Generated outputs (gitignored)
```

**For detailed organization details, responsibilities, and import structure, see [`REPOSITORY_STRUCTURE.md`](REPOSITORY_STRUCTURE.md)**

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
- **Cost tracking:** Captures actual token usage from Anthropic API (`response.usage`)
- Attaches `_cost_data` to each classification result for observability
- Handles API errors and response parsing
- Contains standalone test mode: `python classifier.py`
- Cost optimized: uses cheaper Haiku model, not Opus/Sonnet
- **Current accuracy:** 93% on manual test cases with clear job descriptions, but degrades significantly on truncated text

**db_connection.py** (Data Layer)
- Initializes Supabase PostgreSQL client
- Helper functions: `generate_job_hash()` for deduplication
- Insert functions: `insert_raw_job()` (now accepts title & company parameters), `insert_enriched_job()`
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

**Status:** Operational - 93% accuracy on complete text, **actual measured cost $0.00388/job** with Haiku (validated 2025-11-25)
- **Token usage (Greenhouse full-text jobs):** ~4,156 input tokens/job, ~233 output tokens/job
- **Cost tracking:** Implemented in classifier.py using actual Anthropic API token counts
- **Monthly estimate:** 1,500 jobs/month × $0.00388 = ~$5.82/month (well under budget)

**Known Issue:** Agency spam filtering catches 10-15% pre-LLM (hard) + 5-10% post-LLM (soft), but ~21.6% still leaks through - ongoing refinement needed

---

### Epic 3: Database & Data Layer ✅ COMPLETE
**Goal:** Persist raw and enriched job data in queryable form

**Components:**
- `db_connection.py` - Supabase PostgreSQL client with connection pooling
- Schema: `raw_jobs` (original postings with source tracking + title/company metadata) + `enriched_jobs` (classified results with source tracking)
- Helper functions: deduplication hashing, batch inserts, error handling

**Status:** Stable - schema tested with 1,000+ jobs, queries performant

**Recent Enhancement (2025-12-02):** Added `title` and `company` columns to raw_jobs table to preserve original source metadata before classification. Enables direct analysis of raw_jobs without joins and provides fallback data when classification fails. See `docs/database/SCHEMA_UPDATES.md` for details.

---

### Epic 4: Pipeline Validation & Economics ✅ COMPLETE
**Goal:** Validate that the dual pipeline is viable before investing in analytics layer

**Status:** COMPLETE (validated 2025-11-25)

**Validation Results:**
- ✅ Dual-source integration working (Adzuna + Greenhouse)
- ✅ Deduplication logic operational (0 duplicates in test batches)
- ✅ Classification: 93% accuracy on Greenhouse full text
- ✅ Storage: 100% success rate with proper source tracking
- ✅ Agency filtering: Working (blocks 10-15% pre-LLM, flags 5-10% post-LLM)
- ✅ Unit economics: **$0.00388/job actual measured cost** (well under $0.005 target)
- ✅ Token usage tracking: Implemented in classifier.py using Anthropic API metrics
- ✅ Pipeline reliability: <5% failure rate achieved

**Actual Cost Metrics (Measured 2025-11-25):**
- **Input tokens:** ~4,156 tokens/job (Greenhouse full-text, 11K+ chars)
- **Output tokens:** ~233 tokens/job
- **Cost per classification:** $0.00388/job
- **Cost per unique merged job:** $0.00340/job (accounting for deduplication)
- **Monthly estimate:** 1,500 jobs/month = ~$5.10/month
- **Budget headroom:** $15-20/month supports 4,400-5,900 jobs/month

**Key Achievement:** Cost tracking now embedded in production pipeline via `classifier.py`, not just validation

**Production Data Collection (Cumulative as of 2025-12-07):**
- ✅ **Adzuna Pipeline:** Ongoing continuous collection from all 3 cities (London, NYC, Denver)
  - **Current total:** 4,963 raw jobs → 4,676 enriched jobs
  - **All 11 role types covered:** Data Scientist, Data Engineer, ML Engineer, Analytics Engineer, Data Analyst, AI Engineer, Data Architect, Product Manager, Technical PM, Growth PM, AI PM
  - **Storage:** All jobs successfully stored in Supabase (raw_jobs + enriched_jobs tables)
- ✅ **Greenhouse Pipeline:** Ongoing scraping from configured companies
  - **Current total:** 1,213 Greenhouse raw jobs → 953 enriched jobs
  - **Storage:** All jobs successfully stored with proper source tracking
  - **Combined dataset:** 4,676 Adzuna + 953 Greenhouse = 5,629 total enriched jobs ready for analytics

**Validation Artifacts:**
- `validation_actual_costs.json` - 7-job test with real API costs
- `validation_e2e_success.json` - E2E pipeline test results
- `validation_e2e_final.json` - Final E2E validation

**Decision:** Pipeline validated as economically viable. Sufficient dataset collected. Ready to proceed to Epic 5 (Analytics Query Layer).

---

### Epic 5: Analytics Query Layer ✅ COMPLETE
**Goal:** Programmatically answer marketplace questions from enriched job data

**Status:** COMPLETE (2025-12-16)

**Implementation Approach:**
- **Architecture:** Next.js API routes (TypeScript) instead of Python `analytics.py`
- **Location:** `portfolio-site/app/api/hiring-market/` directory
- **Query Layer:** Supabase JS client with server-side filtering
- **Deployed:** Live at `richjacobs.me/projects/hiring-market`

**Completed Components:**
- ✅ `/api/hiring-market/role-demand` - Role demand by city/subfamily
- ✅ `/api/hiring-market/top-skills` - 3-level skill hierarchy (domain → family → skill)
- ✅ `/api/hiring-market/working-arrangement` - Remote/Hybrid/Onsite split
- ✅ `/api/hiring-market/top-companies` - Employer hiring activity
- ✅ `/api/hiring-market/experience-distribution` - Seniority level distribution
- ✅ `/api/hiring-market/count` - Job count with filters
- ✅ `/api/hiring-market/last-updated` - Pipeline freshness indicator

**Query Patterns Implemented:**
- Time series filtering (7/30/90 days, all time)
- Geographic segmentation (London/NYC/Denver)
- Skill demand tracking with hierarchical grouping
- Work arrangement distribution by role
- Employer activity ranking

**Success Criteria Met:**
- ✅ 5 marketplace questions answered programmatically
- ✅ Query latency <5s with caching optimizations
- ✅ Server-side filtering reduces bandwidth
- ✅ Type-safe contracts between API and frontend
- ✅ Unit tests completed
- ✅ E2E tests completed

**See:** `docs/epic5_analytics_layer_planning.md` for detailed implementation phases

**Depends On:** Epic 4 ✅ COMPLETE
**Unblocks:** Epic 6 ✅ COMPLETE

---

### Epic 6: Dashboard & Visualization ✅ COMPLETE
**Goal:** Non-technical users can explore insights without SQL

**Status:** COMPLETE (2025-12-16)

**Implementation Approach:**
- **Architecture:** Next.js dashboard (React 19) instead of Streamlit
- **Location:** `portfolio-site/app/projects/hiring-market/` directory
- **Charts:** Chart.js + sunburst-chart for interactive visualizations
- **Design:** Matches richjacobs.me design system (Geist fonts, lime/emerald accents)
- **Deployed:** Live at `richjacobs.me/projects/hiring-market`

**Completed Components:**
- ✅ Global filter system (date range, city, job family)
- ✅ Custom dropdowns with smooth animations
- ✅ Real-time job count display
- ✅ Five interactive visualizations:
  1. **Role Demand Chart** - Bar chart with gradient coloring by volume
  2. **Skills Demand Chart** - 3-level sunburst (domain → family → skill)
  3. **Working Arrangement Chart** - Stacked bar chart (Remote/Hybrid/Onsite)
  4. **Top Companies Chart** - Ranked bar chart by hiring activity
  5. **Experience Distribution Chart** - Seniority level distribution

**Features Implemented:**
- ✅ Interactive filters with URL-ready architecture
- ✅ Chart.js visualizations with custom styling
- ✅ Smooth loading states with skeleton loaders
- ✅ Frontend caching for instant role switching
- ✅ Last updated timestamp with relative time
- ✅ Data source indicators for quality transparency
- ✅ Share functionality with Web Share API + clipboard fallback
- ✅ Responsive design (desktop-focused for portfolio demos)
- ✅ Error handling and empty states

**Success Criteria Met:**
- ✅ 5 marketplace questions answered with visualizations
- ✅ Consistent with richjacobs.me design system
- ✅ Loads in <3s with caching
- ✅ Professional polish suitable for portfolio
- ✅ Added to main site's projects page
- ✅ GitHub repo documentation available
- ✅ Browser tested (Chrome, Firefox, Safari)
- ✅ Unit tests completed
- ✅ E2E tests completed

**See:** `docs/epic5_analytics_layer_planning.md` for detailed implementation phases

**Depends On:** Epic 5 ✅ COMPLETE (implemented together)
**Unblocks:** Epic 7 (automation to keep dashboard fresh)

---

### Epic 7: Automation & Operational Excellence ⏳ PLANNED
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

**Depends On:** Epic 4 ✅ COMPLETE + Epic 6 (dashboard exists)

---

## Epic 4 Completion Summary

**Status:** ✅ COMPLETE (2025-11-26)

Epic 4 validated the dual-source pipeline is economically viable and technically sound, then executed production data collection.

**Validation Approach (2025-11-25):**
- Small-scale testing (7-10 jobs) proved pipeline mechanics
- Actual cost tracking implemented in production code (`classifier.py`)
- Measured real token usage from Anthropic API instead of estimates

**Economic Viability:**
- **Target:** ≤$0.005/job → **Actual:** $0.00388/job ✅ (23% under target)
- **Monthly budget:** $15-20 → **Actual usage:** ~$5.10 for 1,500 jobs ✅ (66-74% under budget)
- **Headroom:** Can process 4,400-5,900 jobs/month sustainably

**Technical Validation:**
- Dual-source integration working (Adzuna + Greenhouse)
- Deduplication preventing duplicate classifications
- Classification accuracy 93% on full-text jobs
- Storage 100% success rate
- Agency filtering blocking 10-15% of jobs pre-LLM

**Production Data Collection:**
- ✅ **Adzuna (2025-11-26):** 1,279 raw jobs → 1,044 enriched jobs (all 3 cities, 11 role types)
- ✅ **Greenhouse (2025-11-28):** 109 companies, 3,913 scraped, 207 kept (94.7% filter), 184 stored
- ✅ **Combined dataset:** 1,228 total enriched jobs (1,044 + 184)

**Key Innovation:**
Cost tracking now embedded in production pipeline, not just validation scripts. Every classification returns actual token counts and costs for ongoing observability.

**Decision:** Pipeline validated. Dataset collected. Ready to proceed to Epic 5 (Analytics Query Layer).

## Current State & Known Limitations

### ✅ Working Well
- **Dual-source pipeline operational:** Adzuna API + Greenhouse scraper both functioning
- Unified job ingestion with deduplication (MD5 hashing) reliable and tested
- Agency hard filtering prevents 10-15% of wasted API calls
- Classification achieves 93% accuracy on complete job descriptions (test cases)
- Database schema stable and queries performant
- Greenhouse scraper captures full job text (9,000-15,000+ chars)
- Greenhouse production run complete: 109 companies processed, 62 with active jobs, 184 jobs stored (2025-11-28)

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
**Epic 7: Automation & Operational Excellence** (ready to start)
- **Status:** Epics 1-6 ✅ COMPLETE - Full pipeline operational, dashboard live at richjacobs.me/projects/hiring-market
- **Dataset:** 5,629 enriched jobs (4,676 Adzuna + 953 Greenhouse) across all 3 cities and 11 role types (as of 2025-12-07)
- **Dataset growth:** Manual pipeline runs; needs automation for consistent freshness
- **Action:** Set up GitHub Actions for daily automated pipeline execution
- **Goal:** Keep dashboard data fresh without manual intervention, achieve ≥95% successful run rate
- **See:** Epic 7 section in "Planned Epics" for full details

## Post-Project Epics

Future enhancements planned after core platform (Epics 1-7) completion:

### Epic: Data Standardization & Canonicalization System ⏸️ PLANNED
**Goal:** Normalize and standardize LLM-extracted fields that are inconsistent, non-deterministic, or in free-form formats

**Problems Addressed:**

**Phase 1: Employer Size Canonicalization**
- Same employer receives different size classifications (170+ employers with 2-3 variants)
- Name variations ("Coinbase" vs "coinbase") treated as separate entities
- Repeated classifications waste LLM costs

**Phase 2: Experience Range Normalization**
- 90% null rate (5,090/5,629 jobs have no value)
- 90+ inconsistent formats in the 10% that exists
- Free-form string extraction made data unusable despite "flexibility" intent

**Solutions:**
- **Employer Size**: Canonical mapping tables with name normalization + LLM fallback
- **Experience Range**: Two-tier normalization (canonical forms + seniority alignment) + pattern-based backfill

**Expected Benefits (Combined Phases):**
- **Phase 1:** 100% consistency, 80-90% reduction in employer size LLM calls, 10-15% cost savings
- **Phase 2:** 90% null → 100% coverage, 90+ formats → 5 canonical forms, enables experience analytics

**Status:** Detailed implementation plan ready (10 sessions across 2 phases)
**See:** [`docs/employer_size_canonicalization_epic.md`](docs/employer_size_canonicalization_epic.md) for complete architecture, schema, implementation phases, and code examples

**Priority:** Medium (quality improvement, cost optimization, unblocks analytics)
**Complexity:** Moderate-High (10 implementation sessions estimated, 2 phases)

---

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
   - Production run (2025-11-28): 109 companies processed, 3,913 jobs scraped, 184 stored
   - Validated 94.7% filter rate from combined title + location filtering
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

- **Title + Location filtering before LLM:** Production validated 94.7% filter rate (2025-11-28)
  - Title filter: Removes 60-70% of jobs (non-Data/Product roles)
  - Location filter: Removes 89% of remaining jobs (outside London/NYC/Denver)
  - Production run: 3,913 jobs scraped → 207 kept (94.7% filtered)
  - Individual examples: Figma 99.2% filtered, Stripe 97.8% filtered
  - Avoids expensive description fetching AND classification costs
- **Hard filtering before LLM:** Only valid jobs reach Claude, avoiding wasted API calls on known recruiters
- **Cheap model selection:** Claude 3.5 Haiku used instead of Opus/Sonnet - much lower cost per classification
- **Batch deduplication:** MD5 hash prevents re-classifying duplicate jobs
- **Actual measured cost per classified job:** $0.00388/job for classifications (Haiku pricing) - **MEASURED 2025-11-25**
  - Based on actual Anthropic API token usage from Greenhouse full-text jobs (11K+ chars)
  - Input: ~4,156 tokens/job @ $0.80 per 1M tokens
  - Output: ~233 tokens/job @ $2.40 per 1M tokens
  - Cost tracking implemented in `classifier.py` using `response.usage` from Anthropic API
- **Cost per unique merged job:** $0.00340/job (accounting for deduplication)
- **Example cost with filtering:** 127 jobs scraped → 1 classified → $0.00340 total (vs $0.43 without filtering)
- **Monthly estimate:** With 94.7% filtering, production run classified 207 jobs from 3,913 scraped in single run
- **Budget headroom:** $15-20/month supports 4,400-5,900 classified jobs/month (83,000-111,000 jobs scraped with 94.7% filtering)

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

**Supabase Queries & Data Fetching:**
- **CRITICAL:** Supabase has a 1,000 row default limit - all queries MUST implement pagination
- **Pagination template:** Use `offset()` and `limit()` in a loop until no rows returned
  ```python
  all_data = []
  offset = 0
  page_size = 1000
  while True:
      batch = supabase.table('table_name').select('columns').offset(offset).limit(page_size).execute()
      if not batch.data:
          break
      all_data.extend(batch.data)
      offset += page_size
  ```
- Without pagination, queries hitting the 1K limit will silently truncate results
- Always verify result completeness by checking if last batch returned fewer than `page_size` rows
- When writing analysis/reporting scripts, handle pagination to get accurate full dataset counts

**High API costs:**
- Check if hard filtering is working (should block 10-15% of jobs)
- Verify deduplication is preventing re-classification
- Consider if taxonomy is too complex (longer prompts = higher cost)

**Low classification accuracy:**
- **Most common cause:** Text truncation from Adzuna (mitigated by Greenhouse scraper - use `--sources adzuna,greenhouse`)
- Validate taxonomy against actual job descriptions
- Check if job is from unusual industry/company type
- Review edge cases and update taxonomy rules
