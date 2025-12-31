"""
Tests for inline summary generation feature.

Tests the new architecture where summaries are generated inline during
classification instead of via a separate batch job.

Changes tested:
1. classifier.py now outputs a 'summary' field in its JSON response
2. db_connection.py insert_enriched_job() accepts a summary parameter
3. fetch_jobs.py passes classification.get('summary') to insert_enriched_job()
"""
import sys
sys.path.insert(0, 'C:\\Cursor Projects\\job-analytics')

import pytest
from unittest.mock import patch, MagicMock
from datetime import date


class TestClassifierSummaryOutput:
    """Unit tests for classifier.py summary generation"""

    def test_classifier_output_includes_summary_field(self):
        """Classifier should include 'summary' field in output"""
        from pipeline.classifier import classify_job

        # Use a real job description to test
        test_job = """
        Senior Data Engineer
        Acme Corp - London, UK
        Full-time - Hybrid

        We're looking for a Senior Data Engineer to build our data platform.

        You will:
        - Design and build data pipelines using Python and Spark
        - Work with our Data Science team on ML infrastructure
        - Maintain our Snowflake data warehouse

        Requirements:
        - 5+ years experience with Python, SQL
        - Experience with Spark, Airflow
        - Strong communication skills

        Salary: GBP 80,000 - 110,000
        """

        # Call classifier
        result = classify_job(test_job, verbose=False)

        # Verify summary field exists
        assert 'summary' in result, "Classifier output should include 'summary' field"

        # Verify summary is a non-empty string
        summary = result.get('summary')
        assert summary is not None, "Summary should not be None"
        assert isinstance(summary, str), "Summary should be a string"
        assert len(summary) > 20, f"Summary should be meaningful, got: {summary}"
        assert len(summary) < 500, f"Summary should be concise (<500 chars), got {len(summary)} chars"

        print(f"[OK] Summary generated: {summary[:100]}...")

    def test_classifier_summary_content_quality(self):
        """Summary should describe day-to-day work, not be generic"""
        from pipeline.classifier import classify_job

        test_job = """
        Product Manager - Payments
        FinTech Company - New York

        Lead product strategy for our payments platform serving 10M users.

        Responsibilities:
        - Define product roadmap for payment processing features
        - Work with engineering to ship new payment methods
        - Analyze user data to improve conversion rates
        - Collaborate with compliance team on regulations

        Requirements:
        - 4+ years product management experience
        - Payments or fintech background preferred
        """

        result = classify_job(test_job, verbose=False)
        summary = result.get('summary', '')

        # Check summary doesn't contain generic phrases
        generic_phrases = [
            'exciting opportunity',
            'fast-paced environment',
            'dynamic team',
            'passionate individuals'
        ]

        summary_lower = summary.lower()
        for phrase in generic_phrases:
            assert phrase not in summary_lower, f"Summary contains generic phrase: '{phrase}'"

        # Check summary mentions specific context
        # At least one of these domain-specific terms should appear
        domain_terms = ['payment', 'product', 'roadmap', 'user', 'engineering', 'feature']
        has_domain_term = any(term in summary_lower for term in domain_terms)
        assert has_domain_term, f"Summary should mention domain-specific terms. Got: {summary}"

        print(f"[OK] Summary quality check passed: {summary}")


class TestDbConnectionSummaryParam:
    """Unit tests for db_connection.py summary parameter"""

    def test_insert_enriched_job_accepts_summary_param(self):
        """insert_enriched_job should accept summary parameter without error"""
        from pipeline.db_connection import insert_enriched_job
        import inspect

        # Check function signature includes summary param
        sig = inspect.signature(insert_enriched_job)
        param_names = list(sig.parameters.keys())

        assert 'summary' in param_names, "insert_enriched_job should have 'summary' parameter"

        # Verify it's optional (has default value)
        summary_param = sig.parameters['summary']
        assert summary_param.default is None, "summary parameter should default to None"

        print("[OK] insert_enriched_job accepts summary parameter")

    def test_insert_enriched_job_with_summary(self):
        """insert_enriched_job should store summary in database"""
        from pipeline.db_connection import insert_enriched_job, supabase, generate_job_hash

        # Create test data
        test_company = "TestCorp_Summary_12345"
        test_title = "Data Engineer"
        test_city = "lon"
        test_summary = "Build data pipelines using Python and Spark. Work with ML team on infrastructure."

        try:
            # First, create a raw_job record (required for foreign key)
            raw_result = supabase.table('raw_jobs').insert({
                'source': 'test',
                'posting_url': 'https://test.com/summary_test',
                'raw_text': 'Test job description',
                'title': test_title,
                'company': test_company,
            }).execute()
            raw_job_id = raw_result.data[0]['id']

            # Insert enriched job with summary
            enriched_job_id = insert_enriched_job(
                raw_job_id=raw_job_id,
                employer_name=test_company,
                title_display=test_title,
                job_family='data',
                city_code=test_city,
                working_arrangement='hybrid',
                position_type='full_time',
                posted_date=date.today(),
                last_seen_date=date.today(),
                job_subfamily='data_engineer',
                summary=test_summary,  # NEW: Pass summary
                data_source='test',
                description_source='test'
            )

            # Verify summary was stored
            result = supabase.table('enriched_jobs').select('summary').eq('id', enriched_job_id).execute()
            stored_summary = result.data[0].get('summary')

            assert stored_summary == test_summary, f"Stored summary doesn't match. Expected: {test_summary}, Got: {stored_summary}"
            print(f"[OK] Summary stored correctly (enriched_job_id={enriched_job_id})")

        finally:
            # Cleanup
            try:
                if 'enriched_job_id' in locals():
                    supabase.table('enriched_jobs').delete().eq('id', enriched_job_id).execute()
                if 'raw_job_id' in locals():
                    supabase.table('raw_jobs').delete().eq('id', raw_job_id).execute()
                print("[OK] Cleanup completed")
            except Exception as e:
                print(f"[WARN] Cleanup error: {e}")

    def test_insert_enriched_job_without_summary(self):
        """insert_enriched_job should work without summary (backward compatibility)"""
        from pipeline.db_connection import insert_enriched_job, supabase

        test_company = "TestCorp_NoSummary_12345"
        test_title = "Product Manager"
        test_city = "nyc"

        try:
            # Create raw_job record
            raw_result = supabase.table('raw_jobs').insert({
                'source': 'test',
                'posting_url': 'https://test.com/no_summary_test',
                'raw_text': 'Test job description',
                'title': test_title,
                'company': test_company,
            }).execute()
            raw_job_id = raw_result.data[0]['id']

            # Insert WITHOUT summary (backward compatibility)
            enriched_job_id = insert_enriched_job(
                raw_job_id=raw_job_id,
                employer_name=test_company,
                title_display=test_title,
                job_family='product',
                city_code=test_city,
                working_arrangement='remote',
                position_type='full_time',
                posted_date=date.today(),
                last_seen_date=date.today(),
                # summary NOT provided - should default to None
                data_source='test',
                description_source='test'
            )

            # Verify record was created
            result = supabase.table('enriched_jobs').select('id, summary').eq('id', enriched_job_id).execute()
            assert len(result.data) == 1, "Record should be created"
            assert result.data[0]['summary'] is None, "Summary should be None when not provided"

            print(f"[OK] Backward compatibility maintained (enriched_job_id={enriched_job_id})")

        finally:
            # Cleanup
            try:
                if 'enriched_job_id' in locals():
                    supabase.table('enriched_jobs').delete().eq('id', enriched_job_id).execute()
                if 'raw_job_id' in locals():
                    supabase.table('raw_jobs').delete().eq('id', raw_job_id).execute()
            except:
                pass


