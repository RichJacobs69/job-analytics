# Epic: Employer Metadata Enrichment

**Status:** Phase 2 Complete - Ready for Full Run
**Priority:** Medium
**Complexity:** Moderate
**Created:** 2026-01-04
**Last Updated:** 2026-01-05

## Implementation Progress

| Task | Status | Notes |
|------|--------|-------|
| Migration 025 (add columns) | [DONE] | industry, website, headquarters, etc. |
| Migration 025b (update view) | [DONE] | View includes employer_industry |
| Migration 025c (add financial_services) | [DONE] | 19th category for traditional banks |
| classify_employer_industry.py | [DEPRECATED] | Merged into enrich_employer_metadata.py |
| enrich_employer_metadata.py | [DONE] | Combined scraping + LLM enrichment |
| Rule-based pre-classification | [DONE] | Staffing, VC, banks auto-classified |
| Anti-bias prompt rules | [DONE] | Fixes ai_ml over-classification (see docs/temp/INDUSTRY_CLASSIFIER_ANALYSIS.md) |
| Dry-run validation | [DONE] | Tested with OpenAI, Figma, Stripe |
| Run enrichment for all employers | [TODO] | ~690 ATS employers pending |
| Manual curation export/import | [TODO] | Phase 3 |

## Quick Start

```bash
# Dry run (preview)
python -m pipeline.utilities.enrich_employer_metadata --dry-run --limit 10

# Full run for all ATS employers
python -m pipeline.utilities.enrich_employer_metadata --apply

# Re-enrich specific employer
python -m pipeline.utilities.enrich_employer_metadata --employer stripe --apply --force

# Use higher quality model
python -m pipeline.utilities.enrich_employer_metadata --model pro --apply
```

## Problem Statement

Job seekers need richer employer context to make informed decisions:

| Need | Status | Notes |
|------|--------|-------|
| Industry Classification | [DONE] | 19-category taxonomy via LLM |
| Working Arrangement | [DONE] | Extracted from career pages via LLM |
| Company Context | [DONE] | Website, description, HQ, logo |
| Funding/Stage | [NOT IN SCOPE] | Requires paid APIs |

### Constraints

- **Free sources only** - No budget for paid APIs (Crunchbase, Clearbit, etc.)
- **Scale** - ~690 ATS employers (primary focus) + ~4,900 Adzuna employers (future)
- **Bias fix** - Must NOT use job titles for classification (causes ai_ml over-classification)

---

## Current Schema (employer_metadata)

### Columns That Exist NOW

| Column | Type | Populated By | Status |
|--------|------|--------------|--------|
| `id` | SERIAL | auto | - |
| `canonical_name` | TEXT | seed script | [DONE] |
| `display_name` | TEXT | seed script | [DONE] |
| `employer_size` | TEXT | manual | partial |
| `working_arrangement_default` | TEXT | enrich script (LLM) | [DONE] |
| `working_arrangement_source` | TEXT | enrich script | [DONE] |
| `website` | TEXT | enrich script (LLM) | [DONE] |
| `logo_url` | TEXT | enrich script (scraped) | [DONE] |
| `description` | TEXT | enrich script (LLM) | [DONE] |
| `industry` | TEXT | enrich script (LLM) | [DONE] |
| `headquarters_city` | TEXT | enrich script (LLM) | [DONE] |
| `headquarters_country` | TEXT | enrich script (LLM) | [DONE] |
| `ownership_type` | TEXT | enrich script (LLM) | [DONE] |
| `parent_company` | TEXT | enrich script (LLM) | [DONE] |
| `founding_year` | INTEGER | enrich script (LLM) | [DONE] |
| `enrichment_source` | TEXT | enrich script | [DONE] |
| `enrichment_date` | DATE | enrich script | [DONE] |
| `created_at` | TIMESTAMPTZ | auto | - |
| `updated_at` | TIMESTAMPTZ | trigger | - |

### What enrich_employer_metadata.py Does

**Scrapes from career pages:**
- `logo_url` - from og:image meta tag

**Generates via LLM (Gemini):**
- `industry` - 19-category taxonomy with anti-bias rules
- `website` - company's actual domain (NOT the ATS URL)
- `careers_url` - company's careers page (logged, not stored in DB)
- `description` - 1-2 paragraph rich narrative
- `working_arrangement_default` - remote/hybrid/onsite/flexible
- `headquarters_city`, `headquarters_country` - from LLM knowledge
- `ownership_type`, `parent_company` - from LLM knowledge
- `founding_year` - from LLM knowledge

