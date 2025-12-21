# Epic: Global Location Expansion

**Created:** 2025-12-17
**Updated:** 2025-12-18
**Status:** Phase 2 Complete (Phases 1-2 Done)
**Priority:** High
**Estimated Sessions:** 8-12

## Executive Summary

Expand the job analytics pipeline from 3 cities (London, NYC, Denver) to support global tech hubs. This requires a fundamental schema change from the current `city_code` enum to a flexible `locations` JSONB array that supports multi-location jobs, remote work scopes, and regional filtering.

**Test Cities for Phase 1:** San Francisco + Singapore (plus existing London, NYC, Denver)

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Goals](#goals)
3. [Current State](#current-state)
4. [New Architecture](#new-architecture)
5. [Schema Design](#schema-design)
6. [Files to Create](#files-to-create)
7. [Files to Modify](#files-to-modify)
8. [Implementation Phases](#implementation-phases)
9. [Migration Strategy](#migration-strategy)
10. [API Route Changes](#api-route-changes)
11. [Testing Strategy](#testing-strategy)
12. [Success Criteria](#success-criteria)
13. [Future Expansion](#future-expansion)

---

## Problem Statement

### Current Limitations

1. **Hardcoded city enum:** `city_code` only supports 5 values: `lon`, `nyc`, `den`, `remote`, `unk`
2. **No country grouping:** Can't query "all UK jobs" or "all US jobs"
3. **No regional grouping:** Can't query "EMEA jobs" or "APAC jobs"
4. **Remote conflation:** "Remote - US" and "Remote - UK" both become `city_code = 'remote'`
5. **Multi-location loss:** "NYC or Remote" loses the remote component
6. **Adzuna hardcoded:** Only 2 country endpoints (UK, US)
7. **Location patterns limited:** Only match London, NYC, Denver, and generic remote

### Business Impact

- Cannot expand to European capitals (Berlin, Amsterdam, Dublin)
- Cannot expand to Indian tech hubs (Bangalore, Mumbai)
- Cannot expand to APAC (Singapore, Sydney)
- Cannot expand to more US cities (San Francisco, Seattle, Austin)
- Cannot answer regional comparison questions (Europe vs Americas vs APAC)

---

## Goals

### Primary Goals

1. **Flexible location schema:** Support any city, country, or region
2. **Multi-location support:** Store multiple locations per job as array
3. **Remote scope tracking:** Distinguish US Remote vs UK Remote vs Global
4. **Regional grouping:** Enable EMEA, AMER, APAC filtering
5. **Country rollups:** Enable "all UK jobs" queries
6. **Backward compatible:** Migrate existing data without loss

### Secondary Goals

1. **Token efficiency:** Minimize LLM usage for location extraction
2. **Deterministic extraction:** Pattern matching first, LLM fallback only for ambiguous
3. **Extensible config:** Easy to add new cities via YAML config
4. **Query performance:** Efficient JSONB indexing for location queries

---

## Current State

### Database Schema

```sql
-- Current enriched_jobs table
city_code VARCHAR  -- enum: lon | nyc | den | remote | unk
working_arrangement VARCHAR  -- enum: onsite | hybrid | remote | flexible | unknown
```

### Location Filtering Files

| File | Purpose | Current Patterns |
|------|---------|------------------|
| `config/greenhouse_location_patterns.yaml` | Greenhouse pre-filter | ~60 patterns (London, NYC, Denver, Remote variants) |
| `config/lever_location_patterns.yaml` | Lever pre-filter | Copy of greenhouse patterns |

### Location Filtering Code

| File | Function | Purpose |
|------|----------|---------|
| `scrapers/greenhouse/greenhouse_scraper.py` | `load_location_patterns()` | Load YAML patterns |
| `scrapers/greenhouse/greenhouse_scraper.py` | `matches_target_location()` | Substring matching |
| `scrapers/lever/lever_fetcher.py` | Same functions imported | Reuses greenhouse functions |

### Adzuna Configuration

```python
# scrapers/adzuna/fetch_adzuna_jobs.py
ADZUNA_BASE_URLS = {
    "lon": "https://api.adzuna.com/v1/api/jobs/gb/search",  # UK
    "nyc": "https://api.adzuna.com/v1/api/jobs/us/search",  # US
    "den": "https://api.adzuna.com/v1/api/jobs/us/search",  # US
}

LOCATION_QUERIES = {
    "lon": "London",
    "nyc": "New York",
    "den": "Colorado"
}
```

### Classifier Prompt (classifier.py lines 215-220)

```
# LOCATION MAPPING GUIDANCE
- London, UK / London, England / Greater London → lon
- New York, NY / NYC / Manhattan, Brooklyn, Queens, Bronx, Staten Island → nyc
- Denver, CO / Any Colorado city → den
- Remote / Work from Home / WFH / Remote-first / Anywhere → remote
- If location cannot be determined → unk
```

---

## New Architecture

### Location Extraction Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     RAW LOCATION STRING                              │
│         (from Lever API, Greenhouse scrape, or Adzuna API)          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│              [1] PATTERN MATCHING (Python - FREE)                    │
│                                                                      │
│  Input: "London or Stockholm"                                        │
│  Config: config/location_mapping.yaml                                │
│  Output: [                                                           │
│    {"type": "city", "country_code": "GB", "city": "london"},        │
│    {"type": "city", "country_code": "SE", "city": "stockholm"}      │
│  ]                                                                   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                          ┌─────────┴─────────┐
                          │                   │
                    Matched?              Not Matched
                          │                   │
                          ▼                   ▼
┌─────────────────────────────┐   ┌───────────────────────────────────┐
│      Return locations       │   │  [2] CHECK AMBIGUOUS RULES        │
│         array               │   │                                   │
└─────────────────────────────┘   │  - "Flexible" (location or WFH?)  │
                                  │  - "Multiple locations"            │
                                  │  - Company office names            │
                                  └───────────────────────────────────┘
                                              │
                                    ┌─────────┴─────────┐
                                    │                   │
                              Resolvable?         Ambiguous
                                    │                   │
                                    ▼                   ▼
                          ┌─────────────────┐  ┌───────────────────────┐
                          │  Return best    │  │ [3] LLM FALLBACK      │
                          │  guess          │  │     (~$0.001/job)     │
                          └─────────────────┘  │                       │
                                               │  Only for truly       │
                                               │  ambiguous cases      │
                                               │  (<5% of jobs)        │
                                               └───────────────────────┘
```

### Data Flow Changes

```
BEFORE:
  Lever API → location: "London" → city_code: "lon" → enriched_jobs

AFTER:
  Lever API → location: "London or Stockholm"
            → location_extractor.py
            → locations: [{"type": "city", "country_code": "GB", "city": "london"},
                         {"type": "city", "country_code": "SE", "city": "stockholm"}]
            → enriched_jobs
```

---

## Schema Design

### New Column

```sql
-- Add to enriched_jobs table
ALTER TABLE enriched_jobs
ADD COLUMN locations JSONB NOT NULL DEFAULT '[]';

-- Create GIN index for efficient querying
CREATE INDEX idx_enriched_jobs_locations ON enriched_jobs USING GIN (locations);
```

### Location Object Structure

```typescript
interface Location {
  type: "city" | "country" | "region" | "remote";

  // For type="city" or type="country"
  country_code?: string;  // ISO 3166-1 alpha-2: US, GB, SG, DE, IN
  city?: string;          // snake_case: san_francisco, london, singapore

  // For type="region" (multi-country remote)
  region?: string;        // EMEA | AMER | APAC

  // For type="remote"
  scope?: "global" | "country" | "region";
}
```

### Example Data

| Job Posting | `locations` JSONB |
|-------------|-------------------|
| "London, UK" | `[{"type": "city", "country_code": "GB", "city": "london"}]` |
| "San Francisco, CA" | `[{"type": "city", "country_code": "US", "city": "san_francisco"}]` |
| "Singapore" | `[{"type": "city", "country_code": "SG", "city": "singapore"}]` |
| "Remote - US" | `[{"type": "remote", "scope": "country", "country_code": "US"}]` |
| "Remote - Global" | `[{"type": "remote", "scope": "global"}]` |
| "Remote - EMEA" | `[{"type": "remote", "scope": "region", "region": "EMEA"}]` |
| "NYC or Remote" | `[{"type": "city", "country_code": "US", "city": "new_york"}, {"type": "remote", "scope": "country", "country_code": "US"}]` |
| "London or Stockholm" | `[{"type": "city", "country_code": "GB", "city": "london"}, {"type": "city", "country_code": "SE", "city": "stockholm"}]` |

### Columns to Keep vs Deprecate

| Column | Status | Reason |
|--------|--------|--------|
| `city_code` | **DEPRECATE** | Replaced by `locations` JSONB array |
| `working_arrangement` | **KEEP** | Orthogonal dimension: WHERE (locations) vs HOW (arrangement) |

---

## Files to Create

### New Files

| File | Purpose |
|------|---------|
| `config/location_mapping.yaml` | Master location config with all cities, countries, regions |
| `pipeline/location_extractor.py` | Deterministic location extraction from raw strings |
| `pipeline/utilities/migrate_locations.py` | Backfill script for existing data |
| `tests/test_location_extractor.py` | Unit tests for location extraction |
| `tests/test_location_migration.py` | Tests for migration script |

### config/location_mapping.yaml Structure

```yaml
# Master location configuration
# All cities, countries, and regions for the job analytics pipeline

version: "1.0"
last_updated: "2025-12-17"

# =============================================================================
# CITIES
# =============================================================================
# Format: snake_case key → {country_code, display_name, patterns[]}

cities:
  # -------------------------
  # United States
  # -------------------------
  new_york:
    country_code: US
    display_name: New York
    patterns:
      - new york
      - nyc
      - manhattan
      - brooklyn
      - queens
      - bronx
      - new york, ny
      - new york city
      - ny metro

  san_francisco:
    country_code: US
    display_name: San Francisco
    patterns:
      - san francisco
      - sf
      - bay area
      - san francisco, ca
      - san francisco, california
      - sf bay
      - sfba

  denver:
    country_code: US
    display_name: Denver
    patterns:
      - denver
      - denver, co
      - denver, colorado
      - boulder
      - boulder, co
      - colorado springs
      - denver metro

  seattle:
    country_code: US
    display_name: Seattle
    patterns:
      - seattle
      - seattle, wa
      - seattle, washington
      - bellevue
      - redmond

  austin:
    country_code: US
    display_name: Austin
    patterns:
      - austin
      - austin, tx
      - austin, texas

  # -------------------------
  # United Kingdom
  # -------------------------
  london:
    country_code: GB
    display_name: London
    patterns:
      - london
      - greater london
      - london, uk
      - london, england
      - london, united kingdom
      - central london

  # -------------------------
  # Singapore (city-state)
  # -------------------------
  singapore:
    country_code: SG
    display_name: Singapore
    patterns:
      - singapore
      - sg

  # -------------------------
  # Europe (future expansion)
  # -------------------------
  berlin:
    country_code: DE
    display_name: Berlin
    patterns:
      - berlin
      - berlin, germany
      - berlin, de

  amsterdam:
    country_code: NL
    display_name: Amsterdam
    patterns:
      - amsterdam
      - amsterdam, netherlands
      - amsterdam, nl

  dublin:
    country_code: IE
    display_name: Dublin
    patterns:
      - dublin
      - dublin, ireland
      - dublin, ie

  stockholm:
    country_code: SE
    display_name: Stockholm
    patterns:
      - stockholm
      - stockholm, sweden
      - stockholm, se

  # -------------------------
  # India (future expansion)
  # -------------------------
  bangalore:
    country_code: IN
    display_name: Bangalore
    patterns:
      - bangalore
      - bengaluru
      - bangalore, india
      - bengaluru, india
      - blr

  mumbai:
    country_code: IN
    display_name: Mumbai
    patterns:
      - mumbai
      - bombay
      - mumbai, india

# =============================================================================
# COUNTRIES
# =============================================================================
# ISO 3166-1 alpha-2 codes

countries:
  US:
    display_name: United States
    aliases: [usa, united states, united states of america, america]
  GB:
    display_name: United Kingdom
    aliases: [uk, united kingdom, great britain, britain, england]
  SG:
    display_name: Singapore
    aliases: []
  DE:
    display_name: Germany
    aliases: [deutschland]
  NL:
    display_name: Netherlands
    aliases: [holland]
  IE:
    display_name: Ireland
    aliases: []
  SE:
    display_name: Sweden
    aliases: []
  IN:
    display_name: India
    aliases: []
  AU:
    display_name: Australia
    aliases: []
  CA:
    display_name: Canada
    aliases: []

# =============================================================================
# REGIONS
# =============================================================================

regions:
  EMEA:
    display_name: Europe, Middle East & Africa
    patterns:
      - emea
      - europe
      - european
      - middle east
      - africa
    countries: [GB, DE, FR, NL, IE, SE, ES, IT, AT, CH, PL, BE, DK, NO, FI, PT, IL, AE, ZA]

  AMER:
    display_name: Americas
    patterns:
      - amer
      - americas
      - north america
      - south america
      - latam
      - latin america
    countries: [US, CA, MX, BR, AR, CO, CL]

  APAC:
    display_name: Asia Pacific
    patterns:
      - apac
      - asia pacific
      - asia
      - pacific
      - asiapac
    countries: [SG, IN, AU, NZ, JP, KR, CN, HK, TW, ID, PH, MY, TH, VN]

# =============================================================================
# REMOTE PATTERNS
# =============================================================================

remote_patterns:
  global:
    patterns:
      - remote
      - fully remote
      - 100% remote
      - work from anywhere
      - anywhere
      - worldwide
      - global remote

  us_only:
    country_code: US
    patterns:
      - remote - us
      - remote - usa
      - remote (us)
      - us remote
      - remote united states
      - work from home - us

  uk_only:
    country_code: GB
    patterns:
      - remote - uk
      - remote - gb
      - remote (uk)
      - uk remote
      - remote united kingdom
      - work from home - uk

  emea:
    region: EMEA
    patterns:
      - remote - emea
      - emea remote
      - remote (emea)

  apac:
    region: APAC
    patterns:
      - remote - apac
      - apac remote
      - remote (apac)
      - remote - asia

# =============================================================================
# ADZUNA ENDPOINT MAPPING
# =============================================================================

adzuna_endpoints:
  US:
    base_url: https://api.adzuna.com/v1/api/jobs/us/search
    cities:
      - new_york
      - san_francisco
      - denver
      - seattle
      - austin
  GB:
    base_url: https://api.adzuna.com/v1/api/jobs/gb/search
    cities:
      - london
  SG:
    base_url: https://api.adzuna.com/v1/api/jobs/sg/search
    cities:
      - singapore
  DE:
    base_url: https://api.adzuna.com/v1/api/jobs/de/search
    cities:
      - berlin
  NL:
    base_url: https://api.adzuna.com/v1/api/jobs/nl/search
    cities:
      - amsterdam
  IN:
    base_url: https://api.adzuna.com/v1/api/jobs/in/search
    cities:
      - bangalore
      - mumbai
  AU:
    base_url: https://api.adzuna.com/v1/api/jobs/au/search
    cities:
      - sydney
```

---

## Files to Modify

### Pipeline Files

| File | Changes |
|------|---------|
| `pipeline/db_connection.py` | Add `locations` parameter to `insert_enriched_job()` |
| `pipeline/fetch_jobs.py` | Use `location_extractor` instead of hardcoded city_code |
| `pipeline/classifier.py` | Simplify location guidance (pattern matching handles most cases) |

### Scraper Files

| File | Changes |
|------|---------|
| `scrapers/adzuna/fetch_adzuna_jobs.py` | Expand `ADZUNA_BASE_URLS` and `LOCATION_QUERIES` |
| `scrapers/greenhouse/greenhouse_scraper.py` | Use new `location_extractor` module |
| `scrapers/lever/lever_fetcher.py` | Use new `location_extractor` module |

### Config Files

| File | Changes |
|------|---------|
| `config/greenhouse_location_patterns.yaml` | **DEPRECATE** - Replaced by `location_mapping.yaml` |
| `config/lever_location_patterns.yaml` | **DEPRECATE** - Replaced by `location_mapping.yaml` |
| `docs/schema_taxonomy.yaml` | Update `location_city` enum documentation |

### API Routes (portfolio-site)

| File | Changes |
|------|---------|
| `app/api/hiring-market/role-demand/route.ts` | Update query to use `locations` JSONB |
| `app/api/hiring-market/top-skills/route.ts` | Update query to use `locations` JSONB |
| `app/api/hiring-market/working-arrangement/route.ts` | No change (uses `working_arrangement`) |
| `app/api/hiring-market/top-companies/route.ts` | Update query to use `locations` JSONB |
| `app/api/hiring-market/experience-distribution/route.ts` | Update query to use `locations` JSONB |
| `app/api/hiring-market/count/route.ts` | Update query to use `locations` JSONB |

### Frontend Components (portfolio-site)

| File | Changes |
|------|---------|
| `app/projects/hiring-market/components/GlobalFilters.tsx` | Add country/region filter options |

---

## Implementation Phases

### Phase 1: Schema & Core Infrastructure (Sessions 1-2) ✅ COMPLETE

**Session 1: Database & Config** ✅
1. ✅ Created `config/location_mapping.yaml` with cities/countries/regions (Phase 1: London, NYC, Denver, SF, Singapore)
2. ✅ Added `locations` JSONB column to `enriched_jobs` table (migration 008)
3. ✅ Created GIN index for efficient querying
4. ✅ Kept `city_code` column for backward compatibility

**Session 2: Location Extractor Module** ✅
1. ✅ Created `pipeline/location_extractor.py` with all functions
   - `load_location_config()` - Load YAML config
   - `extract_locations(raw_location, description_text)` - Main extraction function
   - `match_city_pattern()` - Match against city patterns
   - `match_remote_pattern()` - Match against remote patterns
   - `match_region_pattern()` - Match against region patterns
   - `match_country_pattern()` - Match against country aliases
   - `is_location_match()` - Utility for pre-filtering
   - `split_multi_location()` - Handle "NYC or Remote" patterns
2. ✅ Created `tests/test_location_extractor.py` with 50+ test cases
3. ✅ Tested with manual test run - all patterns working correctly

### Phase 2: Backfill Existing Data (Sessions 3-4) ✅ COMPLETE

**Session 3: Migration Script** ✅
1. ✅ Created `pipeline/utilities/migrate_locations.py`
2. ✅ Migration logic implemented:
   - `city_code = 'lon'` → `[{"type": "city", "country_code": "GB", "city": "london"}]`
   - `city_code = 'nyc'` → `[{"type": "city", "country_code": "US", "city": "new_york"}]`
   - `city_code = 'den'` → `[{"type": "city", "country_code": "US", "city": "denver"}]`
   - `city_code = 'remote'` → Infers scope from `data_source` field (adzuna_lon → GB, etc.)
   - `city_code = 'unk'` → Re-processes with location extractor on raw_jobs.raw_text

**Session 4: Run Backfill** ✅
1. ✅ Ran migration on full dataset (8,670 jobs)
2. ✅ 100% success rate (8,670/8,670 jobs migrated, 0 failures)
3. ✅ Validation results:
   - **lon (2,844 jobs):** 100% mapped to London, GB
   - **nyc (3,082 jobs):** 100% mapped to New York, US
   - **den (1,675 jobs):** 100% mapped to Denver, US
   - **remote (471 jobs):** 48% global, 26% US-scoped, 14% SG-scoped (intelligent inference)
   - **unk (598 jobs):** Re-processed successfully
     - 54 jobs discovered as San Francisco (9%)
     - 11 jobs discovered as Singapore (2%)
     - 15 jobs remain unknown (2.5%)
4. ✅ **Discoveries:** Found SF and Singapore jobs that were previously unknown!

### Phase 3: Pipeline Integration (Sessions 5-6)

**Session 5: Update Scrapers**
1. Update `scrapers/greenhouse/greenhouse_scraper.py`:
   - Replace `load_location_patterns()` with `location_extractor`
   - Replace `matches_target_location()` with new matching logic
   - Update filter stats to use new structure
2. Update `scrapers/lever/lever_fetcher.py` similarly

**Session 6: Update Pipeline Core**
1. Update `pipeline/fetch_jobs.py`:
   - Import and use `location_extractor`
   - Remove hardcoded city_code assignments
   - Update incremental processing for all sources
2. Update `pipeline/db_connection.py`:
   - Add `locations` parameter to `insert_enriched_job()`
   - Update hash generation to use locations
3. Update `pipeline/classifier.py`:
   - Simplify location guidance in prompt
   - Remove hardcoded city mappings

### Phase 4: API & Frontend Updates (Sessions 7-8)

**Session 7: API Route Updates**
1. Update all Next.js API routes to query `locations` JSONB
2. Add new query helpers for:
   - Filter by country
   - Filter by region
   - Filter by city
   - Include remote jobs in country/region filters
3. Test API routes with new schema

**Session 8: Frontend Updates**
1. Update `GlobalFilters.tsx`:
   - Add country dropdown (initially: US, GB, SG)
   - Add region dropdown (EMEA, AMER, APAC)
   - Update city dropdown to be country-aware
2. Update dashboard visualizations to handle new data structure
3. Test end-to-end filtering

### Phase 5: Test Cities - SF & Singapore (Sessions 9-10)

**Session 9: San Francisco**
1. Update Adzuna config for SF (US endpoint, "San Francisco" query)
2. Run Adzuna pipeline for SF
3. Run Greenhouse/Lever for SF-based companies
4. Validate location extraction accuracy
5. Check dashboard shows SF data correctly

**Session 10: Singapore**
1. Update Adzuna config for Singapore (SG endpoint)
2. Run Adzuna pipeline for Singapore
3. Run Greenhouse/Lever for Singapore-based companies
4. Validate location extraction accuracy
5. Check dashboard shows Singapore data correctly

### Phase 6: Cleanup & Documentation (Sessions 11-12)

**Session 11: Deprecation**
1. Remove `city_code` column from queries (keep in schema temporarily)
2. Deprecate old location pattern files
3. Update all documentation references

**Session 12: Final Documentation**
1. Update `CLAUDE.md` with new location architecture
2. Update `MULTI_SOURCE_PIPELINE.md`
3. Create migration guide for future cities
4. Document query patterns for new schema

---

## Migration Strategy

### Phase 1: Additive (No Breaking Changes)

```sql
-- Step 1: Add new column (nullable initially)
ALTER TABLE enriched_jobs ADD COLUMN locations JSONB;

-- Step 2: Create index
CREATE INDEX idx_enriched_jobs_locations ON enriched_jobs USING GIN (locations);

-- Step 3: Backfill from city_code
UPDATE enriched_jobs SET locations =
  CASE city_code
    WHEN 'lon' THEN '[{"type": "city", "country_code": "GB", "city": "london"}]'::jsonb
    WHEN 'nyc' THEN '[{"type": "city", "country_code": "US", "city": "new_york"}]'::jsonb
    WHEN 'den' THEN '[{"type": "city", "country_code": "US", "city": "denver"}]'::jsonb
    WHEN 'remote' THEN '[{"type": "remote", "scope": "unknown"}]'::jsonb
    WHEN 'unk' THEN '[{"type": "unknown"}]'::jsonb
    ELSE '[]'::jsonb
  END;

-- Step 4: Set NOT NULL and default
ALTER TABLE enriched_jobs ALTER COLUMN locations SET NOT NULL;
ALTER TABLE enriched_jobs ALTER COLUMN locations SET DEFAULT '[]'::jsonb;
```

### Phase 2: Remote Scope Inference

```python
# For city_code = 'remote', infer scope from source
def infer_remote_scope(job):
    metadata = job.get('metadata', {})
    adzuna_city = metadata.get('adzuna_city')

    if adzuna_city == 'lon':
        return [{"type": "remote", "scope": "country", "country_code": "GB"}]
    elif adzuna_city in ('nyc', 'den'):
        return [{"type": "remote", "scope": "country", "country_code": "US"}]
    else:
        # Greenhouse/Lever - check raw_jobs.raw_text for remote patterns
        return extract_locations_from_text(job['raw_text'])
```

### Phase 3: Unknown Re-processing

```python
# For city_code = 'unk', re-process with new pattern matcher
def reprocess_unknown_locations():
    unknown_jobs = supabase.table('enriched_jobs').select('*').eq('city_code', 'unk').execute()

    for job in unknown_jobs:
        raw_job = get_raw_job(job['raw_job_id'])
        locations = extract_locations(raw_job['raw_text'])

        if locations and locations[0]['type'] != 'unknown':
            update_job_locations(job['id'], locations)
```

---

## API Route Changes

### Current Query Pattern

```typescript
// Current: Filter by city_code enum
const { data } = await supabase
  .from('enriched_jobs')
  .select('*')
  .eq('city_code', 'lon');
```

### New Query Patterns

```typescript
// Filter by specific city
const { data } = await supabase
  .from('enriched_jobs')
  .select('*')
  .contains('locations', [{ country_code: 'GB', city: 'london' }]);

// Filter by country (any city in that country)
const { data } = await supabase
  .from('enriched_jobs')
  .select('*')
  .or(`locations.cs.[{"country_code":"US"}],locations.cs.[{"type":"remote","country_code":"US"}]`);

// Filter by region (EMEA, AMER, APAC)
// Requires custom RPC function or client-side filtering
```

### Helper Functions to Create

```typescript
// lib/location-queries.ts

export function buildLocationFilter(params: {
  country?: string;
  city?: string;
  region?: string;
  includeRemote?: boolean;
}) {
  // Build appropriate Supabase filter for locations JSONB
}

export function filterJobsByLocation(jobs: Job[], location: LocationFilter): Job[] {
  // Client-side filtering for complex queries
}
```

---

## Testing Strategy

### Unit Tests (`tests/test_location_extractor.py`)

```python
# Test cases for location extraction

def test_simple_city():
    assert extract_locations("London") == [{"type": "city", "country_code": "GB", "city": "london"}]

def test_city_with_country():
    assert extract_locations("London, UK") == [{"type": "city", "country_code": "GB", "city": "london"}]

def test_multi_location():
    result = extract_locations("London or Stockholm")
    assert len(result) == 2
    assert {"type": "city", "country_code": "GB", "city": "london"} in result
    assert {"type": "city", "country_code": "SE", "city": "stockholm"} in result

def test_remote_us():
    assert extract_locations("Remote - US") == [{"type": "remote", "scope": "country", "country_code": "US"}]

def test_remote_global():
    assert extract_locations("Remote") == [{"type": "remote", "scope": "global"}]

def test_city_or_remote():
    result = extract_locations("NYC or Remote")
    assert len(result) == 2
    # Should have NYC city and US remote (inferred from NYC)

def test_san_francisco_variations():
    for variant in ["San Francisco", "SF", "Bay Area", "San Francisco, CA"]:
        result = extract_locations(variant)
        assert result[0]["city"] == "san_francisco"
        assert result[0]["country_code"] == "US"

def test_singapore():
    assert extract_locations("Singapore") == [{"type": "city", "country_code": "SG", "city": "singapore"}]
```

### Integration Tests

```python
# Test full pipeline with new location extraction

def test_lever_job_location_extraction():
    # Fetch real Lever job, extract location, verify result
    pass

def test_greenhouse_job_location_extraction():
    # Scrape real Greenhouse job, extract location, verify result
    pass

def test_adzuna_job_location_extraction():
    # Fetch real Adzuna job, extract location, verify result
    pass
```

### Migration Tests

```python
# Test migration script

def test_migrate_london_jobs():
    # Verify lon → london conversion
    pass

def test_migrate_remote_jobs_with_source():
    # Verify remote scope inference from adzuna_city
    pass

def test_migrate_unknown_jobs():
    # Verify re-processing of unknown locations
    pass
```

---

## Success Criteria

### Phase 1-2 (Schema & Migration)
- [ ] `locations` column added to enriched_jobs
- [ ] GIN index created and performant
- [ ] 100% of existing jobs have `locations` populated
- [ ] Remote jobs have correct scope inferred (not all "global")
- [ ] Unknown jobs re-processed and improved

### Phase 3-4 (Pipeline & API)
- [ ] All three pipelines use new location extractor
- [ ] No regression in existing city filtering
- [ ] API routes updated and tested
- [ ] Frontend filters work with new data

### Phase 5 (Test Cities)
- [ ] San Francisco jobs successfully ingested
- [ ] Singapore jobs successfully ingested
- [ ] Dashboard shows new cities correctly
- [ ] Location extraction accuracy >95%

### Overall
- [ ] No increase in LLM token usage (pattern matching handles most cases)
- [ ] Query performance maintained or improved
- [ ] All existing marketplace questions still answerable
- [ ] New regional/country questions now answerable

---

## Future Expansion

### Cities Ready in Config (Not Active Yet)

| City | Country | Adzuna Endpoint | Status |
|------|---------|-----------------|--------|
| Berlin | DE | Yes | Config ready |
| Amsterdam | NL | Yes | Config ready |
| Dublin | IE | Yes (via UK?) | Config ready |
| Stockholm | SE | No | Greenhouse/Lever only |
| Bangalore | IN | Yes | Config ready |
| Mumbai | IN | Yes | Config ready |
| Sydney | AU | Yes | Config ready |
| Seattle | US | Yes | Config ready |
| Austin | US | Yes | Config ready |

### Adding a New City

1. Add city definition to `config/location_mapping.yaml`
2. Add patterns for the city
3. If Adzuna supported, add to `adzuna_endpoints` section
4. Run pipeline with `--cities new_city`
5. Validate location extraction
6. Update frontend filter options

### Regional Dashboard Views

Future work could add:
- "EMEA Market Overview" dashboard
- "APAC Market Overview" dashboard
- Cross-regional comparison views

---

## References

- [ISO 3166-1 Country Codes](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)
- [Adzuna API Documentation](https://developer.adzuna.com/)
- [PostgreSQL JSONB Indexing](https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING)
- Current architecture: `docs/architecture/MULTI_SOURCE_PIPELINE.md`
- Current schema: `docs/database/SCHEMA_UPDATES.md`

---

**Last Updated:** 2025-12-17
**Author:** Claude Code
**Status:** Planning - Ready for Phase 1 Implementation
