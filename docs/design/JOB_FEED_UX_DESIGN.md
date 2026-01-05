# Job Feed UX Design

**Epic:** EPIC-008 Curated Job Feed
**Version:** 1.5
**Date:** 2026-01-05
**Status:** Employer Context Enhancement

---

## Design Principles

1. **Mobile-first** - Job seekers search across devices; touch-friendly by default
2. **Progressive disclosure** - Show essentials upfront, details on demand
3. **Information density** - Use horizontal space efficiently; no wasted real estate
4. **Honest UI** - Caveats for ambiguous signals; no false promises
5. **Sequential scanning** - Groups stacked vertically for focused review

---

## Information Architecture

### Page Hierarchy

```
/projects/hiring-market/jobs
    |
    +-- Header (back link, title, job count)
    |
    +-- Filter Bar (sticky)
    |       Desktop: inline pills
    |       Mobile: collapsed button -> bottom sheet
    |
    +-- Filter Summary ("Your filters: London, Data, Senior+")
    |
    +-- Job Groups (stacked vertically, separated by dividers)
    |       1. Fresh Matches
    |       2. Still Hiring
    |       3. Scaling Teams
    |       4. Remote Friendly
    |       5. Top Compensation (US only)
    |
    +-- Footer (data source info, link to dashboard)
```

### Group Order Rationale

| Order | Group | Why First/Last |
|-------|-------|----------------|
| 1 | Fresh Matches | Highest urgency - early applicant advantage |
| 2 | Still Hiring | Active roles, employer context |
| 3 | Scaling Teams | Volume signal, growth indicator |
| 4 | Remote Friendly | Arrangement preference |
| 5 | Top Compensation | US-only caveat, salary-focused subset |

---

## Component Specifications

### JobCard (Collapsed)

**3-Column Layout (Desktop):**

```
+------------------------------------------------------------------------+
| LEFT (flex-1)                       | CENTER (max-w-280)  | RIGHT       |
| Title (lg, semibold, white)         | [Skill] [Skill]     | [Details v] |
| [Logo] Company . London . Hybrid    | [Skill] [Skill] +N  | [Apply]     |
| Posted 2d ago . GBP90-120k [FinTech]|                     |             |
+------------------------------------------------------------------------+
    ^                             ^
  24px avatar              Muted industry badge
  (rounded-full)           at END of row 3
```

**Mobile Layout:**

```
+----------------------------------+
| Title                   [v][Apply]|
| [Logo] Company . London . Hybrid |
| 2d ago . GBP90k [FinTech]        |
|----------------------------------|
| [Skill] [Skill] [Skill] [Skill]  |
+----------------------------------+
```

**Company Logo (NEW):**
- Size: 24px (collapsed), 48px (expanded)
- Style: `rounded-full` (circular)
- Fallback: Company initial in circle (`bg-gray-700 text-gray-300`)
- Position: Left of company name on row 2

**Industry Badge (NEW):**
- Position: End of row 3 (after salary)
- Style: Same muted style as skills (`bg-gray-800/40 text-gray-500 text-xs rounded-md`)
- Fallback: Hide entirely if industry is null or "other"

**Specifications:**

| Element | Desktop | Mobile |
|---------|---------|--------|
| Title | `text-lg font-semibold text-white truncate` | `text-base` |
| Meta | `text-sm text-gray-400` | Same |
| Skills | `text-xs bg-gray-800/40 text-gray-500 rounded-md select-none cursor-default` | Same |
| Salary | `text-xs text-gray-400` | Same |
| Details | `text-xs text-gray-500` with chevron | Icon only on mobile |
| Apply | `bg-lime-500/10 text-lime-400 px-4 py-2` | Same |

**Skills Note:** Skills are display-only labels, not interactive filters. Muted styling prevents rage clicks.

**States:**

| State | Style |
|-------|-------|
| Default | `bg-[#1a1a1a] border border-gray-800` |
| Hover | `hover:bg-[#1f1f1f] hover:border-gray-700` |
| Expanded | `ring-1 ring-lime-500/20` |

### JobCard (Expanded)

```
+------------------------------------------------------------------------+
| [Collapsed header - logo, title, company, location, salary, industry]  |
| [Collapse button only - no Apply]                                      |
|------------------------------------------------------------------------|
| ABOUT THIS ROLE (2/3)              |  SKILLS (1/3)                     |
| [AI summary paragraph]             |  [Python] [SQL] [ML]              |
|                                    |  [Experimentation] [A/B Testing]  |
|------------------------------------------------------------------------|
| INSIGHTS                                                               |
| [check] Posted 1 day ago   [check] 4 similar roles   [check] Top 25%  |
|------------------------------------------------------------------------|
| ABOUT STRIPE                                                           |
| [FinTech] [Public] | San Francisco, US | 12 open roles                |
|                                                                        |
| Stripe is a financial infrastructure platform for the internet...      |
| [Show more]                                                            |
|------------------------------------------------------------------------|
| [Stripe careers]                              [Apply to this role]     |
+------------------------------------------------------------------------+
```

