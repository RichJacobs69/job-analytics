# Epic: Employer Metadata System

**Status:** Planned
**Priority:** Medium
**Complexity:** Low-Moderate
**Estimated Effort:** 3-4 development sessions

## Problem Statement

Employer-level attributes are currently stored per-job in `enriched_jobs`, causing:

1. **Inconsistent Classifications**: Same employer receives different `employer_size` values across jobs
   - Example: Braze has 20 jobs as "scaleup" and 9 as "enterprise" (should be enterprise - public company, 1700 employees)
2. **No Single Source of Truth**: Employer attributes repeated across N job rows
3. **Name Variation Issues**: Case differences (e.g., "Figma" vs "figma") treated as separate entities
4. **No Home for Company Data**: Nowhere to store ownership type, HQ location, industry, etc.

### Example Data Quality Issues

From production query (2025-12-30):
```
| employer_name | employer_sizes                     | jobs |
|---------------|-----------------------------------|------|
| Braze         | ["scaleup", "enterprise"]          | 29   |
| Coinbase      | ["enterprise","scaleup","startup"] | 15   |
```

**Root Cause:** LLM classifies employer_size per-job with no memory of previous classifications.

## Proposed Solution: Employer Metadata Table

### Architecture

```
enriched_jobs                     employer_metadata
+------------------+              +----------------------+
| employer_name ---|------------->| canonical_name (PK)  |
| title_display    |              | aliases TEXT[]       |
| job_family       |              | display_name         |
| employer_size    | (deprecated) | employer_size        |
| ...              |              | size_source          |
+------------------+              | ownership_type       |
                                  | hq_city              |
                                  | hq_country_code      |
                                  +----------------------+

employer_fill_stats (unchanged - temporal metrics only)
+----------------------+
| employer_name (PK)   |
| median_days_to_fill  |
| sample_size          |
| computed_at          |
+----------------------+
```

**Key Design Decisions:**
- Single `employer_metadata` table (not separate canonical + aliases tables)
- Aliases stored as `TEXT[]` array (simpler than separate table for ~7 current variations)
- `employer_fill_stats` remains separate (temporal metrics vs static attributes)
- JOIN via `canonical_name` or `ANY(aliases)` lookup

### Database Schema

```sql
CREATE TABLE employer_metadata (
    -- Identity
    canonical_name TEXT PRIMARY KEY,      -- Normalized lookup key (lowercase)
    aliases TEXT[] DEFAULT '{}',          -- Name variations: ['Figma', 'figma', 'FIGMA']
    display_name TEXT NOT NULL,           -- Pretty display version: 'Figma'

    -- Classification (Phase 1)
    employer_size TEXT CHECK (employer_size IN ('startup', 'scaleup', 'enterprise')),
    size_source TEXT DEFAULT 'llm_majority',  -- llm_majority/manual/external

    -- Company Info (Future phases)
    ownership_type TEXT,                  -- public/private/nonprofit
    hq_city TEXT,
    hq_country_code TEXT,
    industry TEXT,
    employee_count_range TEXT,            -- e.g., "1000-5000"

    -- Tracking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for alias lookups
CREATE INDEX idx_employer_aliases ON employer_metadata USING GIN (aliases);

-- Index for size filtering
CREATE INDEX idx_employer_size ON employer_metadata (employer_size);

COMMENT ON TABLE employer_metadata IS 'Canonical employer attributes. Single source of truth for company-level data.';
COMMENT ON COLUMN employer_metadata.canonical_name IS 'Normalized lowercase name used as lookup key';
COMMENT ON COLUMN employer_metadata.aliases IS 'All known name variations including original case variants';
COMMENT ON COLUMN employer_metadata.size_source IS 'How size was determined: llm_majority (seeded from jobs), manual (human override), external (API)';
```

### Query Patterns

**Lookup employer by name (handles variations):**
```sql
SELECT * FROM employer_metadata
WHERE canonical_name = lower('Figma')
   OR 'Figma' = ANY(aliases);
```

**Join with enriched_jobs:**
```sql
SELECT
    ej.title_display,
    ej.employer_name,
    em.employer_size,
    em.display_name
FROM enriched_jobs ej
LEFT JOIN employer_metadata em
    ON lower(ej.employer_name) = em.canonical_name
    OR ej.employer_name = ANY(em.aliases);
```

**Combined employer context (with fill stats):**
```sql
SELECT
    em.display_name,
    em.employer_size,
    em.ownership_type,
    em.hq_city,
    efs.median_days_to_fill
FROM employer_metadata em
LEFT JOIN employer_fill_stats efs ON em.canonical_name = lower(efs.employer_name);
```

