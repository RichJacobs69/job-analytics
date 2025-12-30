---
name: gha-analyzer
description: Analyze GitHub Actions workflow runs for the job-analytics scraping pipeline. Use when asked to analyze GHA logs, debug workflow failures, optimize batch timing, investigate classifier or deduplication issues, or review pipeline performance across Greenhouse, Lever, and Adzuna sources.
---

# GitHub Actions Pipeline Analyzer

Analyze GitHub Actions workflow runs for debugging, optimization, and issue detection in the job-analytics scraping pipeline.

## When to Use This Skill

Trigger when user asks to:
- Analyze GitHub Actions logs or workflow runs
- Debug workflow failures or errors
- Optimize batch timing or parallelization
- Investigate classifier issues (job_family, skills extraction)
- Review deduplication behavior
- Check pipeline health across sources (Greenhouse, Lever, Adzuna)
- Find rate limiting or API issues
- Review pipeline data quality
- Analyze costs and performance trends

## Repository Context

The job-analytics repository has three main scraping workflows:

| Workflow | Schedule | Description |
|----------|----------|-------------|
| `scrape-greenhouse.yml` | Mon-Thu 7AM UTC | Batched (4 batches, ~91 companies, 120min timeout) |
| `scrape-lever.yml` | Every 48h, 6AM UTC | All 61 companies (20min timeout) |
| `scrape-adzuna.yml` | Every 48h, 6:30AM UTC | Matrix strategy for 5 cities (60min timeout) |

## Analysis Workflow

### Step 1: Fetch Recent Runs

```bash
# List recent workflow runs (all workflows)
gh run list --repo richjacobs/job-analytics --limit 20

# List runs for specific workflow
gh run list --repo richjacobs/job-analytics --workflow scrape-greenhouse.yml --limit 10
gh run list --repo richjacobs/job-analytics --workflow scrape-lever.yml --limit 10
gh run list --repo richjacobs/job-analytics --workflow scrape-adzuna.yml --limit 10

# Check for failed runs
gh run list --repo richjacobs/job-analytics --status failure --limit 10
```

### Step 2: Get Detailed Run Information

```bash
# View specific run details (replace RUN_ID)
gh run view RUN_ID --repo richjacobs/job-analytics

# Download logs for a specific run
gh run view RUN_ID --repo richjacobs/job-analytics --log

# Get just failed job logs
gh run view RUN_ID --repo richjacobs/job-analytics --log-failed
```

### Step 3: Analyze for Specific Issues

## Issue Detection Patterns

### 1. Classifier Issues

Look for these patterns in logs:

```
[ERROR] Failed to parse.*response as JSON
[WARNING] Unknown job_subfamily
job_family auto-assigned:
Skills enriched: \d+/\d+ mapped
```

**Common Classifier Problems:**
- `Unknown job_subfamily` - LLM returned invalid subfamily code
- JSON parse errors - LLM response malformed
- Skills mapping failures - Unknown skills not in ontology
- `out_of_scope` misclassification - Title filtering missed edge case

### 2. Deduplication Issues

Look for these patterns:

```
was_duplicate.*True
action.*updated|inserted|skipped
duplicate key.*unique constraint
23505.*error
```

**Dedupe Metrics to Extract:**
- Count of `was_duplicate: True` vs `False`
- Ratio of `inserted` vs `updated` vs `skipped`
- Cross-source duplicates (same job from Adzuna + Greenhouse)

### 3. Timing and Performance

Look for these patterns:

```
GREENHOUSE BATCH \d+
Companies: \d+ of \d+
Range:.*->
Indices: \[\d+:\d+\]
Cost: \$[\d.]+
Latency: \d+ms
```

**Timing Metrics to Extract:**
- Total run duration per workflow
- Per-company scraping time (Greenhouse: ~47 sec each)
- LLM classification latency (typical: 200-500ms per job)
- Rate limit delays

### 4. Rate Limiting and API Errors

Look for these patterns:

```
rate limit|429|too many requests
RetryError|retry|backoff
APIConnectionError|timeout
quota exceeded|billing
```

**API Issues:**
- Gemini/Claude rate limits
- Supabase connection errors
- Adzuna API quota exhaustion
- Greenhouse/Lever scraping blocks

### 5. Batch Parallelization (Adzuna)

Adzuna uses matrix strategy for cities. Analyze:

```bash
# Check matrix job timing
gh run view RUN_ID --repo richjacobs/job-analytics --json jobs --jq '.jobs[] | {name, conclusion, startedAt, completedAt}'
```

