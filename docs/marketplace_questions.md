# Marketplace Questions

**Version:** 1.0
**Last Updated:** 2025-11-05
**Purpose:** Define key questions the platform must answer for job seekers and employers

---

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 35 |
| High Availability | 27 |
| Complex Availability | 8 |
| Coverage Estimate | 75% answerable with job posting data |

**Priority Distribution:** High (16), Medium (15), Low (4)

---

## Market Demand & Supply

| ID | Side | Avail. | Priority | Question |
|----|------|--------|----------|----------|
| MDS001 | Employer | High | High | Which job subfamilies are growing fastest in Product/Data in each city? |
| MDS002 | Employer | High | Medium | Which titles are most commonly used for roles similar to ours? |
| MDS003 | Employer | Complex | High | What is the estimated time-to-fill for Senior Data Scientist roles across cities? |
| MDS004 | Candidate | High | High | Is demand for my skill increasing or decreasing compared with last year? |
| MDS005 | Candidate | Complex | High | Which employers fill roles like mine fastest? |
| MDS006 | Candidate | High | Medium | When are most jobs in my field posted (day/month patterns)? |
| MDS007 | Employer | High | High | Which new job titles are emerging this year that didn't exist last year? |

<details>
<summary>Question Details</summary>

**MDS001** — Identifies emerging areas of hiring activity for competitive positioning.
- Labels: `job_family`, `job_subfamily`, `location.city_code`, `posting.posted_date`
- Aggregation: growth_rate | Time: trend_monthly

**MDS002** — Improves discoverability by adopting market-standard titles.
- Labels: `role.title_display`, `role.title_canonical`, `job_subfamily`
- Aggregation: count_distinct | Time: point_in_time

**MDS003** — Enables realistic hiring timeline planning by geography.
- Labels: `job_subfamily`, `location.city_code`, `posting.posted_date`, `posting.last_seen_date`
- Aggregation: median_days | Time: rolling_average

**MDS004** — Helps focus job search and upskilling on growing technologies.
- Labels: `skills.items.name`, `posting.posted_date`, `location.city_code`
- Aggregation: percentage_change | Time: year_over_year

**MDS005** — Prioritizes applications to employers with quicker hiring.
- Labels: `employer.name`, `job_subfamily`, `posting.posted_date`, `posting.last_seen_date`
- Aggregation: median_days | Time: point_in_time

**MDS006** — Helps candidates time their job search for maximum opportunity.
- Labels: `posting.posted_date`, `job_subfamily`
- Aggregation: distribution | Time: seasonal_pattern

**MDS007** — Identifies market evolution to stay ahead of role trends.
- Labels: `role.title_display`, `posting.posted_date`
- Aggregation: new_unique_values | Time: year_over_year

</details>

---

## Title & Leveling Clarity

| ID | Side | Avail. | Priority | Question |
|----|------|--------|----------|----------|
| TLC001 | Candidate | High | Medium | If I'm a Data Product Manager, which alternate titles describe similar work? |
| TLC002 | Employer | Complex | Medium | Does our chosen title reduce applicant volume versus synonyms? |

<details>
<summary>Question Details</summary>

**TLC001** — Expands search pool by including functionally equivalent titles.
- Labels: `role.title_canonical`, `job_subfamily`, `skills.items`
- Aggregation: list_similar | Time: point_in_time

**TLC002** — Evaluates how title choice influences applicant traffic.
- Labels: `role.title_display`, `posting.posted_date`
- Aggregation: comparative_volume | Time: trend_weekly

</details>

---

## Skills Gap & Upskilling

| ID | Side | Avail. | Priority | Question |
|----|------|--------|----------|----------|
| SGU001 | Employer | High | High | Which tools or skills are most listed in Analytics Engineer roles in London? |
| SGU002 | Employer | High | Medium | Which data/ML skills are most commonly paired with experimentation for AI PMs? |
| SGU003 | Candidate | High | High | Which adjacent skills are most frequently co-mentioned with my core skill? |
| SGU004 | Candidate | High | High | How easy is it to pivot from my current role into a new target role? |
| SGU005 | Employer | Complex | Medium | Which skill requirements most improve applicant quality? |