**Section Order:**
1. About This Role + Skills (2-column grid)
2. Insights (horizontal pills)
3. About Company (merged: metadata + truncated narrative)
4. CTAs

**About Company Section (Merged):**

| Element | Style |
|---------|-------|
| Section heading | `text-xs uppercase tracking-wide text-gray-500` |
| Industry badge | `bg-gray-800/40 text-gray-500 text-xs rounded-md` |
| Ownership badge | Same muted style (only show public/acquired) |
| Size badge | Same muted style (startup/scale-up/enterprise) |
| Parent company badge | Same muted style (e.g., "Alphabet" for YouTube) |
| HQ location | `text-sm text-gray-400` inline after badges |
| Open roles count | `text-sm text-gray-400` inline |
| Description | `text-sm text-gray-300 line-clamp-2` (truncated to 2 lines) |
| Show more link | `text-lime-400 text-xs` reveals full description |

**Metadata Line Order:** `[Industry] [Ownership] [Size] [Parent?] | HQ | Open roles`

**Example with parent:** `[Video Platform] [Public] [Enterprise] [Alphabet] | San Bruno, US | 8 open roles`

**Data Fallbacks:**

| Missing Data | Fallback |
|--------------|----------|
| No logo | Show company initial in circle (in header) |
| No industry | Hide badge (don't show "Other") |
| No description | Hide entire company section |
| No HQ | Omit from metadata line |
| No ownership type | Hide badge |
| No employer_size | Hide badge |
| No parent_company | Hide badge (most companies don't have one) |
| No open roles count | Omit from metadata line |

### JobFeedGroup

```
+------------------------------------------------------------------------+
| [icon] GROUP LABEL (count)                                             |
| Tagline describing the group                                           |
| Caveat in italic if applicable                                         |
|------------------------------------------------------------------------|
| [JobCard]                                                              |
| [JobCard]                                                              |
| [JobCard]                                                              |
| [Show X more]                                                          |
+------------------------------------------------------------------------+
```

**Group Icons:**

| Group | Icon | Color |
|-------|------|-------|
| Fresh Matches | sparkles | lime-400 |
| Still Hiring | clock | lime-400 |
| Scaling Teams | trending-up | lime-400 |
| Remote Friendly | globe | lime-400 |
| Top Compensation | dollar-sign | lime-400 |

### JobFilters

**Desktop (Inline with Separators):**

```
+------------------------------------------------------------------------------------------------------+
| [City v] | [Industry v] | [Data] [Product] [Delivery] [+ Roles v] | [Jr] [Mid] [Sr] [Staff+] | [Has Salary] | Reset (n)
+------------------------------------------------------------------------------------------------------+
              ^
        NEW: Industry dropdown (19 options)
```

**Industry Filter (NEW):**

Position: After City dropdown, before Job Family pills.

```
+----------------------------------+
| All Industries                   |  <- Default/clear option
|----------------------------------|
| TECHNOLOGY                       |  <- Group header (not selectable)
|   AI/ML                          |
|   DevTools                       |
|   Data Infrastructure            |
|   Cybersecurity                  |
|----------------------------------|
| FINANCE                          |
|   FinTech                        |
|   Financial Services             |
|   Crypto & Web3                  |
|----------------------------------|
| COMMERCE                         |
|   E-commerce & Marketplace       |
|   MarTech                        |
|----------------------------------|
| SERVICES                         |
|   HealthTech                     |
|   EdTech                         |
|   HR Tech                        |
|   Professional Services          |
|----------------------------------|
| OTHER                            |
|   Consumer                       |
|   Mobility & Logistics           |
|   PropTech                       |
|   Climate Tech                   |
|   Hardware & Robotics            |
|   Other                          |
+----------------------------------+
```

**Dropdown Behavior:**
- Single select (not multi-select)
- Groups are visual headers only
- "All Industries" clears filter
- URL param: `?industry=fintech`
- Match City dropdown styling

**Job Family Hierarchy:**

```
Data (9 roles)           Product (6 roles)       Delivery (4 roles)
+- data_analyst          +- product_manager      +- delivery_manager
+- data_engineer         +- core_pm              +- project_manager
+- analytics_engineer    +- growth_pm            +- programme_manager
+- data_scientist        +- platform_pm          +- scrum_master
+- ml_engineer           +- technical_pm
+- ai_engineer           +- ai_ml_pm
+- research_scientist_ml
+- data_architect
+- product_analytics
```

**"+ Roles" Dropdown:**

```
+----------------------------------+
| DATA                             |
| [Data Analyst] [Data Engineer]   |
| [Analytics Engineer] ...         |
|                                  |
| PRODUCT                          |
| [Product Manager] [Core PM] ...  |
|                                  |
| DELIVERY                         |
| [Delivery Manager] ...           |
+----------------------------------+
```

**Mobile (Collapsed -> Bottom Sheet):**

```
+----------------------------------+
| [Filters (3)]           [Reset]  |
+----------------------------------+
          |
          v (tap)
+----------------------------------+
| Filters                      [X] |
|----------------------------------|
| Location                         |
| [Dropdown]                       |
|                                  |
| Industry                    NEW  |
| [Dropdown - grouped]             |
|                                  |
| Job Family                       |
| [Data] [Product] [Delivery]      |
|                                  |
| Specific Roles                   |
| DATA: [pill] [pill] ...          |
| PRODUCT: [pill] [pill] ...       |
| DELIVERY: [pill] [pill] ...      |
|                                  |
| Seniority                        |
| [Jr] [Mid] [Sr] [Staff+]         |
|                                  |
| Compensation (US only)           |
| [Has Salary]                     |
|                                  |
| [Apply Filters]                  |
+----------------------------------+
```

**Filter Pills:**

| State | Style |
|-------|-------|
| Inactive | `bg-gray-800 text-gray-400 border-transparent rounded-full` |
| Active | `bg-lime-500/20 text-lime-400 border-lime-500/30 rounded-full` |

**Salary Toggle (US Cities Only):**

Shown only when city is New York, Denver, or San Francisco (salary transparency laws).
Displayed as a toggle pill for visual consistency with other filters.

---

## Responsive Breakpoints

| Breakpoint | Width | Layout Changes |
|------------|-------|----------------|
| Mobile | < 640px | Single column, skills below, filter sheet |
| Tablet (sm) | 640px+ | Skills inline, filter bar visible |
| Desktop (lg) | 1024px+ | Full 3-column cards, more skills visible |

---

## User Flows

### Flow A: Dashboard to Jobs

```
Dashboard (/projects/hiring-market)
    |
    +-- User sets filters (city, job_family)
    |
    +-- CTA appears: "View 47 matching jobs"
    |
    +-- Click -> /jobs?city=london&job_family=data
    |
    +-- Job Feed loads with filters pre-populated
```

### Flow B: Direct Entry (Returning User)

```
Bookmark or direct link
    |
    +-- /jobs (no params)
    |
    +-- Load preferences from localStorage
    |
    +-- Show personalized feed
```

### Flow C: Job Application

```
Job Feed
    |
    +-- Scan cards (title, company, skills visible)
    |
    +-- Click card to expand
    |       |
    |       +-- Read summary
    |       +-- Review fit signals
    |
    +-- Click "Apply" -> Opens ATS in new tab
```

---

## Accessibility Checklist

| Requirement | Implementation |
|-------------|----------------|
| Focus visible | Custom lime ring on interactive elements |
| Keyboard nav | Tab through cards, Enter to expand |
| Touch targets | Min 44x44px on all buttons |
| Color contrast | 4.5:1 for text, 3:1 for UI |
| Screen reader | `aria-expanded` on cards, `aria-label` on buttons |
| Reduced motion | Respect `prefers-reduced-motion` |
| **Company logo** | `alt="{companyName} logo"` or decorative `aria-hidden` |
| **Industry badge** | `aria-label="Industry: FinTech"` |
| **Company section** | `<h3>` or `role="heading" aria-level="3"` |
| **Website link** | `target="_blank" rel="noopener noreferrer"` + external icon |
| **Industry dropdown** | Proper `aria-label`, keyboard navigable groups |

---

## File Structure

```
app/projects/hiring-market/jobs/
    |-- page.tsx                 # Main feed page
    +-- components/
        |-- JobCard.tsx          # Expandable job card (add logo + industry)
        |-- JobFeedGroup.tsx     # Group container
        |-- JobFilters.tsx       # Filter bar + mobile sheet (add industry)
        +-- CompanyLogo.tsx      # NEW: Avatar with initial fallback
```

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| JobCard | [DONE] | 3-column layout, expand/collapse, context fetch on expand |
| JobFeedGroup | [DONE] | Accepts API format, vertical + horizontal layouts |
| JobFilters | [DONE] | Desktop inline, mobile sheet, family hierarchy |
| Page layout | [DONE] | Stacked groups with dividers |
| API integration | [DONE] | Live data from /feed endpoint with filter params |
| Relevance sorting | [DONE] | Location primacy > freshness > filter matches |
| Exclusive group routing | [DONE] | Each job in exactly one group (no duplicates) |
| Loading skeletons | [DONE] | Skeleton cards while loading |
| Empty states | [DONE] | No results messaging with reset button |
| Error states | [DONE] | Error display with retry button |
| localStorage | [TODO] | Persist filter preferences |
| Dashboard CTA | [TODO] | "View X jobs" button |
| **CompanyLogo** | [TODO] | **NEW:** 24px avatar with initial fallback |
| **Industry badge** | [TODO] | **NEW:** Muted badge on row 3 (after salary) |
| **Company context section** | [TODO] | **NEW:** Full employer profile in expanded view |
| **Industry filter** | [TODO] | **NEW:** Grouped dropdown after City |
| **API: employer fields** | [TODO] | **NEW:** Add logo_url, industry, description to response |

---

## Design Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-03 | Single column over 2-column | Users review groups sequentially, not in parallel |
| 2026-01-03 | Skills in center column | Better use of horizontal space; quick tech stack scan |
| 2026-01-03 | Vertical layout over horizontal scroll | Easier expand/collapse; better for detailed review |
| 2026-01-03 | Dividers between groups | Clear visual separation for focused scanning |
| 2026-01-03 | Mobile skills below content | No room inline; separate row maintains readability |
| 2026-01-03 | Muted skill badges (no border) | Prevents rage clicks - skills look like labels, not buttons |
| 2026-01-03 | "Details" text + chevron | Clearer affordance than icon-only expand trigger |
| 2026-01-03 | Family pills + roles dropdown | 19 subfamilies too many for flat pills; hierarchy scales |
| 2026-01-03 | Salary as toggle pill | Visual consistency; checkbox looked out of place |
| 2026-01-03 | US-only salary filter | Only NY, CO, CA have transparency laws; honest about data limits |
| 2026-01-03 | Visual separators in filter bar | Groups related controls; reduces cognitive load |
| 2026-01-03 | Relevance scoring | Location primacy (100) > Freshness (0-50) > Filter matches (10 each) |
| 2026-01-03 | Exclusive group routing | Remote > Fresh > Top Comp > Still Hiring > Scaling; no duplicates |
| 2026-01-03 | Post-filter country-scoped remote | PostgREST limitation; filter wrong-country remote in application layer |
| 2026-01-03 | Context fetch on expand | Lazy load summary + fit signals to reduce initial payload |
| 2026-01-03 | Disabled Apply button | Grayed out when posting URL unavailable; prevents broken links |
| 2026-01-05 | Logo on collapsed card | 24px avatar left of company name adds visual recognition at glance |
| 2026-01-05 | Industry badge on row 3 | After salary, less prominent than company name; doesn't crowd row 2 |
| 2026-01-05 | Industry dropdown (grouped) | 19 categories grouped into 5 logical groups for easier scanning |
| 2026-01-05 | Logo fallback = initial | Show first letter in circle when logo_url is missing |
| 2026-01-05 | Hide "Other" industry | Don't display uninformative badge; only show meaningful categories |
| 2026-01-05 | Merged company section | Combine profile + about into one section; metadata pills above truncated narrative |
| 2026-01-05 | Truncated description | 2-line clamp with "Show more" - reduces info overload, respects attention |
| 2026-01-05 | Remove "Founded" year | Not relevant to job application decision; reduces noise |
| 2026-01-05 | Insights rename | Changed from "Why This Might Fit" - old name implied preference matching |
| 2026-01-05 | Data-driven insights only | Removed tautological signals like "Hybrid matches filter"; keep non-obvious data |
| 2026-01-05 | Remove "Ready to apply?" | Patronizing microcopy that adds no value |

---

## Next Steps

### Employer Context (Priority)

1. **Run employer enrichment** - `python -m pipeline.utilities.enrich_employer_metadata --apply --force`
2. **API: Add employer fields** - logo_url, industry, website to /feed response
3. **API: Add context fields** - description, HQ, founding_year to /[id]/context response
4. **CompanyLogo component** - 24px avatar with initial fallback
5. **Industry badge** - Muted badge on row 3 after salary
6. **Company context section** - Full profile in expanded view
7. **Industry filter dropdown** - Grouped options after City

### Other

8. **localStorage** - Persist user filter preferences
9. **Dashboard CTA** - Add "View X jobs" button to analytics page
10. **Analytics** - Track card expansions, apply clicks
11. **URL params** - Make filter state shareable via URL
