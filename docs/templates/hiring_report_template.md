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
| 1 | Key Findings | Verbose summary with headline + narrative + bullets | All sections |
| 2 | Key Takeaways: Job Seekers | Actionable insights for candidates | All sections |
| 3 | Key Takeaways: Hiring Managers | Strategic insights for talent acquisition | All sections |
| 4 | Market Metrics | Derived contextual insights (structure, accessibility, flexibility) | Calculated |
| 5 | Market Context | External factors and comparative analysis | Research |
| 6 | Industry Distribution | Sector breakdown | employer_metadata.industry |
| 7 | Company Maturity | Young/growth/mature split | employer_metadata.founding_year |
| 8 | Ownership Type | Public vs private hiring | employer_metadata.ownership_type |
| 9 | Employer Size | Startup vs enterprise mix | employer_metadata.employer_size |
| 10 | Top Employers | Market fragmentation | employer.name |
| 11 | Role Specialization | Subfamily breakdown | job_subfamily |
| 12 | Seniority Distribution | Career level demand | seniority |
| 13 | IC vs Management | Track split | track |
| 14 | Working Arrangement | Remote/hybrid/onsite | working_arrangement |
| 15 | Compensation | Salary benchmarks (overall + by subfamily) | salary data (US cities only) |
| 16 | Skills Demand | Capability expectations | skills (full descriptions only) |
| 17 | Methodology | Credibility, data quality notes, CTA | Static |

**Location-specific rules:**
- **London (lon)**: Skip compensation section entirely (no UK pay transparency laws)
- **Singapore (sgp)**: Skip compensation section (no pay transparency laws)
- **NYC (nyc)**: Full compensation analysis (NY pay transparency law)
- **Denver (den)**: Full compensation analysis (Colorado pay transparency law)
- **San Francisco (sfo)**: Full compensation analysis (California pay transparency law)
- **All locations**: Skills section limited to roles with full job descriptions

---

## Tone & Voice Guidelines

These principles apply to ALL narrative content across reports. Consistency in voice builds credibility and reader trust.

### Core Principles

| Principle | Do | Don't |
|-----------|----|----- |
| **Analytical over promotional** | "The 18:1 ratio indicates fierce competition" | "Exciting opportunities await!" |
| **Specific over vague** | "25% of roles require <3 years experience" | "Entry is competitive" |
| **Honest over optimistic** | "Entry is brutal - consider other markets first" | "Opportunities exist for everyone" |
| **Contextual over absolute** | "38% ML - nearly double NYC's 24%" | "38% of roles are ML" |
| **Actionable over descriptive** | "Target the modern data stack: dbt, Snowflake, Airflow" | "Various tools are in demand" |

### Section-Specific Tone

| Section | Tone | Rationale |
|---------|------|-----------|
| **Key Findings** | Verbose and analytical | Establish credibility through depth; explain "so what" not just "what" |
| **Job Seeker Takeaways** | Direct, realistic, no false optimism | Job seekers appreciate honesty over cheerleading |
| **Hiring Manager Takeaways** | Strategic, benchmark-oriented | Help them understand competitive positioning |
| **Interpretations** | Concise but insightful | One strong observation > three weak ones |
| **Market Context** | Factual with external grounding | Cite sources; connect data to real-world factors |

### Voice Characteristics

**Be verbose and interpretive.** Don't just present data - explain what it means and why it matters.

**Too sparse:**
> ML Engineer (38%) is the most common role.

**Good:**
> ML Engineering dominates the SF data market in a way that's unique among US cities. At 38% of all roles, it's nearly double the concentration seen in NYC (24%) or Denver (20%). This reflects the city's position as the global center for AI research and development. For job seekers, ML skills aren't just valuable - they're the primary path to maximizing opportunity in this market.

### Language Standards

| Pattern | Use | Avoid |
|---------|-----|-------|
| Comparisons | "nearly double", "3x more likely", "outpaces" | "more than", "higher than" (too weak) |
| Certainty | "indicates", "suggests", "reflects" | "proves", "definitely", "always" |
| Numbers | "1 in 4 roles", "four in ten", "a quarter" | Overuse of raw percentages |
| Hedging | "With 61% coverage, this likely understates..." | Pretending sparse data is definitive |
| Emphasis | "THE path", "exceptionally competitive", "remarkable" | Excessive superlatives |

### Phrases to Use

- "This reflects..." / "This signals..."
- "The takeaway is clear:"
- "What makes [X] distinctive..."
- "For candidates, this means..."
- "Candidates should recognize that..."
- "The data suggests..."
- "Notably, ..." / "Importantly, ..."

### Phrases to Avoid

- "Exciting opportunities" (promotional)
- "Great news for job seekers" (cheerleading)
- "As you can see" (filler)
- "It's worth noting that" (weak hedging)
- "Interestingly" (overused)
- "In conclusion" (unnecessary)
- Any emoji usage

### Verbs: Neutral Over Emotional

Use neutral, factual verbs. Avoid dramatic or emotional language that implies judgment.

| Avoid (emotional) | Use instead (neutral) |
|-------------------|----------------------|
| dominates, dominating | leads, accounts for, represents |
| crushing, brutal | competitive, challenging |
| exploding, surging | growing, increasing |
| plummeting, collapsing | declining, decreasing |
| thriving, booming | strong, robust |
| struggling | facing headwinds, contracting |
| commanding | holding, representing |
| emerging as | becoming, now represents |

