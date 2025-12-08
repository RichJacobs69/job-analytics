# Epic 5: Job Market Dashboard - Delivery Plan

> **Status:** Phase 0 Complete ✅
> **Created:** 2025-12-07
> **Last Updated:** 2025-12-08
> **Delivery:** Incremental (ship question-by-question)

## Goal

Ship a professional analytics dashboard at `richjacobs.me/projects/job-market` that:
- Answers 5 marketplace questions with interactive visualizations
- Matches your site's existing design system
- Impresses in portfolio reviews and interviews

---

## Key Decisions (Locked In)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **API Architecture** | Next.js API Routes (TypeScript) | Simplest approach; queries Supabase directly from Vercel serverless functions |
| **Chart Library** | **Chart.js** ✅ | Smaller bundle (~60KB vs 400KB), better performance; Tremor incompatible with React 19; Recharts too heavy |
| **Query Strategy** | Supabase JS client for simple queries, SQL functions for complex (UNNEST) | ~5.6K rows allows JS grouping; only skills query needs SQL function |
| **Filtering Location** | Server-side (query params → API routes → Supabase) | Bandwidth efficient, scalable, enables caching |
| **Data Quality Handling** | Subset to Greenhouse for skills/work-arrangement questions | Adzuna truncation causes ~29% skills extraction and F1=0.565 for work arrangement; Greenhouse achieves ~85%+ |
| **Pipeline Freshness** | Infer from `MAX(last_seen_date)` | Uses existing timestamp from pipeline; derived from data |
| **Mobile Responsiveness** | Could-have (defer to v2) | Charts on mobile are complex; focus on desktop-first for portfolio demo |
| **Supabase Security** | Server-side service key only; RLS optional for v1 | API routes are the only access point; no client-side key exposure |
| **Orchestration** | Python pipeline writes independently; portfolio reads only | Later automated via GitHub Actions |

---

## Phase 0: Foundation ✅ COMPLETE

### Deliverable: Technical decisions locked in

**Status:** Completed 2025-12-08

**What Was Built:**

1. ✅ **Supabase Integration**
   - Installed `@supabase/supabase-js` in portfolio-site
   - Created `lib/supabase.ts` - lazy-initialized server-side client
   - Added `.env.local.example` template
   - Configured `.env.local` with Supabase credentials
   - Fixed schema mismatch: using `last_seen_date` instead of non-existent `created_at`

2. ✅ **Test API Route**
   - Created `/api/job-market/test-connection/route.ts`
   - Returns database stats: enriched_jobs count, raw_jobs count, Greenhouse count, cities
   - Validates Supabase connection end-to-end
   - **Tested with Postman** - working ✅

3. ✅ **Shared TypeScript Types**
   - Created `lib/types/job-market.ts`
   - Defined `ApiResponse<T>` wrapper
   - Defined interfaces for all 5 dashboard questions
   - Type-safe contract between API and frontend

4. ✅ **Chart Library POC**
   - Created `/projects/chart-test` comparison page
   - **Tremor eliminated:** Incompatible with React 19
   - Tested Recharts vs Chart.js with exact color palette
   - Side-by-side comparison with pros/cons
   - **Decision: Chart.js** (lighter bundle, good performance)

5. ✅ **Files Created:**
   ```
   portfolio-site/
   ├── .env.local.example
   ├── .env.local (configured)
   ├── lib/
   │   ├── supabase.ts
   │   └── types/job-market.ts
   └── app/
       ├── api/job-market/
       │   └── test-connection/route.ts
       └── projects/chart-test/page.tsx
   ```

**Architectural Decisions Made:**

- **Filtering:** Server-side via query params (not client-side)
- **Query approach:** Supabase JS client for 1-2 dimension grouping, SQL functions only for complex (UNNEST)
- **Data freshness:** Derived from `MAX(last_seen_date)` in enriched_jobs
- **Chart library:** Chart.js for lighter bundle and better performance

**Decision Gate:** ✅ Library chosen, can query Supabase from API route, POC ready for testers

---

## Phase 1: Infrastructure

### Deliverable: Working data pipeline (API to Frontend)

**Tasks:**

