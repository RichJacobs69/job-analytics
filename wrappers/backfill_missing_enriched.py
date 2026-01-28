#!/usr/bin/env python3
"""
Wrapper script: Backfill jobs missing from enriched_jobs table.

Purpose:
--------
Finds all raw_jobs that don't have a corresponding enriched_job and processes them
through the classification pipeline.

This script is useful for:
1. Recovering from classification failures (null job_family, API errors, etc.)
2. Backfilling after bug fixes
3. Processing jobs that were skipped due to transient errors

Usage:
------
python backfill_missing_enriched.py [--limit N] [--dry-run]

Arguments:
  --limit N    : Only process N jobs (default: all)
  --dry-run    : Show what would be processed without actually processing
  --hours N    : Only process raw_jobs from last N hours (default: all time)

Note: This is a wrapper around pipeline/utilities/backfill_missing_enriched.py
"""

import sys
from pathlib import Path

# Add project root to Python path for module imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    from pipeline.utilities.backfill_missing_enriched import backfill_missing_enriched

    import argparse
    parser = argparse.ArgumentParser(
        description='Backfill missing enriched_jobs from raw_jobs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be processed
  python backfill_missing_enriched.py --dry-run

  # Process all missing jobs
  python backfill_missing_enriched.py

  # Process only 50 missing jobs
  python backfill_missing_enriched.py --limit 50

  # Process only jobs from last 24 hours
  python backfill_missing_enriched.py --hours 24

  # Dry run for recent jobs
  python backfill_missing_enriched.py --hours 24 --dry-run
        """
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of jobs to process (default: all)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually processing'
    )

    parser.add_argument(
        '--hours',
        type=int,
        help='Only process jobs from last N hours (default: all time)'
    )

    parser.add_argument(
        '--source',
        type=str,
        help='Filter by source (e.g., custom, greenhouse, lever, ashby, workable, adzuna)'
    )

    args = parser.parse_args()

    backfill_missing_enriched(
        limit=args.limit,
        dry_run=args.dry_run,
        hours_back=args.hours,
        source=args.source
    )
