# Epic: Employer Metadata System

**Status:** In Progress
**Priority:** Medium
**Complexity:** Low-Moderate
**Started:** 2026-01-04

## Problem Statement

Employer-level attributes are currently stored per-job in `enriched_jobs`, causing:

1. **Inconsistent Classifications**: Same employer receives different `employer_size` values across jobs
2. **No Single Source of Truth**: Employer attributes repeated across N job rows
3. **Name Variation Issues**: Case differences (e.g., "Figma" vs "figma") treated as separate entities
4. **Missing Working Arrangement**: When classifier returns 'unknown', we have no fallback for known company policies (e.g., Harvey AI is hybrid - 3 days/week in office)

### Trigger: Working Arrangement Fallback

This epic was accelerated due to Ashby/Lever jobs missing working arrangement data. The Ashby API provides `isRemote: bool` but no hybrid/onsite distinction. Company policies like "3 days in office" are shown on web pages but not in API responses.

**Example:** Harvey AI's job "Innovation Product Manager, EMEA" was classified as `working_arrangement: unknown` because the hybrid policy wasn't in the job description text.

## Solution: Employer Metadata Table

### Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Migration `018_create_employer_metadata.sql` | [DONE] | Table created in Supabase |
| Migration `019_rename_employer_fill_stats_column.sql` | [DONE] | Renamed employer_name -> canonical_name |
| Migration `020_create_jobs_with_employer_context_view.sql` | [TODO] | View for API with display_name JOIN |
| `db_connection.py` functions | [DONE] | Cache + lookup + upsert |
| `seed_employer_metadata.py` utility | [DONE] | Seeds from config files (source of truth) |
| `employer_stats.py` updated | [DONE] | Uses canonical_name (lowercase) |
| `fetch_jobs.py` fallback logic | [DONE] | 5 locations updated |
| Run seed script | [DONE] | 1,455 employers, 327 from config |
| Set known company arrangements | [TODO] | Harvey AI, Intercom, etc. |
| Update Job Feed API to use view | [TODO] | portfolio-site changes |

### Database Schema (Implemented)

```sql
CREATE TABLE employer_metadata (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,      -- lowercase, normalized
    aliases TEXT[] DEFAULT '{}',              -- name variations
    display_name TEXT NOT NULL,               -- pretty version for UI
    employer_size TEXT CHECK (employer_size IN ('startup', 'scaleup', 'enterprise')),
    working_arrangement_default TEXT CHECK (
        working_arrangement_default IN ('hybrid', 'remote', 'onsite', 'flexible')
    ),
    working_arrangement_source TEXT CHECK (
        working_arrangement_source IN ('manual', 'inferred', 'scraped')
    ),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Working Arrangement Fallback Priority

```
1. Classifier extraction from job text     (highest confidence)
2. ATS flag (Ashby is_remote=True)         (API signal)
3. employer_metadata.working_arrangement_default  (company policy)
4. 'unknown'                               (honest uncertainty)
```

### Architecture

```
                              employer_metadata (source of truth)
                              +----------------------------+
                              | canonical_name (PK)        |
                              | display_name               | <-- UI display
                              | employer_size              | <-- Canonical
                              | working_arrangement_default|
                              | working_arrangement_source |
                              +----------------------------+
                                        ^
                                        | JOIN lower(employer_name)
                                        |
enriched_jobs                           |           employer_fill_stats
+------------------+                    |           +----------------------------+
| employer_name    |--------------------+---------->| canonical_name (PK)        |
| title_display    |                                | median_days_to_fill        |
| job_family       |                                | sample_size                |
| employer_size    | (deprecated)                   +----------------------------+
| working_arr...   |
+------------------+
        |
        | COALESCE(em.display_name, ej.employer_name)
        v
