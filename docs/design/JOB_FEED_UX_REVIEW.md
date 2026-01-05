# Job Feed UX Review & Iteration Log

**Date:** 2026-01-05
**Status:** In Progress
**Mockup:** `docs/design/job-feed-mockup.html`

---

## Design Decisions Made

### Collapsed Card

| Element | Decision | Rationale |
|---------|----------|-----------|
| Company logo | 24px avatar left of company name | Visual recognition at glance |
| Logo fallback | First initial in gray circle | Handles missing logo_url gracefully |
| Industry badge | End of row 3 (after salary) | Less prominent, doesn't crowd company line |
| Skills | Center column, hidden when expanded | Shown in dedicated section below instead |
| Apply button | Visible in collapsed, hidden when expanded | Forces "read then act" flow |

### Expanded Card - Final Structure

```
+------------------------------------------------------------------------+
| [Collapsed header - logo, title, company, location, salary, industry]  |
| [Collapse button only - no Apply]                                      |
|------------------------------------------------------------------------|
| ABOUT THIS ROLE (2/3)              |  SKILLS (1/3)                     |
| [AI summary paragraph]             |  [Python] [SQL] [ML]              |
|                                    |  [Experimentation] [A/B Testing]  |
|------------------------------------------------------------------------|
| INSIGHTS (renamed from "Why This Might Fit")                           |
| [check] Early applicant  [check] 4 similar roles  [check] 75th %ile    |
|------------------------------------------------------------------------|
| COMPANY PROFILE (1/3)    |  ABOUT [COMPANY] (2/3)                      |
| Monzo                    |  [Full paragraph description]               |
| [FinTech] [Private]      |                                             |
| HQ: London, UK           |                                             |
| Founded: 2015            |                                             |
| Open roles: 12           |                                             |
|------------------------------------------------------------------------|
| [Monzo careers]                              [Apply to this role]      |
+------------------------------------------------------------------------+
```

### Key Layout Decisions

| Decision | Rationale |
|----------|-----------|
| Skills in dedicated section (not header) when expanded | More room for full list, cleaner header |
| "Insights" pills (horizontal) | Compact, saves vertical space vs. stacked list |
| Company Profile 1/3, About 2/3 | Description needs more room than structured labels |
| No logo in Company Profile | Already shown in card header - avoid duplication |
| Two CTAs at bottom | "Monzo careers" (secondary) + "Apply to this role" (primary) |
| Remove "Ready to apply?" | Patronizing microcopy that adds no value |

---

## UX Issues Identified

### Critical

1. **Information overload** - ~~5 sections in expanded view is too much.~~ [RESOLVED] Merged Company Profile + About into single section with truncated narrative + "Show more". Now 3 content sections.

2. **"Insights" signals must be non-obvious** - Don't restate filter criteria as insights.

### Major

3. **Filter bar touch targets too small** - Pills are ~28px height, need 44px for WCAG compliance.

4. **Industry badge contrast** - `#737373` on dark background is ~3.5:1, needs 4.5:1 for WCAG AA.

5. **Two competing CTAs** - "Monzo careers" vs "Apply to this role" may cause hesitation.

6. **Mobile expanded state not designed** - Mockup only shows desktop expanded view.

### Minor

7. **Dot separators feel dated** - Consider pipes or spacing.

8. **"Collapse" is jargon** - Use "Less" or icon-only.

9. **Inconsistent date format** - "2d ago" vs "21d ago" - standardize.

---

## "Insights" Section Redesign

### Renamed from "Why This Might Fit"

The old name implied preference matching, but restating filter criteria is useless:
> "You filtered for Hybrid → We show Hybrid jobs → 'Hybrid matches!'" = tautology

### Valid Insight Signals (non-obvious, data-driven)

| Signal | Data Source | Example |
|--------|-------------|---------|
| Freshness | `days_open` | "Posted 1 day ago" |
| Longevity vs avg | `days_open` / `employer_median_days_to_fill` | "Open 18 days - avg is 12" |
| Company activity | Count jobs by employer | "4 similar roles open" |
| Salary percentile | Compare to distribution | "Top 25% for this role" |
| Fill time ratio | `fill_time_ratio` | "Taking longer than usual" |

### Invalid Signals (remove these)

| Signal | Why Invalid |
|--------|-------------|
| "Hybrid matches your preference" | Restates filter - obvious |
| "Senior matches your level" | Restates filter - obvious |
| "London matches your location" | Restates filter - obvious |
| "Data role matches your family" | Restates filter - obvious |

