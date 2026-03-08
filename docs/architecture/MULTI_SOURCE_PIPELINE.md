# Multi-Source Pipeline Architecture: Greenhouse + Lever + Ashby + Workable + SmartRecruiters

## Overview

Five-source job ingestion strategy providing premium company depth via browser automation (Greenhouse) and public APIs (Lever, Ashby, Workable, SmartRecruiters) before unified classification and analysis.

---

## The Pipeline

```
PIPELINE A: Greenhouse  PIPELINE B: Lever  PIPELINE C: Ashby  PIPELINE D: Workable  PIPELINE E: SmartRecruiters
(REST API)             (Public API)       (Public API)       (Public API)          (Public API)

Greenhouse Job Board API  Lever API          Ashby API          Workable API          SmartRecruiters API
    |                       |                  |                  |                      |
greenhouse_api_fetcher.py lever_fetcher.py   ashby_fetcher.py   workable_fetcher.py   smartrecruiters_fetcher.py
|- Single request/company|- JSON API        |- JSON API        |- JSON API            |- JSON API
|- Structured salary     |- EU + Global     |- Structured comp  |- workplace_type      |- locationType
|- Title/location filter     |                  |              |- salary               |- experienceLevel
    |                       |                  |                  |                      |
    +--------+--------------+-----------+------+------------------+----------------------+
             |
             v
     UNIFIED JOB INGESTION LAYER
     |- Combines all 5 sources
     |- Deduplicates by: (company + title + location) MD5
     |- Prefers full descriptions over truncated
     |- Tracks data source for each job
               |
               v
    [Hard Filter - Agency Blocklist]
        |- Checks against config/agency_blacklist.yaml
        |- Skips known recruitment firms
               |
               v
    classifier.py (Gemini 2.5 Flash)
        |- Builds structured prompt from schema_taxonomy.yaml
        |- Extracts: function, level, skills, remote status
        |- Generates 2-3 sentence role summary (INLINE)
        |- Returns JSON classification + summary
               |
               v
    skill_family_mapper.py (Deterministic)
        |- Overwrites LLM family_code with exact lookup
        |- Fallback: normalized matching (plurals, UK/US spelling)
        |- Source: config/skill_family_mapping.yaml (997 skills, 39 families)
        |- Domains: config/skill_domain_mapping.yaml (9 domains)
               |
               v
    [Soft Detection - Agency Pattern Matching]
        |- Validates classifications
        |- Flags suspected recruitment firms
               |
               v
    db_connection.py (Supabase PostgreSQL)
        |- raw_jobs table (original postings + source)
        |- enriched_jobs table (classified + summary)
        |      employer_name is FK to employer_metadata.canonical_name
        |      (lowercase canonical, display via view)
        |- employer_metadata table (source of truth for employers)
        |      canonical_name, display_name, working_arrangement_default
        |- employer_fill_stats table (median days to fill)
               |
               v
    jobs_with_employer_context (VIEW)
        |- JOINs enriched_jobs + employer_metadata + employer_fill_stats
        |- employer_name = display_name (proper casing for UI)
        |- days_open, fill_time_ratio (computed)
               |
               v
    Analytics Layer (Next.js API Routes)
        |- richjacobs.me/projects/hiring-market
        |- Dashboard + Job Feed (queries view, not raw tables)
```

---

## Data Source Comparison

| Aspect | Greenhouse Scraper | Lever API | Ashby API | Workable API | SmartRecruiters API |
|--------|-------------------|-----------|-----------|-------------|---------------------|
| **Coverage** | 452 companies | 182 companies | 169 companies | 135 companies | 35 companies |
| **Description Length** | 9,000-15,000+ chars | 5,000-15,000+ chars | 5,000-15,000+ chars | 5,000-15,000+ chars | 5,000-15,000+ chars |
| **Content Sections** | Full posting | Full posting | Full posting | Full posting | Full posting |
| **Technology** | Browser (Playwright) | Public JSON API | Public JSON API | Public JSON API | Public JSON API |
| **Update Frequency** | On-demand | On-demand | On-demand | On-demand | On-demand |
| **Cost** | Browser (moderate) | API calls (minimal) | API calls (minimal) | API calls (minimal) | API calls (minimal) |
| **Speed** | Slow (~1 job/2 sec) | Fast (~10 jobs/sec) | Fast (~10 jobs/sec) | Fast (~10 jobs/sec) | Fast (~10 jobs/sec) |
| **Quality/Depth** | Narrow but deep | Narrow but deep | Narrow but deep | Narrow but deep | Narrow but deep |
| **Salary Data** | Rarely in text | Rarely in text | Structured (best) | Structured | Rarely |
| **Unique Data** | Full descriptions | EU support | Compensation | workplace_type | locationType, experienceLevel |
| **Best For** | Premium analysis | Premium analysis | Premium + salary | Workplace context | Structured metadata |

