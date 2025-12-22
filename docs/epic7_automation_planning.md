# Epic 7: Automation & Operational Excellence

**Created:** 2025-12-22
**Status:** IN PROGRESS (Phase 1 Testing)
**Priority:** High
**Estimated Sessions:** 2-4

---

## Executive Summary

Automate the job analytics pipeline using GitHub Actions to maintain fresh dashboard data without manual intervention.

**Approach:**
- Lever + Adzuna: Every 48 hours (fast HTTP APIs)
- Greenhouse: Daily batches Mon-Thu (360 companies split into 4 batches of ~91)

**Budget:** ~400 min/month of 2,000 min available (80% buffer for retries/debugging).

### Current Status (2025-12-22)

**Phase 1 IN PROGRESS:**
- [DONE] All 3 workflows created
- [DONE] Secrets configured (ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY, ADZUNA_APP_ID, ADZUNA_API_KEY)
- [DONE] Import path fixes for GitHub Actions compatibility
- [DONE] Location filter config files created (were missing!)
- [DONE] False positive patterns fixed ("global" removed from location filters)
- [DONE] Lever workflow tested in GitHub Actions
- [TODO] Adzuna workflow tested in GitHub Actions
- [TODO] Greenhouse workflow tested in GitHub Actions

**Issues Discovered & Fixed:**
1. `lever_location_patterns.yaml` and `greenhouse_location_patterns.yaml` didn't exist - location filtering was silently disabled
2. "global" pattern matched "global company" in descriptions - caused false positives (India, Brazil jobs slipping through)
3. Import paths needed `pipeline.` prefix for GitHub Actions environment
4. Bay Area cities (Foster City, San Mateo) and NYC Metro (Jersey City, Hoboken) missing from location mapping

---

## Table of Contents

