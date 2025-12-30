# Hiring Market Report Template

## Metadata & Generation Config

```yaml
report_config:
  job_family: "product" | "data" | "delivery"  # One per report
  location: "lon" | "nyc" | "den" | "sfo" | "sgp"  # Note: "remote" and "unk" exist in taxonomy but not used for market reports
  period: "monthly" | "quarterly"
  period_label: "December 2025"  # Human-readable
  
thresholds:
  minimum_jobs_to_publish: 30
  minimum_for_full_section: 20
  minimum_for_granular_breakdown: 10
  sparse_data_warning: true  # Auto-add caveats when below thresholds

# Location display names for reports
location_labels:
  lon: "London"
  nyc: "New York"
  den: "Denver"
  sfo: "San Francisco"
  sgp: "Singapore"

# Job family display names for reports  
job_family_labels:
  product: "Product Management"
  data: "Data Roles"
  delivery: "Project & Delivery"
```

---

## Section Overview

| # | Section | Purpose | Data Requirements |
|---|---------|---------|-------------------|
| 1 | Executive Summary | Hook with headline stats | Basic counts |
| 1b | Data Quality Signal | Agency-filtered trust badge | is_agency, agency_confidence |
| 2 | Key Takeaways: Job Seekers | Actionable candidate insights | All sections |
| 3 | Key Takeaways: Hiring Managers | Strategic talent insights | All sections |
| 4 | Top Employers | Market fragmentation | employer.name |
| 5 | Industry Distribution | Sector breakdown | LLM-inferred from employers |
| 6 | Employer Size | Startup vs enterprise mix | company_size_estimate |
| 7 | Role Specialization | Subfamily breakdown | job_subfamily |
| 8 | Seniority Distribution | Career level demand | seniority |
| 9 | IC vs Management | Track split | track |
| 10 | Working Arrangement | Remote/hybrid/onsite | working_arrangement |
| 11 | Compensation | Salary benchmarks | salary data (US cities only) |
| 12 | Skills Demand | Capability expectations | skills (full descriptions only) |
| 13 | Contextual Metrics | Derived insights | Calculated from above |
| 14 | About / Methodology | Credibility + CTA | Static |

**Location-specific rules:**
- **London (lon)**: Skip compensation section entirely (no UK pay transparency laws)
- **Singapore (sgp)**: Skip compensation section (no pay transparency laws)
- **NYC (nyc)**: Full compensation analysis (NY pay transparency law)
- **Denver (den)**: Full compensation analysis (Colorado pay transparency law)
- **San Francisco (sfo)**: Full compensation analysis (California pay transparency law)
- **All locations**: Skills section limited to roles with full job descriptions

---

## Report Structure

### 1. Cover / Executive Summary

**Purpose:** Hook the reader with 3-4 headline findings. This is what people see on LinkedIn before clicking "see more."

**Required fields:**
- `job_family` (display label)
- `location.city_code` (display label)
- `period_label`
- `total_jobs` (count of jobs in report)

**Content blocks:**

#### Headline Stat (Required)
The single most interesting finding. Pick the most surprising or actionable insight.

```
Example: "Technical and AI-focused PM positions now account for almost 1/3 of all openings."
```

#### Key Findings (3-4 bullets)
Short, specific, number-backed claims.

```
Example:
- 80% of roles are Individual Contributor positions
- Senior-level openings account for almost ½ of all demand  
- Technical and AI/ML roles comprise 30%
```

**Generation logic:**
- Calculate subfamily distribution → surface any category >25% as notable
- Calculate seniority distribution → highlight dominant tier
- Calculate track split (IC vs management) → note if skewed >70% either way
- Compare to previous period if available → call out significant shifts (±5pp)

---

### 1b. Data Quality Signal

**Purpose:** Differentiate from noisy job boards by highlighting direct employer postings. Job seekers hate agency spam—this is a trust signal.

**Required fields:**
- `employer.is_agency`
- `employer.agency_confidence`

**Content block:**

```
Example:
"This report includes X direct employer postings. Y agency listings (Z%) were identified and excluded from analysis."
```

Or as a badge/callout:
```
✓ Agency-filtered: 94% direct employer roles
```

