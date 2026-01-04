# Epic: Employer Metadata Enrichment

**Status:** Phase 1 In Progress
**Priority:** Medium
**Complexity:** Moderate
**Created:** 2026-01-04
**Last Updated:** 2026-01-04

## Implementation Progress

| Task | Status | Notes |
|------|--------|-------|
| Migration 025 (add columns) | [DONE] | industry, website, headquarters, etc. |
| Migration 025b (update view) | [DONE] | View includes employer_industry |
| Migration 025c (add financial_services) | [DONE] | 19th category for traditional banks |
| classify_employer_industry.py | [DONE] | LLM batch classifier ready |
| Dry-run test (100 employers) | [DONE] | Classifications validated |
| Run classifier for all employers | [TODO] | ~5,500 employers pending |
| Career page scraper | [TODO] | Phase 2 |
| Manual curation export/import | [TODO] | Phase 3 |

## Problem Statement

The `employer_metadata` table currently stores only basic attributes (`canonical_name`, `display_name`, `employer_size`, `working_arrangement_default`). Job seekers would benefit from richer employer context including:

1. **Industry Classification** - Filter jobs by sector (fintech, healthtech, AI/ML, etc.)
2. **Working Arrangement** - Know company remote/hybrid/onsite policy before applying
3. **Company Context** - Website, description, headquarters, logo
4. **Funding/Stage** - Understand company maturity (startup vs enterprise)

### Constraints

- **Data freshness required** - Cannot rely on aged sources for attributes that change (working arrangement, funding)
- **Free sources only** - No budget for paid APIs (Crunchbase, Clearbit, etc.)
- **Scale** - Must classify ~5,500+ employers (600 ATS + 4,900 Adzuna)

---

## Solution: Extended Employer Metadata

### New Schema Columns

```sql
-- Identity
website TEXT                         -- Primary domain (e.g., stripe.com)
logo_url TEXT                        -- Company logo URL
description TEXT                     -- Brief company description (1-2 sentences)

-- Classification
industry TEXT                        -- 19-category taxonomy (see below)
industry_source TEXT                 -- manual | inferred | scraped

-- Organization
headquarters_city TEXT               -- e.g., "San Francisco"
headquarters_country TEXT            -- e.g., "US"
ownership_type TEXT                  -- private | public | subsidiary | acquired
parent_company TEXT                  -- If subsidiary/acquired
founding_year INTEGER                -- Year founded

-- Funding (optional, for private companies)
funding_stage TEXT                   -- seed | series_a | series_b | series_c | growth | public
total_funding_usd BIGINT             -- Total funding raised
last_funding_date DATE               -- Most recent funding round

-- Metadata
enrichment_source TEXT               -- manual | inferred | scraped
enrichment_date DATE                 -- When data was last enriched
```

---

## Industry Taxonomy (19 Categories)

Domain-focused verticals, not business models. "B2B SaaS" was intentionally excluded - it's a business model that spans multiple industries.

| Code | Label | Examples | Classification Signals |
|------|-------|----------|------------------------|
| `fintech` | FinTech | Stripe, Monzo, Affirm, Plaid | payments, neobank, lending platform, insurtech |
| `financial_services` | Financial Services | JPMorgan, Capital One, BlackRock | traditional bank, insurer, asset manager |
| `healthtech` | HealthTech | Flatiron, Omada, Oscar | health, medical, patient, clinical, pharma |
| `ecommerce` | E-commerce & Marketplace | Instacart, Deliveroo, Etsy | marketplace, retail, delivery, logistics |
| `ai_ml` | AI/ML | OpenAI, Anthropic, Harvey AI | ai-first, foundation model, llm, generative |
| `consumer` | Consumer Tech | Spotify, Reddit, Strava | consumer, social, entertainment, gaming |
| `mobility` | Mobility & Logistics | Uber, Waymo, Zipline | transportation, autonomous, fleet, vehicle |
| `proptech` | PropTech | Airbnb, Zillow, CoStar | real estate, property, housing, rental |
| `edtech` | EdTech | Coursera, Duolingo, Guild | education, learning, training, course |
| `climate` | Climate Tech | Watershed, Crusoe, Yes Energy | climate, sustainability, carbon, renewable |
| `crypto` | Crypto & Web3 | Coinbase, Kraken, OpenSea | crypto, blockchain, defi, web3 |
| `devtools` | Developer Tools | GitHub, Vercel, Linear, Retool | dev productivity, IDE, CI/CD, infrastructure |
| `data_infra` | Data Infrastructure | Snowflake, Databricks, dbt Labs | data platforms, analytics tools, pipelines |
| `cybersecurity` | Cybersecurity | Okta, Vanta, 1Password | security, identity, compliance |
| `hr_tech` | HR Tech | Rippling, Gusto, Deel, Lattice | HR, payroll, workforce, recruiting |
| `martech` | Marketing Tech | Braze, Amplitude, HubSpot | marketing, analytics, CRM, customer data |
| `professional_services` | Professional Services | Deloitte, Accenture, PwC | consulting, advisory (non-tech companies) |
| `hardware` | Hardware & Robotics | Apple, Gecko Robotics, Cruise | physical products, robotics, semiconductor |
| `other` | Other | Catch-all | unclassified |

