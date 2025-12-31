# Epic: Curated Job Feed

**Epic ID:** EPIC-008
**Version:** 1.1
**Created:** 2025-12-27
**Updated:** 2025-12-31
**Owner:** Rich
**Status:** In Progress (Phase 1 Infrastructure Complete)

---

## Implementation Status

### Phase 1: Infrastructure [DONE]

| Component | Status | Notes |
|-----------|--------|-------|
| **Database Migrations** | [DONE] | 010, 012, 013 executed on Supabase |
| `employer_fill_stats` table | [DONE] | Stores median fill times per employer |
| `enriched_jobs.summary` column | [DONE] | AI-generated role summaries (inline, migration 013) |
| `url_status` column | [DONE] | 404 detection for dead link filtering |
| **Pipeline Scripts** | [DONE] | Summary generation now inline in classifier |
| `employer_stats.py` | [DONE] | Uses 404 as closed signal (not last_seen_date) |
| `classifier.py` | [DONE] | Now generates summaries inline during classification |
| `url_validator.py` | [DONE] | Parallel HTTP HEAD checks, 10 workers |
| **GitHub Actions** | [DONE] | `refresh-derived-tables.yml` (URL validation + stats only) |
| **API Endpoints** | [DONE] | 2 new endpoints in portfolio-site |
| `/api/hiring-market/jobs/feed` | [DONE] | 5 groups, all working |
| `/api/hiring-market/jobs/[id]/context` | [DONE] | Summary + fit signals |

### Phase 2: Frontend [NOT STARTED]

| Component | Status |
|-----------|--------|
| Job feed page (`/projects/hiring-market/jobs`) | [TODO] |
| Filter bar component | [TODO] |
| Job card component | [TODO] |
| Expandable card with context | [TODO] |
| localStorage persistence | [TODO] |
| Analytics dashboard CTA | [TODO] |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **404 for closed detection** | More reliable than `last_seen_date` heuristic |
| **Fixed 30-day threshold for "Still Hiring"** | Simpler than employer median comparison; median is display-only |
| **Inline summary generation** | Summaries generated during classification (single Gemini call), not batch. Ensures 100% data completeness, eliminates GHA runaway risk |
| **Summary in enriched_jobs column** | Simpler than separate table; no JOIN needed; `job_summaries` table deprecated |
| **REST not GraphQL** | 2 endpoints don't justify new tooling/patterns |
| **localStorage + URL params** | No auth needed, shareable URLs |

### Test Results (2025-12-30)

```
Feed endpoint: /api/hiring-market/jobs/feed?job_family=data

Groups populated:
  scaling_teams:    610 jobs
  fresh_matches:    381 jobs
  still_hiring:     152 jobs
  remote_friendly:  278 jobs
  top_compensation:  78 jobs

Total matching: 1,162 jobs
```

---

## Overview

### Problem Statement

The current Hiring Market Dashboard provides market-level analytics (trends, distributions, comparisons) but doesn't give job seekers a direct path to action. Users see interesting data but lack a clear "what should I do with this?" moment. In a buyer's market where candidates compete against hundreds of applicants, they need curated, high-relevance job recommendations—not another infinite scroll.

### Vision

> "Verified roles from real companies. No ghost jobs. No agency spam. We show our working."

A curated feed of high-relevance jobs organised by intent, with transparent context to help candidates prioritise where to invest their limited application energy. We can't solve ghosting, but we can ensure you're not wasting time on junk listings.

### Core Principles

1. **Quality over quantity** — 7 verified matches beat 500 keyword hits from aggregators
2. **Explainability** — Every recommendation comes with context ("why this might be a fit")
3. **Transparency** — No black-box algorithms; users see exactly how we filtered and grouped
4. **Honesty about limits** — We show what we know; we caveat what's ambiguous
5. **Direct apply only** — Greenhouse/Lever sources mean you land on the real ATS, not a redirect chain

### Differentiation from LinkedIn/Indeed/Aggregators