jobs_with_employer_context (VIEW)
+----------------------------------+
| employer_name (= display_name)   | <-- Proper casing for UI
| employer_name_raw                | <-- Original for debugging
| employer_canonical               | <-- For JOINs
| employer_median_days_to_fill     | <-- From employer_fill_stats
| days_open                        | <-- Computed
| fill_time_ratio                  | <-- Computed
| ... all enriched_jobs fields ... |
+----------------------------------+
```

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `migrations/018_create_employer_metadata.sql` | Created | Table schema |
| `migrations/019_rename_employer_fill_stats_column.sql` | Created | Rename employer_name -> canonical_name |
| `migrations/020_create_jobs_with_employer_context_view.sql` | Created | View with display_name JOIN |
| `pipeline/db_connection.py` | Modified | Added `get_employer_metadata()`, `get_working_arrangement_fallback()`, `upsert_employer_metadata()` |
| `pipeline/utilities/seed_employer_metadata.py` | Modified | Seeds from config files (source of truth) |
| `pipeline/employer_stats.py` | Modified | Uses canonical_name (lowercase) |
| `pipeline/fetch_jobs.py` | Modified | Fallback logic at 5 locations (Greenhouse, Adzuna, Lever, Ashby, generic store) |

## Usage

### Seed the table from existing data

```bash
# Preview what would be created
python -m pipeline.utilities.seed_employer_metadata --dry-run

# Seed with minimum 3 jobs per employer
python -m pipeline.utilities.seed_employer_metadata --min-jobs 3

# Include known working arrangements
python -m pipeline.utilities.seed_employer_metadata --seed-known
```

### Update known company arrangements

```bash
# Update only known arrangements
python -m pipeline.utilities.seed_employer_metadata --update-known-only
```

### Add new company manually

```python
from pipeline.db_connection import upsert_employer_metadata

upsert_employer_metadata(
    canonical_name='harvey ai',
    display_name='Harvey AI',
    working_arrangement_default='hybrid',
    working_arrangement_source='manual'
)
```

## Known Companies with Working Arrangements

| Company | Arrangement | Source |
|---------|-------------|--------|
| Harvey AI | hybrid | Career page: "3 days/week in office" |
| Intercom | hybrid | Career page |
| (add more as verified) | | |

## Future Enhancement: Career Page Scraping

**Status:** Planned (separate work item)

Working arrangement policies should eventually be scraped from company career pages:

1. During ATS scraping, also fetch the company's main careers page
2. Extract working arrangement policy using pattern matching or LLM
3. Store with `working_arrangement_source='scraped'`
4. Flag for human review if confidence is low

## Benefits

| Benefit | Impact |
|---------|--------|
| Consistent working arrangements | Known companies get correct arrangement, not 'unknown' |
| Single source of truth | Update once, applies to all future jobs |
| Extensibility | Easy to add more employer attributes |
| No classifier changes | Fallback applied post-classification |

## Success Metrics

- Harvey AI jobs now show `hybrid` instead of `unknown`
- Known companies have correct working arrangements
- Cache hit rate for employer lookups >= 80%

## Display Name Source Priority

The `seed_employer_metadata.py` script uses this priority for `display_name`:

1. **ATS config file key** (source of truth) - e.g., "Nuro" from `config/greenhouse/company_ats_mapping.json`
2. **KNOWN_WORKING_ARRANGEMENTS** dict - manual overrides
3. **Most common capitalized variant** from enriched_jobs data
4. **Most common variant overall** - last resort

This ensures proper casing (e.g., "Figma" not "figma") even when all jobs came from sources that use lowercase slugs.

## API Integration

The Job Feed API in `portfolio-site` should query the `jobs_with_employer_context` view instead of `enriched_jobs` directly:

```sql
-- Old (enriched_jobs directly)
SELECT employer_name, ... FROM enriched_jobs WHERE ...

-- New (via view with proper display_name)
SELECT employer_name, ... FROM jobs_with_employer_context WHERE ...
```

The view automatically:
- JOINs with `employer_metadata` to get `display_name`
- JOINs with `employer_fill_stats` to get `median_days_to_fill`
- Computes `days_open` and `fill_time_ratio`

---

**Document Version:** 4.0
**Last Updated:** 2026-01-04
**Previous Version:** 3.0 (2026-01-04) - working_arrangement_default implementation
**Changes in v4.0:** Added display_name source priority, employer_fill_stats canonical_name rename, jobs_with_employer_context view
