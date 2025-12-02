# Repository Structure (Updated 2025-12-02)

> **Single Source of Truth for Directory Organization**
>
> This document is the authoritative guide for how files are organized in this repository. For development guidance and project overview, see [`CLAUDE.md`](CLAUDE.md). For system architecture details, see [`docs/architecture/`](docs/architecture/).

## Organization Overview

The repository is now organized into three clear areas:

### 1. **`wrapper/` Directory** (User-Facing Entry Points)
Thin wrapper scripts that serve as the main entry points for users. Each wrapper imports from `pipeline/` to avoid code duplication.

```
wrapper/
├── __init__.py                          # Package marker with documentation
├── fetch_jobs.py                        # Wrapper → pipeline/fetch_jobs.py
├── run_all_cities.py                    # Wrapper → pipeline/run_all_cities.py
├── check_pipeline_status.py             # Wrapper → pipeline/utilities/check_pipeline_status.py
├── analyze_db_results.py                # Wrapper → pipeline/utilities/analyze_db_results.py
├── backfill_missing_enriched.py         # Wrapper → pipeline/utilities/backfill_missing_enriched.py
└── backfill_agency_flags.py             # Wrapper → pipeline/utilities/backfill_agency_flags.py
```

**Why separate wrapper directory?**
- Clean separation: wrappers are isolated from production code
- Clear intent: directory name signals "these are entry points"
- Easy to manage: can move to `bin/` for system-wide installation if needed
- Users can call: `python wrapper/fetch_jobs.py` or add to PATH

### 2. **`pipeline/` Directory** (Core Production Code)

#### Core Pipeline Scripts
These are the production components of the job analytics pipeline:

```
pipeline/fetch_jobs.py              # Main dual-source orchestrator
pipeline/classifier.py              # Claude LLM integration
pipeline/db_connection.py           # Supabase PostgreSQL client
pipeline/agency_detection.py        # Agency filtering logic
pipeline/unified_job_ingester.py    # Merge & deduplication
pipeline/run_all_cities.py          # Parallel orchestration (original)
pipeline/README.md                  # Pipeline documentation
```

#### Utilities Subdirectory
Maintenance and diagnostic tools:

```
pipeline/utilities/check_pipeline_status.py      # Quick status checks
pipeline/utilities/analyze_db_results.py         # Database analysis
pipeline/utilities/backfill_missing_enriched.py  # Job recovery
pipeline/utilities/backfill_agency_flags.py      # Agency flag updates
```

### 3. **Other Directories** (Unchanged)

```
scrapers/              # Web scrapers (Adzuna, Greenhouse)
config/                # Configuration files
docs/                  # Documentation
  ├── README.md        # Documentation index
  ├── schema_taxonomy.yaml
  ├── system_architecture.yaml
  ├── product_brief.yaml
  └── archive/         # Historical docs and session notes
tests/                 # Test suite
output/                # Generated outputs (gitignored)
```

## Usage Examples

### Core Pipeline

```bash
# Fetch from both sources (London, 100 jobs per query)
python fetch_jobs.py lon 100 --sources adzuna,greenhouse

# Adzuna only
python fetch_jobs.py lon 100 --sources adzuna

# Greenhouse only
python fetch_jobs.py --sources greenhouse

# Run all cities in parallel
python run_all_cities.py --max-jobs 100 --sources adzuna,greenhouse
```

### Utilities

```bash
# Check pipeline status
python check_pipeline_status.py

# Analyze database
python analyze_db_results.py

# Backfill missing jobs (dry run)
python backfill_missing_enriched.py --dry-run

# Backfill missing jobs (last 24 hours, limit 50)
python backfill_missing_enriched.py --hours 24 --limit 50

# Update agency flags
python backfill_agency_flags.py --dry-run
```

## Import Structure

**From pipeline modules:** (used within the pipeline)
```python
from pipeline.classifier import classify_job_with_claude
from pipeline.db_connection import supabase, insert_enriched_job
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
   - User-facing wrappers in root

2. **Easy discoverability:**
   - Users still call scripts from project root: `python fetch_jobs.py`
   - Developers know to look in `pipeline/` for implementation
   - Utilities grouped logically in `pipeline/utilities/`

3. **Scalability:**
   - Easy to add new utilities without cluttering root
   - Core pipeline stays focused and clean
   - Future additions have clear home

4. **Backward compatibility:**
   - Wrapper scripts maintain existing command-line interface
   - No need to update documentation or tutorials
   - Old scripts can be archived systematically

## Changes from Previous Structure

### Archived (Session 2025-12-02)
These diagnostic scripts from debugging are now in `docs/archive/session_2025-12-02_backfill/`:
- `analyze_job_discrepancy.py` - Initial discrepancy analysis
- `detailed_job_analysis.py` - Detailed UPSERT analysis
- `check_schema.py` - Quick schema inspection
- `monitor_progress.ps1` - PowerShell monitoring script
- `SESSION_SUMMARY.md` - Complete session documentation

### Created (Session 2025-12-02)
New utilities for ongoing use:
- `pipeline/utilities/backfill_missing_enriched.py` - Recovers missing jobs
- Wrapper scripts for all utilities

### Moved to Subdirectories
All scripts properly organized with updated imports:
- Core pipeline scripts → `pipeline/`
- Utilities → `pipeline/utilities/`
- Wrapper scripts in root

## File Statistics

| Area | Count | Type |
|------|-------|------|
| Root wrappers | 6 | Python scripts |
| Core pipeline | 6 | Python scripts |
| Utilities | 4 | Python scripts |
| **Total active** | **16** | **Scripts** |
| Archived | 5 | Diagnostic scripts |
| **Total with archive** | **21** | **All scripts** |

## Next Steps

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

**Last Updated:** 2025-12-02
**Changes:** Reorganized core/utility scripts into pipeline/ directory with wrapper scripts for backward compatibility
**Status:** Ready for production use and analytics layer development
