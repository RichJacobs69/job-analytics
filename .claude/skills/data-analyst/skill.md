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

| Resource | Purpose |
|----------|---------|
| `pipeline/report_generator.py` | **Codified queries** - All SQL logic for report generation |
| `docs/templates/hiring_report_template.md` | Master template for market reports |
| `docs/schema_taxonomy.yaml` | Classification taxonomy (v1.5.0) |
| `docs/marketplace_questions.yaml` | Questions the platform answers |

---

## Report Generator Script

**All queries are codified in `pipeline/report_generator.py`** to ensure consistency across reports.

### Quick Start

```bash
# Generate report data summary
python pipeline/report_generator.py --city lon --family data --start 2025-12-01 --end 2025-12-31

# Generate JSON output for programmatic use
python pipeline/report_generator.py --city lon --family data --start 2025-12-01 --end 2025-12-31 --output json
```

### Using Programmatically

```python
from pipeline.report_generator import ReportGenerator

generator = ReportGenerator()
data = generator.generate_report_data(
    city_code='lon',
    job_family='data',
    start_date='2025-12-01',
    end_date='2025-12-31'
)

# Access structured data
print(data['summary']['total_jobs'])
print(data['seniority']['distribution'])
print(data['skills']['top_skills'])
print(data['market_metrics']['accessibility']['senior_to_junior_ratio'])
```

### Output Structure

The `generate_report_data()` method returns:

```python
{
    'meta': { 'city_code', 'job_family', 'start_date', 'end_date', 'generated_at' },
    'summary': { 'total_jobs', 'direct_jobs', 'agency_jobs', 'agency_rate', 'unique_employers' },
    'employers': { 'unique_employers', 'jobs_per_employer', 'top_5_concentration', 'top_15_concentration', 'top_employers' },
    'seniority': { 'distribution', 'coverage', 'senior_to_junior_ratio', 'entry_accessibility_rate' },
    'subfamily': { 'distribution', 'coverage' },
    'track': { 'distribution', 'coverage' },
    'working_arrangement': { 'distribution', 'coverage' },
    'skills': { 'total_with_skills', 'coverage', 'top_skills', 'skill_pairs' },
    'metadata_enrichment': { 'industry', 'employer_size', 'maturity', 'ownership', 'match_rate' },
    'compensation': { 'available', 'overall', 'by_seniority', 'by_subfamily' },  # US cities only
    'market_metrics': { 'structure', 'accessibility', 'flexibility', 'data_quality' },
}
```

### Portfolio Site JSON

After generating a report, create a JSON file for the portfolio site:

```
portfolio-site/content/reports/{city}-data-{month}-{year}.json
```

See existing files (e.g., `sf-data-december-2025.json`) for the required schema.

---

## Pre-Generation Checklist

**STOP. Before writing any code or generating any report, confirm ALL of the following with the user:**

### Required Inputs

| Input | Question to Ask | Example Values |
|-------|-----------------|----------------|
| **Time period** | "Which month/quarter and year?" | December 2025, Q4 2024 |
| **Job family** | "Which job family: Product, Data, Delivery, or all?" | data, product, delivery |
| **Location(s)** | "Which city/cities?" | NYC, London, Denver, SF, Singapore |
| **Output type** | "What outputs do you need: full report, summary, LinkedIn post, or all?" | full report + summary |

### Confirmation Template

```
Before I generate this report, confirming:
- **Time period:** [month/quarter + year]
- **Job family:** [product/data/delivery]
- **Location:** [city]
- **Outputs:** [full report / summary / LinkedIn post]

Correct?
```

**Do not proceed until user confirms.**

---

## Report Segmentation Standard

### Default: Location x Job Family

The atomic unit for reports is **one location + one job family**.

**Standard naming:** `[City] [Job Family] Market - [Month] [Year]`

Examples:
- "NYC Data & Analytics Market - December 2025"
- "London Product Management Market - Q4 2024"
- "Denver Project & Delivery Market - January 2026"

### Allowed Variations (on request only)