| Their Problem | Our Solution | Honest Limitation |
|---------------|--------------|-------------------|
| Ghost jobs, dead listings | Direct ATS sources only (Greenhouse/Lever) | Can't verify budget is still approved |
| Agency spam, redirect chains | No agencies, no aggregators | Smaller total volume |
| Generic "Data" category | Precise taxonomy (Analytics Engineer ≠ Data Engineer) | — |
| Black-box "relevance" ranking | Transparent grouping with explained logic | — |
| No employer context | Fill-time baselines, scaling signals | Ambiguous signals get caveats |
| Ghosting after application | **We can't solve this** | Link to Glassdoor reviews as proxy |

**What we're NOT claiming:**
- We can't tell you which companies will respond
- We can't access the hidden job market (70-85% of hires happen through networking)
- We can't guarantee the role is still open—only that it's posted on a real ATS

---

## User Stories

### Core User Stories

**US-000: Discover Jobs from Analytics**  
As a user exploring market trends, I want to easily view jobs matching my current filter selection so that I can move from research to action without re-entering my preferences.

**Acceptance Criteria:**
- CTA appears on analytics dashboard when subfamily and city are selected
- CTA shows count of matching jobs (e.g., "View 47 matching jobs →")
- Clicking CTA navigates to job feed with filters pre-applied via URL params
- Job feed includes "← Back to market trends" link to return

**CTA Loading States:**

| State | Display | Behavior |
|-------|---------|----------|
| Loading | "View jobs →" (no count) | Still clickable |
| Success | "View 47 jobs →" | Shows count |
| Error | "View jobs →" | Graceful fallback, hide count |
| Zero results | Hide CTA entirely | Don't show "View 0 jobs" |

**US-001: Set Preferences**  
As a job seeker, I want to set my role preferences (subfamily, seniority, city, working arrangement) so that I only see relevant jobs.

**Acceptance Criteria:**
- User can select: City (multi-select), Role subfamily (multi-select), Seniority level (multi-select), Working arrangement (multi-select)
- Preferences persist in localStorage across sessions
- Preferences reflected in URL params (shareable/bookmarkable)
- Clear "Reset filters" option

**US-002: View Curated Feed**  
As a job seeker, I want to see a curated list of ≤5 jobs matching my preferences so that I can focus my application energy on high-fit opportunities.

**Acceptance Criteria:**
- Maximum 5 jobs displayed per day (scarcity by design)
- Jobs sorted by relevance (matching criteria count + freshness)
- Each job card shows: Title, Company, Location, Working arrangement, Posted date, Seniority level
- "Apply" button links directly to job posting URL
- Empty state if no jobs match filters

**US-003: View Job Context**  
As a job seeker, I want to see contextual information about each job so that I can quickly assess fit without leaving the page.

**Acceptance Criteria:**
- Expandable job card reveals: Role summary (2-3 sentences, AI-generated from description), Company context (size estimate, industry if available), Key skills mentioned, Salary range (if available), "Days open" indicator
- Context loads on expand (not on initial page load)

**US-003a: Understand Why This Job Was Recommended**  
As a job seeker, I want to see explicit reasoning for why each job was shown to me so that I trust the recommendations and understand the matching logic.

**Acceptance Criteria:**
- Each expanded card includes a "Why this might be a fit" section
- Reasoning is specific and data-driven, not generic (e.g., "Open 18 days — avg for Analytics Engineer roles is 12 days" not "Good opportunity")
- Reasoning references user's stated preferences explicitly (e.g., "Hybrid matches your preference")
- At least 2-3 fit signals shown per job

**US-004: Browse Jobs by Intent**  
As a job seeker, I want to see jobs organised by different signals (freshness, longevity, company activity, compensation, remote) so that I can prioritise based on what matters to me.

**Acceptance Criteria:**
- Feed organised into 5 distinct groups: Fresh Matches, Still Hiring, Scaling Teams, Top Compensation (US only), Remote Friendly
- Each group clearly labelled with icon and tagline explaining the logic
- Jobs can appear in multiple groups where criteria overlap
- Groups with 0 matching jobs are hidden
- "Show more" option if group has >5 matching jobs

### Stretch User Stories (v1.1)

**US-005: Save/Dismiss Jobs**  
As a job seeker, I want to save interesting jobs and dismiss irrelevant ones so that my feed improves over time.

