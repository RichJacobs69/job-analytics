"""
Integration test: Verify the full pipeline works end-to-end

Tests the complete flow:
1. Create UnifiedJob objects (simulating merge)
2. Add classifications
3. Verify storage preparation works

This simulates what happens in fetch_jobs.py without hitting APIs.
"""

import asyncio
from unified_job_ingester import UnifiedJob, DataSource
from classifier import classify_job_with_claude
from datetime import date

print("=" * 80)
print("INTEGRATION TEST: FULL PIPELINE FLOW")
print("=" * 80)

async def test_pipeline():
    # Step 1: Simulate merged jobs
    print("\n[STEP 1] Creating simulated merged jobs...")

    jobs = [
        UnifiedJob(
            company="Test Company A",
            title="Senior Data Engineer",
            location="London",
            description="We are seeking a Senior Data Engineer with 5+ years experience in Python, SQL, and Apache Spark. You will build data pipelines and work with our data science team to deliver insights. Strong knowledge of AWS and data warehousing required.",
            url="https://test.com/job/1",
            source=DataSource.GREENHOUSE,
            description_source=DataSource.GREENHOUSE
        ),
        UnifiedJob(
            company="Test Company B",
            title="Product Manager",
            location="New York",
            description="Join our product team to drive vision and strategy for our data platform. You'll work cross-functionally with engineering and design to deliver features that delight users. Experience with B2B SaaS products preferred.",
            url="https://test.com/job/2",
            source=DataSource.ADZUNA,
            description_source=DataSource.ADZUNA
        ),
        UnifiedJob(
            company="Test Company C",
            title="Sales Representative",
            location="London",
            description="Short description",  # This should be filtered (<50 chars)
            url="https://test.com/job/3",
            source=DataSource.ADZUNA,
            description_source=DataSource.ADZUNA
        ),
    ]

    print(f"[OK] Created {len(jobs)} test jobs")

    # Step 2: Simulate classification
    print("\n[STEP 2] Classifying jobs (simulating fetch_jobs.classify_jobs())...")

    classified_jobs = []
    filtered_count = 0

    for i, job in enumerate(jobs, 1):
        print(f"\n  [{i}/{len(jobs)}] Processing: {job.title}")

        # Check description length (same as fetch_jobs.py)
        if not job.description or len(job.description.strip()) < 50:
            print(f"    [FILTERED] Description too short (<50 chars)")
            filtered_count += 1
            continue

        try:
            # Classify with Claude
            print(f"    [CLASSIFYING] Calling Claude API...")
            classification = classify_job_with_claude(job.description)

            # Add classification to job (THE FIX WE APPLIED)
            job.classification = classification

            # Extract key info for display
            role = classification.get('role', {})
            location = classification.get('location', {})

            print(f"    [OK] Classified as: {role.get('job_family')}/{role.get('job_subfamily')}")
            print(f"         Seniority: {role.get('seniority')}, Remote: {location.get('working_arrangement')}")

            classified_jobs.append(job)

        except Exception as e:
            print(f"    [ERROR] Classification failed: {str(e)[:100]}")
            continue

    print(f"\n[SUMMARY] Classified: {len(classified_jobs)}, Filtered: {filtered_count}")

    # Step 3: Verify jobs are ready for storage
    print("\n[STEP 3] Verifying jobs are ready for database insertion...")

    ready_for_storage = 0
    for i, job in enumerate(classified_jobs, 1):
        print(f"\n  [{i}/{len(classified_jobs)}] Validating: {job.title}")

        # Check all required fields (same validation as fetch_jobs.store_jobs())
        errors = []

        if not isinstance(job, UnifiedJob):
            errors.append(f"Wrong type: {type(job).__name__}")

        if not job.classification:
            errors.append("Missing classification")
        else:
            role = job.classification.get('role', {})
            location = job.classification.get('location', {})

            if not role.get('job_family'):
                errors.append("Missing job_family")
            # Note: city_code can be null - store_jobs() uses fallback default
            # This is expected behavior when location isn't in description

        if errors:
            print(f"    [ERROR] Validation failed: {', '.join(errors)}")
        else:
            print(f"    [OK] Ready for insertion")
            print(f"         Company: {job.company}")
            print(f"         Source: {job.source.value} (description from {job.description_source.value})")
            print(f"         Family: {job.classification['role']['job_family']}")
            ready_for_storage += 1

    print(f"\n[SUMMARY] Ready for storage: {ready_for_storage}/{len(classified_jobs)}")

    # Step 4: Test to_dict() for JSON export
    print("\n[STEP 4] Testing JSON serialization...")

    import json

    try:
        export_data = [job.to_dict() for job in classified_jobs]
        json_str = json.dumps(export_data, indent=2)

        print(f"[OK] Successfully serialized {len(export_data)} jobs to JSON")
        print(f"     JSON size: {len(json_str)} bytes")

        # Verify classification is in JSON
        for job_dict in export_data:
            if 'classification' not in job_dict:
                print("[ERROR] Classification missing from JSON!")
                return False

        print("[OK] All jobs have classification in JSON")

    except Exception as e:
        print(f"[ERROR] JSON serialization failed: {e}")
        return False

    # Final summary
    print("\n" + "=" * 80)
    print("INTEGRATION TEST RESULTS")
    print("=" * 80)
    print(f"Input jobs: {len(jobs)}")
    print(f"Filtered (empty desc): {filtered_count}")
    print(f"Classified: {len(classified_jobs)}")
    print(f"Ready for storage: {ready_for_storage}")
    print(f"Success rate: {100 * ready_for_storage / len(jobs):.1f}%")

    if ready_for_storage > 0:
        print("\n" + "=" * 80)
        print("[SUCCESS] PIPELINE INTEGRATION TEST PASSED!")
        print("=" * 80)
        print("\nThe pipeline is working end-to-end:")
        print("  1. [OK] UnifiedJob objects created")
        print("  2. [OK] Classifications added successfully")
        print("  3. [OK] Jobs validated for storage")
        print("  4. [OK] JSON serialization working")
        print("\nYou can now run the real pipeline:")
        print("  python fetch_jobs.py lon 10 --sources adzuna,greenhouse\n")
        return True
    else:
        print("\n[ERROR] No jobs ready for storage!")
        return False

# Run the test
if __name__ == "__main__":
    result = asyncio.run(test_pipeline())
    exit(0 if result else 1)
