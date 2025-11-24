"""
Quick test to verify UnifiedJob classification field fix

This tests that:
1. UnifiedJob can accept a classification field
2. Classification persists correctly
3. to_dict() handles classification properly
"""

from unified_job_ingester import UnifiedJob, DataSource
from datetime import datetime

print("=" * 80)
print("TESTING UNIFIEDJOB CLASSIFICATION FIELD FIX")
print("=" * 80)

# Test 1: Create a UnifiedJob
print("\n[TEST 1] Creating UnifiedJob instance...")
job = UnifiedJob(
    company="Test Corp",
    title="Senior Data Engineer",
    location="London",
    description="This is a test job description with more than 50 characters to pass the filter.",
    url="https://test.com/job/123",
    source=DataSource.GREENHOUSE,
    description_source=DataSource.GREENHOUSE
)
print("[OK] UnifiedJob created successfully")

# Test 2: Add classification
print("\n[TEST 2] Adding classification to job...")
test_classification = {
    "employer": {
        "name": "Test Corp",
        "department": "data",
        "company_size_estimate": "scaleup"
    },
    "role": {
        "title_display": "Senior Data Engineer",
        "job_family": "data",
        "job_subfamily": "data_engineer",
        "seniority": "senior",
        "track": "ic",
        "position_type": "full_time",
        "experience_range": "5-7 years"
    },
    "location": {
        "city_code": "lon",
        "working_arrangement": "hybrid"
    },
    "compensation": {
        "currency": "gbp",
        "base_salary_range": {
            "min": 70000,
            "max": 90000
        },
        "equity_eligible": True
    },
    "skills": [
        {"name": "Python", "family_code": "programming"},
        {"name": "SQL", "family_code": "programming"},
        {"name": "Spark", "family_code": "big_data"}
    ]
}

try:
    job.classification = test_classification
    print("[OK] Classification added successfully")
except Exception as e:
    print(f"[ERROR] Failed to add classification: {e}")
    exit(1)

# Test 3: Verify classification persists
print("\n[TEST 3] Verifying classification persists...")
if job.classification is None:
    print("[ERROR] Classification is None!")
    exit(1)
elif job.classification == test_classification:
    print("[OK] Classification matches expected value")
else:
    print("[ERROR] Classification doesn't match!")
    exit(1)

# Test 4: Test to_dict() method
print("\n[TEST 4] Testing to_dict() method...")
try:
    job_dict = job.to_dict()
    print("[OK] to_dict() executed successfully")

    # Verify classification is in dict
    if 'classification' in job_dict:
        print("[OK] Classification found in dict output")
        print(f"  Job Family: {job_dict['classification']['role']['job_family']}")
        print(f"  Subfamily: {job_dict['classification']['role']['job_subfamily']}")
        print(f"  Seniority: {job_dict['classification']['role']['seniority']}")
    else:
        print("[ERROR] Classification not in dict output!")
        exit(1)

except Exception as e:
    print(f"[ERROR] to_dict() failed: {e}")
    exit(1)

# Test 5: Test with None classification (should be allowed)
print("\n[TEST 5] Testing with None classification...")
job2 = UnifiedJob(
    company="Test Corp 2",
    title="Data Analyst",
    location="New York",
    description="Another test job",
    url="https://test.com/job/124",
    source=DataSource.ADZUNA
)

if job2.classification is None:
    print("[OK] Default classification is None (as expected)")
else:
    print(f"[ERROR] Default classification should be None, got: {job2.classification}")
    exit(1)

# Test 6: Test JSON serialization
print("\n[TEST 6] Testing JSON serialization...")
import json
try:
    json_str = json.dumps(job.to_dict(), indent=2)
    print("[OK] JSON serialization successful")
    print(f"  JSON length: {len(json_str)} characters")
except Exception as e:
    print(f"[ERROR] JSON serialization failed: {e}")
    exit(1)

# Summary
print("\n" + "=" * 80)
print("ALL TESTS PASSED!")
print("=" * 80)
print("\nThe UnifiedJob classification field fix is working correctly.")
print("You can now:")
print("  1. Run the dual pipeline: python fetch_jobs.py lon 10 --sources adzuna,greenhouse")
print("  2. Classifications will be stored in the UnifiedJob.classification field")
print("  3. Jobs with empty descriptions (<50 chars) will be filtered out")
print("  4. Database insertion should work without manual workarounds\n")