**US-006: View Application History**  
As a job seeker, I want to track which jobs I've applied to so that I don't duplicate efforts.

---

## Information Architecture

### Navigation Change

**Current:**
```
richjacobs.me/projects/hiring-market → Dashboard (charts)
```

**Proposed:**
```
richjacobs.me/projects/hiring-market → Market Trends (landing, primary)
    │
    ├── Filter by subfamily + city
    │       │
    │       └── [CTA: "View X matching jobs →"]
    │                    │
    └────────────────────┴──→ /jobs?subfamily=X&city=Y (Job Feed)
                                    │
                                    └── [Link: "← Back to market trends"]
```

**Rationale:**
- Analytics is genuinely differentiated (no competitor has this view with our taxonomy)
- Lower friction for new users (can explore without setting preferences)
- Builds trust before asking for engagement
- Cross-link CTA validates job feed demand before over-investing
- Job feed is a feature within the platform, not a replacement landing page

Jobs become a **conversion path from analytics**, not the primary experience.

### Job Feed Page Structure

The feed is organised into **semantic groups**, each curated to max 5 jobs. This avoids conflating different job-seeking intents into a single ranked list.

**Feed Groups (v1):**

| Group | Icon | Logic | Tagline | Caveat |
|-------|------|-------|---------|--------|
| Fresh Matches | 🆕 | Posted <7 days, high relevance | "Be an early applicant" | — |
| Still Hiring | ⏳ | >1.5x employer avg fill time | "Open longer than usual for this company" | "For senior roles, this often indicates high standards. For junior roles, investigate further." |
| Scaling Teams | 🚀 | Company has 3+ similar open roles | "Actively hiring for this function" | "Could indicate growth or turnover—check Glassdoor reviews" |
| Top Compensation | 💰 | 75th+ percentile salary for role/city | "Above-market pay" | US cities only (NYC, Denver, SF) where data is reliable |
| Remote Friendly | 🌍 | `working_arrangement = 'remote'` | "Work from anywhere" | — |

**Group limits:** Max 7 jobs per group (research supports 7±2 as cognitive sweet spot)

