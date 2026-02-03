"""
Backfill Script: Fix global remote misclassifications

Purpose:
--------
Updates enriched_jobs where locations contains scope="global" by checking
the job description for country restrictions (e.g., "US only", "based in Canada").

Jobs are often listed with location="Remote" but have country restrictions
buried in the description. This script fixes those misclassifications.

Usage:
------
python pipeline/utilities/backfill_global_remote.py [--limit N] [--dry-run]

Arguments:
  --limit N    : Only process N jobs (default: all)
  --dry-run    : Show what would be updated without actually updating
  --source     : Only process jobs from a specific source (greenhouse, lever, etc.)
"""

import logging
import argparse
import sys
import json
from typing import List, Dict, Optional

sys.path.insert(0, '.')
from pipeline.db_connection import supabase
from pipeline.location_extractor import extract_country_restriction_from_description

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_global_remote_jobs(limit: int = None, source: str = None) -> List[Dict]:
    """
    Find enriched_jobs with scope="global" in locations.

    Returns:
        List of enriched_job records with their raw_job_id
    """
    logger.info("Finding enriched_jobs with global remote scope...")

    jobs = []
    offset = 0
    page_size = 1000

    while True:
        # Use filter with cs (contains) operator for JSONB array matching
        query = supabase.table('enriched_jobs') \
            .select('id, raw_job_id, employer_name, title_display, locations, data_source') \
            .filter('locations', 'cs', '[{"scope":"global"}]')

        if source:
            query = query.eq('data_source', source)

        query = query.range(offset, offset + page_size - 1)
        result = query.execute()

        if not result.data:
            break

        for job in result.data:
            jobs.append(job)
            if limit and len(jobs) >= limit:
                return jobs

        if len(result.data) < page_size:
            break

        offset += page_size

    return jobs


def get_raw_job_descriptions(raw_job_ids: List[int]) -> Dict[int, str]:
    """
    Fetch descriptions for a list of raw_job_ids.

    Returns:
        Dict mapping raw_job_id to description text
    """
    description_map = {}

    # Batch fetch in chunks of 100
    for i in range(0, len(raw_job_ids), 100):
        chunk = raw_job_ids[i:i+100]
        result = supabase.table('raw_jobs') \
            .select('id, raw_text, metadata') \
            .in_('id', chunk) \
            .execute()

        for job in result.data:
            # Try raw_text first (full description), then metadata
            description = job.get('raw_text') or ''

            # If no raw_text, try to get from metadata
            if not description:
                metadata = job.get('metadata') or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}
                description = metadata.get('description') or ''

            description_map[job['id']] = description

    return description_map


def update_job_location(enriched_id: int, new_locations: List[Dict]) -> bool:
    """
    Update an enriched_job with new location data.

    Returns:
        True if successful, False otherwise
    """
    try:
        supabase.table('enriched_jobs') \
            .update({'locations': new_locations}) \
            .eq('id', enriched_id) \
            .execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update job {enriched_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Backfill global remote misclassifications')
    parser.add_argument('--limit', type=int, help='Maximum jobs to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    parser.add_argument('--source', type=str, help='Only process jobs from this source')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("BACKFILL GLOBAL REMOTE MISCLASSIFICATIONS")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info(f"Limit: {args.limit or 'None (all)'}")
    logger.info(f"Source: {args.source or 'All sources'}")
    logger.info("=" * 60)

    # Find jobs with global remote scope
    global_remote_jobs = find_global_remote_jobs(limit=args.limit, source=args.source)
    logger.info(f"Found {len(global_remote_jobs)} jobs with global remote scope")

    if not global_remote_jobs:
        logger.info("Nothing to do!")
        return

    # Get raw_job descriptions
    raw_job_ids = [j['raw_job_id'] for j in global_remote_jobs if j.get('raw_job_id')]
    logger.info(f"Fetching descriptions for {len(raw_job_ids)} raw_jobs...")
    description_map = get_raw_job_descriptions(raw_job_ids)

    # Process each job
    stats = {
        'total': len(global_remote_jobs),
        'reclassified': 0,
        'still_global': 0,
        'no_description': 0,
        'errors': 0,
        'by_country': {}
    }

    for i, job in enumerate(global_remote_jobs, 1):
        enriched_id = job['id']
        raw_job_id = job.get('raw_job_id')
        employer = job.get('employer_name', 'Unknown')
        title = job.get('title_display', 'Unknown')[:40]

        if not raw_job_id:
            stats['no_description'] += 1
            continue

        description = description_map.get(raw_job_id, '')

        if not description or len(description) < 50:
            stats['no_description'] += 1
            continue

        # Check for country restriction in description
        country_code = extract_country_restriction_from_description(description)

        if not country_code:
            stats['still_global'] += 1
            continue

        # Found a country restriction - build new locations
        new_locations = [{
            "type": "remote",
            "scope": "country",
            "country_code": country_code
        }]

        # Track by country
        stats['by_country'][country_code] = stats['by_country'].get(country_code, 0) + 1

        if args.dry_run:
            logger.info(f"[{i}/{len(global_remote_jobs)}] Would reclassify: {employer} - {title} -> {country_code}")
            stats['reclassified'] += 1
        else:
            if update_job_location(enriched_id, new_locations):
                stats['reclassified'] += 1
                if i % 100 == 0:
                    logger.info(f"[{i}/{len(global_remote_jobs)}] Reclassified {stats['reclassified']} jobs...")
            else:
                stats['errors'] += 1

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total with global remote:     {stats['total']}")
    logger.info(f"Reclassified to country:      {stats['reclassified']}")
    logger.info(f"Still global (no restriction):{stats['still_global']}")
    logger.info(f"No description available:     {stats['no_description']}")
    logger.info(f"Errors:                       {stats['errors']}")

    if stats['by_country']:
        logger.info("")
        logger.info("Reclassified by country:")
        for country, count in sorted(stats['by_country'].items(), key=lambda x: -x[1]):
            logger.info(f"  {country}: {count}")


if __name__ == '__main__':
    main()
