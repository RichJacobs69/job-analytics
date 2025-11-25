# Epic 5: Analytics Query Layer - Implementation Plan

## Status
- **Epic:** 5 of 7
- **Status:** Ready to start (Epic 4 ✅ COMPLETE)
- **Goal:** Programmatically answer 35 marketplace questions from enriched job data
- **Timeline:** TBD (depends on dataset size and query complexity)

## Overview

Build `analytics.py` module that encapsulates query patterns for answering marketplace questions. Focus on SQL query functions that aggregate enriched job data from Supabase PostgreSQL.

## Dependencies

**Prerequisites:**
- ✅ Epic 4 complete (pipeline validated)
- ⏳ Dataset expansion (500-1,000 jobs needed for robust analytics)

**Data Requirements:**
- Enriched jobs table populated with classified data
- At least 500 jobs across 3 cities (lon, nyc, den)
- Multiple time periods for trend analysis (ideally 2-3 months)

## Marketplace Questions Breakdown

Total: 35 questions across 7 categories

### High Availability Questions (27) - Answer with Job Posting Data

Can be answered directly from our enriched_jobs table:

**Market Demand & Supply (5 questions):**
- MDS001: Which job subfamilies growing fastest per city?
- MDS002: Most common titles for similar roles?
- MDS004: Is demand for skill increasing/decreasing YoY?
- MDS006: When are most jobs posted (seasonal patterns)?
- MDS007: New job titles emerging this year?

**Title & Leveling Clarity (6 questions):**
- TLC001: Alternative titles for same work?
- TLC002: Years of experience for Senior vs Staff?
- TLC003: IC vs Management salary difference?
- TLC004: Skills required for seniority level?
- TLC005: Department differences (Product vs Data)?

**Skills Gap & Upskilling (6 questions):**
- SGU001: Top skills for Analytics Engineer in London?
- SGU002: Adjacent skills frequently co-mentioned?
- SGU003: Fastest-growing technical skills?
- SGU004: Skills for Senior → Staff transition?
- SGU005: Skills differ between Product/Data roles?
- SGU006: Skill demand by city?

**Work Arrangement & Location (4 questions):**
- WAL001: % of Data Engineer postings onsite/hybrid/remote?
- WAL002: Where are remote AI Engineer roles?
- WAL003: Cities with most hybrid roles?
- WAL004: Work arrangement trends over time?

**Compensation & Transparency (3 questions):**
- CT001: Salary range distribution for Data Scientist NYC?
- CT002: Most common salary ranges for PM NYC?
- CT005: Equity eligibility by role/seniority?

**Competitive Positioning (3 questions):**
- CP001: Which competitors posted most Platform PM roles in London?
- CP002: Employers hiring for my skill set in NYC?
- CP003: Most active employers per city?

### Complex Availability Questions (8) - Need Additional Data

Require data we don't capture from job postings alone:

**Market Demand & Supply:**
- MDS003: Estimated time-to-fill (need posting removal dates)
- MDS005: Employers who fill roles fastest (need hiring completion data)

**Compensation & Transparency:**
- CT003: Employers paying above/below median (need more salary data)
- CT004: Compensation differences by company size (need company metadata)

**Role Scope & Realism:**
- RSR001: Experience ranges for Senior Data roles
- RSR002: How many "hybrid" roles are truly listed?
- RSR003: Do job responsibilities match advertised title?
- RSR004: Skills asked for vs realistically needed?

**Focus for Epic 5:** Prioritize the 27 high-availability questions

## Query Pattern Categories

### 1. Time Series Aggregation
**Questions:** MDS001, MDS004, MDS006, MDS007, SGU003, WAL004

**Pattern:**
```sql
SELECT
  DATE_TRUNC('month', posted_date) AS period,
  <dimension>,
  COUNT(*) AS job_count,
  LAG(COUNT(*)) OVER (PARTITION BY <dimension> ORDER BY period) AS prev_count,
  <growth_calculation>
FROM enriched_jobs
WHERE <filters>
GROUP BY period, <dimension>
ORDER BY period DESC, <metric> DESC
```

**Example Implementation:**
```python
def get_job_growth_by_subfamily(city_code: str, lookback_months: int = 12):
    """
    Answer MDS001: Which job subfamilies are growing fastest?
    Returns monthly job counts and growth rates.
    """
    pass
```

