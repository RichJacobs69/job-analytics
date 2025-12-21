"""
Analyze database results for today's pipeline run and overall totals.
Shows comprehensive breakdown by all dimensions in enriched_jobs table.

Updated 2025-12-21: Now uses `locations` JSONB column instead of deprecated `city_code`.
See: docs/architecture/GLOBAL_LOCATION_EXPANSION_EPIC.md
"""

import sys
sys.path.insert(0, '.')
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
from collections import defaultdict
import pandas as pd
from tabulate import tabulate


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

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

def analyze_enriched_jobs_dimensions():
    """Analyze all dimensions in enriched_jobs table and create tabulated breakdowns."""

    print("\n" + "=" * 100)
    print("COMPREHENSIVE ENRICHED JOBS DIMENSION ANALYSIS")
    print("=" * 100)

    # Get all enriched jobs data using pagination
    print("Fetching ALL enriched jobs data using pagination...")
    all_data = []
    page_size = 1000
    offset = 0

    while True:
        jobs_page = supabase.table("enriched_jobs").select(
            "locations, job_family, job_subfamily, seniority, working_arrangement, "
            "data_source, description_source, deduplicated"
        ).range(offset, offset + page_size - 1).execute()

        if not jobs_page.data:
            break

        all_data.extend(jobs_page.data)
        offset += page_size

        print(f"Fetched {len(all_data)} records so far...")

        # Safety check to prevent infinite loops
        if len(jobs_page.data) < page_size:
            break

    print(f"Total records fetched: {len(all_data)}")
    all_jobs = type('obj', (object,), {'data': all_data})

    if not all_jobs.data:
        print("No enriched jobs data found!")
        return

    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(all_jobs.data)
    total_jobs = len(df)

    # Extract primary city from locations JSONB for analysis
    df['location_city'] = df['locations'].apply(extract_primary_city)

    print(f"\nTotal enriched jobs analyzed: {total_jobs:,}")
    print("\n" + "-" * 100)

    # Define dimensions to analyze
    dimensions = [
        ('location_city', 'Location (from JSONB)'),
        ('job_family', 'Job Family'),
        ('job_subfamily', 'Job Subfamily'),
        ('seniority', 'Seniority Level'),
        ('working_arrangement', 'Working Arrangement'),
        ('data_source', 'Data Source'),
        ('description_source', 'Description Source'),
        ('deduplicated', 'Deduplicated')
    ]

    # Analyze each dimension
    for column, display_name in dimensions:
        if column not in df.columns:
            print(f"\n⚠️  Warning: Column '{column}' not found in data")
            continue

        print(f"\n{chr(9654)} {display_name} Breakdown")
        print("-" * 50)

        # Get value counts
        counts = df[column].value_counts(dropna=False)
        percentages = (counts / total_jobs * 100).round(2)

        # Create table data
        table_data = []
        for value, count in counts.items():
            # Handle None/NaN values
            display_value = str(value) if pd.notna(value) else 'NULL/None'
            table_data.append([
                display_value,
                f"{count:,}",
                f"{percentages[value]:.2f}%"
            ])

        # Print tabulated results
        headers = ['Value', 'Count', 'Percentage']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))

        # Summary stats
        unique_values = counts.count()
        most_common = counts.index[0] if len(counts) > 0 else 'N/A'
        most_common_count = counts.iloc[0] if len(counts) > 0 else 0

        print(f"\nSummary: {unique_values} unique values, most common: '{most_common}' ({most_common_count:,} jobs)")

    print("\n" + "=" * 100)
    print("CROSS-DIMENSION ANALYSIS")
    print("=" * 100)

    # Cross-analysis: Job Family by Location
    print(f"\n{chr(9654)} Job Family by Location")
    print("-" * 30)
    cross_city_family = pd.crosstab(df['location_city'], df['job_family'], margins=True)
    print(tabulate(cross_city_family, headers='keys', tablefmt='grid'))

    # Cross-analysis: Seniority by Job Family
    print(f"\n{chr(9654)} Seniority by Job Family")
    print("-" * 30)
    cross_family_seniority = pd.crosstab(df['job_family'], df['seniority'], margins=True)
    print(tabulate(cross_family_seniority, headers='keys', tablefmt='grid'))

    # Cross-analysis: Working Arrangement by Location
    print(f"\n{chr(9654)} Working Arrangement by Location")
    print("-" * 35)
    cross_city_arrangement = pd.crosstab(df['location_city'], df['working_arrangement'], margins=True)
    print(tabulate(cross_city_arrangement, headers='keys', tablefmt='grid'))

    # Data Source Analysis
    print(f"\n{chr(9654)} Data Source Quality Analysis")
    print("-" * 35)

    # Deduplication analysis
    dedup_by_source = pd.crosstab(df['data_source'], df['deduplicated'], margins=True)
    print("Deduplication by Data Source:")
    print(tabulate(dedup_by_source, headers='keys', tablefmt='grid'))

    # Description source analysis
    if 'description_source' in df.columns:
        desc_source_by_data_source = pd.crosstab(df['data_source'], df['description_source'], margins=True)
        print("\nDescription Source by Data Source:")
        print(tabulate(desc_source_by_data_source, headers='keys', tablefmt='grid'))

    print("\n" + "=" * 100)

