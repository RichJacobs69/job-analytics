# Adding New Locations Guide

**Last Updated:** 2025-12-22
**Epic:** Global Location Expansion - Phase 6 Documentation
**Purpose:** Step-by-step guide for adding new cities, countries, or regions to the job analytics platform

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Adding a New City](#adding-a-new-city)
3. [Adding a New Country](#adding-a-new-country)
4. [Adding a New Region](#adding-a-new-region)
5. [Testing & Validation](#testing--validation)
6. [Frontend Integration](#frontend-integration)
7. [Deployment Checklist](#deployment-checklist)

---

## Prerequisites

Before adding a new location, ensure you have:
- [x] Access to `config/location_mapping.yaml`
- [x] Understanding of location extraction system (`pipeline/location_extractor.py`)
- [x] Frontend access (`portfolio-site/lib/location-queries.ts` and `GlobalFilters.tsx`)
- [x] Database access (for validation queries)

---

## Adding a New City

### 1. Update Location Mapping Config

Edit `config/location_mapping.yaml` and add your city under the appropriate country:

```yaml
cities:
  # Example: Adding Austin, Texas
  austin:
    country_code: US
    display_name: Austin
    patterns:
      - austin
      - austin, tx
      - austin, texas
```

**Pattern Guidelines:**
- Include city name alone (e.g., "austin")
- Include city with state (e.g., "austin, tx", "austin, texas")
- Include common variations (e.g., "atx" for Austin)
- **Use lowercase** for all patterns (matching is case-insensitive)

### 2. Add to Adzuna Endpoints (if applicable)

If the city's country has an Adzuna API endpoint, add it to the `adzuna_endpoints` section:

```yaml
adzuna_endpoints:
  US:
    base_url: https://api.adzuna.com/v1/api/jobs/us/search
    cities:
      - new_york
      - san_francisco
      - denver
      - seattle
      - austin  # ADD NEW CITY HERE
```

### 3. Update Frontend Constants

Add the city to `portfolio-site/lib/location-queries.ts`:

```typescript
// Update SUPPORTED_CITIES
export const SUPPORTED_CITIES = [
  'london', 'new_york', 'denver', 'san_francisco', 'singapore',
  'austin',  // ADD NEW CITY HERE
] as const;

// Update getCityCountryCode()
export function getCityCountryCode(city: string): string | null {
  const cityToCountry: Record<string, string> = {
    london: 'GB',
    new_york: 'US',
    denver: 'US',
    san_francisco: 'US',
    seattle: 'US',
    austin: 'US',  // ADD NEW CITY HERE
    singapore: 'SG',
    // ... etc
  };
  return cityToCountry[city] || null;
}

// Update getCityDisplayName()
export function getCityDisplayName(city: string): string {
  const displayNames: Record<string, string> = {
    london: 'London',
    new_york: 'New York',
    denver: 'Denver',
    san_francisco: 'San Francisco',
    austin: 'Austin',  // ADD NEW CITY HERE
    // ... etc
  };
  return displayNames[city] || city;
}
```

### 4. Add to UI Dropdown

Update `portfolio-site/app/projects/hiring-market/components/GlobalFilters.tsx`:

```typescript
<CustomSelect
  value={filters.city || 'all'}
  options={[
    { value: 'all', label: 'All Locations' },
    { value: 'london', label: 'London' },
    { value: 'new_york', label: 'New York City' },
    { value: 'denver', label: 'Denver' },
    { value: 'san_francisco', label: 'San Francisco' },
    { value: 'singapore', label: 'Singapore' },
    { value: 'austin', label: 'Austin' },  // ADD NEW CITY HERE
  ]}
  onChange={(value) =>
    handleFilterChange('city', value === 'all' ? undefined : value)
  }
  className="..."
/>
```

### 5. Update Description Text

Update the dashboard description in `GlobalFilters.tsx` and `layout.tsx` to include the new city:

```typescript
// GlobalFilters.tsx
<p className="text-xl text-gray-300">
  Real-time intelligence on Data and Product role demand, skill trends,
  and working arrangements across London, NYC, Denver, San Francisco, Singapore, and Austin
</p>

// layout.tsx
description: "Interactive analytics dashboard tracking data and product roles across London, NYC, Denver, San Francisco, Singapore, and Austin...",
```

---

## Adding a New Country

### 1. Update Location Mapping Config

Add the country to `config/location_mapping.yaml`:

```yaml
countries:
  CA:  # Canada
    display_name: Canada
    aliases: []
```

### 2. Update Frontend Constants

Add to `portfolio-site/lib/location-queries.ts`:

```typescript
// Update SUPPORTED_COUNTRIES
export const SUPPORTED_COUNTRIES = ['US', 'GB', 'SG', 'DE', 'NL', 'IE', 'SE', 'IN', 'AU', 'CA'] as const;

// Update COUNTRY_TO_REGION
export const COUNTRY_TO_REGION: Record<string, string> = {
  GB: 'EMEA',
  DE: 'EMEA',
  NL: 'EMEA',
  // ... etc
  CA: 'AMER',  // ADD NEW COUNTRY HERE
};

// Update getCountryDisplayName()
export function getCountryDisplayName(countryCode: string): string {
  const displayNames: Record<string, string> = {
    US: 'United States',
    GB: 'United Kingdom',
    SG: 'Singapore',
    CA: 'Canada',  // ADD NEW COUNTRY HERE
    // ... etc
  };
  return displayNames[countryCode] || countryCode;
}
```

### 3. Update Region Mapping

Add the country to its region in `config/location_mapping.yaml`:

```yaml
regions:
  AMER:
    display_name: Americas
    patterns:
      - amer
      - americas
      - north america
    countries: [US, CA, MX, BR, AR, CO, CL]  # ADD NEW COUNTRY HERE
```

And update `REGION_COUNTRIES` in `location-queries.ts`:

```typescript
export const REGION_COUNTRIES: Record<string, string[]> = {
  EMEA: ['GB', 'DE', 'NL', 'IE', 'SE'],
  AMER: ['US', 'CA'],  // ADD NEW COUNTRY HERE
  APAC: ['SG', 'IN', 'AU'],
};
```

---

## Adding a New Region

Adding regions is less common. Only needed if expanding beyond EMEA/AMER/APAC.

### 1. Update Location Mapping Config

```yaml
regions:
  MENA:  # Middle East & North Africa
    display_name: Middle East & North Africa
    patterns:
      - mena
      - middle east
      - north africa
    countries: [AE, SA, EG, IL]
```

### 2. Update Frontend Constants

```typescript
// Update SUPPORTED_REGIONS
export const SUPPORTED_REGIONS = ['EMEA', 'AMER', 'APAC', 'MENA'] as const;

// Update REGION_COUNTRIES
export const REGION_COUNTRIES: Record<string, string[]> = {
  EMEA: ['GB', 'DE', 'NL', 'IE', 'SE'],
  AMER: ['US'],
  APAC: ['SG', 'IN', 'AU'],
  MENA: ['AE', 'SA', 'EG', 'IL'],  // NEW REGION
};

// Update COUNTRY_TO_REGION for countries in new region
export const COUNTRY_TO_REGION: Record<string, string> = {
  // ... existing mappings
  AE: 'MENA',
  SA: 'MENA',
  EG: 'MENA',
  IL: 'MENA',
};
```

---

## Testing & Validation

### 1. Test Location Extraction

Run the location extractor test suite:

```bash
cd "C:\Cursor Projects\job-analytics"
pytest tests/test_location_extractor.py -v
```

Add test cases for your new location:

```python
def test_austin_extraction():
    result = extract_locations("Austin, TX")
    assert len(result) == 1
    assert result[0]["city"] == "austin"
    assert result[0]["country_code"] == "US"

def test_austin_variations():
    variations = ["Austin", "austin, texas", "ATX"]
    for variant in variations:
        result = extract_locations(variant)
        assert result[0]["city"] == "austin"
```

### 2. Test JSONB Queries

Test that the new location filters work in Supabase queries:

```python
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')
supabase = create_client(url, key)

# Test city filter
result = supabase.table('enriched_jobs') \
    .select('id', count='exact', head=True) \
    .filter('locations', 'cs', '[{"city":"austin"}]') \
    .execute()

print(f"Austin jobs: {result.count}")
```

### 3. Test Frontend Filtering

1. Start dev server: `cd portfolio-site && npm run dev`
2. Navigate to `http://localhost:3000/projects/hiring-market`
3. Select new city from dropdown
4. Verify data loads correctly
5. Check browser console for errors

### 4. Validate Inclusive Filtering

Ensure inclusive filtering works (city includes remote + country + region):

```typescript
// For Austin, should include:
// - Direct Austin matches: [{"city":"austin"}]
// - US country-scoped remote: [{"scope":"country"}]
// - Global remote: [{"scope":"global"}]
// - US country-wide: [{"type":"country"}]
// - AMER region: (via COUNTRY_TO_REGION mapping)
```

---

## Frontend Integration

### API Route Testing

Test each API endpoint with the new location:

```bash
# Test role-demand
curl "http://localhost:3000/api/hiring-market/role-demand?city=austin&job_family=data"

# Test top-skills
curl "http://localhost:3000/api/hiring-market/top-skills?city=austin"

# Test count
curl "http://localhost:3000/api/hiring-market/count?city=austin&job_family=data"
```

All should return data without errors.

---

## Deployment Checklist

Before deploying location changes to production:

- [ ] **Backend:**
  - [ ] Updated `config/location_mapping.yaml` with new location
  - [ ] Tested location extraction with `test_location_extractor.py`
  - [ ] Validated JSONB queries return correct results
  - [ ] Ran pipeline to collect data for new location

- [ ] **Frontend:**
  - [ ] Updated `lib/location-queries.ts` with new city/country/region
  - [ ] Updated `GlobalFilters.tsx` dropdown options
  - [ ] Updated description text in `GlobalFilters.tsx` and `layout.tsx`
  - [ ] Tested UI filtering in local dev environment
  - [ ] Verified API routes return data for new location

- [ ] **Documentation:**
  - [ ] Updated `CLAUDE.md` if significant architectural changes
  - [ ] Updated `GLOBAL_LOCATION_EXPANSION_EPIC.md` status

- [ ] **Deployment:**
  - [ ] Commit changes to both repositories
  - [ ] Push to GitHub
  - [ ] Verify Vercel deployment succeeds
  - [ ] Test live site with new location
  - [ ] Monitor for errors in production logs

---

## Example: Adding Berlin

Here's a complete example of adding Berlin, Germany:

### 1. Backend Changes

**`config/location_mapping.yaml`:**
```yaml
cities:
  berlin:
    country_code: DE
    display_name: Berlin
    patterns:
      - berlin
      - berlin, germany
      - berlin, de

countries:
  DE:
    display_name: Germany
    aliases: [deutschland]

regions:
  EMEA:
    display_name: Europe, Middle East & Africa
    patterns:
      - emea
      - europe
    countries: [GB, DE, NL, IE, SE]  # DE already in list

adzuna_endpoints:
  DE:
    base_url: https://api.adzuna.com/v1/api/jobs/de/search
    cities:
      - berlin
```

### 2. Frontend Changes

**`portfolio-site/lib/location-queries.ts`:**
```typescript
export const SUPPORTED_CITIES = [
  'london', 'new_york', 'denver', 'san_francisco', 'singapore',
  'berlin',  // NEW
] as const;

export function getCityCountryCode(city: string): string | null {
  const cityToCountry: Record<string, string> = {
    // ... existing
    berlin: 'DE',  // NEW
  };
  return cityToCountry[city] || null;
}

export function getCityDisplayName(city: string): string {
  const displayNames: Record<string, string> = {
    // ... existing
    berlin: 'Berlin',  // NEW
  };
  return displayNames[city] || city;
}

export const COUNTRY_TO_REGION: Record<string, string> = {
  // ... existing
  DE: 'EMEA',  // NEW
};
```

**`portfolio-site/app/projects/hiring-market/components/GlobalFilters.tsx`:**
```typescript
options={[
  { value: 'all', label: 'All Locations' },
  { value: 'london', label: 'London' },
  { value: 'new_york', label: 'New York City' },
  { value: 'denver', label: 'Denver' },
  { value: 'san_francisco', label: 'San Francisco' },
  { value: 'singapore', label: 'Singapore' },
  { value: 'berlin', label: 'Berlin' },  // NEW
]}
```

### 3. Test & Deploy

```bash
# Test backend
cd "C:\Cursor Projects\job-analytics"
pytest tests/test_location_extractor.py::test_berlin_extraction -v

# Test frontend
cd "C:\Cursor Projects\portfolio-site"
npm run dev
# Visit http://localhost:3000/projects/hiring-market and select Berlin

# Deploy
git add .
git commit -m "Add Berlin as new location"
git push
```

---

## Troubleshooting

**Location not extracted correctly:**
- Check pattern matching is case-insensitive
- Verify patterns are in lowercase in YAML
- Test with `pipeline/location_extractor.py` directly

**Frontend filter returns no data:**
- Verify inclusive filtering logic includes all relevant job types
- Check API routes are using `applyLocationFilter()` correctly
- Validate JSONB query syntax with direct Supabase query

**Dropdown not showing new city:**
- Clear browser cache
- Check GlobalFilters.tsx has new option
- Verify TypeScript compilation succeeded (no type errors)

---

## Future Enhancements

**Potential improvements to location system:**
- Multi-city filtering: `?city=london,berlin` (already supported via comma-separated values)
- Country-level dashboards: dedicated views for "All US jobs" or "All EMEA jobs"
- Regional comparisons: side-by-side charts comparing AMER vs EMEA vs APAC
- Location autocomplete: typeahead search for cities instead of dropdown

---

**Last Updated:** 2025-12-22
**Author:** Claude Code
**Status:** Operational - ready for future location expansion
