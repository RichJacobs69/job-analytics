# Repository Structure (Updated 2025-12-03)

> **Single Source of Truth for Directory Organization**
>
> This document is the authoritative guide for how files are organized in this repository. For development guidance and project overview, see [`CLAUDE.md`](CLAUDE.md). For system architecture details, see [`docs/architecture/`](docs/architecture/).

## Organization Overview

The repository is organized into clear functional areas:

### 1. **`wrappers/` Directory** (User-Facing Entry Points)
Thin wrapper scripts that serve as the main entry points for users. Each wrapper imports from `pipeline/` to avoid code duplication.

```
wrappers/
├── __init__.py                          # Package marker with documentation
├── fetch_jobs.py                        # Wrapper → pipeline/fetch_jobs.py (INCREMENTAL UPSERTS)
├── run_all_cities.py                    # Wrapper → pipeline/run_all_cities.py
├── check_pipeline_status.py             # Wrapper → pipeline/utilities/check_pipeline_status.py
├── analyze_db_results.py                # Wrapper → pipeline/utilities/analyze_db_results.py
├── backfill_missing_enriched.py         # Wrapper → pipeline/utilities/backfill_missing_enriched.py
├── backfill_agency_flags.py             # Wrapper → pipeline/utilities/backfill_agency_flags.py
└── migrate_raw_jobs_schema.py           # Wrapper → pipeline/utilities/migrate_raw_jobs_schema.py
```

**Why separate wrappers directory?**
- Clean separation: wrappers are isolated from production code
- Clear intent: directory name signals "these are entry points"
- Easy to manage: can move to `bin/` for system-wide installation if needed
- Users can call: `python wrappers/fetch_jobs.py` or add to PATH

### 2. **`pipeline/` Directory** (Core Production Code)

#### Core Pipeline Scripts
These are the production components of the job analytics pipeline:

```
pipeline/fetch_jobs.py              # Main orchestrator with INCREMENTAL UPSERTS per company
pipeline/classifier.py              # Claude LLM integration
pipeline/db_connection.py           # Supabase PostgreSQL client (insert_raw_job_upsert)
pipeline/agency_detection.py        # Agency filtering logic
pipeline/unified_job_ingester.py    # Merge & deduplication
pipeline/run_all_cities.py          # Parallel orchestration
pipeline/README.md                  # Pipeline documentation
```

#### Utilities Subdirectory
Maintenance and diagnostic tools:

```
pipeline/utilities/check_pipeline_status.py      # Quick status checks
pipeline/utilities/analyze_db_results.py         # Database analysis
pipeline/utilities/backfill_missing_enriched.py  # Job recovery
pipeline/utilities/backfill_agency_flags.py      # Agency flag updates
pipeline/utilities/migrate_raw_jobs_schema.py    # Schema migration helper
pipeline/utilities/derive_missing_titles.py      # Title derivation utility
pipeline/utilities/scrape_adzuna_titles.py       # Adzuna title scraper
```

### 3. **`migrations/` Directory** (Database Migrations)
SQL and Python scripts for database schema changes:

```
migrations/
├── README.md                           # Migration instructions
├── 000_backfill_raw_jobs_metadata.py   # Backfill NULL company/title
├── 001_add_raw_jobs_hash.sql           # Add hash column with UNIQUE constraint
├── 001a_deduplicate_raw_jobs.py        # Remove duplicate records
├── 002_add_last_seen_timestamp.sql     # Add last_seen for resume capability
├── 003_allow_unk_city_code.sql         # Allow 'unk' city code for Greenhouse
└── verify_001_hash_migration.py        # Migration verification
```

### 4. **Other Directories**

```
scrapers/              # Web scrapers (Adzuna, Greenhouse)
  ├── adzuna/          # Adzuna API client
  └── greenhouse/      # Greenhouse browser automation scraper

config/                # Configuration files
  ├── agency_blacklist.yaml
  ├── company_ats_mapping.json
  ├── greenhouse_title_patterns.yaml
  └── greenhouse_location_patterns.yaml

docs/                  # Documentation
  ├── README.md        # Documentation index
  ├── architecture/    # Architecture design docs
  │   ├── DUAL_PIPELINE.md
  │   └── INCREMENTAL_UPSERT_DESIGN.md  # IMPLEMENTED 2025-12-03
  ├── costs/           # Cost tracking and metrics (NEW 2025-12-04)
  │   ├── COST_METRICS.md              # Cost analysis & optimization
  │   └── claude_api_*.csv             # Anthropic usage exports
  ├── database/        # Database documentation
  │   └── SCHEMA_UPDATES.md
  ├── testing/         # Test documentation
  └── archive/         # Historical docs and session notes

tests/                 # Test suite
  ├── test_*.py        # Test files
  └── TESTING_GUIDE.md # Consolidated testing guide
output/                # Generated outputs (gitignored)
```

## Usage Examples

### Core Pipeline (Incremental Upserts)