**Notes:**
- A job can appear in multiple groups (e.g., fresh + remote + top comp)
- Groups with 0 matching jobs are hidden
- Each group shows max 7 jobs, sorted by relevance within group
- Source filter: Greenhouse + Lever only (no Adzuna) for direct-apply UX
- "Show more" available if group has additional matches beyond 7

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo]  Jobs for You    [Market Trends →]                 │
├─────────────────────────────────────────────────────────────┤
│  FILTERS (sticky on scroll)                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐       │
│  │ City ▼  │ │ Role ▼  │ │ Level ▼ │ │ Arrangement ▼│       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────────┘       │
│                                          [Reset Filters]    │
├─────────────────────────────────────────────────────────────┤
│  YOUR MATCHES · Analytics Engineer · Senior · London        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🆕 FRESH MATCHES (3)                                       │
│  Posted in the last 7 days                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Senior Analytics Engineer                           │   │
│  │ Wise · London · Hybrid · £90-120k                   │   │
│  │ Posted 2 days ago                                   │   │
│  │ [▼ Show details]                    [Apply →]       │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Analytics Engineer                                  │   │
│  │ Monzo · London · Hybrid · £75-95k                   │   │
│  │ Posted 5 days ago                                   │   │
│  │ [▼ Show details]                    [Apply →]       │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Senior Analytics Engineer                           │   │
│  │ Revolut · London · Onsite · £85-105k                │   │
│  │ Posted 6 days ago                                   │   │
│  │ [▼ Show details]                    [Apply →]       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ⏳ STILL HIRING (2)                                  │
│  Open longer than usual for this company                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Senior Analytics Engineer                           │   │
│  │ Stripe · London · Hybrid · £95-120k                 │   │
│  │ Open 8 weeks · Stripe avg is 4 weeks                │   │
│  │ [▼ Show details]                    [Apply →]       │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Lead Analytics Engineer                             │   │
│  │ Deliveroo · London · Hybrid · £100-130k             │   │
│  │ Open 6 weeks · Deliveroo avg is 3 weeks             │   │
│  │ [▼ Show details]                    [Apply →]       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  🚀 SCALING TEAMS (4)                                       │
│  Companies actively hiring for this role                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Analytics Engineer                                  │   │
│  │ Deliveroo · London · Hybrid · £75-95k               │   │
│  │ Deliveroo has 5 open Analytics roles                │   │
│  │ [▼ Show details]                    [Apply →]       │   │
│  └─────────────────────────────────────────────────────┘   │
│  [Show 3 more in this group]                               │
│                                                             │
│  🌍 REMOTE FRIENDLY (2)                                     │
│  Work from anywhere                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Senior Analytics Engineer                           │   │
│  │ GitLab · London · Remote · £90-115k                 │   │
│  │ Posted 4 days ago                                   │   │
│  │ [▼ Show details]                    [Apply →]       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  [View all 47 matching jobs →]                             │
└─────────────────────────────────────────────────────────────┘
```

**US cities (NYC, Denver, SF) also show compensation group:**

```
│  💰 TOP COMPENSATION (3)                                    │
│  Above-market pay for this role                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Senior Analytics Engineer                           │   │
│  │ Stripe · NYC · Hybrid · $185-220k                   │   │
│  │ 90th percentile for NYC Analytics Engineers         │   │
│  │ [▼ Show details]                    [Apply →]       │   │
│  └─────────────────────────────────────────────────────┘   │
```

### "View All" Page Structure

**Route:** `/projects/hiring-market/jobs/all?[filters]`

When user clicks "Show more" or "View all X matching jobs", show compact list view:

```
+-------------------------------------------------------------+
| <- Back to curated feed                                      |
+-------------------------------------------------------------+
|  FILTERS (same as main feed)                                 |
|  [City v]  [Role v]  [Level v]  [Arrangement v]    [Reset]   |
+-------------------------------------------------------------+
|  Showing 47 of 47 jobs                        [Sort: Recent] |
+-------------------------------------------------------------+
|  Senior Analytics Engineer                                   |
|  Monzo . London . Hybrid . GBP 85-110k           Posted 2d   |
|                                       [Details] [Apply ->]   |
+-------------------------------------------------------------+
|  Analytics Engineer                                          |
|  Wise . London . Remote . GBP 75-95k             Posted 3d   |
|                                       [Details] [Apply ->]   |
+-------------------------------------------------------------+
|  ... (paginated, 20 per page)                                |
+-------------------------------------------------------------+
|  [<- Previous]  Page 1 of 3  [Next ->]                       |
+-------------------------------------------------------------+
```

**Key differences from grouped feed:**
- No intent groups (flat list)
- Compact cards (single row per job, no group badges)
- Sort control (Recent / Salary / Company A-Z)
- Pagination (20 per page, not infinite scroll)
- "Details" opens modal or navigates to expanded view

**Why pagination over infinite scroll:**
- Users need sense of progress ("page 2 of 3")
- Easier to return to specific job
- Better for accessibility (focus management)

### Expanded Job Card (on click "Show details")

```
┌─────────────────────────────────────────────────────────────┐
│ ⏳ STILL HIRING                                             │
│                                                             │
│ Senior Analytics Engineer                                  │
│ Monzo · London · Hybrid · £85-110k                         │
│ Open 6 weeks · Monzo avg is 3 weeks                        │
├─────────────────────────────────────────────────────────────┤
│ ROLE SUMMARY                                               │
│ Own the analytics infrastructure for Monzo's lending       │
│ products. You'll build dbt models, define metrics, and     │
│ partner with Data Scientists on experimentation.           │
├─────────────────────────────────────────────────────────────┤
│ KEY SKILLS                                                 │
│ SQL · dbt · Python · Looker · Experimentation              │
├─────────────────────────────────────────────────────────────┤
│ COMPANY CONTEXT                                            │
│ Scale-up · 2,500+ employees · Digital Banking              │
│ 12 open Data roles currently                               │
│ [View Glassdoor reviews →]                                 │
├─────────────────────────────────────────────────────────────┤
│ WHY THIS MIGHT BE A FIT                                    │
│ • Open 6 weeks — Monzo typically fills in 3 (for Senior    │
│   roles, this often means high hiring bar)                 │
│ • Monzo hiring 3 similar roles (check reviews for context) │
│ • Hybrid matches your preference                           │
│                                                             │
│ [▲ Hide details]                          [Apply →]        │
└─────────────────────────────────────────────────────────────┘
```

**Note:** Glassdoor link helps users assess employer responsiveness and culture—information we can't provide directly.

---

## Technical Design

### Data Requirements

**Existing fields (already in enriched_jobs):**
- `title_display`, `company_name`, `city_code`, `working_arrangement`
- `seniority`, `job_subfamily`, `posted_date`, `posting_url`
- `salary_min`, `salary_max`, `currency`
- `description` (full text for summary generation)
- `source` (for filtering to Greenhouse/Lever only)

**New/derived fields needed:**
- `days_open`: Calculated from `posted_date`
- `company_role_count`: Count of active roles per company (aggregation)
- `summary`: AI-generated 2-3 sentence summary (inline during classification)
- `employer_median_fill_days`: Median time-to-fill for this employer (calculated from historical closed roles)
- `salary_percentile`: Percentile rank of salary within role/city (US cities only)

**New derived table: `employer_fill_stats`**
```sql
CREATE TABLE employer_fill_stats AS
SELECT 
  company_name,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY 
    DATE_PART('day', last_seen_date - posted_date)
  ) as median_days_to_fill,
  COUNT(*) as sample_size
