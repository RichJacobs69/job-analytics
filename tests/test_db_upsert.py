"""
Test insert_raw_job_upsert() function for incremental pipeline

NOTE: This is a live integration test that hits Supabase.
Run with: pytest tests/test_db_upsert.py -m integration -v

Tests:
1. First insert creates new record
2. Second insert with same hash updates existing (deduplication)
3. Source priority: Greenhouse description overwrites Adzuna
4. Different city = different job (no deduplication)
5. Hash generation consistency
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.db_connection import insert_raw_job_upsert, supabase, generate_job_hash


@pytest.mark.integration
class TestUpsertBehavior:
    """Test UPSERT deduplication and source priority (live Supabase)"""

    def test_upsert_full_lifecycle(self):
        """Test insert, update, source priority, and city separation"""
        test_company = "TestCorp_Upsert_12345"
        test_title = "Senior Data Engineer"
        test_city = "lon"
        nyc_id = None

        try:
            # Test 1: First insert creates new record
            result1 = insert_raw_job_upsert(
                source='adzuna',
                posting_url='https://test.com/job1',
                title=test_title,
                company=test_company,
                raw_text='Short description from Adzuna (100 chars)',
                city_code=test_city,
                source_job_id='adzuna_123'
            )
            assert result1['action'] == 'inserted'
            assert not result1['was_duplicate']
            first_id = result1['id']

            # Test 2: Second insert with same hash updates existing
            result2 = insert_raw_job_upsert(
                source='adzuna',
                posting_url='https://test.com/job1_updated',
                title=test_title,
                company=test_company,
                raw_text='Updated description from Adzuna',
                city_code=test_city,
                source_job_id='adzuna_123_v2'
            )
            assert result2['id'] == first_id

            # Test 3: Greenhouse overwrites Adzuna description
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
            assert result3['id'] == first_id

            record = supabase.table('raw_jobs').select('raw_text').eq('id', first_id).execute()
            assert record.data[0]['raw_text'] == greenhouse_text

            # Test 4: Different city = different job
            result4 = insert_raw_job_upsert(
                source='adzuna',
                posting_url='https://test.com/job_nyc',
                title=test_title,
                company=test_company,
                raw_text='Same job but in NYC',
                city_code='nyc',
                source_job_id='adzuna_nyc_789'
            )
            assert result4['id'] != first_id
            assert result4['action'] == 'inserted'
            nyc_id = result4['id']

            # Test 5: Hash generation consistency
            hash1 = generate_job_hash(test_company, test_title, test_city)
            hash2 = generate_job_hash(test_company, test_title, test_city)
            assert hash1 == hash2

        finally:
            # Cleanup
            for test_id in [first_id, nyc_id]:
                if test_id:
                    try:
                        supabase.table('raw_jobs').delete().eq('id', test_id).execute()
                    except Exception:
                        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