**Display options:**
1. **Badge format** (recommended for Gamma): Single line with checkmark, shown prominently
2. **Detailed format**: Full sentence with counts, used in methodology section

**Metrics to surface:**
- `direct_employer_count`: Jobs where is_agency = false
- `agency_count`: Jobs where is_agency = true
- `agency_rate`: agency_count / total_jobs (before filtering)
- `direct_employer_rate`: 1 - agency_rate

**Filtering logic:**
- High confidence agencies (is_agency = true, agency_confidence = high): Always exclude
- Medium confidence agencies: Exclude by default, flag count
- Low confidence: Include but monitor

**Why this matters:**
- Agencies often post duplicate/stale roles
- Agency postings obscure actual employer demand
- Direct postings = higher signal for market analysis
- Differentiates your reports from Indeed/LinkedIn noise

---

### 2. Key Takeaways by Audience

**Purpose:** Immediately answer "what does this mean for me?" for both primary audiences. Front-load the value—don't make readers dig.

#### For Job Seekers (3-4 bullets)

Actionable insights for candidates. Focus on:
- Where to focus search (hot subfamilies, growing employers)
- Realistic expectations (seniority distribution, entry difficulty)
- Differentiators (skills in demand, underserved niches)
- Flexibility options (remote availability, startup vs enterprise)

```
Example:
- Target Technical and AI/ML PM roles—nearly 1/3 of openings, likely less competition per role than Core PM
- Senior-level experience is table stakes; 80% of roles require 3+ years
- SQL and Python fluency are baseline expectations—lack of these will filter you out early
- Remote-only candidates face a constrained market (13% of roles)—consider hybrid flexibility
```

**Tone:** Direct, realistic, no false optimism. Job seekers appreciate honesty over cheerleading.

#### For Hiring Managers & Recruiters (3-4 bullets)

Strategic insights for talent acquisition. Focus on:
- Competitive positioning (how crowded is your niche)
- Compensation benchmarking (where disclosed)
- Talent pool signals (what candidates expect)
- Market timing (hiring velocity, seasonal patterns)

```
Example:
- You're competing with Figma, JPMorgan, and Capital One for PM talent—differentiate on mission or flexibility
- The market is fragmented (top 15 employers = 15%)—strong employer brand matters less than role clarity
- 80% of roles are IC track—if you're hiring managers, you have less competition but a thinner candidate pool
- Candidates expect hybrid as default (52%)—onsite-only policies may limit your funnel
```

**Tone:** Strategic, benchmark-oriented. Help them understand the competitive landscape.

**Generation logic:**
- Pull 2 insights from market composition (employer concentration, size distribution)
- Pull 2 insights from role structure (seniority, track, subfamily)
- Pull 1-2 insights from candidate expectations (arrangement, skills, comp where available)
- Frame each for the specific audience's decision-making context

---

### 4. Market Composition: Top Employers

**Purpose:** Show market fragmentation and identify major hiring players.

**Required fields:**
- `employer.name`
- Count of jobs per employer

**Thresholds:**
- Show top 10-15 employers
- Only include employers with ≥2 jobs
- If top 15 employers represent <20% of market, note "highly fragmented"

**Content blocks:**

#### Concentration metric
```
Example: "The market is highly fragmented, with the top 15 employers representing almost 15% of the total market."
```

#### Employer groupings (Optional)
If natural clusters emerge (e.g., Finance vs Tech), group them. Otherwise, single ranked list.

```
Example groupings:
- Design & Tech Giants: Figma (14), Google (4), Microsoft (4)
- Finance & Fintech: JPMorgan Chase (12), Capital One (9)
```

**Sparse data rule:**
- If <50 total jobs, reduce to top 5 employers
- If top employer has >20% of all jobs, call this out explicitly

---

### 5. Industry Distribution

**Purpose:** Show which sectors are driving hiring demand. Helps candidates target industries and hiring managers understand competitive landscape.

**Data source:** LLM-inferred from employer names. No structured industry field required.

