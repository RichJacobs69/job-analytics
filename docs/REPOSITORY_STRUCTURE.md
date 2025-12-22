# Repository Structure (Updated 2025-12-16)

> **Single Source of Truth for Directory Organization**
>
> This document is the authoritative guide for how files are organized in this repository. For development guidance and project overview, see [`CLAUDE.md`](../CLAUDE.md). For system architecture details, see [`docs/architecture/`](architecture/).

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
pipeline/
├── fetch_jobs.py              # Main orchestrator with INCREMENTAL UPSERTS per company
├── classifier.py              # Claude LLM integration
├── db_connection.py           # Supabase PostgreSQL client (insert_raw_job_upsert)
├── agency_detection.py        # Agency filtering logic
├── unified_job_ingester.py    # Merge & deduplication
├── run_all_cities.py          # Parallel orchestration
├── location_extractor.py      # Location extraction from job postings (pattern-based)
├── job_family_mapper.py       # Deterministic job_subfamily → job_family mapping
└── skill_family_mapper.py     # Skill name → skill_family → skill_domain mapping
```

#### Utilities Subdirectory
Maintenance, diagnostic, and backfill tools:

```
pipeline/utilities/
├── check_pipeline_status.py        # Quick status checks
├── analyze_db_results.py           # Database analysis
├── backfill_missing_enriched.py    # Job recovery
├── backfill_agency_flags.py        # Agency flag updates
├── backfill_out_of_scope.py        # Out of scope flag backfill
├── backfill_skill_families.py      # Skill family backfill
├── backfill_skill_family_rename.py # Skill family rename backfill
├── backfill_source_job_id.py       # Source job ID backfill
├── backfill_working_arrangement.py # Working arrangement backfill
├── migrate_locations.py            # Migrate city_code to locations JSONB (one-time)
├── discover_greenhouse_slugs.py    # Greenhouse company slug discovery
└── validate_greenhouse_slugs.py    # Greenhouse slug validation
```

### 3. **`scrapers/` Directory** (Data Source Integrations)

```
scrapers/
├── adzuna/                    # Adzuna Jobs API client
│   └── fetch_adzuna_jobs.py   # Paginated API fetcher
│
├── greenhouse/                # Greenhouse ATS scraper
│   └── greenhouse_scraper.py  # Browser automation (Playwright)
│
└── lever/                     # Lever ATS scraper
    ├── __init__.py
    ├── lever_fetcher.py           # Main Lever job fetcher
    ├── discover_lever_companies.py # Company discovery utility
    └── validate_lever_sites.py    # Site validation utility
```

### 4. **`config/` Directory** (Configuration Files)

```
config/
├── agency_blacklist.yaml              # Agency names for hard filtering
├── company_ats_mapping.json           # Company → ATS slug mapping (302 companies)
├── greenhouse_checked_companies.json  # Validated Greenhouse companies
├── greenhouse_title_patterns.yaml     # Title patterns for Greenhouse filtering
├── lever_company_mapping.json         # Lever company configurations
├── lever_title_patterns.yaml          # Title patterns for Lever filtering
├── location_mapping.yaml              # Master location config (cities, countries, regions)
├── job_family_mapping.yaml            # job_subfamily → job_family mapping (strict)
├── skill_family_mapping.yaml          # skill → skill_family mapping (849 skills)
├── skill_domain_mapping.yaml          # skill_family → domain mapping (32 families, 8 domains)
└── supported_ats.yaml                 # Supported ATS platforms
```

### 5. **`migrations/` Directory** (Database Migrations)
SQL scripts for database schema changes:

```
migrations/
├── README.md                              # Migration instructions
├── 001_add_raw_jobs_hash.sql              # Add hash column with UNIQUE constraint
├── 002_add_last_seen_timestamp.sql        # Add last_seen for resume capability
├── 003_allow_unk_city_code.sql            # Allow 'unk' city code
├── 004_allow_remote_city_code.sql         # Allow 'remote' city code
├── 005_remove_hash_unique_constraint.sql  # Remove hash uniqueness
├── 006_unique_source_job_id.sql           # Unique constraint on source_job_id
├── 007_allow_unknown_working_arrangement.sql # Allow 'unknown' working arrangement
└── 008_add_locations_jsonb.sql            # Add locations JSONB column with GIN index
```

### 6. **`docs/` Directory** (Documentation)

```
docs/
├── README.md                           # Documentation index
├── REPOSITORY_STRUCTURE.md             # This file
├── architecture/                       # Architecture design docs
│   ├── DUAL_PIPELINE.md               # Adzuna + Greenhouse dual sources
│   ├── INCREMENTAL_UPSERT_DESIGN.md   # Incremental upsert architecture
│   ├── GLOBAL_LOCATION_EXPANSION_EPIC.md # Location system epic (COMPLETE)
│   └── ADDING_NEW_LOCATIONS.md        # Guide for adding new cities/countries/regions
├── costs/                              # Cost tracking and metrics
│   ├── COST_METRICS.md                # Cost analysis & optimization
│   └── claude_api_*.csv               # Anthropic usage exports
├── database/
│   └── SCHEMA_UPDATES.md              # Database schema changelog
├── archive/                            # Historical docs
│   └── prod_run_plan_output/          # Production run guides
├── blacklisting_process.md            # Agency detection methodology
├── CASE_STUDY_MVP_REPORT.md           # Project case study
├── employer_size_canonicalization_epic.md # Future epic planning
├── epic5_analytics_layer_planning.md  # Dashboard delivery plan
├── marketplace_questions.yaml         # Business questions spec
├── product_brief.yaml                 # Product requirements
├── schema_taxonomy.yaml               # Classification taxonomy
└── system_architecture.yaml           # System design spec
```

### 7. **`tests/` Directory** (Test Suite)

```
tests/
├── TESTING_GUIDE.md                    # Consolidated testing guide
├── test_db_upsert.py                   # Database upsert logic
├── test_e2e_greenhouse_filtered.py     # E2E pipeline tests
├── test_end_to_end.py                  # Full pipeline integration
├── test_greenhouse_scraper_filtered.py # Scraper integration tests
├── test_greenhouse_scraper_simple.py   # Basic scraper tests
├── test_greenhouse_title_filter_unit.py # Title filter unit tests
├── test_incremental_pipeline.py        # Incremental upsert tests
├── test_location_extractor.py          # Location extraction tests (50+ cases)
├── test_resume_capability.py           # Resume capability tests
└── test_two_companies.py               # Multi-company scraping
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
from pipeline.job_family_mapper import derive_job_family
from pipeline.skill_family_mapper import get_skill_family
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
   - Data source integrations in `scrapers/`

