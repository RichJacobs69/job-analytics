"""
Backfill Script: Process raw_jobs missing from enriched_jobs

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
"""

import logging
import argparse
import sys
from datetime import datetime, timedelta, date
from typing import List, Dict
sys.path.insert(0, '.')
from pipeline.db_connection import supabase, insert_enriched_job
from pipeline.classifier import classify_job
from pipeline.agency_detection import is_agency_job, validate_agency_classification
from pipeline.location_extractor import extract_locations

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_missing_enriched_jobs(hours_back: int = None, limit: int = None) -> List[Dict]:
    """
    Find all raw_jobs that don't have a corresponding enriched_job.

    Args:
        hours_back: Only look at raw_jobs from last N hours (None = all time)
        limit: Maximum number of jobs to return

    Returns:
        List of raw_job records that need processing
    """

    logger.info("Step 1: Finding raw_jobs missing from enriched_jobs...")

    # Get all enriched job raw_job_ids (handle pagination)
    logger.info("  Fetching all enriched_job raw_job_ids...")
    enriched_raw_ids = set()
    offset = 0
    page_size = 1000

    while True:
        enriched_response = supabase.table('enriched_jobs')\
            .select('raw_job_id')\
            .range(offset, offset + page_size - 1)\
            .execute()

        if not enriched_response.data:
            break

        for job in enriched_response.data:
            enriched_raw_ids.add(job['raw_job_id'])

        if len(enriched_response.data) < page_size:
            break

        offset += page_size

    logger.info(f"  Found {len(enriched_raw_ids)} enriched jobs")

    # Build raw_jobs query with pagination
    logger.info("  Fetching raw_jobs...")
    raw_jobs = []
    offset = 0
    page_size = 1000

    if hours_back:
        cutoff = datetime.now() - timedelta(hours=hours_back)
        cutoff_str = cutoff.isoformat()
        logger.info(f"  Filtering to jobs scraped after {cutoff_str}")

    while True:
        query = supabase.table('raw_jobs').select('*').range(offset, offset + page_size - 1)

        if hours_back:
            query = query.gte('scraped_at', cutoff_str)

        raw_response = query.execute()

        if not raw_response.data:
            break

        raw_jobs.extend(raw_response.data)

        if len(raw_response.data) < page_size:
            break

        offset += page_size

    logger.info(f"  Found {len(raw_jobs)} total raw jobs")

    # Filter to only jobs missing from enriched
    missing_jobs = [job for job in raw_jobs if job['id'] not in enriched_raw_ids]

    logger.info(f"  {len(missing_jobs)} raw_jobs are missing from enriched_jobs")

    if limit and len(missing_jobs) > limit:
        logger.info(f"  Limiting to first {limit} jobs")
        missing_jobs = missing_jobs[:limit]

    return missing_jobs


def infer_city_from_url(url: str) -> str:
    """Infer city from posting URL (best effort)"""
    if not url:
        return 'lon'  # Default to London
    if '.co.uk' in url or 'london' in url.lower():
        return 'lon'
    if 'newyork' in url.lower() or 'nyc' in url.lower():
        return 'nyc'
    if 'denver' in url.lower():
        return 'den'
    return 'lon'  # Default to London


