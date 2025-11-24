# Archive: Historical Documentation

This directory contains previous analyses, implementation reports, design documents, and research that are no longer the active development path, but provide valuable historical context for understanding how the system evolved.

**Last Updated:** November 21, 2025
**Status:** Legacy reference only - for understanding project evolution

---

## Why This Archive Exists

As projects evolve, old documentation becomes outdated. Rather than deleting it, we keep it here to answer questions like:
- "Why did we choose Adzuna over Indeed?"
- "What was tried before the dual-pipeline approach?"
- "What ATS platforms were evaluated?"
- "How did we discover certain limitations?"

## Strategic & Planning Documents

### ATS Analysis Phase (Nov 2025)
- **ATS_ANALYSIS_STRATEGIC_REPORT.md** - Strategic evaluation of ATS platform options
  - Compared 12+ ATS providers (Greenhouse, Workable, Lever, etc.)
  - Analysis of coverage, complexity, scraping feasibility
  - Recommendation to focus on Greenhouse as primary platform

- **INDEPENDENT_SCRAPING_FEASIBILITY.md** - Research on independent job scraping
  - Legal considerations for scraping career pages
  - Technical feasibility analysis
  - Decision to implement Greenhouse + Adzuna approach

- **INDEED_VS_ADZUNA_COMPARISON.md** - Comparison of job data sources
  - Why Adzuna was chosen over Indeed
  - Coverage, API quality, and cost considerations

### Scraping Implementation

- **ATS_SCRAPING_GUIDE.md** - Technical guide to scraping different ATS platforms
  - Browser automation approaches
  - Handling pagination and dynamic content
  - Rate limiting strategies

- **ATS_SCRAPING_TEST_RESULTS.md** - Early test results from ATS scraping experiments
  - Proof-of-concept tests
  - Performance metrics
  - Issues discovered and solutions

### Implementation Notes

- **GREENHOUSE_SCRAPER_STATUS.md** - Initial Greenhouse scraper development notes
  - Development timeline
  - Challenges encountered
  - Solutions implemented

- **HYBRID_SCRAPING_IMPLEMENTATION_COMPLETE.md** - Dual-pipeline implementation notes
  - How Adzuna API and Greenhouse scraping were integrated
  - Deduplication strategy
  - Architecture decisions made

- **IMPLEMENTATION_COMPLETE.md** - Project completion notes from initial rollout
  - What was built
  - What worked well
  - What needed refinement

---

## Archived Code

### directory: `validation_scripts/`

**Old validation approaches** - superseded by `validate_greenhouse_batched.py` in root

- **validate_all_greenhouse_companies.py** - Earlier non-batched validation script
  - All 91 companies tested in single run
  - Lacked resumability (would restart if interrupted)
  - Replaced by batched version for reliability

#### directory: `greenhouse/`
- **phase1_ats_validation.py** - Initial ATS validation prototype
  - Single-company testing approach
  - Early validation methodology
  - Learning phase before scaling

- **test_greenhouse_validation.py** - Original Greenhouse scraper test
  - Manual testing of 1-2 companies
  - Proof-of-concept validation

---

## How to Use This Archive

### As a Developer
If you're wondering "why did we do X?", check here for the analysis that led to that decision.

### As a Historian
If you're studying the project evolution, this archive shows:
1. What was tried (ATS comparison, different scraping approaches)
2. What worked (dual pipeline with Adzuna + Greenhouse)
3. What changed (batched validation for reliability)
4. Why it changed (lessons learned from early attempts)

### When Adding to the Archive
When decommissioning code or analysis:
1. Move it here instead of deleting it
2. Create a new section above if needed
3. Add a one-line description of what it was and why it's archived
4. Update this README

---

## Timeline of Evolution

**November 2025 - ATS Analysis Phase**
- Evaluated 12+ ATS platforms
- Analyzed feasibility of scraping
- Decided to implement dual-source approach

**November 2025 - Initial Implementation**
- Built Adzuna API scraper
- Built Greenhouse web scraper
- Single validation script for all companies

**November 2025 - Optimization Phase**
- Created batched validation for reliability
- Tested across all 90 companies
- Identified 24 companies with active Greenhouse presence

**November 2025 - Cleanup Phase (Current)**
- Consolidated validation scripts
- Archived old approaches
- Documented evolution

---

## Accessing Current Code

The **active** current code and documentation lives in:
- `../` (parent docs directory) for current specs
- `../../scrapers/` for current scrapers
- `../../validate_greenhouse_batched.py` for current validation

This archive is for reference, not development.
