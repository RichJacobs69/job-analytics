#!/usr/bin/env python3
"""
Quick status check for the job classification pipeline.

Shows:
- Total jobs ingested (raw_jobs table)
- Total jobs classified (enriched_jobs table)
- Classification rate
- Breakdown by location (extracted from locations JSONB)
- Recent activity

Updated 2025-12-21: Now uses `locations` JSONB column instead of deprecated `city_code`.
See: docs/architecture/GLOBAL_LOCATION_EXPANSION_EPIC.md

Usage:
    python check_pipeline_status.py
"""

import sys
import json
sys.path.insert(0, '.')
from pipeline.db_connection import supabase
from datetime import datetime, timedelta


def extract_primary_city(locations) -> str:
    """Extract primary city from locations JSONB for display purposes."""
    if not locations:
        return 'unknown'
    if isinstance(locations, str):
        try:
            locations = json.loads(locations)
        except (json.JSONDecodeError, TypeError):
            return 'unknown'
    if not isinstance(locations, list) or len(locations) == 0:
        return 'unknown'

    first_loc = locations[0]
    loc_type = first_loc.get('type', 'unknown')

    if loc_type == 'city':
        return first_loc.get('city', 'unknown')
    elif loc_type == 'remote':
        scope = first_loc.get('scope', 'global')
        country = first_loc.get('country_code', '')
        return f"remote_{country.lower()}" if country else 'remote_global'
    elif loc_type == 'country':
        return first_loc.get('country_code', 'unknown').lower()
    else:
        return 'unknown'


def format_timestamp(ts):
    """Format timestamp for display."""
    if not ts:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(ts)[:19]


def get_status():
    """Fetch pipeline status from database."""
    try:
        # Total counts
        raw_response = supabase.table('raw_jobs').select('count', count='exact').execute()
        enriched_response = supabase.table('enriched_jobs').select('count', count='exact').execute()

        raw_count = raw_response.count if raw_response.count is not None else 0
        enriched_count = enriched_response.count if enriched_response.count is not None else 0

        # Breakdown by location (enriched jobs) - paginate through all results
        # Supabase API limits to 1,000 per request, so we need to paginate
        # Uses locations JSONB column instead of deprecated city_code
        location_counts = {}
        unknown_count = 0
        rows_fetched = 0
        offset = 0
        page_size = 1000

        while True:
            location_response = supabase.table('enriched_jobs').select(
                'locations'
            ).range(offset, offset + page_size - 1).execute()

            if not location_response.data:
                break

            rows_fetched += len(location_response.data)

            for job in location_response.data:
                location = extract_primary_city(job.get('locations'))
                if location == 'unknown':
                    unknown_count += 1
                else:
                    location_counts[location] = location_counts.get(location, 0) + 1

            # If we got fewer rows than page_size, we're done
            if len(location_response.data) < page_size:
                break

            offset += page_size

        # Recent activity (last enriched job)
        recent_response = supabase.table('enriched_jobs').select(
            'posted_date'
        ).order('posted_date', desc=True).limit(1).execute()

        last_job_time = None
        if recent_response.data:
            last_job_time = recent_response.data[0].get('posted_date')

        # By source - paginate through all results
        # Supabase API limits to 1,000 per request, so we need to paginate
        source_counts = {}
        null_source_count = 0
        offset = 0

        while True:
            source_response = supabase.table('raw_jobs').select(
                'source'
            ).range(offset, offset + page_size - 1).execute()

            if not source_response.data:
                break

            for job in source_response.data:
                source = job.get('source')
                if source is None:
                    null_source_count += 1
                else:
                    source_counts[source] = source_counts.get(source, 0) + 1

            # If we got fewer rows than page_size, we're done
            if len(source_response.data) < page_size:
                break

            offset += page_size

        return {
            'raw_count': raw_count,
            'enriched_count': enriched_count,
            'location_counts': location_counts,
            'unknown_location_count': unknown_count,
            'last_job_time': last_job_time,
            'source_counts': source_counts,
            'null_source_count': null_source_count,
            'rows_fetched': rows_fetched,
        }
    except Exception as e:
        print(f"Error querying database: {e}", file=sys.stderr)
        return None


def main():
    print("\n" + "="*60)
    print("PIPELINE STATUS CHECK")
    print("="*60 + "\n")

    status = get_status()
    if not status:
        print("Failed to retrieve status. Check your database connection.")
        return

    raw = status['raw_count']
    enriched = status['enriched_count']
    pending = raw - enriched
    rows_fetched = status.get('rows_fetched', 0)

    # Main metrics
    print(f"Raw Jobs Ingested:        {raw:,}")
    print(f"Jobs Classified:          {enriched:,}")
    print(f"Rows Fetched for breakdown: {rows_fetched:,}  (total count={enriched:,})")
    print(f"Pending Classification:   {pending:,}")
    print(f"\n  (Pending = raw jobs not yet in enriched_jobs)")
    print(f"   Could be: in-progress, failed, or not yet started")

    if raw > 0:
        rate = (enriched / raw) * 100
        print(f"\nClassification Rate:      {rate:.1f}%")

    # By location - show with sum check (extracted from locations JSONB)
    if status['location_counts']:
        print(f"\nClassified Jobs by Location:")
        location_sum = 0
        # Sort by count descending to show most common locations first
        sorted_locations = sorted(status['location_counts'].items(), key=lambda x: -x[1])
        for location, count in sorted_locations:
            location_sum += count
            print(f"  {location:20} {count:,}")

        # Show if there are jobs with unknown location
        if status['unknown_location_count'] > 0:
            print(f"  {'unknown':20} {status['unknown_location_count']:,}  [LOCATION NOT PARSED]")
            location_sum += status['unknown_location_count']

        # Verify sum matches total
        print(f"  {'-' * 30}")
        print(f"  {'TOTAL':20} {location_sum:,}", end="")
        if location_sum == enriched:
            print("  [OK]")
        else:
            missing = enriched - location_sum
            print(f"  [ERROR: {missing:,} jobs missing location]")

    # By source - with sum check
    if status['source_counts'] or status['null_source_count'] > 0:
        print(f"\nRaw Jobs by Source:")
        source_sum = 0
        for source in sorted(status['source_counts'].keys()):
            count = status['source_counts'][source]
            source_sum += count
            print(f"  {source:15} {count:,}")

        # Show if there are jobs without a source
        if status['null_source_count'] > 0:
            print(f"  NO SOURCE {status['null_source_count']:,}  [MISSING SOURCE]")
            source_sum += status['null_source_count']

        print(f"  {'-' * 20}")
        print(f"  {'TOTAL':15} {source_sum:,}", end="")
        if source_sum == raw:
            print("  [OK]")
        else:
            missing = raw - source_sum
            print(f"  [ERROR: {missing:,} jobs missing source]")

    # Recent activity
    if status['last_job_time']:
        last_time = format_timestamp(status['last_job_time'])
        print(f"\nMost Recent Job Posted: {last_time}")

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