**Classification approach:**
```
Prompt: "Given this list of company names hiring for [job_family] roles, 
group them into 5-8 industry clusters. For each company, assign ONE 
primary industry. Return industry name, company list, and job count."

Example industries:
- Fintech & Financial Services
- Enterprise SaaS
- Consumer Tech / B2C
- E-commerce & Retail
- Healthcare & Biotech
- Media & Entertainment
- Infrastructure & Dev Tools
- Agency / Consultancy
```

**Content blocks:**

#### Industry breakdown (percentage of roles)
```
Example:
- Non-Fintech: 86%
- Fintech/Financial Services: 14%
```

Or more granular:
```
- Enterprise SaaS: 28%
- Fintech & Banking: 22%
- Consumer Tech: 18%
- E-commerce: 12%
- Healthcare: 8%
- Other: 12%
```

#### Industry sub-segments (where meaningful)
For large categories, break down further:

```
Fintech & Financial Services (14%):
- Traditional Banks: JPMorgan Chase, BNY Mellon, Citigroup
- Payment Processors: Capital One, Visa, Mastercard
- Neobanks: Wise, Monzo
- Crypto: Coinbase, Kraken
```

#### Interpretation
```
Example: "The 'London = Fintech' stereotype has some truth—but SaaS, marketing tech, and general technology account for the majority of PM hiring."
```

**Sparse data rules:**
- If any industry cluster has <5 jobs, merge into "Other"
- Limit to 6-8 industries max for readability
- Always show "Other" category to avoid false precision

**Generation logic:**
1. Extract unique employer names from dataset
2. Send to LLM with classification prompt
3. Aggregate job counts by assigned industry
4. Calculate percentages and rank
5. Identify sub-segments for top 2-3 industries

---

### 6. Employer Size Distribution

**Purpose:** Signal whether the market skews toward stability (enterprise) or growth (startup).

**Required fields:**
- `employer.company_size_estimate` (startup | scaleup | enterprise)

**Content blocks:**

#### Percentage breakdown
```
Example:
- Enterprise (1,000+): 45%
- Scale-up (50-1,000): 32%  
- Startup (<50): 23%
```

#### Interpretation sentence
Frame what this means for the job seeker.

```
Example: "London offers more stability-focused PM roles than pure startup ecosystems, with a heavy enterprise presence."
```

**Sparse data rule:**
- If `company_size_estimate` is null for >40% of jobs, add caveat: "Company size estimated for X% of roles based on available data."
- If any category has <10 jobs, combine into "Other" or skip percentage

---

### 7. Role Specialization (Subfamily Breakdown)

**Purpose:** Show which subspecialties dominate and which are emerging.

**Required fields:**
- `role.job_subfamily`

**Content blocks:**

#### Percentage breakdown by subfamily
For Product:
```
- Core PM: 55%
- Technical PM: 20%
- AI/ML PM: 10%
- Platform PM: 8%
- Growth PM: 5%
```

For Data:
```
- Data Engineer: 28%
- Data Scientist: 22%
- Data Analyst: 18%
- Analytics Engineer: 12%
- ML Engineer: 10%
- AI Engineer: 5%
- Product Analytics: 3%
- Research Scientist: 2%
- Data Architect: 1%
```

For Delivery:
```
- Project Manager: 40%
- Programme Manager: 25%
- Delivery Manager: 22%
- Scrum Master: 13%
```

#### Interpretation
Call out the growth story or surprising finding.

```
Example: "While Core PM roles dominate, technical specialisation is the clear growth area with almost 4 in 10 roles requiring a technical, platform or AI specialism."
```

**Sparse data rule:**
- If any subfamily has <5 jobs, group into "Other specializations"
- If >3 subfamilies have <10 jobs each, simplify to top 4 + "Other"

---

### 8. Seniority Distribution (Career Level Demand)

**Purpose:** Help candidates understand where the demand is and realistic entry points.

**Required fields:**
- `role.seniority` (junior | mid | senior | staff_principal | director_plus)
- Optionally: `role.track` to separate IC seniority from management titles

**Content blocks:**

#### Percentage breakdown
```
- Junior: 4%
- Mid-Level: 17%
- Senior: 59%
- Staff/Principal: 6%
- Director+: 14%
```

#### Interpretation
```
Example: "The London market values experience with almost 80% of roles requiring seasoned Product Managers. Entry continues to be challenging for juniors."
```

