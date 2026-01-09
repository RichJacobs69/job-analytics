# Bug: Remote Scope Misclassification

## Issue

Jobs with country/region-specific remote eligibility are being classified as **global remote** when location restrictions are only mentioned in the job description, not the location field.

**Example:**
- Instacart job: https://instacart.careers/job/?gh_jid=7406756
- Stored in DB as: `[{"type":"remote","scope":"global"}]`
- Description says: "Currently, we are only hiring in the following provinces: Ontario, Alberta, British Columbia, and Nova Scotia."
- **Should be:** `[{"type":"remote","scope":"country","country_code":"CA"}]` (or region-level)

## Root Cause

### Current Location Extraction Flow

From `pipeline/fetch_jobs.py` (lines 539, 919, 1241, 1610, 2003):

```python
extracted_locations = extract_locations(greenhouse_location)
# Only passes the location field string
# description_text parameter exists but is never used
```

### Location Extractor Logic (`pipeline/location_extractor.py`)

When location field contains just **"Remote"** (no co-located cities):

1. Line 278: Defaults to `{'type': 'remote', 'scope': 'global'}`
2. Lines 433-444: Scope inference only works if there are **co-located cities** in the same location string (e.g., "San Francisco or Remote" → infers US scope)
3. **description_text parameter exists but has no implementation** - it's accepted but never scanned

### Why This Fails

| Location Field | Description | Current Classification | Should Be |
|----------------|-------------|------------------------|-----------|
| "Remote" | "Must be authorized to work in the US" | Global | US country |
| "Remote" | "Only hiring in Ontario, Alberta, BC, Nova Scotia" | Global | Canada country |
| "Remote" | "Available in all 50 states" | Global | US country |
| "Remote" | "EU-based candidates only" | Global | Region (EMEA) |
| "NYC or Remote" | "Must be authorized to work in the US" | US country (inferred from NYC) | US country ✓ |

The inference works when cities are present, but fails when location field is just "Remote".

## Impact

**Database query to estimate scale:**

```sql
-- Find global remote jobs that might be mis-scoped
SELECT
  id,
  employer_name,
  title,
  locations,
  LEFT(description, 200) as description_snippet
FROM enriched_jobs
WHERE
  locations = '[{"type":"remote","scope":"global"}]'::jsonb
  AND (
    description ILIKE '%authorized to work in the%'
    OR description ILIKE '%must be based in%'
    OR description ILIKE '%only hiring in%'
    OR description ILIKE '%available in%'
    OR description ILIKE '%50 states%'
    OR description ILIKE '%US residents%'
    OR description ILIKE '%EU only%'
    OR description ILIKE '%provinces:%'
  )
LIMIT 100;
```

This will show how many "global" remote jobs actually have location restrictions buried in the description.

## Common Patterns to Detect

### US-scoped indicators:
- "authorized to work in the US"
- "US-based remote"
- "available in all 50 states"
- "must be based in the United States"
- "US residents only"
- "not available outside the US"
- "must have US work authorization"

### Canada-scoped indicators:
- "only hiring in the following provinces:"
- "available in: Ontario, Alberta, BC"
- "Canadian residents"
- "authorized to work in Canada"

### UK-scoped indicators:
- "UK-based remote"
- "must have right to work in the UK"
- "UK residents only"

### EU/EMEA-scoped indicators:
- "EU-based candidates only"
- "EMEA region"
- "European Union work authorization"

### Global confirmations (these ARE truly global):
- "work from anywhere"
- "no location restrictions"
- "global remote position"
- "hire in 50+ countries"

## Proposed Solutions

### Option 1: Enhance Location Extractor (Recommended)

**File:** `pipeline/location_extractor.py`

Add a new function:

