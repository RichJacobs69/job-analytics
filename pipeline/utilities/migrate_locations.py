"""
Migrate existing city_code data to new locations JSONB structure

Part of: Global Location Expansion Epic - Phase 2
Purpose: Backfill the locations column for all existing enriched_jobs records

Migration strategy:
1. Simple city codes (lon, nyc, den) -> direct mapping
2. Remote jobs -> infer scope from source metadata
3. Unknown jobs -> re-process with location extractor

Usage:
    python pipeline/utilities/migrate_locations.py [--dry-run] [--limit N] [--verbose]

Examples:
    # Dry run to see what would be migrated
    python pipeline/utilities/migrate_locations.py --dry-run --limit 10

    # Migrate all jobs
    python pipeline/utilities/migrate_locations.py

    # Migrate with verbose logging
    python pipeline/utilities/migrate_locations.py --verbose
"""

import os
import sys
import json
import argparse
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from pipeline.location_extractor import get_legacy_city_code_mapping, extract_locations


# =============================================================================
# Migration Logic
# =============================================================================

def migrate_city_code_to_locations(
    city_code: str,
    raw_text: Optional[str] = None,
    adzuna_city: Optional[str] = None,
    adzuna_location: Optional[str] = None,
    lever_location: Optional[str] = None,
    greenhouse_location: Optional[str] = None
) -> List[Dict]:
    """
    Convert a legacy city_code to new locations array.

    Args:
        city_code: Legacy city code (lon, nyc, den, remote, unk)
        raw_text: Raw job text (NOT used - unreliable for location extraction)
        adzuna_city: Adzuna source city from metadata (lon, nyc, den, etc.) for inferring remote scope
        adzuna_location: Adzuna's actual location from API (e.g., "Fort Lee, New Jersey") - reliable
        lever_location: Lever's location field from API (reliable, short string like "London, UK")
        greenhouse_location: Greenhouse's location field from job posting (reliable metadata)

    Returns:
        List of location objects for the locations JSONB column
    """
    legacy_mapping = get_legacy_city_code_mapping()

    # PRIORITY 1: For jobs with location metadata (Adzuna/Lever/Greenhouse), use that as authoritative source
    # These are the actual locations from the job posting, not inferred from search queries
    # Use whichever is available - do NOT fall back to city_code, which may be incorrect
    if adzuna_location:
        return extract_locations(adzuna_location)

    if lever_location:
        return extract_locations(lever_location)

    if greenhouse_location:
        return extract_locations(greenhouse_location)

    # PRIORITY 2: Simple city codes (lon, nyc, den) - only for non-Lever jobs
    # (Lever jobs should have been handled above via lever_location)
    if city_code in ["lon", "nyc", "den"]:
        legacy_loc = legacy_mapping.get(city_code)
        if legacy_loc:
            return [{
                "type": legacy_loc["type"],
                "country_code": legacy_loc["country_code"],
                "city": legacy_loc["city"]
            }]

    # Remote jobs - infer scope from adzuna_city metadata ONLY
    # NOTE: Do NOT extract from raw_text - it's unreliable and causes false positives
    # (raw_text contains company descriptions, office locations, etc. that aren't the job location)
    elif city_code == "remote":
        # Only use adzuna_city if available (from Adzuna API metadata)
        if adzuna_city:
            # adzuna_city from metadata: lon, nyc, den, etc.
            if adzuna_city == "lon":
                return [{
                    "type": "remote",
                    "scope": "country",
                    "country_code": "GB"
                }]
            elif adzuna_city in ["nyc", "den"]:
                return [{
                    "type": "remote",
                    "scope": "country",
                    "country_code": "US"
                }]

        # No reliable metadata - default to global remote (safest assumption)
        return [{
            "type": "remote",
            "scope": "global"
        }]

    # Unknown locations - use adzuna_city metadata
    # NOTE: lever_location is already handled above (PRIORITY 1)
    # NOTE: Do NOT extract from raw_text - it's unreliable and causes false positives
    elif city_code == "unk":
        # Try adzuna_city from Adzuna API metadata
        if adzuna_city:
            legacy_loc = legacy_mapping.get(adzuna_city)
            if legacy_loc:
                return [{
                    "type": legacy_loc["type"],
                    "country_code": legacy_loc["country_code"],
                    "city": legacy_loc["city"]
                }]

        # No reliable metadata - mark as unknown
        # This is the conservative approach to avoid false positives
        return [{"type": "unknown"}]

    # Fallback for unexpected city_code values
    return [{"type": "unknown"}]


# =============================================================================
# Database Operations
# =============================================================================