<details>
<summary>Question Details</summary>

**SGU001** — Guides job descriptions to reflect current market expectations.
- Labels: `skills.items.name`, `job_subfamily`, `location.city_code`
- Aggregation: frequency_count | Time: point_in_time

**SGU002** — Identifies capability clusters within advanced Product roles.
- Labels: `skills.items.family`, `skills.items.name`, `job_subfamily`
- Aggregation: co_occurrence | Time: point_in_time

**SGU003** — Highlights complementary skills for resume optimization.
- Labels: `skills.items.name`
- Aggregation: co_occurrence | Time: point_in_time

**SGU004** — Shows skill delta between current and target roles.
- Labels: `skills.items.name`, `job_subfamily`
- Aggregation: skill_overlap_percentage | Time: point_in_time

**SGU005** — Correlates skill criteria with hiring outcomes.
- Labels: `skills.items`, `job_subfamily`
- Aggregation: correlation_score | Time: trend_quarterly

</details>

---

## Work Arrangement & Location

| ID | Side | Avail. | Priority | Question |
|----|------|--------|----------|----------|
| WAL001 | Employer | High | Medium | What percentage of Data Engineer postings in Denver are Onsite, Hybrid, or Remote? |
| WAL002 | Candidate | High | Medium | Where are most AI Engineer roles that allow Remote work? |
| WAL003 | Employer | Complex | High | Does shifting from hybrid to on-site policy affect applicant numbers? |

<details>
<summary>Question Details</summary>

**WAL001** — Enables workforce strategy aligned with market norms.
- Labels: `job_subfamily`, `location.working_arrangement`, `location.city_code`, `posting.posted_date`
- Aggregation: percentage_split | Time: point_in_time

**WAL002** — Targets geographies aligned with work flexibility preferences.
- Labels: `job_subfamily`, `location.city_code`, `location.working_arrangement`
- Aggregation: count_by_location | Time: point_in_time

**WAL003** — Quantifies talent-attraction impact of work arrangements.
- Labels: `location.working_arrangement`, `posting.posted_date`
- Aggregation: comparative_volume | Time: before_after

</details>

---

## Compensation & Transparency

| ID | Side | Avail. | Priority | Question | Notes |
|----|------|--------|----------|----------|-------|
| CT001 | Employer | High | High | What is the distribution of posted salary ranges for Data Scientist roles in NYC and Denver? | High availability due to pay transparency laws |
| CT002 | Employer | Complex | High | What is the median salary for Data Analysts in London tech firms? | Complex in London — only ~30% show salary |
| CT003 | Candidate | High | High | Which salary ranges are most frequently advertised for Product Manager roles in NYC? | — |
| CT004 | Candidate | Complex | Medium | Which companies include equity or bonuses for my role? | Rarely disclosed in job postings |

<details>
<summary>Question Details</summary>

**CT001** — Provides pay benchmarking in transparent markets.
- Labels: `compensation.base_salary_range`, `location.city_code`, `job_subfamily`
- Aggregation: distribution_percentiles | Time: point_in_time

**CT002** — Supports budgeting and offer calibration with limited data.
- Labels: `compensation.base_salary_range`, `location.city_code`, `employer.company_size_estimate`
- Aggregation: median | Time: point_in_time

**CT003** — Benchmarks expectations for better negotiation.
- Labels: `compensation.base_salary_range`, `location.city_code`, `job_subfamily`
- Aggregation: frequency_bands | Time: point_in_time

**CT004** — Enables total compensation comparisons where disclosed.
- Labels: `compensation.equity_eligible`, `employer.name`, `job_subfamily`
- Aggregation: percentage_offering | Time: point_in_time

</details>

---

## Process Transparency

| ID | Side | Avail. | Priority | Question |
|----|------|--------|----------|----------|
| PT001 | Employer | High | Medium | Do our job ads specify clear application instructions and concrete requirements? |
| PT002 | Candidate | High | High | Which employers describe clear, skill-based requirements for AI PM roles? |
| PT003 | Candidate | Complex | High | Which employers have faster, more transparent hiring processes? |