```python
def infer_scope_from_description(description: str) -> Optional[Dict]:
    """
    Scan job description for country/region-specific eligibility phrases.

    Returns:
        Location dict with inferred scope if found, None otherwise
    """
    if not description:
        return None

    desc_lower = description.lower()

    # US-scoped patterns
    us_patterns = [
        'authorized to work in the us',
        'us-based remote',
        'all 50 states',
        'us residents only',
        'must be based in the united states',
        'us work authorization'
    ]
    if any(pattern in desc_lower for pattern in us_patterns):
        return {'type': 'remote', 'scope': 'country', 'country_code': 'US'}

    # Canada-scoped patterns
    ca_patterns = [
        'only hiring in the following provinces',
        'canadian residents',
        'authorized to work in canada',
        'provinces: ontario'  # Common pattern
    ]
    if any(pattern in desc_lower for pattern in ca_patterns):
        return {'type': 'remote', 'scope': 'country', 'country_code': 'CA'}

    # UK-scoped patterns
    uk_patterns = [
        'uk-based remote',
        'right to work in the uk',
        'uk residents only'
    ]
    if any(pattern in desc_lower for pattern in uk_patterns):
        return {'type': 'remote', 'scope': 'country', 'country_code': 'GB'}

    # EU/EMEA-scoped patterns
    eu_patterns = [
        'eu-based candidates',
        'emea region',
        'european union work authorization'
    ]
    if any(pattern in desc_lower for pattern in eu_patterns):
        return {'type': 'remote', 'scope': 'region', 'region': 'EMEA'}

    return None
```

**Then update `extract_locations()` function (around line 432):**

```python
# After co-located city inference, before deduplication:

# If we still have unscoped global remote, check description
if description_text:
    has_unscoped_global = any(
        loc.get("type") == "remote" and loc.get("scope") == "global"
        for loc in locations
    )

    if has_unscoped_global:
        inferred_scope = infer_scope_from_description(description_text)
        if inferred_scope:
            # Replace global remote with scoped remote
            locations = [
                inferred_scope if (loc.get("type") == "remote" and loc.get("scope") == "global")
                else loc
                for loc in locations
            ]
```

**Then update `fetch_jobs.py` to pass description:**

```python
# Greenhouse (line 539)
extracted_locations = extract_locations(
    greenhouse_location,
    description_text=job.description
)

# Lever (line 1241)
extracted_locations = extract_locations(
    lever_location,
    description_text=job.description
)

# Ashby (line 1610)
extracted_locations = extract_locations(
    ashby_location,
    description_text=job.description
)

# Workable (line 2003)
extracted_locations = extract_locations(
    workable_location,
    description_text=job.description
)
```

### Option 2: Backfill Script

Create `pipeline/utilities/fix_remote_scope.py`:

```python
#!/usr/bin/env python3
"""
Backfill script to re-classify global remote jobs that have country-specific restrictions.

Usage:
    python pipeline/utilities/fix_remote_scope.py --dry-run
    python pipeline/utilities/fix_remote_scope.py --limit=100
"""

import argparse
from pipeline.db_connection import SupabaseConnection
from pipeline.location_extractor import infer_scope_from_description  # After implementing

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()

    db = SupabaseConnection()
    supabase = db.supabase

    # Find global remote jobs
    offset = 0
    fixed_count = 0

    while True:
        result = supabase.table('enriched_jobs').select('*').eq(
            'locations',
            '[{"type":"remote","scope":"global"}]'
        ).offset(offset).limit(1000).execute()

        if not result.data:
            break

        for job in result.data:
            description = job.get('description', '')
            inferred = infer_scope_from_description(description)

            if inferred:
                print(f"Job {job['id']} ({job['employer_name']} - {job['title']})")
                print(f"  Current: global")
                print(f"  Inferred: {inferred}")

                if not args.dry_run:
                    supabase.table('enriched_jobs').update({
                        'locations': [inferred]
                    }).eq('id', job['id']).execute()
                    print(f"  [UPDATED]")

                fixed_count += 1

                if args.limit and fixed_count >= args.limit:
                    break

        if args.limit and fixed_count >= args.limit:
            break

        offset += 1000

    print(f"\nTotal jobs {'would be' if args.dry_run else ''} fixed: {fixed_count}")

if __name__ == '__main__':
    main()
```

## Testing Strategy

### Unit Tests

