# Repository Structure (Updated 2026-02-07)

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
├── classifier.py              # Gemini 2.5 Flash LLM integration (default; Claude fallback)
├── db_connection.py           # Supabase PostgreSQL client (insert_raw_job_upsert)
├── agency_detection.py        # Agency filtering logic
├── unified_job_ingester.py    # Merge & deduplication
├── run_all_cities.py          # Parallel orchestration
├── location_extractor.py      # Location extraction from job postings (pattern-based)
├── job_family_mapper.py       # Deterministic job_subfamily → job_family mapping
├── skill_family_mapper.py     # Skill name → skill_family mapping (exact + normalized fuzzy)
├── report_generator.py        # Flexible report builder (city/family/date filters, portfolio output)
├── employer_stats.py          # Compute median fill times per employer (Epic 8)
├── summary_generator.py       # Backfill utility for summaries (new jobs get inline)
└── url_validator.py           # HTTP 404 detection for dead link filtering (Epic 8)
```

#### Utilities Subdirectory
Maintenance, diagnostic, and backfill tools:

```
pipeline/utilities/
├── check_pipeline_status.py                # Quick status checks
├── analyze_db_results.py                   # Database analysis
├── backfill_missing_enriched.py            # Job recovery
├── backfill_agency_flags.py                # Agency flag updates
├── backfill_locations.py                   # Location data backfill
├── backfill_global_scope.py                # Global remote scope backfill
├── backfill_track_seniority.py             # Track + seniority backfill (IC/Manager + level)
├── backfill_working_arrangement_defaults.py # Working arrangement defaults backfill
├── audit_skills_taxonomy.py                # Skills taxonomy audit (unmapped skills, duplicates, gaps)
├── backfill_skill_families.py              # Skill family backfill (with --dry-run, --stats-only)
├── seed_employer_metadata.py               # Seed employer_metadata from config files
├── enrich_employer_metadata.py             # Enrich employer_metadata (industry, HQ, etc.)
├── discover_ats_companies.py               # Multi-ATS company discovery (Google CSE)
└── validate_ats_slugs.py                   # Unified ATS slug validation
```

Archived utilities (one-time or superseded scripts) live in `pipeline/utilities/archive/` (17 files).
See `pipeline/utilities/archive/DEPRECATION.md` for details.

### 3. **`scrapers/` Directory** (Data Source Integrations)

```
scrapers/
├── adzuna/                           # Adzuna Jobs API client
│   └── fetch_adzuna_jobs.py          # Paginated API fetcher
│
├── greenhouse/                       # Greenhouse ATS scraper
│   └── greenhouse_scraper.py         # Browser automation (Playwright)
│
├── lever/                            # Lever ATS fetcher
│   └── lever_fetcher.py              # Public JSON API client
│
├── ashby/                            # Ashby ATS fetcher
│   └── ashby_fetcher.py              # Public JSON API client (structured compensation)
│
├── workable/                         # Workable ATS fetcher
│   └── workable_fetcher.py           # Public JSON API client (workplace_type, salary)
│
├── smartrecruiters/                   # SmartRecruiters ATS fetcher
│   └── smartrecruiters_fetcher.py    # Public JSON API client (locationType, experienceLevel)
│
└── custom/                           # Custom career site scrapers
    └── google_rss_fetcher.py         # Google RSS job feed fetcher
