---
name: data-analyst
description: Data analyst for hiring market insights. Use when asked to create reports, analyze trends, generate content for LinkedIn/blog posts, answer marketplace questions, or produce data visualizations.
---

# Data Analyst

Generate actionable insights from hiring market data. Create reports, identify trends, and produce content for marketing and thought leadership.

## When to Use This Skill

Trigger when user asks to:
- Create a hiring market report (monthly/quarterly)
- Analyze hiring trends
- Generate LinkedIn post content
- Write blog article drafts
- Answer marketplace questions
- Compare cities/roles/companies
- Identify emerging patterns
- Produce data visualizations

## Key References

Before generating reports, review:
- `docs/templates/hiring_report_template.md` - Master template for market reports
- `docs/schema_taxonomy.yaml` - Classification taxonomy (v1.5.0)
- `docs/marketplace_questions.yaml` - Questions the platform answers

## Data Context

### Available Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `enriched_jobs` | Classified job postings | All taxonomy fields below |
| `raw_jobs` | Unprocessed postings | title, description, posting_url |

### Taxonomy Reference (v1.5.0)

**Job Families:**
| Code | Label |
|------|-------|
| `product` | Product Management |
| `data` | Data & Analytics |
| `delivery` | Project & Delivery |
| `out_of_scope` | Not in scope |

**Product Subfamilies:**
| Code | Label |
|------|-------|
| `core_pm` | Core PM |
| `growth_pm` | Growth PM |
| `platform_pm` | Platform PM |
| `technical_pm` | Technical PM |
| `ai_ml_pm` | AI/ML PM |

**Data Subfamilies:**
| Code | Label |
|------|-------|
| `product_analytics` | Product Analytics |
| `data_analyst` | Data Analyst |
| `analytics_engineer` | Analytics Engineer |
| `data_engineer` | Data Engineer |
| `ml_engineer` | Machine Learning Engineer |
| `data_scientist` | Data Scientist |
| `research_scientist_ml` | Research Scientist (ML/AI) |
| `data_architect` | Data Architect |

**Delivery Subfamilies:**
| Code | Label |
|------|-------|
| `delivery_manager` | Delivery Manager |
| `project_manager` | Project Manager |
| `programme_manager` | Programme Manager |
| `scrum_master` | Scrum Master |

**Locations:**
| Code | Label | Compensation Data |
|------|-------|-------------------|
| `lon` | London | ❌ Skip (no transparency laws) |
| `nyc` | New York | ✅ Full analysis |
| `den` | Denver | ✅ Full analysis |
| `sfo` | San Francisco | ✅ Full analysis |
| `sgp` | Singapore | ❌ Skip (no transparency laws) |

**Seniority Levels:**
| Code | Label |
|------|-------|
| `junior` | Junior |
| `mid` | Mid-Level |
| `senior` | Senior |
| `staff_principal` | Staff/Principal |
| `director_plus` | Director+ |

**Working Arrangement:**
| Code | Label |
|------|-------|
| `onsite` | Onsite |
| `hybrid` | Hybrid |
| `remote` | Remote |
| `flexible` | Flexible (employee choice) |
| `unknown` | Unknown |

**Track:**
| Code | Label |
|------|-------|
| `ic` | Individual Contributor |
| `management` | Management |

### Key Fields in enriched_jobs

```sql
-- Core classification
job_family          -- product, data, delivery, out_of_scope
job_subfamily       -- specific role type
seniority           -- junior, mid, senior, staff_principal, director_plus
track               -- ic, management

-- Location & arrangement
city_code           -- lon, nyc, den, sfo, sgp
working_arrangement -- onsite, hybrid, remote, flexible, unknown

-- Employer
employer_name       -- company name
company_size_estimate -- startup, scaleup, enterprise
is_agency           -- true if recruitment agency
agency_confidence   -- high, medium, low

-- Compensation (US cities only)
salary_min          -- minimum salary
salary_max          -- maximum salary
currency            -- gbp, usd, sgd

-- Skills (full descriptions only - filter by source internally)
skills              -- JSONB array of {name, family_code}
source              -- INTERNAL: used to filter for full descriptions

-- Posting metadata
posted_date         -- when job was posted
last_seen_date      -- when job was last observed active
posting_url         -- link to job
```

## Data Quality Rules

### Agency Filtering

**Always exclude agency postings from analysis:**

```sql
-- Standard filter for all queries
WHERE (is_agency = false OR is_agency IS NULL)
```

Report the filtering in methodology:
- Count total raw jobs
- Count excluded agency jobs
- Report: "X agency listings (Y%) identified and excluded"

### Skills Analysis

**Only use jobs with full descriptions (internal source filter):**

```sql
-- For skills queries only
-- INTERNAL: source determines description quality, don't expose in output
WHERE source IN ('greenhouse', 'lever')
```

