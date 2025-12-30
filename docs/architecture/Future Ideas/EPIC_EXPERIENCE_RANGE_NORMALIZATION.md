# Epic: Experience Range Normalization

**Status:** Planned
**Priority:** Low
**Complexity:** Moderate
**Estimated Effort:** 4-5 development sessions
**Entity:** Job-level (enriched_jobs)

## Problem Statement

The `experience_range` field in `enriched_jobs` has severe data quality issues:

1. **90% Null Rate**: 5,090 out of 5,629 enriched jobs (90.4%) have no experience_range data
2. **Massive Format Inconsistency**: 90+ different formats in the 10% that exists:
   - `5+ years` vs `5 years` vs `>3 years` vs `Greater than 3 years`
   - `3-5 years` vs `3-5+ years` vs `5-7+ years` (inconsistent upper bound notation)
   - `6 months` vs `6-month` vs `6-month contract` vs `6 months-1 year` (unit chaos)
   - Case variations: `18 Months` vs `18 months`
3. **Unmeasurable Extraction Quality**: Free-form string with no validation
4. **Unusable for Analytics**: Can't group, bin, or aggregate across 90+ formats

**Design Note**: Field was left as free-form string to "preserve flexibility," but resulted in data that's neither flexible nor usable.

### Example Data Quality Issues

```
| experience_range         | count |
|-------------------------|-------|
| 5+ years                | 45    |
| 5 years                 | 23    |
| >3 years                | 18    |
| Greater than 3 years    | 12    |
| 3-5 years               | 34    |
| 3-5+ years              | 8     |
| 6 months                | 15    |
| 6-month contract        | 7     |
... (90+ more variants)
```

## Proposed Solution: Two-Tier Normalization

### Approach

```
Raw LLM Output              Normalized Form           Analytics Bucket
+-----------------------+   +------------------+     +----------------+
| "5+ years"            |-->| min: 5, max: null|---->| senior         |
| ">3 years"            |-->| min: 3, max: null|---->| mid            |
| "3-5 years"           |-->| min: 3, max: 5   |---->| mid            |
| "Greater than 3"      |-->| min: 3, max: null|---->| mid            |
+-----------------------+   +------------------+     +----------------+
```

**Tier 1**: Normalize raw extraction to structured form (min_years, max_years)
**Tier 2**: Map to seniority-aligned buckets for analytics

### Database Schema Changes

Add columns to `enriched_jobs`:
```sql
ALTER TABLE enriched_jobs ADD COLUMN experience_min_years DECIMAL(4,1);
ALTER TABLE enriched_jobs ADD COLUMN experience_max_years DECIMAL(4,1);
ALTER TABLE enriched_jobs ADD COLUMN experience_bucket TEXT
    CHECK (experience_bucket IN ('entry', 'junior', 'mid', 'senior', 'staff_principal'));

COMMENT ON COLUMN enriched_jobs.experience_min_years IS 'Normalized minimum years from experience_range';
COMMENT ON COLUMN enriched_jobs.experience_max_years IS 'Normalized maximum years (null for open-ended like 5+)';
COMMENT ON COLUMN enriched_jobs.experience_bucket IS 'Seniority-aligned bucket for analytics grouping';
```

### Mapping Reference Table

```sql
CREATE TABLE experience_range_mappings (
    id SERIAL PRIMARY KEY,
    pattern TEXT NOT NULL,              -- Regex pattern to match raw formats
    min_years DECIMAL(4,1),
    max_years DECIMAL(4,1),
    bucket TEXT,
    confidence FLOAT DEFAULT 0.9,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Seed with known patterns
INSERT INTO experience_range_mappings (pattern, min_years, max_years, bucket, notes) VALUES
('^\s*(\d+)\+?\s*years?\s*$', NULL, NULL, NULL, 'N+ years - extract N as min'),
('^\s*>\s*(\d+)\s*years?\s*$', NULL, NULL, NULL, '>N years - extract N as min'),
('^\s*(\d+)\s*-\s*(\d+)\s*years?\s*$', NULL, NULL, NULL, 'N-M years - extract range'),
-- ... more patterns
;
```

### Bucket Definitions