### Recommended Pill Format

```html
<span class="inline-flex items-center gap-1.5 text-xs text-gray-300
             bg-lime-500/10 border border-lime-500/20 px-2.5 py-1 rounded-full">
  <svg class="w-3 h-3 text-lime-400"><!-- checkmark --></svg>
  Early applicant
</span>
```

---

## Filter Bar Spec

### Current Layout
```
[City v] | [Industry v] | [Data] [Product] [Delivery] | [Jr] [Mid] [Sr] [Staff+] | [Has Salary] | Reset (3)
```

### Industry Dropdown (Grouped)

```
All Industries
─────────────────
TECHNOLOGY
  AI/ML
  DevTools
  Data Infrastructure
  Cybersecurity
─────────────────
FINANCE
  FinTech
  Financial Services
  Crypto & Web3
─────────────────
COMMERCE
  E-commerce
  MarTech
─────────────────
SERVICES
  HealthTech
  EdTech
  HR Tech
  Professional Services
─────────────────
OTHER
  Consumer
  Mobility
  PropTech
  Climate Tech
  Hardware
```

---

## Accessibility Fixes Needed

| Issue | Current | Fix |
|-------|---------|-----|
| Filter pill height | ~28px | Increase to 44px (`py-2.5`) |
| Badge text contrast | #737373 (~3.5:1) | Use #a3a3a3 (4.5:1) |
| Focus states | Not defined | Add visible focus ring |
| Screen reader labels | Missing | Add aria-labels to icon buttons |
| Mobile expanded | Not designed | Create mobile-specific layout |

---

## Data Requirements

### For Collapsed Card
- `title_display`
- `employer_name` (display_name)
- `employer_logo_url` (nullable)
- `employer_industry` (nullable)
- `city_code`
- `working_arrangement`
- `posted_date` / `days_open`
- `salary_min`, `salary_max`, `currency`
- `skills` (array, truncated to 4-5)

### For Expanded Card (lazy loaded)
- `summary` (AI-generated role summary)
- `skills` (full array)
- `employer_description`
- `employer_headquarters_city`, `employer_headquarters_country`
- `employer_ownership_type`
- `employer_size` (startup/scale-up/enterprise)
- `employer_parent_company` (e.g., "Alphabet" for YouTube) [NOT IN VIEW YET]
- `employer_website`
- `employer_median_days_to_fill`
- Open roles count (computed)

### For Insights (Secondary Signals)
- `experience_range` - experience requirement
- `track` - IC vs Management clarity
- `salary_max` + `city_code` - salary transparency signal (London/Singapore)
- `days_open` - freshness (only if NOT in Fresh Matches group)
- `employer_median_days_to_fill` - longevity (only if NOT in Still Hiring group)
- Job count by employer - activity signal (needs aggregation)
- Salary percentile - compensation signal (needs computation)

---

## Next Steps

### Completed
1. ~~Update mockup~~ - Renamed to "Insights", merged company sections (v1.4)
2. ~~Simplify sections~~ - Reduced from 5 to 3 content sections

### Infrastructure
3. **Add parent_company to view** - Migration needed (field exists in table, not exposed)
4. **Run employer enrichment** - Populate description, logo, HQ, parent_company data
5. **Update portfolio-site API** - Return new employer fields (size, parent_company)

### UX Iteration
6. **Fix accessibility** - Increase touch targets (44px), fix badge contrast (#a3a3a3)
7. **Design mobile expanded** - Currently missing
8. **Implement secondary insights logic** - Exclude group's primary signal

---

## Files

| File | Purpose |
|------|---------|
| `docs/design/job-feed-mockup.html` | Interactive HTML mockup |
| `docs/design/JOB_FEED_UX_DESIGN.md` | Component specs (v1.3) |
| `docs/design/JOB_FEED_UX_REVIEW.md` | This review document |
| `C:\Users\rich2\.claude\plans\robust-percolating-minsky.md` | Original implementation plan |

---

## Lovable Prompt

A comprehensive prompt for recreating this design in Lovable was provided earlier in the session. Key elements:
- Dark theme (#0a0a0a background)
- Lime accent (#a3e635)
- 3-column collapsed card layout
- Expandable with lazy-loaded context
- Grouped industry dropdown
- Sample job data included

---

**Document Version:** 1.0
**Last Updated:** 2026-01-05
