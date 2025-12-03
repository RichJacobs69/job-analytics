#!/usr/bin/env python3
"""
Wrapper script: Backfill agency flags on existing enriched_jobs.

Purpose:
--------
Reprocess all existing jobs in enriched_jobs table to add/update agency detection flags.

Usage:
    python backfill_agency_flags.py [--batch-size N] [--dry-run] [--force]

Arguments:
  --batch-size N : How many jobs to process at once (default: 50)
  --dry-run      : Show what would be updated without actually updating
  --force        : Reprocess ALL jobs (even those with existing flags)

Note: This is a wrapper around pipeline/utilities/backfill_agency_flags.py
"""

if __name__ == "__main__":
    import sys
    from pipeline.utilities.backfill_agency_flags import backfill_agency_flags

    import argparse
    parser = argparse.ArgumentParser(
        description='Backfill agency flags on existing enriched_jobs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be updated
  python backfill_agency_flags.py --dry-run

  # Update all jobs with agency flags
  python backfill_agency_flags.py

  # Force reprocess all jobs
  python backfill_agency_flags.py --force

  # Use smaller batch size
  python backfill_agency_flags.py --batch-size 25
        """
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='How many jobs to process at once (default: 50)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without actually updating'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Reprocess ALL jobs (even those with existing flags)'
    )

    args = parser.parse_args()

    backfill_agency_flags(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        force_reprocess=args.force
    )