class TestPipelineIntegration:
    """Integration tests for summary flow through pipeline"""

    def test_classification_dict_has_summary_key(self):
        """Classification result dict should have 'summary' key for pipeline to extract"""
        from pipeline.classifier import classify_job

        test_job = """
        ML Engineer
        AI Startup - San Francisco
        Build and deploy machine learning models at scale.
        Requirements: Python, TensorFlow, MLOps experience.
        """

        classification = classify_job(test_job, verbose=False)

        # This is what fetch_jobs.py uses
        summary = classification.get('summary')

        assert summary is not None, "classification.get('summary') should return a value"
        assert isinstance(summary, str), "Summary should be a string"

        print(f"[OK] classification.get('summary') works: {summary[:50]}...")


class TestSummaryGeneratorBackfill:
    """Tests for summary_generator.py as backfill utility"""

    def test_summary_generator_includes_ashby(self):
        """summary_generator.py should include Ashby in data_source filter"""
        from pipeline.summary_generator import generate_summaries
        import inspect

        # Read the source to verify Ashby is included
        source = inspect.getsource(generate_summaries)

        assert 'ashby' in source.lower(), "summary_generator should include 'ashby' in data_source filter"
        print("[OK] summary_generator.py includes Ashby")


def run_all_tests():
    """Run all tests and report results"""
    print("=" * 70)
    print("INLINE SUMMARY GENERATION TESTS")
    print("=" * 70)

    all_passed = True

    # Test 1: Classifier output
    print("\n[TEST 1] Classifier Summary Output")
    print("-" * 40)
    try:
        test = TestClassifierSummaryOutput()
        test.test_classifier_output_includes_summary_field()
    except Exception as e:
        print(f"[FAIL] {e}")
        all_passed = False

    # Test 2: Summary quality
    print("\n[TEST 2] Summary Content Quality")
    print("-" * 40)
    try:
        test = TestClassifierSummaryOutput()
        test.test_classifier_summary_content_quality()
    except Exception as e:
        print(f"[FAIL] {e}")
        all_passed = False

    # Test 3: DB function signature
    print("\n[TEST 3] DB Function Signature")
    print("-" * 40)
    try:
        test = TestDbConnectionSummaryParam()
        test.test_insert_enriched_job_accepts_summary_param()
    except Exception as e:
        print(f"[FAIL] {e}")
        all_passed = False

    # Test 4: DB insert with summary
    print("\n[TEST 4] DB Insert With Summary")
    print("-" * 40)
    try:
        test = TestDbConnectionSummaryParam()
        test.test_insert_enriched_job_with_summary()
    except Exception as e:
        print(f"[FAIL] {e}")
        all_passed = False

    # Test 5: Backward compatibility
    print("\n[TEST 5] Backward Compatibility (No Summary)")
    print("-" * 40)
    try:
        test = TestDbConnectionSummaryParam()
        test.test_insert_enriched_job_without_summary()
    except Exception as e:
        print(f"[FAIL] {e}")
        all_passed = False

    # Test 6: Pipeline integration
    print("\n[TEST 6] Pipeline Integration")
    print("-" * 40)
    try:
        test = TestPipelineIntegration()
        test.test_classification_dict_has_summary_key()
    except Exception as e:
        print(f"[FAIL] {e}")
        all_passed = False

    # Test 7: Ashby support
    print("\n[TEST 7] Ashby Support in Summary Generator")
    print("-" * 40)
    try:
        test = TestSummaryGeneratorBackfill()
        test.test_summary_generator_includes_ashby()
    except Exception as e:
        print(f"[FAIL] {e}")
        all_passed = False

    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("[OK] ALL TESTS PASSED")
    else:
        print("[FAIL] SOME TESTS FAILED - see above")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
