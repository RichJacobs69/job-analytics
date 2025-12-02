# Wrapper Directory Reorganization (2025-12-02)

## Change Summary

Moved all wrapper scripts from project root into a dedicated `wrapper/` directory for cleaner organization.

### Before
```
job-analytics/
├── fetch_jobs.py              (wrapper)
├── run_all_cities.py          (wrapper)
├── check_pipeline_status.py   (wrapper)
├── analyze_db_results.py      (wrapper)
├── backfill_missing_enriched.py (wrapper)
├── backfill_agency_flags.py   (wrapper)
├── pipeline/                  (production code)
└── ...
```

### After
```
job-analytics/
├── wrapper/                   (USER-FACING ENTRY POINTS)
│   ├── __init__.py
│   ├── fetch_jobs.py
│   ├── run_all_cities.py
│   ├── check_pipeline_status.py
│   ├── analyze_db_results.py
│   ├── backfill_missing_enriched.py
│   └── backfill_agency_flags.py
│
├── pipeline/                  (CORE PRODUCTION CODE)
│   ├── fetch_jobs.py          (implementation)
│   ├── classifier.py
│   ├── db_connection.py
│   ├── unified_job_ingester.py
│   ├── agency_detection.py
│   ├── run_all_cities.py      (implementation)
│   └── utilities/             (maintenance scripts)
│       ├── check_pipeline_status.py
│       ├── analyze_db_results.py
│       ├── backfill_missing_enriched.py
│       └── backfill_agency_flags.py
└── ...
```

## Benefits

| Aspect | Improvement |
|--------|-------------|
| **Clarity** | Clear signal: "wrapper/" = entry points, "pipeline/" = implementation |
| **Cleanliness** | Root directory is now empty of Python scripts |
| **Organization** | Each directory has clear purpose and responsibility |
| **Scalability** | Can easily add more wrappers without cluttering root |
| **Distribution** | wrapper/ can be copied to `bin/` for system-wide installation |

## Usage

Users now call wrappers from the project root:
```bash
python wrapper/fetch_jobs.py lon 100 --sources adzuna,greenhouse
python wrapper/check_pipeline_status.py
python wrapper/backfill_missing_enriched.py --dry-run
```

Or add wrapper/ to PATH for direct access:
```bash
export PATH="$PATH:$(pwd)/wrapper"
fetch_jobs.py lon 100 --sources adzuna,greenhouse
```

## Architecture

```
User calls: python wrapper/fetch_jobs.py
                        ↓
wrapper/fetch_jobs.py (thin wrapper ~30 lines)
    imports from pipeline.fetch_jobs
                        ↓
pipeline/fetch_jobs.py (full implementation ~500+ lines)
    uses other pipeline modules (classifier, db_connection, etc.)
```

## Documentation Updated

- ✅ REPOSITORY_STRUCTURE.md - now shows wrapper/ as section 1
- ✅ CLAUDE.md - updated all usage examples to use wrapper/ paths
- ✅ wrapper/__init__.py - added package documentation

## No Code Changes

- ✅ All wrapper scripts import statements unchanged
- ✅ All pipeline module implementations unchanged
- ✅ No duplication (wrappers are still thin ~400-2000 byte files)
- ✅ Backward compatible (same functionality, better organization)

---

**Status:** Reorganization complete. Root directory is clean, wrapper scripts properly organized.