---

## Why Five Sources?

### Greenhouse Strengths
- **Quality:** Complete job postings (9,000+ chars)
- **Curation:** 452 premium tech companies configured
- **Depth:** All job sections captured
- **Reliability:** Direct from company source

### Greenhouse Limitations
- **Scale:** Requires browser automation (slower)
- **Cost:** Higher per job (browser resources)
- **Maintenance:** DOM changes can break scraper

### Lever Strengths
- **Quality:** Complete job postings (5,000-15,000+ chars)
- **Speed:** Public JSON API, no browser needed
- **Simplicity:** No authentication required
- **Reliability:** Official API, well-documented
- **EU Support:** Separate EU instance for GDPR-compliant companies

### Lever Limitations
- **Scale:** Only companies using Lever ATS
- **Discovery:** Need to identify Lever-using companies

### Ashby Strengths
- **Quality:** Complete job postings (5,000-15,000+ chars)
- **Structured Compensation:** Best salary data of any source (min/max/currency/interval)
- **Speed:** Public JSON API, no browser needed
- **Reliability:** Well-documented API
- **Remote Data:** Structured `isRemote` field

### Ashby Limitations
- **Scale:** Smaller market share than Greenhouse/Lever
- **Discovery:** Need to identify Ashby-using companies

### Workable Strengths
- **Quality:** Complete job postings (5,000-15,000+ chars)
- **Workplace Type:** Structured `workplace_type` field (remote/hybrid/onsite)
- **Salary Data:** Structured salary ranges in many postings
- **Speed:** Public JSON API, no browser needed

### Workable Limitations
- **Scale:** Medium market share among ATS platforms
- **Discovery:** Need to identify Workable-using companies

### SmartRecruiters Strengths
- **Quality:** Complete job postings with structured metadata
- **Location Type:** Structured `locationType` field
- **Experience Level:** Structured `experienceLevel` field
- **Speed:** Public JSON API, no browser needed

### SmartRecruiters Limitations
- **Scale:** Smaller company universe (35 companies currently)
- **Discovery:** Need to identify SmartRecruiters-using companies

### Combined Strategy

```
Greenhouse + Lever + Ashby + Workable + SmartRecruiters = Complete Coverage

Quality (GH)     Quality (Lever)    Quality (Ashby)    Quality (Workable)   Quality (SR)
452 companies +  182 companies  +  169 companies  +  135 companies     +  35 companies
9K-15K chars     5K-15K chars       Full + salary      Full + workplace     Full + metadata
Browser auto     JSON API           JSON API           JSON API             JSON API
On-demand        On-demand          On-demand          On-demand            On-demand

Result: Deep analysis of ~970+ premium companies (5 ATS sources)
      + Best salary data (Ashby + Workable)
      + Best workplace metadata (Workable + SmartRecruiters)
```

---

## Implementation Status

### Pipeline A: Greenhouse - COMPLETE
- **File:** `scrapers/greenhouse/greenhouse_api_fetcher.py`
- **API:** `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`
- **Config:** `config/greenhouse/company_ats_mapping.json` (452 companies)
- **Filtering:** `config/greenhouse/title_patterns.yaml`, `config/greenhouse/location_patterns.yaml` (shared via `scrapers/common/filters.py`)
- **Reliability:** High (REST API, no browser dependency)
- **Performance:** ~1-2s per company (single HTTP request)
- **Status:** Production-ready, 94.7% filter rate achieved

#### Greenhouse API Features
- Single HTTP request per company (vs Playwright browser automation)
- Structured salary data via `pay_input_ranges` (min/max cents with currency)
- Department and office data in dedicated fields
- `updated_at` timestamp for change detection
- No Playwright browser dependency required
- Optionally add `url_type` for faster resolution

### Pipeline B: Lever - COMPLETE
- **File:** `scrapers/lever/lever_fetcher.py`
- **Validation:** `pipeline/utilities/validate_ats_slugs.py lever`
- **Config:** `config/lever/company_mapping.json` (182 companies)
- **Filtering:** `config/lever/title_patterns.yaml`, `config/lever/location_patterns.yaml`
- **Status:** Production-ready