### 2. Skill Demand Tracking
**Questions:** SGU001, SGU002, SGU003, SGU004, SGU005, SGU006, MDS004

**Pattern:**
```sql
WITH skill_occurrences AS (
  SELECT
    UNNEST(skills) AS skill_name,
    <grouping_dimension>
  FROM enriched_jobs
  WHERE <filters>
)
SELECT
  skill_name,
  COUNT(*) AS frequency,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS percentage
FROM skill_occurrences
GROUP BY skill_name, <grouping_dimension>
ORDER BY frequency DESC
```

**Example Implementation:**
```python
def get_top_skills_for_role(job_subfamily: str, city_code: str = None, top_n: int = 15):
    """
    Answer SGU001: Top skills for Analytics Engineer in London?
    Returns ranked list of skills with frequency.
    """
    pass
```

### 3. Skill Co-Occurrence Analysis
**Questions:** SGU002

**Pattern:**
```sql
WITH jobs_with_skill AS (
  SELECT job_id, skills
  FROM enriched_jobs
  WHERE <skill> = ANY(skills)
)
SELECT
  UNNEST(skills) AS co_occurring_skill,
  COUNT(*) AS frequency,
  COUNT(*) * 100.0 / (SELECT COUNT(*) FROM jobs_with_skill) AS co_occurrence_rate
FROM jobs_with_skill
WHERE UNNEST(skills) != <skill>
GROUP BY co_occurring_skill
ORDER BY frequency DESC
LIMIT 20
```

**Example Implementation:**
```python
def get_co_occurring_skills(skill_name: str, city_code: str = None, top_n: int = 20):
    """
    Answer SGU002: Adjacent skills frequently co-mentioned with Python?
    Returns skills that appear with target skill.
    """
    pass
```

### 4. Geographic Comparisons
**Questions:** MDS001, SGU006, WAL001, WAL002, WAL003, CP003

**Pattern:**
```sql
SELECT
  city_code,
  <metric>,
  COUNT(*) AS count,
  <aggregation>
FROM enriched_jobs
WHERE <filters>
GROUP BY city_code, <dimension>
ORDER BY city_code, <metric> DESC
```

**Example Implementation:**
```python
def compare_cities_by_metric(metric: str, job_subfamily: str = None):
    """
    Compare cities by any metric (working_arrangement, salary, skill demand).
    Returns breakdown by city.
    """
    pass
```

### 5. Compensation Analysis
**Questions:** CT001, CT002, CT005

**Pattern:**
```sql
SELECT
  <dimension>,
  percentile_cont(0.25) WITHIN GROUP (ORDER BY compensation.base_salary_range.min) AS p25_min,
  percentile_cont(0.50) WITHIN GROUP (ORDER BY compensation.base_salary_range.min) AS p50_min,
  percentile_cont(0.75) WITHIN GROUP (ORDER BY compensation.base_salary_range.min) AS p75_min,
  percentile_cont(0.90) WITHIN GROUP (ORDER BY compensation.base_salary_range.min) AS p90_min,
  COUNT(*) AS sample_size
FROM enriched_jobs
WHERE compensation.base_salary_range.min IS NOT NULL
  AND <filters>
GROUP BY <dimension>
ORDER BY p50_min DESC
```

**Example Implementation:**
```python
def get_salary_distribution(job_subfamily: str, city_code: str, seniority: str = None):
    """
    Answer CT001: Salary range distribution for Data Scientist NYC?
    Returns percentiles and sample size.
    """
    pass
```

### 6. Employer Activity Tracking
**Questions:** CP001, CP002, CP003

**Pattern:**
```sql
SELECT
  employer.name,
  COUNT(*) AS job_count,
  <additional_metrics>
FROM enriched_jobs
WHERE <filters>
GROUP BY employer.name
ORDER BY job_count DESC
LIMIT 20
```

**Example Implementation:**
```python
def get_top_hiring_employers(city_code: str, job_subfamily: str = None, period_days: int = 90):
    """
    Answer CP001: Which competitors posted most Platform PM roles in London?
    Returns ranked list of employers by posting volume.
    """
    pass
```

### 7. Working Arrangement Analysis
**Questions:** WAL001, WAL002, WAL003, WAL004

**Pattern:**
```sql
SELECT
  working_arrangement,
  COUNT(*) AS count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (<partition>) AS percentage
FROM enriched_jobs
WHERE <filters>
GROUP BY working_arrangement, <dimension>
ORDER BY count DESC
```

