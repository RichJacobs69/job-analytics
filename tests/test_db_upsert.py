"""
Test insert_raw_job_upsert() function for incremental pipeline

Tests:
1. First insert creates new record
2. Second insert with same hash updates existing (deduplication)
3. Source priority: Greenhouse description overwrites Adzuna
4. Different city = different job (no deduplication)
"""
import sys
sys.path.insert(0, 'C:\\Cursor Projects\\job-analytics')

from pipeline.db_connection import insert_raw_job_upsert, supabase, generate_job_hash


def test_upsert_behavior():
    """Test UPSERT deduplication and source priority"""
    print("=" * 70)
    print("TESTING: insert_raw_job_upsert() - Incremental Pipeline Deduplication")
    print("=" * 70)

    # Test data
    test_company = "TestCorp_Upsert_12345"
    test_title = "Senior Data Engineer"
    test_city = "lon"

    all_tests_passed = True

    try:
        # ============================================
        # Test 1: First insert creates new record
        # ============================================
        print("\n[Test 1] First insert should create new record...")
        result1 = insert_raw_job_upsert(
            source='adzuna',
            posting_url='https://test.com/job1',
            title=test_title,
            company=test_company,
            raw_text='Short description from Adzuna (100 chars)',
            city_code=test_city,
            source_job_id='adzuna_123'
        )

        if result1['action'] == 'inserted' and not result1['was_duplicate']:
            print(f"  ✓ PASS: New record created (id={result1['id']})")
        else:
            print(f"  ✗ FAIL: Expected 'inserted', got '{result1['action']}'")
            all_tests_passed = False

        first_id = result1['id']

        # ============================================
        # Test 2: Second insert with same hash updates existing
        # ============================================
        print("\n[Test 2] Second insert with same company+title+city should update...")
        result2 = insert_raw_job_upsert(
            source='adzuna',
            posting_url='https://test.com/job1_updated',
            title=test_title,
            company=test_company,
            raw_text='Updated description from Adzuna',
            city_code=test_city,
            source_job_id='adzuna_123_v2'
        )

        if result2['id'] == first_id:
            print(f"  ✓ PASS: Same ID returned (id={result2['id']}) - deduplication working")
        else:
            print(f"  ✗ FAIL: Different ID returned - created duplicate!")
            all_tests_passed = False

        # ============================================
        # Test 3: Greenhouse overwrites Adzuna description
        # ============================================
        print("\n[Test 3] Greenhouse full description should overwrite Adzuna...")
        greenhouse_text = "Full job description from Greenhouse with 9000+ characters" * 100
        result3 = insert_raw_job_upsert(
            source='greenhouse',
            posting_url='https://greenhouse.io/testcorp/job1',
            title=test_title,
            company=test_company,
            raw_text=greenhouse_text,
            city_code=test_city,
            source_job_id='greenhouse_456'
        )

        if result3['id'] == first_id:
            print(f"  ✓ PASS: Same ID returned (id={result3['id']})")

            # Verify description was updated
            record = supabase.table('raw_jobs').select('raw_text').eq('id', first_id).execute()
            stored_text = record.data[0]['raw_text']

            if stored_text == greenhouse_text:
                print(f"  ✓ PASS: Description updated to Greenhouse version ({len(stored_text)} chars)")
            else:
                print(f"  ✗ FAIL: Description not updated correctly")
                all_tests_passed = False
        else:
            print(f"  ✗ FAIL: Different ID returned - should have updated existing")
            all_tests_passed = False

        # ============================================
        # Test 4: Different city = different job (no deduplication)
        # ============================================
        print("\n[Test 4] Same company+title but different city = separate job...")
        result4 = insert_raw_job_upsert(
            source='adzuna',
            posting_url='https://test.com/job_nyc',
            title=test_title,
            company=test_company,
            raw_text='Same job but in NYC',
            city_code='nyc',  # Different city
            source_job_id='adzuna_nyc_789'
        )

        if result4['id'] != first_id and result4['action'] == 'inserted':
            print(f"  ✓ PASS: New record created for NYC (id={result4['id']})")
        else:
            print(f"  ✗ FAIL: Should have created separate record for NYC")
            all_tests_passed = False

        nyc_id = result4['id']

        # ============================================
        # Test 5: Verify hash generation is consistent
        # ============================================
        print("\n[Test 5] Hash generation consistency...")
        hash1 = generate_job_hash(test_company, test_title, test_city)
        hash2 = generate_job_hash(test_company, test_title, test_city)

        if hash1 == hash2:
            print(f"  ✓ PASS: Hash generation consistent ({hash1})")
        else:
            print(f"  ✗ FAIL: Hash generation inconsistent")
            all_tests_passed = False

        # ============================================
        # Cleanup test records
        # ============================================
        print("\n[Cleanup] Removing test records...")
        deleted_count = 0
        for test_id in [first_id, nyc_id]:
            try:
                supabase.table('raw_jobs').delete().eq('id', test_id).execute()
                deleted_count += 1
            except:
                pass

        print(f"  ✓ Cleaned up {deleted_count} test records")

        # ============================================
        # Summary
        # ============================================
        print("\n" + "=" * 70)
        if all_tests_passed:
            print("✓ ALL TESTS PASSED - UPSERT function working correctly!")
        else:
            print("✗ SOME TESTS FAILED - Check errors above")
        print("=" * 70)

        return all_tests_passed

    except Exception as e:
        print(f"\n✗ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_upsert_behavior()
    exit(0 if success else 1)
