# Job Feed UX Design

**Epic:** EPIC-008 Curated Job Feed
**Version:** 1.2
**Date:** 2026-01-03
**Status:** API Integration Complete

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
| LEFT (flex-1)                   | CENTER (max-w-280)    | RIGHT        |
| Title (lg, semibold, white)     | [Skill] [Skill]       | [Details v]  |
| Company . Location . Arrangement| [Skill] [Skill] +N    | [Apply]      |
| Posted . Salary                 |   (muted, display-only)|              |
+------------------------------------------------------------------------+
```

**Mobile Layout:**

```
+----------------------------------+
| Title                   [v][Apply]|
| Company . Location . Arrangement |
| Posted . Salary                  |
|----------------------------------|
| [Skill] [Skill] [Skill] [Skill]  |
+----------------------------------+
```

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
| [Collapsed content as above]                                           |
|------------------------------------------------------------------------|
| ABOUT THIS ROLE                                                        |
| 2-3 sentence AI-generated summary of the role...                       |
|                                                                        |
| WHY THIS MIGHT FIT                                                     |
| [check] Posted 2 days ago - be an early applicant                      |
| [check] Hybrid matches your preference                                 |
| [check] Monzo has 4 similar open roles                                 |
+------------------------------------------------------------------------+
```

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
+-------------------------------------------------------------------------------------------+
| [City v] | [Data] [Product] [Delivery] [+ Roles v] | [Jr] [Mid] [Sr] [Staff+] | [Has Salary] | Reset (n)
+-------------------------------------------------------------------------------------------+
              ^                            ^                                        ^
           Family pills              Dropdown popover                    US cities only
```

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

---

## File Structure

```
app/projects/hiring-market/jobs/
    |-- page.tsx                 # Main feed page
    +-- components/
        |-- JobCard.tsx          # Expandable job card
        |-- JobFeedGroup.tsx     # Group container
        +-- JobFilters.tsx       # Filter bar + mobile sheet
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

---

## Next Steps

1. **localStorage** - Persist user filter preferences
2. **Dashboard CTA** - Add "View X jobs" button to analytics page
3. **Analytics** - Track card expansions, apply clicks
4. **URL params** - Make filter state shareable via URL
