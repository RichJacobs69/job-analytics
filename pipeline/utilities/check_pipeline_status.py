#!/usr/bin/env python3
"""
Quick status check for the job classification pipeline.

Shows:
- Total jobs ingested (raw_jobs table)
- Total jobs classified (enriched_jobs table)
- Classification rate
- Breakdown by city
- Recent activity

Usage:
    python check_pipeline_status.py
"""

import sys
sys.path.insert(0, '.')
from pipeline.db_connection import supabase
from datetime import datetime, timedelta


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

        # Breakdown by city (enriched jobs) - paginate through all results
        # Supabase API limits to 1,000 per request, so we need to paginate
        city_counts = {}
        null_count = 0
        rows_fetched = 0
        offset = 0
        page_size = 1000

        while True:
            city_response = supabase.table('enriched_jobs').select(
                'city_code'
            ).range(offset, offset + page_size - 1).execute()

            if not city_response.data:
                break

            rows_fetched += len(city_response.data)

            for job in city_response.data:
                city = job.get('city_code')
                if city is None:
                    null_count += 1
                else:
                    city_counts[city] = city_counts.get(city, 0) + 1

            # If we got fewer rows than page_size, we're done
            if len(city_response.data) < page_size:
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
            'city_counts': city_counts,
            'null_city_count': null_count,
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

    # By city - show with sum check
    if status['city_counts']:
        print(f"\nClassified Jobs by City:")
        city_sum = 0
        for city in sorted(status['city_counts'].keys()):
            count = status['city_counts'][city]
            city_sum += count
            print(f"  {city.upper():10} {count:,}")

        # Show if there are jobs without a city
        if status['null_city_count'] > 0:
            print(f"  NO CITY   {status['null_city_count']:,}  [MISSING CITY_CODE]")
            city_sum += status['null_city_count']

        # Verify sum matches total
        print(f"  {'-' * 20}")
        print(f"  TOTAL     {city_sum:,}", end="")
        if city_sum == enriched:
            print("  [OK]")
        else:
            missing = enriched - city_sum
            print(f"  [ERROR: {missing:,} jobs missing city_code]")

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