<details>
<summary>Question Details</summary>

**PT001** — Improves candidate experience and reduces drop-off.
- Labels: `posting.posting_url`, `role.title_display`, `skills.items`
- Aggregation: clarity_score | Time: point_in_time

**PT002** — Prioritizes roles with transparent expectations.
- Labels: `skills.items`, `employer.name`, `job_subfamily`
- Aggregation: clarity_ranking | Time: point_in_time

**PT003** — Enables job-search prioritization based on efficiency.
- Labels: `employer.name`, `posting.posted_date`, `posting.last_seen_date`
- Aggregation: process_efficiency_score | Time: rolling_average

</details>

---

## Competitive Positioning

| ID | Side | Avail. | Priority | Question |
|----|------|--------|----------|----------|
| CP001 | Employer | High | High | Which competitors posted the most Platform PM roles in London last quarter? |
| CP002 | Employer | High | Medium | Which skill combinations are competitors standardizing on for MLOps hires? |
| CP003 | Candidate | High | High | Which employers most frequently hire for my skill set in NYC? |
| CP004 | Employer | Complex | Low | What titles and skills bring us the best inbound candidates versus peers? |
| CP005 | Candidate | High | Medium | What company sizes (startup/scale-up/enterprise) are hiring most for my role? |

<details>
<summary>Question Details</summary>

**CP001** — Supports headcount planning via hiring activity benchmarking.
- Labels: `employer.name`, `job_subfamily`, `location.city_code`, `posting.posted_date`
- Aggregation: count_ranking | Time: quarterly

**CP002** — Highlights emerging capability standards.
- Labels: `skills.items.family`, `skills.items.name`, `employer.name`
- Aggregation: skill_clusters | Time: point_in_time

**CP003** — Guides applications toward consistent demand employers.
- Labels: `employer.name`, `skills.items`, `location.city_code`
- Aggregation: frequency_count | Time: trend_monthly

**CP004** — Links JD design to applicant conversion metrics.
- Labels: `role.title_display`, `skills.items`, `employer.name`
- Aggregation: conversion_correlation | Time: trend_quarterly

**CP005** — Helps target search by company stage preference.
- Labels: `employer.company_size_estimate`, `job_subfamily`
- Aggregation: percentage_split | Time: point_in_time

</details>

---

## Role Scope & Realism

| ID | Side | Avail. | Priority | Question |
|----|------|--------|----------|----------|
| RSR001 | Employer | High | Medium | Are we asking for more years of experience than peers for a given seniority? |
| RSR002 | Candidate | High | Low | For Senior Data roles in Denver, what experience ranges are most listed? |

<details>
<summary>Question Details</summary>

**RSR001** — Ensures realistic expectations to reduce self-screen-out.
- Labels: `role.title_display`, `role.experience_range`, `job_subfamily`
- Aggregation: comparative_percentile | Time: point_in_time

**RSR002** — Gauges if candidates meet market-level expectations.
- Labels: `role.title_display`, `role.experience_range`, `location.city_code`
- Aggregation: frequency_bands | Time: point_in_time

</details>

---

## Reference: Aggregation Types

| Type | Description |
|------|-------------|
| growth_rate | Period-over-period percentage change |
| count_distinct | Unique value count |
| percentage_change | Relative change between periods |
| median_days | Median duration in days |
| distribution | Statistical distribution of values |
| frequency_count | Occurrence count |
| percentage_split | Percentage breakdown by category |
| co_occurrence | Frequency of items appearing together |
| correlation_score | Statistical correlation coefficient |
| clarity_score | Composite score for posting clarity |
| skill_overlap_percentage | Percentage of shared skills |
| conversion_correlation | Correlation with conversion metrics |

## Reference: Time Dimensions

| Type | Description |
|------|-------------|
| point_in_time | Current snapshot |
| trend_monthly | Month-over-month trend |
| trend_quarterly | Quarter-over-quarter trend |
| trend_weekly | Week-over-week trend |
| year_over_year | Year-over-year comparison |
| seasonal_pattern | Recurring temporal patterns |
| rolling_average | Moving average over time window |
| before_after | Comparison of two time periods |
