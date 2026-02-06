"""
Backfill lever_location for existing Lever jobs in raw_jobs table.

Purpose:
    Fetches location data from Lever API for existing jobs and updates
    the metadata field with lever_location.

Usage:
    python pipeline/utilities/backfill_lever_location.py [--dry-run] [--limit N]
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv
from supabase import create_client


# Lever API endpoints
LEVER_API_URLS = {
    "global": "https://api.lever.co/v0/postings",
    "eu": "https://api.eu.lever.co/v0/postings"
}


def fetch_lever_job_location(company_slug: str, job_id: str, instance: str = "global") -> str:
    """
    Fetch location for a single job from Lever API.

    Args:
        company_slug: The company's Lever site slug
        job_id: The Lever job ID
        instance: 'global' or 'eu'

    Returns:
        Location string or empty string if not found
    """
    base_url = LEVER_API_URLS.get(instance, LEVER_API_URLS['global'])
    url = f"{base_url}/{company_slug}/{job_id}"

    headers = {
        'User-Agent': 'job-analytics-bot/1.0',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            return ""  # Job no longer exists

        response.raise_for_status()
        job_data = response.json()

        # Location is in categories
        categories = job_data.get('categories', {})
        return categories.get('location', '')

    except Exception as e:
        print(f"    Error fetching job {job_id}: {e}")
        return ""


def backfill_lever_locations(dry_run: bool = False, limit: int = None, verbose: bool = False):
    """
    Backfill lever_location in metadata for all Lever jobs.

    Args:
        dry_run: If True, don't update database
        limit: Maximum number of jobs to process
        verbose: Print detailed progress
    """
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("ERROR: Missing Supabase credentials in .env")
        sys.exit(1)

    supabase = create_client(supabase_url, supabase_key)

    print("="*70)
    print("LEVER LOCATION BACKFILL")
    print("="*70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print(f"Limit: {limit if limit else 'ALL'}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Get all Lever jobs
    query = supabase.table("raw_jobs").select(
        "id, source_job_id, metadata"
    ).eq("source", "lever")

    if limit:
        query = query.limit(limit)

    result = query.execute()
    lever_jobs = result.data if result.data else []

    print(f"\nFound {len(lever_jobs)} Lever jobs to process\n")

    # Stats
    stats = {
        'total': len(lever_jobs),
        'already_has_location': 0,
        'location_found': 0,
        'location_not_found': 0,
        'updated': 0,
        'errors': 0
    }

    for i, job in enumerate(lever_jobs, 1):
        job_id = job['id']
        source_job_id = job.get('source_job_id', '')
        metadata = job.get('metadata') or {}

        # Check if already has lever_location
        if metadata.get('lever_location'):
            stats['already_has_location'] += 1
            if verbose:
                print(f"[{i}/{len(lever_jobs)}] {job_id}: Already has location: {metadata.get('lever_location')}")
            continue

        # Need company_slug to fetch from API
        company_slug = metadata.get('company_slug')
        lever_instance = metadata.get('lever_instance', 'global')

        if not company_slug or not source_job_id:
            stats['errors'] += 1
            if verbose:
                print(f"[{i}/{len(lever_jobs)}] {job_id}: Missing company_slug or source_job_id")
            continue

        # Fetch location from Lever API
        location = fetch_lever_job_location(company_slug, source_job_id, lever_instance)

        # Rate limit
        time.sleep(0.5)  # 2 requests per second

        if location:
            stats['location_found'] += 1

            # Update metadata
            metadata['lever_location'] = location

            if not dry_run:
                try:
                    supabase.table("raw_jobs").update({
                        "metadata": json.dumps(metadata)
                    }).eq("id", job_id).execute()
                    stats['updated'] += 1
                except Exception as e:
                    print(f"    Error updating {job_id}: {e}")
                    stats['errors'] += 1

            if verbose or i % 50 == 0:
                print(f"[{i}/{len(lever_jobs)}] {job_id}: {location}")
        else:
            stats['location_not_found'] += 1
            if verbose:
                print(f"[{i}/{len(lever_jobs)}] {job_id}: Location not found (job may be removed)")

        # Progress
        if i % 100 == 0:
            print(f"Progress: {i}/{len(lever_jobs)} ({i*100//len(lever_jobs)}%)")

    # Summary
    print("\n" + "="*70)
    print("BACKFILL SUMMARY")
    print("="*70)
    print(f"Total Lever jobs: {stats['total']}")
    print(f"Already had location: {stats['already_has_location']}")
    print(f"Location found from API: {stats['location_found']}")
    print(f"Location not found (removed): {stats['location_not_found']}")
    print(f"Updated in database: {stats['updated']}")
    print(f"Errors: {stats['errors']}")
    print("="*70)

    if dry_run:
        print("\n*** DRY RUN COMPLETE - No changes made ***")
    else:
        print(f"\n*** BACKFILL COMPLETE - {stats['updated']} jobs updated ***")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill lever_location for existing Lever jobs"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making database changes"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of jobs to process"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress"
    )

    args = parser.parse_args()

    backfill_lever_locations(
        dry_run=args.dry_run,
        limit=args.limit,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
