"""
Wrapper Scripts: User-Facing Entry Points

This directory contains thin wrapper scripts that serve as the main entry points for users.
Each wrapper imports from the pipeline/ directory to avoid code duplication.

Users call these scripts from the project root:
    python wrapper/fetch_jobs.py lon 100 --sources adzuna,greenhouse
    python wrapper/check_pipeline_status.py
    python wrapper/backfill_missing_enriched.py --dry-run

Or install these in a bin/ directory for system-wide access.

The actual implementations are in:
    pipeline/ - Core pipeline modules
    pipeline/utilities/ - Maintenance and diagnostic utilities
"""