def fetch_jobs_to_migrate(
    supabase,
    limit: Optional[int] = None,
    offset: int = 0,
    remigrate_all: bool = False
) -> List[Dict]:
    """
    Fetch jobs that need migration.

    Args:
        supabase: Supabase client
        limit: Maximum number of jobs to fetch (None = all)
        offset: Offset for pagination
        remigrate_all: If True, fetch ALL jobs (for re-migration). If False, only fetch jobs with NULL locations.

    Returns:
        List of job records
    """
    query = supabase.table("enriched_jobs").select(
        "id, city_code, raw_job_id"
    )

    if not remigrate_all:
        query = query.is_("locations", "null")

    if limit:
        query = query.limit(limit)

    if offset:
        query = query.range(offset, offset + limit - 1)

    result = query.execute()
    return result.data


def fetch_raw_text(supabase, raw_job_id: str) -> Optional[str]:
    """
    Fetch raw_text from raw_jobs table.

    Args:
        supabase: Supabase client
        raw_job_id: Raw job ID

    Returns:
        Raw text string or None
    """
    result = supabase.table("raw_jobs").select("raw_text").eq("id", raw_job_id).execute()

    if result.data and len(result.data) > 0:
        return result.data[0].get("raw_text")

    return None


def update_job_locations(
    supabase,
    job_id: str,
    locations: List[Dict],
    dry_run: bool = False
) -> bool:
    """
    Update the locations column for a job.

    Args:
        supabase: Supabase client
        job_id: Enriched job ID
        locations: List of location objects
        dry_run: If True, don't actually update

    Returns:
        True if successful
    """
    if dry_run:
        return True

    try:
        supabase.table("enriched_jobs").update({
            "locations": json.dumps(locations)
        }).eq("id", job_id).execute()

        return True
    except Exception as e:
        print(f"Error updating job {job_id}: {e}")
        return False


# =============================================================================
# Migration Statistics
# =============================================================================

class MigrationStats:
    """Track migration statistics"""

    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
        self.by_type = {
            "city": 0,
            "remote_country": 0,
            "remote_unknown": 0,
            "unknown": 0,
            "re_processed": 0,
        }
        self.by_source_city_code = {
            "lon": 0,
            "nyc": 0,
            "den": 0,
            "remote": 0,
            "unk": 0,
        }

    def record_migration(self, city_code: str, locations: List[Dict], was_reprocessed: bool = False):
        """Record a successful migration"""
        self.total += 1
        self.success += 1
        self.by_source_city_code[city_code] = self.by_source_city_code.get(city_code, 0) + 1

        # Categorize the result
        if locations and len(locations) > 0:
            loc_type = locations[0].get("type")

            if loc_type == "city":
                self.by_type["city"] += 1
            elif loc_type == "remote":
                scope = locations[0].get("scope")
                if scope in ["country", "region"]:
                    self.by_type["remote_country"] += 1
                else:
                    self.by_type["remote_unknown"] += 1
            elif loc_type == "unknown":
                self.by_type["unknown"] += 1

            if was_reprocessed:
                self.by_type["re_processed"] += 1

    def record_failure(self):
        """Record a failed migration"""
        self.total += 1
        self.failed += 1

    def print_summary(self):
        """Print migration summary"""
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Total jobs processed: {self.total}")
        print(f"Successfully migrated: {self.success}")
        print(f"Failed: {self.failed}")
        print()
        print("By source city_code:")
        for city_code, count in sorted(self.by_source_city_code.items()):
            print(f"  {city_code:10s}: {count:5d}")
        print()
        print("By result type:")
        for type_name, count in sorted(self.by_type.items()):
            print(f"  {type_name:20s}: {count:5d}")
        print("=" * 60)


# =============================================================================
# Main Migration Function
# =============================================================================

