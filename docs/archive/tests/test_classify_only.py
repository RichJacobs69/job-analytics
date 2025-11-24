"""
Test 3: Classification Only
Purpose: Verify we can classify <10 merged jobs without errors
"""
import json
import sys
import io
from classifier import classify_job_with_claude
from agency_detection import detect_agency

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_classify():
    """Test classification of merged jobs"""

    print("=" * 70)
    print("TEST 3: CLASSIFICATION")
    print("=" * 70)

    # Load merged jobs
    print("\n[STEP 1] Loading merged jobs from test_merged_jobs.json...")
    try:
        with open('test_merged_jobs.json', 'r') as f:
            merged_data = json.load(f)
        print(f"[OK] Loaded {len(merged_data)} merged jobs\n")
    except FileNotFoundError:
        print("[ERROR] test_merged_jobs.json not found!")
        print("  Please run test_dedupe_only.py first\n")
        return

    # Load agency blacklist
    print("[STEP 2] Loading agency blacklist...")
    try:
        with open('config/agency_blacklist.yaml', 'r') as f:
            import yaml
            blacklist_config = yaml.safe_load(f)
        print(f"[OK] Loaded agency blacklist\n")
    except Exception as e:
        print(f"[WARN] Could not load agency blacklist: {e}\n")

    # Classify each job
    print("[STEP 3] Classifying jobs...")
    classified_results = []
    agencies_filtered = 0
    classification_success = 0
    classification_failed = 0

    for i, job_data in enumerate(merged_data, 1):
        company = job_data['company']
        title = job_data['title']
        description = job_data['description']

        print(f"\n  [{i}/{len(merged_data)}] {company} - {title[:40]}...")

        # Step 1: Check agency filter
        try:
            is_agency, reason = detect_agency(company, description)
            if is_agency:
                print(f"    [FILTERED] Agency detected: {reason}")
                agencies_filtered += 1
                continue
        except Exception as e:
            print(f"    [WARN] Agency check failed: {str(e)[:50]}")

        # Step 2: Classify with Claude
        try:
            classification = classify_job_with_claude(description, verbose=False)

            # Extract key fields
            role = classification.get('role', {})
            location = classification.get('location', {})
            skills = classification.get('skills', [])

            classified_results.append({
                'company': company,
                'title': title,
                'job_family': role.get('job_family'),
                'job_subfamily': role.get('job_subfamily'),
                'seniority': role.get('seniority'),
                'working_arrangement': location.get('working_arrangement'),
                'skills_count': len(skills),
                'full_classification': classification
            })

            print(f"    [OK] Classified as {role.get('job_family')}/{role.get('job_subfamily')}")
            print(f"         Seniority: {role.get('seniority')}, Remote: {location.get('working_arrangement')}")
            print(f"         Skills: {len(skills)}")
            classification_success += 1

        except Exception as e:
            error_msg = str(e)[:100]
            print(f"    [ERROR] Classification failed: {error_msg}")
            classified_results.append({
                'company': company,
                'title': title,
                'error': error_msg
            })
            classification_failed += 1

    # Summary
    print("\n" + "=" * 70)
    print("[STEP 4] Summary")
    print("=" * 70)
    print(f"Total jobs processed: {len(merged_data)}")
    print(f"  - Filtered as agencies: {agencies_filtered}")
    print(f"  - Successfully classified: {classification_success}")
    print(f"  - Classification failed: {classification_failed}\n")

    # Save results
    print("[STEP 5] Saving classified results to test_classified_jobs.json...")
    with open('test_classified_jobs.json', 'w') as f:
        json.dump(classified_results, f, indent=2)
    print(f"[OK] Saved {len(classified_results)} results\n")

    print("=" * 70)
    print("TEST 3 COMPLETE - CLASSIFICATION TESTED")
    print("=" * 70)

if __name__ == '__main__':
    test_classify()
