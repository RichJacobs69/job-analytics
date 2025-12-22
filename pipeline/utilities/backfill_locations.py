"""
Backfill Script: Fix enriched_jobs with unknown locations

Purpose:
--------
Updates enriched_jobs that have locations = [{"type":"unknown"}] by re-extracting
location data from the corresponding raw_jobs metadata.

This script is useful for:
1. Fixing jobs processed before location extraction was properly configured
2. Recovering location data after fixing metadata field name issues

Usage:
------
python pipeline/utilities/backfill_locations.py [--limit N] [--dry-run]

Arguments:
  --limit N    : Only process N jobs (default: all)
  --dry-run    : Show what would be updated without actually updating
"""

import logging
import argparse
import sys
import json
from typing import List, Dict, Tuple

sys.path.insert(0, '.')
from pipeline.db_connection import supabase
from pipeline.location_extractor import extract_locations

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Map short city codes to full names for location extractor
CITY_CODE_TO_NAME = {
    'lon': 'London',
    'nyc': 'New York',
    'den': 'Denver',
    'sfo': 'San Francisco',
    'sgp': 'Singapore',
}


def find_unknown_location_jobs(limit: int = None) -> List[Dict]:
    """
    Find enriched_jobs with [{"type":"unknown"}] locations.

    Returns:
        List of enriched_job records with their raw_job_id
    """
    logger.info("Finding enriched_jobs with unknown locations...")

    jobs = []
    offset = 0
    page_size = 1000

    while True:
        query = supabase.table('enriched_jobs') \
            .select('id, raw_job_id, locations, city_code') \
            .range(offset, offset + page_size - 1)

        result = query.execute()

        if not result.data:
            break

        for job in result.data:
            locations = job.get('locations', [])
            # Check if locations is [{"type":"unknown"}]
            if (isinstance(locations, list) and
                len(locations) == 1 and
                locations[0].get('type') == 'unknown'):
                jobs.append(job)
                if limit and len(jobs) >= limit:
                    return jobs

        if len(result.data) < page_size:
            break

        offset += page_size

    return jobs


def get_raw_job_metadata(raw_job_ids: List[int]) -> Dict[int, Dict]:
    """
    Fetch metadata for a list of raw_job_ids.

    Returns:
        Dict mapping raw_job_id to metadata dict
    """
    metadata_map = {}

    # Batch fetch in chunks of 100
    for i in range(0, len(raw_job_ids), 100):
        chunk = raw_job_ids[i:i+100]
        result = supabase.table('raw_jobs') \
            .select('id, metadata, source') \
            .in_('id', chunk) \
            .execute()

        for job in result.data:
            metadata = job.get('metadata') or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            metadata_map[job['id']] = {
                'metadata': metadata,
                'source': job.get('source')
            }

    return metadata_map


def extract_location_from_metadata(metadata: Dict) -> Tuple[List[Dict], str]:
    """
    Extract location from raw_job metadata.

    Returns:
        Tuple of (locations list, legacy city_code)
    """
    # Prefer adzuna_city (normalized code) over adzuna_location (free text)
    source_location = (
        metadata.get('adzuna_city') or  # Normalized city code (lon, nyc, etc.)
        metadata.get('adzuna_location') or  # Free text fallback
        metadata.get('lever_location') or
        metadata.get('greenhouse_location')
    )

    # Convert short city codes to full names
    if source_location and source_location.lower() in CITY_CODE_TO_NAME:
        source_location = CITY_CODE_TO_NAME[source_location.lower()]

    if not source_location:
        return [{"type": "unknown"}], 'unk'

    locations = extract_locations(source_location)

    # Derive legacy city_code
    city_code = 'unk'
    if locations and locations[0].get('type') == 'city':
        city_name = locations[0].get('city', '')
        city_to_code = {
            'london': 'lon',
            'new_york': 'nyc',
            'denver': 'den',
            'san_francisco': 'sfo',
            'singapore': 'sgp'
        }
        city_code = city_to_code.get(city_name, 'unk')
    elif locations and locations[0].get('type') == 'remote':
        city_code = 'remote'

    return locations, city_code


def update_job_location(enriched_id: int, locations: List[Dict], city_code: str) -> bool:
    """
    Update an enriched_job with new location data.

    Returns:
        True if successful, False otherwise
    """
    try:
        supabase.table('enriched_jobs') \
            .update({
                'locations': locations,
                'city_code': city_code
            }) \
            .eq('id', enriched_id) \
            .execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update job {enriched_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Backfill unknown locations in enriched_jobs')
    parser.add_argument('--limit', type=int, help='Maximum jobs to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("BACKFILL UNKNOWN LOCATIONS")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info(f"Limit: {args.limit or 'None (all)'}")
    logger.info("=" * 60)

    # Find jobs with unknown locations
    unknown_jobs = find_unknown_location_jobs(limit=args.limit)
    logger.info(f"Found {len(unknown_jobs)} jobs with unknown locations")

    if not unknown_jobs:
        logger.info("Nothing to do!")
        return

    # Get raw_job metadata
    raw_job_ids = [j['raw_job_id'] for j in unknown_jobs]
    logger.info(f"Fetching metadata for {len(raw_job_ids)} raw_jobs...")
    metadata_map = get_raw_job_metadata(raw_job_ids)

    # Process each job
    stats = {
        'total': len(unknown_jobs),
        'updated': 0,
        'still_unknown': 0,
        'no_metadata': 0,
        'errors': 0
    }

    for i, job in enumerate(unknown_jobs, 1):
        enriched_id = job['id']
        raw_job_id = job['raw_job_id']

        raw_data = metadata_map.get(raw_job_id, {})
        metadata = raw_data.get('metadata', {})

        if not metadata:
            stats['no_metadata'] += 1
            if not args.dry_run:
                logger.debug(f"[{i}/{len(unknown_jobs)}] Job {enriched_id}: No metadata")
            continue

        locations, city_code = extract_location_from_metadata(metadata)

        # Check if we found a real location
        if locations[0].get('type') == 'unknown':
            stats['still_unknown'] += 1
            continue

        if args.dry_run:
            logger.info(f"[{i}/{len(unknown_jobs)}] Would update job {enriched_id}: {locations} (city_code: {city_code})")
            stats['updated'] += 1
        else:
            if update_job_location(enriched_id, locations, city_code):
                stats['updated'] += 1
                if i % 100 == 0 or i == len(unknown_jobs):
                    logger.info(f"[{i}/{len(unknown_jobs)}] Updated {stats['updated']} jobs...")
            else:
                stats['errors'] += 1

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total with unknown locations: {stats['total']}")
    logger.info(f"Updated with real locations:  {stats['updated']}")
    logger.info(f"Still unknown (no data):      {stats['still_unknown']}")
    logger.info(f"No metadata found:            {stats['no_metadata']}")
    logger.info(f"Errors:                       {stats['errors']}")


if __name__ == '__main__':
    main()
