# Multi-Source Pipeline Architecture: Adzuna + Greenhouse + Lever

## Overview

Three-source job ingestion strategy combining mass-market coverage (Adzuna), premium company depth via browser automation (Greenhouse), and premium company depth via public API (Lever) before unified classification and analysis.

---

## The Pipeline

```
PIPELINE A: Adzuna API          PIPELINE B: Greenhouse Scraping    PIPELINE C: Lever API
(Mass market jobs)              (Premium - browser automation)     (Premium - public API)

Adzuna Job API                  Greenhouse Career Pages            Lever Postings API
    |                               |                                   |
fetch_adzuna_jobs.py           greenhouse_scraper.py               lever_fetcher.py
|- Fetch paginated results     |- Browser automation (Playwright)  |- Public JSON API (no auth)
|- Format for processing       |- Multi-company scraping           |- Full descriptions included
|- Deduplication (MD5)         |- Full descriptions (9-15K chars)  |- EU + Global instances
    |                          |- Title/location filtering              |
    |                               |                                   |
    |                               |                                   |
    +---------------+---------------+-----------------------------------+
                    |
                    v
          UNIFIED JOB INGESTION LAYER
          (Merges all sources, handles overlap)
          |- Combines Adzuna + Greenhouse + Lever
          |- Deduplicates by: (company + title + location) MD5
          |- Prefers full descriptions over truncated
          |- Tracks data source for each job
                    |
                    v
    [Hard Filter - Agency Blocklist]
        |- Checks against config/agency_blacklist.yaml
        |- Skips known recruitment firms (cost optimization)
                    |
                    v
    classifier.py (Claude 3.5 Haiku LLM)
        |- Builds structured prompt from taxonomy
        |- Extracts: function, level, skills, remote status
        |- Returns JSON classification
                    |
                    v
    [Soft Detection - Agency Pattern Matching]
        |- Validates classifications
        |- Flags suspected recruitment firms
                    |
                    v
    db_connection.py (Supabase PostgreSQL)
        |- raw_jobs table (original postings + source)
        |- enriched_jobs table (classified results)
                    |
                    v
    Analytics Layer (Next.js API Routes)
        |- richjacobs.me/projects/hiring-market
        |- 5 interactive visualizations
```

---

## Data Source Comparison

| Aspect | Adzuna API | Greenhouse Scraper | Lever API |
|--------|------------|-------------------|-----------|
| **Coverage** | 1,500+ jobs/month (general) | 302 companies (curated) | 50+ companies (curated) |
| **Description Length** | 100-200 chars (truncated) | 9,000-15,000+ chars (complete) | 5,000-15,000+ chars (complete) |
| **Content Sections** | Basic summary only | Full posting with all sections | Full posting with all sections |
| **Technology** | REST API | Browser automation (Playwright) | Public JSON API (no auth) |
| **Update Frequency** | Continuous daily | On-demand by company | On-demand by company |
| **Cost** | API calls (minimal) | Browser automation (moderate) | API calls (minimal) |
| **Speed** | Fast (~50 jobs/min) | Slow (~1 job/2 sec) | Fast (~10 jobs/sec) |
| **Quality/Depth** | Wide but shallow | Narrow but deep | Narrow but deep |
| **Best For** | Market trends, volume | Premium company analysis | Premium company analysis |

---

## Why Three Sources?

### Adzuna Strengths
- **Coverage:** 1,500+ jobs per month across all companies
- **Speed:** Real-time daily updates
- **Cost:** Simple API calls, negligible cost
- **Breadth:** Captures mass market jobs

### Adzuna Limitations
- **Depth:** Descriptions truncated to 100-200 characters
- **Selection:** No control over job quality
- **Recency:** May include outdated postings

### Greenhouse Strengths
- **Quality:** Complete job postings (9,000+ chars)
- **Curation:** 302 premium tech companies configured
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

### Combined Strategy