```

### 4. **`config/` Directory** (Configuration Files)

```
config/
├── greenhouse/                        # Greenhouse-specific configs
│   ├── company_ats_mapping.json       # Company → ATS slug mapping (452 companies, with url_type)
│   ├── checked_companies.json         # Validated Greenhouse companies
│   ├── title_patterns.yaml            # Title patterns for Greenhouse filtering
│   └── location_patterns.yaml         # Location patterns for Greenhouse filtering
├── lever/                             # Lever-specific configs
│   ├── company_mapping.json           # Lever company configurations (182 companies)
│   ├── title_patterns.yaml            # Title patterns for Lever filtering
│   └── location_patterns.yaml         # Location patterns for Lever filtering
├── ashby/                             # Ashby-specific configs
│   ├── company_mapping.json           # Ashby company configurations (169 companies)
│   ├── title_patterns.yaml            # Title patterns for Ashby filtering
│   └── location_patterns.yaml         # Location patterns for Ashby filtering
├── workable/                          # Workable-specific configs
│   ├── company_mapping.json           # Workable company configurations (135 companies)
│   ├── title_patterns.yaml            # Title patterns for Workable filtering
│   └── location_patterns.yaml         # Location patterns for Workable filtering
├── smartrecruiters/                   # SmartRecruiters-specific configs
│   ├── company_mapping.json           # SmartRecruiters company configurations (35 companies)
│   ├── title_patterns.yaml            # Title patterns for SmartRecruiters filtering
│   └── location_patterns.yaml         # Location patterns for SmartRecruiters filtering
├── agency_blacklist.yaml              # Agency names for hard filtering
├── location_mapping.yaml              # Master location config (cities, countries, regions)
├── job_family_mapping.yaml            # job_subfamily → job_family mapping (strict)
├── skill_family_mapping.yaml          # skill → skill_family mapping (997 skills, 40 families)
├── skill_domain_mapping.yaml          # skill_family → domain mapping (40 families, 9 domains)
└── supported_ats.yaml                 # Supported ATS platforms
```

### 5. **`migrations/` Directory** (Database Migrations)
SQL scripts for database schema changes (32 migration files):

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
├── 008_add_locations_jsonb.sql            # Add locations JSONB column with GIN index
├── 009_add_sfo_sgp_city_codes.sql         # Add SF and Singapore city codes
├── 010_create_employer_fill_stats.sql     # Employer fill stats table (Epic 8)
├── 011_create_job_summaries.sql           # [DEPRECATED] Replaced by inline summary
├── 012_add_url_status_column.sql          # URL health tracking column (Epic 8)
├── 013_add_summary_column.sql             # Inline summary column on enriched_jobs
├── 014_add_updated_at_trigger.sql         # Auto-update updated_at column
├── 015_add_timestamps_all_tables.sql      # Add timestamps to all tables
├── 016_update_url_status.sql              # Expand url_status values
├── 017_add_410_url_status.sql             # Add HTTP 410 (Gone) status
├── 018_create_employer_metadata.sql       # Employer metadata table (canonical names)
├── 019_rename_employer_fill_stats_column.sql # Rename employer_name to canonical_name
├── 020_create_jobs_with_employer_context_view.sql # View with display_name JOIN
├── 021_add_employer_name_fk.sql           # FK constraint on enriched_jobs.employer_name
├── 022_simplify_view_joins.sql            # Remove LOWER() from view JOINs
├── 023_drop_aliases_column.sql            # Remove unused aliases column
├── 024_drop_enriched_jobs_employer_size.sql # Remove employer_size from enriched_jobs
├── 025_extend_employer_metadata.sql       # Extend employer_metadata with industry, HQ, etc.
├── 025b_update_view_with_industry.sql     # Add industry to jobs_with_employer_context view
├── 025c_add_financial_services_industry.sql # Add financial_services industry value
├── 025c_add_parent_company_to_view.sql    # Add parent_company to view
├── 026_standardize_headquarters.sql       # Standardize headquarters values
├── 027_add_productivity_industry.sql      # Add productivity industry value
├── 028_add_careers_url.sql                # Add careers_url to employer_metadata
└── 029_posted_date_default.sql            # Default value for posted_date
```

### 6. **`docs/` Directory** (Documentation)

```
docs/
├── README.md                           # Documentation index
├── REPOSITORY_STRUCTURE.md             # This file
├── PRODUCT_BRIEF.md                    # Product requirements
├── architecture/                       # Architecture design docs
│   ├── MULTI_SOURCE_PIPELINE.md       # 6-source pipeline architecture
│   ├── INCREMENTAL_UPSERT_DESIGN.md   # Incremental upsert architecture
│   ├── ADDING_NEW_LOCATIONS.md        # Guide for adding new cities/countries/regions
│   ├── SECURITY_AUDIT_REPORT.md       # Security assessment
│   ├── In Progress/                   # Active epic documents
│   └── Done/                          # Completed epic documents
├── design/                             # UX design specifications
│   ├── JOB_FEED_UX_DESIGN.md         # Job feed UX spec (v1.5)
│   └── job-feed-mockup.html           # Interactive HTML mockup
├── costs/                              # Cost tracking and metrics
│   ├── COST_METRICS.md                # Historical cost analysis (pre-Gemini migration)
│   └── claude_api_*.csv               # Anthropic usage exports
├── database/
│   └── SCHEMA_UPDATES.md              # Database schema changelog
├── archive/                            # Historical docs and completed epics
├── blacklisting_process.md            # Agency detection methodology
├── marketplace_questions.md           # Business questions spec
├── schema_taxonomy.yaml               # Classification taxonomy
└── system_architecture.yaml           # System design spec
```

### 7. **`tests/` Directory** (Test Suite)