**Example Implementation:**
```python
def get_work_arrangement_distribution(job_subfamily: str = None, city_code: str = None):
    """
    Answer WAL001: % of Data Engineer postings onsite/hybrid/remote?
    Returns distribution across work arrangements.
    """
    pass
```

## Module Structure: `analytics.py`

```python
"""
Job market analytics query functions.
Answers marketplace questions from enriched job data.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from supabase import Client
from db_connection import get_supabase_client

# ============================================
# 1. Time Series & Trends
# ============================================

def get_job_growth_by_subfamily(
    city_code: str,
    lookback_months: int = 12
) -> List[Dict]:
    """MDS001: Which job subfamilies are growing fastest?"""
    pass

def get_skill_demand_trend(
    skill_name: str,
    city_code: Optional[str] = None,
    lookback_months: int = 12
) -> List[Dict]:
    """MDS004: Is demand for Python increasing/decreasing YoY?"""
    pass

def get_posting_seasonality(
    job_subfamily: Optional[str] = None
) -> Dict:
    """MDS006: When are most jobs posted (day/month patterns)?"""
    pass

# ============================================
# 2. Skills Analysis
# ============================================

def get_top_skills_for_role(
    job_subfamily: str,
    city_code: Optional[str] = None,
    top_n: int = 15
) -> List[Dict]:
    """SGU001: Top skills for Analytics Engineer in London?"""
    pass

def get_co_occurring_skills(
    skill_name: str,
    city_code: Optional[str] = None,
    top_n: int = 20
) -> List[Dict]:
    """SGU002: Adjacent skills frequently co-mentioned?"""
    pass

def get_fastest_growing_skills(
    city_code: Optional[str] = None,
    lookback_months: int = 12,
    top_n: int = 15
) -> List[Dict]:
    """SGU003: Fastest-growing technical skills?"""
    pass

# ============================================
# 3. Compensation Benchmarking
# ============================================

def get_salary_distribution(
    job_subfamily: str,
    city_code: str,
    seniority: Optional[str] = None
) -> Dict:
    """CT001: Salary range distribution for Data Scientist NYC?"""
    pass

def get_equity_eligibility_rate(
    job_subfamily: Optional[str] = None,
    seniority: Optional[str] = None
) -> Dict:
    """CT005: Equity eligibility by role/seniority?"""
    pass

# ============================================
# 4. Work Arrangements
# ============================================

def get_work_arrangement_distribution(
    job_subfamily: Optional[str] = None,
    city_code: Optional[str] = None
) -> Dict:
    """WAL001: % of Data Engineer postings onsite/hybrid/remote?"""
    pass

def find_remote_jobs_by_city(
    job_subfamily: str
) -> List[Dict]:
    """WAL002: Where are most AI Engineer roles that allow Remote work?"""
    pass

# ============================================
# 5. Employer Intelligence
# ============================================

def get_top_hiring_employers(
    city_code: str,
    job_subfamily: Optional[str] = None,
    period_days: int = 90
) -> List[Dict]:
    """CP001: Which competitors posted most Platform PM roles in London?"""
    pass

def find_employers_hiring_skill(
    skill_name: str,
    city_code: str,
    top_n: int = 20
) -> List[Dict]:
    """CP002: Employers hiring for my skill set in NYC?"""
    pass

# ============================================
# 6. Title & Leveling
# ============================================

def find_similar_titles(
    job_subfamily: str,
    top_n: int = 15
) -> List[Dict]:
    """TLC001: Alternative titles for same work?"""
    pass

def get_experience_by_seniority(
    job_subfamily: str,
    city_code: Optional[str] = None
) -> Dict:
    """TLC002: Years of experience for Senior vs Staff?"""
    pass
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
**Goal:** Basic query functions and testing framework

- [ ] Create `analytics.py` module skeleton
- [ ] Implement database connection helpers
- [ ] Add query result caching (optional, for performance)
- [ ] Create `test_analytics.py` with sample queries
- [ ] Test on small dataset (50-100 jobs)

**Deliverables:**
- `analytics.py` with 2-3 working query functions
- Test suite validating query correctness
- Query performance baseline (<5s for simple aggregations)

### Phase 2: Time Series & Trends (Week 2)
**Goal:** Answer growth/trend questions

- [ ] `get_job_growth_by_subfamily()` - MDS001
- [ ] `get_skill_demand_trend()` - MDS004
- [ ] `get_posting_seasonality()` - MDS006
- [ ] `get_fastest_growing_skills()` - SGU003

**Testing:**
- Validate month-over-month growth calculations
- Check YoY comparison logic
- Verify time period filters work correctly

### Phase 3: Skills Analysis (Week 3)
**Goal:** Answer skill-related questions

- [ ] `get_top_skills_for_role()` - SGU001
- [ ] `get_co_occurring_skills()` - SGU002
- [ ] Skills by seniority functions - SGU004
- [ ] Skills comparison across departments - SGU005

**Testing:**
- Verify skill extraction from enriched_jobs
- Check co-occurrence matrix calculations
- Validate skill frequency rankings

### Phase 4: Compensation & Work Arrangements (Week 4)
**Goal:** Answer salary and location questions

- [ ] `get_salary_distribution()` - CT001
- [ ] `get_equity_eligibility_rate()` - CT005
- [ ] `get_work_arrangement_distribution()` - WAL001
- [ ] `find_remote_jobs_by_city()` - WAL002

**Testing:**
- Validate percentile calculations
- Check null handling for missing salary data
- Verify work arrangement filters

### Phase 5: Employer Intelligence (Week 5)
**Goal:** Answer competitive positioning questions

- [ ] `get_top_hiring_employers()` - CP001
- [ ] `find_employers_hiring_skill()` - CP002
- [ ] Employer activity tracking - CP003

**Testing:**
- Validate employer ranking logic
- Check skill matching accuracy
- Verify time period filters

### Phase 6: Polish & Optimization (Week 6)
**Goal:** Performance tuning and documentation

- [ ] Add query result caching for expensive aggregations
- [ ] Create usage examples in docstrings
- [ ] Performance profiling (target: <5s for all queries)
- [ ] Add README with query catalog
- [ ] Integration with Streamlit (prep for Epic 6)

**Deliverables:**
- Complete `analytics.py` with all 27 high-priority functions
- Test suite covering all query patterns
- Performance benchmarks
- Documentation and usage examples

## Success Criteria

1. **Coverage:** Can programmatically answer 27 high-availability marketplace questions
2. **Performance:** Query latency <5s for common aggregations (stretch: <2s)
3. **Accuracy:** Results validated against manual spot-checks (100% match)
4. **Maintainability:** Query functions clearly documented with examples
5. **Scalability:** Queries perform well with 500-1,000+ job dataset

## Risks & Mitigations

### Risk 1: Insufficient Data for Trends
**Problem:** Need multiple time periods for YoY/MoM calculations

**Mitigation:**
- Run job scraping across 2-3 months before starting Epic 5
- Focus first on point-in-time questions (top skills, distributions)
- Add trend queries later as dataset grows

### Risk 2: Compensation Data Sparse
**Problem:** Only ~30% of jobs have salary info (London especially)

**Mitigation:**
- NYC/Denver focus for salary queries (pay transparency laws)
- Add sample size warnings to query results
- Consider confidence intervals for small samples

### Risk 3: Query Performance
**Problem:** Large aggregations on 1,000+ jobs may be slow

**Mitigation:**
- Add database indexes on common filter columns (city_code, job_subfamily, posted_date)
- Implement query result caching (Redis or in-memory)
- Pre-compute common aggregations (daily batch job)

### Risk 4: Schema Changes
**Problem:** Database schema may evolve, breaking queries

**Mitigation:**
- Version control analytics.py with schema version
- Add integration tests that fail if schema changes
- Use helper functions to isolate schema dependencies

## Next Steps

**Before starting Epic 5:**
1. Expand job scraping to build 500-1,000 job dataset
2. Run larger Adzuna batches across all 3 cities
3. Scrape additional Greenhouse companies for depth
4. Validate database schema matches analytics.py assumptions

**Ready to start when:**
- ✅ Epic 4 complete (DONE)
- ⏳ 500+ jobs in enriched_jobs table
- ⏳ At least 2 cities represented (lon + nyc or den)
- ⏳ Multiple posting dates for trend analysis

**First implementation task:**
Create `analytics.py` skeleton with database connection and 1-2 sample query functions

## References

- Marketplace questions: `docs/marketplace_questions.yaml`
- Database schema: `docs/database/schema_updates.md`
- SQL query examples: CLAUDE.md "Analytics Layer & Marketplace Questions" section
- Epic 6 dependency: Streamlit dashboard will consume these query functions
