# Epic: Data Standardization & Canonicalization System

**Status:** Post-Project Epic (Planned)
**Priority:** Medium
**Complexity:** Moderate
**Estimated Effort:** 8-10 development sessions (2 phases)

## Problem Statement

Multiple fields extracted by the LLM are non-deterministic, inconsistent, or in free-form formats, making them unsuitable for analytics:

### Phase 1: Employer Size Classification
Current employer size classification uses LLM-based inference for every job posting, leading to:

1. **Inconsistent Classifications**: Same employer receives different size classifications across multiple job postings
2. **Name Variation Issues**: Case differences and slight name variations (e.g., "Coinbase" vs "coinbase", "83zero Limited" vs "83zero Ltd") treated as separate entities
3. **Unnecessary LLM Costs**: Repeatedly classifying the same employer's size for each job posting
4. **Data Quality Issues**: ~170+ employers with 2-3 different size classifications in current dataset

### Phase 2: Experience Range Normalization
Current experience_range field has severe data quality issues:

1. **90% Null Rate**: 5,090 out of 5,629 enriched jobs (90.4%) have no experience_range data
2. **Massive Format Inconsistency**: 90+ different formats in the 10% that exists:
   - `5+ years` vs `5 years` vs `>3 years` vs `Greater than 3 years`
   - `3-5 years` vs `3-5+ years` vs `5-7+ years` (inconsistent upper bound notation)
   - `6 months` vs `6-month` vs `6-month contract` vs `6 months-1 year` (unit chaos)
   - Case variations: `18 Months` vs `18 months`
3. **Unmeasurable Extraction Quality**: Free-form string with no validation means garbage data impossible to detect
4. **Unusable for Analytics**: Can't group, bin, or aggregate across 90+ inconsistent formats

**Design Note**: Field was left as free-form string to "preserve flexibility," but resulted in data that's **neither flexible nor usable**. Attempted "raw data preservation" made data worse, not better. Would be more useful normalized than raw.

### Example Data Quality Issues

From production query (2025-12-15):
```
| employer_name | employer_sizes                     | num_sizes |
|---------------|-----------------------------------|-----------|
| Coinbase      | ["enterprise","scaleup","startup"] | 3         |
| coinbase      | ["enterprise","scaleup"]           | 2         |
| Confidential  | ["enterprise","scaleup","startup"] | 3         |
| anthropic     | ["scaleup","startup"]              | 2         |
```

**Root Causes:**
- Name normalization issues (case sensitivity)
- LLM non-determinism across different job postings
- Temporal inconsistency (company growth over time not reflected deterministically)

## Proposed Solution: Hybrid Canonicalization System

### Architecture Overview

```
Job Ingestion Flow:
    ↓
Normalize Employer Name
    ↓
Check Canonical Mapping Table ──→ Found? ──→ Use Cached Size
    ↓ Not Found
Fallback to LLM Classification
    ↓
Store in Canonical Table (for future reuse)
    ↓
Continue Classification Pipeline
```

### Core Components

#### 1. Database Schema

**employer_canonical table:**
```sql
CREATE TABLE employer_canonical (
  canonical_name TEXT PRIMARY KEY,
  employer_size TEXT NOT NULL CHECK (employer_size IN ('startup', 'scaleup', 'enterprise')),
  employee_count_range TEXT,  -- Optional: e.g., "1000-5000"
  last_verified TIMESTAMP DEFAULT NOW(),
  verified_by TEXT DEFAULT 'llm',  -- Options: 'llm', 'manual', 'api'
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_canonical_size ON employer_canonical(employer_size);
CREATE INDEX idx_canonical_verified ON employer_canonical(last_verified);
```

**employer_aliases table:**
```sql
CREATE TABLE employer_aliases (
  alias_name TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL REFERENCES employer_canonical(canonical_name) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT NOW(),
  created_by TEXT DEFAULT 'auto'  -- Options: 'auto', 'manual'
);

CREATE INDEX idx_aliases_canonical ON employer_aliases(canonical_name);
```

#### 2. Name Normalization Logic