| Rollup Type | Example | When to Use |
|-------------|---------|-------------|
| Multi-city, single family | "US Data Market" | Comparative analysis across markets |
| Single city, multi-family | "NYC Tech Hiring" | City-level thought leadership |
| Single family, all cities | "Global PM Hiring" | Function-specific insights |

---

## Interpretive Commentary Requirements

**Reports must go beyond "what the numbers say" to explain "why this matters."**

### Web Research Requirement

For each report, search for relevant context on:
- **Economic factors:** Fed rate decisions, recession indicators, hiring freezes/thaws
- **Policy changes:** RTO mandates, immigration policy, pay transparency laws
- **Industry news:** Major layoffs, funding trends, M&A activity
- **Seasonal patterns:** Budget cycles, Q1 hiring surges, holiday slowdowns

**Search queries to run:**
```
[city] tech hiring [month] [year]
[job_family] job market trends [year]
[city] layoffs OR hiring freeze [month] [year]
remote work policy changes [year]
```

### Source Citation

**Every external claim must include a source.**

Format: `[Finding] ([Source Name], [Date])`

Example:
> "The 15% increase in remote roles may reflect the broader pullback from strict RTO mandates, with several major tech employers softening their in-office requirements in Q4 (WSJ, November 2024)."

### Tone: Hedged Speculation

| Avoid | Use Instead |
|-------|-------------|
| "This is because..." | "This likely reflects..." |
| "The reason is..." | "This could be driven by..." |
| "This proves that..." | "This aligns with..." |
| "Companies are doing X because..." | "This may indicate that..." |

---

## Data Context

### Available Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `enriched_jobs` | Classified job postings | All taxonomy fields |
| `employer_metadata` | Enriched company data | industry, employer_size, founding_year, ownership_type |
| `raw_jobs` | Unprocessed postings | title, description, posting_url |

### Taxonomy Reference (v1.5.0)

**Job Families:** product, data, delivery, out_of_scope

**Data Subfamilies:** data_engineer, ml_engineer, data_analyst, data_scientist, data_architect, product_analytics, analytics_engineer, research_scientist_ml, ai_engineer

**Locations:**

| Code | Label | Compensation Data |
|------|-------|-------------------|
| `lon` | London | Skip (no transparency laws) |
| `nyc` | New York | Full analysis |
| `den` | Denver | Full analysis |
| `sfo` | San Francisco | Full analysis |
| `sgp` | Singapore | Skip (no transparency laws) |

**Seniority:** junior, mid, senior, staff_principal, director_plus

**Working Arrangement:** onsite, hybrid, remote, flexible, unknown

**Track:** ic, management

### Industry Codes

| Code | Display Label |
|------|---------------|
| `ai_ml` | AI & Machine Learning |
| `data_infra` | Data Infrastructure |
| `fintech` | Fintech |
| `financial_services` | Financial Services |
| `healthtech` | Healthcare & Biotech |
| `consumer` | Consumer Tech |
| `ecommerce` | E-commerce & Retail |
| `professional_services` | Professional Services |
| `mobility` | Mobility & Transportation |
| `martech` | Marketing Technology |
| `cybersecurity` | Cybersecurity |
| `hr_tech` | HR Technology |
| `proptech` | Property Technology |
| `devtools` | Developer Tools |
| `edtech` | Education Technology |
| `climate` | Climate & Sustainability |
| `crypto` | Crypto & Web3 |
| `productivity` | Productivity Software |
| `other` | Other |

---

## Data Quality Rules

### Agency Filtering

Always exclude agency postings. The report_generator handles this automatically.

Report in methodology: "X agency listings (Y%) identified and excluded"

### Skills Analysis

Only jobs with full descriptions (skills coverage in output). If < 30 jobs with skills, skip section with note:
> "Skills analysis requires full job descriptions. Insufficient data for this market segment."

### Compensation Analysis

**Only for US cities with pay transparency laws (nyc, den, sfo).**

For London and Singapore, skip compensation section with note:
> "Compensation data excluded due to low disclosure rates in markets without pay transparency legislation."