2. **Easy discoverability:**
   - Users call scripts via wrappers: `python wrappers/fetch_jobs.py`
   - Developers look in `pipeline/` for implementation
   - Utilities grouped logically in `pipeline/utilities/`

3. **Scalability:**
   - Easy to add new utilities without cluttering root
   - Core pipeline stays focused and clean
   - New scrapers go in `scrapers/` with consistent structure

4. **Backward compatibility:**
   - Wrapper scripts maintain existing command-line interface
   - Old scripts can be archived systematically

## File Statistics

| Area | Count | Type |
|------|-------|------|
| Root wrappers | 8 | Python scripts |
| Core pipeline | 9 | Python scripts |
| Utilities | 12 | Python scripts |
| Scrapers | 6 | Python scripts (across 3 ATS integrations) |
| Migrations | 8 | SQL scripts |
| Config files | 10 | YAML/JSON files |
| Test files | 10 | Python scripts |
| **Total active** | **63** | **Scripts + configs** |

## Current Status

### Implemented Features
- **Incremental Upserts:** Per-company database writes (no more 3-hour batch failures)
- **Resume Capability:** `--resume-hours N` skips recently processed companies
- **Hash-based Deduplication:** UPSERT by company+title+city hash
- **Last Seen Tracking:** Distinguishes first discovery from most recent scrape
- **Multi-ATS Support:** Greenhouse, Lever, and Adzuna integrations
- **Deterministic Mapping:** Job family and skill family derived from mappings (not LLM)

### Completed Epics
- **Epic 5: Analytics Query Layer** - Next.js API routes at `richjacobs.me/projects/hiring-market`
- **Epic 6: Dashboard & Visualization** - Interactive dashboard with 5 chart types
- **Global Location Expansion Epic** - JSONB location system supporting 14 cities, 9 countries, 3 regions (completed 2025-12-22)

### Ready to Start
- **Epic 7: Automation & Operational**
  - GitHub Actions for daily pipeline execution
  - Monitoring and alerting for pipeline failures

### Maintaining Cleanliness
- Archive diagnostic scripts after use in `docs/archive/session_YYYY-MM-DD/`
- Keep `pipeline/` and root directory clean
- Document major changes in session summary files

---

**Last Updated:** 2025-12-22
**Changes:** Updated after Global Location Expansion Epic completion - added location_extractor.py, location_mapping.yaml, migrate_locations.py, test_location_extractor.py, migration 008, and architecture docs. Removed deprecated greenhouse_location_patterns.yaml and lever_location_patterns.yaml. Ruthlessly cleaned 36 debug files from repository.
**Status:** Clean structure, 100% compliant with documented organization