**employer_normalizer.py:**
```python
import re
from typing import Optional

class EmployerNameNormalizer:
    """
    Normalizes employer names for consistent matching.
    Handles case, whitespace, legal suffixes, and common variations.
    """

    LEGAL_SUFFIXES = [
        'ltd', 'limited', 'inc', 'incorporated', 'llc', 'corp', 'corporation',
        'plc', 'gmbh', 'ag', 'sa', 'srl', 'bv', 'nv'
    ]

    @staticmethod
    def normalize(name: str) -> str:
        """
        Normalize employer name to canonical form.

        Steps:
        1. Lowercase
        2. Strip whitespace
        3. Remove legal suffixes
        4. Remove special characters except alphanumeric and spaces
        5. Collapse multiple spaces
        """
        if not name:
            return ""

        # Lowercase and strip
        normalized = name.lower().strip()

        # Remove common legal suffixes
        for suffix in EmployerNameNormalizer.LEGAL_SUFFIXES:
            pattern = rf'\b{suffix}\.?\s*$'
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)

        # Remove special characters, keep alphanumeric and spaces
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)

        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)

        return normalized.strip()

    @staticmethod
    def generate_common_aliases(canonical_name: str, original_name: str) -> list[str]:
        """
        Generate common variations of employer name.

        Returns list of likely aliases (case variants, with/without legal suffixes).
        """
        aliases = set()

        # Add original name as-is
        aliases.add(original_name.strip())

        # Add case variants
        aliases.add(original_name.lower())
        aliases.add(original_name.upper())
        aliases.add(original_name.title())

        # Add with common legal suffixes
        base = canonical_name
        for suffix in ['Ltd', 'Limited', 'Inc', 'LLC', 'Corp']:
            aliases.add(f"{base} {suffix}")
            aliases.add(f"{base.title()} {suffix}")

        return list(aliases)
```

#### 3. Canonical Mapping Service

**employer_size_service.py:**
```python
from typing import Optional
from supabase import Client
from .employer_normalizer import EmployerNameNormalizer
from .classifier import classify_employer_size_llm  # Existing LLM classifier

class EmployerSizeService:
    """
    Manages employer size classifications with caching and fallback to LLM.
    """

    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.normalizer = EmployerNameNormalizer()

    def get_employer_size(self, employer_name: str, use_llm_fallback: bool = True) -> tuple[str, str]:
        """
        Get employer size with caching strategy.

        Args:
            employer_name: Raw employer name from job posting
            use_llm_fallback: Whether to call LLM if not found in cache

        Returns:
            Tuple of (employer_size, source) where source is 'cached' or 'llm'
        """
        # Step 1: Normalize name
        normalized = self.normalizer.normalize(employer_name)

        if not normalized:
            return ('unknown', 'error')

        # Step 2: Check aliases table
        alias_result = self.supabase.table('employer_aliases')\
            .select('canonical_name')\
            .eq('alias_name', normalized)\
            .execute()

        if alias_result.data:
            canonical_name = alias_result.data[0]['canonical_name']

            # Step 3: Get size from canonical table
            canonical_result = self.supabase.table('employer_canonical')\
                .select('employer_size')\
                .eq('canonical_name', canonical_name)\
                .execute()

            if canonical_result.data:
                return (canonical_result.data[0]['employer_size'], 'cached')

        # Step 4: Fallback to LLM if enabled
        if use_llm_fallback:
            employer_size = classify_employer_size_llm(employer_name)

            # Store result for future use
            self._store_canonical_mapping(normalized, employer_name, employer_size)

            return (employer_size, 'llm')

        return ('unknown', 'not_found')

    def _store_canonical_mapping(self, canonical_name: str, original_name: str, employer_size: str):
        """
        Store new employer in canonical tables.

        Creates canonical entry and common aliases.
        """
        # Insert into canonical table (upsert)
        self.supabase.table('employer_canonical').upsert({
            'canonical_name': canonical_name,
            'employer_size': employer_size,
            'verified_by': 'llm',
            'last_verified': 'now()'
        }).execute()

        # Generate and store aliases
        aliases = self.normalizer.generate_common_aliases(canonical_name, original_name)

        for alias in aliases:
            self.supabase.table('employer_aliases').upsert({
                'alias_name': alias,
                'canonical_name': canonical_name,
                'created_by': 'auto'
            }).execute()
```

#### 4. Integration with Classification Pipeline

**Updated classifier.py:**
```python
from .employer_size_service import EmployerSizeService

def classify_job(job_data: dict, supabase_client) -> dict:
    """
    Main classification function - updated to use employer size service.
    """
    employer_size_service = EmployerSizeService(supabase_client)

    # ... existing classification logic ...

    # Replace LLM employer size classification with cached lookup
    employer_size, source = employer_size_service.get_employer_size(
        job_data.get('employer_name', '')
    )

    classification_result = {
        # ... other fields ...
        'employer_size': employer_size,
        'employer_size_source': source,  # Track whether cached or fresh LLM call
    }

    return classification_result
```

