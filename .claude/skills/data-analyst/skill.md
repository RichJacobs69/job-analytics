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

# Generate portfolio report WITH month-over-month comparison
python pipeline/report_generator.py --city lon --family data --start 2025-12-01 --end 2025-12-31 --compare-start 2025-11-01 --compare-end 2025-11-30 --output portfolio
```

### Month-over-Month Comparison

The report generator supports MoM comparisons for 4 sections:
- **Industry Distribution** - Tracks industry hiring shifts
- **Top Employers** - Shows employer market share changes
- **Role Specialization** - Monitors subfamily demand changes
- **Seniority Distribution** - Tracks seniority level shifts

When `--compare-start` and `--compare-end` are provided, each section includes a `comparison` object:

```json
{
  "comparison": {
    "previousPeriod": "November 2025",
    "biggestGainer": { "label": "AI & Machine Learning", "change": 4.0 },
    "biggestDecline": { "label": "Consumer Tech", "change": -2.5 },
    "newEntries": null
  }
}
```

The portfolio site renders this as a compact "Biggest Movers" summary box below each chart.

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

### Market Context Deduplication

When generating reports for multiple cities, each city's Market Context section must feature **city-specific insights**, not verbatim shared macro trends. Shared national or global statistics (e.g., "AI postings 45% above pre-pandemic levels") should be:

1. **Referenced briefly** with local grounding (e.g., "consistent with Denver's 24% ML Engineer share")
2. **Not copy-pasted identically** across cities -- adapt framing and emphasis per market
3. **Limited to 1-2 shared items max** per city; prioritize local context (city-specific industry shifts, employer moves, policy impacts)

### Source Geographic Relevance

**Every external citation must be geographically relevant to the city being reported on.**

| City | Acceptable Sources | NOT Acceptable |
|------|--------------------|----------------|
| London | UK-specific data (ONS, HMRC, UK recruiter reports) | US labor market data (Indeed Hiring Lab US, BLS) |
| Singapore | Singapore/APAC data (MOM Singapore, regional reports) | US or UK labor market data |
| NYC, Denver, SF | US national data (with "nationally" qualifier), city-specific data | UK or APAC data |

- US-sourced stats (Indeed Hiring Lab, BLS) must **never** appear in London or Singapore market context
- When using national US data for a US city, qualify with "nationally" or "across the US" -- do not present national aggregates as city-level findings
- If no geographically relevant source exists for a market context item, **drop the item** rather than misapply a source from another geography

### Source Citation

**Every external claim must include a source.**

Format: `[Finding] ([Source Name], [Date])`

Example:
> "The 15% increase in remote roles may reflect the broader pullback from strict RTO mandates, with several major tech employers softening their in-office requirements in Q4 (WSJ, November 2024)."

### Tone: Neutral, Data-Driven Language

**Core principle: Let the data speak. Use numbers and benchmarks, not adjectives.**

#### Hedging Causal Claims

| Avoid | Use Instead |
|-------|-------------|
| "This is because..." | "This likely reflects..." |
| "The reason is..." | "This could be driven by..." |
| "This proves that..." | "This aligns with..." / "This is consistent with..." |
| "Companies are doing X because..." | "This may indicate that..." |
| "reflecting X" (unhedged) | "likely reflecting X" / "consistent with X" |
| "The shift indicates..." (from MoM data) | "Based on a single month's movement, this may indicate..." |
| "Roles are being absorbed into..." (from MoM data) | "Based on a single month's movement, the decline may indicate..." |

#### Word Blocklist

Never use these words in report content. They editorialize rather than describe.

| Category | Blocked Words | Use Instead |
|----------|--------------|-------------|
| **Emotive adjectives** | remarkable, impressive, stunning, extraordinary, exceptional, incredible, outstanding, fierce | (remove adjective, or use: high, broad, notable) |
| **Power language** | dominate, dominated, dominates, dominant, dominance, commanding, powerhouse, crushing | leads, accounts for, represents the largest share |
| **Catastrophe language** | collapse, collapsed, plunge, explode, skyrocket, soar | declined sharply, dropped, grew, increased |
| **Editorializing** | epicenter, fundamental shift, game-changing, unprecedented | center, shift, change |
| **Vague intensifiers** | significant, dramatic, massive, huge, tremendous, robust | (use the specific number instead, or: notable, wide) |
| **Certainty language** | clearly, obviously, undoubtedly, certainly, definitely, proves | (remove, or hedge with: may, likely, appears to) |

#### Correct Patterns

| Instead of | Write |
|-----------|-------|
| "The market shows remarkable flexibility with 72% remote" | "The market offers 72% remote availability" |
| "Fintech dominates at 23%" | "Fintech leads at 23%" |
| "Mid-level roles collapsed -9.2pp" | "Mid-level roles declined -9.2pp" |
| "A dramatic shift toward ML engineering" | "ML engineering's share grew +3.8pp to 40%" |
| "Despite significant economic headwinds" | (remove -- unsourced external claim) |

### Data Scope: Avoiding Whole-Market Claims

**Core principle: Our data represents a slice of the market, not the whole market.**

Our sources (direct employer integrations and job board aggregators) skew toward tech-forward and scaling companies. Large enterprises using other hiring platforms are underrepresented. All commentary must reflect this limited scope.

#### Language Rules

| Avoid | Use Instead |
|-------|-------------|
| "[City]'s data market is..." | "Among tracked employers, [City]'s data hiring shows..." |
| "X% market share" | "X% of tracked roles/postings" |
| "The market is highly fragmented" | (remove -- sampling artifact, see below) |
| "Broadly distributed employer landscape" | (remove -- sampling artifact, see below) |
| "Competing against X% of the market" | "Among direct employer postings, X% offer..." |
| "The most fragmented employer landscape" | (remove -- sampling artifact, see below) |
| "All data hiring in [city]" | "All tracked roles" |
| "X% of the market" | "X% of tracked roles/direct employer postings" |
| "The most accessible market" | "The most accessible of tracked cities" |

#### Employer Concentration Is a Sampling Artifact -- Do NOT Editorialize

**Our direct employer sources (Greenhouse, Lever, Ashby, Workable) skew toward startups and scale-ups.** Large enterprises use Workday, Taleo, and SuccessFactors, which we do not scrape. A single bank or big tech company could have more data roles than our entire top 10. Therefore:

- **NEVER** describe employer concentration as a market finding (e.g., "broadly distributed", "highly fragmented", "distributed hiring")
- **NEVER** present "jobs per employer" or "top 5 concentration" as evidence of market health or opportunity
- **NEVER** frame low concentration as positive for job seekers ("wide range of opportunities", "substantial choice")
- **DO** present these metrics factually with "Among tracked employers" as the benchmark label
- **DO** keep the raw numbers (jobs per employer, top 5 %) -- they describe our sample, not the market

| Blocked Phrases | Why |
|-----------------|-----|
| "broadly distributed employer landscape" | Sampling artifact, not a market finding |
| "highly/very fragmented" | Sampling artifact |
| "distributed hiring" | Sampling artifact |
| "no single employer dominates" | Would change if we added enterprise ATS |
| "creates diverse opportunities" (re: concentration) | Causal claim from biased data |

#### Where This Matters Most

- **meta.summary** - Always qualify with "among tracked employers" or similar
- **keyFindings narratives** - Avoid definitive pronouncements about what a city's market "is"
- **Employer concentration metrics** - These are sampling artifacts; present factually with "Among tracked employers" benchmark, never editorialize
- **Employer size/maturity/ownership distributions** - These reflect our sample bias; present as "among tracked employers"
- **Working arrangement claims** - Always specify "direct employer postings"; never claim flexibility rates apply to the whole market
- **Cross-city comparisons** - Use "across tracked cities" not "across all markets"
- **Takeaways** - When citing percentages from our data, clarify they are from tracked roles

#### Required Disclosures

Every report must include:

1. **dataNote**: "Based on [N] direct employer postings from [N]+ companies, sourced via direct employer integrations and job board aggregators. This sample skews toward tech-forward and scaling companies; large enterprises may be underrepresented. Recruitment agency listings excluded."

2. **methodology.limitations[0]**: "Not a complete census of the market - direct employer sources and job board aggregators over-represent tech-forward and scaling companies; large enterprises may be underrepresented"

**IMPORTANT: Do NOT name specific ATS platforms in report content.** Use generic terms: "direct employer integrations", "direct employer sources", "direct employer postings", or "job board aggregators".

---

## Data Context

### Available Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `enriched_jobs` | Classified job postings | All taxonomy fields |
| `employer_metadata` | Enriched company data | industry, employer_size, founding_year, ownership_type |
| `raw_jobs` | Unprocessed postings | title, description, posting_url |

### Location Filtering (CRITICAL)

**Always use inclusive location filtering** for ALL queries. A city market report includes all jobs accessible to candidates in that city, not just jobs with local offices.

**Use the `locations` JSONB field, NOT `city_code`** (legacy field with drift issues).

**Inclusive filtering includes:**

| Filter Type | Example | Description |
|-------------|---------|-------------|
| Direct city | `{"city": "london"}` | Jobs based in the city |
| Global remote | `{"scope": "global"}` | Remote jobs open to anyone |
| Country remote | `{"scope": "country"}` | Remote jobs scoped to the country |
| Country-wide | `{"type": "country"}` | Jobs open anywhere in the country |
| Region | `{"region": "EMEA"}` | Jobs open to the region (London/EMEA, US cities/AMER) |

**Example query pattern:**
```python
# Build inclusive OR filter for any city
def build_location_filter(city: str, country_code: str, region: str = None):
    parts = [
        f'locations.cs.[{{"city":"{city}"}}]',
        'locations.cs.[{"scope":"global"}]',
        'locations.cs.[{"scope":"country"}]',
        'locations.cs.[{"type":"country"}]'
    ]
    if region:
        parts.append(f'locations.cs.[{{"region":"{region}"}}]')
    return ','.join(parts)