```bash
# Greenhouse only with incremental per-company writes (RECOMMENDED)
python wrappers/fetch_jobs.py --sources greenhouse

# With resume capability (skip companies done in last 24h)
python wrappers/fetch_jobs.py --sources greenhouse --resume-hours 24

# Specific companies
python wrappers/fetch_jobs.py --sources greenhouse --companies stripe,figma

# Dual pipeline (Adzuna batch + Greenhouse incremental)
python wrappers/fetch_jobs.py lon 100 --sources adzuna,greenhouse

# Adzuna only (batch mode)
python wrappers/fetch_jobs.py lon 100 --sources adzuna
```

### Utilities

```bash
# Check pipeline status
python wrappers/check_pipeline_status.py

# Analyze database
python wrappers/analyze_db_results.py

# Backfill missing jobs (dry run)
python wrappers/backfill_missing_enriched.py --dry-run

# Backfill missing jobs (last 24 hours, limit 50)
python wrappers/backfill_missing_enriched.py --hours 24 --limit 50

# Update agency flags
python wrappers/backfill_agency_flags.py --dry-run
```

## Import Structure

**From pipeline modules:** (used within the pipeline)
```python
from pipeline.classifier import classify_job_with_claude
from pipeline.db_connection import supabase, insert_enriched_job, insert_raw_job_upsert
from pipeline.unified_job_ingester import UnifiedJob, UnifiedJobIngester
```

**From utilities:** (allow calling from project root)
```python
import sys
sys.path.insert(0, '.')
from pipeline.utilities.check_pipeline_status import main
main()
```

## Key Benefits of This Organization

1. **Clear separation of concerns:**
   - Core production code in `pipeline/`
   - Maintenance utilities in `pipeline/utilities/`
   - User-facing wrappers in `wrappers/`
   - Database migrations in `migrations/`

2. **Easy discoverability:**
   - Users call scripts via wrappers: `python wrappers/fetch_jobs.py`
   - Developers look in `pipeline/` for implementation
   - Utilities grouped logically in `pipeline/utilities/`

3. **Scalability:**
   - Easy to add new utilities without cluttering root
   - Core pipeline stays focused and clean
   - Future additions have clear home

4. **Backward compatibility:**
   - Wrapper scripts maintain existing command-line interface
   - Old scripts can be archived systematically

## Changes from Previous Structure

### Archived (Session 2025-12-03)
Implementation tracking docs moved to `docs/archive/session_2025-12-03_incremental/`:
- `PHASE_1_IMPLEMENTATION_STATUS.md` - Phase 1 tracking
- `LAST_SEEN_IMPLEMENTATION.md` - Last seen timestamp feature

Production run logs moved to `docs/archive/prod_run_plan_output/`:
- Production run logs and metrics
- Parallel execution guide

### Deleted (2025-12-07 Cleanup)
- Ad-hoc test files: `.check_wheely.py`, `test_wheely_scrape.py`, `test_custom_domain_companies.py`, `temp_query.py`
- Output files: `validate_greenhouse_results.json`, `config_cleanup_results.md`
- Duplicate documentation: `docs/epic_5_analytics_plan.md` (kept `epic5_analytics_layer_planning.md`)
- Redundant READMEs: `pipeline/README.md`, `scrapers/greenhouse/README.md`, `tests/README_TITLE_FILTER_TESTS.md`, `tests/QUICK_REFERENCE.md`
- Git artifact files: Various malformed git command outputs in root directory

### Deleted (Previous Sessions)
- `core/` - Empty directory removed
- `nul` - Windows artifact removed
- `scripts/` - Directory removed after moving contents

### Consolidated
- Database migrations now only in root `migrations/` (old `docs/database/migrations/` archived)

## File Statistics

| Area | Count | Type |
|------|-------|------|
| Root wrappers | 8 | Python scripts |
| Core pipeline | 6 | Python scripts |
| Utilities | 11 | Python scripts |
| Migrations | 6 | SQL scripts |
| Test files | 10 | Python scripts |
| **Total active** | **41** | **Scripts** |
| Documentation | 3 | README files (docs/, tests/, migrations/) |

## Current Status

### Implemented Features
- **Incremental Upserts:** Per-company database writes (no more 3-hour batch failures)
- **Resume Capability:** `--resume-hours N` skips recently processed companies
- **Hash-based Deduplication:** UPSERT by company+title+city hash
- **Last Seen Tracking:** Distinguishes first discovery from most recent scrape

### Ready to Start
- **Epic 5: Analytics Query Layer**
  - Build `analytics.py` with query functions
  - Implement common aggregation patterns
  - Answer marketplace questions programmatically

### Maintaining Cleanliness
- Archive diagnostic scripts after use in `docs/archive/session_YYYY-MM-DD/`
- Keep `pipeline/` and root directory clean
- Document major changes in session summary files

---

**Last Updated:** 2025-12-07
**Changes:** Major cleanup - consolidated READMEs (6→3), moved utility scripts, removed ad-hoc test files
**Previous (2025-12-04):** Added `docs/costs/` directory with cost metrics, API usage tracking
**Previous (2025-12-03):** Implemented incremental upsert architecture, cleaned up orphaned files
**Status:** Clean structure, 100% compliant with documented organization