If < 30 jobs from these sources, skip skills section with note:
> "Skills analysis requires full job descriptions. Insufficient data for this market segment."

### Compensation Analysis

**Only for US cities with pay transparency laws:**

```sql
-- Compensation queries
WHERE city_code IN ('nyc', 'den', 'sfo')
  AND salary_min IS NOT NULL
```

For London and Singapore, skip compensation section with note:
> "Compensation data excluded due to low disclosure rates in markets without pay transparency legislation."

## Report Generation

### Monthly/Quarterly Market Report

**Use the template:** `docs/templates/hiring_report_template.md`

**Workflow:**

1. **Validate data volume:**
```sql
SELECT COUNT(*) as total_jobs
FROM enriched_jobs
WHERE job_family = '{job_family}'
  AND city_code = '{city_code}'
  AND posted_date BETWEEN '{start_date}' AND '{end_date}'
  AND (is_agency = false OR is_agency IS NULL);
```
- If < 30 jobs, do not publish report

2. **Generate each section per template thresholds**

3. **Calculate contextual metrics** (see Metrics section below)

4. **Output as markdown for gamma.app import**

### Section Checklist

| Section | Min Jobs | Special Rules |
|---------|----------|---------------|
| Executive Summary | 30 | Always include |
| Data Quality Signal | 30 | Show agency filter stats |
| Key Takeaways | 30 | Split by persona |
| Top Employers | 30 | Top 10-15, min 2 jobs each |
| Industry Distribution | 30 | LLM-inferred clustering |
| Employer Size | 30 | Need 60% coverage |
| Role Specialization | 30 | Combine <5 into "Other" |
| Seniority Distribution | 30 | Combine thin tiers |
| IC vs Management | 30 | Report count if mgmt <10 |
| Working Arrangement | 30 | Need 70% coverage |
| Compensation | 20 with salary | US cities only |
| Skills Demand | 30 full desc | Internal: source filter |
| Contextual Metrics | 50 | Skip cross-segment if thin |

## Key Metrics & Calculations

### Market Structure Metrics

```sql
-- Jobs per employer (market fragmentation)
SELECT 
    COUNT(*)::float / COUNT(DISTINCT employer_name) as jobs_per_employer
FROM enriched_jobs
WHERE job_family = '{job_family}' 
  AND city_code = '{city_code}'
  AND (is_agency = false OR is_agency IS NULL);
-- Benchmark: <1.5 = fragmented, 1.5-3 = moderate, >3 = concentrated

-- Top 5 employer concentration
WITH employer_counts AS (
    SELECT employer_name, COUNT(*) as jobs
    FROM enriched_jobs
    WHERE job_family = '{job_family}' AND city_code = '{city_code}'
      AND (is_agency = false OR is_agency IS NULL)
    GROUP BY employer_name
    ORDER BY jobs DESC
    LIMIT 5
)
SELECT SUM(jobs)::float / (SELECT COUNT(*) FROM enriched_jobs 
    WHERE job_family = '{job_family}' AND city_code = '{city_code}'
    AND (is_agency = false OR is_agency IS NULL)) as top_5_concentration
FROM employer_counts;
-- Benchmark: <15% = fragmented, 15-30% = moderate, >30% = concentrated
```

### Accessibility Metrics

```sql
-- Senior-to-junior ratio
SELECT 
    COUNT(*) FILTER (WHERE seniority IN ('senior', 'staff_principal', 'director_plus'))::float /
    NULLIF(COUNT(*) FILTER (WHERE seniority = 'junior'), 0) as senior_to_junior_ratio
FROM enriched_jobs
WHERE job_family = '{job_family}' AND city_code = '{city_code}'
  AND (is_agency = false OR is_agency IS NULL);
-- Benchmark: >10:1 = very competitive entry, 5-10:1 = competitive, <5:1 = accessible

-- Entry accessibility rate
SELECT 
    COUNT(*) FILTER (WHERE seniority IN ('junior', 'mid'))::float / COUNT(*) as entry_rate
FROM enriched_jobs
WHERE job_family = '{job_family}' AND city_code = '{city_code}'
  AND (is_agency = false OR is_agency IS NULL);

-- Management opportunity rate
SELECT 
    COUNT(*) FILTER (WHERE track = 'management')::float / COUNT(*) as mgmt_rate
FROM enriched_jobs
WHERE job_family = '{job_family}' AND city_code = '{city_code}'
  AND (is_agency = false OR is_agency IS NULL);
```

### Flexibility Metrics

