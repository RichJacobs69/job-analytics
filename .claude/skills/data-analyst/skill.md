---
name: data-analyst
description: Data analyst for hiring market insights. Use when asked to create reports, analyze trends, generate content for LinkedIn/blog posts, answer marketplace questions, or produce data visualizations.
---

# Data Analyst

Generate actionable insights from hiring market data. Create reports, identify trends, and produce content for marketing and thought leadership.

## When to Use This Skill

Trigger when user asks to:
- Analyze hiring trends
- Create a report or case study
- Generate LinkedIn post content
- Write blog article drafts
- Answer marketplace questions
- Compare cities/roles/companies
- Identify emerging patterns
- Produce data visualizations

## Data Context

### Available Data

| Table | Records | Key Fields |
|-------|---------|------------|
| `enriched_jobs` | ~6,000+ | job_family, seniority, working_arrangement, skills, employer_name, city_code |
| `raw_jobs` | ~6,000+ | title, description, posting_url, source |

### Dimensions Available

| Dimension | Values |
|-----------|--------|
| **Cities** | London (lon), NYC (nyc), Denver (den), San Francisco (sfo), Singapore (sgp) |
| **Job Families** | Data, Product |
| **Subfamilies** | core_de, analytics_eng, ml_eng, data_sci, bi_analyst, core_pm, technical_pm, growth_pm, ai_ml_pm, platform_pm |
| **Seniority** | junior, mid, senior, staff, principal, director, vp, c_level |
| **Working Arrangement** | onsite, hybrid, remote |
| **Sources** | adzuna, greenhouse, lever |

### Key Metrics

| Metric | Description | Calculation |
|--------|-------------|-------------|
| Job Volume | Count of active postings | COUNT(*) |
| Role Distribution | % by subfamily | COUNT by subfamily / total |
| Remote Rate | % remote-friendly | COUNT(remote OR hybrid) / total |
| Skill Demand | Top skills by frequency | COUNT by skill_name |
| Hiring Velocity | New jobs per week | COUNT WHERE scraped_at > 7 days ago |
| Employer Concentration | Top N employers share | SUM(top 10) / total |

## Analysis Templates

### 1. Weekly Hiring Pulse

**Purpose:** Quick snapshot of market activity

```sql
-- New jobs this week by city
SELECT city_code, COUNT(*) as new_jobs
FROM enriched_jobs
WHERE scraped_at > NOW() - INTERVAL '7 days'
GROUP BY city_code
ORDER BY new_jobs DESC;

-- Top hiring companies this week
SELECT employer_name, COUNT(*) as jobs
FROM enriched_jobs
WHERE scraped_at > NOW() - INTERVAL '7 days'
GROUP BY employer_name
ORDER BY jobs DESC
LIMIT 10;

-- Hot skills this week
SELECT skill->>'name' as skill, COUNT(*) as mentions
FROM enriched_jobs, jsonb_array_elements(skills) as skill
WHERE scraped_at > NOW() - INTERVAL '7 days'
GROUP BY skill->>'name'
ORDER BY mentions DESC
LIMIT 15;
```

**Output format:**
```markdown
## Weekly Hiring Pulse - [Date Range]

### Top Line Numbers
- **New Jobs:** X (+Y% vs last week)
- **Active Employers:** X
- **Top City:** [City] (X jobs)

### Highlights
- [Trend 1]
- [Trend 2]
- [Trend 3]
```

### 2. City Comparison Report

**Purpose:** Compare hiring across markets

```sql
-- Jobs by city and family
SELECT
    city_code,
    job_family,
    COUNT(*) as jobs,
    ROUND(AVG(CASE WHEN working_arrangement = 'remote' THEN 1 ELSE 0 END) * 100, 1) as remote_pct
FROM enriched_jobs
GROUP BY city_code, job_family
ORDER BY city_code, jobs DESC;

-- Seniority distribution by city
SELECT
    city_code,
    seniority,
    COUNT(*) as jobs
FROM enriched_jobs
WHERE seniority IS NOT NULL
GROUP BY city_code, seniority;
```

**Output format:**
```markdown
## City Comparison: [City A] vs [City B]

| Metric | [City A] | [City B] | Delta |
|--------|----------|----------|-------|
| Total Jobs | X | Y | +Z% |
| Data Roles | X | Y | +Z% |
| Product Roles | X | Y | +Z% |
| Remote Rate | X% | Y% | +Z pp |
| Avg Seniority | [level] | [level] | - |

### Key Differences
1. [Insight]
2. [Insight]
```

### 3. Role Deep Dive

**Purpose:** Detailed analysis of specific role type

```sql
-- Role breakdown
SELECT
    job_subfamily,
    COUNT(*) as jobs,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pct
FROM enriched_jobs
WHERE job_family = 'data'  -- or 'product'
GROUP BY job_subfamily
ORDER BY jobs DESC;

-- Skills for role
SELECT
    skill->>'name' as skill,
    skill->>'family_code' as family,
    COUNT(*) as mentions
FROM enriched_jobs, jsonb_array_elements(skills) as skill
WHERE job_subfamily = 'core_de'  -- example
GROUP BY skill->>'name', skill->>'family_code'
ORDER BY mentions DESC
LIMIT 20;
```

### 4. Skills Demand Analysis

**Purpose:** Identify in-demand skills