---

## Data Sources

### Tier 1: Free Sources (In Scope)

| Source | Data Points | Method |
|--------|-------------|--------|
| **LLM (Gemini)** | industry classification | Batch process company name + job descriptions |
| **Career Pages** | working_arrangement, description, logo | Scrape during ATS fetch |
| **Company Website** | website, meta description | Derive from career page URL |
| **Job Data** | industry signals, tech stack | Infer from existing job descriptions |

### Tier 2: Paid APIs (Not in Scope)

| Source | Data Points | Notes |
|--------|-------------|-------|
| Crunchbase | funding, industry, HQ, founding_year | $49-199/mo, API is enterprise tier |
| Clearbit/Breeze | firmographics, logo | Requires HubSpot, ~$0.10/record |
| BuiltWith | tech_stack | $295/mo+ |

### Tier 3: Deprecated APIs (Not in Scope)

| Source | Data Points | Notes |
|--------|-------------|-------|
| LinkedIn | employee_count, growth | API deprecated 2019, scraping only |
| Glassdoor | ratings, reviews | API deprecated 2021, scraping only |

---

## Implementation Plan

### Phase 1: Schema + Industry Classification

| Task | File | Description |
|------|------|-------------|
| Migration | `migrations/025_extend_employer_metadata.sql` | Add new columns to employer_metadata |
| View Update | `migrations/025b_update_view.sql` | Add industry to jobs_with_employer_context |
| Industry Classifier | `pipeline/utilities/classify_employer_industry.py` | Batch LLM classification for all ~5,500 employers |
| Taxonomy Update | `docs/schema_taxonomy.yaml` | Add industry enum |

**LLM Classification Approach:**
- Input: company name + 3 sample job titles/descriptions
- Output: industry from 18-category taxonomy
- Cost: ~$15-25 for 5,500 employers (using Gemini)
- Batch with rate limiting

### Phase 2: Career Page Scraping

| Task | File | Description |
|------|------|-------------|
| Career Scraper | `pipeline/utilities/scrape_career_pages.py` | Extract working_arrangement, description, logo |

**Working Arrangement Signals:**
```python
HYBRID_SIGNALS = ["hybrid", "days in office", "days a week", "flexible"]
REMOTE_SIGNALS = ["fully remote", "remote-first", "work from anywhere", "distributed"]
ONSITE_SIGNALS = ["on-site", "in-office", "in-person required"]
```

### Phase 3: Manual Curation

| Task | File | Description |
|------|------|-------------|
| Export Script | `pipeline/utilities/export_for_curation.py` | Generate CSV of top 100 employers |
| Import Script | Same file | Validate and upload curated data |

**Focus on:**
- Employers with highest job counts
- Low-confidence LLM classifications
- Missing working_arrangement after scraping

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Employers with industry set | >95% of ~5,500 |
| ATS employers with working_arrangement | >50% of ~600 |
| Top 100 employers fully enriched | 100% |
| Data freshness (enrichment_date < 6 months) | >80% |

---

## Data Freshness Strategy

### Attributes That Change Frequently

| Attribute | Refresh Frequency | Method |
|-----------|-------------------|--------|
| working_arrangement | Monthly | Career page re-scrape |
| funding_stage | On news | Manual update |

### Attributes That Rarely Change

| Attribute | Refresh Frequency |
|-----------|-------------------|
| industry | Rarely (acquisitions only) |
| headquarters | Rarely |
| founding_year | Never |
| website | Rarely |

---

## API/UI Integration

### Job Feed Filter

```typescript
// New filter option
const industryOptions = [
  { value: 'fintech', label: 'FinTech' },
  { value: 'healthtech', label: 'HealthTech' },
  { value: 'ai_ml', label: 'AI/ML' },
  // ... etc
];
```

### SQL Query

```sql
SELECT * FROM jobs_with_employer_context
WHERE industry = 'fintech'
  AND job_family = 'data'
  AND seniority = 'senior';
```

---

## Files to Create/Modify

| File | Action | Priority |
|------|--------|----------|
| `migrations/025_extend_employer_metadata.sql` | CREATE | P1 |
| `migrations/025b_update_view.sql` | CREATE | P1 |
| `pipeline/utilities/classify_employer_industry.py` | CREATE | P1 |
| `pipeline/utilities/scrape_career_pages.py` | CREATE | P2 |
| `pipeline/utilities/export_for_curation.py` | CREATE | P3 |
| `docs/schema_taxonomy.yaml` | MODIFY | P1 |
| `.claude/skills/taxonomy-architect/taxonomy-architect-skill.md` | MODIFY | P1 |

---

## Not in Scope

- Paid APIs (Crunchbase, Clearbit, BuiltWith)
- Deprecated APIs requiring scraping (Glassdoor, LinkedIn)
- GitHub tech stack extraction (nice-to-have, future)
- Glassdoor ratings (API deprecated)

---

**Document Version:** 1.0
**Last Updated:** 2026-01-04