| Bucket | Years Range | Typical Seniority |
|--------|-------------|-------------------|
| entry | 0-1 | Intern, New Grad |
| junior | 1-3 | Junior, Associate |
| mid | 3-5 | Mid-level |
| senior | 5-8 | Senior |
| staff_principal | 8+ | Staff, Principal, Director |

## Implementation Plan

### Session 1: Pattern Analysis & Mapping Design

**Goal:** Understand all variants and design comprehensive mapping

- [ ] Query all distinct experience_range values from enriched_jobs
- [ ] Categorize into pattern groups
- [ ] Design regex patterns for each group
- [ ] Create mapping table schema
- [ ] Seed with initial patterns
- [ ] Test patterns against actual data

**Success Criteria:**
- 95%+ of observed formats have matching patterns
- Patterns documented and tested

### Session 2: Normalizer Implementation

**Goal:** Build normalization service

- [ ] Create `experience_range_normalizer.py`
  - Pattern matching logic
  - Unit conversion (months to years)
  - Confidence scoring
- [ ] Write comprehensive unit tests
- [ ] Test on sample of 100 records

```python
class ExperienceRangeNormalizer:
    """
    Normalizes experience range from 90+ format variants.

    Handles:
    - Unit conversion (months -> years)
    - Format standardization (5+ vs >5 vs Greater than 5)
    - Range parsing (5-7 years -> min: 5, max: 7)
    - Edge cases (contracts like "6-month contract")
    """

    def normalize(self, raw_text: str) -> dict:
        """
        Returns: {
            'min_years': 5.0,
            'max_years': None,  # null for open-ended
            'bucket': 'senior',
            'confidence': 0.95
        }
        """
```

**Success Criteria:**
- Normalizer handles all pattern groups
- Unit tests pass
- Confidence scoring works

### Session 3: Backfill Existing Data

**Goal:** Normalize the 10% of jobs that have experience_range

- [ ] Add new columns to enriched_jobs (migration)
- [ ] Write backfill script
- [ ] Run on 539 existing records with experience_range
- [ ] Generate report of:
  - Successfully normalized
  - Low-confidence matches
  - Unmapped formats
- [ ] Review and fix edge cases

**Success Criteria:**
- 95%+ of existing data normalized
- Low-confidence cases reviewed
- Report generated

### Session 4: Pipeline Integration

**Goal:** Normalize experience on new job classifications

- [ ] Update classifier.py to call normalizer after LLM extraction
- [ ] Store both raw and normalized forms
- [ ] Track normalization confidence
- [ ] Add validation: bucket should align with seniority field

**Success Criteria:**
- All new jobs get normalized experience
- Confidence tracked
- No classification failures

### Session 5: Analytics Integration

**Goal:** Use normalized data for reporting

- [ ] Update analytics queries to use experience_bucket
- [ ] Test grouping/aggregation queries
- [ ] Document bucket definitions for users
- [ ] Consider: deprecate raw experience_range?

**Success Criteria:**
- Analytics can answer "What experience do Senior roles require?"
- Bucket distribution makes sense

## Benefits

| Benefit | Impact |
|---------|--------|
| Queryable data | Can filter/group by experience level |
| Consistent format | No more 90+ variants |
| Analytics-ready | Bucket-based aggregation works |
| Validates LLM output | Catches extraction errors |

## Alternatives Considered

| Approach | Verdict | Reason |
|----------|---------|--------|
| Keep free-form string | Rejected | Unusable for analytics |
| Stricter LLM prompt | Tried | Still produces variants |
| Remove field entirely | Considered | Loses valuable signal |
| Use seniority as proxy | Partial | Good for 90% null cases, but loses granularity |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| New formats appear | Audit script detects unmapped, add patterns |
| Pattern too aggressive | Confidence scoring, manual review |
| Bucket alignment wrong | Cross-validate with seniority field |

## Relationship to Other Fields

**seniority** (enriched_jobs):
- Also captures experience level but differently
- experience_bucket should generally align
- Use seniority as fallback when experience_range is null (90% of cases)

**experience_range** (enriched_jobs):
- Raw LLM extraction, keep for debugging
- Will be superseded by normalized fields

---

**Document Version:** 1.0
**Last Updated:** 2025-12-30
**Extracted From:** EPIC_EMPLOYER_METADATA.md (formerly Phase 2 of employer_size_canonicalization_epic.md)
**Status:** Planned - lower priority than EPIC_EMPLOYER_METADATA