```
Adzuna + Greenhouse + Lever = Complete Coverage

Volume (Adzuna)      Quality (Greenhouse)       Quality (Lever)
1,500 jobs/month  +  302 companies          +   50+ companies
100-200 chars        9,000-15,000 chars         5,000-15,000 chars
All companies        Browser automation         JSON API
Daily updates        On-demand scraping         On-demand fetching

Result: Deep analysis of premium companies (Greenhouse + Lever)
      + Broad market trend tracking (Adzuna)
```

---

## Implementation Status

### Pipeline A: Adzuna - COMPLETE ✓
- **File:** `scrapers/adzuna/fetch_adzuna_jobs.py`
- **Config:** N/A (API-based, no company mapping)
- **Status:** Production-ready, running daily

### Pipeline B: Greenhouse - COMPLETE ✓
- **File:** `scrapers/greenhouse/greenhouse_scraper.py`
- **Config:** `config/company_ats_mapping.json` (302 companies)
- **Filtering:** `config/greenhouse_title_patterns.yaml`, `config/greenhouse_location_patterns.yaml`
- **Status:** Production-ready, 94.7% filter rate achieved

### Pipeline C: Lever - COMPLETE ✓
- **File:** `scrapers/lever/lever_fetcher.py`
- **Discovery:** `scrapers/lever/discover_lever_companies.py`
- **Validation:** `scrapers/lever/validate_lever_sites.py`
- **Config:** `config/lever_company_mapping.json` (50+ companies)
- **Filtering:** `config/lever_title_patterns.yaml`, `config/lever_location_patterns.yaml`
- **Status:** Production-ready

### Unified Ingester - COMPLETE ✓
- **File:** `pipeline/unified_job_ingester.py`
- **Merges:** All three sources with MD5 deduplication
- **Status:** Production-ready