**Sets automatically:**
- `enrichment_source` = 'scraped'
- `enrichment_date` = today
- `working_arrangement_source` = 'scraped' (respects manual > scraped > inferred)

**Note:** The ATS career page URL (e.g., job-boards.greenhouse.io/stripe) is passed to the LLM as context, but the LLM infers the company's actual website (e.g., stripe.com) and careers page (e.g., jobs.stripe.com) from its knowledge.

### Columns NOT YET Added (Future)

```sql
-- Funding (requires paid API like Crunchbase)
funding_stage TEXT                   -- seed | series_a | series_b | ... | public
total_funding_usd BIGINT             -- Total funding raised
last_funding_date DATE               -- Most recent funding round
```

These would require paid data sources and are out of scope for now.

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

### Currently Used (enrich_employer_metadata.py)

| Source | Data Points | Method |
|--------|-------------|--------|
| **Career Pages** | logo_url | Scrape og:image meta tag |
| **Career Page Text** | working_arrangement signals | Passed to LLM for extraction |
| **LLM (Gemini)** | industry, website, careers_url, description, HQ, ownership, founding_year | Company name + ATS URL + career page text |

**Key Changes:**
- Industry is classified using career page text, NOT job titles (fixes ai_ml over-classification)
- Website is LLM-inferred (e.g., "stripe.com"), NOT scraped from ATS URL (which would give "greenhouse.io")
- Careers URL is also LLM-inferred (e.g., "jobs.stripe.com") for companies with custom career pages

### Not Used (Paid APIs)

| Source | Data Points | Notes |
|--------|-------------|-------|
| Crunchbase | funding, industry, HQ | $49-199/mo, API is enterprise tier |
| Clearbit/Breeze | firmographics, logo | Requires HubSpot, ~$0.10/record |
| BuiltWith | tech_stack | $295/mo+ |
| LinkedIn | employee_count | API deprecated, scraping only |
| Glassdoor | ratings, reviews | API deprecated |

---

## Implementation Plan

### Phase 1: Schema [DONE]

| Task | File | Description |
|------|------|-------------|
| Migration | `migrations/025_extend_employer_metadata.sql` | Add new columns to employer_metadata |
| View Update | `migrations/025b_update_view.sql` | Add industry to jobs_with_employer_context |
| Financial Services | `migrations/025c_add_financial_services_industry.sql` | 19th category for traditional banks |

### Phase 2: Combined Enrichment [DONE]

| Task | File | Description |
|------|------|-------------|
| Unified Enricher | `pipeline/utilities/enrich_employer_metadata.py` | Combined scraping + LLM enrichment |
| Old Classifier | `pipeline/utilities/classify_employer_industry.py` | [DEPRECATED] - merged into above |

**Enrichment Approach (fixes ai_ml over-classification):**
- Input: company name + website + career page text (NOT job titles)
- Rule-based pre-classification for staffing/VC/banks
- Anti-bias rules in LLM prompt
- Output: industry, description, working_arrangement, HQ, ownership, founding_year
- Cost: ~$20-50 for 690 ATS employers (using Gemini Flash)

**Working Arrangement Detection:**
- Extracted by LLM from career page text
- Source priority: manual > scraped > inferred

### Phase 3: Manual Curation [TODO]

| Task | File | Description |
|------|------|-------------|
| Export Script | `pipeline/utilities/export_for_curation.py` | Generate CSV of top 100 employers |
| Import Script | Same file | Validate and upload curated data |

**Focus on:**
- Employers with highest job counts
- Low-confidence LLM classifications
- Missing working_arrangement after enrichment

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

## Files Created/Modified

| File | Status | Notes |
|------|--------|-------|
| `migrations/025_extend_employer_metadata.sql` | [DONE] | Schema extension |
| `migrations/025b_update_view.sql` | [DONE] | View update |
| `migrations/025c_add_financial_services_industry.sql` | [DONE] | 19th category |
| `pipeline/utilities/enrich_employer_metadata.py` | [DONE] | Main enrichment script |
| `pipeline/utilities/classify_employer_industry.py` | [DEPRECATED] | Merged into above |
| `pipeline/utilities/export_for_curation.py` | [TODO] | Phase 3 |
| `docs/temp/INDUSTRY_CLASSIFIER_ANALYSIS.md` | [DONE] | Root cause analysis |

---

## Not in Scope

- Paid APIs (Crunchbase, Clearbit, BuiltWith)
- Deprecated APIs requiring scraping (Glassdoor, LinkedIn)
- GitHub tech stack extraction (nice-to-have, future)
- Glassdoor ratings (API deprecated)

---

**Document Version:** 2.0
**Last Updated:** 2026-01-05