### Benefits

1. **Consistency**: Same employer always gets same size classification
2. **Cost Savings**: ~80-90% reduction in employer size LLM calls (estimated based on employer reuse patterns)
3. **Performance**: Instant lookup vs ~100-200ms LLM call
4. **Data Quality**: Eliminates name variation issues
5. **Audibility**: Track which classifications are cached vs fresh
6. **Maintainability**: Manual overrides supported via canonical table

### Cost Analysis

**Current State:**
- Every job posting: 1 LLM call for employer size
- 5,629 enriched jobs × $0.00388/job = ~$21.84 total (includes all classification)
- Employer size represents ~10-15% of classification cost ≈ $2.18-3.28

**With Canonicalization:**
- First occurrence: 1 LLM call (same cost)
- Subsequent occurrences: Database lookup (~0.001s, negligible cost)
- Estimated savings: 80-90% of employer size classification costs
- Estimated monthly savings: ~$1.75-2.95 (small but scales with volume)

**Additional Value:**
- Improved data quality (no cost to inconsistency)
- Faster classification pipeline
- Foundation for employer-level analytics

## Implementation Plan

### Phase 1: Employer Size Canonicalization

#### Phase 1a: Schema & Core Service (Session 1)
**Goal:** Create database tables and core service logic

- [ ] Create migration script for `employer_canonical` and `employer_aliases` tables
- [ ] Run migration in Supabase
- [ ] Implement `EmployerNameNormalizer` class with tests
- [ ] Implement `EmployerSizeService` class with tests
- [ ] Add integration tests (mock Supabase)

**Success Criteria:**
- All tables created successfully
- Service can normalize names consistently
- Service can store and retrieve mappings

#### Phase 1b: One-Time Backfill (Session 2)
**Goal:** Populate canonical tables from existing data

- [ ] Write backfill script: `backfill_employer_canonical.py`
  - Query all distinct `employer_name` from `enriched_jobs`
  - Group by normalized name
  - For conflicts (multiple sizes), pick most common OR flag for manual review
  - Insert into canonical tables
- [ ] Run backfill on production data
- [ ] Generate report of:
  - Total employers canonicalized
  - Conflicts requiring manual review
  - Aliases created
- [ ] Manually review and fix conflicts (Coinbase, Confidential, etc.)

**Success Criteria:**
- All existing employers mapped to canonical form
- <5% require manual conflict resolution
- Report generated with statistics

#### Phase 1c: Pipeline Integration (Session 3)
**Goal:** Update classification pipeline to use new service

- [ ] Update `classifier.py` to use `EmployerSizeService`
- [ ] Add `employer_size_source` field to `enriched_jobs` table
- [ ] Update schema to track cache hit rate
- [ ] Add logging for cache hits vs LLM calls
- [ ] Run integration tests on small batch (10-20 jobs)

**Success Criteria:**
- Classification pipeline uses cached sizes when available
- Falls back to LLM for new employers
- All jobs still classified successfully
- Cache hit rate logged and observable

#### Phase 1d: Validation & Monitoring (Session 4)
**Goal:** Validate system is working and cost savings realized

- [ ] Run pipeline on 100-200 new jobs
- [ ] Calculate cache hit rate
- [ ] Validate consistency (same employer = same size)
- [ ] Compare LLM cost before/after
- [ ] Add monitoring dashboard query:
  ```sql
  -- Cache hit rate over time
  SELECT
    DATE(created_at) as date,
    employer_size_source,
    COUNT(*) as count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY DATE(created_at)) as percentage
  FROM enriched_jobs
  WHERE created_at >= NOW() - INTERVAL '30 days'
  GROUP BY DATE(created_at), employer_size_source
  ORDER BY date DESC;
  ```

**Success Criteria:**
- Cache hit rate ≥70% on new jobs
- No classification failures
- Cost per job reduced by 10-15%
- Zero employer size conflicts in new data

#### Phase 1e: Maintenance & Enhancement (Session 5)
**Goal:** Tools for ongoing data quality management

- [ ] Create admin script: `manage_employer_canonical.py`
  - List all employers with size
  - Update employer size (with reason/notes)
  - Merge duplicate employers
  - Add new aliases manually