1. **Create API structure**
   ```
   /api/job-market/
     ├── test-connection.ts    # Returns COUNT(*) from enriched_jobs
     └── types.ts              # Shared TypeScript interfaces
   ```

   **API contracts (shared across all endpoints):**
   - Query params: `date_range` (default: last 30d), `city` (multi-select), `role_family`
   - Response envelope: `{ data, meta: { last_updated, filters, source_info }, error }`
   - Error handling: Graceful degradation, meaningful error messages

2. **Create dashboard page skeleton**
   ```
   /app/projects/job-market/
     ├── page.tsx           # Main dashboard
     └── layout.tsx         # Inherits site navigation
   ```
   - Empty page inheriting header/footer
   - Fetches test-connection API and displays result
   - Loading state skeleton

3. **Set up shared types**
   ```typescript
   // Example: /lib/types/job-market.ts
   interface JobDemandData {
     city_code: string;
     job_subfamily: string;
     count: number;
   }

   interface ApiResponse<T> {
     data: T;
     meta: {
       last_updated: string;
       total_records: number;
       source: 'all' | 'greenhouse' | 'adzuna';
     };
     error?: string;
   }
   ```

**Decision Gate:** Can fetch data from Supabase and display on page

---

## Phase 2: First Chart

### Deliverable: One complete question with working visualization

**Pick the simplest high-impact question:**
**"Which roles have most job postings by city?"** (MDS001 variant)

**Tasks:**

1. **Write API endpoint**
   - `/api/job-market/role-demand.ts`
   - Query: `SELECT city_code, job_subfamily, COUNT(*) ... GROUP BY ...`
   - Returns JSON array
   - **Data source:** All enriched_jobs (5,629 records) - no quality concerns for simple counts

2. **Build chart component**
   - Create `<RoleDemandChart>` component
   - Grouped bar chart (roles x cities)
   - Basic interactivity (tooltips, legend)
   - Use winning library from Phase 0 POC

3. **Add to dashboard page**
   - Section with title + description
   - Chart with loading state
   - Data source attribution: "Based on X job listings"

4. **Write basic tests**
   - Unit test: API endpoint returns expected shape
   - E2E test: Chart renders with data

**Decision Gate:** One complete question looks good, ready to replicate pattern

---

## Phase 3: Core Analytics

### Deliverable: 4 more questions answered

**Add questions one at a time in priority order:**

### Question 2: "What skills are most in-demand for [role]?" (SGU001)
- **Data source:** Greenhouse only (953 jobs) - skills extraction requires full text
- Interactive: dropdown to select role + city
- Horizontal bar chart (easier to read skill names)
- Shows frequency + percentage
- **Data quality note:** Display "Based on 953 premium company listings"

### Question 3: "What's the remote/hybrid/onsite split by role?" (WAL001)
- **Data source:** Greenhouse only (953 jobs) - work arrangement classification quality
- Stacked bar chart or pie charts
- Filter by city
- Shows percentages prominently
- **Data quality note:** Display source indicator

### Question 4: "Which companies are hiring most actively?" (CP001)
- **Data source:** All enriched_jobs (5,629 records) - company counts are reliable
- Top 10 companies by role type
- Filterable by city + date range
- Bar chart ranked by count

### Question 5: "What experience levels are companies targeting?" (RSR001)
- **Data source:** All enriched_jobs (5,629 records) - seniority is well-classified
- Distribution chart (Junior/Mid/Senior/Staff+)
- Segmented by role subfamily
- Shows hiring reality vs expectations

**Build pattern for each:**
1. API endpoint (query + JSON response)
2. Chart component (reuse styling from first chart)
3. Add to dashboard (consistent layout)
4. Unit test for API
5. E2E test for chart rendering

---

## Phase 4: UX & Interactivity

### Deliverable: Dashboard feels cohesive and polished

**Tasks:**

1. **Add global filters** (affects all charts)
   - Date range picker (last 30/60/90 days, custom)
   - City multi-select (London, NYC, Denver)
   - Role family filter (Product vs Data)

2. **Consistent visual design**
   - Match your site's color palette (lime/emerald accents)
   - Typography hierarchy (Geist Sans/Mono)
   - Spacing/padding system
   - Card/section styling using existing `.card-standard` class