**Example:**
- Avoid: "ML Engineering dominates the market"
- Use: "ML Engineering leads at 25%" or "ML Engineering accounts for 25% of roles"

The data speaks for itself - emotional verbs suggest we're selling a narrative rather than presenting facts.

### Balancing Honesty with Helpfulness

Reports should be **realistic without being discouraging**. Frame challenges as information, not obstacles.

**Too negative:**
> Entry-level candidates have almost no chance in this market.

**Balanced:**
> The 18:1 senior-to-junior ratio makes SF the most competitive US market for entry. Early-career candidates should consider building experience in Denver (6:1) or NYC (10:1) before targeting SF roles.

The goal is empowering readers with actionable intelligence, not demoralizing them or giving false hope.

---

## CRITICAL: Market Climate Research (Pre-Generation Requirement)

**Before generating any report, you MUST research the current hiring climate to ensure takeaways reflect market reality.**

Our job posting data shows *what* is being hired. External sources tell us *whether* hiring is healthy, frozen, or contracting. Without this context, our advice may be dangerously out of touch.

### Required Research Sources

Query these sources before writing Key Takeaways:

| Source | What It Tells Us | Search Query |
|--------|------------------|--------------|
| [Indeed Hiring Lab](https://www.hiringlab.org/) | Job posting volume trends, hiring freeze indicators | `site:hiringlab.org tech hiring [current year]` |
| [Crunchbase News](https://news.crunchbase.com/) | Layoff counts, funding trends, VC activity | `site:news.crunchbase.com layoffs [current year]` |
| [TechCrunch Layoffs](https://techcrunch.com/) | Running tally of tech layoffs | `site:techcrunch.com tech layoffs [current year] list` |
| [Bureau of Labor Statistics](https://www.bls.gov/) | Official employment statistics | `site:bls.gov data scientist employment` |
| [World Economic Forum](https://www.weforum.org/) | AI impact on jobs, future of work | `site:weforum.org AI jobs [current year]` |
| [LinkedIn Economic Graph](https://economicgraph.linkedin.com/) | Hiring rate trends, skills demand | `site:linkedin.com hiring trends [job_family] [current year]` |

### Key Questions to Answer

Before writing takeaways, establish:

1. **Is hiring expanding or contracting?**
   - How do current job posting volumes compare to 12 months ago?
   - Are there active hiring freezes in the sector?
   - What is the current layoff rate?

2. **Who has leverage - candidates or employers?**
   - In a hiring freeze, employers have leverage (more candidates per role)
   - In a boom, candidates have leverage (multiple offers, negotiating power)
   - This determines salary negotiation advice

3. **How is AI affecting this job family?**
   - Which tasks are being automated?
   - Are role definitions changing?
   - Are traditional roles shrinking while new roles emerge?

4. **What is the funding environment?**
   - Is VC funding flowing or frozen?
   - Which sectors are receiving investment?
   - How does this affect startup vs enterprise hiring?

### How This Affects Takeaways

| Market Condition | Job Seeker Advice | Hiring Manager Advice |
|------------------|-------------------|----------------------|
| **Hiring freeze / layoffs** | Be realistic about competition (laid-off workers are applying). Salary negotiation power is limited. Consider stability over upside. | You have more leverage. Median offers may suffice. Speed is less critical - candidates have fewer options. |
| **Hiring boom** | Negotiate aggressively. Multiple offers are possible. Target 75th percentile. | Budget for 75th percentile or lose candidates. Speed is critical. |
| **AI disruption** | Traditional roles are shrinking. Emphasize AI-augmented skills. The role you're hired for may not exist in 2 years. | Consider how AI will change this role. Hire for adaptability, not just current skills. |
| **VC freeze (non-AI)** | Startup equity is riskier. Prefer companies with runway. | Compete on stability, not equity promises. |
| **AI funding boom** | AI companies are hiring while others freeze. Distinguish between AI and non-AI employers. | If you're not an AI company, you're competing differently. |

### Citation Requirement

Every Key Takeaway that references market conditions must cite a source:

**Good:**
> "The 21:1 senior-to-junior ratio makes SF the hardest US market for entry. Combined with a tech hiring freeze now in its third year ([Indeed Hiring Lab, July 2025](https://www.hiringlab.org/)), early-career candidates should build experience elsewhere first."

**Bad:**
> "Entry is competitive" (no context, no source)

### Market Climate Summary Block

Add a brief climate summary at the start of Key Takeaways sections:

```markdown
## Key Takeaways: Job Seekers

**Market climate (January 2026):** Tech hiring remains in a holding pattern, with job listings down 35% from pre-pandemic levels ([Indeed](https://www.hiringlab.org/)). AI roles are the exception, with AI companies capturing 50% of all VC funding ([Crunchbase](https://news.crunchbase.com/)). Employers have more leverage than in 2021-2022; salary negotiation power is limited for non-AI roles.

2.1. **First takeaway...**
```

---

## Report Structure

### 1. Key Findings

**Purpose:** Lead with a comprehensive narrative that synthesizes the most important insights. This is the "so what" of the entire report, delivered upfront.

**Structure:**
1. **Opening paragraph** - 2-3 sentences that capture the market's defining characteristics
2. **Key findings bullets** - 4-5 specific, number-backed insights that support the narrative
3. **Note on data coverage** - Brief mention of sample size and agency exclusion

**Tone:** Verbose and analytical. Don't just list facts - explain what they mean and why they matter. Use comparative context (vs other markets, vs expectations).

**Example:**

```markdown
## Key Findings

San Francisco's data market in December 2025 is unmistakably the AI capital of the United States. Nearly four in ten open roles are for ML Engineers - almost double the concentration seen in New York or Denver. This isn't just about job titles: the city's employer base tells the same story, with AI/ML companies and autonomous vehicle firms together accounting for a quarter of all hiring activity. The compensation reflects this specialization, with Research Scientists commanding median salaries around $250K and ML Engineers at $188K.

What makes SF distinctive isn't just the AI focus - it's the company profile. Over half of hiring comes from growth-stage companies (6-15 years old), the Waymo and Roblox generation that offers meaningful equity upside without early-stage risk. But this maturity comes at a cost for newcomers: the 18:1 senior-to-junior ratio is the most competitive among US markets, making SF a difficult entry point for early-career candidates.

- **ML Engineering dominance:** 38% of all roles - nearly double NYC (24%) and Denver (20%)
- **AI epicenter:** AI/ML industry (15%) and Mobility (10%) together drive a quarter of hiring
- **Premium compensation:** Research Scientist ML median $250K; ML Engineer $188K
- **Growth-stage market:** 51% of jobs at companies 6-15 years old
- **Competitive entry:** 18:1 senior-to-junior ratio, the highest among US markets

*Based on over 1,100 direct employer postings from 500+ companies. Recruitment agency listings excluded.*
```

---

### 2. Key Takeaways by Persona

**Purpose:** Translate the findings into actionable advice for the two primary audiences.

#### Key Takeaways: Job Seekers (4-5 bullets)

Actionable insights for candidates. Focus on:
- Where to focus search (hot subfamilies, growing employers)
- Realistic expectations (seniority distribution, entry difficulty)
- Differentiators (skills in demand, underserved niches)
- Flexibility options (remote availability, startup vs enterprise)
- Compensation context

**Tone:** Direct, realistic, no false optimism. Job seekers appreciate honesty over cheerleading.

```
Example:
1. **ML Engineering is THE path** - 38% of roles are ML Engineer. If you're pivoting to data in SF, ML skills maximize your options.
2. **Entry is brutal** - The 18:1 senior-to-junior ratio is the highest among US markets. Consider Denver (6:1) or NYC (10:1) for entry-level opportunities.
3. **Research Scientists are premium** - $250K median. If you have the PhD, SF pays top dollar for ML research talent.
4. **Growth-stage sweet spot** - Over half of jobs are at companies 6-15 years old. Equity upside with operational stability.
5. **AV companies are hiring aggressively** - Waymo and Zoox are among the top employers. Autonomous vehicles remain data-intensive.
```

#### Key Takeaways: Hiring Managers (3-4 bullets)

Strategic insights for talent acquisition. Focus on:
- Competitive positioning (who you're competing against)
- Compensation benchmarking (what the market pays)
- Talent pool signals (what candidates expect)

**Tone:** Strategic, benchmark-oriented. Help them understand the competitive landscape.

```
Example:
1. **Competing with Waymo and OpenAI** - The top employers are AV and AI leaders. Differentiate on mission, not just compensation.
2. **Candidates expect equity** - Private companies (20%) slightly outnumber public (19%). Equity compensation is table stakes.
3. **Staff+ is expensive** - ML Engineer median $188K, Research Scientist $250K. Budget for SF premiums.
4. **Startup talent is available** - 24% of jobs are at startups (vs 11% in NYC). Candidates comfortable with startup environments.
```

---

### 3. Industry Distribution

**Purpose:** Show which sectors are driving hiring demand. Helps candidates target industries and hiring managers understand competitive landscape.

**Data source:** `employer_metadata.industry` - use structured industry codes, NOT LLM inference.

**Industry code reference:**

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

**Content blocks:**

#### Industry breakdown (percentage of roles with industry data)
```
Example:
- AI & Machine Learning: 15%
- Mobility & Transportation: 12%
- Consumer Tech: 10%
- Fintech: 6%
- Data Infrastructure: 5%
- Other industries: 52%
```

#### Interpretation
```
Example: "AI/ML companies account for 15% of data hiring, reflecting SF's position as the global AI epicenter. The 12% mobility share is driven by autonomous vehicle companies (Waymo, Zoox)."
```

**Sparse data rules:**
- If any industry has <5 jobs, merge into "Other"
- Limit to top 8-10 industries + "Other" for readability
- Always note coverage: "Industry data available for X% of jobs"
- If coverage <30%, add caveat about limited industry visibility

**Generation logic:**
1. Join enriched_jobs with employer_metadata on normalized employer name
2. Aggregate job counts by industry code
3. Calculate percentages of total jobs with industry data
4. Report coverage rate

---

### 5. Company Maturity

**Purpose:** Show whether hiring is concentrated at early-stage startups, growth companies, or mature enterprises. Helps candidates understand risk/reward tradeoffs.

**Data source:** `employer_metadata.founding_year` - calculate company age as (current_year - founding_year).

**Maturity categories:**

| Category | Age Range | Characteristics |
|----------|-----------|-----------------|
| Young | <=5 years | Founded 2020+, early-stage, higher risk/reward |
| Growth | 6-15 years | Founded 2010-2019, scale-up phase, Series B+ typically |
| Mature | >15 years | Founded pre-2010, established enterprises |

**Content blocks:**

#### Maturity distribution
```
Example:
- Young (<=5 yrs): 12%
- Growth (6-15 yrs): 51%
- Mature (>15 yrs): 37%
```

#### Interpretation
```
Example: "SF's data market skews toward growth-stage companies (51%), reflecting the city's concentration of well-funded scale-ups. Denver's 76% mature company share indicates a more enterprise-dominated market."
```

**Sparse data rules:**
- Only publish if founding_year data available for >=20% of jobs
- Always note coverage: "Based on X jobs with company founding data"

---

### 6. Ownership Type

**Purpose:** Show public vs private company hiring patterns. Helps candidates understand equity compensation context and company stability.

**Data source:** `employer_metadata.ownership_type`

**Ownership categories:**

| Type | Description |
|------|-------------|
| `private` | VC-backed or bootstrapped |
| `public` | Listed companies (NYSE, NASDAQ, etc.) |
| `subsidiary` | Division of larger company |
| `acquired` | Recently acquired |

**Content blocks:**

#### Ownership distribution
```
Example:
- Private: 26%
- Public: 19%
- Subsidiary: 9%
```

#### Interpretation
```
Example: "Private companies account for 26% of hiring, suggesting candidates should understand equity compensation structures. The 19% public company share offers more salary transparency but typically less equity upside."
```

**Sparse data rules:**
- Only publish if ownership data available for >=15% of jobs
- Combine subsidiary + acquired if either has <10 jobs

---

### 7. Employer Size Distribution

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

### 8. Top Employers

**Purpose:** Show market fragmentation and identify major hiring players.

**Required fields:**
- `employer.name`
- Count of jobs per employer

**Thresholds:**
- Show top 10-15 employers
- Only include employers with >=2 jobs
- If top 15 employers represent <20% of market, note "highly fragmented"

**Content blocks:**

#### Employer table
```
Example:
| Employer | Jobs |
|----------|------|
| Waymo | 48 |
| Roblox | 35 |
| Block | 32 |
```

#### Employer groupings (Optional)
If natural clusters emerge (e.g., Finance vs Tech vs AV), group them.

```
Example groupings:
- AV Cluster: Waymo (48), Zoox (29)
- Finance & Fintech: Capital One (28), Block (32)
```

#### Market interpretation
Explain what the employer mix reveals about the market.

**Sparse data rule:**
- If <50 total jobs, reduce to top 5 employers
- If top employer has >20% of all jobs, call this out explicitly

---

### 9. Role Specialization (Subfamily Breakdown)

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

### 10. Seniority Distribution (Career Level Demand)

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

### 11. IC vs Management Track

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

### 12. Working Arrangement Breakdown

**Purpose:** Critical filter for many job seekers post-COVID.

**Required fields:**
- `enriched_jobs.working_arrangement` (onsite | hybrid | remote | flexible | unknown)

**Internal logic (NOT exposed in report):**
- Job-level arrangement is the primary source
- For jobs with "unknown" arrangement, use `employer_metadata.working_arrangement_default` as fallback
- **Report final aggregated figures only** - do NOT expose the two-layer data quality methodology
- Readers don't need to know about "job-level known" vs "employer defaults" - just show the effective distribution

**Content blocks:**

#### Coverage note (subtitle)
Show simple coverage: "X% of roles with known working arrangement"

#### Arrangement distribution (donut chart)
```
- Remote: 44%
- Hybrid: 23%
- Onsite: 24%
- Flexible: 9%
```

Note: "Flexible" means employer offers choice (remote OR hybrid OR onsite). Report as distinct category.

#### Interpretation
```
Example: "Remote work leads at 44%, reflecting the competitive talent market where companies must offer flexibility to attract top ML talent. Onsite (24%) and hybrid (23%) are nearly equal, while the 9% flexible rate indicates companies that offer genuine employee choice."
```

**Sparse data rule:**
- If working_arrangement is null/unknown for >30% of jobs, add caveat in interpretation
- If remote <10 jobs, report count not percentage

**JSON schema (simplified):**
```json
"workingArrangement": {
  "coverage": "67% of roles with known working arrangement",
  "data": [
    { "label": "Remote", "value": 44 },
    { "label": "Onsite", "value": 24 },
    { "label": "Hybrid", "value": 23 },
    { "label": "Flexible", "value": 9 }
  ],
  "interpretation": "Remote work leads at 44%..."
}
```

---

### 13. Compensation Insights (US Cities Only: NYC, Denver, San Francisco)

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

#### Salary by subfamily (REQUIRED for Data reports)
```
Example:
| Subfamily | Median | Sample |
|-----------|--------|--------|
| ML Engineer | $195,000 | n=150 |
| Data Scientist | $175,000 | n=120 |
| Data Engineer | $160,000 | n=140 |
| Analytics Engineer | $155,000 | n=45 |
| Data Analyst | $130,000 | n=100 |
| Product Analytics | $145,000 | n=50 |
```

**Subfamily premium calculation:**
```
ML Engineer premium vs Data Analyst: +50% ($195K vs $130K)
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

### 14. Skills Demand

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

### 4-5. Market Metrics & Market Context

**Purpose:** Add analytical depth with derived metrics that contextualize findings. These help readers understand not just "what" but "how significant." Place these sections immediately after Key Takeaways to frame the detailed analysis.

**Section 4: Market Metrics** - Quantitative benchmarks (structure, accessibility, flexibility)
**Section 5: Market Context** - Cross-segment comparisons and external factors

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

### 17. Methodology

**Purpose:** Build credibility, provide transparency about data collection, and document data quality.

**Content blocks:**

#### Methodology (semi-static)
```
This report analyzes direct employer job postings for [Job Family] roles in [Location] during [Period].

Data collection:
- Over [X] roles from [Y]+ employers aggregated from multiple sources
- Recruitment agency postings identified and excluded
- Jobs deduplicated across sources to avoid double-counting

Classification:
- Roles classified using an LLM-powered taxonomy
- Subfamily, seniority, skills, and working arrangement extracted
- Employer metadata enriched from company databases where available

Limitations:
- Not a complete census of the market - some roles may not be captured
- Skills analysis based on [X] roles with skill data ([Y]% coverage)
- Salary data only available for US markets with pay transparency laws
- Working arrangement specified in [X]% of postings
- Employer metadata (industry, size) available for [X]% of jobs
```

#### Data Quality Metrics (internal reference)

```yaml
agency_rate:
  formula: "count(is_agency=true) / total_raw_jobs"
  interpretation: "Recruitment agency noise in raw data"
  benchmark: "<10% = clean, 10-25% = moderate, >25% = high agency activity"

seniority_coverage:
  formula: "count(seniority != null) / total_jobs"
  interpretation: "Proportion of roles with seniority classification"

skills_coverage:
  formula: "count(has_skills) / total_jobs"
  interpretation: "Proportion of roles with skill data extracted"

employer_metadata_coverage:
  formula: "count(has_industry OR has_size) / total_jobs"
  interpretation: "Proportion of roles with enriched employer data"
```

**Do not:**
- Quote specific data source names or percentages (e.g., "Adzuna 68%, Greenhouse 32%")
- Quote exact agency filtering counts
- Use precise job counts in methodology (use approximations)

#### Data Coverage (display in Methodology)

Data coverage metrics should be displayed in a 4-column grid within the Methodology section:

```json
"dataQuality": [
  { "label": "Seniority coverage", "value": "85%", "description": "Roles with seniority level classified" },
  { "label": "Arrangement coverage", "value": "56%", "description": "Roles with working arrangement known" },
  { "label": "Skills coverage", "value": "84%", "description": "Roles with skills extracted from description" },
  { "label": "Employer metadata", "value": "77%", "description": "Roles with enriched company data" }
]
```

#### About & Links
```
This report was created by Rich Jacobs, a data product manager focused on hiring market intelligence.
Want the data? Contact rich@richjacobs.me

Links (on separate lines with emojis):
- [link emoji] linkedin.com/in/rjacobsuk
- [globe emoji] richjacobs.me
```

---

## Conditional Section Logic

```yaml
section_rules:
  key_findings:
    min_jobs: 30
    fallback: "Generate with heavy caveats about limited sample"

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

## Data Presentation Guidelines

### Use Percentages, Not Counts

**Key principle:** We cannot claim complete market coverage. Percentage shares are meaningful; absolute job counts can mislead readers into thinking this is the entire market.

**Rules:**
- **Never show job counts in tables or charts** - use % share only
- **Show aggregate totals once** (e.g., "over 1,100 jobs from 500+ employers") for sample size context in Key Findings
- **Round to whole numbers** - 18.1% becomes 18%, 17.8:1 becomes 18:1
- **Use approximate language for aggregates** - "over 1,100" not "1,119", "500+ employers" not "516"

**Example - Good:**
```
| Subfamily | % of Roles |
|-----------|------------|
| ML Engineer | 38% |
| Data Scientist | 22% |
| Data Engineer | 18% |
```

**Example - Avoid (counts exposed):**
```
| Subfamily | Jobs | % |
|-----------|------|---|
| ML Engineer | 426 | 38% |
| Data Scientist | 243 | 22% |
```

### Commentary Style

**Be verbose and interpretive.** Don't just present data - explain what it means.

**Example - Too sparse:**
```
ML Engineer (38%) is the most common role.
```

**Example - Good (verbose):**
```
ML Engineering dominates the SF data market in a way that's unique among US cities. At 38% of all roles, it's nearly double the concentration seen in NYC (24%) or Denver (20%). This reflects the city's position as the global center for AI research and development, where even traditional companies are building ML-first products. For job seekers, this concentration means ML skills aren't just valuable - they're the primary path to maximizing opportunity in this market.
```

### Rounding Rules

| Type | Rule | Example |
|------|------|---------|
| Percentages | Whole numbers | 18.6% → 19% |
| Ratios | One decimal max, prefer whole | 17.8:1 → 18:1 |
| Salaries | Round to nearest $1K | $177,438 → $177,000 |
| Aggregates | Use approximations | 1,119 → "over 1,100" |

---

## Chart Type Recommendations

**Add a markdown note after each table indicating the recommended chart type for visualization.**

**Format:** `*Chart: [chart type]*`

**Chart type guide by data type:**

| Data Pattern | Recommended Chart | Example Use |
|--------------|-------------------|-------------|
| Part-to-whole (single dimension) | Donut | Industry distribution, Track split (IC vs Mgmt) |
| Categorical comparison | Horizontal Bar | Top employers, Subfamily distribution |
| Ranked/ordered list | Horizontal Bar | Skills demand, Seniority distribution |
| Multi-dimensional breakdown | Stacked Bar | Seniority by subfamily, Arrangement by company size |
| Range/spread data | Stacked Bar | Salary ranges (25th/median/75th percentiles) |
| Time series | Line | Month-over-month trends |
| Salary overall distribution | Histogram | Salary distribution by $20K buckets |
| Two metrics comparison | Grouped Bar | Remote rate by company size |

### Salary Distribution Visualization

**For the overall compensation distribution, use a histogram with salary buckets.**

Salary data is typically right-skewed (not normally distributed), so a bell curve is not appropriate. Instead:

1. **Create $20K buckets** from the minimum to maximum observed
2. **Show % of roles** in each bucket (not counts)
3. **Annotate the median** with a vertical line or marker

**Example table for histogram:**
```
| Salary Range | % of Roles |
|--------------|------------|
| $80-100K | 5% |
| $100-120K | 12% |
| $120-140K | 18% |
| $140-160K | 22% |
| $160-180K | 20% |
| $180-200K | 13% |
| $200-220K | 6% |
| $220K+ | 4% |

*Chart: Histogram with median marker at $177K*
```

**When to use Stacked Bar vs Horizontal Bar:**

| Table Type | Chart | Rationale |
|------------|-------|-----------|
| Salary by Seniority | Stacked bar (25th/median/75th) | Shows salary range spread, not just median |
| Salary by Subfamily | Stacked bar (25th/median/75th) | Highlights compensation variance by role |
| Single-dimension rankings | Horizontal bar | Simple comparison (skills, employers) |
| Part-to-whole (<5 categories) | Donut | Clean visualization of composition |

**Example usage in reports:**

```markdown
| Subfamily | Jobs | % |
|-----------|------|---|
| ML Engineer | 426 | 38% |
| Data Scientist | 243 | 22% |
| Data Engineer | 202 | 18% |

*Chart: Horizontal bar*
```

```markdown
| Track | Jobs | % |
|-------|------|---|
| IC | 1,037 | 93% |
| Management | 76 | 7% |

*Chart: Donut*
```

```markdown
| Level | 25th | Median | 75th | Sample |
|-------|------|--------|------|--------|
| Junior | $95,000 | $117,000 | $140,000 | n=37 |
| Senior | $155,000 | $178,000 | $210,000 | n=466 |
| Staff+ | $190,000 | $218,000 | $250,000 | n=166 |

*Chart: Stacked bar (25th/median/75th percentiles)*
```

**Stacked bar examples:**
- Salary ranges by seniority (show 25th/median/75th as stacked segments)
- Salary ranges by subfamily (show 25th/median/75th as stacked segments)
- Seniority breakdown by role type (if cross-tabulated)
- Working arrangement by company size (if cross-tabulated)

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
- **Use % shares** — Always show percentage of analyzed jobs, not raw counts alone

**Recommended structure for Gamma import:**
1. Each H2 section becomes a slide
2. Hero stats use H1 or bold large text
3. Keep body text under 50 words per slide
4. Include data tables with all comparative/contextual stats
5. Let Gamma generate charts from your table data

---

## Web Visualization Design Standards (React/Next.js)

When generating reports for the portfolio site web visualization, follow these design standards established in the SF December 2025 prototype.

### Layout Principles

**Two-column layout for donut charts:**
- Chart + legend on left column
- Narrative interpretation on right column
- Maximizes horizontal real estate
- Legend items displayed horizontally (single line with flex-wrap)

**Card-based sections:**
- Dark background: `#1a1a1a`
- Border: `gray-800`
- Rounded corners: `rounded-xl`
- Padding: `p-6`

### Chart Component Library

| Component | Use Case | Key Props |
|-----------|----------|-----------|
| `HorizontalBarChart` | Rankings, distributions | `data`, `valueLabel`, `valueSuffix`, `height` |
| `DonutChart` | Part-to-whole (2-5 categories) | `data`, `centerValue`, `centerLabel`, `narrative` |
| `RangeBarChart` | Salary ranges (25th/median/75th) | `data` with `p25`, `median`, `p75`, `sample` |

**Note:** Salary histogram is not used - the salary by role breakdown provides more granular and relevant compensation data.

### Donut Chart with Narrative

When a donut chart has an interpretation, use the two-column layout:

```tsx
<DonutChart
  data={companyMaturity.data}
  centerValue="51%"
  centerLabel="Growth Stage"
  size={200}
  narrative={companyMaturity.interpretation}  // Enables two-column layout
/>
```

### Range Bar Chart for Salary Data

Show salary spread with 25th-75th percentile range and median marker:

```tsx
<RangeBarChart
  data={compensation.bySeniority}  // Array with p25, median, p75, sample
  height={220}
/>
```

### Market Metrics - Row-Based Layout

Organize market metrics into three rows, each with metrics displayed in 3 columns:

1. **Market Structure** - Jobs per employer, Top 5 concentration, Top 15 concentration
2. **Accessibility** - Senior-to-Junior ratio (highlighted in red), Entry accessibility, Management opportunity
3. **Flexibility** - Remote availability, Flexibility rate

**Note:** Data Quality metrics belong in the Methodology section, not Market Metrics.

Each metric should have:
- `label`: Metric name (e.g., "Jobs per employer")
- `value`: The value (e.g., "2.3" or "12%")
- `benchmark`: Interpretive label (e.g., "Moderate concentration")
- `description`: One-line explanation (e.g., "Average open roles per hiring company")

### List Formatting - Use Numbered Lists Only

**Adopt uniform numbering throughout reports. Do not mix bullets and numbers.**

Use section-based numbering with decimal notation:

```
1. Key Findings
   1.1. AI epicenter: AI/ML industry (15%) combined with Mobility (10%)...
   1.2. ML Engineer dominance: 38% of all roles...
   1.3. Premium compensation: Research Scientist ML $250K median...

2. Key Takeaways: Job Seekers
   2.1. ML Engineering is THE career path in SF...
   2.2. Entry-level is exceptionally competitive...
   2.3. Research Scientists command premium compensation...

3. Key Takeaways: Hiring Managers
   3.1. You're competing with Waymo and OpenAI for talent...
   3.2. Private equity compensation is expected...
```

**Rules:**
- Top-level sections use whole numbers (1, 2, 3...)
- Items within sections use decimal notation (1.1, 1.2, 2.1, 2.2...)
- Nested items use additional decimals if needed (1.1.1, 1.1.2...)
- Never use bullet points (-) for lists in reports
- Methodology section lists are the exception - use bullets for data collection, classification, limitations

### Color Palette

| Purpose | Color | Tailwind Class |
|---------|-------|----------------|
| Primary accent | Lime | `text-lime-400`, `bg-lime-400` |
| Secondary accent | Emerald | `text-emerald-400` |
| Warning/highlight | Red | `text-red-400` |
| Text primary | White | `text-white` |
| Text secondary | Gray 300 | `text-gray-300` |
| Text muted | Gray 400-500 | `text-gray-400`, `text-gray-500` |
| Background | Near black | `bg-[#0a0a0a]` |
| Card background | Dark gray | `bg-[#1a1a1a]` |

### Section Separators

Use horizontal rules between major sections:

```tsx
<hr className="border-gray-800 my-12" />
```

### Data File Structure (JSON)

**IMPORTANT: JSON Output Location**

JSON files MUST be saved to the portfolio-site repository, NOT to job-analytics:

```
C:\Cursor Projects\portfolio-site\content\reports\{city}-data-{month}-{year}.json
```

Example filenames:
- `london-data-december-2025.json`
- `nyc-data-december-2025.json`
- `denver-data-december-2025.json`
- `sf-data-december-2025.json`

The markdown reports stay in `job-analytics/docs/reports/`, but the JSON goes to portfolio-site.

---

Reports should have a companion JSON file with this structure:

```json
{
  "meta": { "city", "cityCode", "period", "jobFamily", "totalJobs", "uniqueEmployers", "summary" },
  "keyFindings": { "narrative": [], "bullets": [{ "title": "...", "text": "..." }], "dataNote": "..." },
  "takeaways": {
    "jobSeekers": [{ "title": "...", "text": "..." }],
    "hiringManagers": [{ "title": "...", "text": "..." }]
  },
  "industryDistribution": { "coverage": "X% of roles with industry data", "data": [{ "label": "...", "value": N }], "interpretation": "..." },
  "companyMaturity": { "coverage": "X% of roles with company age data", "data": [], "interpretation": "..." },
  "ownershipType": { "coverage": "X% of roles with ownership data", "data": [], "interpretation": "..." },
  "employerSize": { "coverage": "X% of roles with company size data", "data": [], "interpretation": "..." },
  "topEmployers": { "data": [{ "label": "...", "value": N }], "interpretation": "..." },
  "roleSpecialization": { "data": [], "interpretation": "..." },
  "seniorityDistribution": { "data": [], "seniorToJuniorRatio": N, "entryAccessibilityRate": N, "interpretation": "..." },
  "icVsManagement": { "data": [], "interpretation": "..." },
  "workingArrangement": {
    "coverage": "X% of roles with known working arrangement",
    "data": [{ "label": "Remote", "value": 44 }],
    "interpretation": "..."
  },
  "compensation": {
    "coverage": "X% of roles with disclosed salary ranges",
    "overall": { "percentile25": N, "median": N, "percentile75": N, "iqr": N } | null,
    "bySeniority": [{ "label": "Senior", "p25": N, "median": N, "p75": N, "sample": N }],
    "byRole": [{ "label": "ML Engineer", "p25": N, "median": N, "p75": N, "sample": N }],
    "insights": [{ "label": "...", "text": "..." }]
  },
  "skillsDemand": { "coverage": "X% of roles with skills data", "data": [], "skillPairs": [{ "skills": "Python + SQL", "value": N }], "interpretation": "..." },
  "marketMetrics": {
    "marketStructure": [{ "label": "...", "value": "...", "benchmark": "...", "description": "..." }],
    "accessibility": [{ "label": "...", "value": "...", "benchmark": "...", "description": "...", "highlight": true }],
    "flexibility": [{ "label": "...", "value": "...", "benchmark": "...", "description": "..." }]
  },
  "marketContext": [{ "title": "...", "description": "..." }],
  "methodology": { "description": "...", "dataCollection": [], "classification": [], "limitations": [], "dataQuality": [{ "label": "...", "value": "X%", "description": "..." }] },
  "about": { "author": "...", "bio": "...", "linkedin": "rjacobsuk", "website": "richjacobs.me", "contact": "..." }
}
```

**Key format rules:**
- All `coverage` fields must be descriptive strings (e.g., "76% of roles with industry data"), not bare numbers
- All chart data arrays use `{ "label": "...", "value": N }` format where value is a rounded integer percentage
- `keyFindings.bullets` use `{ "title": "...", "text": "..." }` format (NOT plain strings)
- `takeaways` items use `{ "title": "...", "text": "..." }` format
- `marketContext` items use `{ "title": "...", "description": "..." }` format
- `marketMetrics` items use `{ "label", "value", "benchmark", "description" }` format
- `dataQuality` lives under `methodology` and displays in Methodology section
- `seniorToJuniorRatio` and `entryAccessibilityRate` are numbers (not strings)
- `compensation.overall` is null for non-US markets (London, Singapore)
- `about.linkedin` and `about.website` should be short handles (e.g., "rjacobsuk", "richjacobs.me"), NOT full URLs

### Required Sections (in order)

1. Header (title, period)
2. Key Findings (narrative paragraphs + bullets + data note)
3. Key Takeaways: Job Seekers
4. Key Takeaways: Hiring Managers
5. Industry Distribution (horizontal bar)
6. Company Maturity (donut with narrative)
7. Ownership Type (donut with narrative)
8. Employer Size (donut with narrative)
9. Top Employers (horizontal bar)
10. Role Specialization (horizontal bar)
11. Seniority Distribution (horizontal bar + ratio metrics)
12. IC vs Management (donut with narrative)
13. Working Arrangement (coverage subtitle + donut with narrative)
14. Compensation (stats grid + range bars by seniority and role) - US cities only
15. Skills Demand (horizontal bar)
16. Market Metrics (3-row layout: Market Structure, Accessibility, Flexibility)
17. Market Context (numbered list with title + description)
18. Methodology (description + bulleted lists + Data Coverage grid)
19. About (author bio with email CTA + emoji links)
20. Footer

---

## Adding New Reports to the Portfolio Site

The portfolio site uses a dynamic routing system. To add a new report:

### Step 1: Create the JSON Data File

Create a new JSON file in the portfolio site:

```
portfolio-site/content/reports/{city}-data-{month}-{year}.json
```

**Example:** `nyc-data-december-2025.json`

The file must follow the schema defined in the "Data File Structure (JSON)" section above.

### Step 2: Deploy

That's it. The dynamic route system will:
1. Automatically detect the new JSON file at build time
2. Generate a static page at `/writing/reports/{slug}`
3. Add it to the reports index page at `/writing/reports`

### URL Structure

```
/writing/reports                      # Index page listing all reports
/writing/reports/sf-data-december-2025   # Individual report page
/writing/reports/nyc-data-december-2025  # Another report
```

### File Locations (Portfolio Site)

```
portfolio-site/
├── content/reports/
│   ├── sf-data-december-2025.json    # Report data files
│   ├── nyc-data-december-2025.json
│   └── denver-data-december-2025.json
├── lib/
│   └── reportData.ts                  # Data loader utility
├── app/writing/reports/
│   ├── page.tsx                       # Index page
│   └── [slug]/
│       ├── page.tsx                   # Dynamic route handler
│       └── ReportContent.tsx          # Shared report component
└── components/charts/                 # Reusable chart components
```

### Naming Convention

Use lowercase with hyphens:
- `{city}-data-{month}-{year}.json`
- Examples: `sf-data-december-2025.json`, `nyc-data-january-2026.json`

### Validation

Before deploying, validate your JSON:
1. Ensure all required fields are present (see schema)
2. Check that arrays have data (empty arrays will render empty charts)
3. Verify percentage values are whole numbers (not decimals)
4. Confirm salary values are in dollars (not thousands)

---

## Generating Portfolio Reports via CLI

Use `report_generator.py` to generate portfolio-ready JSON directly:

```bash
# Generate SF report and save to portfolio-site
python pipeline/report_generator.py --city sfo --family data --start 2025-12-01 --end 2025-12-31 --output portfolio --save "C:\Cursor Projects\portfolio-site\content\reports\sf-data-december-2025.json"

# Generate London report
python pipeline/report_generator.py --city lon --family data --start 2025-12-01 --end 2025-12-31 --output portfolio --save "C:\Cursor Projects\portfolio-site\content\reports\london-data-december-2025.json"

# Preview without saving (outputs to console)
python pipeline/report_generator.py --city nyc --family data --start 2025-12-01 --end 2025-12-31 --output portfolio
```

**Output formats:**
- `--output portfolio` - Website-ready JSON with placeholders for narrative content
- `--output json` - Raw data format (for debugging/analysis)
- `--output summary` - Console summary (default)

**After generation:**
1. Open the JSON file
2. Replace all `[PLACEHOLDER]` markers with actual narrative content
3. Verify the report renders correctly on localhost

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