**Parallelization Metrics:**
- Are all 5 city jobs running in parallel?
- Which cities are slowest?
- Are there sequential bottlenecks?

## Extended Pipeline Observations

### 6. Data Quality Checks

Look for these patterns indicating data quality issues:

```
# Missing required fields
Missing city_code
Missing employer_name
Missing title_display

# Working arrangement issues
working_arrangement.*unknown
working_arrangement.*null

# Salary extraction
salary_min.*null.*salary_max.*null
currency.*null

# Location parsing
locations.*\[\]
city_code.*unk
```

**Data Quality Metrics:**
- Null rate for key fields (seniority, working_arrangement, salary)
- `unk` city_code frequency (location extraction failures)
- Empty skills array rate
- Working arrangement distribution (should see mix of onsite/hybrid/remote)

### 7. Company-Specific Issues

Look for patterns by company:

```
# Company timeout/failure patterns
Scraping.*failed
No jobs found for
timeout.*exceeded

# Companies with unusual counts
Jobs found: 0
Jobs found: [0-2]
Jobs found: [100+]
```

**Company Health Checks:**
- Companies consistently returning 0 jobs (careers page changed?)
- Companies timing out (too many jobs or slow page?)
- Companies with suspiciously high job counts (might be duplicating)
- New companies not appearing in logs (config not updated?)

### 8. Cross-Source Analysis

When analyzing across sources:

```
# Source identification
data_source.*adzuna|greenhouse|lever
description_source.*adzuna|ats_scrape

# Merge indicators
deduplicated.*True
merged_from_source
original_url_secondary
```

**Cross-Source Metrics:**
- Adzuna vs Greenhouse overlap rate (same job appearing in both)
- Text source quality (Adzuna truncated vs Greenhouse full)
- Classification accuracy by source (Greenhouse should be higher)

### 9. Agency Detection Effectiveness

Look for agency-related patterns:

```
# Agency blocklist hits
agency.*blocked|filtered
agency_blacklist
Blocked agency

# Agency classification
is_agency.*True
agency_confidence.*high|medium
```

**Agency Metrics:**
- Jobs blocked by agency blocklist
- Jobs classified as agency that slipped through
- False positive rate (legitimate companies flagged)
- New agencies appearing (add to blocklist)

### 10. Skills Extraction Quality

Look for skills-related patterns:

```
Skills enriched: \d+/\d+
family_code.*null
skills.*\[\]
MAXIMUM 20 skills
```

**Skills Metrics:**
- Average skills extracted per job
- Unmapped skills rate (family_code: null)
- Most common unmapped skills (candidates for ontology)
- Skills distribution by job family (data jobs should have SQL/Python)

### 11. LLM Cost Tracking

Look for cost patterns:

```
Cost: \$[\d.]+
total_cost.*[\d.]+
Token usage: \d+ input, \d+ output
Latency: \d+ms
```

**Cost Metrics:**
- Total cost per workflow run
- Average cost per job (~$0.00388 for Claude Haiku)
- Cost trends over time (increasing = more jobs or longer descriptions)
- Provider comparison (Gemini 88% cheaper than Claude)

### 12. Job Flow Analysis

Track job progression through pipeline:

```
# Raw job insertion
insert_raw_job_upsert
action.*inserted

# Classification
classify_job
job_family.*product|data|delivery|out_of_scope

# Enriched job creation
insert_enriched_job
job_hash
```

**Flow Metrics:**
- Raw jobs -> Classified jobs ratio (should be ~1:1)
- Out of scope rejection rate (with title filtering, should be low)
- Classification error rate
- Enriched job upsert vs insert rate

### 13. Workflow Timing Patterns

Analyze timing trends:

```bash
# Get timing for last 10 Greenhouse runs
gh run list --repo richjacobs/job-analytics --workflow scrape-greenhouse.yml --json databaseId,createdAt,updatedAt,conclusion --limit 10

# Calculate duration in minutes
# (updatedAt - createdAt) / 60000
```

**Timing Benchmarks:**
| Workflow | Expected Duration | Alert Threshold |
|----------|------------------|-----------------|
| Greenhouse Batch | 45-90 min | >100 min |
| Lever | 10-20 min | >25 min |
| Adzuna (per city) | 5-15 min | >30 min |

### 14. Workflow Summary Artifacts

Check step summary output:

```bash
# View run summary
gh run view RUN_ID --repo richjacobs/job-analytics

# Look for summary stats in logs
grep -E "Companies:|Batch:|Timestamp:|Jobs:" logs.txt
```

