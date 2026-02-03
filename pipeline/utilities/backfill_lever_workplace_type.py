"""
Backfill lever_workplace_type for existing Lever jobs.

Purpose:
    Fetches workplaceType from Lever API for existing jobs and updates:
    1. raw_jobs.metadata with lever_workplace_type
    2. enriched_jobs.working_arrangement with the correct value

Usage:
    python pipeline/utilities/backfill_lever_workplace_type.py [--dry-run] [--limit N]
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


def fetch_lever_job_workplace_type(company_slug: str, job_id: str, instance: str = "global") -> str:
    """
    Fetch workplaceType for a single job from Lever API.

    Args:
        company_slug: The company's Lever site slug
        job_id: The Lever job ID
        instance: 'global' or 'eu'

    Returns:
        workplaceType string (onsite/hybrid/remote/unspecified) or empty string if not found
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

        # workplaceType is a top-level field
        return job_data.get('workplaceType', '')

    except Exception as e:
        print(f"    Error fetching job {job_id}: {e}")
        return ""


def backfill_lever_workplace_type(dry_run: bool = False, limit: int = None, verbose: bool = False):
    """
    Backfill lever_workplace_type for all Lever jobs.

    Updates both raw_jobs.metadata and enriched_jobs.working_arrangement.

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
    print("LEVER WORKPLACE TYPE BACKFILL")
    print("="*70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print(f"Limit: {limit if limit else 'ALL'}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Get all Lever jobs from enriched_jobs with their raw_job data
    # We need to paginate since there could be many jobs
    all_jobs = []
    offset = 0
    batch_size = 1000

    while True:
        query = supabase.table("enriched_jobs").select(
            "id, raw_job_id, working_arrangement"
        ).eq("data_source", "lever").range(offset, offset + batch_size - 1)

        if limit and offset + batch_size > limit:
            query = query.limit(limit - offset)

        result = query.execute()
        batch = result.data if result.data else []

        if not batch:
            break

        all_jobs.extend(batch)
        offset += len(batch)

        if limit and len(all_jobs) >= limit:
            all_jobs = all_jobs[:limit]
            break

        if len(batch) < batch_size:
            break

    print(f"\nFound {len(all_jobs)} Lever jobs in enriched_jobs to process")

    # Get raw_jobs data for these jobs (need metadata with company_slug)
    raw_job_ids = [j['raw_job_id'] for j in all_jobs if j.get('raw_job_id')]

    print(f"Fetching raw_jobs metadata for {len(raw_job_ids)} jobs...")

    raw_jobs_map = {}
    for i in range(0, len(raw_job_ids), 100):
        batch_ids = raw_job_ids[i:i+100]
        result = supabase.table("raw_jobs").select(
            "id, source_job_id, metadata"
        ).in_("id", batch_ids).execute()

        for rj in (result.data or []):
            raw_jobs_map[rj['id']] = rj

    print(f"Found {len(raw_jobs_map)} matching raw_jobs records\n")

    # Stats
    stats = {
        'total': len(all_jobs),
        'already_has_workplace_type': 0,
        'workplace_type_found': 0,
        'workplace_type_not_found': 0,
        'raw_updated': 0,
        'enriched_updated': 0,
        'errors': 0,
        'by_type': {'onsite': 0, 'hybrid': 0, 'remote': 0, 'unspecified': 0}
    }

    for i, enriched_job in enumerate(all_jobs, 1):
        enriched_id = enriched_job['id']
        raw_job_id = enriched_job.get('raw_job_id')
        current_wa = enriched_job.get('working_arrangement', 'unknown')

        if not raw_job_id or raw_job_id not in raw_jobs_map:
            stats['errors'] += 1
            if verbose:
                print(f"[{i}/{len(all_jobs)}] {enriched_id}: No matching raw_job found")
            continue

        raw_job = raw_jobs_map[raw_job_id]
        source_job_id = raw_job.get('source_job_id', '')
        metadata = raw_job.get('metadata') or {}

        # Parse metadata if it's a JSON string
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}

        # Check if already has lever_workplace_type in metadata
        existing_wt = metadata.get('lever_workplace_type')
        if existing_wt:
            stats['already_has_workplace_type'] += 1
            if verbose:
                print(f"[{i}/{len(all_jobs)}] {enriched_id}: Already has workplace_type: {existing_wt}")
            continue

        # Need company_slug to fetch from API
        company_slug = metadata.get('company_slug')
        lever_instance = metadata.get('lever_instance', 'global')

        if not company_slug or not source_job_id:
            stats['errors'] += 1
            if verbose:
                print(f"[{i}/{len(all_jobs)}] {enriched_id}: Missing company_slug or source_job_id")
            continue

        # Fetch workplace_type from Lever API
        workplace_type = fetch_lever_job_workplace_type(company_slug, source_job_id, lever_instance)

        # Rate limit - 2 requests per second
        time.sleep(0.5)

        if workplace_type:
            stats['workplace_type_found'] += 1
            stats['by_type'][workplace_type] = stats['by_type'].get(workplace_type, 0) + 1

            # Update metadata in raw_jobs
            metadata['lever_workplace_type'] = workplace_type

            # Determine new working_arrangement
            # Only update if Lever provides a specific type (not 'unspecified')
            new_wa = current_wa
            if workplace_type in ('onsite', 'hybrid', 'remote'):
                new_wa = workplace_type

            if not dry_run:
                try:
                    # Update raw_jobs metadata
                    supabase.table("raw_jobs").update({
                        "metadata": metadata
                    }).eq("id", raw_job_id).execute()
                    stats['raw_updated'] += 1

                    # Update enriched_jobs working_arrangement if changed
                    if new_wa != current_wa:
                        supabase.table("enriched_jobs").update({
                            "working_arrangement": new_wa
                        }).eq("id", enriched_id).execute()
                        stats['enriched_updated'] += 1

                except Exception as e:
                    print(f"    Error updating {enriched_id}: {e}")
                    stats['errors'] += 1

            if verbose or i % 50 == 0:
                if new_wa != current_wa:
                    print(f"[{i}/{len(all_jobs)}] {enriched_id}: {current_wa} -> {new_wa}")
                else:
                    print(f"[{i}/{len(all_jobs)}] {enriched_id}: {workplace_type} (no change)")
        else:
            stats['workplace_type_not_found'] += 1
            if verbose:
                print(f"[{i}/{len(all_jobs)}] {enriched_id}: Job not found on Lever (may be removed)")

        # Progress
        if i % 100 == 0:
            print(f"Progress: {i}/{len(all_jobs)} ({i*100//len(all_jobs)}%)")

    # Summary
    print("\n" + "="*70)
    print("BACKFILL SUMMARY")
    print("="*70)
    print(f"Total Lever jobs: {stats['total']}")
    print(f"Already had workplace_type: {stats['already_has_workplace_type']}")
    print(f"Workplace type found from API: {stats['workplace_type_found']}")
    print(f"  - onsite: {stats['by_type'].get('onsite', 0)}")
    print(f"  - hybrid: {stats['by_type'].get('hybrid', 0)}")
    print(f"  - remote: {stats['by_type'].get('remote', 0)}")
    print(f"  - unspecified: {stats['by_type'].get('unspecified', 0)}")
    print(f"Job not found (removed from Lever): {stats['workplace_type_not_found']}")
    print(f"raw_jobs updated: {stats['raw_updated']}")
    print(f"enriched_jobs updated: {stats['enriched_updated']}")
    print(f"Errors: {stats['errors']}")
    print("="*70)

    if dry_run:
        print("\n*** DRY RUN COMPLETE - No changes made ***")
    else:
        print(f"\n*** BACKFILL COMPLETE ***")
        print(f"  - {stats['raw_updated']} raw_jobs metadata updated")
        print(f"  - {stats['enriched_updated']} enriched_jobs working_arrangement updated")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill lever_workplace_type for existing Lever jobs"
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

    backfill_lever_workplace_type(
        dry_run=args.dry_run,
        limit=args.limit,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