def analyze_database():
    """Analyze database for today's run and overall totals."""

    # Get today's date (start of day)
    today = datetime.now().date()
    today_str = today.isoformat()

    print("=" * 80)
    print("DATABASE ANALYSIS - ADZUNA PIPELINE RESULTS")
    print("=" * 80)
    print(f"Analysis Date: {today}")
    print()

    # ========== RAW JOBS ANALYSIS ==========
    print("=" * 80)
    print("RAW JOBS TABLE")
    print("=" * 80)

    # Total raw jobs (all time)
    total_raw = supabase.table("raw_jobs").select("*", count="exact").execute()
    total_raw_count = total_raw.count

    # Raw jobs from today
    today_raw = supabase.table("raw_jobs").select("*", count="exact").gte("scraped_at", today_str).execute()
    today_raw_count = today_raw.count

    print(f"\nTODAY'S RUN ({today_str}):")
    print(f"  New raw jobs added: {today_raw_count:,}")
    print(f"\nOVERALL TOTALS (All Time):")
    print(f"  Total raw jobs: {total_raw_count:,}")

    # Note: raw_jobs table doesn't have city_code column
    # City breakdown only available in enriched_jobs table

    # ========== ENRICHED JOBS ANALYSIS ==========
    print("\n" + "=" * 80)
    print("ENRICHED JOBS TABLE")
    print("=" * 80)

    # Total enriched jobs (all time)
    total_enriched = supabase.table("enriched_jobs").select("*", count="exact").execute()
    total_enriched_count = total_enriched.count

    # Enriched jobs from today
    today_enriched = supabase.table("enriched_jobs").select("*", count="exact").gte("classified_at", today_str).execute()
    today_enriched_count = today_enriched.count

    print(f"\nTODAY'S RUN ({today_str}):")
    print(f"  New enriched jobs added: {today_enriched_count:,}")
    print(f"\nOVERALL TOTALS (All Time):")
    print(f"  Total enriched jobs: {total_enriched_count:,}")

    # Note: City breakdowns now use locations JSONB column
    # Detailed location analysis is available in the CROSS-DIMENSION ANALYSIS section
    print(f"\n--- Location breakdowns available in dimension analysis below ---")

    # ========== JOB FAMILY BREAKDOWN ==========
    print("\n" + "=" * 80)
    print("JOB FAMILY BREAKDOWN (Enriched Jobs)")
    print("=" * 80)

    # Get all enriched jobs from today to analyze (using locations JSONB)
    today_jobs_data = supabase.table("enriched_jobs").select("job_family, locations").gte("classified_at", today_str).execute()

    # Count by job family - TODAY
    family_counts_today = defaultdict(int)
    family_by_location_today = defaultdict(lambda: defaultdict(int))

    for job in today_jobs_data.data:
        family = job.get('job_family') or 'unknown'
        location = extract_primary_city(job.get('locations'))
        family_counts_today[family] += 1
        family_by_location_today[family][location] += 1

    print(f"\n--- Today's Jobs by Family ({today_str}) ---")
    for family in sorted(family_counts_today.keys()):
        print(f"  {family}: {family_counts_today[family]:,}")
        # Show top locations for each family
        locations_sorted = sorted(family_by_location_today[family].items(), key=lambda x: -x[1])
        for loc, count in locations_sorted[:5]:
            print(f"    - {loc}: {count:,}")

    # Get all enriched jobs (all time) to analyze - using pagination
    all_jobs_data = []
    offset = 0
    page_size = 1000
    while True:
        batch = supabase.table("enriched_jobs").select("job_family, locations").range(offset, offset + page_size - 1).execute()
        if not batch.data:
            break
        all_jobs_data.extend(batch.data)
        if len(batch.data) < page_size:
            break
        offset += page_size

    # Count by job family - OVERALL
    family_counts_all = defaultdict(int)
    family_by_location_all = defaultdict(lambda: defaultdict(int))

    for job in all_jobs_data:
        family = job.get('job_family') or 'unknown'
        location = extract_primary_city(job.get('locations'))
        family_counts_all[family] += 1
        family_by_location_all[family][location] += 1

    print(f"\n--- Overall Jobs by Family (All Time) ---")
    for family in sorted(family_counts_all.keys()):
        print(f"  {family}: {family_counts_all[family]:,}")
        # Show top locations for each family
        locations_sorted = sorted(family_by_location_all[family].items(), key=lambda x: -x[1])
        for loc, count in locations_sorted[:5]:
            print(f"    - {loc}: {count:,}")

    # ========== DATA SOURCE BREAKDOWN ==========
    print("\n" + "=" * 80)
    print("DATA SOURCE BREAKDOWN (Enriched Jobs)")
    print("=" * 80)

    # Today's breakdown
    adzuna_today = supabase.table("enriched_jobs").select("*", count="exact").eq("data_source", "adzuna").gte("classified_at", today_str).execute()
    greenhouse_today = supabase.table("enriched_jobs").select("*", count="exact").eq("data_source", "greenhouse").gte("classified_at", today_str).execute()

    print(f"\nTODAY'S RUN ({today_str}):")
    print(f"  Adzuna: {adzuna_today.count:,}")
    print(f"  Greenhouse: {greenhouse_today.count:,}")

    # Overall breakdown
    adzuna_all = supabase.table("enriched_jobs").select("*", count="exact").eq("data_source", "adzuna").execute()
    greenhouse_all = supabase.table("enriched_jobs").select("*", count="exact").eq("data_source", "greenhouse").execute()

    print(f"\nOVERALL (All Time):")
    print(f"  Adzuna: {adzuna_all.count:,}")
    print(f"  Greenhouse: {greenhouse_all.count:,}")

    # ========== SUMMARY ==========
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nToday's Pipeline Run Success:")
    print(f"  Raw jobs ingested: {today_raw_count:,}")
    print(f"  Jobs classified: {today_enriched_count:,}")
    if today_raw_count > 0:
        classification_rate = (today_enriched_count / today_raw_count) * 100
        print(f"  Classification rate: {classification_rate:.1f}%")

    print(f"\nCumulative Database Totals:")
    print(f"  Total raw jobs: {total_raw_count:,}")
    print(f"  Total enriched jobs: {total_enriched_count:,}")
    if total_raw_count > 0:
        overall_rate = (total_enriched_count / total_raw_count) * 100
        print(f"  Overall classification rate: {overall_rate:.1f}%")

    print("\n" + "=" * 80)

    # Run comprehensive dimension analysis
    analyze_enriched_jobs_dimensions()

if __name__ == "__main__":
    analyze_database()