3. **Loading & error states**
   - Skeleton loaders for charts
   - Empty state messaging ("No data for this filter combo")
   - Error handling (API failures with graceful degradation)

4. **Data freshness indicator**
   - "Last updated: [MAX(created_at)]"
   - Derived from query, not separate tracking

**Decision Gate:** Feels like a professional product, not a prototype

---

## Phase 5: Performance & Polish

### Deliverable: Fast, reliable, production-ready

**Tasks:**

1. **Optimize data fetching**
   - Add caching to API routes (stale-while-revalidate)
   - Parallel data fetches where possible
   - Consider pre-loading data on page mount

2. **Chart performance**
   - Limit data points if needed (top 20, not all 500)
   - Debounce filter changes
   - Prefer code-splitting + tree-shaking for chart library
   - Use server components for data fetching where appropriate

3. **Add metadata for portfolio**
   - Page title, description, OG image
   - Clear data source + last updated timestamp
   - "About this data" section explaining methodology

4. **Accessibility basics**
   - Keyboard navigation works
   - Color contrast meets WCAG standards
   - Alt text for charts (for screen readers)

5. **Testing completion**
   - Verify all unit tests pass
   - Verify all E2E tests pass
   - Manual smoke test on production URL

**Decision Gate:** Passes your quality bar for portfolio

---

## Phase 6: Launch Prep

### Deliverable: Deployed and shareable

**Tasks:**

1. **Write project documentation**
   - Add to main site's projects page
   - Brief description of what you built
   - Link to GitHub repo (make public)

2. **Final testing**
   - Test on different browsers (Chrome, Firefox, Safari)
   - Get feedback from 2-3 people

3. **Deploy**
   - Push to GitHub (triggers Vercel deploy)
   - Verify environment variables work in production
   - Test live URL

4. **Share**
   - Add to LinkedIn/portfolio
   - Prepare 2-minute demo walkthrough
   - Document tech stack for interviews

---

## Success Criteria

### Must-have:
- [ ] 5 questions answered with visualizations
- [ ] Consistent with richjacobs.me design
- [ ] Loads in <3 seconds
- [ ] No errors in production
- [ ] "Last updated" derived from data timestamp
- [ ] Data source indicator for quality-sensitive questions
- [ ] Unit tests for API endpoints
- [ ] E2E tests for chart rendering

