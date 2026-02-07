"""
Backfill Script: Re-extract locations by scope and source

Purpose:
--------
Re-runs extract_locations() on enriched_jobs matching a given scope and source,
using the raw location string from raw_jobs metadata. Useful after fixes to
location_extractor.py to correct historically misclassified jobs.

Usage:
------
# Re-extract all scope=global jobs from greenhouse/lever/ashby (the common fix)
python pipeline/utilities/backfill_global_scope.py --scope global --dry-run

# Target a single source
python pipeline/utilities/backfill_global_scope.py --scope global --source ashby --dry-run

# Target scope=country jobs from lever only
python pipeline/utilities/backfill_global_scope.py --scope country --source lever --dry-run

# Only jobs classified before a certain date
python pipeline/utilities/backfill_global_scope.py --scope global --before 2026-02-03

# Run for real (no --dry-run)
python pipeline/utilities/backfill_global_scope.py --scope global
"""

import logging
import argparse
import sys
import json
from typing import List, Dict, Optional

sys.path.insert(0, '.')
from pipeline.db_connection import supabase
from pipeline.location_extractor import extract_locations

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

VALID_SOURCES = ['greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters', 'adzuna']
VALID_SCOPES = ['global', 'country', 'region']


def find_jobs(scope: str, sources: List[str], before: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
    """Find enriched_jobs matching scope and source filters."""
    jobs = []
    offset = 0
    page_size = 1000

    while True:
        query = supabase.table('enriched_jobs') \
            .select('id, raw_job_id, locations, data_source, employer_name, title_display') \
            .contains('locations', json.dumps([{"scope": scope}])) \
            .in_('data_source', sources) \
            .range(offset, offset + page_size - 1)

        if before:
            query = query.lt('classified_at', before)

        result = query.execute()

        if not result.data:
            break

        jobs.extend(result.data)

        if limit and len(jobs) >= limit:
            return jobs[:limit]

        if len(result.data) < page_size:
            break

        offset += page_size

    return jobs


def get_raw_job_data(raw_job_ids: List[int]) -> Dict[int, Dict]:
    """Fetch metadata and description for raw_job_ids."""
    data_map = {}

    for i in range(0, len(raw_job_ids), 100):
        chunk = raw_job_ids[i:i + 100]
        result = supabase.table('raw_jobs') \
            .select('id, metadata, raw_text, source') \
            .in_('id', chunk) \
            .execute()

        for job in result.data:
            metadata = job.get('metadata') or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            data_map[job['id']] = {
                'metadata': metadata,
                'raw_text': job.get('raw_text', ''),
                'source': job.get('source')
            }

    return data_map


def extract_location_string(metadata: Dict) -> Optional[str]:
    """Pull the raw location string from metadata, handling all sources."""
    return (
        metadata.get('ashby_location') or
        metadata.get('lever_location') or
        metadata.get('greenhouse_location') or
        metadata.get('adzuna_location') or
        metadata.get('adzuna_city') or
        None
    )


def locations_changed(old: List[Dict], new: List[Dict]) -> bool:
    """Check if locations have meaningfully changed."""
    return json.dumps(old, sort_keys=True) != json.dumps(new, sort_keys=True)


def main():
    parser = argparse.ArgumentParser(
        description='Re-extract locations for enriched_jobs by scope and source',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scope global --dry-run          # Preview all scope=global fixes
  %(prog)s --scope global --source ashby     # Fix only Ashby global-scope jobs
  %(prog)s --scope global --before 2026-02-03  # Only pre-fix jobs
  %(prog)s --scope country --source lever    # Re-extract country-scoped Lever jobs
        """
    )
    parser.add_argument('--scope', required=True, choices=VALID_SCOPES,
                        help='Target location scope to re-extract')
    parser.add_argument('--source', choices=VALID_SOURCES,
                        help='Target a single data source (default: greenhouse,lever,ashby)')
    parser.add_argument('--before', type=str, metavar='YYYY-MM-DD',
                        help='Only jobs classified before this date')
    parser.add_argument('--limit', type=int, help='Maximum jobs to process')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    args = parser.parse_args()

    sources = [args.source] if args.source else ['greenhouse', 'lever', 'ashby']
    before_date = f"{args.before}T00:00:00" if args.before else None

    logger.info("=" * 70)
    logger.info("BACKFILL LOCATIONS BY SCOPE")
    logger.info("=" * 70)
    logger.info(f"  Scope:   {args.scope}")
    logger.info(f"  Sources: {', '.join(sources)}")
    logger.info(f"  Before:  {args.before or '(all time)'}")
    logger.info(f"  Limit:   {args.limit or '(none)'}")
    logger.info(f"  Mode:    {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info("=" * 70)

    # Step 1: Find matching jobs
    jobs = find_jobs(args.scope, sources, before=before_date, limit=args.limit)
    logger.info(f"Found {len(jobs)} scope={args.scope} jobs")

    if not jobs:
        logger.info("Nothing to backfill!")
        return

    # Step 2: Fetch raw metadata + descriptions
    raw_ids = [j['raw_job_id'] for j in jobs if j.get('raw_job_id')]
    logger.info(f"Fetching raw data for {len(raw_ids)} raw_jobs...")
    raw_data = get_raw_job_data(raw_ids)

    # Step 3: Re-extract and compare
    stats = {'total': len(jobs), 'changed': 0, 'unchanged': 0, 'no_location': 0, 'errors': 0}

    for i, job in enumerate(jobs, 1):
        enriched_id = job['id']
        raw_job_id = job.get('raw_job_id')
        old_locations = job.get('locations', [])

        raw = raw_data.get(raw_job_id, {})
        metadata = raw.get('metadata', {})
        description = raw.get('raw_text', '')

        location_str = extract_location_string(metadata)
        if not location_str:
            stats['no_location'] += 1
            continue

        new_locations = extract_locations(location_str, description_text=description)

        if not locations_changed(old_locations, new_locations):
            stats['unchanged'] += 1
            continue

        if args.dry_run:
            logger.info(f"[{i}/{len(jobs)}] {enriched_id} | {job['employer_name']} | {job['data_source']}")
            logger.info(f"  RAW: \"{location_str}\"")
            logger.info(f"  OLD: {json.dumps(old_locations)}")
            logger.info(f"  NEW: {json.dumps(new_locations)}")
            stats['changed'] += 1
        else:
            try:
                supabase.table('enriched_jobs') \
                    .update({'locations': new_locations}) \
                    .eq('id', enriched_id) \
                    .execute()
                stats['changed'] += 1
                if i % 50 == 0 or i == len(jobs):
                    logger.info(f"  [{i}/{len(jobs)}] Updated {stats['changed']} so far...")
            except Exception as e:
                logger.error(f"Failed to update {enriched_id}: {e}")
                stats['errors'] += 1

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"  Total matched:     {stats['total']}")
    logger.info(f"  Changed:           {stats['changed']}")
    logger.info(f"  Unchanged:         {stats['unchanged']}")
    logger.info(f"  No raw location:   {stats['no_location']}")
    logger.info(f"  Errors:            {stats['errors']}")


if __name__ == '__main__':
    main()
