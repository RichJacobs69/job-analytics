# Pipeline Directory

This directory contains the core job analytics pipeline - the production code that processes job postings from multiple sources.

## Structure

```
pipeline/
├── Core Pipeline Scripts (production)
│   ├── fetch_jobs.py              # Main orchestrator: Adzuna + Greenhouse dual pipeline
│   ├── classifier.py              # Claude LLM integration for job classification
│   ├── db_connection.py           # Supabase PostgreSQL client and helpers
│   ├── agency_detection.py        # Hard/soft agency filtering
│   ├── unified_job_ingester.py    # Merge and deduplication logic
│   └── run_all_cities.py          # Parallel execution for 3 cities
│
└── utilities/                      # Maintenance and diagnostic scripts
    ├── check_pipeline_status.py    # Quick status checks
    ├── analyze_db_results.py       # Database analysis and breakdown
    ├── backfill_missing_enriched.py  # Recover jobs missing from enriched_jobs
    └── backfill_agency_flags.py    # Retroactive agency flag updates
```

## Usage

### Core Pipeline

**Fetch jobs (dual pipeline - default):**
```bash
python fetch_jobs.py lon 100 --sources adzuna,greenhouse
```

**Adzuna only:**
```bash
python fetch_jobs.py lon 100 --sources adzuna
```

**Greenhouse only:**
```bash
python fetch_jobs.py --sources greenhouse
```

**Run all cities in parallel:**
```bash
python run_all_cities.py --max-jobs 100
```

### Utilities

All utilities can be called from the project root using wrapper scripts:

```bash
# Check pipeline status
python check_pipeline_status.py

# Analyze database results
python analyze_db_results.py

# Backfill missing enriched jobs
python backfill_missing_enriched.py --dry-run
python backfill_missing_enriched.py --limit 50
python backfill_missing_enriched.py --hours 24

# Backfill agency flags
python backfill_agency_flags.py --dry-run
python backfill_agency_flags.py --force
```

## Module Responsibilities

### `fetch_jobs.py`
- Main entry point for the pipeline
- Coordinates Adzuna API and Greenhouse scraper
- Orchestrates: fetch → merge → classify → store
- Supports flexible source selection (`--sources` flag)

### `classifier.py`
- LLM integration with Claude 3.5 Haiku
- Builds structured classification prompts from taxonomy
- Extracts: function, level, skills, remote status, compensation
- Includes cost tracking via actual Anthropic API token usage

### `db_connection.py`
- Supabase PostgreSQL client initialization
- Helper functions: deduplication hashing, batch inserts
- Insert functions: `insert_raw_job()`, `insert_enriched_job()`
- Connection pooling and error handling

### `agency_detection.py`
- Hard filtering: checks against config/agency_blacklist.yaml (before LLM)
- Soft detection: pattern matching on classification results
- Returns boolean flag indicating if job is from recruitment firm

### `unified_job_ingester.py`
- Merges jobs from Adzuna API and Greenhouse scraper
- Deduplicates by MD5 hash: (company + title + location)
- Prefers Greenhouse descriptions (9,000+ chars vs Adzuna's 100-200)
- Tracks data source for each job

### `run_all_cities.py`
- Orchestration wrapper for parallel execution
- Runs fetch_jobs.py for London, NYC, Denver simultaneously
- Uses Python multiprocessing for concurrency

## Utilities (Maintenance Scripts)

### `check_pipeline_status.py`
Quick status check showing:
- Total jobs ingested vs classified
- Classification rate
- Breakdown by city and source
- Recent activity

### `analyze_db_results.py`
Comprehensive database analysis with:
- Today's run statistics
- Overall cumulative totals
- Breakdown by city and job family
- Data source distribution

### `backfill_missing_enriched.py`
Recovery script for jobs that failed to insert into enriched_jobs:
- Finds raw_jobs missing from enriched_jobs
- Re-classifies through Claude API
- City inference from posting URLs
- Handles edge cases and null values

### `backfill_agency_flags.py`
Retroactive agency flag updates:
- Reprocesses jobs when agency detection rules change
- Batch processing to avoid timeouts
- Dry-run mode to preview changes

## Import Pattern

Utilities use `sys.path.insert(0, '.')` to allow imports from the pipeline package:

```python
import sys
sys.path.insert(0, '.')
from pipeline.db_connection import supabase
from pipeline.classifier import classify_job_with_claude
```

Root directory wrapper scripts re-export functions:

```python
from pipeline.utilities.check_pipeline_status import main
main()
```

This allows users to call utilities from the project root:
```bash
python check_pipeline_status.py
```

While keeping actual implementation in subdirectories for cleaner organization.

## Data Flow

```
PIPELINE A: Adzuna API              PIPELINE B: Greenhouse Scraper
    ↓                                    ↓
fetch_adzuna_jobs.py    ← → greenhouse_scraper.py
    ↓                                    ↓
        unified_job_ingester.py (merge & dedup)
                ↓
        [Hard Filter - Agency Blacklist]
                ↓
        classifier.py (Claude LLM)
                ↓
        [Soft Detection - Agency Pattern Matching]
                ↓
        db_connection.py (Supabase PostgreSQL)
        ├── raw_jobs table (original postings + source)
        └── enriched_jobs table (classified results)
```

## Environment Setup

Create `.env` in project root with:
```
ADZUNA_APP_ID=<your_app_id>
ADZUNA_API_KEY=<your_api_key>
ANTHROPIC_API_KEY=<your_anthropic_key>
SUPABASE_URL=<your_supabase_url>
SUPABASE_KEY=<your_supabase_key>
```

See `.env.example` for template.

## Cost Optimization

- **Title + Location filtering:** 94.7% filter rate (3,913 jobs → 207 kept)
- **Hard agency filtering:** Blocks 10-15% pre-LLM (saves API calls)
- **Deduplication:** Prevents re-classification of duplicate jobs
- **Cheap model:** Claude 3.5 Haiku (~$0.00388/classified job)
- **Actual measured cost:** $0.00388/job for Greenhouse full-text

Monthly budget: $15-20 supports 4,400-5,900 classified jobs.