### Pipeline C: Ashby - COMPLETE
- **File:** `scrapers/ashby/ashby_fetcher.py`
- **Config:** `config/ashby/company_mapping.json` (169 companies)
- **Filtering:** `config/ashby/title_patterns.yaml`, `config/ashby/location_patterns.yaml`
- **Status:** Production-ready, best structured salary data

### Pipeline D: Workable - COMPLETE
- **File:** `scrapers/workable/workable_fetcher.py`
- **Config:** `config/workable/company_mapping.json` (135 companies)
- **Filtering:** `config/workable/title_patterns.yaml`, `config/workable/location_patterns.yaml`
- **Status:** Production-ready, workplace_type and salary data
- **See:** `docs/architecture/Done/EPIC_WORKABLE_INTEGRATION.md`

### Pipeline E: SmartRecruiters - COMPLETE
- **File:** `scrapers/smartrecruiters/smartrecruiters_fetcher.py`
- **Config:** `config/smartrecruiters/company_mapping.json` (35 companies)
- **Filtering:** `config/smartrecruiters/title_patterns.yaml`, `config/smartrecruiters/location_patterns.yaml`
- **Status:** Production-ready, locationType and experienceLevel data
- **See:** `docs/architecture/In Progress/EPIC_SMARTRECRUITERS_INTEGRATION.md`

### Unified Ingester - COMPLETE
- **File:** `pipeline/unified_job_ingester.py`
- **Merges:** All five sources with MD5 deduplication
- **Status:** Production-ready

### Orchestrator - COMPLETE
- **File:** `pipeline/fetch_jobs.py`
- **Supports:** `--sources greenhouse,lever,ashby,workable,smartrecruiters`
- **Status:** Production-ready

---

## Lever Technical Details

### API Endpoints

```python
LEVER_API_URLS = {
    "global": "https://api.lever.co/v0/postings",
    "eu": "https://api.eu.lever.co/v0/postings"
}
```

### Usage

```bash
# Fetch from all configured Lever companies
python -c "from scrapers.lever import fetch_all_lever_companies; jobs = fetch_all_lever_companies(); print(f'Fetched {len(jobs)} jobs')"

# Fetch from single company
python -c "from scrapers.lever import fetch_lever_jobs; jobs = fetch_lever_jobs('spotify'); print(f'{len(jobs)} jobs')"
```

### API Response Structure

```json
{
  "id": "abc123",
  "text": "Senior Data Engineer",
  "hostedUrl": "https://jobs.lever.co/company/abc123",
  "applyUrl": "https://jobs.lever.co/company/abc123/apply",
  "categories": {
    "team": "Data Engineering",
    "department": "Engineering",
    "location": "San Francisco, CA",
    "commitment": "Full-time"
  },
  "descriptionPlain": "Full job description...",
  "lists": [
    {"text": "Requirements", "content": "<li>5+ years...</li>"},
    {"text": "Responsibilities", "content": "<li>Build...</li>"}
  ]
}
```

### Full Description Assembly

```python
def build_full_description(job_data: Dict) -> str:
    """
    Concatenates all Lever fields into complete description:
    - descriptionPlain (main description)
    - lists[].content (requirements, responsibilities, etc.)
    - additional field (extra info)

    Result: 5,000-15,000+ chars (full job posting)
    """
```

---

## Configuration Files

### Per-ATS Configuration (each has 3 files)
| ATS | Company Config | Companies | Title Patterns | Location Patterns |
|-----|---------------|-----------|----------------|-------------------|
| Greenhouse | `config/greenhouse/company_ats_mapping.json` | 452 | `title_patterns.yaml` | `location_patterns.yaml` |
| Lever | `config/lever/company_mapping.json` | 182 | `title_patterns.yaml` | `location_patterns.yaml` |
| Ashby | `config/ashby/company_mapping.json` | 169 | `title_patterns.yaml` | `location_patterns.yaml` |
| Workable | `config/workable/company_mapping.json` | 135 | `title_patterns.yaml` | `location_patterns.yaml` |
| SmartRecruiters | `config/smartrecruiters/company_mapping.json` | 35 | `title_patterns.yaml` | `location_patterns.yaml` |

### Shared
| File | Purpose |
|------|---------|
| `config/agency_blacklist.yaml` | Agency names for hard filtering |
| `config/supported_ats.yaml` | Supported ATS platforms |
| `config/skill_family_mapping.yaml` | Skill name to family mapping (997 skills, 40 families) |
| `config/skill_domain_mapping.yaml` | Skill family to domain mapping (40 families, 9 domains) |