def process_missing_job(raw_job: Dict, source_city: str = 'lon') -> bool:
    """
    Process a single raw_job through classification and store in enriched_jobs.

    Args:
        raw_job: Raw job record from database
        source_city: Default city code if extraction fails

    Returns:
        True if successful, False otherwise
    """

    raw_job_id = raw_job['id']
    raw_text = raw_job.get('raw_text', '')
    source = raw_job.get('source', 'unknown')
    posting_url = raw_job.get('posting_url', '')

    # Infer city from URL
    inferred_city = infer_city_from_url(posting_url)

    try:
        # Check description length
        if len(raw_text.strip()) < 50:
            logger.warning(f"Skipping job {raw_job_id}: description too short ({len(raw_text)} chars)")
            return False

        # Hard agency filter
        # Note: We can't easily get company name from raw_text alone
        # So we'll skip this check for backfill and rely on soft detection

        # Classify the job with structured input (including title and company)
        logger.debug(f"Classifying job {raw_job_id}...")
        structured_input = {
            'title': raw_job.get('title', 'Unknown Title'),
            'company': raw_job.get('company', 'Unknown Company'),
            'description': raw_text,
            'location': inferred_city,
            'category': None,
            'salary_min': None,
            'salary_max': None,
        }
        classification = classify_job(
            job_text=raw_text,
            structured_input=structured_input
        )

        if not classification:
            logger.warning(f"Skipping job {raw_job_id}: classification returned None")
            return False

        # Add agency detection
        # Get employer name: prefer classification, fall back to raw_job's company field
        employer_name = classification.get('employer', {}).get('name')
        if not employer_name or employer_name == 'Unknown Company':
            employer_name = raw_job.get('company') or 'Unknown Company'

        # Get title: prefer classification's title_display, fall back to raw_job's title field
        title_from_classification = classification.get('role', {}).get('title_display')
        title_from_raw = raw_job.get('title')
        job_title = title_from_classification or title_from_raw or 'Unknown Title'

        # Skip jobs without employer info (can't create proper enriched record)
        if employer_name == 'Unknown Company' and job_title == 'Unknown Title':
            logger.warning(f"Skipping job {raw_job_id}: no employer or title info")
            return False

        is_agency, agency_conf = validate_agency_classification(
            employer_name=employer_name,
            claude_is_agency=None,
            claude_confidence=None,
            job_description=raw_text
        )

        # Inject agency flags
        if 'employer' not in classification:
            classification['employer'] = {}
        classification['employer']['is_agency'] = is_agency
        classification['employer']['agency_confidence'] = agency_conf

        # Extract classification data
        role = classification.get('role', {})
        location = classification.get('location', {})
        compensation = classification.get('compensation', {})
        employer = classification.get('employer', {})

        # Extract locations from source metadata (Global Location Expansion Epic)
        # Priority: adzuna_location > lever_location > greenhouse_location > fallback
        metadata = raw_job.get('metadata') or {}
        if isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        # Prefer adzuna_city (normalized code) over adzuna_location (free text)
        source_location = (
            metadata.get('adzuna_city') or  # Normalized city code (lon, nyc, etc.)
            metadata.get('adzuna_location') or  # Free text fallback
            metadata.get('lever_location') or
            metadata.get('greenhouse_location')
        )

        # Convert short city codes to full names for location extractor
        city_code_to_name = {
            'lon': 'London',
            'nyc': 'New York',
            'den': 'Denver',
            'sfo': 'San Francisco',
            'sgp': 'Singapore',
        }
        if source_location and source_location.lower() in city_code_to_name:
            source_location = city_code_to_name[source_location.lower()]

        extracted_locations = extract_locations(source_location) if source_location else [{"type": "unknown"}]

        # Derive legacy city_code from locations for backward compatibility (DEPRECATED)
        legacy_city_code = 'unk'
        if extracted_locations and extracted_locations[0].get('type') == 'city':
            city_name = extracted_locations[0].get('city', '')
            city_to_code = {'london': 'lon', 'new_york': 'nyc', 'denver': 'den', 'san_francisco': 'sfo', 'singapore': 'sgp'}
            legacy_city_code = city_to_code.get(city_name, 'unk')
        elif extracted_locations and extracted_locations[0].get('type') == 'remote':
            legacy_city_code = 'remote'

        # Insert enriched job with null-safe job_family
        enriched_job_id = insert_enriched_job(
            raw_job_id=raw_job_id,
            employer_name=employer_name,
            title_display=job_title,
            job_family=role.get('job_family') or 'out_of_scope',  # NULL-SAFE
            city_code=legacy_city_code,  # DEPRECATED - use locations instead
            working_arrangement=location.get('working_arrangement') or 'unknown',
            position_type=role.get('position_type') or 'full_time',
            posted_date=date.today(),
            last_seen_date=date.today(),
            # Optional fields
            job_subfamily=role.get('job_subfamily'),
            seniority=role.get('seniority'),
            track=role.get('track'),
            experience_range=role.get('experience_range'),
            employer_department=employer.get('department'),
            employer_size=employer.get('company_size_estimate'),
            is_agency=employer.get('is_agency'),
            agency_confidence=employer.get('agency_confidence'),
            currency=compensation.get('currency'),
            salary_min=compensation.get('base_salary_range', {}).get('min'),
            salary_max=compensation.get('base_salary_range', {}).get('max'),
            equity_eligible=compensation.get('equity_eligible'),
            skills=classification.get('skills', []),
            # Source tracking
            data_source=source,
            description_source=source,
            deduplicated=False,
            locations=extracted_locations  # NEW: Structured location data
        )

        logger.debug(f"Successfully processed job {raw_job_id} -> enriched {enriched_job_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to process job {raw_job_id}: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def backfill_missing_enriched(
    limit: int = None,
    dry_run: bool = False,
    hours_back: int = None
) -> Dict:
    """
    Main backfill function.

    Args:
        limit: Maximum number of jobs to process
        dry_run: If True, only show what would be done
        hours_back: Only process jobs from last N hours

    Returns:
        Statistics about the backfill operation
    """

    logger.info("="*80)
    logger.info("BACKFILL MISSING ENRICHED JOBS")
    logger.info("="*80)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"Limit: {limit or 'None (process all)'}")
    logger.info(f"Time window: {f'Last {hours_back} hours' if hours_back else 'All time'}")
    logger.info("="*80 + "\n")

    # Find missing jobs
    missing_jobs = find_missing_enriched_jobs(hours_back=hours_back, limit=limit)

    if not missing_jobs:
        logger.info("No missing jobs found. Exiting.")
        return {
            'total_missing': 0,
            'processed': 0,
            'successful': 0,
            'failed': 0
        }

    logger.info(f"\nFound {len(missing_jobs)} jobs to process")

    if dry_run:
        logger.info("\nDRY RUN - Would process these jobs:")
        for i, job in enumerate(missing_jobs[:10]):
            logger.info(f"  [{i+1}] ID: {job['id']}, Source: {job.get('source')}, Length: {len(job.get('raw_text', ''))} chars")
        if len(missing_jobs) > 10:
            logger.info(f"  ... and {len(missing_jobs) - 10} more")
        return {
            'total_missing': len(missing_jobs),
            'processed': 0,
            'successful': 0,
            'failed': 0
        }

    # Process jobs
    logger.info("\nProcessing missing jobs...")
    successful = 0
    failed = 0

    for i, job in enumerate(missing_jobs):
        if (i + 1) % 10 == 0:
            logger.info(f"  Progress: {i+1}/{len(missing_jobs)} ({successful} successful, {failed} failed)")

        if process_missing_job(job):
            successful += 1
        else:
            failed += 1

    # Summary
    stats = {
        'total_missing': len(missing_jobs),
        'processed': len(missing_jobs),
        'successful': successful,
        'failed': failed
    }

    logger.info("\n" + "="*80)
    logger.info("BACKFILL COMPLETE")
    logger.info("="*80)
    logger.info(f"Total missing jobs found: {stats['total_missing']}")
    logger.info(f"Successfully processed:    {stats['successful']}")
    logger.info(f"Failed to process:         {stats['failed']}")
    logger.info(f"Success rate:              {100 * stats['successful'] / stats['processed']:.1f}%")
    logger.info("="*80)

    return stats


if __name__ == "__main__":
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

    args = parser.parse_args()

    backfill_missing_enriched(
        limit=args.limit,
        dry_run=args.dry_run,
        hours_back=args.hours
    )