- [ ] Create periodic audit script:
  - Detect new potential conflicts
  - Flag employers that may have grown (startup → scaleup)
  - Suggest manual reviews
- [ ] Document maintenance procedures
- [ ] Add to automation epic for weekly audits

**Success Criteria:**
- Admin can manually fix any employer mapping
- Audit script catches data quality issues
- Process documented for future maintainers

---

### Phase 2: Experience Range Normalization

#### Phase 2a: Schema & Mapping Design (Session 6)
**Goal:** Design normalization strategy and database schema

**Approach:** Two-tier normalization:
- **Tier 1**: Normalize raw extraction to canonical forms (e.g., "84 months" → "7 years")
- **Tier 2**: Map canonical forms to seniority-aligned buckets for analytics

**Schema additions:**
```sql
CREATE TABLE experience_range_canonical (
  raw_format TEXT PRIMARY KEY,
  canonical_form TEXT NOT NULL,  -- Normalized standard form
  seniority_bucket TEXT,         -- 'junior' / 'mid' / 'senior' / 'staff_principal' / null
  min_years DECIMAL(4,1),        -- Lower bound in years
  max_years DECIMAL(4,1),        -- Upper bound in years (null for open-ended)
  created_at TIMESTAMP DEFAULT NOW(),
  notes TEXT
);

CREATE TABLE experience_range_mappings (
  id SERIAL PRIMARY KEY,
  pattern TEXT NOT NULL,         -- Regex pattern to match raw formats
  canonical_form TEXT NOT NULL,
  confidence FLOAT DEFAULT 0.9,  -- Confidence of this mapping (0-1)
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Tasks:**
- [ ] Design regex patterns for common variations (5+ years, >3 years, "Greater than 3", etc.)
- [ ] Create comprehensive mapping of 90+ observed formats
- [ ] Define seniority bucket alignment rules
- [ ] Document pattern matching strategy
- [ ] Create test fixtures with actual observed data (90+ formats)

**Success Criteria:**
- Mapping covers 95%+ of observed formats
- Clear rules for seniority alignment
- Patterns tested against actual data

#### Phase 2b: Implementation & Backfill (Session 7)
**Goal:** Build normalization service and backfill existing data

**Components:**
```python
# experience_range_normalizer.py
class ExperienceRangeNormalizer:
    """
    Normalizes experience range from 90+ format variants to canonical forms.

    Handles:
    - Unit conversion (months → years, weeks → years)
    - Format standardization (5+ vs >5 vs Greater than 5)
    - Range parsing (5-7 years → min: 5, max: 7)
    - Edge cases (contracts like "6-month contract")
    """

    def normalize(self, raw_text: str) -> dict:
        """
        Returns: {
          canonical_form: "5+ years",
          min_years: 5,
          max_years: null,
          seniority_bucket: "senior",
          confidence: 0.95
        }
        """