FROM enriched_jobs
WHERE last_seen_date < CURRENT_DATE - INTERVAL '7 days'  -- Likely closed
  AND source IN ('greenhouse', 'lever')
GROUP BY company_name
HAVING COUNT(*) >= 3;  -- Minimum sample for meaningful baseline
```

### API Endpoints

**GET /api/jobs/feed**
```typescript
// Request
{
  cities: string[],           // ['lon', 'nyc']
  subfamilies: string[],      // ['analytics_engineer', 'data_engineer']
  seniorities: string[],      // ['senior', 'staff_plus']
  arrangements: string[],     // ['hybrid', 'remote']
  limit_per_group: number     // default 5, max 10
}

// Response
{
  groups: {
    fresh_matches: {
      jobs: Job[],
      total_in_group: number,
      tagline: "Posted in the last 7 days"
    },
    still_hiring: {
      jobs: Job[],
      total_in_group: number,
      tagline: "Open longer than usual for this company"
    },
    scaling_teams: {
      jobs: Job[],
      total_in_group: number,
      tagline: "Companies actively hiring for this role"
    },
    top_compensation: {          // Only included for US cities
      jobs: Job[],
      total_in_group: number,
      tagline: "Above-market pay for this role"
    },
    remote_friendly: {
      jobs: Job[],
      total_in_group: number,
      tagline: "Work from anywhere"
    }
  },
  total_matching: number,
  filters_applied: object
}
```

**GET /api/jobs/:id/context**
```typescript
// Response (called on card expand)
{
  role_summary: string,
  skills: string[],
  company_context: {
    size_estimate: string,
    industry: string,
    open_roles_count: number
  },
  fit_signals: string[]
}
```

### Group Selection Logic

Each group has specific qualification criteria. Jobs can appear in multiple groups.

```typescript
// Group qualification rules
const groupRules = {
  fresh_matches: (job) => 
    daysSince(job.posted_date) <= 7,
  
  still_hiring: (job) => {
    const employerAvg = getEmployerMedianFillDays(job.company_name);
    if (!employerAvg) return false;
    const ratio = daysSince(job.posted_date) / employerAvg;
    return ratio > 1.5;
  },
  
  scaling_teams: (job) => 
    getCompanyOpenRoleCount(job.company_name, job.job_subfamily) >= 3,
  
  top_compensation: (job) => 
    job.salary_percentile >= 75 && ['nyc', 'den', 'sf'].includes(job.city_code),
  
  remote_friendly: (job) => 
    job.working_arrangement === 'remote'
};

