# Bug: US Remote Jobs Appearing in London Filter

## Issue

Waymo job (https://careers.withwaymo.com/jobs/fleet-response-training-program-manager-mountain-view-california-united-states-phoenix-arizona-san-francisco?gh_jid=7435632) appears in London job feed despite being US-only remote.

## Root Cause

Job has locations:
```json
[
  {"type": "city", "country_code": "US", "city": "mountain_view"},
  {"type": "city", "country_code": "US", "city": "phoenix"},
  {"type": "city", "country_code": "US", "city": "san_francisco"},
  {"type": "remote", "scope": "country", "country_code": "US"}
]
```

The API is including **all** remote jobs regardless of their country scope. It should only include:
- Global remote (`scope: "global"`)
- Country-scoped remote matching the selected city's country

## Fix Location

**File:** `portfolio-site/app/api/hiring-market/jobs/feed/route.ts` (or wherever the feed API is)

## Implementation

### Step 1: Add Country Mapping

```typescript
// Map city codes to country codes
const CITY_TO_COUNTRY: Record<string, string> = {
  'lon': 'GB',
  'nyc': 'US',
  'den': 'US',
  'sf': 'US',
  'sing': 'SG'
  // Add any other cities as needed
};
```

### Step 2: Add Post-Filter Function

Add this function after fetching jobs from Supabase:

```typescript
function matchesLocationFilter(job: any, selectedCities: string[]): boolean {
  if (!job.locations || !Array.isArray(job.locations)) {
    return false;
  }

  // Get country codes for selected cities
  const selectedCountries = selectedCities.map(city => CITY_TO_COUNTRY[city]);

  return job.locations.some((loc: any) => {
    // Match exact city
    if (loc.type === 'city' && selectedCities.includes(loc.city)) {
      return true;
    }

    // Match global remote
    if (loc.type === 'remote' && loc.scope === 'global') {
      return true;
    }

    // Match country-scoped remote (must match selected city's country)
    if (loc.type === 'remote' && loc.scope === 'country') {
      return selectedCountries.includes(loc.country_code);
    }

    return false;
  });
}
```

### Step 3: Apply Filter

After fetching jobs from Supabase, before grouping:

```typescript
// Fetch jobs from Supabase
const { data: jobs, error } = await supabase
  .from('jobs_with_employer_context')
  .select('*')
  // ... other filters ...
  .execute();

// POST-FILTER: Remove wrong-country remote jobs
const filteredJobs = jobs.filter(job =>
  matchesLocationFilter(job, selectedCities)
);

// Continue with grouping logic using filteredJobs
const groups = {
  remote_friendly: filteredJobs.filter(/* ... */),
  fresh_matches: filteredJobs.filter(/* ... */),
  // ... etc
};
```

## Why This Bug Exists

From EPIC_JOB_FEED.md:
> **Post-filter for country-scoped remote** | PostgREST can't do multi-key JSONB in OR; filter in application layer

PostgREST (Supabase) cannot filter JSONB arrays with complex OR conditions, so we must filter in the application layer. This post-filter was documented as needed but may not have been implemented or is missing the country-scope check.

## Testing

Test cases to verify:

1. **London filter** should show:
   - ✅ Jobs with London city location
   - ✅ Jobs with `{"type": "remote", "scope": "global"}`
   - ✅ Jobs with `{"type": "remote", "scope": "country", "country_code": "GB"}`
   - ❌ Jobs with `{"type": "remote", "scope": "country", "country_code": "US"}`

2. **NYC filter** should show:
   - ✅ Jobs with NYC city location
   - ✅ Jobs with `{"type": "remote", "scope": "global"}`
   - ✅ Jobs with `{"type": "remote", "scope": "country", "country_code": "US"}`
   - ❌ Jobs with `{"type": "remote", "scope": "country", "country_code": "GB"}`

3. **Multi-city filter (e.g., London + NYC)** should show:
   - ✅ Jobs with either London OR NYC city location
   - ✅ Jobs with `{"type": "remote", "scope": "global"}`
   - ✅ Jobs with `{"type": "remote", "scope": "country", "country_code": "GB"}` OR `"US"`
   - ❌ Jobs with `{"type": "remote", "scope": "country", "country_code": "SG"}`

## Example Jobs to Test With

**After fix, this Waymo job should NOT appear in London filter:**
- URL: https://careers.withwaymo.com/jobs/fleet-response-training-program-manager-mountain-view-california-united-states-phoenix-arizona-san-francisco?gh_jid=7435632
- Locations: US cities + US-scoped remote
- Should appear in: NYC, Denver, SF filters
- Should NOT appear in: London, Singapore filters

## Quick Validation Query

You can test the logic with this SQL query in Supabase:

```sql
-- Find jobs with US-scoped remote that might leak into London filter
SELECT
  id,
  title,
  employer_name,
  locations
FROM enriched_jobs
WHERE
  locations @> '[{"type": "remote", "scope": "country", "country_code": "US"}]'::jsonb
  AND NOT locations @> '[{"type": "city", "country_code": "GB"}]'::jsonb
LIMIT 20;
```

These jobs should NOT appear when filtering by London.