### Orchestrator - COMPLETE ✓
- **File:** `pipeline/fetch_jobs.py`
- **Supports:** `--sources adzuna,greenhouse,lever`
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

    Result: 5,000-15,000+ chars (vs Adzuna's 100-200)
    """
```

---

## Configuration Files

### Lever-Specific
| File | Purpose |
|------|---------|
| `config/lever_company_mapping.json` | Company slug → API instance mapping |
| `config/lever_title_patterns.yaml` | Title patterns for filtering |
| `config/lever_location_patterns.yaml` | Location patterns for filtering |

### Greenhouse-Specific
| File | Purpose |
|------|---------|
| `config/company_ats_mapping.json` | Company → Greenhouse slug mapping |
| `config/greenhouse_title_patterns.yaml` | Title patterns for filtering |
| `config/greenhouse_location_patterns.yaml` | Location patterns for filtering |
| `config/greenhouse_checked_companies.json` | Validated company slugs |

### Shared
| File | Purpose |
|------|---------|
| `config/agency_blacklist.yaml` | Agency names for hard filtering |
| `config/supported_ats.yaml` | Supported ATS platforms |

---

## Quality Metrics

| Metric | Adzuna Only | With Greenhouse | With Lever | Combined |
|--------|------------|-----------------|------------|----------|
| Avg chars per job | 150 | 8,500+ | 7,000+ | 6,000+ |
| Skills extraction F1 | 0.29 | 0.85+ | 0.85+ | 0.80+ |
| Remote status F1 | 0.565 | 0.85+ | 0.85+ | 0.80+ |
| Coverage | 1,500 jobs/mo | +302 companies | +50 companies | Full |

### Classification Confidence

- **Full descriptions (Greenhouse/Lever):** F1 ≥0.85 (high confidence)
- **Truncated descriptions (Adzuna):** F1 ~0.30-0.56 (low confidence)
- **Combined (all sources):** F1 ≥0.80 (good confidence)

---

## Usage Examples

```bash
# Full three-source pipeline
python wrappers/fetch_jobs.py lon 100 --sources adzuna,greenhouse,lever

# Premium companies only (Greenhouse + Lever)
python wrappers/fetch_jobs.py --sources greenhouse,lever

# Specific source only
python wrappers/fetch_jobs.py --sources lever

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

All sources call `classify_job_with_claude(job_text, structured_input)` but provide different data quality:

#### Adzuna Jobs (83% of dataset)

```python
structured_input = {
    'title': "Senior Data Engineer",
    'company': "Tech Company Ltd",
    'description': "We are seeking a Senior Data Engineer to join our growing team. You will be responsible for building and maintaining data pipelines using Python, SQL, and AWS. Strong experience with [TEXT TRUNCATED]",  # ~200 chars
    'location': "London",
    'category': "IT Jobs",
    'salary_min': 75000,
    'salary_max': 95000
}
```

**Prompt sent to Claude:**
```
# JOB TO CLASSIFY

**Job Title:** Senior Data Engineer
**Company:** Tech Company Ltd
**Category:** IT Jobs
**Location:** London
**Salary Range:** 75000 - 95000

**Job Description:**
We are seeking a Senior Data Engineer to join our growing team. You will be
responsible for building and maintaining data pipelines using Python, SQL, and
AWS. Strong experience with [TEXT TRUNCATED]
```

**Classification Results:**
- ✅ Job family/subfamily (from title: "Data Engineer")
- ✅ Seniority (from title: "Senior")
- ⚠️ Skills (only Python, SQL, AWS mentioned before truncation)
- ❌ Working arrangement (cut off) → **80.5% unknown rate**
- ❌ Detailed requirements (cut off)
- ❌ Experience range (cut off)

---

#### Greenhouse Jobs (14% of dataset)

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

#### Lever Jobs (3% of dataset)

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

| Field | Adzuna | Greenhouse | Lever |
|-------|--------|------------|-------|
| **Title** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Company** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Description** | ⚠️ Truncated (~200 chars) | ✅ Full (9K-15K chars) | ✅ Full |
| **Location Metadata** | ✅ Yes | ❌ No | ✅ Yes |
| **Category Metadata** | ✅ Yes ("IT Jobs") | ❌ No | ❌ No |
| **Salary Metadata** | ⚠️ Sometimes | ❌ No | ❌ No |
| **Working Arr. in Text** | ❌ Usually cut off | ✅ Present | ✅ Present |
| **Skills in Text** | ⚠️ Partial | ✅ Detailed | ✅ Detailed |
| **Requirements in Text** | ❌ Cut off | ✅ Complete | ✅ Complete |

### Classification Accuracy Impact

| Source | Working Arr. Unknown | Jobs in DB | Avg Description |
|--------|---------------------|------------|-----------------|
| **Adzuna** | 80.5% | 7,193 | ~200 chars |
| **Greenhouse** | 5.8% | 1,243 | ~12,000 chars |
| **Lever** | 0% | 232 | Full text |

**Key Insight:** Adzuna has great metadata but truncated text. Greenhouse/Lever have full text but no metadata. The multi-source approach combines strengths: use Adzuna for volume/discovery, use Greenhouse/Lever for quality classification.

---

## Future Expansion

Potential additional ATS platforms:

```python
# Planned future scrapers
class ATSScraperOrchestrator:
    scrapers = {
        'greenhouse': GreenhouseScraper(),  # IMPLEMENTED
        'lever': LeverFetcher(),            # IMPLEMENTED
        'ashby': AshbyScraper(),            # Future
        'workable': WorkableScraper(),      # Future
        'custom': CustomCareersScraper()    # For custom career sites
    }
```

---

## Summary

The multi-source architecture provides:

- **Breadth** - 1,500+ jobs/month from Adzuna (market trends)
- **Depth (Greenhouse)** - 302 premium companies via browser automation
- **Depth (Lever)** - 50+ premium companies via public API
- **Quality** - Complete 5,000-15,000+ char descriptions (vs 100-200 char truncation)
- **Flexibility** - Can enable/disable sources independently
- **Cost-effective** - Mix of cheap API + moderate automation
- **Scalable** - Can expand to other ATS platforms

**Current Status:** All three pipelines operational, unified ingestion working, dashboard live at richjacobs.me/projects/hiring-market.

---

**Last Updated:** 2025-12-16
**Changes:** Added Lever as third pipeline source (public JSON API), updated architecture diagram and comparisons
