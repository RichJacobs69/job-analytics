# Hiring Market Analytics: MVP Case Study

> **Project Duration:** November 5, 2025 - December 16, 2025 (6 weeks)
> **Live Dashboard:** [richjacobs.me/projects/hiring-market](https://richjacobs.me/projects/hiring-market)
> **Repositories:** job-analytics (Python pipeline) | portfolio-site (Next.js dashboard)

---

## Executive Summary

Built an end-to-end job market intelligence platform that ingests job postings from multiple sources, enriches them using Claude AI classification, and presents actionable insights through an interactive web dashboard. The project demonstrates full-stack data engineering, LLM integration, and modern web development skills.

**Key Outcomes:**
- 5,629 job listings classified across 3 markets (London, NYC, Denver)
- 302 companies tracked via automated web scraping
- 5 interactive visualizations answering real marketplace questions
- Production-deployed dashboard with <3s load times
- Total LLM classification cost: ~$22 (at $0.00388/job)

---

## The Problem

Job seekers and employers lack accessible, data-driven insights into hiring trends:
- "Which skills are actually in demand for Data Engineers?"
- "What's the remote vs. hybrid split in my target market?"
- "Which companies are hiring most aggressively?"

Existing job boards show listings but don't aggregate intelligence. This project aimed to answer 5 key marketplace questions with real data.

---

## Timeline & Development Phases

### Phase 1: Foundation (Nov 5-14) - 10 days
**Commits:** 8 | **Focus:** Architecture & Data Model

| Date | Milestone |
|------|-----------|
| Nov 5 | Project inception: product brief, taxonomy schema, marketplace questions defined |
| Nov 6 | Schema taxonomy refinements |
| Nov 14 | v1.3: Agency detection system implemented |

**Key Decisions:**
- Chose Supabase PostgreSQL for managed database (free tier)
- Defined 35 marketplace questions to guide what to build
- Created classification taxonomy: job families, subfamilies, seniority levels, skills

**Technical Work:**
- `docs/schema_taxonomy.yaml` - Centralized classification rules
- `docs/marketplace_questions.yaml` - Business requirements as data questions
- `config/agency_blacklist.yaml` - Cost optimization via pre-filtering

---

### Phase 2: Data Pipeline (Nov 24-28) - 5 days
**Commits:** 15 | **Focus:** Dual-Source Ingestion

| Date | Milestone |
|------|-----------|
| Nov 24 | v1.4: Dual-source pipeline operational (Adzuna API + Greenhouse scraping) |
| Nov 25 | Epic 4 Complete: Cost tracking + economic validation |
| Nov 26 | Test suite complete: 39 automated tests for title filtering |
| Nov 27 | Greenhouse scraper enhanced with embed URL support |
| Nov 28 | First production run: 109 companies, 3,913 jobs scraped |

**Key Achievements:**
- **Adzuna Integration:** Paginated API client with rate limiting
- **Greenhouse Scraper:** Playwright-based browser automation for 302 companies
- **Unified Ingester:** MD5 deduplication, source prioritization (Greenhouse > Adzuna)
- **Cost Validation:** Measured $0.00388/job (23% under $0.005 target)

**Technical Innovations:**
- Pre-classification filtering (title + location patterns) achieved 94.7% cost reduction
- Full job descriptions (9,000-15,000 chars) vs. Adzuna's truncated 100-200 chars
- Two-tier agency detection: hard blocklist + soft pattern matching

---

### Phase 3: Pipeline Hardening (Dec 2-6) - 5 days
**Commits:** 25 | **Focus:** Reliability & Scale

| Date | Milestone |
|------|-----------|
| Dec 2 | Repository reorganization + schema updates |
| Dec 3 | Major refactor: incremental upserts, remote location support |
| Dec 4 | Deduplication fixes: 9 commits resolving edge cases |
| Dec 6 | Greenhouse pagination robustness + multi-pattern job extraction |

**Key Challenges Solved:**
- **Deduplication:** Switched from hash-based to `posting_url` as unique key
- **Incremental Processing:** Upsert pattern prevents reprocessing existing jobs
- **Rate Limiting:** Adzuna API pagination with backoff retry logic
- **Edge Cases:** "New" badge removal, table row parsing, sibling element extraction

**Refactoring Patterns:**
- 9 sequential commits on Dec 4 fixing deduplication (shows iterative debugging)
- Reverted rate limiting approach after testing (shows pragmatic decision-making)
- Wrapper/pipeline separation for cleaner architecture

---

### Phase 4: Analytics Dashboard (Dec 7-16) - 10 days
**Commits:** 45 (across both repos) | **Focus:** Visualization & UX

| Date | Milestone |
|------|-----------|
| Dec 7 | Epic 5 Phase 0: Analytics dashboard foundation |
| Dec 8 | Supabase integration in portfolio-site, chart library POC |
| Dec 9 | Phase 1: API infrastructure + dashboard skeleton |
| Dec 10 | Phase 2: First chart complete (Role Demand) |
| Dec 11 | Job sources metric + Supabase query refactoring |
| Dec 13 | Phase 3: Skills Demand sunburst + deterministic skill mapping |
| Dec 14 | Working Arrangement chart, KPI tiles, performance fixes |
| Dec 15 | Phase 5-6: Metadata, testing, site navigation, final polish |
| Dec 16 | Epics 5 & 6 marked complete |

**Dashboard Components Built:**
1. **Role Demand Chart** - Bar chart with gradient coloring by job volume
2. **Skills Demand Chart** - 3-level sunburst (8 domains → 32 families → 849 skills)
3. **Working Arrangement Chart** - Remote/Hybrid/Onsite distribution
4. **Top Employers Chart** - Ranked bar chart by hiring activity
5. **Seniority Distribution** - Junior/Mid/Senior/Staff+ breakdown

**Key Technical Decisions:**
- **Chart.js over Recharts:** 60KB vs 400KB bundle, better React 19 compatibility
- **Server-side filtering:** API routes filter before sending to client
- **Deterministic skill mapping:** LLM extracts names, Python assigns families (100% accuracy)
- **Frontend caching:** Instant role switching without API round-trips

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│     DATA PIPELINE (job-analytics - Python)                       │
│                                                                  │
│  Adzuna API ──┐                                                  │
│               ├──► Unified Ingester ──► Claude Classifier ──┐    │
│  Greenhouse ──┘    (deduplication)      (Haiku LLM)         │    │
│   Scraper                                                    │    │
│                                                              ▼    │
│                                              ┌─────────────────┐ │
│                                              │    Supabase     │ │
│                                              │   PostgreSQL    │ │
│                                              └────────┬────────┘ │
└──────────────────────────────────────────────────────┼──────────┘
                                                       │
                    ┌──────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│     ANALYTICS DASHBOARD (portfolio-site - Next.js)              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  9 API Routes (/api/hiring-market/*)                    │    │
│  │  - role-demand, top-skills, working-arrangement         │    │
│  │  - top-employers, seniority-distribution, kpis          │    │
│  │  - count, last-updated, job-sources                     │    │
│  └─────────────────────┬───────────────────────────────────┘    │
│                        │                                         │
│  ┌─────────────────────▼───────────────────────────────────┐    │
│  │  React Dashboard (Chart.js + Sunburst)                  │    │
│  │  - GlobalFilters, CustomSelect                          │    │
│  │  - 5 Interactive Chart Components                       │    │
│  │  - Skeleton loaders, caching, smooth transitions        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Deployed on Vercel at richjacobs.me/projects/hiring-market     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Data Pipeline (job-analytics)
| Component | Technology | Purpose |
|-----------|------------|---------|
| Runtime | Python 3.x | Core pipeline logic |
| LLM | Claude 3.5 Haiku | Job classification ($0.80/1M input tokens) |
| Database | Supabase PostgreSQL | Managed storage with free tier |
| Web Scraping | Playwright | Browser automation for Greenhouse |
| HTTP | Requests, httpx | Adzuna API client |
| Config | PyYAML | Taxonomy and blacklist configuration |
| Testing | Pytest | 11 test files, 39+ test cases |

### Analytics Dashboard (portfolio-site)
| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | Next.js 16 (App Router) | Server-side rendering, API routes |
| UI | React 19.2 | Component architecture |
| Styling | Tailwind CSS v4 | Utility-first styling |
| Charts | Chart.js 4.x, sunburst-chart | Interactive visualizations |
| Database Client | @supabase/supabase-js | Server-side queries |
| Testing | Vitest | Unit and E2E tests |
| Deployment | Vercel | Automatic deploys from GitHub |

---

## Key Metrics

### Data Volume
| Metric | Value |
|--------|-------|
| Total raw jobs | 6,178 |
| Enriched (classified) jobs | 5,629 |
| Companies tracked | 302 |
| Data sources | 2 (Adzuna API + Greenhouse scraping) |
| Geographic markets | 3 (London, NYC, Denver) |
| Job families | 2 (Data, Product) |
| Job subfamilies | 11 |
| Skills mapped | 849 → 32 families → 8 domains |

### Cost Economics
| Metric | Value |
|--------|-------|
| Cost per classification | $0.00388 |
| Target cost | $0.005 |
| Under budget by | 23% |
| Monthly estimate (1,500 jobs) | ~$5.82 |
| Pre-classification filter rate | 94.7% |

### Codebase
| Metric | Value |
|--------|-------|
| Pipeline code (Python) | ~11,757 lines |
| Dashboard code (TypeScript) | ~4,468 lines |
| Configuration files | 11 YAML/JSON |
| Test files | 11 |
| API endpoints | 9 |
| Dashboard components | 10 |

---

## Key Learnings

### 1. LLM Cost Optimization is Critical
**Challenge:** Claude API calls at scale could be expensive.
**Solution:** Three-tier filtering strategy:
1. **Title filter:** Regex patterns remove 60-70% of non-target roles before scraping
2. **Location filter:** Remove 89% of remaining jobs outside target cities
3. **Agency blocklist:** Hard filter known recruiters before LLM calls

**Result:** 94.7% of scraped jobs filtered before expensive classification.

### 2. Data Quality Trumps Data Volume
**Challenge:** Adzuna provides volume (1,500 jobs/month) but truncates descriptions to 100-200 chars.
**Solution:** Built Greenhouse scraper for full descriptions (9,000-15,000 chars).

**Impact on Classification:**
| Field | Adzuna Only | With Greenhouse |
|-------|-------------|-----------------|
| Skills extraction | ~29% success | ~85% success |
| Work arrangement | F1 = 0.565 | F1 ≥ 0.85 |

### 3. Deterministic Mapping > LLM for Structured Relationships
**Challenge:** LLM occasionally misclassified job_family (e.g., AI PM as "data" instead of "product").
**Solution:** Moved deterministic relationships out of LLM:
- `job_subfamily` → `job_family` (strict mapping in Python)
- `skill_name` → `skill_family` → `skill_domain` (849 skills mapped)

**Result:** 100% accuracy on family assignments, reduced token usage.

### 4. Iterative Debugging is Normal
**Evidence:** December 4th shows 9 sequential commits fixing deduplication:
```
22b862a Implement incremental upsert pattern
3de70ed Fix duplicate logging
25119e3 Fix upsert conflict: use posting_url
bd82308 Handle hash conflicts as duplicates
49c4b46 Remove hash unique constraint
...
```
**Lesson:** Complex data pipelines require iterative refinement. Each edge case discovered improves robustness.

### 5. Architecture Pivots Are Okay
**Original Plan:** Python `analytics.py` + Streamlit dashboard
**Actual Build:** Next.js API routes + React dashboard

**Why the Pivot:**
- Wanted dashboard integrated with existing portfolio site
- Next.js API routes provide type safety and better performance
- React 19 compatibility issues eliminated Tremor (original choice)
- Chart.js (60KB) beat Recharts (400KB) on bundle size

**Outcome:** Cleaner architecture, single deployment, better portfolio presentation.

### 6. Documentation as Architecture
The 1,233-line `CLAUDE.md` served as:
- Living specification for Claude Code collaboration
- Decision log for architectural choices
- Onboarding document for future self
- Epic tracking system (replaced week-based timeline)

---

## Challenges Encountered

### 1. Deduplication Edge Cases
**Problem:** Same job appearing via different URLs, hash conflicts.
**Symptoms:** Duplicate classifications, wasted API calls.
**Solution:** Switched to `posting_url` as canonical unique key, implemented upsert pattern.
**Commits:** 9 fixes on Dec 4 to get it right.

### 2. Greenhouse Scraper Reliability
**Problems:**
- Pagination inconsistency across companies
- Dynamic content loading (Load More, infinite scroll)
- Location field in different DOM positions
- "New" badge text polluting job titles

**Solutions:**
- Multiple pagination strategies (buttons, page numbers, scroll)
- Extended timeouts (600s per company)
- Sibling element traversal for location extraction
- Regex cleaning for badge removal

### 3. React 19 Compatibility
**Problem:** Tremor (original chart choice) incompatible with React 19.
**Discovery:** POC during Phase 0 revealed the issue early.
**Solution:** Chart.js + react-chartjs-2 worked perfectly.
**Lesson:** Always POC third-party libraries before committing.

### 4. Race Conditions in Dashboard
**Problem:** Role selection reset immediately after clicking.
**Root Cause:** `handleFiltersChange` recreated on every render.
**Solution:** Wrapped in `useCallback` with proper dependencies.
**Evidence:** "Fix race condition and loading flicker" commit on Dec 14.

---

## What's Next (Epic 7: Automation)

### Planned
- GitHub Actions for daily automated pipeline runs
- Caching layer for expensive queries
- Monitoring and alerting for pipeline failures
- ≥95% successful run rate target

### Future Enhancements
- Mobile-responsive charts (v2)
- Shareable filtered views via URL parameters
- Compensation benchmarking (NYC/Denver focus)
- Additional marketplace questions (30 more identified)

---

## Repository Statistics

### job-analytics (Python Pipeline)
```
Total commits: 60+
Python files: 47
YAML configs: 11
Test files: 11
Documentation: 1,233 lines (CLAUDE.md) + 751 lines (Epic 5 planning)
```

### portfolio-site (Next.js Dashboard)
```
Total commits: 50+
TypeScript files: ~30 (API + components)
Chart components: 5
API endpoints: 9
Test framework: Vitest
```

---

## Conclusion

This project demonstrates end-to-end delivery of a data product:

1. **Product Thinking:** Started with marketplace questions, not technology
2. **Data Engineering:** Multi-source ingestion, deduplication, quality handling
3. **AI Integration:** LLM classification with cost optimization
4. **Full-Stack Development:** Python pipeline + TypeScript dashboard
5. **DevOps:** Database management, testing, deployment
6. **Iteration:** 6 weeks of continuous improvement across 100+ commits

The result is a functional MVP that answers real questions about the hiring market, deployed and accessible at [richjacobs.me/projects/hiring-market](https://richjacobs.me/projects/hiring-market).

---

*Report generated: December 16, 2025*
*Total development time: ~6 weeks*
*Total commits: 110+ across both repositories*
