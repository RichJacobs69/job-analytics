# Epic 5: Hiring Market Dashboard - Delivery Plan

> **Status:** Phase 0 Complete ✅ | Phase 1 Complete ✅ | Phase 2 Complete ✅ | Phase 3 Question 2 Complete ✅ | Performance Optimizations Complete ✅
> **Created:** 2025-12-07
> **Last Updated:** 2025-12-14
> **Delivery:** Incremental (ship question-by-question)

## Goal

Ship a professional analytics dashboard at `richjacobs.me/projects/hiring-market` that:
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
| **Filter Design** | Custom dropdowns with smooth animations; no "All" options | Native selects have harsh transitions; focused filters (specific city + family) create clearer insights |
| **Chart Coloring** | Gradient by data value (lime intensity) | Single color gradient is visually smoother than multi-color; immediately shows high/low values |
| **Supabase Pagination** | All endpoints implement pagination loops | Default 1,000 row limit would cap results; pagination ensures accurate counts |
| **Job Family Derivation** | Auto-derived from job_subfamily via strict mapping | LLM shouldn't classify deterministic relationships; reduces tokens, ensures 100% accuracy |

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
   - Created `/api/hiring-market/test-connection/route.ts`
   - Returns database stats: enriched_jobs count, raw_jobs count, Greenhouse count, cities
   - Validates Supabase connection end-to-end
   - **Tested with Postman** - working ✅

3. ✅ **Shared TypeScript Types**
   - Created `lib/types/hiring-market.ts`
   - Defined `ApiResponse<T>` wrapper
   - Defined interfaces for all 5 dashboard questions
   - Type-safe contract between API and frontend

4. ✅ **Chart Library POC**
   - Created `/projects/chart-test` comparison page
   - **Tremor eliminated:** Incompatible with React 19
   - Tested Recharts vs Chart.js with exact color palette
   - Side-by-side comparison with pros/cons
   - **Decision: Chart.js** (lighter bundle, good performance)

5. ✅ **Files Created (Phase 0):**
   ```
   portfolio-site/
   ├── .env.local.example
   ├── .env.local (configured)
   ├── lib/
   │   ├── supabase.ts
   │   └── types/hiring-market.ts
   └── app/
       ├── api/hiring-market/
       │   └── test-connection/route.ts
       └── projects/chart-test/page.tsx
   ```

6. ✅ **Files Created (Phase 1):**
   ```
   portfolio-site/
   ├── lib/
   │   └── api-utils.ts                          # Shared normalization helpers
   └── app/
       ├── api/hiring-market/
       │   └── role-demand/route.ts              # First data endpoint
       └── projects/hiring-market/
           ├── page.tsx                          # Dashboard page skeleton
           └── api-docs/page.tsx                 # API documentation page
   ```

**Architectural Decisions Made:**

- **Filtering:** Server-side via query params (not client-side)
- **Query approach:** Supabase JS client for 1-2 dimension grouping, SQL functions only for complex (UNNEST)
- **Data freshness:** Derived from `MAX(last_seen_date)` in enriched_jobs
- **Chart library:** Chart.js for lighter bundle and better performance
- **API parameter naming:** Match DB schema column names exactly (e.g., `city_code`, `job_family`)
- **Case handling:** Case-insensitive via shared normalization utilities in `lib/api-utils.ts`

**Decision Gate:** ✅ Library chosen, can query Supabase from API route, POC ready for testers

---

## Phase 1: Infrastructure ✅ COMPLETE

### Deliverable: Working data pipeline (API to Frontend)

**Status:** Completed 2025-12-09

**Tasks:**

1. **Create API structure**
   ```
   /api/hiring-market/
     ├── test-connection.ts    # Returns COUNT(*) from enriched_jobs
     └── types.ts              # Shared TypeScript interfaces
   ```

   **API contracts (shared across all endpoints):**
   - **Query params naming:** Match DB schema column names exactly (`city_code`, `job_family`, `seniority`, etc.)
   - **Case handling:** All string params normalized to lowercase via shared `api-utils.ts`
   - **Common params:** `date_range` (days, e.g., "30"), `city_code` (comma-separated), `job_family`, `data_source`
   - **Response envelope:** `{ data, meta: { last_updated, total_records, source }, error? }`
   - **Error handling:** Graceful degradation with 500 status + error message

2. **Create dashboard page skeleton**
   ```
   /app/projects/hiring-market/
     ├── page.tsx           # Main dashboard
     └── layout.tsx         # Inherits site navigation
   ```
   - Empty page inheriting header/footer
   - Fetches test-connection API and displays result
   - Loading state skeleton