---

## Quality Metrics

| Metric | All ATS Sources |
|--------|-----------------|
| Avg chars per job | 7,000+ |
| Skills extraction F1 | 0.85+ |
| Remote status F1 | 0.85+ |
| Coverage | ~970+ companies |

### Classification Confidence

- **Full descriptions (Greenhouse/Lever/Ashby/Workable/SmartRecruiters):** F1 >=0.85 (high confidence)

---

## Usage Examples

```bash
# All five sources
python wrappers/fetch_jobs.py --sources greenhouse,lever,ashby,workable,smartrecruiters

# Specific source only
python wrappers/fetch_jobs.py --sources workable

# With resume capability (skip recently processed)
python wrappers/fetch_jobs.py --sources greenhouse,lever --resume-hours 24

# Specific companies
python wrappers/fetch_jobs.py --sources greenhouse --companies stripe,figma

```

---

## Key Design Decisions

### Why Separate Pipelines Until Merge?
- **Isolation:** Each source can fail independently
- **Optimization:** Can tune each source separately
- **Flexibility:** Can enable/disable sources via `--sources` flag
- **Monitoring:** Track source-specific metrics
- **Cost control:** Can cap expensive sources while keeping cheap ones unlimited

### Why Deduplicate by (company + title + location)?
- **Uniqueness:** These three fields identify a unique job posting
- **Robustness:** Handles URL changes, posting ID changes
- **Simple:** Fast MD5 hash computation
- **Reversible:** Can track which jobs came from which source

### Why Prefer Full Descriptions?
- **Quality:** Greenhouse/Lever descriptions are 50-100x longer
- **Completeness:** Include all sections (benefits, arrangements, etc.)
- **Reliability:** Direct from company, not curated by job board

### Lever vs Greenhouse Trade-offs

| Consideration | Greenhouse | Lever |
|--------------|------------|-------|
| Setup complexity | High (Playwright) | Low (HTTP requests) |
| Maintenance | Medium (DOM changes) | Low (stable API) |
| Speed | ~1 job/2 sec | ~10 jobs/sec |
| Reliability | Medium (browser crashes) | High (official API) |
| Description quality | Excellent | Excellent |

---

## Classification Input by Source

### What the Classifier Receives

All sources call `classify_job(job_text, structured_input)` which routes to Gemini 2.5 Flash ($0.000629/job for Greenhouse) or Gemini 3.0 Flash ($0.002435/job for other sources). Data quality varies by source:

#### Greenhouse Jobs

```python
structured_input = {
    'title': "Backend Engineer, Data",
    'company': "Stripe",
    'description': "[9,000-15,000 character COMPLETE job posting]",  # Full text
    'location': None,
    'category': None,
    'salary_min': None,
    'salary_max': None
}
```

**Prompt sent to Claude (excerpt):**
```
# JOB TO CLASSIFY

**Job Title:** Backend Engineer, Data
**Company:** Stripe

**Job Description:**
## Who we are
Stripe is a financial infrastructure platform for businesses...

## What you'll do
- Design and build scalable data infrastructure to support Stripe's rapid growth
- Build and maintain data pipelines processing billions of events daily
- Collaborate with data scientists, analysts, and product teams
- Work with technologies including Python, SQL, Spark, Airflow, dbt, Snowflake

## Who you are
Minimum requirements:
- 5+ years of software engineering experience
- Strong programming skills in Python or similar languages
- Experience building and maintaining data pipelines at scale
- Deep knowledge of SQL and data modeling
- Familiarity with distributed systems (Spark, Kafka, or similar)

## Work arrangement
This role is hybrid, with 2 days per week in our San Francisco office.

[...continues for 12,000+ characters total...]
```

**Classification Results:**
- ✅ Job family/subfamily (Data Engineer)
- ✅ Seniority (Senior, from "5+ years")
- ✅ Skills (Python, SQL, Spark, Airflow, dbt, Snowflake, etc.)
- ✅ Working arrangement (Hybrid - 2 days in office) → **5.8% unknown rate**
- ✅ Experience range (5+ years explicitly stated)
- ✅ Company size estimate (large enterprise from context)
- ✅ Track (IC - no management mentioned)

---

#### Lever Jobs

```python
structured_input = {
    'title': "Data Scientist - Fraud",
    'company': "Plaid",
    'description': "[Complete job posting from Lever API]",  # Full text
    'location': "San Francisco",
    'category': None,
    'salary_min': None,
    'salary_max': None
}
```