## Implementation Plan

### Session 1: Schema & Seeding Script

**Goal:** Create table and seed from existing data

- [ ] Create migration: `migrations/011_create_employer_metadata.sql`
- [ ] Run migration in Supabase
- [ ] Write seeding script: `pipeline/utilities/seed_employer_metadata.py`
  - Query distinct employer_name from enriched_jobs
  - Group by lowercase to identify variations
  - Use majority vote for employer_size
  - Insert into employer_metadata with aliases array
- [ ] Run seeding script
- [ ] Verify: all employers mapped, variations handled

**Seeding Logic:**
```python
# For each unique lowercase employer name:
# 1. Collect all case variations as aliases
# 2. Pick most common employer_size (majority vote)
# 3. Use most common original casing as display_name
# 4. Insert with canonical_name = lowercase version
```

**Success Criteria:**
- All ~400+ employers have metadata rows
- 7 known variations have proper aliases
- No duplicate canonical_names

### Session 2: Pipeline Integration

**Goal:** Update classification pipeline to use employer_metadata

- [ ] Update `classifier.py` to check employer_metadata before LLM classification
- [ ] If employer exists: use cached size, skip LLM employer_size extraction
- [ ] If new employer: classify with LLM, insert into employer_metadata
- [ ] Add logging for cache hits vs new employers
- [ ] Test on batch of 50 jobs

**Success Criteria:**
- Existing employers get consistent size from metadata
- New employers get classified and cached
- Cache hit rate logged

### Session 3: Manual Overrides & Maintenance

**Goal:** Tools for data quality management

- [ ] Create admin script: `pipeline/utilities/manage_employer_metadata.py`
  - List employers by size
  - Update employer size (with reason)
  - Add aliases
  - Merge duplicate employers
- [ ] Fix known issues:
  - Braze: set to 'enterprise', size_source='manual'
  - Other public companies: verify correct size
- [ ] Document maintenance procedures

**Success Criteria:**
- Admin can fix any employer via script
- Known issues resolved
- Process documented

### Session 4+ (Future): Extended Metadata Fields

**Goal:** Expand employer data as needed

Potential fields to add:
- `ownership_type`: public/private/nonprofit (useful for filtering)
- `hq_city`, `hq_country_code`: company headquarters
- `industry`: tech/fintech/healthcare/etc.
- `employee_count_range`: "50-200", "1000-5000", etc.

Each field follows same pattern:
1. Add column to employer_metadata
2. Seed from external source or manual entry
3. Expose in API/dashboard as needed

## Benefits

| Benefit | Impact |
|---------|--------|
| Consistency | Same employer = same size, always |
| Single source of truth | Update once, applies everywhere |
| Extensibility | Easy to add ownership, HQ, industry |
| Query simplicity | JOIN once, get all employer context |
| Cost savings | Skip LLM for known employers (~80% cache hit) |

## Migration Path for enriched_jobs.employer_size

**Phase 1 (Now):** Keep `enriched_jobs.employer_size` populated (denormalized)
- Pipeline writes to both tables
- Queries can use either source
- No breaking changes

**Phase 2 (Later):** Deprecate per-job employer_size
- Queries migrate to JOIN with employer_metadata
- Stop writing to enriched_jobs.employer_size
- Column becomes historical artifact

**Phase 3 (Eventually):** Remove column
- Drop enriched_jobs.employer_size
- All queries use employer_metadata

## Alternatives Considered

| Approach | Verdict | Reason |
|----------|---------|--------|
| Add to employer_fill_stats | Rejected | Different concerns (temporal vs static), wrong table purpose |
| Separate employer_canonical + employer_aliases tables | Rejected | Over-engineering for ~7 name variations |
| External API (Clearbit, LinkedIn) | Deferred | Cost, complexity - consider for premium tier |
| Pure manual mapping | Rejected | Doesn't scale to new employers |

## Success Metrics

**Data Quality:**
- Zero employers with multiple size classifications (post-implementation)
- 100% of employers resolve to canonical metadata

**Performance:**
- Cache hit rate >= 80% on classifications
- Lookup latency < 50ms

**Maintainability:**
- < 1 hour/month manual maintenance
- Admin scripts functional

## Related Epics

- **Experience Range Normalization**: Moved to separate epic (different scope/complexity)
- **Job Feed (Epic 8)**: Uses employer_fill_stats for temporal metrics

---

**Document Version:** 2.0
**Last Updated:** 2025-12-30
**Previous Version:** employer_size_canonicalization_epic.md v1.0
**Architecture Review:** 2025-12-30 (simplified schema based on YAGNI principle)
**Status:** Planned - ready for implementation