**Summary Verification:**
- Expected batch count matches actual
- Company range looks correct
- No gaps in batch coverage (Batch 1, 2, 3, 4)

## Diagnostic Commands

### Quick Health Check

```bash
# Last 5 runs status summary
gh run list --repo richjacobs/job-analytics --limit 5 --json status,conclusion,name,createdAt

# Check if any workflow is currently running
gh run list --repo richjacobs/job-analytics --status in_progress
```

### Deep Dive on Failures

```bash
# Get full logs for failed run
gh run view RUN_ID --repo richjacobs/job-analytics --log-failed 2>&1 | head -500

# Extract error lines
gh run view RUN_ID --repo richjacobs/job-analytics --log 2>&1 | grep -i "error\|failed\|exception"
```

### Performance Analysis

```bash
# Get timing data for recent runs
gh run list --repo richjacobs/job-analytics --workflow scrape-greenhouse.yml --json databaseId,createdAt,updatedAt,conclusion --limit 10
```

### Database State Check (via Supabase)

After workflow runs, verify database state:

```python
# Check recent job counts
python wrappers/check_pipeline_status.py

# Verify no orphaned raw jobs
SELECT COUNT(*) FROM raw_jobs WHERE id NOT IN (SELECT raw_job_id FROM enriched_jobs);
```

## Output Format

When analyzing, produce a structured report:

```markdown
## GHA Pipeline Analysis Report

**Run Analyzed:** [RUN_ID] - [Workflow Name]
**Date:** [Date]
**Status:** [success/failure/cancelled]
**Duration:** [X minutes]

### Summary Stats
- Jobs Processed: X
- New Jobs Inserted: Y
- Duplicates Updated: Z
- Out of Scope: W

### Issues Found

1. **[Issue Category]** - [Severity: Critical/Warning/Info]
   - Description: [What happened]
   - Log excerpt: [Relevant log lines]
   - Suggested fix: [Action to take]

### Data Quality

| Metric | Value | Expected | Status |
|--------|-------|----------|--------|
| Null seniority rate | X% | <20% | OK/WARN |
| Unknown working_arrangement | X% | <10% | OK/WARN |
| Unmapped skills | X% | <15% | OK/WARN |
| Agency detection | X blocked | N/A | INFO |

### Performance

| Metric | Value | Benchmark |
|--------|-------|-----------|
| Total Duration | X min | 45-90 min |
| Avg per Company | X sec | ~47 sec |
| LLM Latency | X ms | <500 ms |
| Total Cost | $X.XX | ~$0.50/batch |

### Recommendations

1. [Optimization suggestion]
2. [Config change needed]
3. [Monitoring alert to add]
```

## Common Fixes

| Issue | Fix |
|-------|-----|
| Classifier JSON parse error | Check if job description truncated; increase token limit |
| Unknown job_subfamily | Add to `config/job_family_mapping.yaml` |
| High duplicate rate | Normal for incremental runs; check if >90% suggests stale data |
| Rate limit errors | Reduce batch size or add delays |
| Timeout on Greenhouse | Increase `timeout-minutes` or reduce batch size |
| Adzuna city fails | Check API quota at adzuna.com/developers |
| Company returns 0 jobs | Verify careers page URL in company_ats_mapping.json |
| High unmapped skills | Add common skills to `config/skill_family_mapping.yaml` |
| Agency slipping through | Add to `config/agency_blacklist.yaml` |
| Location parse failures | Check `config/location_mapping.yaml` patterns |

## Files to Reference

- `.github/workflows/scrape-greenhouse.yml` - Greenhouse workflow config
- `.github/workflows/scrape-lever.yml` - Lever workflow config
- `.github/workflows/scrape-adzuna.yml` - Adzuna workflow config
- `pipeline/classifier.py` - LLM classification logic
- `pipeline/db_connection.py` - Deduplication logic (generate_job_hash, upsert)
- `pipeline/agency_detection.py` - Agency pattern matching
- `config/greenhouse/company_ats_mapping.json` - Greenhouse company list (302)
- `config/lever/company_mapping.json` - Lever company list (61)
- `config/job_family_mapping.yaml` - Subfamily -> family mapping
- `config/skill_family_mapping.yaml` - Skill family assignments
- `config/agency_blacklist.yaml` - Blocked recruitment agencies
- `config/location_mapping.yaml` - Location pattern matching
- `docs/epic7_automation_planning.md` - Automation architecture
