# Epic: Workable ATS Integration

**Epic ID:** EPIC-009  
**Created:** 2026-01-03  
**Status:** Backlog  
**Estimated Effort:** 2-3 days  

---

## Overview

Add Workable as a job source alongside Greenhouse, Lever, and Ashby. Workable has ~30,000 customers (primarily SMB) and offers a public API requiring no authentication.

---

## Technical Reference

### API Endpoints (No Auth Required)

**Primary endpoint:**
```
GET https://www.workable.com/api/accounts/{subdomain}?details=true
```

**Additional endpoints:**
```
GET https://www.workable.com/api/accounts/{subdomain}/locations
GET https://www.workable.com/api/accounts/{subdomain}/departments
```

**Alternative (widget API):**
```
GET https://apply.workable.com/api/v1/widget/accounts/{subdomain}
```

### Rate Limiting

| Limit | Interval | Notes |
|-------|----------|-------|
| 10 requests | 10 seconds | Authenticated API (documented) |
| Unknown | Unknown | Public API (undocumented) |

**Recommendation:** Use 1 request/second for public endpoints. Monitor for HTTP 429 responses.

**Response headers to check:**
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

### URL Patterns

| Pattern | Example |
|---------|---------|
| Careers page | `apply.workable.com/{subdomain}/` |
| Job posting | `apply.workable.com/{subdomain}/j/{shortcode}/` |
| Custom domain | `careers.{company}.com` (some companies) |

### Response Schema

```json
{
  "name": "Company Name",
  "description": "Company description",
  "jobs": [
    {
      "id": "string",
      "title": "string",
      "full_title": "string",
      "shortcode": "ABC123",
      "code": "string",
      "state": "published",
      "department": "Engineering",
      "url": "https://apply.workable.com/company/j/ABC123",
      "application_url": "https://apply.workable.com/company/j/ABC123/apply",
      "workplace_type": "on_site | hybrid | remote",
      "location": {
        "location_str": "London, United Kingdom",
        "country": "United Kingdom",
        "country_code": "GB",
        "region": "Greater London",
        "region_code": "ENG",
        "city": "London",
        "zip_code": "string",
        "telecommuting": false
      },
      "created_at": "2025-01-03",
      "salary": {
        "salary_from": 50000,
        "salary_to": 70000,
        "salary_currency": "GBP"
      }
    }
  ]
}
```

### Field Mapping

| Workable Field | Our Schema Field | Notes |
|----------------|------------------|-------|
| `title` | `role.title_display` | Direct |
| `shortcode` | `posting.req_id` | Unique identifier |
| `department` | `employer.department` | May need normalization |
| `workplace_type` | `location.working_arrangement` | Values align |
| `location.city` | `location.city_code` | Map to our codes |
| `location.country_code` | — | Filter by target markets |
| `salary.*` | `compensation.base_salary_range` | Direct when present |
| `created_at` | `posting.posted_date` | Direct |
| `url` | `posting.posting_url` | Direct |

**Fields requiring LLM classification:**
- `job_family` — infer from title/department
- `job_subfamily` — infer from title/description
- `seniority` — infer from title
- `skills` — extract from description

### Company Discovery Challenge

Unlike other ATS platforms, Workable requires knowing company subdomains upfront. 

**Discovery options:**
1. Manual curation of known tech companies
2. Parse Adzuna redirect chains for `apply.workable.com` URLs
3. Google: `site:apply.workable.com "data engineer"`

**Recommendation:** Start with curated seed list of 50-100 companies. Validate coverage before automating discovery.

---

## User Stories

### US-001: Company Seed List

**As a** platform operator  
**I want to** maintain a list of Workable companies to fetch  
**So that** I can control which companies are ingested

**Acceptance Criteria:**
- [ ] Table stores subdomain, company name, discovery source
- [ ] Track last fetch timestamp and job count per company
- [ ] Flag to enable/disable individual companies

---

### US-002: Job Ingestion

**As a** platform operator  
**I want to** fetch jobs from Workable companies  
**So that** they enter our data pipeline

**Acceptance Criteria:**
- [ ] Fetch jobs for all active companies in seed list
- [ ] Respect rate limits (1 req/sec recommended)
- [ ] Store raw response in dedicated table
- [ ] Use `shortcode` as unique identifier for deduplication
- [ ] Log errors without blocking pipeline
- [ ] Handle 404s gracefully (company removed or no jobs)

---

### US-003: Market Filtering

**As a** platform operator  
**I want to** filter Workable jobs to target markets  
**So that** only relevant jobs proceed to enrichment

**Acceptance Criteria:**
- [ ] Filter to GB and US country codes
- [ ] Filter to target cities (London, NYC metro, Denver metro)
- [ ] Log filtered-out jobs for coverage analysis

---

### US-004: Schema Mapping

**As a** platform operator  
**I want to** map Workable fields to our enriched schema  
**So that** jobs are queryable alongside other sources

**Acceptance Criteria:**
- [ ] Map all available fields per mapping table above
- [ ] Set `source = 'workable'`
- [ ] Generate job hash for cross-source deduplication
- [ ] Handle missing salary/location fields gracefully

---

### US-005: Classification Integration

**As a** platform operator  
**I want to** classify Workable jobs through existing pipeline  
**So that** they receive consistent taxonomy labels

**Acceptance Criteria:**
- [ ] Pass jobs through Haiku classification
- [ ] Apply existing agency detection
- [ ] Store in `enriched_jobs` with source attribution
- [ ] Monitor classification accuracy vs other sources

---

### US-006: Automated Discovery (Future)

**As a** platform operator  
**I want to** discover new Workable companies automatically  
**So that** coverage grows without manual curation

**Acceptance Criteria:**
- [ ] Parse Adzuna jobs for Workable redirect URLs
- [ ] Extract subdomain from URL pattern
- [ ] Validate subdomain returns jobs before adding
- [ ] Deduplicate against existing seed list

---

## Implementation Notes

### Agency Detection

Workable's SMB customer base means higher agency prevalence. Monitor for:
- Staffing companies posting client roles
- "On behalf of" patterns in descriptions
- Single company with jobs across many unrelated locations

### Deduplication

Some Workable jobs may already appear via Adzuna. Use job hash (company + title + location) to detect overlap.

### Description Availability

The `?details=true` parameter should return descriptions, but verify this works on public API. Description quality impacts classification accuracy.

---

## Definition of Done

- [ ] Seed list table created with initial companies
- [ ] Raw jobs table created for Workable source
- [ ] Fetcher runs successfully (manual trigger)
- [ ] Jobs filtered to target markets
- [ ] Jobs flow through classification pipeline
- [ ] Workable jobs appear in `enriched_jobs`
- [ ] Jobs display correctly in dashboard/feed