**Prompt sent to Claude (excerpt):**
```
# JOB TO CLASSIFY

**Job Title:** Data Scientist - Fraud
**Company:** Plaid
**Location:** San Francisco

**Job Description:**
We're looking for a Data Scientist to join our Fraud Detection team at Plaid.

## Responsibilities
- Build and deploy machine learning models to detect fraudulent transactions
- Analyze transaction patterns to identify emerging fraud trends
- Collaborate with engineering teams to integrate models into production

## Requirements
- PhD or MS in Computer Science, Statistics, Mathematics, or related field
- 3+ years of experience in data science or machine learning
- Strong programming skills in Python
- Proficiency with scikit-learn, TensorFlow, or PyTorch

## Location & Work Arrangement
This role can be based in San Francisco, New York, or Raleigh-Durham. We offer
a hybrid work model with 3 days per week in the office.

[...full job posting...]
```

**Classification Results:**
- ✅ Job family/subfamily (Data Scientist)
- ✅ Seniority (Senior/Mid from "3+ years, PhD/MS")
- ✅ Skills (Python, SQL, scikit-learn, TensorFlow, PyTorch)
- ✅ Working arrangement (Hybrid - 3 days in office) → **0% unknown rate**
- ✅ Experience range (3+ years)
- ✅ Compensation ($150k-$200k if stated)
- ✅ Location (Multi-location: SF/NYC/Raleigh-Durham)

---

### Data Quality Comparison

| Field | Greenhouse | Lever | Ashby | Workable | SmartRecruiters |
|-------|------------|-------|-------|----------|-----------------|
| **Title** | Yes | Yes | Yes | Yes | Yes |
| **Company** | Yes | Yes | Yes | Yes | Yes |
| **Description** | Full (9K-15K chars) | Full | Full | Full | Full |
| **Location Metadata** | No | Yes | Yes | Yes | Yes |
| **Salary Metadata** | No | No | Structured (best) | Structured | No |
| **Working Arr. in Text** | Present | Present | Present | Structured field | No |
| **Skills in Text** | Detailed | Detailed | Detailed | Detailed | Detailed |
| **Experience Level** | No | No | No | No | Structured field |

### Classification Accuracy Impact

| Source | Working Arr. Unknown | Avg Description |
|--------|---------------------|-----------------|
| **Greenhouse** | 5.8% | ~12,000 chars |
| **Lever** | 0% | Full text |

**Key Insight:** All ATS sources provide full job descriptions, enabling high-confidence classification across the board.

---

## Future Expansion

All major ATS platforms are now integrated. Potential future additions:

```python
# Current scrapers (all IMPLEMENTED)
class ATSScraperOrchestrator:
    scrapers = {
        'greenhouse': GreenhouseScraper(),       # IMPLEMENTED (452 companies)
        'lever': LeverFetcher(),                  # IMPLEMENTED (182 companies)
        'ashby': AshbyFetcher(),                  # IMPLEMENTED (169 companies)
        'workable': WorkableFetcher(),            # IMPLEMENTED (135 companies)
        'smartrecruiters': SmartRecruitersFetcher(), # IMPLEMENTED (35 companies)
        'custom': GoogleRSSFetcher()              # For custom career sites (experimental)
    }
```

Potential future sources: BambooHR, iCIMS, Jobvite, or direct company RSS feeds.

---

## Summary

The multi-source architecture provides:

- **Depth (Greenhouse)** - 452 premium companies via browser automation
- **Depth (Lever)** - 182 premium companies via public API
- **Depth (Ashby)** - 169 premium companies via public API + best salary data
- **Depth (Workable)** - 135 companies via public API + workplace_type
- **Depth (SmartRecruiters)** - 35 companies via public API + structured metadata
- **Quality** - Complete 5,000-15,000+ char descriptions (vs 100-200 char truncation)
- **Inline Summaries** - AI-generated role summaries during classification (single Gemini 2.5 Flash call)
- **Flexibility** - Can enable/disable sources independently via `--sources` flag
- **Cost-effective** - Mix of cheap API + moderate automation, Gemini 2.5 Flash at $0.000629/job
- **Complete** - All major ATS platforms integrated (~970+ companies)

**Current Status:** All five pipelines operational, unified ingestion working, dashboard + job feed live at richjacobs.me/projects/hiring-market.

---

**Last Updated:** 2026-02-07
**Changes:** Updated to 5-source architecture. Removed Adzuna. Active ATS sources: Greenhouse 452, Lever 182, Ashby 169, Workable 135, SmartRecruiters 35.
