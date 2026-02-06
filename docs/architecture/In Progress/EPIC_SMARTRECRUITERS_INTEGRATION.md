# Epic: SmartRecruiters ATS Integration

**Status:** [IN PROGRESS]
**Created:** 2026-02-06

## Overview

SmartRecruiters is a mid-market/enterprise ATS with ~4,000 customers (Visa, Bosch, LinkedIn, Deloitte). It offers a public Posting API (`GET /v1/companies/{slug}/postings`) requiring no authentication, with rich structured fields including `locationType` (remote/onsite), `experienceLevel`, department, and industry.

**Expected yield:** ~200-500 relevant Data/Product postings across our 5 target cities, with stronger mid-market/enterprise representation than Greenhouse/Lever.

## API Reference

**Base URL:** `https://api.smartrecruiters.com/v1/companies/{slug}/postings`

**Pagination:** `offset` + `limit` (max 100 per page)

**Response shape:**
```json
{
  "totalFound": 42,
  "offset": 0,
  "limit": 100,
  "content": [
    {
      "id": "uuid-string",
      "name": "Data Engineer",
      "location": {
        "city": "London",
        "region": "England",
        "country": "GB",
        "remote": true
      },
      "department": {"id": "...", "label": "Engineering"},
      "experienceLevel": {"id": "mid_senior_level", "label": "Mid-Senior Level"},
      "typeOfEmployment": {"id": "full_time", "label": "Full-time"},
      "industry": {"id": "...", "label": "Internet"},
      "function": {"id": "...", "label": "Information Technology"},
      "jobAd": {
        "sections": {
          "jobDescription": {"text": "..."},
          "qualifications": {"text": "..."},
          "additionalInformation": {"text": "..."},
          "companyDescription": {"text": "..."}
        }
      },
      "releasedDate": "2026-01-15T10:00:00Z"
    }
  ]
}
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API approach | Public Posting API | No auth, structured JSON, rich metadata |
| Rate limiting | 2.0s between requests | Conservative; no documented limit |
| Pagination | offset + limit (max 100/page) | API requirement; loop until exhausted |
| Description | jobAd.sections concatenation | All description parts from list endpoint |
| `location.remote` mapping | `remote` -> `working_arrangement='remote'` | Direct structured signal |
| `experienceLevel` | Pass as classifier hint only | Don't override LLM seniority classification |
| GHA schedule | Thu/Sun 8PM UTC | No conflicts with existing workflows |
| Template | Workable fetcher | Closest API pattern (REST, no auth, structured fields) |

## Key Field Mappings

| SmartRecruiters Field | Pipeline Field | Notes |
|-----------------------|----------------|-------|
| `id` | `source_job_id` | UUID string |
| `name` | `title` | Job title |
| `location.remote` | `working_arrangement` | `true` -> `remote`, `false` -> classifier decides |
| `location.city/region/country` | `locations` (via extract_locations) | Structured location data |
| `experienceLevel.id` | metadata hint | Passed to classifier, not used directly |
| `department.label` | `employer_department` | Via classifier |
| `typeOfEmployment.id` | `position_type` | Via classifier |
| `jobAd.sections.*` | `description` | Concatenated sections |
| `releasedDate` | `published_at` metadata | ISO timestamp |

## Stories

### Story 1: Core Scraper [DONE]
- `scrapers/smartrecruiters/smartrecruiters_fetcher.py`
- `config/smartrecruiters/company_mapping.json`
- `config/smartrecruiters/title_patterns.yaml`
- `config/smartrecruiters/location_patterns.yaml`

### Story 2: Pipeline Integration [DONE]
- `pipeline/unified_job_ingester.py` - SMARTRECRUITERS enum
- `pipeline/fetch_jobs.py` - `process_smartrecruiters_incremental()`

### Story 3: Utility Updates [DONE]
- `pipeline/utilities/discover_ats_companies.py`
- `pipeline/utilities/validate_ats_slugs.py`
- `pipeline/utilities/enrich_employer_metadata.py`
- `pipeline/utilities/seed_employer_metadata.py`

### Story 4: Report Generator + Docs [DONE]
- `pipeline/report_generator.py` - ATS_SOURCES
- `CLAUDE.md` - updated
- This epic doc

### Story 5: GitHub Actions Workflow [DONE]
- `.github/workflows/scrape-smartrecruiters.yml`
- Schedule: Thu/Sun 8PM UTC

### Story 6: Initial Company Seed [TODO]
- Populate `config/smartrecruiters/company_mapping.json` with validated companies
- Validate via `validate_ats_slugs.py smartrecruiters`

## Files Created/Modified

**Created:**
- `scrapers/smartrecruiters/__init__.py`
- `scrapers/smartrecruiters/smartrecruiters_fetcher.py`
- `config/smartrecruiters/company_mapping.json`
- `config/smartrecruiters/title_patterns.yaml`
- `config/smartrecruiters/location_patterns.yaml`
- `.github/workflows/scrape-smartrecruiters.yml`
- `docs/architecture/In Progress/EPIC_SMARTRECRUITERS_INTEGRATION.md`

**Modified:**
- `pipeline/unified_job_ingester.py` - DataSource enum
- `pipeline/fetch_jobs.py` - process function, main(), stats, summary
- `pipeline/report_generator.py` - ATS_SOURCES list
- `pipeline/utilities/discover_ats_companies.py` - ATS_CONFIG
- `pipeline/utilities/validate_ats_slugs.py` - CONFIG_PATHS, VALIDATION_CONFIG, choices
- `pipeline/utilities/enrich_employer_metadata.py` - ATS_URL_TEMPLATES, CONFIG_PATHS, defaults
- `pipeline/utilities/seed_employer_metadata.py` - SmartRecruiters config block
- `CLAUDE.md` - commands, architecture, config, modules, workflows