---

## Report Generation Workflow

### Monthly/Quarterly Market Report

1. **Confirm inputs** (see Pre-Generation Checklist)

2. **Run report generator:**
   ```bash
   python pipeline/report_generator.py --city {city} --family {family} --start {start} --end {end} --output json
   ```

3. **Search for market context** - Run web searches for economic/industry context

4. **Validate data volume** - If < 30 jobs, do not publish report

5. **Generate markdown report** using template at `docs/templates/hiring_report_template.md`

6. **Create portfolio JSON** at `portfolio-site/content/reports/{city}-data-{month}-{year}.json`

### Section Thresholds

| Section | Min Jobs | Special Rules |
|---------|----------|---------------|
| Executive Summary | 30 | Lead with surprising finding |
| Key Takeaways | 30 | Split by persona |
| Top Employers | 30 | Top 10-15, min 2 jobs each |
| Industry Distribution | 30 | Need metadata coverage |
| Company Maturity | 30 | Need founding_year data |
| Ownership Type | 30 | Need ownership_type data |
| Employer Size | 30 | Need 60% coverage |
| Role Specialization | 30 | Combine <5 into "Other" |
| Seniority Distribution | 30 | Add entry accessibility context |
| IC vs Management | 30 | Report count if mgmt <10 |
| Working Arrangement | 30 | Need 70% coverage |
| Compensation | 20 with salary | US cities only |
| Skills Demand | 30 with skills | Source filter |
| Market Metrics | 50 | Skip cross-segment if thin |

---

## Market Metrics Reference

The report_generator calculates these automatically. Key benchmarks:

### Market Structure

| Metric | Benchmark |
|--------|-----------|
| Jobs per employer | <1.5 fragmented, 1.5-3 moderate, >3 concentrated |
| Top 5 concentration | <15% fragmented, 15-30% moderate, >30% concentrated |

### Accessibility

| Metric | Benchmark |
|--------|-----------|
| Senior-to-junior ratio | >10:1 very competitive, 5-10:1 competitive, <5:1 accessible |
| Entry accessibility | % of junior + mid roles |
| Management opportunity | % of management track roles |

### Maturity Categories

| Category | Age | Description |
|----------|-----|-------------|
| Young | <=5 yrs | Early-stage, higher risk/reward |
| Growth | 6-15 yrs | Scale-up phase, Series B+ typically |
| Mature | >15 yrs | Established enterprises |

---

## Content Templates

### LinkedIn Post Template

```markdown
[Hook - surprising stat or question]

I analyzed [X] job postings across [cities] to understand [topic].

Here's what I found:

[Point 1 with specific number]
[Point 2 with specific number]
[Point 3 with specific number]

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
- Keep under 1,300 characters
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
[2-3 paragraphs with data + interpretation + source citation]

## Finding 2: [Headline]
[2-3 paragraphs with data + interpretation + source citation]

## What This Means

### For Job Seekers
- [Actionable insight 1]
- [Actionable insight 2]

### For Hiring Managers
- [Actionable insight 1]
- [Actionable insight 2]

## Methodology
[Standard methodology block]
```

---

## Output Standards

### Always Include

1. **Data quality signal:** Agency filter stats, job count
2. **Time period:** Explicit date range
3. **Caveats:** Note limitations (coverage, compensation availability)
4. **Persona framing:** Split insights for job seekers vs hiring managers
5. **Interpretive context:** Hedged commentary with external source citations

### Never Include (in public output)

1. **Unfiltered data:** Always exclude agencies
2. **London/Singapore salary data:** Skip compensation for these markets
3. **Skills from truncated descriptions:** Only use jobs with skills data
4. **Unsourced speculation:** All "why" commentary needs external citation

### Formatting

- Use specific numbers over vague language ("34%" not "about a third")
- Lead with the most surprising finding
- Include benchmarks for context ("15:1 ratio - well above the 10:1 threshold")
- Show deltas and comparisons where possible (+15%, 2x more likely)
- Hedged language for all causal claims