```

**Tasks:**
- [ ] Implement `ExperienceRangeNormalizer` with pattern matching
- [ ] Build mapping lookup with fallback patterns
- [ ] Add confidence scoring (high confidence = clear match, low = ambiguous)
- [ ] Backfill script: `backfill_experience_ranges.py`
  - Update 539 existing records (10% of dataset)
  - Flag low-confidence matches for manual review
  - Generate report of unmapped formats
- [ ] Add `experience_range_canonical` and `seniority_bucket` columns to `enriched_jobs`
- [ ] Test on sample of 100 records before full backfill

**Success Criteria:**
- ≥95% of observed formats matched with ≥0.9 confidence
- <5% flagged for manual review
- Backfill completes without errors
- Report generated with statistics

#### Phase 2c: Pipeline Integration (Session 8)
**Goal:** Update classifier to use normalized experience ranges

**Tasks:**
- [ ] Update `classifier.py` to call `ExperienceRangeNormalizer` after extraction
- [ ] Store both raw and canonical forms in database
- [ ] Track normalization confidence for quality monitoring
- [ ] Add validation: if seniority_bucket conflicts with seniority level, flag for review
- [ ] Run integration tests on new classifications

**Success Criteria:**
- All new jobs get normalized experience ranges
- Canonical form always populated (no nulls on successful matches)
- Confidence tracking implemented
- No classification failures from normalization

#### Phase 2d: Analytics Integration (Session 9)
**Goal:** Use normalized experience ranges for Epic 5 analytics

**Tasks:**
- [ ] Update analytics queries to use `seniority_bucket` instead of raw `experience_range`
- [ ] Test Epic 5 "Experience Level Distribution" question using buckets
- [ ] Create reference chart: seniority_bucket ↔ years mapping
- [ ] Add documentation explaining why we use seniority as proxy
- [ ] Remove dependency on broken experience_range field

**Success Criteria:**
- Analytics queries work without null handling for 5,629 jobs
- Seniority-based analysis replaces experience_range analysis
- Epic 5 can answer "What experience ranges are common for Senior roles?"

#### Phase 2e: Maintenance & Enhancement (Session 10)
**Goal:** Tools and processes for ongoing management

**Tasks:**
- [ ] Create admin script: `manage_experience_ranges.py`
  - Add new patterns
  - Update mappings
  - Review low-confidence matches
- [ ] Create audit script to detect new unmapped formats
- [ ] Document pattern addition process
- [ ] Set up periodic (monthly) pattern review

**Success Criteria:**
- New formats can be added easily
- Low-confidence matches reviewed regularly
- Process documented

---

## Benefits Summary

**Employer Size Canonicalization (Phase 1):**
- 100% consistency (same employer → same size)
- 80-90% reduction in employer size LLM calls
- 10-15% overall classification cost reduction

**Experience Range Normalization (Phase 2):**
- 90+ formats → 5 canonical forms
- 90% null rate → 100% coverage (normalized + bucketed)
- Enables analytics on experience requirements
- Aligns with seniority classifications for consistency

## Alternative Approaches Considered

### 1. Pure LLM Classification (Current State)
**Pros:** Simple, no additional infrastructure
**Cons:** Inconsistent, costly at scale, name variation issues
**Verdict:** ❌ Not viable long-term

### 2. External API Integration (e.g., Clearbit, LinkedIn)
**Pros:** Professional data, no LLM needed
**Cons:** $$$$ expensive, API limits, not all companies covered
**Verdict:** ⚠️ Consider for premium tier later

### 3. Pure Manual Mapping Table
**Pros:** Perfect accuracy, no LLM cost
**Cons:** Doesn't scale to new employers, high manual effort
**Verdict:** ❌ Not sustainable

### 4. Hybrid System (Proposed)
**Pros:** Scales to new employers, cost-efficient, high quality, auditable
**Cons:** Moderate implementation complexity
**Verdict:** ✅ Best balance of cost/quality/scalability

## Key Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Company growth changes size | Medium | High | Periodic review, `last_verified` timestamp, manual update process |
| Name normalization too aggressive | Medium | Low | Extensive testing on production names, manual override capability |
| Backfill conflicts unresolvable | Low | Medium | Flag for manual review, default to most common classification |
| LLM fallback still needed for long tail | Low | High | Expected behavior, system designed for this |
| Canonical table becomes stale | Medium | Medium | Automated audit script, annual review process |

## Success Metrics

**Data Quality:**
- Zero employers with multiple size classifications (post-implementation)
- 100% of employers resolve to single canonical name
- <1% manual override rate

**Performance:**
- Cache hit rate ≥70% on new job classifications
- Classification latency reduced by 10-15%
- Zero classification failures due to canonicalization

**Cost:**
- 10-15% reduction in per-job classification cost
- Employer size LLM calls reduced by 80-90%
- No increase in database costs

**Maintainability:**
- Admin scripts functional and documented
- Audit process runs weekly
- <1 hour/month manual maintenance required

## Future Enhancements (Out of Scope)

1. **External API Integration**: Use Clearbit/LinkedIn for authoritative employer data
2. **Growth Tracking**: Automatically detect when startup → scaleup based on job volume
3. **Fuzzy Matching**: Use edit distance for even better alias detection
4. **ML-Based Normalization**: Train model to predict canonical name from variations
5. **Employer Analytics**: Track which employers are hiring most aggressively

## References

- **Current issue query**: See original Supabase query showing 170+ employers with multiple sizes
- **Related systems**: Deduplication logic in `unified_job_ingester.py`
- **Existing normalization**: Limited normalization in `db_connection.py` (MD5 hashing)
- **Classification pipeline**: `classifier.py` and `schema_taxonomy.yaml`

---

**Document Version:** 1.0
**Last Updated:** 2025-12-15
**Author:** Planning session with Claude Code
**Status:** Approved for post-project implementation