// Within each group, sort by:
// 1. Relevance score (filter match count)
// 2. Freshness (newer first)
// 3. Limit to 7 per group (show "X more" if overflow)
```

### Seniority-Aware Signal Interpretation

For "Still Hiring" and "Scaling Teams" groups, include contextual caveats based on seniority:

```typescript
function getLongevityCaveat(job: Job, ratio: number): string | null {
  if (ratio <= 1.5) return null;
  
  switch (job.seniority) {
    case 'junior':
      return "For entry-level roles, extended posting may indicate issues—check reviews";
    case 'senior':
    case 'staff_plus':
      return "For senior roles, this often indicates a high hiring bar";
    default:
      return null;
  }
}

function getScalingCaveat(): string {
  return "Could indicate growth or turnover—check Glassdoor reviews";
}
```

### Source Filtering

**Critical:** Only Greenhouse and Lever jobs appear in the curated feed.

```sql
WHERE source IN ('greenhouse', 'lever')
```

Adzuna jobs excluded due to poor apply UX (redirect chains, registration gates).

### Role Summary Generation

**Architecture Decision: Inline Generation (Implemented 2025-12-31)**

Summaries are now generated inline during job classification, not via batch job.

**How it works:**
- `classifier.py` prompt includes summary generation (adds ~100 output tokens)
- Single Gemini call does both classification AND summary
- Summary stored in `enriched_jobs.summary` column
- New jobs always have summaries from day 1

**Why inline over batch:**
- **Data completeness**: 100% of jobs have summaries (batch had 2,190 job backlog)
- **Simpler architecture**: No separate GHA workflow, no `job_summaries` table
- **Cost efficient**: Combined prompt vs two separate LLM calls
- **No runaway risk**: Batch job caused 39-min GHA timeout; inline is bounded per job

**Backfill utility:**
- `summary_generator.py` remains as a backfill tool for regeneration
- Not scheduled; run manually when needed: `python pipeline/summary_generator.py --limit=500`

**Deprecated:**
- `job_summaries` table (dropped)
- Summary step in `refresh-derived-tables.yml` (removed)

### "Why This Fits" Reasoning Engine

The fit reasoning should be deterministic and transparent—no ML black box. Generate reasons by comparing job attributes against user preferences.

**Fit Signal Types:**

| Signal | Logic | Example Output | Caveat (if applicable) |
|--------|-------|----------------|------------------------|
| Preference match | Direct filter match | "Hybrid matches your preference" | — |
| Longevity signal | `days_open > employer_avg * 1.5` | "Open 6 weeks — Monzo typically fills in 3" | Add seniority context: "For Senior roles, this often indicates high standards" |
| Company activity | `company_role_count >= 3` | "Monzo hiring 3 similar roles" | "Check Glassdoor reviews for context on growth vs turnover" |
| Salary fit | Salary >= 75th percentile for role/city | "£95k is 75th percentile for London Analytics Engineers" | US cities only; caveats for wide ranges |
| Freshness | `days_open < 3` | "Posted today — be an early applicant" | — |
| Direct apply | Source is Greenhouse/Lever | "Apply direct to company ATS" | — |

**Seniority-aware longevity interpretation:**

| Seniority | Extended Fill Time Usually Means |
|-----------|----------------------------------|
| Junior/Entry | ⚠️ Potentially unattractive role or unrealistic requirements |
| Mid-level | Neutral — could go either way |
| Senior | Often indicates high hiring bar |
| Staff+ | Expected — these roles commonly take 8-12 weeks |

**Generation approach:** Rule-based, not LLM. Compute fit signals server-side and return as array. This keeps it fast, cheap, and fully explainable.

```typescript
interface FitSignal {
  type: 'preference' | 'longevity' | 'activity' | 'salary' | 'freshness' | 'direct_apply';
  text: string;
  caveat?: string;  // Optional context for ambiguous signals
  strength: 'strong' | 'moderate';
}
```

### localStorage Schema

```typescript
interface UserPreferences {
  cities: string[];
  subfamilies: string[];
  seniorities: string[];
  arrangements: string[];
  lastUpdated: string;  // ISO date
}