**Sparse data rule:**
- If junior roles <5, note "Limited entry-level opportunities identified"
- If staff_plus + director combined <10 jobs, merge into "Senior+"

---

### 9. IC vs Management Track

**Purpose:** Show career path options available in the market.

**Required fields:**
- `role.track` (ic | management)

**Content blocks:**

#### Percentage split
```
- Individual Contributor: 80%
- Management: 20%
```

#### Context
If management roles cluster in specific employers or sectors, call it out.

```
Example: "There are leadership opportunities in Finance—Capital One, JPMorgan Chase and BNY Mellon alone have 21 open management positions."
```

**Sparse data rule:**
- If management track <10 jobs, just report the number rather than percentage
- If track classification confidence is low (>30% uncertain), add caveat

---

### 10. Working Arrangement Breakdown

**Purpose:** Critical filter for many job seekers post-COVID.

**Required fields:**
- `location.working_arrangement` (onsite | hybrid | remote | flexible | unknown)

**Content blocks:**

#### Percentage breakdown
```
- Hybrid: 48%
- Onsite: 30%
- Remote: 12%
- Flexible: 8%
- Unknown: 2%
```

Note: "Flexible" means employer offers choice (remote OR hybrid OR onsite). Report as distinct category.

#### Interpretation
```
Example: "Hybrid dominates, but fully remote roles remain scarce—candidates prioritizing remote work face a constrained market."
```

**Sparse data rule:**
- If working_arrangement is null for >30% of jobs, add caveat: "Working arrangement specified in X% of postings."
- If remote <10 jobs, report count not percentage

---

### 11. Compensation Insights (US Cities Only: NYC, Denver, San Francisco)

**Purpose:** Provide salary benchmarking where data permits.

**IMPORTANT: London and Singapore are excluded from this section.** Neither market has pay transparency laws, and salary disclosure rates are too low for meaningful analysis. For these reports, skip this section entirely with note: "Compensation data excluded due to low disclosure rates in markets without pay transparency legislation."

**Included locations:** NYC, Denver, San Francisco (all have state/local pay transparency laws requiring salary ranges in job postings)

**Required fields:**
- `compensation.base_salary_range.min`
- `compensation.base_salary_range.max`
- `compensation.currency`

**Content blocks:**

#### Salary distribution
```
Example:
- 25th percentile: $125,000
- Median: $155,000
- 75th percentile: $190,000
- Interquartile range: $65,000 (indicates pay band spread)
```

#### Salary by seniority (if sufficient data)
```
Example:
- Mid-Level median: $130,000
- Senior median: $165,000
- Staff+ median: $210,000
- Senior-to-Mid premium: +27%
```

#### Salary by subfamily (if sufficient data)
```
Example:
- Data Engineer median: $160,000
- Data Scientist median: $175,000
- ML Engineer median: $195,000
```

#### Histogram buckets (for visualization)
```
Salary distribution:
- $80-100K: 8%
- $100-120K: 15%
- $120-140K: 22%
- $140-160K: 25%
- $160-180K: 18%
- $180-200K: 8%
- $200K+: 4%
```

**Sparse data rules (STRICT):**
- Only publish if ≥30% of jobs have salary data
- Only break down by seniority if each tier has ≥10 salary data points
- Always caveat with: "Based on X roles with disclosed salary ranges."
- Report IQR alongside median to show spread

**Skip conditions:**
- Location IN (London, Singapore) → Skip entirely
- If <20 jobs have salary data → Skip with note about disclosure rates

---

### 12. Skills Demand

**Purpose:** Surface trending skills and capability expectations.

**INTERNAL NOTE (not for publication): Exclude Adzuna-sourced jobs from this analysis.** Adzuna provides truncated descriptions that don't reliably capture skills. Only use sources with full job text.

**Required fields:**
- `skills.items.name`
- `skills.items.family_code`
- `posting.source` (filter to full-description sources only)

**Content blocks:**

#### Top skills by frequency
```
Top 10 most mentioned skills (based on X roles with full descriptions):
1. SQL (45%)
2. Python (38%)
3. Data Analysis (32%)
4. A/B Testing (28%)
5. Stakeholder Management (25%)
...
```