```sql
-- Remote availability
SELECT 
    COUNT(*) FILTER (WHERE working_arrangement = 'remote')::float / COUNT(*) as remote_rate,
    COUNT(*) FILTER (WHERE working_arrangement IN ('remote', 'hybrid', 'flexible'))::float / COUNT(*) as flexibility_rate
FROM enriched_jobs
WHERE job_family = '{job_family}' AND city_code = '{city_code}'
  AND (is_agency = false OR is_agency IS NULL);

-- Remote by employer size
SELECT 
    company_size_estimate,
    COUNT(*) FILTER (WHERE working_arrangement = 'remote')::float / COUNT(*) as remote_rate
FROM enriched_jobs
WHERE job_family = '{job_family}' AND city_code = '{city_code}'
  AND (is_agency = false OR is_agency IS NULL)
  AND company_size_estimate IS NOT NULL
GROUP BY company_size_estimate;
```

### Compensation Metrics (US cities only)

```sql
-- Salary percentiles
SELECT 
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY (salary_min + salary_max) / 2) as p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY (salary_min + salary_max) / 2) as median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY (salary_min + salary_max) / 2) as p75
FROM enriched_jobs
WHERE job_family = '{job_family}' 
  AND city_code IN ('nyc', 'den', 'sfo')
  AND salary_min IS NOT NULL
  AND (is_agency = false OR is_agency IS NULL);

-- Salary by seniority
SELECT 
    seniority,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY (salary_min + salary_max) / 2) as median_salary,
    COUNT(*) as n
FROM enriched_jobs
WHERE job_family = '{job_family}' 
  AND city_code IN ('nyc', 'den', 'sfo')
  AND salary_min IS NOT NULL
  AND (is_agency = false OR is_agency IS NULL)
GROUP BY seniority
HAVING COUNT(*) >= 10;

-- Seniority premium
-- Calculate: (senior_median - mid_median) / mid_median
```

### Data Quality Metrics

```sql
-- Agency rate (before filtering)
SELECT 
    COUNT(*) FILTER (WHERE is_agency = true)::float / COUNT(*) as agency_rate,
    COUNT(*) FILTER (WHERE is_agency = true) as agency_count,
    COUNT(*) FILTER (WHERE is_agency = false OR is_agency IS NULL) as direct_count
FROM enriched_jobs
WHERE job_family = '{job_family}' AND city_code = '{city_code}';
-- Benchmark: <10% = clean, 10-25% = moderate, >25% = high agency activity

-- Full description coverage (internal source filter)
SELECT 
    COUNT(*) FILTER (WHERE source IN ('greenhouse', 'lever'))::float / COUNT(*) as full_desc_rate
FROM enriched_jobs
WHERE job_family = '{job_family}' AND city_code = '{city_code}'
  AND (is_agency = false OR is_agency IS NULL);
```

## Industry Clustering

**LLM-inferred from employer names** (no structured industry field):

```
Prompt for industry clustering:

Given this list of companies hiring for {job_family} roles in {city}:
{employer_list}

Group them into 5-8 industry clusters. For each company, assign ONE primary industry.

Suggested industries (adapt as needed):
- Fintech & Financial Services
- Enterprise SaaS
- Consumer Tech / B2C
- E-commerce & Retail
- Healthcare & Biotech
- Media & Entertainment
- Infrastructure & Dev Tools
- Agency / Consultancy

Return as JSON:
{
  "industries": [
    {"name": "Fintech & Financial Services", "companies": ["Company A", "Company B"], "job_count": 45},
    ...
  ]
}
```

## Content Templates

### LinkedIn Post Template

```markdown
[Hook - surprising stat or question]

I analyzed [X] job postings across [cities] to understand [topic].

Here's what I found:

📊 [Point 1 with specific number]
📊 [Point 2 with specific number]  
📊 [Point 3 with specific number]

The takeaway for job seekers: [Actionable insight]

The takeaway for hiring managers: [Actionable insight]

---
Full report: [link]

#HiringTrends #[JobFamily] #[City]
```

**Guidelines:**
- Lead with surprising/counterintuitive finding
- Use specific numbers, not vague claims
- Split takeaways by audience
- Keep under 1,300 characters for optimal engagement
- 3-5 hashtags max

### Blog Article Structure

```markdown
# [Title: Question or Surprising Statement]

## TL;DR
[3-4 bullet points with key findings]

## The Data
- X direct employer job postings analyzed
- [Job Family] roles in [Location]
- [Time period]
- Agency listings excluded for accuracy

## Finding 1: [Headline]
[2-3 paragraphs with data]
[Visualization placeholder]

## Finding 2: [Headline]
[2-3 paragraphs with data]
[Visualization placeholder]

## Finding 3: [Headline]
[2-3 paragraphs with data]
[Visualization placeholder]

## What This Means

### For Job Seekers
- [Actionable insight 1]
- [Actionable insight 2]

### For Hiring Managers  
- [Actionable insight 1]
- [Actionable insight 2]

## Methodology
[Standard methodology block from report template]

---
*[Author bio and links]*
```