// Key: 'hiring_intel_prefs'
```

---

## Scope & Phasing

### Phase 1: Core Feed (This Epic)

| Story | Estimate | Priority |
|-------|----------|----------|
| US-000: Analytics → Jobs CTA cross-link | 0.5 day | P0 |
| US-001: Filter UI + localStorage | 0.5 day | P0 |
| US-002: Job cards + grouped feed (5 groups) | 1.5 days | P0 |
| US-003: Expandable context | 0.5 day | P0 |
| US-003a: "Why this fits" reasoning | 0.5 day | P0 |
| US-004: Group selection logic + employer fill stats | 1 day | P0 |
| Role summary generation (batch) | 1 day | P0 |
| API endpoints (grouped response) | 1 day | P0 |

**Total estimate: 6-7 days**

### Phase 2: Enhanced Context (Future)

- Company enrichment (funding rounds, recent news, Glassdoor scores)
- Skills gap analysis ("You have 4/6 required skills")
- Salary benchmarking ("This is 90th percentile for London Analytics Engineers")

### Phase 3: Engagement Features (Future)

- Save/dismiss jobs
- Application tracking
- Email alerts (requires auth)

---

## Success Metrics

### Leading Indicators (Week 1-2)

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Analytics → Jobs CTA click rate | >10% of filtered analytics sessions | Click tracking |
| Filter engagement (on job feed) | >70% of sessions adjust filters | localStorage + analytics event |
| Card expansion rate | >40% of displayed jobs | Click tracking |
| Apply click-through | >15% of displayed jobs | Click tracking |

### Lagging Indicators (Week 3+)

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Return visits | >30% return within 7 days | Analytics |
| Time on page | >90 seconds avg | Analytics |
| Beta user NPS | >40 | Survey |

### Qualitative Validation

Questions to ask beta users:
1. "Would you bookmark this and check it weekly?"
2. "Does this feel different from LinkedIn/Indeed? How?"
3. "Did you see any jobs you actually want to apply to?"
4. "What's missing that would make this your go-to?"

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ≤5 jobs feels too limiting | Medium | High | Add "View all X matching" escape hatch |
| Role summaries feel generic | Medium | Medium | Iterate on prompt; show skills as fallback |
| No jobs match filters | Low | High | Suggest broadening filters; show "close matches" |
| Users expect real-time updates | Low | Low | Show "Updated daily" clearly |

---

## Open Questions

1. ~~**Summary generation timing:** Batch nightly vs. on-demand?~~ **RESOLVED**: Inline during classification (2025-12-31)
2. **"All jobs" view:** Full list or paginated? (Recommend: paginated, 20 per page)
3. **Mobile-first or desktop-first?** (Recommend: desktop-first given job-seeking context)

---

## Definition of Done

- [ ] Analytics dashboard shows "View X matching jobs →" CTA when filters are set
- [ ] CTA passes filter state via URL params to job feed
- [ ] Job feed page at `/jobs` with filter bar (city, role, seniority, arrangement)
- [ ] Filters pre-populate from URL params if present
- [ ] Preferences persist in localStorage for return visits
- [ ] "← Back to market trends" link on job feed
- [ ] Feed displays 5 groups: Fresh Matches, Still Hiring, Scaling Teams, Top Compensation (US), Remote Friendly
- [ ] Each group shows max 7 jobs with clear labelling and tagline
- [ ] Groups with 0 matches are hidden; "Show more" if >7 matches
- [ ] Job cards show: title, company, location, arrangement, salary (if available), contextual info
- [ ] Cards expandable with context (role summary, skills, company context, Glassdoor link)
- [ ] Role summary displayed (AI-generated, 2-3 sentences)
- [ ] "Why this might be a fit" section with 2-3 specific, data-driven reasons
- [ ] Fit reasoning is rule-based and transparent (no black box)
- [ ] Ambiguous signals include caveats (e.g., "Still Hiring" contextualised by seniority)
- [ ] Employer fill-time comparison shown where data available
- [ ] "Apply" links directly to Greenhouse/Lever posting (no Adzuna)
- [ ] "View all" shows full matching list (paginated)
- [ ] Mobile-responsive layout
- [ ] 3+ beta users have tested and provided feedback