#### Skill families breakdown

For Product/Data roles:
```
- Programming: 52% of roles mention at least one programming skill
- Analytics/Statistics: 45%
- Data/ML Tools: 38%
- Cloud Platforms: 22%
- Product Skills: 65% (for PM roles)
```

For Delivery roles:
```
- Methodologies & Frameworks: 78% (Agile, Scrum, SAFe, PRINCE2)
- Delivery Tools: 65% (JIRA, Confluence, MS Project)
- Certifications: 42% (PMP, CSM, PRINCE2 certification)
- Governance & Risk: 35% (Risk management, stakeholder management)
```

#### Skill co-occurrence (what skills cluster together)
```
Common skill pairs:
- Python + SQL: 72% co-occurrence
- SQL + Data Analysis: 68%
- A/B Testing + Statistics: 55%
- AWS + Python: 45%
```

#### Skills by seniority (if sufficient data)
```
Skills more common at Senior+ level:
- Stakeholder Management: 45% (Senior+) vs 20% (Junior/Mid)
- Strategy: 38% vs 12%
- ML/AI: 28% vs 15%

Skills emphasized at Junior/Mid level:
- SQL: 55% vs 40%
- Data Analysis: 48% vs 35%
```

#### Skills by subfamily (if sufficient data)
```
Distinguishing skills by role type:
- Data Engineer: Spark (42%), Airflow (35%), AWS (48%)
- Data Scientist: Python (68%), Statistics (52%), ML (45%)
- ML Engineer: PyTorch (38%), Kubernetes (32%), MLOps (28%)
```

**Sparse data rules:**
- Only include skills mentioned in ≥5% of filtered jobs
- Minimum 30 jobs with full descriptions required for this section
- If <30 full-description jobs available, skip section with note: "Skills analysis requires full job descriptions. This section will be available when more detailed role data is captured."
- For co-occurrence, only report pairs appearing in ≥10 jobs

---

### 13. Market Context & Comparative Metrics

**Purpose:** Add analytical depth with derived metrics that contextualize findings. These help readers understand not just "what" but "how significant."

**Content blocks:**

#### Market Structure Metrics

```yaml
market_depth:
  formula: "total_jobs / unique_employers"
  interpretation: "Average jobs per hiring company"
  example: "1.4 jobs per employer indicates highly distributed hiring"
  benchmark: "<1.5 = fragmented, 1.5-3 = moderate, >3 = concentrated"

employer_concentration:
  formula: "sum(top_5_employer_jobs) / total_jobs"
  interpretation: "Market share of top 5 hirers"
  example: "Top 5 employers = 12% of market"
  benchmark: "<15% = fragmented, 15-30% = moderate, >30% = concentrated"

specialization_index:
  formula: "sum(top_3_subfamilies) / total_jobs"
  interpretation: "How concentrated is hiring in few role types"
  example: "78% of roles in top 3 subfamilies"
  benchmark: ">80% = specialized market, <60% = diverse market"
```

#### Data Quality Metrics

```yaml
agency_rate:
  formula: "count(is_agency=true) / total_raw_jobs"
  interpretation: "Recruitment agency noise in raw data"
  example: "18% of raw postings were agency listings"
  benchmark: "<10% = clean market, 10-25% = moderate noise, >25% = high agency activity"
  note: "High agency rates may indicate talent scarcity or recruiter-heavy market"

direct_employer_rate:
  formula: "count(is_agency=false) / total_raw_jobs"
  interpretation: "Proportion of direct employer postings"
  example: "82% direct employer roles after filtering"

source_quality_mix:
  formula: "count(has_full_description=true) / total_jobs"
  interpretation: "Proportion of roles with complete job descriptions"
  example: "45% of roles have full descriptions available for skills analysis"
  note: "Higher proportion = better skills analysis quality"
```

#### Accessibility Metrics