1. [Constraints & Requirements](#constraints--requirements)
2. [Scraper Characteristics](#scraper-characteristics)
3. [GitHub Actions Limits](#github-actions-limits)
4. [Proposed Architecture](#proposed-architecture)
5. [Workflow Designs](#workflow-designs)
6. [Implementation Phases](#implementation-phases)
7. [Secrets & Configuration](#secrets--configuration)
8. [Monitoring & Alerting](#monitoring--alerting)
9. [Cost Analysis](#cost-analysis)
10. [Risk Mitigation](#risk-mitigation)

---

## Constraints & Requirements

### Must Have
- [DONE] Daily data freshness for dashboard
- [DONE] Stay within GitHub Actions free tier (2,000 min/month)
- [DONE] All 3 scrapers operational (Greenhouse, Lever, Adzuna)
- [TODO] Error handling with notifications
- [DONE] No manual intervention required for normal operations

### Nice to Have
- [DONE] Parallelization for faster runs (Adzuna cities run in parallel matrix)
- [TODO] Retry logic for transient failures
- [DONE] Dashboard freshness indicator updates automatically
- [TODO] Cost tracking and optimization alerts

### Constraints
- GitHub Actions free tier: 2,000 minutes/month (Linux runners)
- Greenhouse full scrape: 4+ hours (240+ minutes)
- 302 Greenhouse companies configured
- Browser automation requires Playwright setup in CI
- Secrets needed: ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY, ADZUNA_APP_ID, ADZUNA_API_KEY

---

## Scraper Characteristics

### 1. Lever Scraper
| Metric | Value |
|--------|-------|
| **Type** | HTTP API (no browser) |
| **Companies** | 61 validated (`lever_company_mapping.json`) |
| **Jobs Available** | 4,137 across all companies |
| **Rate Limit** | 1 request/second (conservative) |
| **Typical Runtime** | 5-10 minutes (61 companies + pagination) |
| **Monthly Minutes** | ~5-10 min/day = 150-300 min/month |
| **Bottleneck** | Rate limiting (1 req/sec) |

**Command:**
```bash
python wrappers/fetch_jobs.py --sources lever
```

**Note:** Lever is fast HTTP API (no browser), but 61 companies with 4,137 jobs means ~5-10 minutes with rate limiting. Still much faster than Greenhouse.

### 2. Adzuna Scraper
| Metric | Value |
|--------|-------|
| **Type** | REST API with rate limiting |
| **Cities** | 5 (London, NYC, Denver, SF, Singapore) |
| **Typical Runtime** | 20-60 seconds per city |
| **Monthly Minutes** | ~5-10 min/day = 150-300 min/month |
| **Bottleneck** | Rate limit (24 calls/min) |

**Commands:**
```bash
# All cities sequential
python wrappers/fetch_jobs.py lon 100 --sources adzuna
python wrappers/fetch_jobs.py nyc 100 --sources adzuna
python wrappers/fetch_jobs.py den 100 --sources adzuna
python wrappers/fetch_jobs.py sfo 100 --sources adzuna
python wrappers/fetch_jobs.py sgp 100 --sources adzuna

# Or parallel via run_all_cities.py (but only supports 3 cities currently)
python wrappers/run_all_cities.py --max-jobs 100 --sources adzuna
```

### 3. Greenhouse Scraper [PRIMARY CHALLENGE]
| Metric | Value |
|--------|-------|
| **Type** | Browser automation (Playwright) |
| **Companies** | 360 configured (`company_ats_mapping.json`) |
| **Typical Runtime** | 4-5 hours full scrape (240-300 min) |
| **Per-Company Average** | ~40-50 seconds |
| **Monthly Minutes (Full Daily)** | 270 min × 30 = 8,100 min (EXCEEDS LIMIT) |
| **Bottleneck** | Browser startup, page loads, dynamic content |

**Commands:**
```bash
# Full run (NOT recommended for CI)
python wrappers/fetch_jobs.py --sources greenhouse

# With resume (skip companies done in last N hours)
python wrappers/fetch_jobs.py --sources greenhouse --resume-hours 24

# Specific companies only
python wrappers/fetch_jobs.py --sources greenhouse --companies "stripe,figma,anthropic"
```

---

## GitHub Actions Limits

### Free Tier (GitHub Free / Public Repos)
| Resource | Limit |
|----------|-------|
| **Minutes/Month** | 2,000 |
| **Concurrent Jobs** | 20 |
| **Job Timeout** | 6 hours (360 minutes) |
| **Artifact Storage** | 500 MB |
| **Cache Storage** | 10 GB |

### Minute Multipliers
| Runner OS | Multiplier | Effective Minutes |
|-----------|------------|-------------------|
| Linux | 1x | 2,000 |
| Windows | 2x | 1,000 |
| macOS | 10x | 200 |

**Decision:** Use Linux runners exclusively (ubuntu-latest)

### Budget Calculation
```
Available: 2,000 minutes/month
Reserved for overhead (setup, cache restore): ~100 min/month

Usable: 1,900 minutes/month
Daily average: 63 minutes/day
```

---

## Proposed Architecture

### Strategy: Mixed Cadence with Daily Greenhouse Batches

Three independent workflows with different schedules:

```
+----------------------+     +----------------------+     +------------------------+
|  scrape-lever.yml    |     |  scrape-adzuna.yml   |     | scrape-greenhouse.yml  |
+----------------------+     +----------------------+     +------------------------+
|                      |     |                      |     |                        |
| - 61 companies       |     | - 5 cities (matrix)  |     | - 360 companies        |
| - HTTP API           |     | - REST API           |     | - Split into 4 batches |
| - ~10 min            |     | - ~10 min            |     | - 91 companies/batch   |
| - 6:00 AM UTC        |     | - 6:30 AM UTC        |     | - ~5-7 min per batch   |
| - Every 48h          |     | - Every 48h          |     | - Daily (Mon-Thu)      |
+----------------------+     +----------------------+     +------------------------+
          |                            |                            |
          v                            v                            v
     150 min/month                150 min/month                ~100 min/month
```

**Total: ~400 min/month (20% of 2,000 min budget)**

### Greenhouse Batch Logic

Companies are dynamically assigned to batches via alphabetical sorting:

```python
companies = sorted(greenhouse_companies.keys())  # Deterministic order
batch_size = len(companies) // 4 + 1             # 91 companies per batch
batch_num = datetime.now().weekday() % 4         # Mon=0, Tue=1, Wed=2, Thu=3

start = batch_num * batch_size
end = start + batch_size
batch = companies[start:end]
```

| Batch | Day | Companies | Example Range |
|-------|-----|-----------|---------------|
| 1 | Monday | 91 | Able → Dwelly |
| 2 | Tuesday | 91 | Easyship → Marqeta |
| 3 | Wednesday | 91 | MasterClass → Scopely |
| 4 | Thursday | 87 | Scythe Robotics → project44 |

**Benefits:**
- No resume logic complexity
- Predictable - same companies same day each week
- No "thundering herd" first run
- Easy to debug - "Stripe is in Batch 3, runs Wednesday"

### Why Not Daily?

Daily runs would exceed the budget:

| Workflow | Daily Runtime | Monthly (30 runs) |
|----------|---------------|-------------------|
| Lever | 10 min | 300 min |
| Adzuna | 10 min | 300 min |
| Greenhouse Full | 270 min | 8,100 min |
| **TOTAL** | | **8,700 min** (4.35x over limit!) |

### Solution: Mixed Cadence with Daily Greenhouse Batches

Jobs typically stay open 30+ days, so this schedule catches everything with massive budget headroom.

| Workflow | Frequency | Duration | Monthly |
|----------|-----------|----------|---------|
| Lever | Every 48h | 10 min | 150 min |
| Adzuna (5 cities) | Every 48h | 10 min | 150 min |
| Greenhouse (91 companies/batch) | Daily Mon-Thu | 6 min | ~100 min |
| **TOTAL** | | | **~400 min** |

**Only 20% of 2,000 min budget - 1,600 min buffer for retries/debugging.**

**Why this works:**
- Jobs open 30+ days = plenty of time to catch them
- Greenhouse split into 4 deterministic batches via alphabetical sort
- Each company scraped once per week (Mon-Thu cycle)
- No resume logic complexity - simple and predictable
- Easy debugging: "Stripe is in Batch 3, runs Wednesday"

### Data Freshness Guarantees

| Source | Schedule | Max Staleness |
|--------|----------|---------------|
| Lever | Every 48h | ~2 days |
| Adzuna | Every 48h | ~2 days |
| Greenhouse | Daily Mon-Thu (4 batches) | 6 days |

**Greenhouse worst case:** A company in Batch 1 (Monday) is 6 days old by Sunday night, then refreshed Monday morning.

**Acceptable because:** Jobs typically stay open 30+ days, so 6-day-old data still catches jobs with 24+ days remaining.

---

## Workflow Designs

### Workflow 1: Lever Scraper (Every 48h)
**File:** `.github/workflows/scrape-lever.yml`
**Schedule:** Every 48 hours at 6:00 AM UTC
**Duration:** ~10 minutes

```yaml
name: Scrape Lever (Every 48h)

on:
  schedule:
    - cron: '0 6 */2 * *'  # Every other day at 6 AM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  lever:
    runs-on: ubuntu-latest
    timeout-minutes: 20  # 61 companies with rate limiting
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run Lever scraper
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: |
          cd job-analytics
          python wrappers/fetch_jobs.py --sources lever
```

### Workflow 2: Adzuna Scraper (Every 48h)
**File:** `.github/workflows/scrape-adzuna.yml`
**Schedule:** Every 48 hours at 6:30 AM UTC
**Duration:** ~10 minutes (5 cities in parallel via matrix)

```yaml
name: Scrape Adzuna (Every 48h)

on:
  schedule:
    - cron: '30 6 */2 * *'  # Every other day at 6:30 AM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  adzuna:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      matrix:
        city: [lon, nyc, den, sfo, sgp]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run Adzuna scraper for ${{ matrix.city }}
        env:
          ADZUNA_APP_ID: ${{ secrets.ADZUNA_APP_ID }}
          ADZUNA_API_KEY: ${{ secrets.ADZUNA_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: |
          cd job-analytics
          python wrappers/fetch_jobs.py ${{ matrix.city }} 100 --sources adzuna
```

### Workflow 3: Greenhouse Scraper (Daily Batches)
**File:** `.github/workflows/scrape-greenhouse.yml`
**Schedule:** Daily Monday-Thursday at 7:00 AM UTC
**Duration:** ~5-7 minutes (91 companies per batch)

```yaml
name: Scrape Greenhouse (Daily Batch)

on:
  schedule:
    - cron: '0 7 * * 1'  # Monday
    - cron: '0 7 * * 2'  # Tuesday
    - cron: '0 7 * * 3'  # Wednesday
    - cron: '0 7 * * 4'  # Thursday
  workflow_dispatch:
    inputs:
      batch_override:
        description: 'Force specific batch (1-4), or leave empty for auto'
        required: false
        default: ''

jobs:
  greenhouse-batch:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium
          playwright install-deps

      - name: Compute batch and run
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          BATCH_OVERRIDE: ${{ github.event.inputs.batch_override }}
        run: |
          cd job-analytics
          python -c "
          import json
          import subprocess
          import os
          from datetime import datetime

          # Load companies
          with open('config/greenhouse/company_ats_mapping.json') as f:
              data = json.load(f)

          greenhouse = data.get('greenhouse', {})
          companies = sorted(greenhouse.keys())
          batch_size = len(companies) // 4 + 1

          # Allow manual override or compute from day of week
          override = os.environ.get('BATCH_OVERRIDE', '').strip()
          if override:
              batch_num = int(override) - 1  # Convert 1-4 to 0-3
          else:
              batch_num = datetime.now().weekday() % 4

          start = batch_num * batch_size
          end = min(start + batch_size, len(companies))
          batch = companies[start:end]

          # Get slugs
          slugs = [greenhouse[c]['slug'] for c in batch]

          print(f'Running Batch {batch_num + 1}: {len(slugs)} companies')
          print(f'Range: {batch[0]} -> {batch[-1]}')

          # Run scraper
          subprocess.run([
              'python', 'wrappers/fetch_jobs.py',
              '--sources', 'greenhouse',
              '--companies', ','.join(slugs)
          ], check=True)
          "
```

---

## Implementation Phases

### Phase 1: Foundation (Session 1) - COMPLETE
**Goal:** Basic workflow setup and validation

**Tasks:**
- [DONE] Create `.github/workflows/` directory structure
- [DONE] Implement `scrape-lever.yml`
- [DONE] Implement `scrape-adzuna.yml`
- [DONE] Test workflows manually via `workflow_dispatch`
- [DONE] Verify secrets configuration
- [DONE] Validate database writes from CI environment
- [DONE] Fix import paths for CI environment (`pipeline.` prefix)
- [DONE] Create missing location filter configs
- [DONE] Fix false positive patterns in location filters

**Deliverables:**
- [DONE] Working Lever workflow (every 48h)
- [DONE] Working Adzuna workflow (every 48h)
- [DONE] Documentation of secrets setup process
- [DONE] First successful automated runs

**Issues Fixed:**
- Import paths: `from job_family_mapper` -> `from pipeline.job_family_mapper`
- Missing configs: `lever_location_patterns.yaml`, `greenhouse_location_patterns.yaml`
- False positives: Removed "global", "worldwide", "anywhere" from remote patterns
- Location coverage: Added Bay Area cities, NYC Metro cities

### Phase 2: Greenhouse Integration (Session 2) - COMPLETE
**Goal:** Greenhouse automation with batch scheduling

**Tasks:**
- [DONE] Implement `scrape-greenhouse.yml` with 4-batch system
- [DONE] Test Playwright setup in GitHub Actions
- [DONE] Batch logic: Mon=Batch1, Tue=Batch2, Wed=Batch3, Thu=Batch4
- [DONE] Manual override option for batch selection
- [DONE] Location filtering enabled and working

**Deliverables:**
- [DONE] Working Greenhouse workflow (daily Mon-Thu batches)
- [DONE] Deterministic batch assignment via alphabetical sort
- [DONE] ~91 companies per batch, ~6 min runtime each

### Phase 3: Monitoring & Alerting (Session 3) - TODO
**Goal:** Operational visibility and failure handling

**Tasks:**
- [TODO] Add Slack/Discord/Email notifications for failures
- [TODO] Implement workflow status badges in README
- [TODO] Create pipeline health dashboard (optional)
- [TODO] Set up GitHub Actions usage alerts (approaching limits)
- [TODO] Document runbook for common failure scenarios

**Deliverables:**
- Notification integration for failures
- Status badges in documentation
- Operations runbook

### Phase 4: Optimization & Polish (Session 4) - TODO
**Goal:** Cost optimization and reliability improvements

**Tasks:**
- [TODO] Analyze actual minute usage after 1-2 weeks
- [TODO] Tune schedules to optimize budget
- [DONE] Implement caching for pip dependencies (already in workflows)
- [TODO] Add retry logic for transient failures
- [TODO] Consider self-hosted runner for Greenhouse (if budget constrained)

**Deliverables:**
- Optimized workflows based on real data
- Documentation updates
- Epic completion summary

---

## Secrets & Configuration

### Required GitHub Secrets

| Secret Name | Description | Source |
|-------------|-------------|--------|
| `ANTHROPIC_API_KEY` | Claude API for classification | Anthropic Console |
| `SUPABASE_URL` | Database connection URL | Supabase Dashboard |
| `SUPABASE_KEY` | Database API key (anon) | Supabase Dashboard |
| `ADZUNA_APP_ID` | Adzuna API app ID | Adzuna Developer Portal |
| `ADZUNA_API_KEY` | Adzuna API key | Adzuna Developer Portal |

### Setup Instructions

1. Go to Repository Settings > Secrets and variables > Actions
2. Click "New repository secret"
3. Add each secret with exact name matching above
4. Secrets are encrypted and only exposed to workflows

### Environment File Reference

For local development, these same values are in `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
ADZUNA_APP_ID=...
ADZUNA_API_KEY=...
```

---

## Monitoring & Alerting

### GitHub Actions Built-in

- **Workflow Run History:** Actions tab shows all runs with status
- **Email Notifications:** GitHub sends emails on workflow failures (default)
- **Status Badges:** Add to README for quick visibility

### Status Badge Examples

```markdown
![Daily Fast Scrapers](https://github.com/YOUR_ORG/job-analytics/actions/workflows/daily-fast.yml/badge.svg)
![Greenhouse Incremental](https://github.com/YOUR_ORG/job-analytics/actions/workflows/daily-greenhouse-incremental.yml/badge.svg)
![Weekly Full Sweep](https://github.com/YOUR_ORG/job-analytics/actions/workflows/weekly-greenhouse-full.yml/badge.svg)
```

### Optional: Slack Integration

```yaml
- name: Notify Slack on failure
  if: failure()
  uses: slackapi/slack-github-action@v1.24.0
  with:
    payload: |
      {
        "text": "Pipeline failed: ${{ github.workflow }}",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Pipeline Failed*\nWorkflow: ${{ github.workflow }}\nRun: ${{ github.run_id }}"
            }
          }
        ]
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

## Cost Analysis

### GitHub Actions (Free Tier)

| Scenario | Monthly Minutes | Status |
|----------|-----------------|--------|
| Lever (10 min × 15 runs, every 48h) | 150 | [OK] |
| Adzuna (10 min × 15 runs, every 48h) | 150 | [OK] |
| Greenhouse (6 min × 16 runs, Mon-Thu) | ~100 | [OK] |
| **TOTAL** | **~400 min** | [OK] 80% buffer remaining |

**Massive headroom:** Only using 20% of 2,000 min budget.

### Mitigation if Over Budget

1. **Reduce Greenhouse frequency:** Every other day incremental
2. **Shorter resume window:** `--resume-hours 48` instead of 24
3. **Prioritize companies:** Only scrape top 100 companies daily
4. **Self-hosted runner:** Free minutes, but requires hosting

### API Costs (Unchanged from Manual)

| API | Cost | Monthly Estimate |
|-----|------|------------------|
| Anthropic (Classification) | $0.00388/job | ~$6-10 |
| Adzuna | Free tier | $0 |
| Supabase | Free tier | $0 |
| **Total** | | ~$6-10/month |

---

## Risk Mitigation

### Risk 1: Exceeding GitHub Actions Minutes
**Likelihood:** Medium
**Impact:** Workflows stop running mid-month

**Mitigations:**
- Monitor usage weekly via Settings > Billing
- Set up usage alerts at 75% threshold
- Have fallback manual run process documented
- Consider self-hosted runner for Greenhouse

### Risk 2: Playwright Browser Failures
**Likelihood:** Medium (CI environments are tricky)
**Impact:** Greenhouse scraper fails

**Mitigations:**
- Use official Playwright GitHub Action
- Cache browser installation
- Increase timeouts for CI environment
- Implement retry logic

### Risk 3: API Rate Limits
**Likelihood:** Low
**Impact:** Partial data collection

**Mitigations:**
- Adzuna: Already respects 24 calls/min limit
- Anthropic: Batch processing with backoff
- Stagger job start times to avoid burst

### Risk 4: Database Connection Issues
**Likelihood:** Low
**Impact:** Data not persisted

**Mitigations:**
- Supabase has high availability
- Implement connection retry logic
- Log all database operations for debugging

### Risk 5: Secrets Exposure
**Likelihood:** Very Low
**Impact:** Security breach

**Mitigations:**
- GitHub encrypts secrets at rest
- Secrets not logged in workflow output
- Use minimal permissions for API keys
- Rotate keys periodically

---

## Open Questions

1. **Self-hosted runner:** Should we consider a cheap VPS for Greenhouse to save GH Actions minutes?
   - Pro: Unlimited minutes, more control
   - Con: Additional infrastructure to maintain

2. **Company prioritization:** Should we tier companies by hiring activity?
   - Tier 1 (Top 50): Daily
   - Tier 2 (Remaining 252): Weekly rotation
   - Would need analysis of historical data to determine tiers

3. **Failure handling:** What's the SLA for pipeline failures?
   - Auto-retry once? Twice?
   - Alert threshold (fail X times before notifying)?

4. **Dashboard freshness indicator:** Should we update a "last pipeline run" timestamp?
   - Already have `/api/hiring-market/last-updated` endpoint
   - Could be enhanced to show per-source freshness

---

## Success Criteria

Epic 7 is complete when:

- [DONE] All 3 scrapers running automatically without manual intervention
- [IN PROGRESS] Pipeline runs successfully >=95% of the time (monitoring)
- [DONE] Lever/Adzuna data refreshed every 48 hours
- [DONE] Greenhouse data refreshed weekly (all companies covered Mon-Thu)
- [DONE] Staying within 2,000 minutes/month budget (~400 min expected)
- [TODO] Failure notifications working
- [IN PROGRESS] Documentation complete for operations handoff

---

## References

- [GitHub Actions Billing](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions)
- [Playwright GitHub Action](https://github.com/microsoft/playwright-github-action)
- [Scraper Documentation](../CLAUDE.md#scraper-characteristics)
- [Resume Capability](../CLAUDE.md#resume-mode)

---

**Last Updated:** 2025-12-22 22:30 UTC
**Author:** Claude Code
**Status:** Phase 1-2 Complete, Phase 3-4 Pending

