# Job Feed UX Design

**Epic:** EPIC-008 Curated Job Feed
**Version:** 1.0
**Date:** 2026-01-03
**Status:** Prototype Complete

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
| Title (lg, semibold, white)     | [Skill] [Skill]       | [v] [Apply]  |
| Company . Location . Arrangement| [Skill] [Skill] +N    |              |
| Posted . Salary                 |                       |              |
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
| Skills | `text-sm bg-gray-800 border border-gray-700/50 px-3 py-1.5` | `text-xs px-2.5 py-1` |
| Salary | `text-xs text-gray-400` | Same |
| Apply | `bg-lime-500/10 text-lime-400 px-4 py-2` | Same |

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

**Desktop (Inline):**

```
+------------------------------------------------------------------------+
| [City v] [Role pill] [Role pill] [Level pill] [Level pill]    [Reset] |
+------------------------------------------------------------------------+
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
| Role                             |
| [pill] [pill] [pill]             |
|                                  |
| Seniority                        |
| [pill] [pill] [pill]             |
|                                  |
| Arrangement                      |
| [pill] [pill] [pill]             |
|                                  |
| [Apply Filters]                  |
+----------------------------------+
```

**Filter Pills:**

| State | Style |
|-------|-------|
| Inactive | `bg-gray-800 text-gray-400 border-transparent` |
| Active | `bg-lime-500/20 text-lime-400 border-lime-500/30` |

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
| JobCard | [DONE] | 3-column layout, expand/collapse |
| JobFeedGroup | [DONE] | Vertical + horizontal layouts |
| JobFilters | [DONE] | Desktop inline, mobile sheet |
| Page layout | [DONE] | Stacked groups with dividers |
| API integration | [TODO] | Connect to /feed endpoint |
| localStorage | [TODO] | Persist filter preferences |
| Dashboard CTA | [TODO] | "View X jobs" button |
| Empty states | [TODO] | No results messaging |
| Loading skeletons | [TODO] | Skeleton cards while loading |

---

## Design Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-03 | Single column over 2-column | Users review groups sequentially, not in parallel |
| 2026-01-03 | Skills in center column | Better use of horizontal space; quick tech stack scan |
| 2026-01-03 | Vertical layout over horizontal scroll | Easier expand/collapse; better for detailed review |
| 2026-01-03 | Dividers between groups | Clear visual separation for focused scanning |
| 2026-01-03 | Mobile skills below content | No room inline; separate row maintains readability |

---

## Next Steps

1. **API Integration** - Connect prototype to live /feed endpoint
2. **Dashboard CTA** - Add "View X jobs" button to analytics page
3. **localStorage** - Persist user filter preferences
4. **Empty States** - Design no-results and error states
5. **Loading States** - Add skeleton loaders
6. **Analytics** - Track card expansions, apply clicks