def run_migration(
    dry_run: bool = False,
    limit: Optional[int] = None,
    verbose: bool = False,
    batch_size: int = 100,
    remigrate_all: bool = False
):
    """
    Run the migration from city_code to locations.

    Args:
        dry_run: If True, don't actually update database
        limit: Maximum number of jobs to migrate (None = all)
        verbose: Print detailed progress
        batch_size: Number of jobs to process per batch
        remigrate_all: If True, re-migrate ALL jobs (not just NULL locations)
    """
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("ERROR: Missing Supabase credentials in .env")
        sys.exit(1)

    supabase = create_client(supabase_url, supabase_key)
    stats = MigrationStats()

    print("=" * 60)
    print("LOCATION MIGRATION: city_code -> locations JSONB")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE MIGRATION'}")
    print(f"Re-migrating ALL jobs: {remigrate_all}")
    print(f"Limit: {limit if limit else 'ALL'}")
    print(f"Batch size: {batch_size}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Count total jobs to migrate
    count_query = supabase.table("enriched_jobs").select(
        "id", count="exact"
    )

    if not remigrate_all:
        count_query = count_query.is_("locations", "null")

    count_result = count_query.execute()

    total_to_migrate = count_result.count
    print(f"\nTotal jobs to migrate: {total_to_migrate}")

    if limit:
        total_to_migrate = min(total_to_migrate, limit)

    print(f"Will process: {total_to_migrate}\n")

    # Process in batches
    offset = 0
    processed = 0
    batch_num = 0
    reconnect_interval = 40  # Reconnect every N batches to avoid HTTP2 connection limits

    while processed < total_to_migrate:
        current_batch_size = min(batch_size, total_to_migrate - processed)
        batch_num += 1

        # Reconnect periodically to avoid HTTP2 connection limits
        if batch_num % reconnect_interval == 0:
            print(f"  [Reconnecting to Supabase to avoid connection limits...]")
            supabase = create_client(supabase_url, supabase_key)

        print(f"\nFetching batch {offset // batch_size + 1} (jobs {processed + 1}-{processed + current_batch_size})...")

        # Retry logic for transient connection errors
        max_retries = 3
        for retry in range(max_retries):
            try:
                jobs = fetch_jobs_to_migrate(supabase, limit=current_batch_size, offset=offset, remigrate_all=remigrate_all)
                break
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"  [Retry {retry + 1}/{max_retries}: {str(e)[:50]}...]")
                    supabase = create_client(supabase_url, supabase_key)  # Reconnect
                    continue
                raise

        if not jobs:
            break

        for job in jobs:
            job_id = job["id"]
            city_code = job.get("city_code", "unk")
            raw_job_id = job.get("raw_job_id")

            # Fetch raw job metadata and text
            raw_text = None
            adzuna_city = None
            adzuna_location = None
            lever_location = None
            greenhouse_location = None

            if raw_job_id:
                # Retry logic for raw_jobs fetch
                for retry in range(max_retries):
                    try:
                        raw_result = supabase.table("raw_jobs").select(
                            "raw_text, metadata"
                        ).eq("id", raw_job_id).execute()
                        break
                    except Exception as e:
                        if retry < max_retries - 1:
                            supabase = create_client(supabase_url, supabase_key)
                            continue
                        raw_result = type('obj', (object,), {'data': None})()  # Empty result

                if raw_result.data:
                    raw_data = raw_result.data[0]
                    raw_text = raw_data.get("raw_text")

                    # Extract location metadata from different sources
                    metadata = raw_data.get("metadata") or {}
                    # Handle case where metadata is stored as JSON string
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except (json.JSONDecodeError, TypeError):
                            metadata = {}
                    # Adzuna jobs have {"adzuna_city": "lon"/"nyc"/etc} - search query city (fallback only)
                    adzuna_city = metadata.get("adzuna_city")
                    # Adzuna jobs may also have {"adzuna_location": "Fort Lee, New Jersey"} - actual location from API
                    adzuna_location = metadata.get("adzuna_location")
                    # Lever jobs have {"lever_location": "London, UK"/etc} - reliable API field
                    lever_location = metadata.get("lever_location")
                    # Greenhouse jobs have {"greenhouse_location": "San Francisco, CA"/etc} - reliable metadata
                    greenhouse_location = metadata.get("greenhouse_location")

            # Perform migration
            locations = migrate_city_code_to_locations(city_code, raw_text, adzuna_city, adzuna_location, lever_location, greenhouse_location)

            # Check if we re-processed successfully
            was_reprocessed = (
                city_code == "unk"
                and locations
                and locations[0].get("type") != "unknown"
            )

            # Update database
            success = update_job_locations(supabase, job_id, locations, dry_run)

            if success:
                stats.record_migration(city_code, locations, was_reprocessed)

                if verbose:
                    print(f"  {job_id}: {city_code} -> {locations}")
            else:
                stats.record_failure()

            processed += 1

            # Progress indicator
            if processed % 50 == 0:
                print(f"  Progress: {processed}/{total_to_migrate} ({processed*100//total_to_migrate}%)")

        offset += batch_size

    # Print summary
    stats.print_summary()

    if dry_run:
        print("\n*** DRY RUN COMPLETE - No changes made to database ***")
    else:
        print(f"\n*** MIGRATION COMPLETE - {stats.success} jobs updated ***")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Migrate city_code to locations JSONB column"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making database changes"
    )
    parser.add_argument(
        "--remigrate-all",
        action="store_true",
        help="Re-migrate ALL jobs (not just ones with NULL locations)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of jobs to migrate"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of jobs to process per batch (default: 100)"
    )

    args = parser.parse_args()

    run_migration(
        dry_run=args.dry_run,
        limit=args.limit,
        verbose=args.verbose,
        batch_size=args.batch_size,
        remigrate_all=args.remigrate_all
    )


if __name__ == "__main__":
    main()
