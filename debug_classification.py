"""
Debug script to test classification on real Adzuna jobs
"""
import json
from scrapers.adzuna.fetch_adzuna_jobs import fetch_adzuna_jobs, format_job_for_classification
from classifier import classify_job_with_claude

# Fetch one job from Adzuna
print("Fetching jobs from Adzuna (London)...")
jobs = fetch_adzuna_jobs('lon', 'data scientist', 1)

if not jobs:
    print("No jobs fetched!")
    exit(1)

print(f"Fetched {len(jobs)} jobs\n")

for i, job in enumerate(jobs[:3], 1):
    print("=" * 70)
    print(f"JOB {i}: {job['title']}")
    print("=" * 70)

    # Format job for classification
    job_text = format_job_for_classification(job)
    print(f"Formatted text length: {len(job_text)} chars")
    print(f"First 200 chars:\n{job_text[:200]}\n")

    # Try to classify
    try:
        result = classify_job_with_claude(job_text)
        print(f"[SUCCESS] Classification successful")
        print(f"  - Job family: {result.get('role', {}).get('job_family')}")
        print(f"  - Seniority: {result.get('role', {}).get('seniority')}")
        print(f"  - Skills count: {len(result.get('skills', []))}")
    except Exception as e:
        print(f"[FAILED] Classification failed: {type(e).__name__}: {str(e)[:100]}")
        import traceback
        traceback.print_exc()

    print()