```yaml
senior_to_junior_ratio:
  formula: "count(senior+) / count(junior)"
  interpretation: "Competition intensity for entry roles"
  example: "15:1 ratio—expect fierce competition for junior positions"
  benchmark: ">10:1 = very competitive entry, 5-10:1 = competitive, <5:1 = accessible"

entry_accessibility_rate:
  formula: "count(junior + mid) / total_jobs"
  interpretation: "Percentage of roles accessible to <3 years experience"
  example: "21% of roles open to early-career candidates"
  
management_opportunity_rate:
  formula: "count(management_track) / total_jobs"
  interpretation: "Leadership pathway availability"
  example: "1 in 5 roles offer people management track"
```

#### Flexibility Metrics

```yaml
remote_availability_index:
  formula: "count(remote) / total_jobs"
  interpretation: "Full remote options available"
  example: "1 in 8 roles offer fully remote work"
  
flexibility_score:
  formula: "(count(remote) + count(hybrid)) / total_jobs"
  interpretation: "Roles with any location flexibility"
  example: "65% of roles offer hybrid or remote arrangements"
  
startup_flexibility_comparison:
  formula: "remote_rate(startup) vs remote_rate(enterprise)"
  interpretation: "Do startups offer more flexibility?"
  example: "Startups: 25% remote vs Enterprise: 8% remote"
```

#### Compensation Metrics (US cities: NYC, Denver, San Francisco)

```yaml
salary_spread:
  formula: "75th_percentile - 25th_percentile"
  interpretation: "Pay band width (IQR)"
  example: "$65K spread indicates wide negotiation range"
  
seniority_premium:
  formula: "(senior_median - mid_median) / mid_median"
  interpretation: "Pay bump for leveling up"
  example: "+27% premium for Senior vs Mid-level"
  
subfamily_premium:
  formula: "Compare median across subfamilies"
  interpretation: "Which specializations pay more"
  example: "ML Engineers earn 18% more than Data Analysts at same level"
```

#### Cross-Segment Comparisons

Generate 2-3 notable comparisons that surface interesting patterns:

```
Example comparisons:
- "Enterprise companies are 3x more likely to require onsite work than startups"
- "AI/ML PM roles pay 22% more than Core PM roles at the same seniority"
- "Finance sector accounts for 40% of management-track roles but only 14% of IC roles"
- "Remote roles are 2x more common in Data Engineering than Product Management"
```

**Generation logic:**
1. Calculate all base metrics for the dataset
2. Compare across meaningful segments (employer size, subfamily, industry, seniority)
3. Surface comparisons with >20% difference or >2x ratio
4. Limit to 3-5 most interesting/actionable comparisons
5. Ensure statistical validity (both segments have ≥10 jobs)

---

### 14. About / Methodology / CTA

**Purpose:** Build credibility and drive engagement.

**Content blocks:**

#### About the author (static)
```
Hey there! I'm Rich—I specialise in data product management and have spent 8 years building technical products. I created this job market intelligence platform to help candidates, recruiters, and employers understand what's really happening in hiring.
```

#### Methodology (semi-static)
```
This report analyzes [X] direct employer job postings for [Job Family] roles in [Location] during [Period].

Data sources: Aggregated from major job boards and company applicant tracking systems.

Data quality measures:
- Agency filtering: Recruitment agency postings are identified and excluded using company name patterns, job description signals, and confidence scoring. [Y] agency listings ([Z]%) were removed from this analysis.
- Deduplication: Jobs reposted within 30 days are consolidated to avoid double-counting.
- Classification: Roles are classified using an LLM-powered taxonomy covering subfamily, seniority, skills, and working arrangement.

Limitations:
- Some roles posted exclusively on company career sites may not be captured.
- Skills analysis is limited to roles with full job descriptions available.
- Salary data is only available for US markets with pay transparency laws.
```

#### Links
- LinkedIn: rjacobsuk
- Website: richjacobs.me
- Email: rich@richjacobs.me

---

## Conditional Section Logic

