"""
Test inserting Greenhouse jobs into Supabase
"""
import json
from datetime import date, datetime
from db_connection import insert_raw_job, insert_enriched_job, generate_job_hash, test_connection
from classifier import classify_job_with_claude

print("=" * 80)
print("TEST: INSERTING GREENHOUSE JOBS INTO SUPABASE")
print("=" * 80 + "\n")

# Step 1: Test connection
print("[STEP 1] Testing Supabase connection...")
if not test_connection():
    print("[ERROR] Could not connect to Supabase. Check your .env file.")
    exit(1)
print()

# Step 2: Load Greenhouse jobs
print("[STEP 2] Loading Greenhouse jobs...")
try:
    with open('test_greenhouse_jobs.json', 'r', encoding='utf-8') as f:
        jobs = json.load(f)
    print(f"[OK] Loaded {len(jobs)} jobs from test_greenhouse_jobs.json\n")
except Exception as e:
    print(f"[ERROR] Failed to load jobs: {e}")
    exit(1)

# Step 3: Insert first 2 jobs into database
print("[STEP 3] Inserting Greenhouse jobs into database...\n")

for i, job in enumerate(jobs[:2], 1):
    print(f"[Job {i}] {job['title'][:50]}...")

    try:
        # Step 3a: Insert raw job
        raw_job_id = insert_raw_job(
            source='greenhouse',
            posting_url=job['url'],
            raw_text=job['description'],  # Store full description in raw_text
            source_job_id=job.get('job_id')
            # Note: full_text and text_source columns don't exist in schema yet
        )
        print(f"  [OK] Raw job inserted (ID: {raw_job_id})")

        # Step 3b: Classify the job
        classification = classify_job_with_claude(job['description'])
        print(f"  [OK] Job classified")
        print(f"    - Family: {classification.get('role', {}).get('job_family')}")
        print(f"    - Subfamily: {classification.get('role', {}).get('job_subfamily')}")
        print(f"    - Seniority: {classification.get('role', {}).get('seniority')}")

        # Step 3c: Insert enriched job
        role = classification.get('role', {})
        location = classification.get('location', {})
        compensation = classification.get('compensation', {})

        enriched_job_id = insert_enriched_job(
            raw_job_id=raw_job_id,
            employer_name=job['company'],
            title_display=job['title'],
            job_family=role.get('job_family'),
            city_code=location.get('city_code') or 'lon',  # Default to London
            working_arrangement=location.get('working_arrangement') or 'onsite',
            position_type=role.get('position_type') or 'full_time',
            posted_date=date.today(),
            last_seen_date=date.today(),
            # Optional fields
            job_subfamily=role.get('job_subfamily'),
            seniority=role.get('seniority'),
            track=role.get('track'),
            experience_range=role.get('experience_range'),
            currency=compensation.get('currency'),
            salary_min=compensation.get('base_salary_range', {}).get('min'),
            salary_max=compensation.get('base_salary_range', {}).get('max'),
            equity_eligible=compensation.get('equity_eligible'),
            skills=classification.get('skills', []),
            # Data source tracking
            data_source='greenhouse',
            description_source='greenhouse_scraper',
            deduplicated=False
        )
        print(f"  [OK] Enriched job inserted (ID: {enriched_job_id})")

    except Exception as e:
        print(f"  [ERROR] Failed: {str(e)[:100]}")
        import traceback
        traceback.print_exc()

    print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print("\nYou can now check Supabase for the inserted jobs:")
print("- raw_jobs table: Contains the raw job postings")
print("- enriched_jobs table: Contains the classified/enriched jobs")
