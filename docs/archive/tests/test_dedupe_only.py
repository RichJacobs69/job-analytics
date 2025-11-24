"""
Test 2: Deduplication (Merge Greenhouse + Adzuna)
Purpose: Verify we can merge <10 Greenhouse jobs with Adzuna jobs
"""
import asyncio
import json
import sys
import io

# Fix Windows charmap encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from scrapers.adzuna.fetch_adzuna_jobs import fetch_adzuna_jobs
from scrapers.greenhouse.greenhouse_scraper import Job as GreenhouseJob
from unified_job_ingester import UnifiedJobIngester

async def test_dedupe():
    """Test deduplication of Greenhouse + Adzuna jobs"""

    print("=" * 70)
    print("TEST 2: DEDUPLICATION (MERGE)")
    print("=" * 70)

    # Load Greenhouse jobs from previous test
    print("\n[STEP 1] Loading Greenhouse jobs from test_greenhouse_jobs.json...")
    try:
        with open('test_greenhouse_jobs.json', 'r') as f:
            gh_data = json.load(f)

        # Convert dicts back to Job objects
        greenhouse_jobs = [
            GreenhouseJob(
                company=j['company'],
                title=j['title'],
                location=j['location'],
                description=j['description'],
                url=j['url'],
                job_id=j.get('job_id'),
            )
            for j in gh_data
        ]
        print(f"[OK] Loaded {len(greenhouse_jobs)} Greenhouse jobs\n")
    except FileNotFoundError:
        print("[ERROR] test_greenhouse_jobs.json not found!")
        print("  Please run test_greenhouse_only.py first\n")
        return

    # Fetch Adzuna jobs (using targeted search strings for product/data roles)
    print("[STEP 2] Fetching Adzuna jobs (London, product/data roles)...")
    try:
        # Use targeted search queries for product and data roles
        search_queries = ['Data Engineer', 'Product Manager']
        adzuna_raw = []

        for query in search_queries:
            print(f"  Fetching: {query}...")
            jobs = fetch_adzuna_jobs('lon', query, results_per_page=3)
            adzuna_raw.extend(jobs)
            print(f"    Found {len(jobs)} jobs")

        # Convert raw Adzuna dicts to Job objects
        adzuna_jobs = []
        for job_data in adzuna_raw:
            adzuna_jobs.append(
                GreenhouseJob(
                    company=job_data.get('company', {}).get('display_name', 'Unknown'),
                    title=job_data.get('title', 'Unknown'),
                    location=job_data.get('location', {}).get('display_name', 'Unspecified'),
                    description=job_data.get('description', ''),
                    url=job_data.get('redirect_url', ''),
                    job_id=str(job_data.get('id', '')),
                )
            )

        print(f"[OK] Fetched {len(adzuna_jobs)} total Adzuna jobs\n")
    except Exception as e:
        print(f"[ERROR] Failed to fetch Adzuna jobs: {e}\n")
        return

    # Run deduplication
    print("[STEP 3] Running deduplication (merge Greenhouse + Adzuna)...")
    ingester = UnifiedJobIngester(verbose=False)
    merged_jobs, stats = await ingester.merge(adzuna_jobs, greenhouse_jobs)

    print(f"[OK] Merge complete:\n")
    print(f"  - Greenhouse input: {len(greenhouse_jobs)}")
    print(f"  - Adzuna input: {len(adzuna_jobs)}")
    print(f"  - Merged total: {len(merged_jobs)}")
    print(f"  - Duplicates removed: {stats['deduplicated']}")
    print(f"  - Dedup rate: {stats['dedup_rate']}")
    print(f"  - Source breakdown:")
    print(f"    - Greenhouse descriptions: {stats['source_breakdown']['greenhouse']}")
    print(f"    - Adzuna descriptions: {stats['source_breakdown']['adzuna']}\n")

    # Save merged jobs for next test
    print("[STEP 4] Saving merged jobs to test_merged_jobs.json...")
    with open('test_merged_jobs.json', 'w') as f:
        merged_dict = [
            {
                'company': j.company,
                'title': j.title,
                'location': j.location,
                'description': j.description,  # Keep full description for classification
                'url': j.url,
                'source': j.source.value if hasattr(j, 'source') else 'unknown',
            }
            for j in merged_jobs
        ]
        json.dump(merged_dict, f, indent=2)

    print(f"[OK] Saved {len(merged_jobs)} merged jobs to test_merged_jobs.json\n")

    print("=" * 70)
    print("TEST 2 COMPLETE - DEDUPLICATION WORKS")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(test_dedupe())