```yaml
section_rules:
  data_quality_signal:
    min_jobs: 30
    required_fields: [is_agency]
    fallback: "Show total job count without agency breakdown if is_agency field unavailable"
    
  key_takeaways:
    min_jobs: 30
    fallback: "Generate with heavy caveats about limited sample"
    
  top_employers:
    min_jobs: 30
    fallback: "Skip section"
    
  industry_distribution:
    min_jobs: 30
    min_unique_employers: 15
    fallback: "Skip section—too few companies for meaningful clustering"
    
  employer_size:
    min_jobs: 30
    min_coverage: 0.6  # 60% of jobs must have size estimate
    fallback: "Add caveat about limited data"
    
  subfamily_breakdown:
    min_jobs: 30
    min_per_category: 5
    fallback: "Combine small categories into 'Other'"
    
  seniority_distribution:
    min_jobs: 30
    min_per_tier: 3
    fallback: "Combine junior+mid, combine staff+director"
    
  track_split:
    min_jobs: 30
    min_management: 5
    fallback: "Report management as count, not percentage"
    
  working_arrangement:
    min_jobs: 30
    min_coverage: 0.7
    fallback: "Add caveat about unspecified arrangements"
    
  compensation:
    locations: ["nyc", "den", "sfo"]  # London and Singapore excluded entirely
    min_jobs_with_salary: 20
    min_coverage: 0.3
    fallback: "Skip section with note about disclosure rates"
    excluded_location_fallback: "Skip entirely with note about lack of pay transparency laws"
    
  skills:
    sources: ["full_description"]  # Internal: filter to sources with complete job text
    min_jobs_from_sources: 30
    fallback: "Skip section with note about requiring full job descriptions"
    
  contextual_metrics:
    min_jobs: 50
    fallback: "Show only market structure metrics, skip cross-segment comparisons"
```

---

## Sparse Data Caveat Templates

Use these when thresholds aren't met:

```markdown
# For low overall sample
> ⚠️ This analysis is based on [X] roles—a smaller market segment. Percentages may shift significantly with additional data.

# For missing field data
> Note: [Field name] was specified in [X]% of postings. Analysis reflects available data only.

# For thin category breakdowns  
> Categories with fewer than 10 roles have been grouped to ensure meaningful comparisons.

# For compensation specifically
> Salary data reflects [X] roles ([Y]%) with disclosed compensation. Markets without pay transparency laws typically show lower disclosure rates.

# For agency filtering
> ✓ [X] agency listings identified and excluded to ensure analysis reflects direct employer demand.

# For high agency rate markets
> Note: [X]% of raw postings in this market were agency listings—higher than typical. This may indicate increased recruiter activity or talent scarcity.
```

---

## Output Format for gamma.app

Gamma works best with:
- Clear H1/H2 hierarchy
- Short paragraphs (2-3 sentences max)
- Bullet points for lists
- Explicit percentage callouts (use large text for hero stats)
- **Data tables for every stat** — Gamma visualizes tables into charts; don't just quote numbers in prose
- **Round percentages to whole numbers** — No one cares about 20.9% vs 21%; use "21%"
- **Double-check the year** — Use the current year from today's date; do not default to prior years

**Recommended structure for Gamma import:**
1. Each H2 section becomes a slide
2. Hero stats use H1 or bold large text
3. Keep body text under 50 words per slide
4. Include data tables with all comparative/contextual stats
5. Let Gamma generate charts from your table data

---

## Example Generation Prompt (for Claude Code skill)

```
Generate a hiring market report for {job_family} roles in {location} for {period}.

## Data Sources

Primary query - enriched_jobs table:
- job_family = '{job_family}'
- city_code = '{location}'  
- posted_date BETWEEN '{start_date}' AND '{end_date}'

For skills analysis only:
- Filter to sources with full job descriptions (has_full_description = true)

For compensation analysis:
- Only if location IN ('nyc', 'den', 'sfo')
- Skip entirely for London and Singapore

## Generation Steps

1. Run base queries to get job counts and validate thresholds
2. Check minimum 30 jobs to proceed
3. Generate executive summary with headline stat
4. Generate persona-specific takeaways (job seekers + hiring managers)
5. For each section, check threshold rules before generating
6. Calculate contextual metrics and cross-segment comparisons
7. Add appropriate caveats for sparse data
8. Output as markdown suitable for gamma.app import

## Output Format

- Use H2 for section headers (becomes Gamma slides)
- Hero stats in bold or large text
- Keep body text concise (<50 words per section)
- Use bullet points for data lists
- Include percentage and absolute numbers where helpful
```