```
tests/
├── TESTING_GUIDE.md                    # Consolidated testing guide
├── eval_gemini.py                      # Gemini classifier evaluation script
├── test_agency_detection.py            # Agency filtering tests
├── test_ashby_fetcher.py               # Ashby fetcher tests
├── test_db_upsert.py                   # Database upsert logic
├── test_e2e_greenhouse_filtered.py     # E2E pipeline tests
├── test_embed_extraction.py            # Embed URL extraction tests
├── test_greenhouse_scraper_filtered.py # Scraper integration tests
├── test_greenhouse_title_filter_unit.py # Title filter unit tests
├── test_incremental_pipeline.py        # Incremental upsert tests
├── test_inline_summary.py             # Inline summary generation tests
├── test_job_family_mapper.py           # Job family mapping tests
├── test_lever_fetcher.py               # Lever fetcher tests
├── test_location_extractor.py          # Location extraction tests (50+ cases)
├── test_pipeline_integration.py        # Simulated pipeline integration tests (all sources)
├── test_resume_capability.py           # Resume capability tests
├── test_skill_family_mapper.py         # Skill family mapping tests
├── test_smartrecruiters_fetcher.py     # SmartRecruiters fetcher tests
├── test_summary_retry_large.py         # Summary retry/large input tests
├── test_url_validator.py               # URL validator tests
├── test_workable_fetcher.py            # Workable fetcher tests
└── fixtures/                           # Test data (CSV/JSON evaluation datasets)
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

# All 6 sources
python wrappers/fetch_jobs.py --sources adzuna,greenhouse,lever,ashby,workable,smartrecruiters

# Adzuna only (batch mode)
python wrappers/fetch_jobs.py lon 100 --sources adzuna

# Reports
python pipeline/report_generator.py --city lon --family data --start 2025-12-01 --end 2025-12-31
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
from pipeline.classifier import classify_job  # Routes to Gemini (default) or Claude
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
| Root wrappers | 8 | Python scripts (7 scripts + __init__) |
| Core pipeline | 13 | Python scripts (incl. report_generator, 3 Epic 8 scripts) |
| Utilities (active) | 14 | Python scripts |
| Utilities (archived) | 17 | Python scripts (pipeline/utilities/archive/) |
| Scrapers | 12 | Python scripts (across 7 directories) |
| Migrations | 32 | SQL scripts (001-029 incl. sub-versions) |
| Config files | 23 | YAML/JSON (6 shared + 3x5 ATS-specific + 2 greenhouse extras) |
| Test files | 20 | Python scripts |
| **Total active** | **122** | **Scripts + configs** |

## Current Status

### Implemented Features
- **6-Source Pipeline:** Adzuna + Greenhouse + Lever + Ashby + Workable + SmartRecruiters
- **Incremental Upserts:** Per-company database writes (no more 3-hour batch failures)
- **Resume Capability:** `--resume-hours N` skips recently processed companies
- **Hash-based Deduplication:** UPSERT by company+title+city hash
- **Last Seen Tracking:** Distinguishes first discovery from most recent scrape
- **Deterministic Mapping:** Job family and skill family derived from mappings (not LLM)
- **Gemini Classifier:** Gemini 2.5 Flash ($0.000629/job) for high-volume sources, Gemini 3.0 Flash ($0.002435/job) for others
- **Report Generator:** Flexible reports by city/family/date with portfolio output

### Completed Epics
- **Epic 5: Analytics Query Layer** - Next.js API routes at `richjacobs.me/projects/hiring-market`
- **Epic 6: Dashboard & Visualization** - Interactive dashboard with 5 chart types
- **Epic 7: Automation & Operational** - GitHub Actions for all 6 ATS sources + Adzuna
- **Ashby Integration** - 169 companies, structured compensation data
- **Workable Integration** - 135 companies, workplace_type and salary data
- **SmartRecruiters Integration** - 35 companies, locationType and experienceLevel
- **Employer Metadata & Enrichment** - industry, HQ, display names, working arrangement defaults
- **Global Location Expansion** - JSONB location system supporting 14 cities, 9 countries, 3 regions
- **Epic 8: Curated Job Feed** (Phase 2 complete)
  - [DONE] Infrastructure: migrations, pipeline scripts, API endpoints
  - [DONE] Frontend: job feed page, filter components, API integration
  - See: `docs/architecture/In Progress/EPIC_JOB_FEED.md`

### Maintaining Cleanliness
- Archive diagnostic scripts after use in `pipeline/utilities/archive/`
- Keep `pipeline/` and root directory clean
- Document major changes in session summary files

---

**Last Updated:** 2026-02-07
**Changes:** Comprehensive documentation refresh -- updated all file counts, added SmartRecruiters/Workable/Ashby throughout, updated migrations to 029, test files to 20, updated classifier to Gemini 2.5 Flash.
**Status:** Clean structure, 6-source pipeline, employer_metadata is source of truth for employer attributes
