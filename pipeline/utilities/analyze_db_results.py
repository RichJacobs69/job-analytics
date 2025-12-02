"""
Analyze database results for today's pipeline run and overall totals.
Shows breakdown by city and job family.
"""

import sys
sys.path.insert(0, '.')
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
from collections import defaultdict

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

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

    # Breakdown by city - TODAY
    print(f"\n--- Today's Enriched Jobs by City ---")
    for city in ['lon', 'nyc', 'den']:
        city_today = supabase.table("enriched_jobs").select("*", count="exact").eq("city_code", city).gte("classified_at", today_str).execute()
        print(f"  {city.upper()}: {city_today.count:,}")

    # Breakdown by city - OVERALL
    print(f"\n--- Overall Enriched Jobs by City (All Time) ---")
    for city in ['lon', 'nyc', 'den']:
        city_total = supabase.table("enriched_jobs").select("*", count="exact").eq("city_code", city).execute()
        print(f"  {city.upper()}: {city_total.count:,}")

    # ========== JOB FAMILY BREAKDOWN ==========
    print("\n" + "=" * 80)
    print("JOB FAMILY BREAKDOWN (Enriched Jobs)")
    print("=" * 80)

    # Get all enriched jobs from today to analyze
    today_jobs_data = supabase.table("enriched_jobs").select("job_family, city_code").gte("classified_at", today_str).execute()

    # Count by job family - TODAY
    family_counts_today = defaultdict(int)
    family_by_city_today = defaultdict(lambda: defaultdict(int))

    for job in today_jobs_data.data:
        family = job.get('job_family') or 'unknown'
        city = job.get('city_code') or 'unknown'
        family_counts_today[family] += 1
        family_by_city_today[family][city] += 1

    print(f"\n--- Today's Jobs by Family ({today_str}) ---")
    for family in sorted(family_counts_today.keys()):
        print(f"  {family}: {family_counts_today[family]:,}")
        for city in ['lon', 'nyc', 'den']:
            if city in family_by_city_today[family]:
                print(f"    - {city.upper()}: {family_by_city_today[family][city]:,}")

    # Get all enriched jobs (all time) to analyze
    all_jobs_data = supabase.table("enriched_jobs").select("job_family, city_code").execute()

    # Count by job family - OVERALL
    family_counts_all = defaultdict(int)
    family_by_city_all = defaultdict(lambda: defaultdict(int))

    for job in all_jobs_data.data:
        family = job.get('job_family') or 'unknown'
        city = job.get('city_code') or 'unknown'
        family_counts_all[family] += 1
        family_by_city_all[family][city] += 1

    print(f"\n--- Overall Jobs by Family (All Time) ---")
    for family in sorted(family_counts_all.keys()):
        print(f"  {family}: {family_counts_all[family]:,}")
        for city in ['lon', 'nyc', 'den']:
            if city in family_by_city_all[family]:
                print(f"    - {city.upper()}: {family_by_city_all[family][city]:,}")

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

if __name__ == "__main__":
    analyze_database()