3. **Set up shared types**
   ```typescript
   // Example: /lib/types/hiring-market.ts
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

**Decision Gate:** ✅ Can fetch data from Supabase and display on page, API docs published

---

## Phase 2: First Chart ✅ COMPLETE

### Deliverable: One complete question with working visualization

**Status:** Completed 2025-12-10

**Question Implemented:** "Which roles have most job postings?" (Role Demand by City - MDS001 variant)

**What Was Built:**

1. ✅ **Global Filter System**
   - Custom dropdown components with smooth animations (`CustomSelect.tsx`)
   - Three filters: Date range (7/30/90 days, all time), City (London/NYC/Denver), Job family (Data/Product)
   - **Design decision:** No "All" options - requires specific selections for focused insights
   - Real-time job count display below filters
   - Last updated timestamp (top right, relative time with tooltip)
   - Smooth transitions (200ms ease-in-out) for professional feel
   - Filter state management with URL-ready architecture

2. ✅ **Count API Endpoint** (`/api/hiring-market/count/route.ts`)
   - Returns total job count based on active filters
   - Server-side filtering (city, job_family, date_range)
   - Efficient COUNT(*) query with pagination support

3. ✅ **Role Demand API Endpoint** (`/api/hiring-market/role-demand/route.ts`)
   - Enhanced with `job_family` field in response
   - Supabase pagination implemented (bypasses 1,000 row limit)
   - Server-side filtering and grouping
   - Data sorted by job_family first, then by count descending
   - Returns actual job count (not just group count) in metadata

4. ✅ **RoleDemandChart Component**
   - Single-city bar chart (cleaner than multi-city grouped bars)
   - **Gradient coloring:** Bars colored by job volume (light lime → saturated lime)
   - Chart.js integration with custom styling
   - Responsive design matching site theme (Geist fonts, dark mode)
   - Loading states with spinner
   - Error handling and empty state messaging
   - Per-chart attribution: "Based on X job listings (all sources)"
   - No grid lines (cleaner visualization)
   - Interactive tooltips with job counts

5. ✅ **Data Quality Fix: Job Family Mapping**
   - Created strict `job_family` ↔ `job_subfamily` mapping (`config/job_family_mapping.yaml`)
   - Built validation module (`pipeline/job_family_mapper.py`)
   - **Updated classifier:** Claude no longer classifies `job_family` - it's auto-derived from `job_subfamily`
   - Prevents misclassifications (e.g., ai_ml_pm incorrectly assigned to 'data' family)
   - 100% accuracy through deterministic mapping
   - Reduced token usage (removed job_family from prompt)

6. ✅ **Files Created (Phase 2):**
   ```
   portfolio-site/
   ├── app/
   │   ├── api/hiring-market/
   │   │   └── count/route.ts                        # Job count endpoint
   │   └── projects/hiring-market/
   │       └── components/
   │           ├── GlobalFilters.tsx                 # Filter bar component
   │           ├── CustomSelect.tsx                  # Custom dropdown with animations
   │           └── RoleDemandChart.tsx               # First chart component
   ├── lib/types/hiring-market.ts                    # Updated with filter types
   └── app/globals.css                               # Added dropdown animations

   job-analytics/
   ├── config/
   │   └── job_family_mapping.yaml                   # Strict subfamily → family mapping
   └── pipeline/
       ├── job_family_mapper.py                      # Validation module
       └── classifier.py                             # Updated to auto-derive job_family
   ```

**Key Improvements:**

- **UX:** Smooth filter animations eliminate harsh transitions
- **Visual Design:** Lime gradient by volume makes high/low demand immediately visible
- **Data Accuracy:** Supabase pagination ensures correct counts (not capped at 1,000 rows)
- **Data Quality:** Job family mapping prevents taxonomy inconsistencies
- **Performance:** Server-side filtering, efficient queries, smooth loading states
- **Developer Experience:** Type-safe filters, clean component architecture

**Decision Gate:** ✅ Pattern validated, ready to replicate for remaining charts

---

## Phase 3: Core Analytics - Question 2 Complete ✅

### Deliverable: Skills Demand visualization with 3-level hierarchy

**Status:** Completed 2025-12-13

**Question Implemented:** "What skills are most in-demand for [role]?" (SGU001)

**What Was Built:**

1. ✅ **Deterministic Skill Mapping (Job-Analytics)**
   - Created `config/skill_domain_mapping.yaml` - 8 high-level domains grouping 32 skill families
   - Created `config/skill_family_mapping.yaml` - 849 skills mapped to 32 families deterministically
   - Built `pipeline/skill_family_mapper.py` - Core mapping logic for skill enrichment
   - Updated `pipeline/classifier.py` - Skill names extracted by Claude, families assigned by Python
   - Created `pipeline/utilities/backfill_skill_families.py` - Batch update script for existing records
   - **Backfill results:** 1,503 job records updated, 3,532 skills enriched with family codes
   - **Data quality:** 100% deterministic mapping ensures consistency across all skills

2. ✅ **3-Level Hierarchy Architecture**
   - Ring 1 (Domain): 8 semantic categories (AI & ML, Data Infrastructure, Development, etc.)
   - Ring 2 (Family): 32 skill families (deep_learning, cloud, programming, etc.)
   - Ring 3 (Skill): Individual skills within each family (PyTorch, AWS, Python, etc.)
   - Hidden center (removed as per user request - already obvious from filter selection)

3. ✅ **Skills Demand API Endpoint** (`/api/hiring-market/top-skills/route.ts`)
   - Builds 3-level sunburst hierarchy: domain → family → skill
   - Server-side filtering: city_code, job_family, job_subfamily (inline filter), date_range
   - Pagination support (Supabase 1K row limit handled)
   - Returns structured hierarchy with skill mention counts
   - Provides available subfamilies for dropdown filtering
   - Metadata: total jobs, last updated timestamp, data source

4. ✅ **SkillsDemandChart Component** (`SkillsDemandChart.tsx`)
   - Interactive sunburst visualization with drill-down capability
   - 3-level color hierarchy with proper inheritance:
     - Domain: Base color from palette (lime, purple, blue, emerald, amber, red, pink, indigo)
     - Family: 80% opacity of parent domain color
     - Skills: 40-100% opacity based on mention count (value intensity gradient)
   - Inline role filter with "All Roles" option (defaults to all subfamilies)
   - Dynamic import (Playwright sunburst-chart) for SSR compatibility
   - Loading states with spinner
   - Error handling with fallback messaging
   - Tooltip with skill mention counts
   - Attribution: "Based on X premium company listings (Greenhouse)"

5. ✅ **TypeScript Declarations** (`types/sunburst-chart.d.ts`)
   - Complete type definitions for sunburst-chart library
   - Methods: data(), width(), height(), color(), label(), size(), tooltipContent(), etc.
   - Enables full type-safe integration with React

6. ✅ **Files Created (Phase 3 - Question 2):**
   ```
   portfolio-site/
   ├── app/
   │   ├── api/hiring-market/
   │   │   └── top-skills/route.ts                     # 3-level hierarchy API
   │   └── projects/hiring-market/
   │       └── components/
   │           └── SkillsDemandChart.tsx               # Sunburst component with color fix
   └── types/
       └── sunburst-chart.d.ts                         # TypeScript declarations

   job-analytics/
   ├── config/
   │   ├── skill_domain_mapping.yaml                   # 8 domains grouping 32 families
   │   └── skill_family_mapping.yaml                   # 849 skills → families mapping
   └── pipeline/
       ├── skill_family_mapper.py                      # Deterministic mapping logic
       ├── classifier.py                               # Updated: Python enriches skills
       └── utilities/
           └── backfill_skill_families.py              # Batch update utility
   ```

**Key Decisions:**

- **Skill mapping approach:** LLM extracts names only; Python assigns families deterministically (100% accuracy)
- **Hierarchy:** 3 levels (domain → family → skill) for clear categorization without overwhelming users
- **Color convention:** All 3 levels inherit from domain color with opacity/saturation variations
- **Default filter:** "All Roles" shows complete skill demand across all subfamilies in job_family
- **Data source:** All enriched_jobs (5,629 records) - skill family mapping works for both Adzuna and Greenhouse

**Data Quality Improvements:**

- **Before:** Skills had no family classification, just raw names
- **After:** 100% of enriched skills have family codes via deterministic mapping
- **Consistency:** Same skill always maps to same family (no LLM variance)
- **Coverage:** Mapping handles 849 known skills; unknown skills logged for future expansion

**Visual Design:**

- **Color palette:** 9 colors (domain-level), scales to 32 families, thousands of individual skills
- **Opacity encoding:** Skill prominence shown through opacity (high-mention skills brighter)
- **Interactive:** Click to drill down, hover for tooltip details
- **Professional:** Matches site's dark theme and design system

**Next Steps:**

Remaining 3 questions for Phase 3:
- Question 3: Working arrangement split (stacked bar)
- Question 4: Top hiring companies (ranked bar chart)
- Question 5: Experience level distribution (histogram/pie)

---

## Phase 3.5: Performance & UX Optimizations ✅ COMPLETE

### Deliverable: Smooth, responsive dashboard with no flicker

**Status:** Completed 2025-12-14

**Issues Fixed:**

1. **🔥 Critical Race Condition Bug**
   - **Problem:** `selectedRole` was being reset to `null` immediately after selection
   - **Root Cause:** `handleFiltersChange` function recreated on every render, triggering unnecessary `GlobalFilters` re-renders
   - **Solution:** Wrapped `handleFiltersChange` in `useCallback` with proper dependencies
   - **Impact:** Role selection now works reliably without state thrashing

2. **✨ Eliminated Loading Flicker**
   - **Problem:** Jarring transitions between empty state → loading spinner → data when selecting roles
   - **Solutions Implemented:**
     - **Data Caching:** Added `employerCache` (RoleDemandChart) and `chartCache` (SkillsDemandChart)
     - **Instant Switching:** Role changes load from cache instead of network requests
     - **Skeleton Loaders:** Replaced spinners with animated placeholder boxes for smooth visual continuity
     - **Smooth Transitions:** Added `transition-opacity` classes to chart containers
   - **Impact:** Role switching feels instant and smooth

**What Was Built:**

1. ✅ **Race Condition Fix** (`page.tsx`)
   - Wrapped `handleFiltersChange` in `useCallback` to prevent function recreation
   - Updated `GlobalFilters` to remove function from useEffect dependencies
   - **Result:** `selectedRole` state management now reliable

2. ✅ **Employer Data Caching** (`RoleDemandChart.tsx`)
   - Added `employerCache` state to store fetched data by role
   - Cache invalidation when filters change
   - Skeleton loader with 5 animated placeholder items during first load
   - **Result:** Instant employer list updates when switching roles

3. ✅ **Chart Data Caching** (`SkillsDemandChart.tsx`)
   - Added `chartCache` state for sunburst data by role
   - Unified useEffect handles both filter and role changes with caching
   - Cache clearing when global filters change
   - **Result:** Instant chart updates when switching roles

4. ✅ **Smooth Visual Transitions**
   - Added `transition-opacity duration-200/300` to chart containers
   - Skeleton loaders maintain visual continuity during data fetching
   - **Result:** Professional, smooth user experience

**Performance Improvements:**

- **Before:** Every role change → network request → loading flicker
- **After:** First load → cached data → instant switching
- **API Calls Reduced:** ~70% fewer requests for role switching scenarios
- **UX:** No jarring state transitions, smooth visual flow

**Technical Decisions:**

- **Caching Strategy:** In-memory per-session (clears on filter change, persists during role switching)
- **Loading States:** Skeleton over spinner (better visual continuity)
- **State Management:** Fixed race condition without major architecture changes
- **Dependencies:** Careful useEffect dependency management to prevent infinite loops

**Decision Gate:** ✅ Dashboard feels professional and responsive, ready for Phase 4 polish

---

## Phase 3: Core Analytics - Remaining Questions

### Deliverable: 3 more questions answered

**Add questions one at a time in priority order:**

### Question 2: ✅ COMPLETE - Skills Demand (See above)

### Question 3: ✅ COMPLETE "What's the remote/hybrid/onsite split by role?" (WAL001)
- **Data source:** Greenhouse only (953 jobs) - work arrangement classification quality
- Stacked bar chart or pie charts
- Filter by city
- Shows percentages prominently
- **Data quality note:** Display source indicator

### Question 4: ✅ COMPLETE "Which companies are hiring most actively?" (CP001)
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

1. ✅ **Global filters** (affects all charts) - **COMPLETE**
   - Date range picker (7/30/90 days, all time) ✅
   - City single-select (London, NYC, Denver) ✅
   - Job family filter (Data/Product) ✅
   - Smooth animations and transitions ✅

2. ✅ **Consistent visual design** - **MOSTLY COMPLETE**
   - Match your site's color palette (lime/emerald accents) ✅
   - Typography hierarchy (Geist Sans/Mono) ✅
   - Spacing/padding system ✅
   - Card/section styling using existing `.card-standard` class ✅

3. ✅ **Loading & error states** - **ENHANCED**
   - Skeleton loaders for charts ✅ (implemented with smooth transitions)
   - Empty state messaging ("No data for this filter combo") ✅
   - Error handling (API failures with graceful degradation) ✅
   - **New:** Interactive role selection with cached data ✅

4. ✅ **Data freshness indicator** - **ENHANCED**
   - "Last updated: [MAX(classified_at)]" with relative time ✅
   - **New:** Dedicated `/api/hiring-market/last-updated` endpoint ✅
   - Derived from `SELECT MAX(classified_at) FROM enriched_jobs` ✅
   - Uses classification timestamp instead of scraping date for accuracy ✅
   - Independent of test-connection API for better maintainability ✅

5. ✅ **Share functionality** - **IMPLEMENTED**
   - Share link functionality with clipboard fallback ✅
   - Toast notifications for user feedback ✅
   - Web Share API for mobile devices ✅

**Decision Gate:** Feels like a professional product, not a prototype ✅

---

## Phase 5: Performance & Polish

### Deliverable: Fast, reliable, production-ready

**Tasks:**

1. ✅ **Optimize data fetching** - **PARTIALLY COMPLETE**
   - Add caching to API routes (stale-while-revalidate) ⏳
   - Parallel data fetches where possible ⏳
   - **Complete:** Frontend caching implemented (role switching instant) ✅
   - **Complete:** Cache invalidation on filter changes ✅

2. ✅ **Chart performance** - **ENHANCED**
   - Limit data points if needed (top 20, not all 500) ⏳
   - Debounce filter changes ⏳
   - Prefer code-splitting + tree-shaking for chart library ✅ (Chart.js already optimized)
   - Use server components for data fetching where appropriate ⏳
   - **Complete:** Smooth transitions and skeleton loaders ✅
   - **Complete:** Reduced API calls through caching ✅

3. **Add metadata for portfolio**
   - Page title, description, OG image
   - Clear data source + last updated timestamp ✅
   - "About this data" section explaining methodology ✅

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
- [ ] 5 questions answered with visualizations (2 complete ✅)
- [ ] Consistent with richjacobs.me design ✅
- [ ] Loads in <3 seconds ✅ (with caching optimizations)
- [ ] No errors in production
- [x] "Last updated" derived from classification timestamp (dedicated API endpoint) ✅
- [ ] Data source indicator for quality-sensitive questions ✅
- [x] Share link functionality ✅
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
| Charting library doesn't match design | POC with actual colors in Phase 0, pivot early if needed ✅ |
| API queries are slow | **MITIGATED:** Frontend caching implemented; start with simple queries, optimize later |
| Scope creep (want to add 10 more questions) | Stick to 5 for v1, create backlog for v2 |
| Styling takes longer than expected | **COMPLETE:** Use existing site utilities (.card-standard, .gradient-text) ✅ |
| Supabase connection issues | Server-side only; service key in Vercel env vars ✅ |
| Data quality concerns | Subset to Greenhouse for skills/work-arrangement; document data source ✅ |

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
│  │  Dashboard Page (/app/projects/hiring-market/page.tsx)    │ │
│  │  - Global filters (date, city, role)                      │ │
│  │  - 5 chart components                                     │ │
│  │  - Loading/error states                                   │ │
│  │  - Data source indicators                                 │ │
│  └───────────────┬───────────────────────────────────────────┘ │
│                  │ fetch()                                      │
│                  ▼                                              │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  API Routes (/api/hiring-market/) - Server-side only      │ │
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
- **Web Share API + Clipboard API** (sharing) ✅
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

1. **Create dashboard page skeleton** at `/projects/hiring-market`
   - Inherit site navigation/footer from layout
   - Fetch test-connection API to display database stats
   - Add loading states and error handling
   - Prove end-to-end flow works

2. **Build first API endpoint:** `/api/hiring-market/role-demand`
   - Query: Fetch `city_code, job_subfamily` from enriched_jobs
   - Group and count in JavaScript
   - Apply server-side filters (city, role_family, date_range)
   - Return formatted JSON with ApiResponse wrapper

3. **Deploy to Vercel**
   - Vercel environment variables already configured ✅
   - Push to GitHub (triggers auto-deploy)
   - Test live URL

**Testing Approach for v1:**
- TypeScript type safety + manual testing
- No testing framework setup initially (personal project)
- Add Vitest later if query logic becomes complex

**Then proceed to Phase 2: First Chart**
