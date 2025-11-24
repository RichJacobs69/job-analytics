"""
Test 4: Storage to Supabase
Purpose: Verify we can store <10 classified jobs to Supabase
Two-step process: insert_raw_job() then insert_enriched_job()
"""
import json
import sys
import io
from datetime import date
from time import time
from db_connection import insert_raw_job, insert_enriched_job

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_storage():
    """Test storing classified jobs to Supabase"""

    print("=" * 70)
    print("TEST 4: STORAGE TO SUPABASE")
    print("=" * 70)

    # Load classified results
    print("\n[STEP 1] Loading classified jobs from test_classified_jobs.json...")
    try:
        with open('test_classified_jobs.json', 'r') as f:
            classified_data = json.load(f)
        print(f"[OK] Loaded {len(classified_data)} classified jobs\n")
    except FileNotFoundError:
        print("[ERROR] test_classified_jobs.json not found!")
        print("  Please run test_classify_only.py first\n")
        return

    # Filter out jobs with errors
    valid_jobs = [j for j in classified_data if 'error' not in j]
    error_jobs = [j for j in classified_data if 'error' in j]

    print(f"Filtered results:")
    print(f"  - Valid jobs to store: {len(valid_jobs)}")
    print(f"  - Failed classifications: {len(error_jobs)}\n")

    # Try to store jobs
    print("[STEP 2] Attempting to store jobs to Supabase...")
    stored_count = 0
    storage_errors = 0

    today = date.today()
    test_run_id = str(int(time() * 1000))  # Unique ID for this test run

    for i, job_data in enumerate(valid_jobs, 1):
        try:
            # Skip jobs without job_family (out-of-scope classifications)
            if not job_data.get('job_family'):
                print(f"  [{i}/{len(valid_jobs)}] [SKIP] Out-of-scope job (no job_family): {job_data['company'][:30]}")
                continue

            # STEP 1: Insert raw job first (get raw_job_id)
            # Determine source based on job origin
            job_source = 'adzuna'  # Default to adzuna
            if 'test_' in job_data.get('url', ''):  # Could be from various sources
                job_source = 'manual'  # Use manual for test data

            # Make URLs unique - if empty, generate a test URL
            job_url = job_data.get('url', '').strip()
            if not job_url:
                # Generate unique URL for jobs without URLs
                job_url = f"https://test.example.com/job/{test_run_id}/{i}"
            else:
                # Append test run ID and job index to make existing URLs unique
                job_url = f"{job_url}?test_run={test_run_id}&job_index={i}"

            raw_job_id = insert_raw_job(
                source=job_source,  # 'adzuna' or 'manual' (valid sources)
                posting_url=job_url,
                raw_text=job_data.get('description', ''),  # Full job description
                source_job_id=str(i),
                metadata={
                    'test_batch': 'modular_test_4',
                    'original_company': job_data['company'],
                    'original_title': job_data['title'],
                }
            )

            # Get classification details (with fallback to database defaults where needed)
            full_classification = job_data.get('full_classification', {})
            role = full_classification.get('role', {})
            location = full_classification.get('location', {})

            # STEP 2: Insert enriched job classification
            insert_enriched_job(
                raw_job_id=raw_job_id,
                employer_name=job_data['company'],
                title_display=job_data['title'],
                job_family=job_data['job_family'],  # Required and must be valid enum
                city_code=location.get('city_code') or 'lon',  # Use classification or default
                working_arrangement=job_data.get('working_arrangement', 'onsite'),
                position_type=role.get('position_type', 'full_time'),  # Use from classification
                posted_date=today,
                last_seen_date=today,
                job_subfamily=job_data.get('job_subfamily'),
                track=role.get('track'),  # Track (IC vs Management) is separate from position_type
                seniority=job_data.get('seniority'),
                is_agency=False,
            )

            print(f"  [{i}/{len(valid_jobs)}] [OK] Stored: {job_data['company'][:30]}")
            stored_count += 1

        except Exception as e:
            error_msg = str(e)[:200]  # Capture more of the error message
            print(f"  [{i}/{len(valid_jobs)}] [ERROR] Failed: {error_msg}")
            storage_errors += 1

            # Print first error in detail
            if storage_errors == 1:
                print(f"\n[DEBUG] Full error from first failure:")
                print(f"  {str(e)}\n")

    # Summary
    skipped_out_of_scope = len(valid_jobs) - stored_count - storage_errors
    print("\n" + "=" * 70)
    print("[STEP 3] Storage Summary")
    print("=" * 70)
    print(f"Total jobs attempted: {len(valid_jobs)}")
    print(f"  - Successfully stored: {stored_count}")
    print(f"  - Storage errors: {storage_errors}")
    print(f"  - Skipped (out-of-scope): {skipped_out_of_scope}")
    print(f"  - Storage success rate: {(stored_count/len(valid_jobs)*100 if valid_jobs else 0):.1f}%\n")

    if storage_errors == 0 and stored_count > 0:
        print("=" * 70)
        print("TEST 4 COMPLETE - STORAGE WORKS")
        print("=" * 70)
    else:
        print("[WARNING] Storage had issues - check Supabase connection or schema\n")
        print("Common issues:")
        print("  - Missing SUPABASE_URL or SUPABASE_KEY in .env")
        print("  - Database schema doesn't match (check db_connection.py)")
        print("  - Supabase project inactive or keys expired\n")

if __name__ == '__main__':
    test_storage()
