---
name: company-curator
description: Manage the company universe for Greenhouse and Lever scrapers. Use when asked to add new companies, validate existing companies, check for broken career pages, or expand source coverage.
---

# Company Curator

Maintain and expand the company universe tracked by the job analytics pipeline. Ensure career page URLs are valid, companies are properly configured, and coverage gaps are identified.

## When to Use This Skill

Trigger when user asks to:
- Add a new company to tracking
- Check if companies are still valid
- Find companies returning 0 jobs
- Expand coverage to new companies
- Validate career page URLs
- Update company configurations
- Identify broken or changed career pages

## Company Inventory

### Current Coverage

| Source | Companies | Config File |
|--------|-----------|-------------|
| Greenhouse | 302 | `config/greenhouse/company_ats_mapping.json` |
| Lever | 61 | `config/lever/company_mapping.json` |
| Adzuna | N/A (API) | Cities configured in workflows |

### Config File Formats

**Greenhouse (`company_ats_mapping.json`):**
```json
{
  "Company Name": {
    "slug": "company-slug",
    "url": "https://job-boards.greenhouse.io/company-slug"
  }
}
```

**Lever (`company_mapping.json`):**
```json
{
  "Company Name": {
    "slug": "company-slug",
    "url": "https://jobs.lever.co/company-slug"
  }
}
```

## Adding New Companies

### Step 1: Identify the ATS

**Greenhouse indicators:**
- URL contains `greenhouse.io` or `boards.greenhouse.io`
- Career page redirects to Greenhouse-hosted page
- Job listings have Greenhouse application forms

**Lever indicators:**
- URL contains `jobs.lever.co` or `lever.co`
- Career page has Lever branding
- Application flow through Lever

**Other ATS (not currently supported):**
- Workday, Ashby, BambooHR, etc.

### Step 2: Find the Slug

**For Greenhouse:**
```bash
# Visit the careers page and find the Greenhouse URL
# Examples:
# https://boards.greenhouse.io/anthropic -> slug = "anthropic"
# https://job-boards.greenhouse.io/stripe -> slug = "stripe"
# https://boards.eu.greenhouse.io/company -> slug = "company" (EU)
```

**For Lever:**
```bash
# Visit careers page and find Lever URL
# Examples:
# https://jobs.lever.co/figma -> slug = "figma"
# https://jobs.eu.lever.co/company -> slug = "company" (EU)
```

### Step 3: Validate the Slug

**Greenhouse validation:**
```bash
python pipeline/utilities/validate_greenhouse_slugs.py --slug company-slug
```

Or manually check:
```bash
curl -s "https://boards.greenhouse.io/company-slug" | head -20
# Should return job listings, not 404
```

**Lever validation:**
```bash
python scrapers/lever/validate_lever_sites.py --slug company-slug
```

Or manually check:
```bash
curl -s "https://api.lever.co/v0/postings/company-slug" | head -20
# Should return JSON array of jobs
```

### Step 4: Add to Config

**For Greenhouse:**
```python
# In config/greenhouse/company_ats_mapping.json
{
  "New Company": {
    "slug": "newcompany",
    "url": "https://boards.greenhouse.io/newcompany"
  }
}
```

**For Lever:**
```python
# In config/lever/company_mapping.json
{
  "New Company": {
    "slug": "newcompany",
    "url": "https://jobs.lever.co/newcompany"
  }
}
```

### Step 5: Test the Addition

```bash
# Test Greenhouse company
python wrappers/fetch_jobs.py --sources greenhouse --companies "New Company" --dry-run

# Test Lever company
python wrappers/fetch_jobs.py --sources lever --companies "New Company" --dry-run
```

## Company Health Checks

### Finding Companies with 0 Jobs

```sql
-- Companies in config but returning 0 jobs recently
-- (Run after a full pipeline execution)

-- Check GHA logs for:
-- "Jobs found: 0" patterns
-- Timeout errors
-- 404 responses
```

**Common reasons for 0 jobs:**
| Reason | Diagnosis | Action |
|--------|-----------|--------|
| Company stopped hiring | Check careers page manually | Keep in config (temporary) |
| Slug changed | 404 in logs | Update slug |
| ATS migration | Different URL structure | Update URL or remove |
| Geographic filter | Jobs exist but not in target cities | Expected behavior |
| Title filter | Jobs exist but not target roles | Expected behavior |

### Validating Existing Companies