```sql
-- Top skills overall
SELECT
    skill->>'name' as skill_name,
    skill->>'family_code' as family,
    COUNT(*) as job_count,
    COUNT(DISTINCT employer_name) as employer_count
FROM enriched_jobs, jsonb_array_elements(skills) as skill
GROUP BY skill->>'name', skill->>'family_code'
ORDER BY job_count DESC
LIMIT 30;

-- Emerging skills (recent vs historical)
WITH recent AS (
    SELECT skill->>'name' as skill, COUNT(*) as recent_count
    FROM enriched_jobs, jsonb_array_elements(skills) as skill
    WHERE scraped_at > NOW() - INTERVAL '14 days'
    GROUP BY skill->>'name'
),
historical AS (
    SELECT skill->>'name' as skill, COUNT(*) as hist_count
    FROM enriched_jobs, jsonb_array_elements(skills) as skill
    WHERE scraped_at <= NOW() - INTERVAL '14 days'
    GROUP BY skill->>'name'
)
SELECT
    r.skill,
    r.recent_count,
    COALESCE(h.hist_count, 0) as historical_count,
    ROUND((r.recent_count::float / NULLIF(h.hist_count, 0) - 1) * 100, 1) as growth_pct
FROM recent r
LEFT JOIN historical h ON r.skill = h.skill
ORDER BY growth_pct DESC NULLS LAST
LIMIT 15;
```

### 5. Employer Analysis

**Purpose:** Hiring activity by company

```sql
-- Top employers
SELECT
    employer_name,
    COUNT(*) as total_jobs,
    COUNT(DISTINCT job_subfamily) as role_diversity,
    MODE() WITHIN GROUP (ORDER BY seniority) as typical_seniority
FROM enriched_jobs
GROUP BY employer_name
ORDER BY total_jobs DESC
LIMIT 20;

-- Employer by role type
SELECT
    employer_name,
    job_family,
    COUNT(*) as jobs
FROM enriched_jobs
GROUP BY employer_name, job_family
HAVING COUNT(*) >= 5
ORDER BY employer_name, jobs DESC;
```

## Content Templates

### LinkedIn Post Template

```markdown
[Hook - surprising stat or question]

I analyzed [X] job postings across [cities] to understand [topic].

Here's what I found:

[Point 1 with data]
[Point 2 with data]
[Point 3 with data]

The takeaway? [Actionable insight]

---
Data from my hiring market analytics project: [link]

#HiringTrends #DataAnalytics #[RelevantHashtag]
```

**Example:**
```markdown
Remote work isn't dead - but it's changing.

I analyzed 6,000+ job postings across London, NYC, and Denver.

The numbers:
- 34% of roles are fully remote
- 41% are hybrid
- Only 25% require full-time office

But here's the interesting part: Senior+ roles are 2x more likely to be remote than junior roles.

Companies want experienced hires they can trust to work independently.

---
Data from my hiring market analytics project: richjacobs.me/projects/hiring-market

#RemoteWork #HiringTrends #DataAnalytics
```

### Blog Article Outline

```markdown
# [Title: Question or Statement]

## Introduction
- Hook with surprising finding
- Why this matters to the reader
- What data was analyzed

## Key Finding 1: [Topic]
- Data visualization
- Analysis
- Implications

## Key Finding 2: [Topic]
- Data visualization
- Analysis
- Implications

## Key Finding 3: [Topic]
- Data visualization
- Analysis
- Implications

## What This Means For You
- If you're a job seeker...
- If you're a hiring manager...
- If you're building skills...

## Methodology
- Data sources
- Time period
- Limitations

## Conclusion
- Summary of insights
- Call to action
```

## Marketplace Questions Reference

From `docs/marketplace_questions.md`, key questions to answer:

### Role Demand
1. Which job subfamilies have the most openings?
2. How does role distribution vary by city?
3. What's the Data vs Product role ratio?

### Skills
4. What are the top 10 most requested skills?
5. Which skills appear together most often?
6. Are certain skills city-specific?

### Working Arrangement
7. What % of jobs are remote vs hybrid vs onsite?
8. Does remote availability vary by seniority?
9. Which companies offer most remote roles?

### Compensation (if available)
10. What's the salary range by role and city?
11. How does remote work affect compensation?

### Employers
12. Which companies are hiring most aggressively?
13. What's the employer concentration (top 10 share)?
14. Are there emerging employers worth watching?

## Output Format

When producing analysis, include:

```markdown
## [Analysis Title]

**Date:** [Date]
**Data Period:** [Start] - [End]
**Records Analyzed:** [Count]

### Executive Summary
[2-3 sentence overview of key findings]

### Key Metrics

| Metric | Value | Trend |
|--------|-------|-------|
| [Metric 1] | [Value] | [up/down/stable] |
| [Metric 2] | [Value] | [up/down/stable] |

### Detailed Findings

#### Finding 1: [Title]
[Analysis with supporting data]

#### Finding 2: [Title]
[Analysis with supporting data]

### Visualizations
[Describe charts/graphs to create or reference dashboard]

### Content Derivatives

**LinkedIn Post (ready to use):**
[Draft post]

**Blog Hook:**
[Opening paragraph for longer article]

### Methodology Notes
- Data sources: [list]
- Filters applied: [list]
- Limitations: [list]
```

## Key Files to Reference

- `docs/CASE_STUDY_MVP_REPORT.md` - Example report format
- `docs/marketplace_questions.md` - Questions to answer
- `docs/PRODUCT_BRIEF.md` - Project context
- Dashboard: `richjacobs.me/projects/hiring-market`