### Gamma.app Export Format

For monthly/quarterly reports destined for gamma.app:

- Each H2 section becomes a slide
- Hero stats: Use **bold** or large numbers
- Keep body text under 50 words per section
- Use bullet points for data lists
- Let Gamma generate charts from bullet-point data

## Analysis Workflows

### Weekly Hiring Pulse

Quick snapshot for social media:

```sql
-- This week's activity
WITH this_week AS (
    SELECT *
    FROM enriched_jobs
    WHERE posted_date > CURRENT_DATE - INTERVAL '7 days'
      AND (is_agency = false OR is_agency IS NULL)
),
last_week AS (
    SELECT COUNT(*) as jobs
    FROM enriched_jobs
    WHERE posted_date BETWEEN CURRENT_DATE - INTERVAL '14 days' 
                          AND CURRENT_DATE - INTERVAL '7 days'
      AND (is_agency = false OR is_agency IS NULL)
)
SELECT 
    COUNT(*) as new_jobs,
    COUNT(DISTINCT employer_name) as active_employers,
    ROUND((COUNT(*)::float / lw.jobs - 1) * 100, 1) as wow_change
FROM this_week, last_week lw
GROUP BY lw.jobs;
```

Output format:
```markdown
## Weekly Hiring Pulse - [Date]

**New Jobs:** X (+Y% vs last week)
**Active Employers:** X
**Top City:** [City] (X jobs)

Highlights:
- [Trend 1]
- [Trend 2]
```

### City Comparison

```sql
SELECT 
    city_code,
    COUNT(*) as total_jobs,
    COUNT(*) FILTER (WHERE job_family = 'data') as data_jobs,
    COUNT(*) FILTER (WHERE job_family = 'product') as product_jobs,
    COUNT(*) FILTER (WHERE job_family = 'delivery') as delivery_jobs,
    ROUND(COUNT(*) FILTER (WHERE working_arrangement = 'remote')::float / COUNT(*) * 100, 1) as remote_pct,
    ROUND(COUNT(*) FILTER (WHERE seniority IN ('junior', 'mid'))::float / COUNT(*) * 100, 1) as entry_pct
FROM enriched_jobs
WHERE (is_agency = false OR is_agency IS NULL)
GROUP BY city_code
ORDER BY total_jobs DESC;
```

### Skills Demand

```sql
-- Top skills (full descriptions only - internal source filter)
SELECT 
    skill->>'name' as skill_name,
    skill->>'family_code' as family,
    COUNT(*) as mentions,
    COUNT(DISTINCT employer_name) as employers,
    ROUND(COUNT(*)::float / (SELECT COUNT(*) FROM enriched_jobs 
        WHERE source IN ('greenhouse', 'lever')
        AND (is_agency = false OR is_agency IS NULL)) * 100, 1) as pct_of_jobs
FROM enriched_jobs, jsonb_array_elements(skills) as skill
WHERE source IN ('greenhouse', 'lever')
  AND (is_agency = false OR is_agency IS NULL)
GROUP BY skill->>'name', skill->>'family_code'
ORDER BY mentions DESC
LIMIT 20;

-- Skill co-occurrence
WITH skill_pairs AS (
    SELECT 
        a.skill->>'name' as skill_a,
        b.skill->>'name' as skill_b,
        e.id as job_id
    FROM enriched_jobs e,
         jsonb_array_elements(e.skills) as a(skill),
         jsonb_array_elements(e.skills) as b(skill)
    WHERE a.skill->>'name' < b.skill->>'name'
      AND e.source IN ('greenhouse', 'lever')
      AND (e.is_agency = false OR e.is_agency IS NULL)
)
SELECT skill_a, skill_b, COUNT(*) as co_occurrences
FROM skill_pairs
GROUP BY skill_a, skill_b
HAVING COUNT(*) >= 10
ORDER BY co_occurrences DESC
LIMIT 15;
```

## Output Standards

### Always Include

1. **Data quality signal:** Agency filter stats, job count
2. **Time period:** Explicit date range
3. **Caveats:** Note limitations (coverage, compensation availability)
4. **Persona framing:** Split insights for job seekers vs hiring managers

### Never Include (in public output)

1. **Specific data sources:** Don't mention source names in reports/posts (use internally for filtering)
2. **Unfiltered data:** Always exclude agencies
3. **London/Singapore salary data:** Skip compensation for these markets
4. **Skills from truncated descriptions:** Only use source-filtered jobs for skills analysis

### Formatting

- Use specific numbers over vague language ("34%" not "about a third")
- Lead with the most surprising finding
- Include benchmarks for context ("15:1 ratio—well above the 10:1 threshold for competitive markets")
- Show deltas and comparisons where possible (+15%, 2x more likely)