# Usage
or_filter = build_location_filter('london', 'GB', 'EMEA')
query = supabase.table('enriched_jobs').or_(or_filter)
```

**Why inclusive?** Job seekers care about ALL roles they're eligible for - local, remote, and regional. Reports should reflect candidate opportunity, not just local office presence.

**Coverage note:** Our direct employer source coverage varies by city. Job counts reflect our source coverage, not total market size. See "Data Scope: Avoiding Whole-Market Claims" above.

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

### Working Arrangement Analysis

**CRITICAL: Direct employer sources only (Adzuna excluded).** The report_generator filters to direct employer sources (Greenhouse, Lever, Ashby, Workable) for working arrangement analysis. Adzuna is excluded because:
- Truncated descriptions (100-200 chars) cause the classifier to default to "onsite"
- Employer metadata fallback has only ~17% coverage for Adzuna employers
- Including Adzuna inflates onsite from ~3% to ~52% -- a misleading artifact

Jobs with `unknown` arrangement are excluded from the distribution.

### Compensation Analysis

**Only for US cities with pay transparency laws (nyc, den, sfo).**

For London and Singapore, skip compensation section with note:
> "Compensation data excluded due to low disclosure rates in markets without pay transparency legislation."

---

## Report Generation Workflow

### Monthly/Quarterly Market Report

1. **Confirm inputs** (see Pre-Generation Checklist)

2. **Run report generator with MoM comparison:**
   ```bash
   python pipeline/report_generator.py \
     --city {city} --family {family} \
     --start {start} --end {end} \
     --compare-start {prev_start} --compare-end {prev_end} \
     --output portfolio \
     --save "portfolio-site/content/reports/{city}-data-{month}-{year}.json"
   ```

   Example for December 2025 with November comparison:
   ```bash
   python pipeline/report_generator.py \
     --city lon --family data \
     --start 2025-12-01 --end 2025-12-31 \
     --compare-start 2025-11-01 --compare-end 2025-11-30 \
     --output portfolio \
     --save "portfolio-site/content/reports/london-data-december-2025.json"
   ```

3. **Search for market context** - Run web searches for economic/industry context:
   ```
   [city] tech hiring [month] [year]
   [city] layoffs OR hiring freeze [month] [year]
   [job_family] job market trends [year]
   remote work policy changes [year]
   ```
   Limit to 3-4 focused searches per city to manage context. See "Parallel Report Generation" below for multi-city workflows.

4. **Validate data volume** - If < 30 jobs, do not publish report

5. **Fill in [PLACEHOLDER] content** - The report generator outputs data with placeholder markers. You MUST replace all placeholders with interpretive content based on the data and market context.

6. **Save completed JSON** to `portfolio-site/content/reports/{city}-data-{month}-{year}.json`

### Placeholder Content Checklist

The report generator creates these sections with `[PLACEHOLDER]` markers that require manual content:

| Section | Field | Content Required |
|---------|-------|------------------|
| `meta` | `summary` | SEO meta description only (not displayed inline on page). 1-2 sentences for search engines and social sharing. Do NOT repeat key findings content. |
| `keyFindings` | `narrative[]` | 3 paragraphs: role composition, employer landscape, accessibility |
| `keyFindings` | `bullets[]` | 5 findings with title + text, lead with most surprising |
| `takeaways` | `jobSeekers[]` | 5 actionable insights for candidates |
| `takeaways` | `hiringManagers[]` | 4 strategic insights for employers |
| `industryDistribution` | `interpretation` | Explain top industries + MoM shifts with context |
| `companyMaturity` | `interpretation` | Explain maturity distribution implications |
| `ownershipType` | `interpretation` | Explain private/public mix implications |
| `employerSize` | `interpretation` | Explain enterprise/scale-up/startup distribution |
| `topEmployers` | `interpretation` | Highlight notable employers + new entrants |
| `roleSpecialization` | `interpretation` | Explain role mix + MoM shifts |
| `seniorityDistribution` | `interpretation` | Explain seniority mix + accessibility |
| `icVsManagement` | `interpretation` | Explain IC/management split |
| `workingArrangement` | `interpretation` | Explain flexibility patterns |
| `skillsDemand` | `interpretation` | Explain skill patterns + pairs |
| `marketContext[]` | 5 items | External context with source citations |

### Content Guidelines for Placeholders

1. **Use hedged language** for causal claims ("likely reflects", "may indicate")
2. **Cite external sources** for market context claims (Source, Date)
3. **Reference MoM changes** where comparison data exists (+X.Xpp, -X.Xpp)
4. **Be specific** with numbers ("24%" not "about a quarter")
5. **Split by persona** for takeaways (job seekers vs hiring managers)
6. **Industry coverage inline** -- `industryDistribution.interpretation` must mention coverage % in the first sentence (e.g., "Among tracked employers with industry data (52% coverage), ..."), consistent with how company metadata sections (maturity, ownership, size) already do it
7. **Single-month hedging** -- MoM changes are single-month movements, not trends. Always qualify speculation derived from MoM data with "based on a single month's movement" or "in the most recent month"

### Local Testing

After creating the report JSON, verify it renders correctly:

1. Start the portfolio-site dev server:
   ```bash
   cd portfolio-site && npm run dev
   ```

2. View the report at:
   ```
   http://localhost:3000/hiring-market/reports/{city}-data-{month}-{year}
   ```

3. Verify:
   - All charts render with data
   - MoM comparison boxes appear below Industry, Top Employers, Role Specialization, and Seniority sections
   - No `[PLACEHOLDER]` text visible in any section
   - Source citations appear in Market Context section

---

### Parallel Report Generation (Multi-City)

When generating reports for multiple cities, use this workflow to avoid sub-agent context exhaustion.

**Problem:** A single sub-agent that reads a large JSON file (~15-35KB), runs web research, and writes the completed JSON will exceed context limits and crash. The report JSON + web search results + Write tool call can consume 70-100K tokens.

**Solution:** Split the work across the main context and lightweight Edit-only sub-agents.

#### Recommended Workflow

1. **Run report generators in parallel** (one Bash call per city, all in background):
   ```bash
   python pipeline/report_generator.py --city {city} --family data \
     --start {start} --end {end} \
     --compare-start {prev_start} --compare-end {prev_end} \
     --output portfolio \
     --save "portfolio-site/content/reports/{city}-data-{month}-{year}.json"
   ```

2. **From the main context**, read each city's data (using targeted offset/limit reads) and run web research (3-4 searches per city). Compile a concise data summary and research notes.

3. **Launch Edit-only sub-agents** (one per city, in parallel) with:
   - All data and research pre-computed in the prompt
   - Explicit instructions to use ONLY the Edit tool -- no Read, no WebSearch, no Write
   - The exact old_string for each placeholder and guidance on what to write
   - Tone rules and word blocklist included in the prompt

4. **Verify** from the main context: grep for `PLACEHOLDER` in each file to confirm zero remain.

#### What NOT To Do

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| Single agent: Read + WebSearch + Write | Exceeds context limits on reports >200 jobs |
| Edit-only agent that also reads the file | Burns context on data reads before reaching edits |
| Edit-only agent that also does web research | Burns context on search results before reaching edits |
| Using Write tool for placeholder filling | Sends entire 25-35KB JSON into context; use Edit instead |

#### Context Budget Guide

| Action | Approximate Tokens |
|--------|-------------------|
| Report generator Bash output | ~5K |
| Reading full JSON file | 15-35K |
| 5 web search results | 15-25K |
| Writing full JSON via Write tool | 25-35K |
| **Total for Read+Search+Write** | **60-100K (too large)** |
| Edit call (per placeholder) | ~0.5-1K |
| **Total for 30 Edit calls** | **15-30K (fits easily)** |

---

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
| Working Arrangement | 30 | Direct employer sources only (Adzuna excluded); unknown excluded |
| Compensation | 20 with salary | US cities only |
| Skills Demand | 30 with skills | Source filter |
| Market Metrics | 50 | Skip cross-segment if thin |

---

## Market Metrics Reference

The report_generator calculates these automatically. Key benchmarks:

### Market Structure

| Metric | Benchmark | Note |
|--------|-----------|------|
| Jobs per employer | "Among tracked employers" | Sampling artifact -- do NOT editorialize |
| Top 5 concentration | "Among tracked employers" | Sampling artifact -- do NOT editorialize |

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