```bash
# Validate all Greenhouse slugs
python pipeline/utilities/validate_greenhouse_slugs.py --all

# Validate all Lever slugs
python scrapers/lever/validate_lever_sites.py --all
```

**Validation checks:**
- URL returns 200 status
- Page contains job listings (not empty)
- No redirect to different domain
- Response time < 10 seconds

### Identifying Stale Companies

```sql
-- Companies not seen in last 30 days
SELECT DISTINCT employer_name, MAX(scraped_at) as last_seen
FROM enriched_jobs
GROUP BY employer_name
HAVING MAX(scraped_at) < NOW() - INTERVAL '30 days'
ORDER BY last_seen;
```

## Expanding Coverage

### Discovery Methods

**1. Competitor analysis:**
```bash
# Find companies similar to existing ones
# Check "Similar companies" on LinkedIn
# Review industry reports
```

**2. Job board mining:**
```bash
# Search Adzuna results for companies using Greenhouse/Lever
# Look for patterns in application URLs
```

**3. Greenhouse/Lever directories:**
```bash
# Greenhouse customer list (limited public info)
# Lever customer case studies
```

**4. Tech company lists:**
```bash
# YC company directory
# Crunchbase filters
# Built In city lists
```

### Discovery Script

```bash
# Find potential Greenhouse companies from Adzuna data
python pipeline/utilities/discover_greenhouse_slugs.py

# Find potential Lever companies
python scrapers/lever/discover_lever_companies.py
```

## Company Categories

### By Industry (for targeting)

| Category | Examples | Priority |
|----------|----------|----------|
| Big Tech | Google, Meta, Amazon | High |
| AI/ML | Anthropic, OpenAI, Cohere | High |
| Fintech | Stripe, Plaid, Affirm | High |
| SaaS | Salesforce, Datadog, Snowflake | Medium |
| Startups | YC companies, Series A-C | Medium |
| Enterprise | Traditional tech companies | Low |

### By ATS Platform

Track which companies use which ATS for coverage planning:

| ATS | Coverage | Notes |
|-----|----------|-------|
| Greenhouse | 348 companies | Primary source |
| Lever | 61 companies | Secondary source |
| Workday | 0 | Not supported (complex) |
| Ashby | 0 | Potential future addition |
| Custom | 0 | Per-company scraping needed |

## Maintenance Tasks

### Weekly Checks

1. Review GHA logs for companies with 0 jobs
2. Check for new 404 errors
3. Verify no company has been returning 0 for 4+ weeks

### Monthly Checks

1. Run full slug validation
2. Review companies for ATS migrations
3. Add 5-10 new companies from discovery

### Quarterly Checks

1. Audit company list against industry changes
2. Remove defunct companies
3. Rebalance coverage across industries

## Output Format

When curating companies, produce:

```markdown
## Company Curation Report

**Date:** [Date]
**Scope:** [What was checked]

### Current Inventory

| Source | Total | Active | Inactive |
|--------|-------|--------|----------|
| Greenhouse | 302 | X | Y |
| Lever | 61 | X | Y |

### Health Check Results

#### Companies Returning 0 Jobs (4+ weeks)
| Company | Last Jobs | Weeks Empty | Action |
|---------|-----------|-------------|--------|
| [Name] | [Date] | X | [Check/Remove] |

#### Validation Failures
| Company | Issue | Resolution |
|---------|-------|------------|
| [Name] | 404 | Update slug to X |
| [Name] | Timeout | Retry / investigate |

### New Companies to Add

| Company | ATS | Slug | Validated |
|---------|-----|------|-----------|
| [Name] | Greenhouse | [slug] | Yes/No |

### Companies to Remove

| Company | Reason |
|---------|--------|
| [Name] | [Defunct/migrated ATS/etc] |

### Config Changes

```json
// Add to company_ats_mapping.json:
{
  "New Company": {"slug": "newco", "url": "..."}
}

// Remove from company_ats_mapping.json:
// "Old Company": {...}
```
```

## Key Files to Reference

- `config/greenhouse/company_ats_mapping.json` - Greenhouse companies
- `config/lever/company_mapping.json` - Lever companies
- `pipeline/utilities/validate_greenhouse_slugs.py` - Validation script
- `pipeline/utilities/discover_greenhouse_slugs.py` - Discovery script
- `scrapers/lever/validate_lever_sites.py` - Lever validation
- `scrapers/lever/discover_lever_companies.py` - Lever discovery
