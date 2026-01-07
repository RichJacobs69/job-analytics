# Epic: Workable ATS Integration

**Epic ID:** EPIC-009
**Created:** 2026-01-03
**Status:** Complete
**Last Updated:** 2026-01-07

---

## Overview

Add Workable as a job source alongside Greenhouse, Lever, and Ashby. Workable has ~30,000 customers (primarily SMB) and offers a public API requiring no authentication.

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| `scrapers/workable/workable_fetcher.py` | [DONE] | API client with filtering |
| `scrapers/workable/__init__.py` | [DONE] | Module exports |
| `config/workable/company_mapping.json` | [DONE] | 54 companies seeded |
| `config/workable/title_patterns.yaml` | [DONE] | Copied from Greenhouse |
| `config/workable/location_patterns.yaml` | [DONE] | Copied from Ashby |
| `pipeline/fetch_jobs.py` | [DONE] | `process_workable_incremental()` added |
| `pipeline/unified_job_ingester.py` | [DONE] | `WORKABLE` in DataSource enum |
| `.github/workflows/scrape-workable.yml` | [DONE] | Wed/Sat 6PM UTC |
| `tests/test_workable_fetcher.py` | [DONE] | Unit tests |
| `CLAUDE.md` | [DONE] | Documentation updated |

---

## Technical Reference

### API Endpoints

**Primary endpoint (used):**
```
GET https://www.workable.com/api/accounts/{subdomain}?details=true
```

**Detail endpoint (not used - requires N+1 requests):**
```
GET https://apply.workable.com/api/v2/accounts/{subdomain}/jobs/{shortcode}
```

### Actual Response Schema

The actual API response differs from initial documentation:

```json
{
  "name": "Company Name",
  "jobs": [
    {
      "title": "Backend Engineer",
      "shortcode": "D9CC0943A4",
      "code": "",
      "employment_type": "Full-time",
      "telecommuting": false,
      "department": "Engineering",
      "url": "https://apply.workable.com/j/D9CC0943A4",
      "application_url": "https://apply.workable.com/j/D9CC0943A4/apply",
      "published_on": "2025-10-22",
      "created_at": "2025-08-20",
      "country": "United Kingdom",
      "city": "London",
      "state": "England",
      "description": "<p>Full HTML description...</p>",
      "locations": [
        {
          "country": "United Kingdom",
          "countryCode": "GB",
          "city": "London",
          "region": "England"
        }
      ]
    }
  ]
}
```

### Key API Differences from Initial Spec

| Expected | Actual | Resolution |
|----------|--------|------------|
| `workplace_type: "hybrid"` | `telecommuting: boolean` | Map true->remote, let classifier infer hybrid |
| `location.location_str` | Top-level `city`, `state`, `country` | Build location string from parts |
| `location.country_code` | `locations[].countryCode` | Extract from locations array |
| `salary` object | Rarely present | Salary often in description text only |

### Working Arrangement Logic

Same pattern as Ashby:
```
1. Classifier infers from description (can detect hybrid/remote/on_site)
2. If classifier returns 'unknown' and telecommuting=true -> 'remote'
3. Else -> employer metadata fallback
```

---

## Tested Companies

| Company | Slug | Jobs | Remote | London |
|---------|------|------|--------|--------|
| Cogna | `cogna` | 12 | 0 | 7 |
| Simple Machines | `simple-machines-3` | 12 | 4 | 1 |
| Mustard Systems | `mustard-systems` | 4 | 0 | 4 |
| Vortexa | `vortexa` | 13 | 0 | 4 |
| Brilliant Corners | `brilliant-corners` | 13 | 0 | 0 |

---

## Usage

```bash
# Test single company
python -c "from scrapers.workable.workable_fetcher import fetch_workable_jobs; jobs, stats = fetch_workable_jobs('cogna'); print(stats)"

# Run pipeline (after seed data added)
python wrappers/fetch_jobs.py --sources workable

# Check if company exists
python -c "from scrapers.workable.workable_fetcher import check_company_exists; print(check_company_exists('cogna'))"
```

---

## Completion Summary

| Milestone | Status |
|-----------|--------|
| Company discovery (54 via Google CSE) | [DONE] |
| Pipeline test via GHA | [DONE] - 135 jobs ingested |
| Employer enrichment | [DONE] - 41/41 employers classified |
| canonical_name fix | [DONE] - Aligned with db_connection.py pattern |

**Final Stats:**
- 54 companies in config
- 135 jobs in enriched_jobs
- 41 distinct employers
- 100% industry classification coverage

---

## Files Created/Modified

| File | Action |
|------|--------|
| `scrapers/workable/workable_fetcher.py` | Created |
| `scrapers/workable/__init__.py` | Created |
| `config/workable/company_mapping.json` | Created (54 companies) |
| `config/workable/title_patterns.yaml` | Created |
| `config/workable/location_patterns.yaml` | Created |
| `pipeline/fetch_jobs.py` | Modified (+400 lines) |
| `pipeline/unified_job_ingester.py` | Modified (DataSource enum) |
| `pipeline/utilities/discover_ats_companies.py` | Modified (added Workable) |
| `pipeline/utilities/enrich_employer_metadata.py` | Modified (added Workable + canonical_name fix) |
| `.github/workflows/scrape-workable.yml` | Created |
| `tests/test_workable_fetcher.py` | Created |
| `CLAUDE.md` | Modified |