Add to `tests/test_location_extractor.py`:

```python
def test_infer_us_scope_from_description():
    """Test: 'Remote' + US authorization phrase -> US country scope"""
    description = "This is a remote role. Must be authorized to work in the US."
    result = extract_locations("Remote", description_text=description)

    assert len(result) == 1
    assert result[0] == {
        "type": "remote",
        "scope": "country",
        "country_code": "US"
    }

def test_infer_canada_scope_from_description():
    """Test: 'Remote' + Canadian provinces -> CA country scope"""
    description = "Currently, we are only hiring in the following provinces: Ontario, Alberta, British Columbia, and Nova Scotia."
    result = extract_locations("Remote", description_text=description)

    assert len(result) == 1
    assert result[0] == {
        "type": "remote",
        "scope": "country",
        "country_code": "CA"
    }

def test_global_remote_without_restrictions():
    """Test: 'Remote' with no description restrictions -> stays global"""
    description = "Join our distributed team working from anywhere."
    result = extract_locations("Remote", description_text=description)

    assert len(result) == 1
    assert result[0] == {
        "type": "remote",
        "scope": "global"
    }

def test_city_overrides_description():
    """Test: 'NYC or Remote' with US phrase -> US scope (city inference wins)"""
    description = "Must be authorized to work in the US."
    result = extract_locations("NYC or Remote", description_text=description)

    # Should have NYC city + US remote (inferred from city, not description)
    assert len(result) == 2
    assert any(loc.get('city') == 'new_york' for loc in result)
    assert any(loc.get('scope') == 'country' and loc.get('country_code') == 'US' for loc in result)
```

### Integration Test

Run on staging/dev Supabase first:

```bash
# Dry run to see what would be fixed
python pipeline/utilities/fix_remote_scope.py --dry-run --limit=100

# Review output, then apply to small batch
python pipeline/utilities/fix_remote_scope.py --limit=10

# Check results in Supabase, then scale up
python pipeline/utilities/fix_remote_scope.py
```

## Deployment Plan

1. **Phase 1: Implement description scanning** (1-2 days)
   - Add `infer_scope_from_description()` to `location_extractor.py`
   - Update `extract_locations()` to use description inference
   - Update `fetch_jobs.py` to pass `description_text`
   - Write unit tests

2. **Phase 2: Backfill existing data** (1 day)
   - Write backfill script
   - Test on staging
   - Run dry-run on production to estimate scale
   - Execute backfill in batches

3. **Phase 3: Verify job feed** (1 hour)
   - Check that Instacart job no longer appears in London filter
   - Verify no false positives (truly global jobs mis-classified)

## Open Questions

1. **Should we create region-level scope for Canadian provinces?**
   - Current: `{"scope": "country", "country_code": "CA"}`
   - Alternative: `{"scope": "region", "country_code": "CA", "provinces": ["ON", "AB", "BC", "NS"]}`
   - Recommendation: Start with country-level for simplicity

2. **How to handle ambiguous phrases?**
   - "Remote - US preferred" → Is this US-only or global with preference?
   - Recommendation: Conservative approach - only re-scope on clear restrictions

3. **What about multi-country remote?**
   - "Remote in US and Canada" → Two country-scoped entries or custom scope?
   - Recommendation: Store as array: `[{"type": "remote", "scope": "country", "country_code": "US"}, {"type": "remote", "scope": "country", "country_code": "CA"}]`

## Success Metrics

After implementation:

1. **Zero false globals**: No jobs with clear country restrictions classified as global
2. **Backfill coverage**: % of mis-scoped jobs fixed (measure before/after with SQL query above)
3. **Feed accuracy**: No US/CA-only jobs showing in London filter
4. **No false positives**: Truly global jobs still classified as global

## Related Issues

- TEMP_LOCATION_FILTER_BUG_FIX.md - API post-filter for country-scoped remote (separate issue)
- docs/architecture/ADDING_NEW_LOCATIONS.md - Location system documentation
- pipeline/location_extractor.py:433-444 - Existing city-based scope inference (works well)