### Could-have (v2):
- [ ] Mobile-responsive charts
- [ ] Exportable data (CSV download)
- [ ] Shareable filtered views (URL parameters)
- [ ] Analytics tracking (see who's using it)
- [ ] Pre-aggregated summary tables for performance
- [ ] Source quality filter (All vs Greenhouse-only)

---

## Risk Management

| Risk | Mitigation |
|------|-----------|
| Charting library doesn't match design | POC with actual colors in Phase 0, pivot early if needed |
| API queries are slow | Start with simple queries, optimize later; consider caching |
| Scope creep (want to add 10 more questions) | Stick to 5 for v1, create backlog for v2 |
| Styling takes longer than expected | Use existing site utilities (.card-standard, .gradient-text) |
| Supabase connection issues | Server-side only; service key in Vercel env vars |
| Data quality concerns | Subset to Greenhouse for skills/work-arrangement; document data source |

---

## 5 Selected Marketplace Questions

### Question 1: Role Demand by City (MDS001)
**User Story:** "Which job subfamilies are most in-demand in each city?"
**Chart Type:** Grouped bar chart
**Data:** `city_code, job_subfamily, COUNT(*)`
**Source:** All enriched_jobs (5,629)
**Filters:** Date range

### Question 2: Top Skills by Role (SGU001)
**User Story:** "What skills are most frequently listed for Analytics Engineers in London?"
**Chart Type:** Horizontal bar chart
**Data:** `skill, COUNT(*), percentage` from UNNEST(skills)
**Source:** Greenhouse only (953) - requires full text for extraction
**Filters:** Role, City

### Question 3: Working Arrangement Split (WAL001)
**User Story:** "What percentage of Data Engineer jobs are Remote vs Hybrid vs Onsite?"
**Chart Type:** Stacked bar or pie chart
**Data:** `working_arrangement, COUNT(*), percentage`
**Source:** Greenhouse only (953) - work arrangement F1=0.565 for Adzuna
**Filters:** Role, City

### Question 4: Top Hiring Companies (CP001)
**User Story:** "Which companies posted the most Platform PM roles in London last quarter?"
**Chart Type:** Bar chart (top 10)
**Data:** `company_name, COUNT(*)`
**Source:** All enriched_jobs (5,629)
**Filters:** Role, City, Date range

### Question 5: Experience Level Distribution (RSR001)
**User Story:** "What experience ranges are most common for Senior Data roles in Denver?"
**Chart Type:** Stacked bar or distribution chart
**Data:** `seniority_level, COUNT(*), percentage`
**Source:** All enriched_jobs (5,629)
**Filters:** Role, City

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│     richjacobs.me (Next.js 16 on Vercel)                       │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Dashboard Page (/app/projects/job-market/page.tsx)       │ │
│  │  - Global filters (date, city, role)                      │ │
│  │  - 5 chart components                                     │ │
│  │  - Loading/error states                                   │ │
│  │  - Data source indicators                                 │ │
│  └───────────────┬───────────────────────────────────────────┘ │
│                  │ fetch()                                      │
│                  ▼                                              │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  API Routes (/api/job-market/) - Server-side only         │ │
│  │  - role-demand.ts                                         │ │
│  │  - top-skills.ts (Greenhouse source)                      │ │
│  │  - working-arrangement.ts (Greenhouse source)             │ │
│  │  - top-companies.ts                                       │ │
│  │  - experience-distribution.ts                             │ │
│  │                                                           │ │
│  │  Uses: SUPABASE_SERVICE_KEY (never exposed to client)     │ │
│  └───────────────┬───────────────────────────────────────────┘ │
│                  │ SQL over HTTPS                               │
└──────────────────┼──────────────────────────────────────────────┘
                   ▼
           ┌───────────────┐
           │   Supabase    │
           │  (Postgres)   │
           │               │
           │ enriched_jobs │
           │  5,629 rows   │
           └───────┬───────┘
                   │
                   │ Writes (independent)
                   │
    ┌──────────────┴──────────────┐
    │  job-analytics Pipeline     │
    │  (Python, GitHub Actions)   │
    │                             │
    │  - Adzuna API fetch         │
    │  - Greenhouse scraper       │
    │  - Claude classification    │
    │  - Supabase insert          │
    └─────────────────────────────┘
```

---

## Tech Stack Summary

**Frontend (portfolio-site):**
- Next.js 16 (App Router)
- React 19.2.0
- TypeScript
- Tailwind CSS v4
- **Chart.js 4.x + react-chartjs-2** ✅
- Geist fonts

**Backend (portfolio-site):**
- Vercel API Routes (serverless functions)
- Supabase client (server-side only)

**Data Pipeline (job-analytics - separate repo):**
- Python 3.x
- Claude 3.5 Haiku (classification)
- Playwright (Greenhouse scraping)
- Supabase (writes)
- GitHub Actions (orchestration - future)

**Deployment:**
- Vercel (automatic deploys from GitHub)
- Already hosting richjacobs.me

---

## Next Steps (Phase 1: Infrastructure)

**Phase 0 Complete ✅** - Moving to Phase 1

1. **Create dashboard page skeleton** at `/projects/job-market`
   - Inherit site navigation/footer from layout
   - Fetch test-connection API to display database stats
   - Add loading states and error handling
   - Prove end-to-end flow works

2. **Build first API endpoint:** `/api/job-market/role-demand`
   - Query: Fetch `city_code, job_subfamily` from enriched_jobs
   - Group and count in JavaScript
   - Apply server-side filters (city, role_family, date_range)
   - Return formatted JSON with ApiResponse wrapper

3. **Deploy to Vercel for testers**
   - Add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` to Vercel environment variables
   - Push to GitHub (triggers auto-deploy)
   - Test live URL with POC page at `richjacobs.me/projects/chart-test`

**Then proceed to Phase 2: First Chart**
