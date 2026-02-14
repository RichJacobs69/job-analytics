# Product Brief: Hiring Market Intelligence Platform

**Version:** 4.0
**Last Updated:** 2026-02-07
**Product Manager:** Rich

**Live Dashboard:** [richjacobs.me/projects/hiring-market](https://richjacobs.me/projects/hiring-market)

---

## Problem Statement

### What's Not Working

**For job seekers:**
The job search experience is broken. The #1 frustration is ghosting (44-75% of candidates report being ghosted post-application), followed by ghost jobs (18-22% of listings are fake or filled), and opaque processes. In a buyer's market with tech postings 49% below 2020 levels and average searches lasting 5.5 months, candidates face a brutal numbers game: only 3% of applications yield interviews, forcing mass-apply strategies that benefit no one.

**The conventional wisdom is wrong:** Job seekers aren't overwhelmed by "too many options"—they're drowning in low-quality options and black-hole application processes. The hidden job market (70-85% of hires happen through networking) means public postings are already the minority channel.

**For employers (future audience):**
Lack visibility into competitors' hiring intensity by role and market, impacting time-to-hire and compensation decisions.

### What We Can (and Can't) Solve

| Problem | Can We Address It? | How |
|---------|-------------------|-----|
| Ghost jobs / dead listings | ✅ Partially | Direct ATS sources (Greenhouse/Lever) = real postings |
| Agency spam / redirect chains | ✅ Yes | No agencies, no aggregators |
| Generic taxonomy | ✅ Yes | Precise classification (Analytics Engineer ≠ Data Engineer) |
| Black-box "relevance" | ✅ Yes | Transparent, rule-based grouping with explained logic |
| Ghosting after application | ❌ No | We don't have outcome data; link to Glassdoor as proxy |
| Hidden job market access | ❌ No | We're in the public posting market |
| Employer response rates | ❌ No | Would require application outcome tracking |

**Honest positioning:** We can't solve the #1 pain point (ghosting). But we can ensure candidates don't waste time on the preventable frustrations: junk listings, agency spam, and keyword-stuffed irrelevance.

### Why Now

- Demand signals for data and product roles are shifting rapidly with AI adoption, remote/onsite changes, and macro volatility—historic reports are stale
- Curated platforms (Otta) have proven 2x interview conversion rates vs. traditional boards, validating the curation model
- Personal development goal: deliver a working prototype to showcase end-to-end product and AI/data engineering skills
- Opportunity to validate a focused product before expanding to employer-facing analytics

---

## Target Users

### Primary: Job Seekers (Product & Data roles)

**Who they are:**
- Mid-to-senior professionals in Product Management or Data roles
- Know what they want (specific subfamily, seniority, location, arrangement)
- Tired of wading through irrelevant noise on LinkedIn/Indeed
- Value quality over quantity in their job search

**What they need:**
1. Verified, active listings (not ghost jobs)
2. Precise role matching (not "Data" as a catch-all)
3. Context to prioritise applications (employer signals, salary benchmarks)
4. Direct apply path (no redirect chains)

**What they explicitly DON'T need from us:**
- Another place to mass-apply to hundreds of jobs
- AI that promises to "match" them perfectly (they're skeptical, rightly)
- Features that require them to upload their CV or create an account

### Secondary: Employers (Future)

Competitive intelligence on hiring patterns, compensation benchmarking, talent availability by market.

---

## Current Scope

### Locations (5 markets)

| City | Country | Salary Data Quality |
|------|---------|---------------------|
| London | UK | ~38% include salary |
| New York City | USA | ~70%+ (transparency law) |
| Denver | USA | ~81% (Colorado law) |
| San Francisco | USA | ~70%+ (California law) |
| Singapore | SG | Variable |

### Data Sources (6 sources)

| Source | Type | Coverage | Description Quality | Use in Job Feed |
|--------|------|----------|---------------------|-----------------|
| Greenhouse | Scraper (Playwright) | 452 companies | Full (9,000-15,000 chars) | Yes |
| Lever | API | 182 companies | Full | Yes |
| Ashby | API | 169 companies | Full + structured salary (best) | Yes |
| Workable | API | 135 companies | Full + workplace_type | Yes |
| SmartRecruiters | API | 35 companies | Full + locationType, experienceLevel | Yes |
| Adzuna | API | Broad aggregator | Truncated (100-200 chars) | No (poor UX) |

**Why no Adzuna in job feed:** Candidates would land on Adzuna, hit a registration gate, then redirect to the actual company page. 3-4 clicks vs. 1 for direct ATS links. Violates our "verified, direct apply" promise.

**Adzuna remains useful for:** Market analytics, trend tracking, coverage breadth.

### Role Families

**Product Roles:**
| Subfamily | Description |
|-----------|-------------|
| Core PM | General product management for user-facing features |
| Growth PM | Acquisition, retention, monetization, conversion |
| Platform PM | Developer tools, APIs, infrastructure products |
| Technical PM | Deep technical skills, often ex-engineer |
| AI/ML PM | AI/ML products, models, data products |

**Data Roles:**
| Subfamily | Description |
|-----------|-------------|
| Product Analytics | Product metrics, experiments, user behavior |
| Data Analyst | Business reporting, dashboards, SQL analysis |
| Analytics Engineer | dbt, metrics layer, data modeling |
| Data Engineer | Pipelines, infrastructure, ETL/ELT |
| ML Engineer | Production ML systems, MLOps, LLM/GenAI |
| Data Scientist | Business insights, predictions, statistical modeling |
| Research Scientist | Novel ML research, publications |
| Data Architect | Data strategy, governance, platform design |

---

## Product Strategy

### Two Complementary Experiences

**1. Market Trends Dashboard (Existing)**
- Aggregate analytics: hiring volume, skill trends, remote/onsite mix, salary distributions
- Audience: Anyone researching the market (job seekers, employers, researchers)
- Value: "What's happening in the market?"

**2. Curated Job Feed (New - Epic 8)**
- Personalised, grouped job recommendations with transparent context
- Audience: Active job seekers who know what they want
- Value: "Which specific roles should I prioritise?"

### Job Feed Value Proposition

> "Verified roles from real companies. No ghost jobs. No agency spam. We show our working."

**What makes us different:**

| Traditional Boards | Us |
|-------------------|-----|
| 500 "Data" jobs | 7 Analytics Engineer roles that match your filters |
| Black-box "relevance" | Transparent groups: Fresh / Still Hiring / Scaling Teams / Top Comp / Remote |
| Agency spam, dead listings | Direct ATS sources only |
| Apply → black hole | Context to prioritise + Glassdoor link for responsiveness signals |

**What we're honest about:**
- We can't tell you who will respond (but we can help you avoid obvious time-wasters)
- We're showing public postings (70-85% of jobs are filled through networking)
- Our signals are context, not guarantees

---

## Architecture

### Data Pipeline

```
Adzuna API ---------+
                    |
Greenhouse ---------+
                    |
Lever --------------+---> unified_job_ingester.py ---> Agency Filter
                    |              |
Ashby --------------+              v
                    |     classifier.py (Gemini 2.5 Flash)
Workable -----------+              |
                    |              v
SmartRecruiters ----+     Supabase PostgreSQL
                                   |
                     +-------------+-------------+
                     |                           |
                     v                           v
           Market Trends Dashboard      Curated Job Feed
            (all sources)            (ATS sources only)
```

### Core Capabilities

**Data Layer:**
- **Ingestion:** Adzuna API + 5 ATS scrapers (Greenhouse/Lever/Ashby/Workable/SmartRecruiters) with incremental updates
- **Extraction:** Titles, locations, compensation, skills, seniority from raw descriptions
- **Storage:** Raw and enriched layers in Supabase PostgreSQL with JSONB for flexible schema
- **Derived tables:** `employer_fill_stats` (median time-to-fill by company)

**AI Layer:**
- **Classification:** Gemini 2.5 Flash ($0.000629/job) and Gemini 3.0 Flash ($0.002435/job) with model routing by source
- **Role Summary:** Gemini-generated 2-3 sentence summaries inline during classification
- **Taxonomy Mapping:** Rule-based pre-filtering + LLM classification
- **Cost Optimization:** Pre-classification filtering achieves 94.7% cost reduction

**Analysis Layer:**
- **Trend Tracking:** Time series by role, skill, and city; remote vs onsite
- **Employer Signals:** Fill-time baselines, scaling indicators
- **Front End:** Next.js with Chart.js (dashboard) and grouped job feed

---

## Success Metrics

### Coverage & Quality

| KPI | Definition | Target | Actual |
|-----|------------|--------|--------|
| Data Coverage | Enriched jobs in database | 5,000+ | 18,000+ |
| Companies Tracked | All ATS sources combined | 300+ | 970+ |
| Classification Cost | Cost per classified job | <$0.005 | ~$0.0005 (Gemini 2.5 Flash) |
| Data Freshness | Pipeline runs successfully | Daily | Automated via GitHub Actions (6 ATS + Adzuna) |

### Job Feed Metrics (New)

| KPI | Definition | Target |
|-----|------------|--------|
| Filter engagement | % sessions that set filters | >70% |
| Card expansion rate | % displayed jobs where user expands details | >40% |
| Apply click-through | % displayed jobs where user clicks Apply | >15% |
| Return visits | % users who return within 7 days | >25% |

### Qualitative Validation

| KPI | Instrument | Target |
|-----|------------|--------|
| Recommendation Intent | "Would you recommend this to a peer?" | ≥60% Yes |
| Differentiation | "Does this feel different from LinkedIn?" | Clear articulation of difference |
| Trust | "Do you understand why these jobs were shown?" | >80% Yes |
| Usefulness | "Did you see jobs you'd actually apply to?" | >50% Yes |

---

## Project Status

### Completed

- [DONE] Epic 1: Data model & taxonomy design
- [DONE] Epic 2: Adzuna API integration
- [DONE] Epic 3: Greenhouse scraper (452 companies)
- [DONE] Epic 4: Cost tracking & validation
- [DONE] Epic 5: Next.js dashboard (5 visualizations)
- [DONE] Epic 6: Lever integration (182 companies)
- [DONE] Epic 7: GitHub Actions automation
- [DONE] Ashby integration (169 companies, structured compensation)
- [DONE] Workable integration (135 companies, workplace_type + salary)
- [DONE] SmartRecruiters integration (35 companies, locationType + experienceLevel)
- [DONE] Employer metadata & enrichment system
- [DONE] LLM migration: Claude Haiku to Gemini 2.5/3.0 Flash (87% cost reduction on high-volume sources)

### In Progress

- [IN PROGRESS] Epic 8: Curated Job Feed (Phase 2 complete; remaining: localStorage, analytics CTA)

### Future Considerations

- Additional cities (Berlin, Toronto, Austin)
- Employer-facing analytics
- Salary benchmarking deep-dive
- Response rate tracking (if data becomes available)
- Community features / Glassdoor integration

---

## Risks & Honest Limitations

| Risk | Mitigation |
|------|------------|
| Users expect us to solve ghosting | Clear messaging: "We filter junk listings, not unresponsive employers" |
| "Still Hiring" signal is ambiguous | Seniority-aware caveats; link to Glassdoor |
| "Scaling Teams" could mean turnover | Explicit caveat: "Check reviews for context" |
| Salary data gaps outside US | Only show Top Compensation group for US cities |
| 970+ companies feels limited vs LinkedIn | Position as "curated quality" not "comprehensive coverage" |
| Users want more than 7 per group | "Show more" expansion; "View all" escape hatch |

---

## Appendix: Research Insights

Key findings from competitive/market research that shaped this brief:

1. **Ghosting is #1 pain (44-75%)**, not information overload
2. **3% application-to-interview rate** means candidates need volume, not curation alone
3. **Hidden job market is 70-85%** of hires—we're in the minority channel
4. **Otta's 2x interview rate** validates curation, but their value is quality employers, not just fewer jobs
5. **7±2 is the cognitive sweet spot** for options (Miller's Law)
6. **Rule-based explainability** is right for high-stakes decisions where trust matters
7. **Salary transparency drives applications** (99% more likely when disclosed)
